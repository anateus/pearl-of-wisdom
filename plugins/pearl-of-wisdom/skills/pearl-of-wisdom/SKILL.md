---
name: pearl-of-wisdom
description: Create, resume, and promote durable probabilistic investigations with the pearl-of-wisdom CLI, preserving assumptions, evidence, and analyses across turns. Use when uncertainty needs a durable investigation record; do not use for ordinary notes, deterministic edits, or unsupported certainty.
---

# Pearl of Wisdom investigations

Use the installed `pearl-of-wisdom` CLI as the durable record for an investigation. Keep the record small, inspectable, and separate from the agent's transient reasoning.

1. Run the [CLI compatibility check](../../scripts/check_cli.py) with `python3` before creating or changing an investigation. Resolve that script relative to this loaded `SKILL.md`, so it belongs to the active plugin version. The check accepts CLI 0.1.2 or a later stable 0.1.x patch release and returns JSON with the compatible executable's absolute path.

   Use the returned `executable` for subsequent commands. The check and the installed CLI do not run `uv` or install packages. Do not replace them with `uvx`, `uv run`, or `uv tool run`.

   If the check fails, stop the investigation workflow and surface its error. For a missing or incompatible CLI, show the exact `install_command` returned by the check. Run that one-time install or update only when authorized, using the host's approval mechanism if its sandbox blocks the tool directories. An existing authorization to install or update Pearl is sufficient. If approval is unavailable, leave the command for the user to run in their terminal. After installation, rerun the check before proceeding. Never change the session's sandbox settings to make installation work.
2. Read [cli-workflow.md](references/cli-workflow.md), then check the relevant subcommand help before invoking a command. Resolve the database explicitly when the surrounding project has a chosen path.
3. Create a new investigation for a new question. Resume by listing or showing existing records and selecting an ID; never create a duplicate merely because a new turn started.
4. Record context, assumptions, observations/evidence, and analyses as separate entries. Preserve source, time, units, and provenance. Read [evidence.md](references/evidence.md) before recording a probabilistic claim.
5. Promote only after the record has a clear question, estimand or decision, assumptions, evidence, analysis, limitations, and a conclusion that is conditional on its model. Use the CLI's current promote/status command and verify the resulting record with `show`.
6. Before a final answer that relies on the investigation, compare every material claim, including incidental advice, with the saved inputs and results. Carry forward each assumption needed for a bound or conclusion. Correct or qualify mismatches; this check improves traceability but does not guarantee correctness.

Hindsight may supply optional continuity context when it is available. It is never probabilistic evidence, a prior, a likelihood, or a replacement for a recorded source. Do not require a Hindsight daemon, log raw prompts, or silently import memory into an investigation.

For method selection, invoke [reasoning-under-uncertainty](../reasoning-under-uncertainty/SKILL.md). A persisted analysis still needs an appropriate method and honest uncertainty bounds.
