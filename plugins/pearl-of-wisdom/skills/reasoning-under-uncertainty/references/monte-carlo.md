# Monte Carlo

Use sampling only when a distribution for each uncertain input is defensible. Name the target quantity, distributions, dependencies, sample count, seed, and stopping or convergence check. Preserve extreme and missing cases instead of silently clipping them. Report quantiles or a decision probability with uncertainty from finite sampling; include a sensitivity ranking when inputs are debatable.

A simulation is a calculation under assumptions. It does not turn an assumption, generated sample, or historical correlation into evidence about the world.

When someone will use a plot and `pearl-of-wisdom-viz` is already available, request `return_draws: true` for an empirical cumulative distribution. Add `draw_variables` only for inputs that need row-level inspection. Forest comparisons use the full-run quantiles already present in each result and do not need exported draws. The reasoning skill never plots automatically.

Treat a written artifact as uninspected until the session's available browser or image tool has opened it. Report retained versus total draws, keep the subset caveat when they differ, and carry the renderer's calibration warning into the answer.
