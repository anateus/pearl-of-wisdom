# Product
<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Coding agents and developers use Pearl while reasoning about uncertain systems. They need numerical results that remain inspectable, reproducible, and easy to carry into an investigation.

## Product Purpose

Pearl runs bounded probabilistic analyses and records the assumptions, evidence, and results that matter later. The visualization companion helps a reader understand a Monte Carlo distribution or compare scenario intervals without replacing the numerical result.

## Positioning

The core stays daemon-free and dependency-free. Visualization is a separate, explicit step whose artifacts retain source hashes, model assumptions, and the distinction between full-run summaries and retained draw subsets.

## Operating Context

Users pipe strict JSON from `pearl-of-wisdom analyze` into `pearl-of-wisdom-viz`, or render saved local result files. HTML is the normal interactive artifact; PNG supports image-only workflows. Files remain caller-owned and may later be referenced from an investigation.

## Capabilities and Constraints

The first visualization release covers Monte Carlo empirical cumulative distributions and two-to-eight-scenario forest comparisons. Numerical summaries remain authoritative. Rendering doesn't establish calibration, infer units, fetch remote input, query SQLite, execute source strings, or install missing packages. Inline HTML must work offline; shared and CDN resources are explicit alternatives.

## Evidence on Hand

The behavior contract and feasibility probes are recorded in `docs/proposal-arviz-visualization.md`. Pearl's current engine, CLI, and tests define the existing compatibility boundary. No customer claims, usage benchmarks, or brand assets are available and none should be fabricated.

## Product Principles

- Keep the number and its assumptions ahead of the chart.
- Make subsets, provenance, resource dependencies, and missing information visible.
- Fail explicitly when an artifact would be misleading or incomplete.
- Preserve a dependency-free core and caller-owned files.
