# Decision analysis and value of information

List feasible actions, mutually exclusive states, outcomes, utilities or costs, and the current information state. Compare expected utility and regret, then show the threshold at which the preferred action changes. For a proposed observation or experiment, compare its expected value of perfect or sample information with its cost, delay, and risk. Do not optimize an unmeasurable utility silently; show the proxy and its limitations.

Pearl implements finite decision analysis. In MCP hosts, check `pearl_status()` compatibility first, discover inputs with `pearl_example(engine='decision-analysis')`, and run `pearl_analyze(engine='decision-analysis', data=REQUEST)` with a JSON object. Do not run the CLI examples in Chat.

Only in shell-capable hosts without MCP tools, run the [CLI compatibility check](../../../scripts/check_cli.py) with `python3`, then use its returned `executable`. Discover a runnable request with:

```bash
pearl-of-wisdom analyze --engine decision-analysis --example
```

The request contains `states`, an object mapping state names to probabilities, and `actions`, an object mapping each action name to its utility for every state. Higher utility is better. Optional `tests` maps test names to `likelihoods` and a nonnegative `cost` (default 0). Each likelihood row maps a state to probabilities for every possible observation, so it specifies `P(observation | state)`. All rows of a test use the same observation names. State and observation probabilities must sum to 1, within an absolute tolerance of `1e-9`; accepted rows are normalized before calculation.

Use the same utility scale for test costs and action payoffs. If delay or risk matters, include its utility cost explicitly; the engine does not infer those costs or convert money into utility. Tests are independent alternatives to acting now, not a sequence of experiments.

Results include `expected_utilities`, `optimal_actions` (including ties), `expected_utility`, per-state `regret`, `expected_regret`, and `evpi`. Each test reports `evsi` before costs and `net_evsi` after its cost, along with observation probabilities, posteriors, and optimal conditional actions. A negative `net_evsi` means that test costs more than its expected decision benefit under this model. Impossible observations have probability 0, null posterior and expected utility, and no recommended action.

Action rankings and information values use exact rational arithmetic over the validated, normalized floating-point inputs. Results are converted to ordinary JSON numbers at the boundary, so two displayed utility totals can round equal even when only one action is optimal. Use `optimal_actions` to identify ties rather than comparing rounded totals yourself.

The default work limit is 1,000,000 cells, counted as `states * actions * (1 + total test outcomes)`. Inputs and results must be finite, and unknown fields are rejected. Nonzero outputs below the normal floating-point range fail with a numerical-limit error; exact intermediate values can be smaller. A positive-probability observation is never deliberately relabeled as impossible to complete a calculation. No causal inference is implied by a test's likelihood table. Preserve assumptions about the utilities and observation process when reporting the result.
