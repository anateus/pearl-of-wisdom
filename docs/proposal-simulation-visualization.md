# Proposal: simulation observations for Pearl visualization

Status: follow-on draft, outside the [first Monte Carlo visualization release](proposal-arviz-visualization.md). Written 2026-09-12 against Pearl 0.2.0 (`1ed31d4`). This defines the additional simulation contract; it does not schedule implementation.

## Purpose

Expose enough bounded event history to explain queue delays, retries, terminal outcomes, and unfinished work. A response-time chart should make its measured population visible. It must not present successful completions as the latency distribution of all arrivals or treat dependent jobs in one queue run as independent simulation replications.

The current [simulation engine](../src/pearl_of_wisdom/engines/system_simulation.py) keeps each job's arrival, latest queue-entry time, current status, and number of started attempts. `_Delay` retains a count, total, and maximum. Completion timestamps and previous queue visits are discarded, so the proposed observations require capture at event transitions. They cannot be reconstructed from the existing result.

## Populations that stay fixed

Events execute in `[0, horizon)`. Measurement events are in `[warmup, horizon)`. An event exactly at the horizon is not processed. Existing tie order, queue admission, timeout, retry, random-stream, and event-budget behavior remain unchanged.

| Measurement | Included population |
| --- | --- |
| Completed response time | Jobs that successfully complete in the measurement window, including jobs that arrived before warmup. Duration starts at original arrival and includes retries. |
| Started-attempt wait | Queue visits whose service starts in the measurement window, including zero waits and queue entry before warmup. Each retry visit is distinct. |
| Terminal outcomes | Successful, failed, timed-out, and rejected jobs. Distinguish whole-run counts from terminal events in the measurement window. |
| Unfinished work | Jobs still waiting, in service, or awaiting retry at the horizon. These have elapsed time but no final response time. |

A queue timeout is not a completed response-time observation. An unstarted visit is absent from the existing started-attempt wait summary even if its queue delay is known at timeout. Charts must retain those distinctions. These populations follow the existing `metadata.response_time_population`, `metadata.wait_time_population`, and `metadata.censoring` fields.

## Proposed export contract

Add `return_observations`, a boolean defaulting to `false`, and `observation_limit`, an integer from 1 through 10,000 that defaults to 10,000 when export is enabled. Supplying the limit without enabling export is an error. Existing requests and results remain identical when export is omitted or false. This is a simulation-specific schema, separate from Monte Carlo `data.draws`.

With export enabled, return `data.observations` with schema version 1, the total eligible job count, retained count, selected job IDs, selection method, measurement boundaries, and computational provenance. Eligible jobs are all arrivals before the horizon, including those before warmup. Zero eligible jobs yields empty tables and an explicit empty population, not fabricated observations.

Retain all eligible jobs up to the limit; above it, select jobs uniformly without replacement using a deterministic random stream separate from simulation randomness. Record selected IDs and preserve their order. All terminal and unfinished states are eligible for selection. Every selected job retains its complete queue-visit history through the horizon. Never sample individual attempts independently and then imply that the remaining visits form a complete job history.

The export contains two related tables:

| Table | Required observations |
| --- | --- |
| Jobs | Stable job ID, original arrival time, terminal time or null, terminal/current status, attempts started, and observation end. Terminal states are `completed`, `failed`, `timed_out`, and `rejected`; unfinished states are `waiting`, `in_service`, and `retrying`. Observation end is terminal time for finished jobs and the horizon otherwise. |
| Queue visits | Job ID and zero-based visit index; queue entry; service start or null; service end or null; visit exit time or null; and exit reason. A rejected or timed-out visit is distinct from a started attempt. A service end records success or failure; pending service or queue residence remains explicit at the horizon. |

Timestamps share the engine's simulation-time unit. Null means the event has not occurred, not zero duration. Records permit reconstruction of successful response times and started waits, plus elapsed lower bounds for unfinished jobs. Visit exit reasons distinguish `started`, `timed_out`, `rejected`, and `waiting_at_horizon`; a started visit's service outcome is `completed`, `failed`, or `in_service_at_horizon`. Retrying jobs retain the failed service observation and their current job state even if no new queue visit occurs before the horizon.

Retained visit count is capped at 100,000 and the complete UTF-8 JSON response, using the CLI's serialization, at 16 MiB, including provenance. Exceeding either limit produces an actionable export validation error; do not drop visits, return partial histories, or silently reduce retained jobs. These are proposed format limits. The existing event-budget failure still returns no apparently complete result.

All existing summaries use the complete simulation, independently of export selection. Export must not consume simulation random values, move an event, change a denominator, or retain histories for unselected jobs. Computational provenance includes the effective request, seed, Pearl version, and Python version; deterministic replay is scoped to those versions and runtime.

## Plot behavior

The companion's simulation view accepts schema 1 observations and the unchanged full result. It shows separate empirical distributions for completed response time and started-attempt wait, with their population definitions, measurement window, eligible observation counts, and retained observation counts. Rejected, timed-out, failed, and unfinished jobs appear in an outcome summary alongside successful jobs.

Full-run and measurement-window counts come directly from their respective summary fields. Curves use the retained observations. When selection omitted jobs, identify the curves as observations from a job sample; do not weight each retained attempt as an independently sampled job. Display unfinished jobs as censored elapsed times or explicit counts, never as zero-latency completions or successful durations equal to the horizon. A sample containing no successful jobs produces a labeled empty response-time view while preserving full-run counts.

A response-time maximum or mean shown as a full-run statistic comes from `data.delays.completed_response_time`. The corresponding started-wait values come from `data.delays.started_attempt_wait`. Quantiles computed only from retained observations must be labeled as such. No fitted distribution, posterior interval, convergence diagnostic, or confidence interval across individual jobs is inferred.

The renderer, resource modes, static summaries, escaped labels, output publication, source hashes, and explicit persistence follow the Monte Carlo companion contract. Simulation adds an engine-specific adapter and observation validation; it does not force job histories into the Monte Carlo draw schema. Direct Bokeh is appropriate for outcome counts and censoring annotations even if ArviZ supplies a distribution plot.

## Acceptance and verification seams

| Seam | Acceptance evidence |
| --- | --- |
| Existing engine | Seeded and deterministic fixtures produce identical summaries with export on and off. Event limits, simultaneous-event rules, and random consumption stay unchanged. |
| Event capture | Hand-worked schedules cover immediate service, queued service, retry success, exhausted retries, rejection, timeout, and every unfinished state. Visit histories reconcile with attempts and terminal outcomes. |
| Measurement boundaries | Fixtures cover arrivals and queue entries before warmup, completions at warmup, and events exactly at the horizon. Reconstructed measurements from an uncapped export match existing summary counts, totals, means, and maxima. |
| Conservation | An uncapped export reconciles whole-run arrivals with terminal and unfinished jobs, and separately reproduces observation-window conservation using work present at warmup. |
| Selection and bounds | Selected jobs and all their visits reproduce for a fixed request/runtime. Capped export leaves full-run metrics unchanged. Zero arrivals, row limits, history limits, byte limits, and malformed controls have explicit outcomes. |
| Interpretation | Fixtures with timeouts, failed jobs, retries, and unfinished work cannot render those records as successful response times. A retained sample with no completions still shows the original full-run completion count. |
| Companion integration | Browser tests inspect population labels, hover values, empty states, and subset/censoring notices using the same artifact/resource lifecycle checks as Monte Carlo. |

Independent simulation replications, survival-model estimation, arbitrary event traces, dependent Monte Carlo inputs, general networks of queues, and changes to queue semantics are outside this follow-on. Before implementation, plan event capture and renderer integration as separate slices using these public seams.
