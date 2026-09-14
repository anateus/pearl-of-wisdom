# Monte Carlo

Use sampling only when a distribution for each uncertain input is defensible. Name the target quantity, distributions, dependencies, sample count, seed, and stopping or convergence check. Preserve extreme and missing cases instead of silently clipping them. Report quantiles or a decision probability with uncertainty from finite sampling; include a sensitivity ranking when inputs are debatable.

A simulation is a calculation under assumptions. It does not turn an assumption, generated sample, or historical correlation into evidence about the world.

When someone will use a plot and `pearl-of-wisdom-viz` is already available, request `return_draws: true` for an empirical cumulative distribution. Add `draw_variables` only for inputs that need row-level inspection. Forest comparisons use the full-run quantiles already present in each result and do not need exported draws. The reasoning skill never plots automatically.

For sharing a model with a general audience, prefer companion 0.2.0's `explain --context FILE --out FILE.html` over an unexplained raw plot. Supply the question, units, plain-language input meanings, evidence statuses, limitations, and local result paths with their exact SHA-256 hashes. The context cannot supply the numerical answer. Use raw `dist` and `forest` plots for statistical inspection.

Before running the model, name the comparison in the core request, for example `"thresholds": {"deadline": {"operator": "le", "value": 30}}`. Core 0.4.0 supports `lt`, `le`, `gt`, and `ge` and returns full-run `matched` and `total` counts under `data.thresholds.events`. Include `return_draws: true` and quantiles `[0.05, 0.5, 0.95]` for an explanatory report. Never derive a full-run deadline probability from capped exported draws. If the saved metric is missing, rerun the model with the threshold.

The report compares named saved scenarios, not live sliders. Declare every changed expression or distribution field relative to the baseline. Label synthetic examples explicitly. Observed or inferred inputs require an authored reference, which the renderer displays without verifying. The middle 90% interval describes simulated outcomes, not confidence in the estimated probability; a scenario comparison does not establish causation. Installing the optional companion still requires authorization.

Treat a written artifact as uninspected until the session's available browser or image tool has opened it. Report retained versus total draws, keep the subset caveat when they differ, and carry the renderer's calibration warning into the answer.
