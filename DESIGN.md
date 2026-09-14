---
name: Pearl Visualization
description: Audit-sheet artifacts for inspectable probabilistic results.
colors:
  paper: "#f7f5ef"
  ink: "#17212b"
  muted: "#53606c"
  rule: "#cbd2d8"
  accent: "#2257a6"
  selection: "#c9daf4"
typography:
  display:
    fontFamily: "Iowan Old Style, Palatino Linotype, Palatino, Georgia, serif"
    fontSize: "1.85rem"
    fontWeight: 600
    lineHeight: 1.15
    letterSpacing: "-0.015em"
  title:
    fontFamily: "Iowan Old Style, Palatino Linotype, Palatino, Georgia, serif"
    fontSize: "1rem"
    fontWeight: 700
    lineHeight: 1.5
  body:
    fontFamily: "Avenir Next, Avenir, Segoe UI, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  data-compact:
    fontFamily: "Avenir Next, Avenir, Segoe UI, sans-serif"
    fontSize: "0.88rem"
    fontWeight: 400
    lineHeight: 1.5
  code:
    fontFamily: "ui-monospace, SFMono-Regular, monospace"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
spacing:
  xs: "4px"
  sm: "8px"
  md: "10px"
  lg: "20px"
  xl: "32px"
components:
  artifact-header:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.display}"
    padding: "0"
  plot-frame:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    padding: "20px 0"
  summary-table:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
  draw-coverage-note:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.muted}"
    typography: "{typography.body}"
  provenance-list:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
---

# Design System: Pearl Visualization

## Overview

**Creative North Star: "The Statistical Audit Sheet"**

Each visualization reads as the audit sheet for one computation. Warm paper, dark ink, thin rules, and a single cobalt data color give the chart enough visual authority without competing with the numerical result.

The document shell stays editorial and restrained. It puts the quantity and unit first, gives most of the width to the chart, then keeps full-run summaries, retained-draw coverage, provenance, resource requirements, and calibration limits in the same reading path.

**Key Characteristics:**

- Warm paper and dark ink establish a quiet reading surface.
- Cobalt identifies data and focus without encoding rank.
- Serif headings separate interpretation from working detail.
- Tabular numbers and thin rules keep summaries easy to compare.
- Responsive records preserve every label and value without horizontal clipping.

## Colors

The palette is deliberately small. Cobalt carries data and focus; warm paper, dark ink, muted gray, and quiet rules carry the document around it.

### Primary

- **Audit Cobalt:** Draws distribution lines, interval bars, and data markers. It also supplies the visible keyboard-focus outline.
- **Selection Blue:** Marks selected text while preserving dark-ink contrast.

### Neutral

- **Warm Paper:** Covers the HTML canvas and fills hollow forest-plot median markers.
- **Dark Ink:** Carries headings, working text, and median-marker outlines.
- **Working Gray:** De-emphasizes units, draw coverage, interpretation notes, resource notes, and PNG footer detail.
- **Quiet Rule:** Separates plot and summary regions and supplies restrained chart grids in PNG output.

## Typography

**Display Font:** Iowan Old Style, falling back through Palatino and Georgia.

**Body Font:** Avenir Next, falling back through Avenir and Segoe UI.

**Label/Mono Font:** The platform UI monospace stack, led by ui-monospace and SFMono-Regular.

**Character:** Editorial serif headings name the computation. A restrained sans serif handles reading and dense numerical comparison, while monospaced text is reserved for selection methods and source hashes.

### Hierarchy

- **Display** (600, 1.85rem, 1.15): The artifact title, with tight tracking (-0.015em) and no competing hero treatment.
- **Title** (700, 1rem, 1.5): Compact section headings such as Full-run summary and Caveats.
- **Body** (400, 1rem, 1.5): Notes, lists, table values, and supporting explanation. Paragraphs stop at 72ch.
- **Compact data** (400, 0.88rem, 1.5): Table records after the narrow-screen reflow.
- **Code** (400, 1rem, 1.5): Selection names and source hashes only.

## Layout

The HTML artifact uses one centered column capped at 1120px, with 16px side gutters, 40px above the title, and 56px below the final note. The plot stretches across the column between horizontal rules. Distribution plots use a 420px chart inside a frame with a 460px minimum height. Forest plots use at least 320px and add 74px per scenario when that is taller.

Supporting paragraphs stop at 72ch. The full-run table spans the column and uses tabular numbers. Its overflow wrapper remains keyboard focusable.

At 640px and below, side gutters narrow to 10px, top padding becomes 24px, and the plot frame contracts to a 390px minimum height. Table rows reflow into labeled vertical records. Each value pairs a label column of at least 116px, up to 40 percent of the row, with the value beside it.

PNG output keeps the same information order and cobalt, gray, and rule roles on Matplotlib's white canvas. Its figure is 9 inches wide at 160 dpi. Height starts at 5.8 inches and increases by 0.18 inches for each footer detail.

## Elevation & Depth

The document shell is flat. It uses no shadows, gradients, paper texture, or layered panels. Thin rules, whitespace, and type hierarchy separate regions. Bokeh's transient overlays belong to the library controls, outside Pearl's surface language.

## Shapes

The shell is rectilinear and has no radius scale. Plot frames and summary records rely on straight horizontal rules.

The distribution uses a 2px cobalt step line with 6px cobalt points. Forest intervals use 4px cobalt segments and 11px hollow median circles filled with warm paper and outlined in dark ink at 2px. These marks describe the statistical form; they are not decorative motifs for unrelated interface elements.

## Components

### Artifact Header

The computation title is a compact serif heading followed by a muted quantity-and-unit line. The heading has an 8px bottom margin; the unit line leaves 28px before the plot.

### Plot Frame

The chart sits between 1px quiet rules with 20px vertical padding. It stretches to the available width. Distribution hover exposes source outcome and cumulative values; forest hover exposes scenario, percentiles, count, and seed without display rounding.

Bokeh's standard pan, wheel zoom, box zoom, reset, and save controls remain recognizable. Forest legends use click-to-hide behavior, so readers can compare a subset without changing the summaries below.

### Full-run Summary Table

Desktop cells use 9px by 10px padding, a quiet bottom rule, right-aligned values, and a left-aligned scenario label. Numeric columns use tabular figures. On narrow screens, the header disappears and each row becomes a self-labeled record with left-aligned values.

### Draw Coverage Note

Distribution artifacts place a muted note directly below the plot. It states retained and population draw counts plus the selection method, and it warns when a retained subset may omit rare outcomes.

### Provenance List

Each result keeps its Pearl version, Python version, and source SHA-256 in the reading flow. Hashes use the monospace role and may wrap anywhere. Interpretation, resource-mode, and optional caveat text follow without visual promotion.

## Do's and Don'ts

### Do:

- **Do** keep the quantity and unit immediately above a width-dominant chart.
- **Do** keep full-run statistics, retained-draw coverage, provenance, resource requirements, and calibration limits visible around the chart.
- **Do** use cobalt for statistical marks and keyboard focus, with tabular figures for comparable numbers.
- **Do** reflow summary rows into labeled records at the 640px threshold.
- **Do** preserve raw source values in hover details and recognizable Bokeh controls.

### Don't:

- **Don't** use color to imply scenario rank or create decorative categories.
- **Don't** add shadows, gradients, paper texture, ornamental composition, or an oversized numeral to the audit sheet.
- **Don't** hide source hashes, subset limits, resource requirements, or calibration caveats behind interaction.
- **Don't** depend on horizontal clipping to expose a summary value on narrow screens.
- **Don't** reuse the plot's statistical marks as decorative interface motifs.
