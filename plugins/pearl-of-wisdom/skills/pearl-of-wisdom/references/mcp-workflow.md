# MCP workflow

Use this workflow in hosts exposing Pearl MCP tools. Tool names below are exact public names; a host may display them with a server prefix. Do not translate them into shell commands in Chat.

## Compatibility and tool contract

Call `pearl_status()` first. It returns `version`, `required` (`>=0.4.0,<0.5.0`), `compatible`, `transport` (`stdio`), `engines`, and `database` (the configured database path). Require `compatible` true and a stable `version` within `required`. Stop if status fails, the version is incompatible, or the chosen engine is absent. The extension configures the database. No tool accepts a model-selected database path.

| Tool | Purpose |
| --- | --- |
| `pearl_status()` | Check compatibility, engines, and configured database |
| `pearl_example(engine)` | Return a runnable request and its result |
| `pearl_analyze(engine, data)` | Analyze an explicit JSON request object without persistence |
| `pearl_create_investigation(status='ephemeral')` | Create a record and return its investigation ID |
| `pearl_list_investigations()` | Find existing records to resume |
| `pearl_show_investigation(investigation_id)` | Read status and entries for verification |
| `pearl_record(investigation_id, kind, data, engine=None)` | Add context, assumption, evidence, or analysis |
| `pearl_promote_investigation(investigation_id)` | Promote an investigation to durable status |

Create, show, and promote return a full investigation envelope, including its ID. List returns an object with an `investigations` array of full envelopes, not a bare array. Record returns the appended record with `id`, `payload`, `created_at`, and an optional `engine`. Keep the investigation ID distinct from the appended record ID.

The `kind` values are exactly `context`, `assumption`, `evidence`, and `analysis`. Supply `engine` only for `analysis`, where it is required. `data` is a JSON object. Keep sources, observation times, units, and provenance with recorded evidence. For analysis, preserve the request and result together with seeds and sensitivity choices. Neither an example nor a stateless analysis writes an investigation.

## Durable sequence

List and show before deciding whether the question needs a new record. Reuse the ID for the same question across turns. For a new question, create an ephemeral investigation, record context and assumptions separately, record evidence, discover the engine request, analyze, then explicitly record the analysis. Show the investigation and compare entries with the intended data before saying they were saved.

Promote only when the record contains a question, estimand or decision, assumptions, evidence, analysis, limitations, and a conclusion conditional on its model. Call `pearl_promote_investigation(investigation_id)`, then show the same ID and confirm durable status and preserved entries. Before relying on the record in a final answer, compare each material claim with saved inputs and results and carry forward its assumptions.

## Errors and unavailable tools

A protocol error, tool error, malformed result, or missing engine is not a successful operation. Surface the error and stop affected work rather than fabricating a result or claiming persistence. For an ambiguous timeout after a write, list or show first and inspect whether it took effect. Do not blindly retry create, record, or promote. A changed database path requires the user's extension configuration, not a new tool argument.

In Claude Desktop Chat without Pearl tools, ask the user to install the companion `.mcpb` through Desktop Extensions and enable it for the conversation. Retry status after the tools become available. Do not offer the Code CLI as an ordinary Chat solution, ask Chat to run a shell or `check_cli.py`, install packages, or invoke Claude Code's Skill tool. Chat uses loaded skill content. If a needed reference is unavailable through the host, ask the user for its content rather than inventing a filesystem reader.

A shell-capable Code or Codex host without MCP tools can instead follow the checked installed [CLI workflow](cli-workflow.md). Do not silently fall back from a failing MCP tool to a different database or backend.

No-model reasoning remains valid when inputs are unidentifiable or a qualitative answer is safer. Hindsight is optional continuity context, never evidence, a prior, a likelihood, or a required daemon. Do not silently import it or log raw prompts.
