# Explanatory visualizations for Pearl

Status: implemented in core 0.4.0 and visualization companion 0.2.0, 2026-09-14. This document preserves the approved plan; the baseline behavior below describes the pre-implementation state. See the [verification record](explanatory-visualization-verification.md) for results and remaining limits. AgentPlan project: `pearl-explanatory-visualization`.

## Outcome

A reader without statistics training should be able to explain what a model predicts, how its assumptions produce that prediction, and what could change the answer. Every numerical statement must come from a saved calculation. The artifact should make the limits of that calculation understandable too.

The first complete example answers: Will this project finish within 30 working days? It leads with a conditional answer, shows completion times against the deadline, explains the model, and compares a reduced-scope scenario. The example uses synthetic assumptions and says so prominently.

The current visual identity stays: warm paper, dark ink, cobalt data, and readable typography. The main change is the reading order and explanatory content. Existing `dist` and `forest` commands remain available for statistical inspection.

## Current behavior and extension points

The [original contract](proposal-arviz-visualization.md) defines the shipped Monte Carlo plots. The [simulation visualization proposal](proposal-simulation-visualization.md) remains a separate project.

| Current code | Verified behavior | Planned extension |
| --- | --- | --- |
| [Monte Carlo engine](../src/pearl_of_wisdom/engines/monte_carlo.py) | Samples independent inputs, sorts all outcomes, computes full-run summaries, and exports at most 10,000 aligned draws. Runs may contain up to 1,000,000 outcomes. | Optional full-run counts for named outcome thresholds. |
| [Result parser](../visualization/src/pearl_of_wisdom_viz/model.py) | Validates numerical results and draw provenance; retains the effective computational request and source hash. | Validate threshold counts and bind explanatory context to each result. |
| [Renderer](../visualization/src/pearl_of_wisdom_viz/render.py) | Leads with ECDF or interval plots, followed by statistics and provenance. | A separate report renderer that leads with the question and answer. |
| [Companion CLI](../visualization/src/pearl_of_wisdom_viz/cli.py) | Accepts quantity, unit, scenario labels, and caveats; publishes files atomically. | An additive `explain` command with a validated context document. |
| [Resource manager](../visualization/src/pearl_of_wisdom_viz/assets.py) | Supports inline, shared-local, and CDN Bokeh assets. | Reuse those resource modes for reports. |
| [Browser tests](../visualization/tests/test_browser.py) | Exercise plots, hover, responsive layout, and static fallback. | Test scenario changes, explanatory text, and keyboard use; add an independent comprehension review. |

Pearl core keeps zero runtime dependencies. The companion continues to render saved results without executing model expressions, querying investigations, fetching evidence, or calling a language model.

## First example

Use a small model whose arithmetic is easy to describe:

`completion time = remaining work / effective daily capacity + external delay`

Work is measured in engineer-days, capacity in engineer-days per working day, and delay in working days. Capacity means effective output, not headcount. A working day is the outcome unit; the artifact makes no calendar-date or holiday claim.

The baseline computational request is valid against the current engine:

```json
{
  "variables": {
    "work": {"distribution": "triangular", "low": 60, "mode": 90, "high": 150},
    "capacity": {"distribution": "triangular", "low": 2.5, "mode": 3.5, "high": 4.5},
    "delay": {"distribution": "discrete", "values": [0, 5, 10], "probabilities": [0.6, 0.3, 0.1]}
  },
  "expression": "work / capacity + delay",
  "samples": 10000,
  "seed": 7,
  "return_draws": true
}
```

The second scenario changes only the expression to `0.8 * work / capacity + delay`. Its explanation states the assumption: reducing scope reduces modeled work by 20%, while capacity and external delay keep the same distributions. It doesn't account for coordination costs, task dependencies, or a relationship between workload and productivity. Inputs are sampled independently.

A planning probe with Pearl 0.3.0 counted every exported outcome; both runs retained all 10,000 draws. The baseline had 4,568 outcomes at or below 30 working days, and reduced scope had 7,615. These figures establish that the example produces a useful comparison. Generate report copy from the saved results during implementation; don't hard-code these figures or adjust assumptions to obtain a preferred headline. Equal seeds do not authorize a claim about the probability that one individual project outperforms another.

All inputs carry the evidence status `assumed` and the explanation that they are synthetic teaching values. There is no claim of calibration to a real team.

## What the reader sees

The first viewport contains the question, the scenario name, a short answer, the synthetic-data label, and a horizontal completion-time chart with a clearly labeled deadline. For the baseline probe, the answer would read: “Under these assumptions, about 46 in 100 simulated projects finish within 30 working days.” The actual count and denominator remain available beside that rounded summary.

| Reader's question | Presentation | Numerical or authored source |
| --- | --- | --- |
| What is the answer? | Natural frequency, exact count, target, and a conditional sentence. | Full-run threshold count and supplied question. |
| What could happen? | A duration axis with median, middle 90% interval, and deadline marker. Explain “middle 90%” next to the interval. | Full-run 5th, 50th, and 95th percentiles. |
| How does the model work? | A small labeled diagram connecting work, capacity, delay, and completion time; plain-language input explanations. | Saved expression and explicit, source-bound context. |
| What changes the answer? | Baseline and reduced-scope comparison, followed by an accessible scenario selector. Name what changed and what stayed fixed. | Separate saved results and verified computational differences. |
| How much should I trust it? | Assumption status, evidence references, independence assumption, and known omissions. | Author-supplied context and saved request. |
| Can I inspect the details? | Expandable ECDF, exact values, count, seed, request, versions, and source hashes. | Existing numerical result and provenance. |

The interval view is the default. The ECDF remains an exploration detail, labeled in everyday terms such as “Share of simulations finishing by this day.” When its draws are capped, identify it as a sample and keep its values distinct from the full-run headline. Neither the sampled curve nor a smoothed density determines the deadline count.

Use a common horizontal scale across scenarios so switching cannot exaggerate a difference. Labels and patterns carry meaning alongside color. The diagram describes model arithmetic; arrows must not imply a causal relationship established from evidence.

## Numerical and context contracts

### Full-run threshold counts

Add an optional Monte Carlo request field named `thresholds`, a mapping of one through 16 distinct identifiers to finite outcome comparisons. Identifiers are nonempty strings bounded to 64 characters. Each comparison has exactly `operator` and `value`; supported operators are `lt`, `le`, `gt`, and `ge`. Reject booleans as numbers, invalid operators, unknown comparison fields, and non-finite values.

The example adds `"thresholds": {"deadline": {"operator": "le", "value": 30}}` to its request. The result adds `data.thresholds` with schema version 1 and an `events` mapping. Each event preserves its identifier, operator, and value and contains integer `matched` and `total` fields, with `total == data.count` and `0 <= matched <= total`. The fraction is derived from those counts rather than stored as another authoritative value.

Count against the sorted full outcome list already held by the engine. Binary searches distinguish strict from inclusive comparisons, including ties. No extra random draws, outcome resampling, or full input retention are needed. Include threshold definitions in the effective request when present. Omission preserves the existing request behavior and result shape. Threshold counts work with or without draw export.

The report requires the named threshold metric to exist in every result and match the requested comparison exactly. It rejects missing metrics, mismatched targets, inconsistent totals, and contradictory extrema/counts. A capped draw subset is never a fallback source for a full-run count. With complete draws, validate the count by recomputing it; with capped draws, validate that retained matches and misses are compatible with the reported population counts.

Display rounding is separate from calculation. “About 46 in 100” is a readable summary; the exact count is 4,568 of 10,000. Nonzero rare events must not become “impossible,” and a run with no observed failures must not become “guaranteed.” Distinguish the finite simulation sample from uncertainty in model assumptions. More simulations reduce sampling noise; they don't validate the model. The middle 90% outcome interval is not a confidence interval for the estimated probability.

### Explanation context

Add a strict, versioned context document consumed by `pearl-of-wisdom-viz explain --context FILE --out FILE.html`. This is a proposed command, implemented in slice 1 below.

The context supplies the question, outcome label and unit, target metric identifier, input descriptions and evidence status, a plain-language model explanation, limitations, and one through eight ordered scenarios. Each scenario includes a unique identifier, label, local result path, expected source SHA-256, and explicit changed computational fields. Resolve paths relative to the context file. Validate context size at 256 KiB and the aggregate result-input size at 16 MiB.

The renderer takes expressions, distributions, counts, and quantiles from the validated saved result. The context describes their meaning; it cannot override them or supply a precomputed headline. Bind input descriptions to declared variable names, check scenario changes against the saved effective requests, and reject a stale result hash. This first report format requires draw provenance and the 5th, 50th, and 95th percentiles.

The author declares the common outcome and units because current results don't encode units. Show that declaration and reject internally conflicting context. The renderer can check declared bindings; it cannot prove that an author's physical units or natural-language explanation are correct. Evidence statuses distinguish `assumed`, `observed`, and `inferred`; observed and inferred inputs require a supplied reference. References are displayed without fetching or validating their claims.

Treat all supplied text as escaped text, not HTML or executable code. A figure can have a supplied explanation but never an untraceable numerical assertion generated by the renderer. Hash the context as well as each result in the artifact descriptor.

### Interaction and portable output

The first report offers named, precomputed scenarios. Selecting one updates the answer, count, interval, target annotation, assumption changes, and detail view together. It never evaluates Python or user expressions in the browser. Arbitrary sliders and live model execution are deferred until there is a separate execution contract.

Use semantic HTML controls with visible focus and announced result changes. With JavaScript unavailable or shared assets missing, all scenario answers, comparisons, assumptions, and audit details remain readable. The artifact still answers its question.

HTML supports the existing inline, shared-local, and CDN policies, including explicit dependency notices and atomic publication. For `explain`, HTML is the first export. Existing `dist` and `forest` PNG behavior stays available. A complete report PDF or PNG export can follow after the reading experience is established.

## Implementation slices

Later paths marked “new” are proposed locations. Existing shared files should be edited in sequence to avoid overlap.

### 1. Produce one traceable answer from a saved run

Outcome: the baseline request can produce a simple HTML report with its question, full-run deadline count, conditional answer, and synthetic assumptions. This proves the path through core, result parsing, context validation, and publication before visual expansion.

Owned components: `src/pearl_of_wisdom/engines/monte_carlo.py`, `tests/test_monte_carlo.py`, `tests/test_cli.py`, `visualization/src/pearl_of_wisdom_viz/model.py`, and `visualization/src/pearl_of_wisdom_viz/cli.py`. Add `explanation.py` for context and facts and `explain_render.py` for the report under the companion package. Add focused `test_explanation.py` and `test_explain_render.py` tests. Put the runnable example generator and its authored context under a new `visualization/examples/project_deadline/` directory.

Start with failing tests for strict/inclusive thresholds, ties, zero/all matches, and request omission. Add a deterministic capped-export case in which the retained subset omits a matching outcome; the displayed answer must still use the full-run count. Verify identical outcomes and existing summaries with threshold reporting enabled or disabled. Cover malformed context, missing metrics, stale hashes, and a readable answer with JavaScript disabled.

Output: the context schema, generated requests and results, and a minimal `project-deadline.html`. The generator must compute hashes from the actual saved bytes and publish results before invoking the renderer.

### 2. Make the baseline model understandable

Depends on slice 1. Replace the minimal layout with the question-led reading order, annotated interval, deadline, model diagram, assumption descriptions, and expandable audit view. Use full-run quantiles for the primary chart and retained draws only in the labeled ECDF detail. Extend the example to produce the finished single-scenario artifact.

Owned components: the new report renderer and its tests, the example, `PRODUCT.md`, `DESIGN.md`, `.impeccable/design.json`, and a new `.impeccable/surfaces/explanatory-report.md`. Record lay readers as the audience of this surface while preserving the existing technical plot surface.

Verify known quantiles, constant and skewed outcomes, thresholds outside the outcome range, long labels, and rare-event wording. Inspect desktop and 390px screenshots together. A reviewer given only the artifact must be able to identify the question, answer, input assumptions, and conditional nature of the result.

Output: the first artifact suitable for Mike to read and react to. This is the first product checkpoint.

### 3. Explain scenario changes

Depends on slice 2. Add the reduced-scope scenario, an always-readable comparison, and keyboard-operable scenario selection. Keep a shared duration scale. Show changed fields and their authored meaning alongside the updated result; preserve limitations on every scenario.

Owned components: explanation context validation, report renderer, browser tests, and the example generator. Tests cover unequal simulation counts, scenario ordering, duplicate identifiers, mismatched units or thresholds, changed-field drift, and synchronized updates to every displayed fact.

Compare per-scenario deadline rates and their difference in percentage points. Don't claim a paired probability, rank overall utility, or infer the best decision from this one outcome. No attribution or sensitivity ranking is produced without a dedicated calculation.

Output: interactive `project-deadline.html` and a capture showing baseline and reduced scope before and after selection.

### 4. Prove portability and explanatory reuse

Depends on slice 3. Exercise inline, shared-local, and CDN resource modes; JavaScript-disabled reading; missing shared assets; keyboard navigation; and responsive layout. Reuse existing publication and resource code. Keep all important text outside canvas-only content.

Owned components: CLI, resource integration, report/browser tests, and examples. Add a second small synthetic example asking whether an activity stays within a budget, using only a new context and model result. This is a reuse test, not another bespoke renderer. The implementation must also support a `ge` target in focused tests.

Output: both question-driven artifacts, a context-authoring example, and failure messages that explain how to obtain a missing threshold metric or repair a context mismatch.

### 5. Run independent browser and comprehension reviews

Depends on slice 4. Use fresh subagents: one installs built wheels and tests the real CLI and browser interactions; another receives only the rendered artifact and reader questions. The comprehension reviewer must not receive source code, calculation answers, the plan, or author commentary outside the artifact. Compare its answers with a separately computed answer key. The primary agent checks the evidence and artifacts directly.

Ask the comprehension reviewer to identify the question and outcome unit, explain the answer and interval, describe the model's assumptions, explain what changed between scenarios, and name one reason a real outcome could differ. Fail if it mistakes simulated outcomes for observed project data, interprets the outcome interval as a confidence interval, treats the deadline result as a guarantee, or claims that the scenario comparison proves causation.

This is an agent comprehension check, not a human user study. Present the artifact and findings to Mike; leave real lay-reader comprehension unverified until someone in that audience has read it. Numerical and functional acceptance can pass independently of that human feedback.

Preserve the interactive HTML, source/context hashes, desktop and mobile screenshots, before/after scenario captures, a short interaction recording, a no-JavaScript capture, and the review report. After reviewing the genuine artifact, use disposable copies with a headline contradicting the visible exact count and with a planted page error to verify that the respective review procedures detect failures. Correct discovered defects and rerun the affected checks before release.

### 6. Document and release the report workflow

Depends on slice 5 and resolution of its findings. Document how an author supplies context and evidence, generates threshold metrics, inspects the artifact, and attaches it to an investigation. Update plugin guidance to prefer an explanatory report when sharing with a general audience and retain raw plots for statistical inspection. Include a worked command that uses the shipped example.

Owned components: `README.md`, `visualization/README.md`, plugin skills and their Monte Carlo reference, `plugins/pearl-of-wisdom/scripts/check_cli.py`, compatibility tests, package versions, lockfiles, plugin manifests, and bundled wheel. Use a new core minor version for the request extension and a new companion minor version for `explain`; update the plugin's currently pinned CLI compatibility range together.

Build and install both wheels in a fresh environment, run the shipped example end to end, validate the plugin, then commit, push, and reinstall using the existing authorized release workflow. Verify the remote commit and installed wheel identity. Keep previous `dist`/`forest` fixtures and their numerical behavior passing. Because this is additive and changes no persisted investigation schema, rollback is reinstalling the preceding packages; reports remain files owned by the caller.

## Verification commands and acceptance

Run from the repository root. These commands already apply to the current package layout and will include the new tests after implementation:

```bash
uv run pytest -q
uv run ruff check .
uv lock --check
uv run --project visualization pytest -q visualization/tests
uv run --project visualization ruff check visualization
uv lock --project visualization --check
uv build --wheel
uv build --project visualization --wheel
claude plugin validate --strict plugins/pearl-of-wisdom
```

Each slice runs its focused tests before the affected full suites. Building alone is not the example check: the installed-wheel review must execute the generator and render its context, then inspect the resulting HTML in a real browser. Freeze the generator command in the example README once that interface exists.

| Acceptance criterion | Where it is established |
| --- | --- |
| Every headline and interval is traceable to the correct full run. | Slice 1 count tests; slice 2 quantile tests; slice 5 independent answer key. |
| The report explains the question, model, assumptions, and limits. | Slice 2 artifact checkpoint; slice 5 blinded comprehension review and separate human feedback. |
| Scenario controls update all related content consistently. | Slice 3 browser tests and before/after artifacts. |
| The result remains readable offline, on mobile, and without JavaScript. | Slice 4 integration tests; slice 5 installed-wheel review. |
| Context can describe another domain without changes to the renderer. | Slice 4 second example. |
| Existing users retain the current command behavior and dependency boundary. | Omission/compatibility tests, existing suites, and slice 6 package checks. |

## Decisions from the pressure test

Full-run threshold counts are necessary because capped draws can miss rare outcomes. Requiring every report to export all draws would limit model runs to the export cap and leave existing larger runs unsupported.

An annotated interval is the initial chart because it makes the deadline and range visible without requiring the reader to interpret a cumulative curve. It doesn't describe multimodality by itself; the ECDF detail remains available and must not be presented as a complete model explanation.

Precomputed scenarios keep the artifact portable and reproducible. The selector chooses saved calculations; arbitrary simulation controls would require another runtime and validation design. General sensitivity analysis, causal explanations, scheduling realism, correlated inputs, additional engines, and report PDF export remain outside this phase.

No important choice requires clarification before slice 1. The 30-working-day example and two starting scenarios are implementation defaults. The first readable artifact is the point to adjust the explanatory structure based on Mike's feedback.
