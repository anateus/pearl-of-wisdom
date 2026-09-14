# Pearl of Wisdom visualization companion

`pearl-of-wisdom-viz` turns saved Monte Carlo results into question-led reports, empirical cumulative distributions, and scenario interval comparisons. It is separate from Pearl core so `pearl-of-wisdom` keeps zero runtime dependencies.

The renderer treats the numerical result as authoritative. Distribution shape comes from explicitly exported draws. Forest markers and intervals come from each result's full-run 5th, 50th, and 95th percentiles, even when retained draws are present.

## Setup

Python 3.12 or newer and [uv](https://docs.astral.sh/uv/) are required.

```bash
uv sync --project visualization --locked
uv run --project visualization pearl-of-wisdom-viz --help
```

Matplotlib PNG output uses the optional extra:

```bash
uv sync --project visualization --locked --extra matplotlib
```

## Explain a model to a general reader

Use `explain` when readers need to understand the question, answer, and assumptions before inspecting a statistical plot. The report leads with a conditional natural frequency, such as “about 46 in 100 simulated projects,” and the exact full-run count. It then shows the middle 90% outcome interval against the target, the model's arithmetic, and the source of each input. Saved-scenario controls update the answer, comparison, model, and interval highlight together. Exact numbers, retained-draw distributions, and provenance are available under audit details.

The [worked examples](examples/README.md) generate complete synthetic project-deadline and outing-budget reports through both CLIs. They save the requests, results, context, and artifact descriptor, so you can inspect or adapt the whole example.

### Generate a threshold metric

Pearl core 0.4.0 adds optional named comparisons against the full simulation run:

```json
{
  "variables": {"duration": {"distribution": "uniform", "low": 20, "high": 40}},
  "expression": "duration",
  "samples": 10000,
  "seed": 7,
  "return_draws": true,
  "quantiles": [0.05, 0.5, 0.95],
  "thresholds": {"deadline": {"operator": "le", "value": 30}}
}
```

Save this request, then use the core `analyze --engine monte-carlo --data` command to save its JSON result. Each event in `data.thresholds.events` contains `operator`, `value`, `matched`, and `total`. The four supported operators are `lt`, `le`, `gt`, and `ge`; inclusive comparisons count ties. Requests accept one through 16 named thresholds, with finite numeric values and nonblank identifiers of at most 64 characters. Omit `thresholds` to preserve the earlier result shape. Threshold reporting doesn't change sampling or require draw export.

The report requires draw provenance plus the 5th, 50th, and 95th percentiles. Its headline and interval use the full run, never a retained subset. A missing metric is an error: regenerate the result with the required threshold rather than estimating its count from capped draws.

### Supply the meaning, not the answer

Create a context JSON file beside the result. The following illustrates its schema; replace the hash with the SHA-256 of the exact saved result bytes:

```json
{
  "schema_version": 1,
  "illustrative": true,
  "question": "Will this project finish within 30 working days?",
  "outcome": {
    "label": "Completion time",
    "unit": "working days",
    "subject": "simulated projects"
  },
  "target": {"id": "deadline", "operator": "le", "value": 30},
  "model": {
    "explanation": "Completion time is the assumed project duration.",
    "inputs": {
      "duration": {
        "label": "Project duration",
        "unit": "working days",
        "description": "Assume any duration from 20 to 40 working days is equally likely.",
        "evidence": {"status": "assumed", "note": "Synthetic teaching values."}
      }
    },
    "limitations": ["This example has not been calibrated to a real team."]
  },
  "scenarios": [{
    "id": "baseline",
    "label": "Current scope",
    "source": "baseline.result.json",
    "sha256": "REPLACE_WITH_SAVED_RESULT_SHA256",
    "changes": []
  }]
}
```

`illustrative` is required. Set it to `true` for synthetic teaching examples. Setting it to `false` doesn't establish that a model is calibrated. Input evidence is `assumed`, `observed`, or `inferred`; observed and inferred inputs require a `reference` string. References are displayed as supplied text, not fetched or verified.

The input keys must match the saved model's variables exactly. Expressions and distribution values come from the saved request. All supplied text is escaped; the browser never evaluates the model expression. The renderer cannot check whether authored explanations or physical units are true.

Supply one through eight ordered scenarios with unique identifiers and labels. The first is the baseline. Later scenarios declare every changed expression or distribution field relative to that baseline, for example:

```json
"changes": [{
  "path": "variables.duration.high",
  "description": "Assume the upper duration bound is 35 working days instead of 40."
}]
```

The renderer rejects missing or extra changed fields. Scenario identifiers start with a letter and contain letters, digits, underscores, or hyphens, up to 64 characters. Each source is a local file resolved relative to the context. All scenarios share the context's outcome unit and target comparison. Their sample counts and seeds may differ; the report uses each scenario's denominator and compares shares in percentage points without implying pairing or causation.

Context is limited to 256 KiB and the combined result files to 16 MiB. Unknown fields, duplicate JSON keys, stale hashes, missing quantiles, and inconsistent threshold counts fail validation. Complete draws allow count recomputation; capped draws allow only consistency checks against retained outcomes and full-run extrema. Hashes establish file identity, not model validity.

Render the context with companion 0.2.0:

```bash
pearl-of-wisdom-viz explain --context context.json --out report.html
```

Open the artifact before sharing it. “Middle 90%” describes the spread of simulated outcomes, not confidence in the estimated chance or a promise about reality. Ties can place more than 90% inside the percentile endpoints. No observed failures in one finite run is not a guarantee. More simulations reduce sampling noise; they don't validate input assumptions.

## Distribution artifact

Ask Pearl to retain bounded draw rows, then pipe its strict JSON result into the companion:

```bash
uv run --project . pearl-of-wisdom analyze --engine monte-carlo --data '{
  "variables": {
    "duration_ms": {"distribution": "uniform", "low": 40, "high": 80}
  },
  "expression": "duration_ms",
  "samples": 4000,
  "seed": 7,
  "return_draws": true
}' | uv run --project visualization pearl-of-wisdom-viz dist \
  --quantity duration --unit ms --out duration.html
```

`draw_limit` defaults to 10,000 and may be set from 1 through 10,000. `draw_variables` retains up to 16 named input columns aligned with every exported outcome. A capped export is a deterministic uniform subset selected without changing the engine's random stream. Full-run moments, extrema, and quantiles still use every sample.

## Scenario comparison

Forest plots take two through eight result files. The caller supplies nonempty, unique labels in the same order:

```bash
uv run --project visualization pearl-of-wisdom-viz forest \
  --input baseline.json --label baseline \
  --input candidate.json --label candidate \
  --quantity latency --unit ms --out comparison.html
```

Scenario counts and seeds stay separate. The command doesn't pool results, infer pairing, or reorder scenarios.

## Output and resources

Bokeh HTML is the default. `--resources inline` is also the default and produces one portable offline file. `shared` publishes an immutable, verified BokehJS bundle under `${XDG_DATA_HOME:-~/.local/share}/pearl-of-wisdom/viz/assets`; `PEARL_VIZ_ASSETS_DIR` overrides that directory. `cdn` uses versioned public BokehJS URLs and needs network access when opened.

`explain` supports these HTML resource modes. It doesn't export a whole-report PNG or PDF. Existing `dist` and `forest` PNG output remains available. Without JavaScript, all report scenarios and their audit text remain readable; missing shared assets leave the text and selector usable and show recovery instructions.

```bash
pearl-of-wisdom-viz dist ... --resources shared --out duration.html
PEARL_VIZ_RESOURCES=cdn pearl-of-wisdom-viz dist ... --out duration.html
pearl-of-wisdom-viz dist ... --backend matplotlib --out duration.png
```

An existing destination fails unless `--overwrite` is explicit. Publication is atomic. Success writes one JSON descriptor with absolute artifact location, media type, source and artifact hashes, dependency versions, and numerical summaries. Recording that descriptor in Pearl preserves provenance and location, not the file itself. The caller owns the artifact and any eventual shared-asset cleanup.

Every artifact states that rendering reflects supplied assumptions and doesn't establish calibration. For `dist` and `forest`, repeated `--caveat` values are escaped and shown verbatim. For `explain`, the context's limitations and per-input evidence serve that role, and the descriptor adds `context_sha256`.

To attach a report to an existing investigation, save its descriptor and record it as analysis data:

```bash
pearl-of-wisdom-viz explain --context context.json --out report.html > descriptor.json
pearl-of-wisdom --db pearl.sqlite3 record-analysis INVESTIGATION_ID \
  --data "$(<descriptor.json)"
pearl-of-wisdom --db pearl.sqlite3 show INVESTIGATION_ID
```

Keep the report and source files alongside that record. Recording the descriptor doesn't copy those files into SQLite.
