---
name: reasoning-under-uncertainty
description: Choose proportionate quantitative or qualitative reasoning for uncertain questions, routing among exact calculation, bounds and sensitivity, Monte Carlo, discrete Bayes, causal inference and experiments, decision analysis and value of information, system simulation, or no model. Use even for modest uncertainty when it could change the answer; do not activate for deterministic edits or unsupported precision.
---

# Reasoning under uncertainty

Make uncertainty explicit, then choose the cheapest method that can change the decision. The goal is a calibrated answer, not a number for its own sake.

1. State the question, decision, estimand, assumptions, and evidence already available. Separate observations from hypotheses and label unknowns.
2. Read [routing.md](references/routing.md). Select one primary route and explain why it fits. Use no model when the uncertainty is immaterial, the inputs are not identifiable, or a qualitative answer is safer.
3. Read only the reference for the selected route. Keep inputs, units, seed, priors, and sensitivity choices reproducible. Never present invented inputs as measurements.
4. Report a range or distribution, the assumptions that drive it, and what evidence would change the conclusion. Distinguish model uncertainty from sampling uncertainty.

Use a lower activation floor: a rough bound, a small sensitivity table, or a short list of unknowns is worthwhile when uncertainty is modest but decision-relevant. Do not manufacture probabilities for subjective language, treat correlation as causation, or use a simulation to disguise missing data.

For durable multi-turn work, use the [pearl-of-wisdom](../pearl-of-wisdom/SKILL.md) skill and its CLI workflow. Hindsight, if present, is optional context and never evidence for a probability.
