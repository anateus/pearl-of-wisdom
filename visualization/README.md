# Pearl of Wisdom visualization companion

`pearl-of-wisdom-viz` turns validated Monte Carlo results into an empirical cumulative distribution or a scenario interval comparison. It is separate from Pearl core so `pearl-of-wisdom` keeps zero runtime dependencies.

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

```bash
pearl-of-wisdom-viz dist ... --resources shared --out duration.html
PEARL_VIZ_RESOURCES=cdn pearl-of-wisdom-viz dist ... --out duration.html
pearl-of-wisdom-viz dist ... --backend matplotlib --out duration.png
```

An existing destination fails unless `--overwrite` is explicit. Publication is atomic. Success writes one JSON descriptor with absolute artifact location, media type, source and artifact hashes, dependency versions, and numerical summaries. Recording that descriptor in Pearl preserves provenance and location, not the file itself. The caller owns the artifact and any eventual shared-asset cleanup.

Every artifact states that rendering reflects supplied assumptions and doesn't establish calibration. Repeated `--caveat` values are escaped and shown verbatim.
