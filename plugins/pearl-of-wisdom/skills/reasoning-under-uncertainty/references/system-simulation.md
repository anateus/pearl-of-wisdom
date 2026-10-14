# System simulation

Use this route for feedback, queues, resource contention, state transitions, or time-dependent behavior. Define state, events, transition and scheduling rules, initial conditions, horizon, warm-up, and metrics before running scenarios. Validate invariants and edge cases, compare against any observed baseline, and vary structural assumptions. A simulation can expose mechanisms and operational ranges; it cannot validate its own premises.

Pearl implements one finite FIFO worker queue. In MCP hosts, check `pearl_status()` compatibility first, discover inputs with `pearl_example(engine='system-simulation')`, and run `pearl_analyze(engine='system-simulation', data=REQUEST)` with a JSON object. Do not run the CLI examples in Chat.

Only in shell-capable hosts without MCP tools, run the [CLI compatibility check](../../../scripts/check_cli.py) with `python3`, then use its returned `executable`. Discover a runnable request with:

```bash
pearl-of-wisdom analyze --engine system-simulation --example
```

Required fields are `arrivals`, `service_time`, `servers`, and `horizon`. Use one consistent time unit throughout the request.

| Field | Meaning |
| --- | --- |
| `arrivals` | Either `{"times": [0, 1, 2]}` with sorted nonnegative times, or `{"count": 100, "start": 0, "interarrival": 2}`. The generated process places its first arrival at `start` (default 0) and samples the intervals after it. Counts are finite; arrivals at or after the horizon are excluded and reported separately. |
| `service_time` | A positive number or a supported duration distribution. Each attempt samples its service time when it starts. |
| `servers` | Number of workers, from 1 through 10,000. |
| `horizon`, `warmup` | Process events in `[0, horizon)` and measure in `[warmup, horizon)`. Warm-up defaults to 0 and must precede the horizon. |
| `waiting_capacity` | Waiting slots, excluding workers. Defaults to 100,000. An arrival or retry that cannot start or wait is rejected; 0 allows service only when a worker is free. |
| `wait_timeout` | Optional positive maximum wait for each queue visit. A job still waiting at its deadline times out permanently. |
| `failure_probability`, `max_retries`, `retry_delay` | Failure probability per completed attempt, maximum additional attempts, and fixed nonnegative delay before rejoining the queue. Defaults are 0. Failed attempts release the worker; retried jobs face capacity and waiting timeout again. |
| `seed`, `max_events` | Signed 64-bit seed (default 0) and execution budget (default and maximum 1,000,000 processed events). Budget exhaustion fails the analysis. |

Service and interarrival durations accept a positive number or `{"distribution": "constant", "value": 2}`, `{"distribution": "uniform", "low": 1, "high": 3}`, or `{"distribution": "exponential", "mean": 2}`. The engine uses one seeded random stream: it draws generated interarrivals first, then service times at attempt start and failures at completion. Keep the seed and the entire request when comparing runs; changes to the model can change later draws.

At the same timestamp, completions free workers and dispatch existing FIFO waiters before waiting timeouts. External arrivals and retries follow in insertion order. A waiter can start exactly at its waiting deadline. Events exactly at the horizon are not processed.

`counts` covers the full run; `observation.counts` covers the measurement window. `unfinished` separates waiting, service, and retry-delay states at the horizon. `conservation` checks that arrivals equal terminal outcomes plus unfinished jobs, both for the run and with carry-in work for the observation window.

`throughput` counts successful completions per observation time unit. `utilization` divides busy-worker time by workers times observation duration. `average_queue_length` divides accumulated waiting-job time by observation duration. `integrals` preserves those time totals. Delay summaries expose count, total, mean, and maximum; empty means and maxima are null. `completed_response_time` includes jobs that complete successfully inside the window, even if they arrived before warm-up. `started_attempt_wait` includes queue visits that start service inside the window, including zero waits and time spent waiting before warm-up.

Unfinished jobs are excluded from response-time summaries, and visits that never start service are excluded from waiting-time summaries. Check those censored populations before interpreting delays during overload. A fixed horizon does not imply the queue reached a steady state; use explicit warm-up and multiple scenario runs when the question requires them.

Limits are 100,000 requested arrivals, 100 retries per job, and `1e12` for each supplied time value. Numeric overflow or increments that cannot advance the floating-point clock fail validation. General queue networks, arbitrary event scripts, and automatic steady-state detection are outside this engine's scope.
