# Routing guide

Choose the first route whose inputs and output match the question. Escalate only when the simpler route cannot distinguish the decisions.

In MCP hosts, call `pearl_status()` for compatibility, then `pearl_example(engine)` for the request and result and `pearl_analyze(engine, data)` to calculate. CLI examples in method references are for shell-capable hosts only: `analyze --engine ENGINE --example` maps to `pearl_example(engine=ENGINE)`, and `analyze --engine ENGINE --data REQUEST` maps to `pearl_analyze(engine=ENGINE, data=REQUEST)` with a JSON object. Chat does not run shell examples or the CLI compatibility script. Follow the loaded skill's host guidance when tools or reference content are unavailable.

| Route | Use when | Minimum output |
| --- | --- | --- |
| Exact calculation | Inputs and rules are known and finite or algebraically defined | Formula, units, result, and checks |
| Bounds / sensitivity | Inputs are uncertain but plausible limits or influential variables are available | Interval or one-at-a-time / scenario sensitivity |
| Monte Carlo | Several uncertain numeric inputs combine and repeated sampling answers the question | Reproducible samples, seed, quantiles, and convergence check |
| Discrete Bayes | Competing hypotheses, discrete evidence, and likelihoods or defensible priors exist | Prior, likelihood, posterior, and normalization |
| Causal inference / experiment | The question is intervention or mechanism, not association | Estimand, identification assumptions, design, and confounders |
| Decision analysis / VoI | Actions have different outcomes, costs, or reversible information-gathering options | Expected utility, regret or threshold, and information value |
| System simulation | Feedback, queues, state transitions, or time dynamics dominate | State, transition rules, horizon, and scenario results |
| No model | Inputs are unidentifiable, stakes require domain review, or uncertainty cannot change action | Explicit unknowns, safe next step, and evidence needed |

Negative boundaries: do not infer causality from a posterior; do not call a Monte Carlo run evidence; do not use a prior as an observation; do not turn a confidence label into a calibrated probability. If a route depends on unavailable facts, downgrade to bounds or no model.

For worked routing cases, see [routing-cases.json](../../../evals/routing-cases.json).
