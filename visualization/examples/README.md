# Explanatory report examples

These synthetic examples show how to explain a saved model, not how to forecast a real project or price a real outing. Both use the same `explain` renderer; only the model requests and authored context change.

From the repository root:

```bash
uv run --project visualization --with-editable . python visualization/examples/generate.py \
  --example project --out-dir reports/project
uv run --project visualization --with-editable . python visualization/examples/generate.py \
  --example budget --out-dir reports/budget
```

Open `reports/project/project-deadline.html` or `reports/budget/outing-budget.html`. Select a saved scenario, compare its answer and interval with the baseline, then open audit details. Add `--overwrite` only when you intend to replace the example's existing files. `--resources shared` or `--resources cdn` chooses an explicit alternative to the default portable, offline HTML.

The generator invokes both CLIs in its Python environment. Each output directory contains the exact requests, saved results, hash-bound `context.json`, report HTML, and `descriptor.json`. The generator's `project()` and `budget()` functions contain the authored questions, input meanings, evidence statuses, limitations, and declared scenario changes.

The project model divides remaining work by daily capacity and adds external delay. Its second scenario assumes 20% less work, holding capacity and delay distributions fixed. The budget model multiplies attendance by cost per person and adds shared travel; its second scenario changes attendance from 12 to 10 people. Neither comparison establishes a causal effect or ranks the overall value of the alternatives.

To exercise installed wheels instead of the checkout's editable packages:

```bash
uv build --wheel
uv build --project visualization --wheel
uv venv .example-venv
uv pip install --python .example-venv/bin/python \
  dist/pearl_of_wisdom-0.4.0-py3-none-any.whl \
  visualization/dist/pearl_of_wisdom_viz-0.2.0-py3-none-any.whl
.example-venv/bin/python visualization/examples/generate.py \
  --example project --out-dir reports/installed-project
```

For a new question, adapt the context and model rather than editing the renderer. See the [context contract](../README.md#supply-the-meaning-not-the-answer) for validation rules and provenance limits.
