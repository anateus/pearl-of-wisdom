# Explanatory visualization verification

Core 0.4.0 adds optional full-run threshold counts. Visualization companion 0.2.0 adds `explain`, which binds authored context to saved Monte Carlo results and produces a question-led HTML report. Existing distribution and forest commands remain supported. The core wheel still declares no runtime dependencies.

## Evidence

The final source suites pass: 379 core tests and 83 visualization tests. Two live host tests remain skipped because they require the explicit `PEARL_RUN_HOST_E2E=1` opt-in. Ruff, both lockfile checks, package builds, plugin validation, and both skill validators pass.

A final installed-CLI smoke check exposed an existing quantile edge case: interpolating equal endpoints could move a constant outcome just outside its extrema, which the renderer correctly rejected. The engine now returns equal endpoints directly. Nine constant-value regression cases and the original CLI-to-renderer reproduction pass. Sampling and threshold counts are unchanged.

A fresh browser-review agent installed both wheels into an isolated Python environment, confirmed imports from that environment rather than the checkout, and ran the example generator through the installed CLI modules. Its final Chrome review passed 184 checks covering desktop and 390px layouts, keyboard selection, synchronized facts and chart emphasis, audit disclosure, inline offline output, no-JavaScript reading, shared resources present or missing, and the installed constant-outcome regression. The primary agent inspected the saved evidence, report, screenshots, and artifact hashes and independently recomputed the four examples' counts and quantiles from their complete saved outcomes.

CDN behavior was tested with the version-correct Bokeh resource served by the browser test harness, not by measuring public CDN availability. The intentionally missing shared-library case preserves readable text and controls but emits `net::ERR_FILE_NOT_FOUND` and `Bokeh is not defined`. This is not a complete accessibility audit.

| Synthetic scenario | Full-run target count | Median | Middle 90% outcome interval |
| --- | --- | --- | --- |
| Project, current scope | 4,568 / 10,000 within 30 working days | 30.86 working days | 20.80 to 44.84 working days |
| Project, 20% less work | 7,615 / 10,000 within 30 working days | 25.08 working days | 16.66 to 36.92 working days |
| Outing, 12 people | 8,462 / 10,000 at or below 600 USD | 516.05 USD | 391.99 to 647.32 USD |
| Outing, 10 people | 9,872 / 10,000 at or below 600 USD | 443.31 USD | 329.50 to 559.68 USD |

These checks cover all 10,000 saved outcomes in each example, not a retained subset or extrapolation. Table values are rounded to two decimal places; reports use four significant digits and expose full precision under audit details. They are calculations under synthetic assumptions, not observed project or spending data.

## Reader and visual review

A separate fresh agent received only the rendered project report and reader questions, without source, the plan, or an answer key. It correctly explained the question, working-day unit, conditional frequencies, median and middle-90% interval, assumed inputs, model arithmetic, scenario change, and real-world limitations. Its answers were saved before a consistency check.

The reader identified ambiguity between sampled input values and formula-only changes, inconsistent selected-scenario color in the audit plot, and missing input-shape explanation. Those findings were accepted. The report now explains one sampled value per uncertain input per simulated outcome, fixed inputs, triangular sampling shapes, and application of the scenario formula after sampling. The selected interval and cumulative curve use the same emphasis. Focused regression tests and new browser captures cover the changes.

The independent visual review initially returned `fix`. After scoring the corrected captures, it returned `ship` for both material fixes, with no visible regression in the reviewed views. Impeccable preserved the existing visual identity and added a separate explanatory reading order.

Two positive controls checked the review procedures. The blinded reader detected a disposable report whose headline claimed 99 in 100 while its visible exact count remained 4,568 of 10,000. The browser listener caught a planted `PEARL_BROWSER_REVIEW_POSITIVE_CONTROL` error in a separate fixture. Neither control altered a genuine report.

This is an agent comprehension check, not a human user study. Real lay-reader comprehension remains unverified until a person in that audience reads the report. Input calibration, authored evidence claims, and physical units remain the report author's responsibility.

## Preserved artifacts

The local evidence directory is `.impeccable/review/explanatory/`. It is intentionally Git-ignored; the [example generator](../visualization/examples/README.md) provides a reproducible route to new reports without publishing local review captures.

Final installed-wheel HTML, contexts, results, descriptors, screenshots, and videos are under `installed/final/`. The main entries are `project/project-deadline.html`, `budget/outing-budget.html`, `project-interaction.webm`, `budget-interaction.webm`, and `evidence.json`. The review narrative is `installed/report.md`. Blinded answers, the positive-control review, and visual verdict remain in `comprehension.md`, `consistency-review.md`, and `finish-verdict.md`.

| Reviewed wheel | SHA-256 |
| --- | --- |
| `pearl_of_wisdom-0.4.0-py3-none-any.whl` | `0e3473f3ef3d5a40018d4d7d12ffe6634a54fd68c41b07b77c01342c3864a91a` |
| `pearl_of_wisdom_viz-0.2.0-py3-none-any.whl` | `5b7af1bdd8bbf800d5e08586b804318f43f3652b9118f818dc85e1ba44c5a997` |

No persisted investigation schema changed. Rollback is reinstalling the preceding package versions; reports and their source files remain caller-owned.
