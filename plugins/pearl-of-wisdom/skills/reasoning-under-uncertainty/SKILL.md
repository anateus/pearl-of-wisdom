---
name: reasoning-under-uncertainty
description: Choose proportionate quantitative or qualitative reasoning for uncertain questions, routing among exact calculation, bounds and sensitivity, Monte Carlo, discrete Bayes, causal inference and experiments, decision analysis and value of information, system simulation, or no model. Use even for modest uncertainty when it could change the answer; do not activate for deterministic edits or unsupported precision.
---

# Reasoning under uncertainty

Make uncertainty explicit, then choose the cheapest method that can change the decision. The goal is a calibrated answer, not a number for its own sake.

1. State the question, decision, estimand, assumptions, and evidence already available. Separate observations from hypotheses and label unknowns.
2. Choose one route and explain why it fits. Use exact calculation for known rules and inputs, bounds or sensitivity for plausible input limits, Monte Carlo for combined uncertain numeric inputs, discrete Bayes for competing hypotheses and defensible likelihoods, causal inference for interventions, decision analysis for action payoffs or information value, and system simulation for queues or time dynamics. Use no model when uncertainty is immaterial, inputs are unidentifiable, or a qualitative answer is safer.
3. Read [routing.md](references/routing.md) and only the selected method reference when the host exposes their content. In Chat, use loaded content rather than assuming filesystem access or invoking Claude Code's Skill tool. Ask for relevant reference content if unavailable and needed to proceed safely.
4. Prefer MCP tools when available. Call `pearl_status()` before analysis: require `compatible` true, `required` equal to `>=0.4.0,<0.5.0`, and a stable `version` in that range. Check `engines` for the selected engine, and note `database` and `transport`. Discover the request and result with `pearl_example(engine)`, then call `pearl_analyze(engine, data)` with your explicit request object. These calls are stateless and do not save an investigation. Keep inputs, units, seed, priors, and sensitivity choices reproducible. Never present invented inputs as measurements.
5. Report a range or distribution, the assumptions that drive it, and what evidence would change the conclusion. Distinguish model uncertainty from sampling uncertainty. On a tool error, incompatible version, or unavailable engine, stop affected analysis and explain the problem. Do not invent a result or silently switch methods.

The supported engine names are `monte-carlo`, `discrete-bayes`, `causal`, `decision-analysis`, and `system-simulation`. In MCP hosts, reference examples written as `analyze --engine ENGINE --example` mean `pearl_example(engine=ENGINE)`. Commands written as `analyze --engine ENGINE --data REQUEST` mean `pearl_analyze(engine=ENGINE, data=REQUEST)` with a JSON object, not a shell string or filename. Exact calculation, bounds, and no-model routes do not require a Pearl engine.

In Claude Desktop Chat without Pearl tools, ask the user to install the companion `.mcpb` through Desktop Extensions and enable it for this conversation, then retry `pearl_status()`. Do not offer the Code CLI as an ordinary Chat solution. In Chat, do not run shell commands, invoke `check_cli.py`, or install packages. Qualitative or no-model reasoning can continue without pretending a tool ran.

Only in a shell-capable Code or Codex host without Pearl MCP tools, run the [CLI compatibility check](../../scripts/check_cli.py) with `python3` before using the CLI. Resolve it relative to this loaded `SKILL.md` and use its returned `executable`. Discover an engine's request with `analyze --engine ENGINE --example`. If the check fails, stop and surface its error and exact `install_command` if supplied. Install or update only when authorized, use the host's approval mechanism if needed, and rerun the check. Never substitute `uvx`, `uv run`, or `uv tool run` or change sandbox settings to bypass approval. Follow [cli-workflow.md](../pearl-of-wisdom/references/cli-workflow.md) for this host only.

A rough bound, small sensitivity table, or short list of unknowns is worthwhile when uncertainty is modest but decision-relevant. Do not manufacture probabilities for subjective language, treat correlation as causation, or use a simulation to disguise missing data.

For durable multi-turn work, use the available [pearl-of-wisdom](../pearl-of-wisdom/SKILL.md) content and [MCP workflow](../pearl-of-wisdom/references/mcp-workflow.md). Explicitly record analyses and verify saved entries before relying on them. Hindsight, if present, is optional context and never evidence for a probability, prior, or likelihood.
