# Causal inference and experiments

First state the intervention, unit, outcome, time window, and estimand. Draw or describe the causal structure, identify confounders and post-treatment variables, and list the assumptions needed for identification. Prefer randomization, natural experiments, or a credible quasi-experimental design when feasible. Report threats, spillovers, selection, missingness, and uncertainty. Association, predictive accuracy, and a Bayesian posterior alone do not identify an intervention effect.

Pearl implements interventions in explicitly supplied discrete causal models through `analyze --engine causal`. Run the [CLI compatibility check](../../../scripts/check_cli.py) with `python3`, then use its returned `executable`. Start with:

```bash
pearl-of-wisdom analyze --engine causal --example
```

The request uses the same `network` and `query` format as [discrete Bayes](discrete-bayes.md), plus a nonempty `interventions` object mapping variable names to states and a nonempty `assumptions` list of strings. Explain why the graph includes relevant common causes and why its conditional probability tables represent mechanisms that remain valid under the proposed intervention. Recording those assumptions does not verify them.

The engine validates the original graph and tables, removes incoming edges to intervened variables, fixes their states, and enumerates the resulting distribution. Multiple interventions and queries on intervened variables are supported. Optional `evidence` is observed in the intervened model: the returned distribution is `P(query | do(interventions), evidence)` and `evidence_probability` is `P(evidence | do(interventions))`. Conditioning on a post-treatment variable can change the estimand. This is not a counterfactual calculation about an individual observed before treatment.

Results record the interventions, evidence, assumptions, and interpretation in metadata. The CLI limit is 4,096 joint states and 128 variables; assumptions are limited to 100 entries of at most 4,096 characters. Invalid original networks remain invalid even when an intervention would remove their problematic edges. Impossible evidence is rejected. Positive joint probabilities below the normal floating-point range produce a numerical-limit error, including products that round to zero or lose precision in the subnormal range. This conservative limit also applies to the shared observational Bayes enumerator.

Use `discrete-bayes` for observational updates. This causal engine does not learn a graph, estimate conditional tables from a dataset, discover hidden confounders, or establish identification from observational data. Claims remain conditional on the supplied causal model.
