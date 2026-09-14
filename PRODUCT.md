# Product
<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Coding agents and developers use Pearl while reasoning about uncertain systems. They need numerical results that remain inspectable, reproducible, and easy to carry into an investigation.

Explanatory reports also serve readers who don't know statistical plot conventions. They need to understand what a model says, how it reaches that answer, and why reality could differ.

## Product Purpose

Pearl runs bounded probabilistic analyses and records the assumptions, evidence, and results that matter later. The visualization companion explains a model's answer to a concrete question or supports technical inspection of distributions and scenario intervals. Saved numerical results remain authoritative.

## Positioning

The core stays daemon-free and dependency-free. Visualization is a separate, explicit step whose artifacts retain source hashes, model assumptions, and the distinction between full-run summaries and retained draw subsets.

## Operating Context

Users pipe strict JSON from `pearl-of-wisdom analyze` into `pearl-of-wisdom-viz`, or render saved local result files. For an explanatory report, authors bind a question, input meanings, evidence statuses, and limitations to saved calculations using a context file. HTML is the normal interactive artifact; raw plot PNGs support image-only workflows. Files remain caller-owned and may later be referenced from an investigation.

## Capabilities and Constraints

Visualization covers question-led Monte Carlo reports with one through eight saved scenarios, empirical cumulative distributions, and two-to-eight-scenario forest comparisons. Report answers use named full-run threshold counts, and primary intervals use full-run quantiles. Numerical summaries remain authoritative. Rendering doesn't establish calibration, infer units, fetch remote input, query SQLite, execute source strings, or install missing packages. Inline HTML must work offline; shared and CDN resources are explicit alternatives. General sensitivity rankings, live simulation controls, and whole-report PNG/PDF export are outside the current report workflow.

## Evidence on Hand

The raw-plot contract and feasibility probes are recorded in `docs/proposal-arviz-visualization.md`; the report contract is in `docs/plan-explanatory-visualization.md`. The shipped examples use synthetic inputs. Agent comprehension checks are not human user studies; real lay-reader comprehension remains unverified until a person in that audience reads the report. No customer claims or usage benchmarks are available and none should be fabricated.

## Product Principles

- Keep the number and its assumptions ahead of the chart.
- Make subsets, provenance, resource dependencies, and missing information visible.
- Fail explicitly when an artifact would be misleading or incomplete.
- Preserve a dependency-free core and caller-owned files.
