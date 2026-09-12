"""Hand-calculated queue schedules and safety contracts."""

import copy
import json

import pytest

from pearl_of_wisdom.engines.protocol import AnalysisEngine
from pearl_of_wisdom.engines.system_simulation import (
    MAX_ARRIVALS,
    SystemSimulationEngine,
    SystemSimulationValidationError,
)


def run(**changes):
    request = SystemSimulationEngine().example_request()
    request.update(changes)
    return SystemSimulationEngine().analyze(request)


def test_fifo_schedule_has_exact_delay_and_time_averages():
    result = (
        SystemSimulationEngine()
        .analyze(
            {
                "arrivals": {"times": [0, 1, 2]},
                "service_time": 2,
                "servers": 1,
                "horizon": 7,
            }
        )
        .data
    )

    # Starts 0, 2, 4; finishes 2, 4, 6. Queue area is 1 + 2 = 3.
    assert result["counts"]["arrivals"] == result["counts"]["completed"] == 3
    assert result["counts"]["unfinished"] == 0
    assert result["delays"]["completed_response_time"] == {
        "count": 3,
        "total": 9.0,
        "mean": 3.0,
        "maximum": 4.0,
    }
    assert result["delays"]["started_attempt_wait"]["mean"] == 1
    assert result["average_queue_length"] == pytest.approx(3 / 7)
    assert result["utilization"] == pytest.approx(6 / 7)
    assert result["throughput"] == pytest.approx(3 / 7)


def test_engine_contract_and_fresh_example():
    engine = SystemSimulationEngine()
    assert isinstance(engine, AnalysisEngine)
    assert engine.name == "system_simulation"
    assert engine.supports("simulation.discrete_event")
    assert not engine.supports("simulation.monte_carlo")
    first = engine.example_request()
    first["arrivals"]["times"].append(100)
    assert engine.example_request()["arrivals"]["times"] == [0, 1, 2]
    json.dumps(engine.analyze(engine.example_request()).to_dict(), allow_nan=False)


def test_shared_workers_capacity_and_fifo():
    data = run(
        arrivals={"times": [0, 0, 0, 0]},
        servers=2,
        waiting_capacity=1,
        service_time=2,
        horizon=5,
    ).data
    assert data["counts"]["completed"] == 3
    assert data["counts"]["rejected"] == 1
    assert data["integrals"] == {"queue_time": 2, "busy_server_time": 6}
    assert data["average_queue_length"] == pytest.approx(0.4)
    assert data["utilization"] == pytest.approx(0.6)
    assert data["delays"]["started_attempt_wait"]["mean"] == pytest.approx(2 / 3)


def test_zero_waiting_capacity_still_admits_into_idle_workers():
    data = run(arrivals={"times": [0, 0, 2]}, waiting_capacity=0, horizon=5).data
    assert data["counts"]["completed"] == 2
    assert data["counts"]["rejected"] == 1
    assert data["integrals"]["queue_time"] == 0


def test_completion_dispatches_waiter_before_its_tied_timeout_and_new_arrival():
    data = run(arrivals={"times": [0, 0, 2]}, wait_timeout=2, horizon=7).data
    assert data["counts"]["completed"] == 3
    assert data["counts"]["timed_out"] == 0
    assert data["delays"]["completed_response_time"]["total"] == 10


def test_timeout_releases_waiting_capacity_before_simultaneous_arrival():
    data = run(
        arrivals={"times": [0, 0, 1]},
        service_time=3,
        wait_timeout=1,
        waiting_capacity=1,
        horizon=4,
    ).data
    assert data["counts"]["completed"] == 1
    assert data["counts"]["timed_out"] == 2
    assert data["counts"]["rejected"] == 0
    assert data["integrals"]["queue_time"] == 2
    # Timed-out visits are omitted from the service-start wait population.
    assert data["delays"]["started_attempt_wait"] == {
        "count": 1,
        "total": 0,
        "mean": 0,
        "maximum": 0,
    }


def test_bounded_retries_release_worker_during_delay():
    data = run(
        arrivals={"times": [0]},
        service_time=1,
        failure_probability=1,
        max_retries=2,
        retry_delay=1,
        horizon=6,
    ).data
    assert data["counts"]["failed"] == 1
    assert data["counts"]["attempts_started"] == 3
    assert data["counts"]["attempts_failed"] == 3
    assert data["counts"]["retries_scheduled"] == 2
    assert data["counts"]["completed"] == 0
    assert data["utilization"] == 0.5
    assert data["delays"]["completed_response_time"]["mean"] is None


def test_retries_rejoin_fifo_and_stale_timeouts_cannot_cancel_new_visits():
    data = run(
        arrivals={"times": [0, 0]},
        service_time=1,
        failure_probability=1,
        max_retries=1,
        wait_timeout=3,
        horizon=6,
    ).data
    assert data["counts"]["failed"] == 2
    assert data["counts"]["attempts_started"] == 4
    assert data["counts"]["timed_out"] == 0
    assert data["integrals"]["queue_time"] == 3


def test_retry_faces_capacity_and_external_arrivals_win_equal_priority_ties():
    data = run(
        arrivals={"times": [0, 1]},
        service_time=1,
        failure_probability=1,
        max_retries=1,
        waiting_capacity=0,
        horizon=5,
    ).data
    # At 1, pre-scheduled arrival starts before the first job's new retry.
    assert data["counts"]["rejected"] == 1
    assert data["counts"]["failed"] == 1
    assert data["counts"]["attempts_started"] == 3


def test_warmup_clips_integrals_but_keeps_full_delays_of_observed_outcomes():
    data = run(warmup=3, horizon=5).data
    assert data["counts"]["completed"] == 2
    assert data["observation"]["counts"]["completed"] == 1
    assert data["observation"]["counts"]["arrivals"] == 0
    assert data["observation"]["unfinished_at_start"] == 2
    assert data["observation"]["unfinished_at_end"] == 1
    assert data["unfinished"] == {"waiting": 0, "in_service": 1, "retrying": 0}
    assert data["integrals"] == {"queue_time": 1, "busy_server_time": 2}
    assert data["utilization"] == 1
    assert data["average_queue_length"] == 0.5
    assert data["throughput"] == 0.5
    assert data["delays"]["completed_response_time"]["mean"] == 3
    assert data["delays"]["started_attempt_wait"]["mean"] == 2
    assert data["conservation"]["observation_balanced"]


def test_window_includes_warmup_events_and_excludes_horizon_events():
    result = run(arrivals={"times": [0, 2, 4]}, warmup=2, horizon=4)
    data = result.data
    assert data["counts"]["arrivals"] == 2
    assert data["counts"]["completed"] == 1
    assert data["observation"]["counts"]["completed"] == 1
    assert data["observation"]["counts"]["arrivals"] == 1
    assert data["unfinished"]["in_service"] == 1
    assert result.metadata["arrivals_at_or_after_horizon"] == 1


def test_empty_window_and_unfinished_categories():
    empty = run(arrivals={"times": []}, warmup=2).data
    assert empty["utilization"] == empty["average_queue_length"] == empty["throughput"] == 0
    assert empty["delays"]["completed_response_time"]["count"] == 0
    assert empty["delays"]["completed_response_time"]["mean"] is None
    assert empty["conservation"]["observation_balanced"]
    data = run(
        arrivals={"times": [0, 0, 0]},
        service_time=1,
        horizon=1.5,
        failure_probability=1,
        max_retries=1,
        retry_delay=2,
        warmup=1.25,
    ).data
    assert data["unfinished"] == {"waiting": 1, "in_service": 1, "retrying": 1}
    assert data["counts"]["unfinished"] == 3
    assert data["observation"]["unfinished_at_start"] == 3
    assert data["conservation"]["balanced"]


def test_generated_constant_arrivals_match_fixed_schedule():
    fixed = run(arrivals={"times": [1, 2, 3]}).data
    generated = run(arrivals={"start": 1, "count": 3, "interarrival": 1}).data
    assert generated == fixed
    zero = run(arrivals={"count": 0, "interarrival": 1}).data
    assert zero["counts"]["arrivals"] == 0


@pytest.mark.parametrize("seed", range(5))
def test_seeded_stochastic_runs_obey_conservation_and_utilization_bounds(seed):
    kwargs = {
        "arrivals": {
            "count": 100,
            "interarrival": {"distribution": "exponential", "mean": 0.2},
        },
        "service_time": {"distribution": "uniform", "low": 0.5, "high": 1.5},
        "servers": 2,
        "waiting_capacity": 3,
        "wait_timeout": 0.7,
        "failure_probability": 0.4,
        "max_retries": 2,
        "retry_delay": 0.3,
        "horizon": 12,
        "warmup": 4,
        "seed": seed,
    }
    result = run(**kwargs)
    assert result.to_dict() == run(**kwargs).to_dict()
    data = result.data
    counts = data["counts"]
    assert counts["arrivals"] == sum(
        counts[name] for name in ("completed", "failed", "rejected", "timed_out", "unfinished")
    )
    assert data["conservation"]["observation_balanced"]
    assert counts["attempts_started"] == (
        counts["completed"] + counts["attempts_failed"] + data["unfinished"]["in_service"]
    )
    assert 0 <= data["utilization"] <= 1
    assert 0 <= data["average_queue_length"] <= 3
    assert counts["attempts_started"] <= 3 * counts["arrivals"]
    assert result.to_dict() != run(**{**kwargs, "seed": seed + 1}).to_dict()
    json.dumps(result.to_dict(), allow_nan=False)


def test_constant_and_exponential_service_distributions():
    assert run(service_time={"distribution": "constant", "value": 2}).data == run().data
    data = run(service_time={"distribution": "exponential", "mean": 1}, horizon=100).data
    assert data["counts"]["completed"] == 3
    assert 0 < data["utilization"] < 1


def test_event_budget_exhaustion_raises_instead_of_returning_partial_metrics():
    with pytest.raises(SystemSimulationValidationError, match="max_events exhausted"):
        run(max_events=1)
    # Exactly enough events is valid; events at the horizon do not consume budget.
    assert run(arrivals={"times": [0]}, horizon=2, max_events=1).data["counts"]["unfinished"] == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"unknown": 1},
        {"horizon": 0},
        {"horizon": True},
        {"horizon": float("inf")},
        {"horizon": 10**1000},
        {"warmup": -1},
        {"warmup": 7},
        {"warmup": float("nan")},
        {"servers": 0},
        {"servers": 1.0},
        {"servers": True},
        {"servers": 10_001},
        {"seed": True},
        {"seed": 0.5},
        {"seed": 2**63},
        {"max_events": 0},
        {"max_events": 1_000_001},
        {"max_events": False},
        {"waiting_capacity": -1},
        {"waiting_capacity": True},
        {"wait_timeout": None},
        {"wait_timeout": 0},
        {"wait_timeout": float("nan")},
        {"failure_probability": True},
        {"failure_probability": -0.1},
        {"failure_probability": 1.1},
        {"failure_probability": float("inf")},
        {"max_retries": True},
        {"max_retries": -1},
        {"max_retries": 101},
        {"retry_delay": True},
        {"retry_delay": -1},
        {"arrivals": []},
        {"arrivals": {}},
        {"arrivals": {"times": [1, 0]}},
        {"arrivals": {"times": [-1]}},
        {"arrivals": {"times": [True]}},
        {"arrivals": {"times": [float("inf")]}},
        {"arrivals": {"times": "0,1"}},
        {"arrivals": {"times": [0], "count": 1}},
        {"arrivals": {"times": [0], "unknown": 1}},
        {"arrivals": {"count": MAX_ARRIVALS + 1, "interarrival": 1}},
        {"arrivals": {"count": True, "interarrival": 1}},
        {"arrivals": {"count": 1, "interarrival": 0}},
        {"arrivals": {"count": 1, "start": True, "interarrival": 1}},
        {"service_time": None},
        {"service_time": 0},
        {"service_time": True},
        {"service_time": {"distribution": []}},
        {"service_time": {"distribution": "normal", "mean": 1}},
        {"service_time": {"distribution": "constant", "value": 1, "extra": 1}},
        {"service_time": {"distribution": "uniform", "low": 2, "high": 1}},
        {"service_time": {"distribution": "uniform", "low": 0, "high": 1}},
        {"service_time": {"distribution": "uniform", "low": 1, "high": True}},
        {"service_time": {"distribution": "exponential", "mean": False}},
    ],
)
def test_invalid_inputs_are_rejected_without_mutating_request(changes):
    request = SystemSimulationEngine().example_request()
    request.update(changes)
    before = copy.deepcopy(request)
    with pytest.raises(SystemSimulationValidationError):
        SystemSimulationEngine().analyze(request)
    assert repr(request) == repr(before)


def test_request_requires_object_and_bounded_arrival_schedule():
    with pytest.raises(SystemSimulationValidationError, match="request must be an object"):
        SystemSimulationEngine().analyze([])
    with pytest.raises(SystemSimulationValidationError, match="at most"):
        run(arrivals={"times": [0] * (MAX_ARRIVALS + 1)})


@pytest.mark.parametrize(
    "changes",
    [
        {"arrivals": {"start": 1e12, "count": 2, "interarrival": 1e-300}},
        {"arrivals": {"times": [1e11]}, "horizon": 1e12, "service_time": 1e-300},
        {"arrivals": {"times": [1e11, 1e11]}, "horizon": 1e12, "wait_timeout": 1e-300},
        {
            "arrivals": {"times": [1e11]},
            "horizon": 1e12,
            "failure_probability": 1,
            "max_retries": 1,
            "retry_delay": 1e-300,
        },
    ],
)
def test_unrepresentable_time_progress_is_rejected(changes):
    with pytest.raises(SystemSimulationValidationError, match="does not advance time"):
        run(**changes)


def test_overflowing_derived_rate_is_rejected_as_simulation_validation():
    with pytest.raises(SystemSimulationValidationError, match="finite"):
        run(arrivals={"times": [0]}, service_time=5e-324, horizon=1e-323)
