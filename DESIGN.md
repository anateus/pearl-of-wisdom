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
  report-question:
    fontFamily: "Iowan Old Style, Palatino Linotype, Palatino, Georgia, serif"
    fontSize: "clamp(2rem, 3.4vw, 3.1rem)"
    fontWeight: 600
    lineHeight: 1.18
    letterSpacing: "-0.025em"
  report-title:
    fontFamily: "Iowan Old Style, Palatino Linotype, Palatino, Georgia, serif"
    fontSize: "1.55rem"
    fontWeight: 600
    lineHeight: 1.18
  report-scenario:
    fontFamily: "Iowan Old Style, Palatino Linotype, Palatino, Georgia, serif"
    fontSize: "1.15rem"
    fontWeight: 600
    lineHeight: 1.18
  report-body:
    fontFamily: "Avenir Next, Avenir, Segoe UI, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.6
  report-answer:
    fontFamily: "Avenir Next, Avenir, Segoe UI, sans-serif"
    fontSize: "clamp(1.25rem, 2.1vw, 1.75rem)"
    fontWeight: 400
    lineHeight: 1.4
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
  report-answer:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.report-answer}"
    padding: "18px 0 0"
  report-scenario-control:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.report-body}"
    padding: "0"
  report-model-map:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.report-body}"
    padding: "24px 0"
  report-assumptions:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
  report-audit:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.report-body}"
    padding: "8px 0"
---

# Design System: Pearl Visualization

## Overview

**Creative North Star: "The Statistical Audit Sheet"**

Each visualization reads as the audit sheet for one computation. Warm paper, dark ink, thin rules, and a single cobalt data color give the chart enough visual authority without competing with the numerical result.

The document shell stays editorial and restrained. Raw-plot artifacts put the quantity and unit first, give most of the width to the chart, then keep full-run summaries, retained-draw coverage, provenance, resource requirements, and calibration limits in the same reading path.

Explanatory reports extend this system with a question, a conditional answer, and the model behind it. They use larger reading type, a shared chart scale, and native scenario controls. Assumptions and limitations remain in the main document; exact values and source details sit in an audit disclosure.

**Key Characteristics:**

- Warm paper and dark ink establish a quiet reading surface.
- Cobalt identifies data and focus without encoding rank.
- Serif headings separate interpretation from working detail.
- Tabular numbers and thin rules keep summaries easy to compare.
- Responsive records preserve every label and value without horizontal clipping.

## Colors

The palette is deliberately small. Cobalt carries data and focus; warm paper, dark ink, muted gray, and quiet rules carry the document around it.

### Primary

- **Audit Cobalt:** Draws distribution lines, interval bars, and data markers. It also supplies the visible keyboard-focus outline. Reports use it for the selected scenario's control label, interval, median, and cumulative curve. The other scenarios' chart marks use Working Gray.
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

**Character:** Editorial serif headings name the computation or question. A restrained sans serif handles reading and dense numerical comparison. Monospaced text identifies selection methods and source hashes; reports also use it for input identifiers, formulas, and saved computational requests.

### Hierarchy

- **Display** (600, 1.85rem, 1.15): The artifact title, with tight tracking (-0.015em) and no competing hero treatment.
- **Title** (700, 1rem, 1.5): Compact section headings such as Full-run summary and Caveats.
- **Body** (400, 1rem, 1.5): Notes, lists, table values, and supporting explanation. Paragraphs stop at 72ch.
- **Compact data** (400, 0.88rem, 1.5): Table records after the narrow-screen reflow.
- **Code** (400, 1rem, 1.5): Selection names and source hashes only.

These compact roles remain the raw-plot type scale. Reports use the separate `report-*` roles: a fluid question heading with balanced wrapping and a 23ch measure, serif section and selected-scenario headings, more open body leading, and a fluid sans serif answer capped at 57ch. The conditional phrase uses Working Gray within the answer. Exact counts use bold tabular figures at 0.95rem; interval values use tabular figures at 1.3rem with smaller units. Report paragraphs stop at 73ch.

## Layout

The raw-plot HTML artifact uses one centered column capped at 1120px, with 16px side gutters, 40px above the title, and 56px below the final note. The plot stretches across the column between horizontal rules. Distribution plots use a 420px chart inside a frame with a 460px minimum height. Forest plots use at least 320px and add 74px per scenario when that is taller.

Supporting paragraphs stop at 72ch. The full-run table spans the column and uses tabular numbers. Its overflow wrapper remains keyboard focusable.

At 640px and below, side gutters narrow to 10px, top padding becomes 24px, and the plot frame contracts to a 390px minimum height. Table rows reflow into labeled vertical records. Each value pairs a label column of at least 116px, up to 40 percent of the row, with the value beside it.

PNG output keeps the same information order and cobalt, gray, and rule roles on Matplotlib's white canvas. Its figure is 9 inches wide at 160 dpi. Height starts at 5.8 inches and increases by 0.18 inches for each footer detail.

Reports use a centered column capped at 1056px with 32px side gutters, 36px top padding, and 32px bottom padding. The annotated interval chart sits between thin rules with 26px above and 16px below; its height is 130px plus 58px per scenario. Scenario intervals share one horizontal scale. The model section starts 44px below the chart and places the input list, a 64px arrow, and the formula in three columns with 24px gaps.

At 640px and below, report gutters become 16px and top padding becomes 26px. The question becomes 2rem and the answer 1.25rem. Interval summaries stack vertically. The model map becomes one column, its input list uses two columns, and its arrow rotates downward. Assumption rows become vertical records with their input names, descriptions, distributions, and evidence still together. Audit values reflow from three columns to two. Scenario labels wrap onto additional rows.

## Elevation & Depth

The document shell is flat. It uses no shadows, gradients, paper texture, or layered panels. Thin rules, whitespace, and type hierarchy separate regions. Bokeh's transient overlays belong to the library controls, outside Pearl's surface language.

## Shapes

The shell is rectilinear and has no radius scale. Plot frames and summary records rely on straight horizontal rules.

The distribution uses a 2px cobalt step line with 6px cobalt points. Forest intervals use 4px cobalt segments and 11px hollow median circles filled with warm paper and outlined in dark ink at 2px. These marks describe the statistical form; they are not decorative motifs for unrelated interface elements.

The report's primary intervals use 7px segments and 12px hollow median circles with 3px outlines. A 2px dashed ink line marks the target. These heavier marks support the annotated overview; the audit's cumulative curves keep a 2px line. Native radio circles and disclosure markers retain their familiar control shapes.

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

### Report Question and Answer

The question uses the report heading role above a muted statement of whether the inputs are illustrative. The answer begins below a quiet top rule, with the selected scenario named in a small muted serif heading. A complete conditional sentence carries the estimate; the exact count, declared changes, comparison, and labeled interval values follow. The limitation on interpreting that interval stays visible below its values.

### Saved-scenario Control

A native radio group sits under the question, with a plain legend and labels that wrap as needed. Each radio is 18px; labels have 7px vertical padding. The checked label uses cobalt and weight 600. Keyboard focus uses a 3px cobalt outline offset by 5px.

Selection immediately updates the answer, comparison, model formula, assumptions, and chart emphasis. A polite status announcement reads the selected scenario and answer. The control appears only when JavaScript runs and more than one scenario exists. Without JavaScript, all scenario explanations remain in document order. No entrance animation delays the content.

### Model Arithmetic

Input names use semibold body text with smaller muted units underneath. A thin SVG arrow connects them to the selected scenario's formula and named output. The arrow describes the arithmetic, and its caption states the independence assumption and limit on causal interpretation. The formula uses the platform monospace stack. Horizontal rules and whitespace frame this component without a panel or shadow.

### Assumptions Table

Three desktop columns hold the input, its meaning and values, and author-supplied evidence. The first and last columns occupy 23 and 29 percent of the table. Cells align left and use 16px padding above, below, and to the right. Input names stay prominent; identifiers, distribution details, units, notes, and references use smaller muted text. Evidence status is written out in semibold text. Narrow screens stack each input's cells into one record.

### Report Audit Disclosure

A native details element sits between quiet rules. Its summary uses semibold body text with 12px vertical padding; hover turns it cobalt, and keyboard focus uses the report outline. It opens to the cumulative curves, exact values, draw coverage, versions, seeds, and source hashes for every scenario. A nested disclosure holds each saved computational request.

The main document keeps the conditional answer, full-run count, interval explanation, assumptions, limitations, and resource note visible. The audit uses tabular figures and wrapping source details, and remains operable without JavaScript.

## Do's and Don'ts

### Do:

- **Do** keep the quantity and unit immediately above a width-dominant chart in raw-plot artifacts.
- **Do** keep full-run statistics, retained-draw coverage, provenance, resource requirements, and calibration limits visible around raw plots.
- **Do** use cobalt for statistical marks and keyboard focus, with tabular figures for comparable numbers.
- **Do** reflow summary rows into labeled records at the 640px threshold.
- **Do** preserve raw source values in hover details and recognizable Bokeh controls.
- **Do** keep report answers, model explanations, and chart emphasis synchronized with the selected scenario.
- **Do** preserve the shared interval scale and label the target, median, and middle 90% in reports.

### Don't:

- **Don't** use color to imply scenario rank or create decorative categories.
- **Don't** add shadows, gradients, paper texture, ornamental composition, or an oversized numeral to the audit sheet.
- **Don't** hide source hashes, subset limits, resource requirements, or calibration caveats behind interaction in raw-plot artifacts.
- **Don't** depend on horizontal clipping to expose a summary value on narrow screens.
- **Don't** reuse the plot's statistical marks as decorative interface motifs.
- **Don't** move the report's assumptions, interval explanation, or model limitations into its audit disclosure.
