"""Bounded discrete-event simulation of a FIFO queue and shared worker pool.

Events run in [0, horizon); measurements use [warmup, horizon). At a tie,
completions dispatch existing waiters before timeouts, followed by arrivals and
retries in insertion order. A waiter can start exactly at its timeout deadline.
Retries release the worker, then face queue capacity and timeout again.
"""

from __future__ import annotations

import heapq
import itertools
import math
import random
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from .base import require_only_fields
from .protocol import AnalysisResult, JsonValue

MAX_ARRIVALS = 100_000
MAX_EVENTS = 1_000_000
MAX_SERVERS = 10_000
MAX_RETRIES = 100
MAX_INPUT_TIME = 1e12
REQUEST_FIELDS = {
    "arrivals",
    "service_time",
    "servers",
    "horizon",
    "warmup",
    "seed",
    "waiting_capacity",
    "wait_timeout",
    "failure_probability",
    "max_retries",
    "retry_delay",
    "max_events",
}
TERMINAL_STATES = ("completed", "failed", "rejected", "timed_out")
COUNT_NAMES = (
    "arrivals",
    *TERMINAL_STATES,
    "attempts_started",
    "attempts_failed",
    "retries_scheduled",
)


class SystemSimulationValidationError(ValueError):
    """Raised when a simulation request or its execution is unsafe."""


def _object(value: object, allowed: set[str], label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise SystemSimulationValidationError(f"{label} must be an object")
    require_only_fields(
        value,
        allowed,
        label=label,
        error_type=SystemSimulationValidationError,
    )
    return value


def _number(value: object, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SystemSimulationValidationError(f"{label} must be a finite number")
    try:
        number = float(value)
    except OverflowError as error:
        raise SystemSimulationValidationError(f"{label} must be finite") from error
    if not math.isfinite(number) or not 0 <= number <= MAX_INPUT_TIME:
        raise SystemSimulationValidationError(f"{label} must be between 0 and {MAX_INPUT_TIME}")
    if positive and number == 0:
        raise SystemSimulationValidationError(f"{label} must be positive")
    return number


def _integer(value: object, label: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise SystemSimulationValidationError(f"{label} must be an integer from {low} to {high}")
    return value


def _duration(value: object, label: str) -> Callable[[random.Random], float]:
    if not isinstance(value, Mapping):
        number = _number(value, label, positive=True)
        return lambda rng: number
    kind = value.get("distribution")
    fields = {
        "constant": {"distribution", "value"},
        "uniform": {"distribution", "low", "high"},
        "exponential": {"distribution", "mean"},
    }
    if not isinstance(kind, str) or kind not in fields:
        raise SystemSimulationValidationError(
            f"{label}.distribution must be constant, uniform, or exponential"
        )
    spec = _object(value, fields[kind], label)
    if kind == "constant":
        number = _number(spec.get("value"), f"{label}.value", positive=True)
        return lambda rng: number
    if kind == "uniform":
        low = _number(spec.get("low"), f"{label}.low", positive=True)
        high = _number(spec.get("high"), f"{label}.high", positive=True)
        if high < low:
            raise SystemSimulationValidationError(f"{label}.high must be at least low")
        return lambda rng: rng.uniform(low, high)
    mean = _number(spec.get("mean"), f"{label}.mean", positive=True)
    # log1p avoids cancellation for small random draws; zero draws are rejected
    # by _advance, as are increments lost at the current timestamp's precision.
    return lambda rng: -math.log1p(-rng.random()) * mean


def _advance(now: float, delay: float, label: str, *, allow_zero: bool = False) -> float:
    later = now + delay
    if not math.isfinite(delay) or not math.isfinite(later):
        raise SystemSimulationValidationError(f"{label} produced a non-finite timestamp")
    if delay < 0 or (later <= now and not (allow_zero and delay == 0)):
        raise SystemSimulationValidationError(f"{label} does not advance time at float precision")
    return later


def _arrival_times(value: object, rng: random.Random) -> list[float]:
    spec = _object(value, {"times", "count", "start", "interarrival"}, "arrivals")
    if "times" in spec:
        _object(spec, {"times"}, "arrivals")
        raw = spec["times"]
        if not isinstance(raw, list) or len(raw) > MAX_ARRIVALS:
            raise SystemSimulationValidationError(
                f"arrivals.times must be a list with at most {MAX_ARRIVALS} entries"
            )
        times = [_number(t, f"arrivals.times[{i}]") for i, t in enumerate(raw)]
        if any(a > b for a, b in itertools.pairwise(times)):
            raise SystemSimulationValidationError("arrivals.times must be sorted")
        return times
    count = _integer(spec.get("count"), "arrivals.count", 0, MAX_ARRIVALS)
    now = _number(spec.get("start", 0), "arrivals.start")
    sampler = _duration(spec.get("interarrival"), "arrivals.interarrival")
    times = []
    for index in range(count):
        if index:
            now = _advance(now, sampler(rng), "arrivals.interarrival")
        times.append(now)
    return times


@dataclass(slots=True)
class _Job:
    arrival: float
    entered_queue: float
    status: str = "new"
    attempts: int = 0


@dataclass(slots=True)
class _Delay:
    count: int = 0
    total: float = 0.0
    maximum: float = 0.0

    def add(self, duration: float) -> None:
        self.count += 1
        self.total += duration
        self.maximum = max(self.maximum, duration)
        if not math.isfinite(self.total):
            raise SystemSimulationValidationError("delay aggregate overflowed")

    def result(self) -> dict[str, JsonValue]:
        return {
            "count": self.count,
            "total": self.total,
            "mean": self.total / self.count if self.count else None,
            "maximum": self.maximum if self.count else None,
        }


class _Simulation:
    def __init__(self, request: Mapping[str, object]) -> None:
        spec = _object(request, REQUEST_FIELDS, "request")
        self.horizon = _number(spec.get("horizon"), "horizon", positive=True)
        self.warmup = _number(spec.get("warmup", 0), "warmup")
        if self.warmup >= self.horizon:
            raise SystemSimulationValidationError("warmup must be less than horizon")
        self.servers = _integer(spec.get("servers"), "servers", 1, MAX_SERVERS)
        self.capacity = _integer(
            spec.get("waiting_capacity", MAX_ARRIVALS),
            "waiting_capacity",
            0,
            MAX_ARRIVALS,
        )
        self.max_events = _integer(spec.get("max_events", MAX_EVENTS), "max_events", 1, MAX_EVENTS)
        self.max_retries = _integer(spec.get("max_retries", 0), "max_retries", 0, MAX_RETRIES)
        self.seed = _integer(spec.get("seed", 0), "seed", -(2**63), 2**63 - 1)
        self.failure_probability = _number(
            spec.get("failure_probability", 0),
            "failure_probability",
        )
        if self.failure_probability > 1:
            raise SystemSimulationValidationError("failure_probability must be between 0 and 1")
        self.retry_delay = _number(spec.get("retry_delay", 0), "retry_delay")
        self.timeout = (
            _number(spec["wait_timeout"], "wait_timeout", positive=True)
            if "wait_timeout" in spec
            else None
        )
        self.service = _duration(spec.get("service_time"), "service_time")
        self.rng = random.Random(self.seed)
        times = _arrival_times(spec.get("arrivals"), self.rng)
        self.requested_arrivals = len(times)
        self.jobs: list[_Job] = []
        self.events: list[tuple[float, int, int, str, int, int]] = []
        self.sequence = itertools.count()
        self.queue: deque[tuple[int, int]] = deque()
        self.waiting = self.busy = self.processed = 0
        self.counts = dict.fromkeys(COUNT_NAMES, 0)
        self.observed = dict.fromkeys(COUNT_NAMES, 0)
        self.initial_unfinished: int | None = None
        self.response = _Delay()
        self.wait = _Delay()
        self.queue_area = self.busy_area = self.now = 0.0
        for time in times:
            if time < self.horizon:
                job_id = len(self.jobs)
                self.jobs.append(_Job(time, time))
                self.schedule(time, "arrival", job_id)

    def schedule(self, time: float, kind: str, job_id: int, token: int = 0) -> None:
        priority = 0 if kind == "completion" else 1 if kind == "timeout" else 2
        heapq.heappush(self.events, (time, priority, next(self.sequence), kind, job_id, token))

    def count(self, name: str) -> None:
        self.counts[name] += 1
        if self.now >= self.warmup:
            self.observed[name] += 1

    def start(self, job_id: int) -> None:
        job = self.jobs[job_id]
        finish = _advance(self.now, self.service(self.rng), "service_time")
        if self.now >= self.warmup:
            self.wait.add(self.now - job.entered_queue)
        job.status = "in_service"
        job.attempts += 1
        self.busy += 1
        self.count("attempts_started")
        self.schedule(finish, "completion", job_id)

    def dispatch(self) -> None:
        while self.busy < self.servers and self.queue:
            job_id, token = self.queue.popleft()
            job = self.jobs[job_id]
            if job.status == "waiting" and job.attempts == token:
                self.waiting -= 1
                self.start(job_id)

    def admit(self, job_id: int) -> None:
        job = self.jobs[job_id]
        job.entered_queue = self.now
        if self.busy < self.servers:
            self.start(job_id)
        elif self.waiting >= self.capacity:
            job.status = "rejected"
            self.count("rejected")
        else:
            job.status = "waiting"
            self.waiting += 1
            self.queue.append((job_id, job.attempts))
            if self.timeout is not None:
                deadline = _advance(self.now, self.timeout, "wait_timeout")
                self.schedule(deadline, "timeout", job_id, job.attempts)

    def complete(self, job_id: int) -> None:
        job = self.jobs[job_id]
        self.busy -= 1
        if self.rng.random() < self.failure_probability:
            self.count("attempts_failed")
            if job.attempts <= self.max_retries:
                job.status = "retrying"
                self.count("retries_scheduled")
                retry = _advance(self.now, self.retry_delay, "retry_delay", allow_zero=True)
                self.schedule(retry, "retry", job_id)
            else:
                job.status = "failed"
                self.count("failed")
        else:
            job.status = "completed"
            self.count("completed")
            if self.now >= self.warmup:
                self.response.add(self.now - job.arrival)
        self.dispatch()

    def integrate(self, until: float) -> None:
        elapsed = max(0.0, until - max(self.now, self.warmup))
        self.queue_area += self.waiting * elapsed
        self.busy_area += self.busy * elapsed
        if not math.isfinite(self.queue_area) or not math.isfinite(self.busy_area):
            raise SystemSimulationValidationError("time-weighted aggregate overflowed")
        self.now = until

    def active_count(self) -> int:
        return self.counts["arrivals"] - sum(self.counts[name] for name in TERMINAL_STATES)

    def run(self) -> AnalysisResult:
        while self.events and self.events[0][0] < self.horizon:
            if self.processed >= self.max_events:
                raise SystemSimulationValidationError(
                    f"max_events exhausted after {self.processed} events at time {self.now}; "
                    "no complete result is available"
                )
            time, _, _, kind, job_id, token = heapq.heappop(self.events)
            if self.initial_unfinished is None and time >= self.warmup:
                self.initial_unfinished = self.active_count()
            self.integrate(time)
            self.processed += 1
            job = self.jobs[job_id]
            if kind == "completion":
                self.complete(job_id)
            elif kind == "timeout":
                if job.status == "waiting" and job.attempts == token:
                    job.status = "timed_out"
                    self.waiting -= 1
                    self.count("timed_out")
            else:
                if kind == "arrival":
                    self.count("arrivals")
                self.admit(job_id)
        if self.initial_unfinished is None:
            self.initial_unfinished = self.active_count()
        self.integrate(self.horizon)
        return self.result()

    def result(self) -> AnalysisResult:
        duration = self.horizon - self.warmup
        unfinished = {name: 0 for name in ("waiting", "in_service", "retrying")}
        for job in self.jobs:
            if job.status in unfinished:
                unfinished[job.status] += 1
        active = sum(unfinished.values())
        terminal = sum(self.counts[name] for name in TERMINAL_STATES)
        observed_terminal = sum(self.observed[name] for name in TERMINAL_STATES)
        metrics = {
            "throughput": self.observed["completed"] / duration,
            "average_queue_length": self.queue_area / duration,
            "utilization": self.busy_area / (self.servers * duration),
        }
        if not all(math.isfinite(value) for value in metrics.values()):
            raise SystemSimulationValidationError("derived simulation metrics must be finite")
        return AnalysisResult(
            engine=SystemSimulationEngine.name,
            capabilities=SystemSimulationEngine.capabilities,
            data={
                "counts": {**self.counts, "unfinished": active},
                "unfinished": unfinished,
                "observation": {
                    "start": self.warmup,
                    "end": self.horizon,
                    "duration": duration,
                    "counts": self.observed,
                    "unfinished_at_start": self.initial_unfinished,
                    "unfinished_at_end": active,
                },
                **metrics,
                "integrals": {"queue_time": self.queue_area, "busy_server_time": self.busy_area},
                "delays": {
                    "completed_response_time": self.response.result(),
                    "started_attempt_wait": self.wait.result(),
                },
                "conservation": {
                    "arrivals": self.counts["arrivals"],
                    "terminal": terminal,
                    "unfinished": active,
                    "balanced": self.counts["arrivals"] == terminal + active,
                    "observation_balanced": (
                        self.initial_unfinished + self.observed["arrivals"]
                        == observed_terminal + active
                    ),
                },
            },
            metadata={
                "seed": self.seed,
                "servers": self.servers,
                "events_processed": self.processed,
                "max_events": self.max_events,
                "requested_arrivals": self.requested_arrivals,
                "arrivals_at_or_after_horizon": self.requested_arrivals - len(self.jobs),
                "time_interval": "events [0, horizon); measurements [warmup, horizon)",
                "tie_order": (
                    "completion and FIFO dispatch, timeout, arrival/retry in insertion order"
                ),
                "retry_policy": (
                    "release worker; rejoin FIFO after delay; capacity and timeout apply anew"
                ),
                "throughput_denominator": (
                    "observation.duration; numerator: successful completions in window"
                ),
                "utilization_denominator": "servers * observation.duration",
                "queue_length_denominator": "observation.duration",
                "response_time_population": (
                    "jobs successfully completed in window, including arrivals before warmup"
                ),
                "wait_time_population": (
                    "attempts started in window, including zero waits and waits before warmup"
                ),
                "censoring": (
                    "unfinished jobs excluded from response time; "
                    "unstarted visits excluded from wait time"
                ),
                "randomness": (
                    "one seeded stream; interarrivals first, "
                    "then service at start and failure at completion"
                ),
            },
        )


class SystemSimulationEngine:
    """Simulate finite arrivals without a daemon or executable model scripts."""

    name = "system_simulation"
    capabilities = ("simulation.discrete_event", "simulation.queue")

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    def example_request(self) -> dict[str, object]:
        return {
            "arrivals": {"times": [0, 1, 2]},
            "service_time": 2,
            "servers": 1,
            "horizon": 7,
            "seed": 0,
        }

    def analyze(self, request: Mapping[str, object]) -> AnalysisResult:
        return _Simulation(request).run()
