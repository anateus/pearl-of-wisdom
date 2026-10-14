---
name: pearl-of-wisdom
description: Create, resume, and promote durable probabilistic investigations with Pearl MCP tools or a checked installed CLI, preserving assumptions, evidence, and analyses across turns. Use when uncertainty needs a durable investigation record; do not use for ordinary notes, deterministic edits, or unsupported certainty.
---

# Pearl of Wisdom investigations

Keep a small, inspectable investigation record separate from transient reasoning. Prefer Pearl MCP tools when available.

## Choose the host workflow

In an MCP host, call `pearl_status()` first. Check `compatible` is true, `required` is `>=0.4.0,<0.5.0`, and `version` is a stable release in that range. Confirm the engine is in `engines` and note `database` (the database path) and `transport`. The extension configures that path, not tool arguments. Read [mcp-workflow.md](references/mcp-workflow.md) when its content is available through the host. The essential workflow is included here so Chat does not depend on filesystem access:

1. Resume with `pearl_list_investigations()` and `pearl_show_investigation(investigation_id)`. Create only for a new question with `pearl_create_investigation(status='ephemeral')` and retain the returned ID.
2. Save separate entries with `pearl_record(investigation_id, kind, data, engine=None)`. Use `context`, `assumption`, or `evidence` without an engine. Use `analysis` with an engine and preserve the request, result, seed, units, and sensitivity choices in `data`.
3. Discover inputs with `pearl_example(engine)` (request and result), then calculate with `pearl_analyze(engine, data)`. Analysis is stateless: explicitly record any result needed later.
4. Verify writes with `pearl_show_investigation(investigation_id)`. Promote with `pearl_promote_investigation(investigation_id)` only after the record has a question, estimand or decision, assumptions, evidence, analysis, limitations, and a conditional conclusion. Show again and confirm durable status.

Treat a tool error, incompatible version, or missing engine as a failed operation. Stop affected work, explain the error, and never claim a write or promotion succeeded without readback. After an ambiguous timeout, show or list before retrying a write to avoid duplicates.

In Claude Desktop Chat without Pearl tools, ask the user to install the companion `.mcpb` through Desktop Extensions and enable it for this conversation, then retry `pearl_status()`. Do not offer the Code CLI as an ordinary Chat solution. In Chat, do not run shell commands, invoke `check_cli.py`, install packages, or invoke Claude Code's Skill tool. Use the loaded skill content; request the relevant reference content from the user if the host cannot expose it.

Only in a shell-capable Code or Codex host without Pearl MCP tools, run the [CLI compatibility check](../../scripts/check_cli.py) with `python3`. Resolve it relative to this loaded `SKILL.md` so it belongs to the active plugin. It accepts stable CLI 0.4.x from 0.4.0 and returns the compatible executable's absolute path. Use its returned `executable`, not `uvx`, `uv run`, or `uv tool run`. Read [cli-workflow.md](references/cli-workflow.md) and check relevant subcommand help before invoking commands. Resolve the database explicitly when the project has a chosen path.

If the CLI check fails, stop and surface its error. For a missing or incompatible CLI, show its exact `install_command`. Run that one-time install or update only when authorized, using the host's approval mechanism if needed. Existing authorization to install or update Pearl is sufficient. If approval is unavailable, leave the command for the user's terminal. Rerun the check after installation. Never change sandbox settings to make installation work.

## Evidence and conclusions

Preserve source, time, units, and provenance for context, assumptions, observations, and analyses. Read [evidence.md](references/evidence.md) if available before recording a probabilistic claim. Observations are not hypotheses, priors are not observations, and simulated outputs are not independent evidence. If reference content is unavailable, keep these boundaries and ask for the content before making a claim that needs further guidance.

Before a final answer, compare every material claim, including incidental advice, with saved inputs and results. Carry forward every assumption needed for a bound or conclusion. Correct or qualify mismatches. This improves traceability but does not guarantee correctness.

Hindsight may supply optional continuity context. It is never probabilistic evidence, a prior, a likelihood, or a replacement for a recorded source. Do not require a Hindsight daemon, log raw prompts, or silently import memory into an investigation.

For method selection, use [reasoning-under-uncertainty](../reasoning-under-uncertainty/SKILL.md) when its content is available. A persisted analysis still needs an appropriate method and honest uncertainty bounds. Use no model when inputs cannot support one.
