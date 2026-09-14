# Interactive visualization of Pearl models with ArviZ

Status: implemented 2026-09-14 in Pearl 0.3.0 and `pearl-of-wisdom-viz` 0.1.0. Refined 2026-09-12 against Pearl 0.2.0 (`1ed31d4`). Monte Carlo-first scope and inline HTML defaults were confirmed during review. Simulation has a [separate follow-on specification](proposal-simulation-visualization.md).

Implementation lives in the core [Monte Carlo engine](../src/pearl_of_wisdom/engines/monte_carlo.py) and the separate [visualization package](../visualization). The companion uses ArviZ's neutral `predictions` group and `sample` dimension for distribution input, then supplies exact empirical steps and full-run forest statistics to Bokeh or Matplotlib. Visualization dependencies do not enter Pearl core or the bundled plugin wheel.

## Purpose and scope

Add optional plots when a distribution's shape or a comparison between scenarios helps explain a Pearl result. The first release covers Monte Carlo outcome distributions and scenario intervals through a separate `pearl-of-wisdom-viz` package. Pearl's core keeps zero runtime dependencies and its existing JSON CLI.

Plots accompany the numerical result and its assumptions. They don't establish that an input distribution is calibrated. Most answers should still be a number or range with the assumptions that drive it. Automatic plotting in the agent plugin stays outside this release; users or agents can invoke the companion explicitly when someone will use the artifact.

Bokeh HTML is the default output. Matplotlib PNG is an explicit alternative for image-only workflows. HTML uses inline resources by default, with CDN and shared local resources available by choice. Shared resources use the local library directory without an HTTP server.

## What clarification and pressure-testing changed

| Finding | Consequence |
| --- | --- |
| Monte Carlo sorts outcomes and discards each input mapping. | Capture selected rows before sorting. Independently sorting inputs and outcomes would destroy their relationship. |
| The engine permits 1,000,000 samples and has no variable-count limit. | Bound both retained rows and exported input columns. A row cap alone doesn't bound the payload. |
| A retained subset can omit rare outcomes. | Numerical summaries continue to describe the complete run. Label the plotted subset and never use its apparent tail to replace full-run statistics. |
| Monte Carlo returns no justification or warning field. | The renderer needs its own explicit caveat contract. It cannot promise to display warnings that core doesn't emit. |
| ArviZ defaults differ from Pearl's summaries, and the Bokeh distribution plot has no hover tool by default. | Supply summary values and interactions explicitly. A successful HTML write doesn't prove the intended behavior. |
| Simulation retains current job state, but no completion timestamp or attempt history. | Treat simulation export as separate event-capture work with explicit populations, warmup, and censoring. |
| A path recorded in SQLite doesn't copy or retain the referenced file. | Artifact ownership and resource lifetime remain explicit. Recording a reference isn't archival. |

These findings come from the current [Monte Carlo implementation](../src/pearl_of_wisdom/engines/monte_carlo.py), [simulation implementation](../src/pearl_of_wisdom/engines/system_simulation.py), [result protocol](../src/pearl_of_wisdom/engines/protocol.py), and [CLI dispatch](../src/pearl_of_wisdom/cli.py). `analyze` returns a result without opening the investigation store; recording remains a separate operation.

## Monte Carlo export contract

Add three optional request fields:

| Field | Behavior |
| --- | --- |
| `return_draws` | Boolean, default `false`. Omission or `false` preserves the existing result, including metadata. |
| `draw_limit` | Integer from 1 through 10,000, default 10,000 when export is enabled. Booleans are invalid. |
| `draw_variables` | List of distinct declared input names to retain alongside the outcome, default empty, maximum 16 names. |

Supplying either export control while `return_draws` is false or omitted is an error. Unknown fields, unknown or repeated variable names, non-finite values, and invalid limits fail through the existing validation-error path. Other engines do not accept these fields.

With export enabled, add `data.draws` with this versioned shape:

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer `1`. Versions describe the export contract, independently of the package version. |
| `population` | Number of outcome draws in the complete run, equal to `data.count`. |
| `returned` | `min(population, draw_limit)`. |
| `selection` | `all` when every row is retained; otherwise `uniform_without_replacement_v1`. |
| `indices` | Unique zero-based sample indices, in ascending generation order. |
| `outcome` | Finite numeric outcome values, one per retained index. |
| `inputs` | Mapping from each requested input name to its aligned finite numeric values; empty when none were requested. |
| `provenance` | Pearl version, Python version, effective computational request with defaults resolved, and the complete input iteration order. |

All arrays have length `returned`. Row `i` in every array belongs to the same original sample. The effective request excludes export controls; input order is explicit because the current engine consumes its random stream in that order. The renderer treats this request as data and never evaluates it.

For a capped export, select indices uniformly without replacement using a deterministic stream separate from the engine's random stream. Selection depends on the seed and the versioned selection method. Never retain only the first rows, select from sorted outcomes, or oversample extremes without weights. The same request, versions, and runtime reproduce the selection; cross-version bitwise reproducibility is not promised.

The existing count, moments, extrema, quantiles, and metadata remain identical with export on or off. They use all requested samples. Capture only selected inputs during the existing run; additional retained state scales with `returned` and selected columns, not all sample-input combinations. Core writes no sidecar files and does not rerun the analysis for export.

Reject an export if its complete UTF-8 JSON response, using the CLI's serialization, exceeds 16 MiB, including provenance. Do not silently reduce the requested rows or columns to fit. This is a format limit, not a measured performance target. The default request path gains no export allocation.

## Companion CLI and plots

`pearl-of-wisdom-viz` reads strict JSON from stdin or local files and writes one artifact. It doesn't query SQLite, run an engine, infer units, fetch a source URL, or interpret input strings as executable code. The accepted result name is `monte_carlo`, matching the engine's output. The CLI uses `monte-carlo`.

The first command is:

```bash
pearl-of-wisdom analyze --engine monte-carlo --data \
  '{"variables":{"duration_ms":{"distribution":"uniform","low":40,"high":80}},"expression":"duration_ms","samples":4000,"seed":7,"return_draws":true}' \
  | pearl-of-wisdom-viz dist --quantity duration --unit ms --out duration.html
```

`dist` accepts one result, from stdin by default or `--input FILE`. It plots an empirical cumulative distribution function of the retained outcome values. Label both axes and show hover values for outcome and cumulative proportion, plus pan, zoom, and reset. Preserve ties and support one draw, constant outcomes, discrete outcomes, negative values, and skewed distributions. Any internal reduction of the curve must preserve its empirical steps; there is no second silent sample cap.

`forest` accepts two through eight result files, using repeatable `--input FILE` and corresponding `--label TEXT` arguments in order. Labels are required, nonempty, and unique. Both commands require `--quantity` and `--unit`; `unitless` is an explicit unit. For a comparison, these describe the common outcome across every file. The caller establishes comparability because existing Pearl results don't encode physical units.

Forest markers use the full-run `0.5` quantile; interval endpoints use full-run `0.05` and `0.95` quantiles. Label this as the 5th to 95th percentile range. Never silently substitute an ArviZ default interval, a highest-density interval, or statistics computed from retained draws. Missing required quantiles produce an error naming the missing probabilities. Each scenario keeps its own sample count and seed; equal seeds don't establish paired scenarios. The HTML supports hovering for exact values and toggling individual scenarios without changing the underlying summaries.

A forest plot can consume a summary-only 0.2.0 result because its values are already present. A distribution plot requires export schema 1. Neither command synthesizes draws from summary statistics or reorders scenarios to imply a ranking the caller didn't request. Unequal scenario sample counts remain separate and do not cause padding, truncation, or pooling of distributions.

Every artifact includes a readable full-run summary, counts, available seed and version information, and the supplied quantity and unit. Where draws were exported, show retained versus total counts and the selection method. For a capped distribution, state that its shape represents a subset and may omit rare outcomes. Always state that the plot reflects supplied model assumptions and that calibration isn't established by rendering it. Repeated `--caveat TEXT` values appear verbatim as escaped text. A summary-only result marks missing provenance as unavailable.

The numerical summary and caveats in HTML remain readable without JavaScript. PNG includes the same numerical and interpretive information, with no promise of interaction. Host guidance checks the session's available image and browser tools and distinguishes creating a file from inspecting it.

## HTML resource ownership

Resource choice is `--resources inline|shared|cdn`, then `PEARL_VIZ_RESOURCES` if the flag is absent, then `inline`. Invalid HTML resource settings fail explicitly. For PNG, an explicit resource flag is an error and resource environment settings are ignored. `--backend matplotlib` requires a `.png` output; the default Bokeh backend requires `.html`. Never switch backends or resource modes silently.

| Mode | Resource location | Portability |
| --- | --- | --- |
| `inline` | Required JavaScript is embedded in the HTML. | One file opens offline on another machine. |
| `shared` | Required JavaScript lives in Pearl's shared local asset directory. | Small files open offline on this machine while those assets remain available. |
| `cdn` | Versioned BokehJS URLs point to the public CDN. | Opening requires network access; the artifact states that dependency. |

Shared mode uses `${XDG_DATA_HOME:-~/.local/share}/pearl-of-wisdom/viz/assets`, overridable with `PEARL_VIZ_ASSETS_DIR`. This notation describes path resolution; a literal tilde isn't passed to a browser. The companion copies the required assets from its installed Bokeh distribution into an immutable directory keyed by Bokeh version and a digest of the asset bundle. It retains required license notices. It never points an artifact at a virtual environment, package cache, plugin installation directory, or mutable `latest` alias.

The HTML references those files with absolute, percent-encoded `file:` URLs. Moving the HTML elsewhere on the same machine preserves the references. Plot data remains embedded in the artifact, not in the shared directory. The directory is for library code only; no HTTP service, port, daemon, browser security override, or runtime network fetch is involved.

Asset publication is atomic and safe for simultaneous renderer processes. Verify existing asset hashes before reuse. A conflicting or incomplete directory produces an actionable error; do not overwrite assets an older artifact may be using. Upgrades and companion uninstall retain published assets. Automatic pruning is outside scope because there is no registry of every artifact referencing a version. The user owns eventual deletion.

Shared HTML visibly identifies its local dependency. If a required asset fails to load, show a static message explaining that the shared library is unavailable and that portable offline output requires inline resources; preserve the numerical summary. Do not fall back to a CDN. For portable offline sharing or archiving, regenerate in inline mode. Arbitrary webviews and hosted pages are not supported consumers of local `file:` references.

## Validation, persistence, and failure behavior

The companion validates the result envelope and every field it consumes before rendering: engine, export version, finite numbers, positive counts, quantile ordering, equal array lengths, unique in-range indices, declared input columns, and consistent population and selection metadata. Duplicate JSON keys, booleans as numbers, non-finite JSON constants, truncated input, unsupported engines or versions, empty arrays, and inconsistent records are errors. Unrelated additive envelope metadata is allowed. At most eight inputs are accepted, each limited to 16 MiB before parsing. Fields used as labels, caveats, paths, or embedded metadata are escaped for their output context, including script-closing strings.

Malformed input, absent draws, unavailable backend dependencies, asset failures, or an unwritable output produce a nonzero exit and a JSON error on stderr, with no success object on stdout. Errors identify the field or operation and the corrective action where known. Installing or downloading missing packages is never an implicit render step.

Render to a temporary file beside the destination and publish only after success. Existing outputs fail unless `--overwrite` is explicit; failure before publication leaves the old file intact. Concurrent writers must not bypass that rule. Success prints one JSON object with absolute artifact path, media type, resource mode, artifact SHA-256, hashes of the exact source bytes, renderer/dependency versions, and the numerical summaries. Diagnostic output stays on stderr. For shared mode, also return the immutable asset identity and location. No raw draws are repeated on stdout.

If stdout closes after publication, return a nonzero exit; the completed artifact may remain. File publication and delivery of the success descriptor are separate operations. A later pipe failure cannot restore an overwritten file.

Callers may record this descriptor through `record-evidence` or `record-analysis`. That records provenance and location only. Files remain caller-owned, and portable archival uses inline HTML. No SQLite schema change or automatic persistence is part of this work.

## Dependencies and alternatives

ArviZ 1.x is a metapackage over its data, statistics, and plotting packages. Its converters support explicit sample dimensions and return an xarray DataTree. Use a neutral `predictions` group with a `sample` dimension for Pearl outcomes; no artificial MCMC chains or posterior labels are needed. [ArviZ package organization](https://python.arviz.org/en/stable/contributing/contributing_prs.html) and [converter contract](https://python.arviz.org/en/stable/api/generated/arviz.from_dict.html).

Use ArviZ's distribution and forest interfaces with explicit statistics and Bokeh interactions. Forest accepts precomputed statistics, so full-run Pearl quantiles can remain authoritative. A dependency lock must cover the resolved ArviZ components and backends; pinning only the metapackage doesn't fix transitive versions. The base companion installs its HTML dependencies; a companion `matplotlib` extra provides PNG. None enter Pearl core or the bundled plugin wheel. [Distribution API](https://python.arviz.org/projects/plots/en/stable/api/generated/arviz_plots.plot_dist.html) and [forest API](https://python.arviz.org/projects/plots/en/stable/api/generated/arviz_plots.plot_forest.html).

Direct Bokeh is the strongest alternative for this narrow scope: ECDFs and summary intervals don't inherently need ArviZ. It would reduce dependencies but require maintaining plotting and PNG behavior separately. This implementation retains ArviZ as the adapter; direct backend calls supply exact curves, summaries, and interactions where ArviZ defaults don't meet the contract. Plot semantics remain independent of that implementation choice.

An optional extra on Pearl core could also preserve a dependency-free default install. The separate package is preferred because the visualization release and dependency lifecycle can evolve independently of the plugin's wheel and compatibility checks. A local HTTP asset server adds availability and lifecycle work that static shared files avoid. Bokeh already supports external resource paths. [Bokeh resources](https://docs.bokeh.org/en/latest/docs/reference/resources.html).

## Acceptance and verification seams

| Seam | Independently checkable acceptance |
| --- | --- |
| Core compatibility | Existing public Monte Carlo and CLI fixtures produce identical results with export omitted or false. Other engines retain their request/result behavior, and the installed core wheel still has no runtime dependencies. |
| Export fidelity | With all rows retained, recompute an expression from each exported input row and match its outcome; recompute moments and quantiles independently and match the summary. A deterministic capped run retains the same source rows across repeats and leaves the full-run summary unchanged. |
| Bounds | Exercise one draw, exactly 10,000, a run above the cap, the existing 1,000,000-sample limit, 16 selected inputs, and each limit exceeded. Check byte limits and invalid controls through the real CLI. Extra retained inputs remain bounded under the maximum run. |
| Distribution meaning | One-value, constant, discrete, multimodal, and rare-outcome fixtures produce empirical curves with correct labels. A fixture whose retained subset misses an extreme still displays the original full-run extreme and the subset caveat. |
| Scenario meaning | Unequal sample counts, different seeds, equal intervals, and missing quantiles exercise the forest contract. Assert plotted endpoints and median against supplied full-run summaries, including a case where retained-draw statistics differ. |
| HTML behavior | Browser tests verify hover values, zoom/reset, scenario visibility, escaped hostile text, and a readable summary without JavaScript. File existence or Bokeh model inspection alone doesn't satisfy interaction acceptance. |
| Resource lifecycle | Open inline and shared artifacts in a browser with network disabled. Exercise shared paths containing spaces, moved HTML on the same machine, missing assets, concurrent first publication, and an older artifact after a newer bundle is installed. Shared files never require the installing environment to remain present. |
| Artifact lifecycle | Real stdin and file commands produce a truthful success descriptor. Invalid input, absent dependencies, render/write failures, and concurrent output attempts leave no partial artifact; failure before publication preserves an existing file. A broken stdout pipe after publication follows the documented nonzero-exit behavior. |
| Packaging and PNG | Install core and companion separately, exercise an installed-wheel pipeline, and render PNG without a browser service. Browser tests may use automation tooling as a development dependency only. |

KDE, histograms, ridge plots, pair plots, prior/posterior comparisons, MCMC diagnostics, categorical Bayes/causal charts, decision-analysis charts, automatic plugin installation, asset garbage collection, and automatic plot selection are outside this release. A later plugin rollout needs evaluation of when agents plot and whether they retain assumptions; a plotting smoke test cannot establish that benefit.

## Feasibility evidence and limits

Synthetic probes on 2026-09-12 resolved `arviz` 1.3.0, `arviz-base` 1.3.0, `arviz-plots` 1.3.1, `arviz-stats` 1.3.2, Bokeh 3.10.0, and Matplotlib 3.11.2. Explicit `predictions`/`sample` data rendered for continuous, discrete, constant, and single-value ECDFs. A forest probe placed independently supplied endpoints and median into the actual Bokeh glyph data. Matplotlib wrote a PNG. The implementation test suite now covers the CLI, export contract, both renderers, resource modes, and browser interactions.

The installed defaults were an 89% equal-tail interval and a mean point estimate. The distribution models had pan/zoom/reset tools but no hover tool. A forest call with one `ci_probs` entry failed; a controlled follow-up showed that two entries work with both equal and unequal sample counts. Unequal counts also emitted an xarray alignment warning, reinforcing the requirement to avoid relying on implicit concatenation behavior.

A separate local-resource probe opened synthetic HTML in Chrome 153.0.8010.37 with network disabled, using BokehJS 3.10.0 from a shared directory containing spaces. It rendered visible canvases with no page errors; observed requests were the HTML and a local script. That artifact was 8,279 bytes and its shared script was 1,388,321 bytes. This measures one small artifact, not general storage savings or browser compatibility. Safari, Firefox, and embedded webviews were not tested. Earlier timing and environment-size estimates are not acceptance targets, and the original one-day estimate is withdrawn until the export, interaction, and lifecycle work is planned.
