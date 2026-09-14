# Explanatory report

Mode: Read. Primary target: `visualization/src/pearl_of_wisdom_viz/explain_render.py`.

Readers want to understand a model without knowing statistical plot conventions. The approved plan is `docs/plan-explanatory-visualization.md`. Context gives the model meaning; saved calculations supply its numbers.

## Direction contract

### THESIS

Answer a concrete question, then show how to interpret and inspect that answer. The first example asks whether a project finishes within 30 working days.

### OWN-WORLD

Inherit Pearl's warm paper, dark ink, cobalt data, editorial headings, thin rules, and restrained controls. This extends the existing visual system. Charts and model diagrams are generated from data and labeled explicitly.

### STORY

Read the conditional answer, locate the deadline and interval, follow the model arithmetic, then examine assumptions. Choose a saved scenario to see its answer and explanation together. Detailed values and provenance remain available.

### FIRST VIEWPORT

The question leads at left above the answer, exact count, and visible synthetic-data note. Scenario controls precede a wide, annotated duration chart. The selected scenario is named in text. The main answer remains readable on mobile and without JavaScript.

### FORM

The composition is pinned by the approved implementation plan. It inherits the established visual direction, seed `230c9bb8`; no new direction roll is needed. The signature interaction selects a precomputed scenario, updates its explanation, and emphasizes its interval on a shared scale. Feedback is immediate, with no entrance animation hiding evidence.

### FINISH

unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Quality bar

Use the existing [typographic reference](../quality-bar/README.md). The decisive test is whether a reader can explain the result, assumptions, and limitations from the artifact alone. Agent comprehension checks remain distinct from human user feedback.
