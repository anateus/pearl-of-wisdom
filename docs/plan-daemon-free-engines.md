# Three reasoning engines without a daemon

Pearl will calculate the value of gathering information, evaluate interventions in an explicit causal model, and simulate a finite worker queue. Each engine will accept JSON through `analyze`, return the existing `AnalysisResult`, and exit. Existing Monte Carlo and observational Bayes behavior stays compatible.

The work starts from commit `649703096fef178dacfe2f48843c8fd0b9b766e2`. The current registry is `src/pearl_of_wisdom/engines/__init__.py`; the CLI already derives engine choices from that registry. SQLite stores analysis payloads as JSON. These boundaries let the engines ship independently without a daemon or database migration.

## Scope and acceptance

| Slice | Public behavior | Acceptance evidence |
| --- | --- | --- |
| Decision analysis | `analyze --engine decision-analysis` compares finite actions using state probabilities and utilities. It reports expected utilities, ties, regret, expected value of perfect information, and the gross and net value of optional tests with explicit observation likelihoods and costs. Costs use the same utility scale as payoffs. | Independently worked decisions; perfect, useless, and costly tests; zero-probability observations; ties; malformed tables; bounded work. |
| Causal interventions | `analyze --engine causal` calculates a query distribution after setting variables in an explicitly supplied discrete causal network. Requests keep observational evidence separate from interventions and record the causal assumptions. | A confounded example where observation and intervention differ; multiple interventions; intervened query variables; impossible evidence; validation of the original network; unchanged observational Bayes tests. |
| System simulation | `analyze --engine system-simulation` runs a bounded discrete-event FIFO worker queue with fixed or sampled arrivals and service times, finite workers, optional waiting capacity and timeout, bounded retries, a horizon, warm-up, and a seed. Results describe throughput, delay, queue length, utilization, and unfinished work with explicit denominators. | Exact deterministic schedules; queue conservation; simultaneous-event rules; saturation; timeout and retry cases; warm-up accounting; seed reproducibility; enforced event and input bounds. |

Causal effects are conditional on the supplied model and assumptions. This slice does not discover a graph or estimate arbitrary causal effects from a dataset. Simulation starts with one shared worker pool; arbitrary process scripts and general networks of queues are later extensions. Value of information evaluates a supplied test model and does not run experiments.

The three engines use the standard library and strict JSON validation. Unknown fields, booleans passed as numbers, non-finite values, incomplete tables, and excessive workloads produce validation errors. Engines return fresh runnable examples and advertise distinct capabilities. Simulation stops at its configured bounds rather than returning an apparently complete result after exhausting its event budget.

Automatic result persistence, dependent Monte Carlo inputs, database migrations, and a daemon remain deferred. Results from each new engine can be recorded with the existing `record-analysis` command.

## Parallel ownership

| Owner | Files | Dependencies |
| --- | --- | --- |
| Decision agent | `src/pearl_of_wisdom/engines/decision_analysis.py`, `tests/test_decision_analysis.py` | Existing `AnalysisEngine` and `AnalysisResult` contract. |
| Causal agent | `src/pearl_of_wisdom/engines/causal.py`, `tests/test_causal.py`; small changes to `discrete_bayes.py` only if needed for shared validated enumeration | Existing Bayes validation and enumeration. Preserve its public requests and results. |
| Simulation agent | `src/pearl_of_wisdom/engines/system_simulation.py`, `tests/test_system_simulation.py` | Existing result contract. Keep sampling helpers local unless a shared change is agreed. |
| Integrator | Engine registry and exports, CLI integration tests, README, plugin method references, version metadata, bundled wheel, this plan | Integrate each engine as its contract settles; package after all three pass. |

The engine classes are `DecisionAnalysisEngine`, `CausalEngine`, and `SystemSimulationEngine`. Their result names are `decision_analysis`, `causal`, and `system_simulation`, following the existing distinction between hyphenated CLI names and underscore result names.

Agents work in the shared checkout with exclusive file ownership. They report request and result contracts before integration and leave bounded findings in task-specific scratch files. The integrator reads the implementation and rechecks the central mathematical or scheduling claim before accepting a report. A second parallel pass reviews each engine independently after implementation.

## Execution and verification

1. Record the initiative and assignment ledger, then dispatch the three engine slices. Start tests from hand-derived public behavior and retain focused validation cases beside each engine.
2. Register engines, exercise each through the real CLI, and verify that `record-analysis` accepts its CLI engine name. Keep default `analyze` stateless and preserve the existing engines' input contracts.
3. Update the README and routing references with executable examples, supported input shapes, output meanings, and limits. Prepare a consistent package/plugin version and rebuild the bundled wheel so installed plugin users receive the new engines.
4. Run the focused engine suites, the full local suite, Ruff, package build, plugin validation, and installed-wheel checks. Run the available host end-to-end tests after packaging, using their existing isolated installation workflow.
5. Review the fixed-base diff, resolve findings, rerun affected checks, and open the work stream's Hunk review pane. Report actual verification results and any remaining limitations.

The mathematical references are [Stanford's decision-analysis notes](https://web.stanford.edu/class/msande290/files/Perry_Notes1.pdf) and [Pearl's causal-model formulation](https://web.cs.ucla.edu/~kaoru/ch1-final.pdf). [SimPy's environment documentation](https://simpy.readthedocs.io/en/latest/topical_guides/environments.html) illustrates bounded simulated-time execution; this implementation does not require SimPy.

## Implementation outcome

Version 0.2.0 implements all three engines and includes the rebuilt plugin wheel. Three agents implemented the engines concurrently, followed by independent mathematical and integration reviews. Review findings led to exact rational policy scoring in decision analysis and explicit numerical-limit errors in the shared Bayes enumerator. All implementation findings were resolved.

The local suite passed 336 tests, with the two opt-in host tests skipped. This includes CLI compatibility and install hints when Codex adds a cachebuster to the plugin version. Separate Codex host execution passed both tests, including real plugin installation and durable-record use. Ruff, package build, both plugin validators, skill validation, installed-wheel execution, and wheel/source equality checks passed. A separate scheduling oracle matched 2,000 deterministic queue scenarios covering capacity, waiting timeouts, warm-up, delays, and unfinished work.

Claude runtime verification remains incomplete. Its host test failed twice with `api_error` before reaching plugin assertions; a minimal Claude request with no Pearl plugin also timed out after 90 seconds. Those observations do not establish the underlying host or API cause. The Claude manifest validates, and the shared CLI and plugin contracts pass their local checks.
