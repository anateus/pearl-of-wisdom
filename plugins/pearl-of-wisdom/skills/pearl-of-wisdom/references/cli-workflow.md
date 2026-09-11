# CLI workflow

Run the compatibility check linked from [the skill](../SKILL.md), then use the returned executable directly. The examples below use `pearl-of-wisdom` for readability; use its checked absolute path when invoking it. Install or update the bundled wheel once when the check requests it.

The command is intentionally the source of truth for its flags. Start with:

```bash
pearl-of-wisdom --help
pearl-of-wisdom --db PATH create --help
pearl-of-wisdom analyze --help
pearl-of-wisdom --db PATH list --help
pearl-of-wisdom --db PATH show INVESTIGATION_ID --help
```

To discover each engine's input shape without reading package source, ask `analyze` for a machine-readable example. The response contains the request and the result produced by running it:

```bash
pearl-of-wisdom analyze --engine discrete-bayes --example
pearl-of-wisdom analyze --engine monte-carlo --example
```

The current public seams include `create`, `list`, `show`, `promote`, `analyze`, and record commands such as `record-context`, `record-assumption`, `record-evidence`, and `record-analysis`. Use their JSON output as the handoff between turns. If a release names resume or promote differently, follow that release's help text and verify with `show`.

Recommended sequence:

```text
create → record context/assumptions → record evidence → analyze → record analysis → promote → show
```

Use a stable investigation ID when passing work between agents. Treat a nonzero exit status or structured error as a failed operation; do not claim that an entry was recorded until `show` confirms it.
