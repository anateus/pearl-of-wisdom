"""Question-led reports whose claims are derived from validated saved results."""

# ruff: noqa: E501 -- Keep authored HTML readable without splitting its text nodes.

from __future__ import annotations

import html
import json
import math
from importlib.resources import files
from typing import Any

from bokeh.embed import components
from bokeh.models import (
    ColumnDataSource,
    CustomJSHover,
    FixedTicker,
    HoverTool,
    NumeralTickFormatter,
    Span,
)
from bokeh.plotting import figure

from .explanation import Explanation, Scenario, frequency
from .model import VisualizationError
from .render import RenderedArtifact, _bokeh_resources, _ecdf

ACCENT = "#2257a6"
INK = "#17212b"
MUTED = "#53606c"
PAPER = "#f7f5ef"


def escape(value: Any) -> str:
    return html.escape(str(value))


def number(value: float) -> str:
    return f"{value:,.4g}"


def condition(report: Explanation) -> str:
    event = report.scenarios[0].threshold
    phrase = {"lt": "below", "le": "at or below", "gt": "above", "ge": "at or above"}[
        event.operator
    ]
    boundary = str(int(event.value)) if event.value.is_integer() else repr(event.value)
    return f"{phrase} {boundary} {report.unit}"


def _style_plot(plot: Any) -> None:
    plot.background_fill_color = PAPER
    plot.border_fill_color = PAPER
    plot.outline_line_color = None
    plot.grid.grid_line_color = "#cbd2d8"
    plot.grid.grid_line_alpha = 0.6
    plot.axis.axis_label_text_font_style = "normal"
    plot.axis.axis_label_text_color = INK
    plot.axis.major_label_text_color = MUTED
    plot.toolbar.logo = None


def _plots(report: Explanation) -> dict[str, Any]:
    scenarios = report.scenarios
    low = [s.result.summary.require_quantile(0.05) for s in scenarios]
    high = [s.result.summary.require_quantile(0.95) for s in scenarios]
    median = [s.result.summary.require_quantile(0.5) for s in scenarios]
    target = scenarios[0].threshold.value
    start, end = min(*low, target), max(*high, target)
    padding = (end - start) * 0.12 if start != end else max(abs(start) * 0.1, 1)
    if not all(math.isfinite(value) for value in (padding, start - padding, end + padding)):
        raise VisualizationError(
            "outcome range is too large to display; rescale the model's outcome unit"
        )
    y = list(reversed(range(len(scenarios))))
    source = ColumnDataSource(
        {
            "low": low,
            "high": high,
            "median": median,
            "y": y,
            "label": [s.label for s in scenarios],
            "identifier": [s.identifier for s in scenarios],
            "color": [ACCENT] + [MUTED] * (len(scenarios) - 1),
        },
        name="pearl-interval-data",
    )
    interval = figure(
        height=130 + 58 * len(scenarios),
        sizing_mode="stretch_width",
        x_range=(start - padding, end + padding),
        y_range=(-0.65, len(scenarios) - 0.35),
        tools="",
        toolbar_location=None,
        x_axis_label=f"{report.quantity} ({report.unit})",
    )
    _style_plot(interval)
    interval.yaxis.ticker = FixedTicker(ticks=y)
    interval.yaxis.major_label_overrides = {
        row: s.label if len(s.label) <= 24 else s.label[:21] + "..."
        for row, s in zip(y, scenarios, strict=True)
    }
    interval.yaxis.axis_line_color = None
    interval.yaxis.major_tick_line_color = None
    interval.yaxis.minor_tick_line_color = None
    interval.ygrid.grid_line_color = None
    line = interval.segment(
        "low", "y", "high", "y", source=source, line_width=7, line_color="color"
    )
    points = interval.scatter(
        "median", "y", source=source, size=12, fill_color=PAPER, line_width=3, line_color="color"
    )
    interval.add_layout(
        Span(location=target, dimension="height", line_color=INK, line_dash="dashed", line_width=2)
    )
    interval.add_tools(
        HoverTool(
            renderers=[line, points],
            tooltips=[
                ("Scenario", "@label"),
                ("5th percentile", "@low{custom}"),
                ("Median", "@median{custom}"),
                ("95th percentile", "@high{custom}"),
            ],
            formatters={
                f"@{name}": CustomJSHover(code="return String(value)")
                for name in ("low", "median", "high")
            },
        )
    )
    ecdf = figure(
        height=320,
        sizing_mode="stretch_width",
        tools="pan,wheel_zoom,reset,save",
        x_axis_label=f"{report.quantity} ({report.unit})",
        y_axis_label="Share at or below this value",
    )
    _style_plot(ecdf)
    ecdf.yaxis.formatter = NumeralTickFormatter(format="0%")
    ecdf.y_range.start, ecdf.y_range.end = 0, 1.02
    for index, scenario in enumerate(scenarios):
        assert scenario.result.draws is not None
        values, cumulative = _ecdf(scenario.result.draws.outcomes)
        data = ColumnDataSource({"outcome": values, "cumulative": cumulative})
        curve = ecdf.step(
            "outcome",
            "cumulative",
            source=data,
            mode="after",
            line_width=2,
            line_color=ACCENT if index == 0 else MUTED,
            line_dash="solid" if index % 2 == 0 else "dashed",
            legend_label=scenario.label,
        )
        curve.glyph.name = f"pearl-ecdf-{scenario.identifier}"
        points = ecdf.scatter(
            "outcome", "cumulative", source=data, size=4, alpha=0, legend_label=scenario.label
        )
        ecdf.add_tools(
            HoverTool(
                renderers=[points],
                tooltips=[
                    ("Outcome", "@outcome{custom}"),
                    ("Cumulative share", "@cumulative{custom}"),
                ],
                formatters={
                    f"@{name}": CustomJSHover(code="return String(value)")
                    for name in ("outcome", "cumulative")
                },
            )
        )
    ecdf.legend.click_policy = "hide"
    ecdf.legend.location = "bottom_right"
    return {"interval": interval, "ecdf": ecdf}


def _answer(report: Explanation, scenario: Scenario, index: int) -> str:
    event, summary = scenario.threshold, scenario.result.summary
    low, median, high = (summary.require_quantile(p) for p in (0.05, 0.5, 0.95))
    rate = frequency(event)
    lead = f"{rate} {report.subject} have {report.quantity.lower()} {condition(report)}."
    if event.matched == 0:
        lead = f"None of the {event.total:,} {report.subject} meet the target in this run."
    elif event.matched == event.total:
        lead = f"All {event.total:,} {report.subject} meet the target in this run."
    change_text = " ".join(change.description for change in scenario.changes) or "Baseline model."
    difference = ""
    if index:
        delta = 100 * (event.fraction - report.scenarios[0].threshold.fraction)
        if delta == 0:
            comparison = f"The simulated share meeting the target is unchanged from {report.scenarios[0].label}."
        else:
            comparison = (
                f"The simulated share meeting the target is {abs(delta):.1f} percentage points "
                f"{'higher' if delta > 0 else 'lower'} than {report.scenarios[0].label}."
            )
        difference = f'<p class="comparison-note">{escape(comparison)} This compares model scenarios; it does not establish a causal effect.</p>'
    return f"""<article data-scenario="{scenario.identifier}" class="scenario-answer {"is-active" if index == 0 else ""}">
<h2>{escape(scenario.label)}</h2><p class="answer"><span>Under these assumptions,</span> {escape(lead[0].lower() + lead[1:])}</p>
<p class="exact-count"><strong>{event.matched:,} of {event.total:,}</strong> simulated outcomes meet the target. Each simulation is one possible outcome of this model.</p>
<p class="change-explanation">{escape(change_text)}</p>{difference}
<dl class="interval-summary"><div><dt>Median: at least half are at or below</dt><dd>{number(median)} <span>{escape(report.unit)}</span></dd></div>
<div><dt>The middle 90% fall between</dt><dd>{number(low)} and {number(high)} <span>{escape(report.unit)}</span></dd></div></dl>
<p class="interval-explanation">This range describes the spread of simulated outcomes, not confidence in the estimated chance or a promise about a real outcome.</p>
</article>"""


def _distribution(spec: dict) -> str:
    kind = spec.get("distribution")
    if kind == "triangular" and all(k in spec for k in ("low", "mode", "high")):
        if spec["low"] == spec["high"]:
            return f"Fixed at {spec['low']}."
        return (
            f"From {spec['low']} to {spec['high']}; most likely {spec['mode']}. "
            "A triangular distribution: likelihood tapers linearly away from the most likely "
            "value toward the bounds."
        )
    if kind == "constant":
        return f"Fixed at {spec.get('value')}."
    if (
        kind == "discrete"
        and isinstance(spec.get("values"), list)
        and isinstance(spec.get("probabilities"), list)
        and len(spec["values"]) == len(spec["probabilities"])
    ):
        return (
            "; ".join(
                f"{value}: {probability}"
                for value, probability in zip(spec["values"], spec["probabilities"], strict=True)
            )
            + " (value: probability)."
        )
    return json.dumps(spec, ensure_ascii=False, sort_keys=True)


def _model(report: Explanation) -> str:
    names = "".join(
        f"<li>{escape(a.label)} <span>{escape(a.unit)}</span></li>" for a in report.assumptions
    )
    formulas, rows = [], []
    for index, scenario in enumerate(report.scenarios):
        assert scenario.result.draws is not None
        request = scenario.result.draws.effective_request
        active = "is-active" if index == 0 else ""
        formulas.append(
            f'<div data-scenario="{scenario.identifier}" class="{active}"><p class="model-scenario">{escape(scenario.label)}</p><code>{escape(request["expression"])}</code></div>'
        )
        cells = []
        for a in report.assumptions:
            reference = (
                f'<p class="evidence-reference">Reference: {escape(a.reference)}</p>'
                if a.reference
                else ""
            )
            cells.append(
                f'<tr><th scope="row">{escape(a.label)}<code>{escape(a.name)}</code></th>'
                f'<td><p>{escape(a.description)}</p><p class="distribution">{escape(_distribution(request["variables"][a.name]))} <span>{escape(a.unit)}</span></p></td>'
                f'<td><strong class="evidence-status">{escape(a.status.capitalize())}</strong><p>{escape(a.note)}</p>{reference}</td></tr>'
            )
        rows.append(
            f'<div data-scenario="{scenario.identifier}" class="{active}"><h3>{escape(scenario.label)}</h3><table class="assumptions"><thead><tr><th>Input</th><th>Meaning and values</th><th>Evidence supplied by the author</th></tr></thead><tbody>{"".join(cells)}</tbody></table></div>'
        )
    return f"""<section class="model-section" aria-labelledby="model-heading"><h2 id="model-heading">How this model works</h2>
<p>{escape(report.model_explanation)}</p>
<p>For each simulated outcome, the model samples one value for each uncertain input, keeps fixed inputs at their specified values, and applies the formula below.</p>
<div class="model-map"><ul>{names}</ul><svg class="model-arrow" viewBox="0 0 64 24" aria-hidden="true"><path d="M2 12h56m-9-8 9 8-9 8" fill="none" stroke="currentColor" stroke-width="2"/></svg>
<div class="formula">{"".join(formulas)}<p>Model arithmetic produces <strong>{escape(report.quantity.lower())}</strong>.</p></div></div>
<p class="model-caption">The arrows describe the calculation. They do not establish cause and effect. Inputs are sampled independently.</p>
<h2>What went into the model</h2>
<p>These are the input values before the scenario's formula is applied. Formula-only changes can change the outcome while leaving these sampled inputs unchanged.</p>
{"".join(rows)}</section>"""


def _audit(report: Explanation, ecdf_div: str) -> str:
    details = []
    for scenario in report.scenarios:
        result, event = scenario.result, scenario.threshold
        assert result.draws is not None
        draws = result.draws
        note = (
            "Every outcome is retained."
            if draws.returned == draws.population
            else "This curve uses a retained sample and may omit rare outcomes. The headline counts and intervals use the full run."
        )
        details.append(f"""<section><h3>{escape(scenario.label)}</h3>
<p>{event.matched:,} of {event.total:,} outcomes meet the target; exact fraction {event.fraction!r}.</p>
<p>{draws.returned:,} of {draws.population:,} draws retained. {note}</p>
<dl class="audit-values"><div><dt>5th percentile</dt><dd>{result.summary.require_quantile(0.05)!r}</dd></div><div><dt>Median</dt><dd>{result.summary.require_quantile(0.5)!r}</dd></div><div><dt>95th percentile</dt><dd>{result.summary.require_quantile(0.95)!r}</dd></div><div><dt>Minimum / maximum</dt><dd>{result.summary.minimum!r} / {result.summary.maximum!r}</dd></div><div><dt>Mean / standard deviation</dt><dd>{result.summary.mean!r} / {result.summary.standard_deviation!r}</dd></div></dl>
<p>Seed {escape(result.metadata.get("seed", "unavailable"))}; Pearl {escape(draws.pearl_version)}; Python {escape(draws.python_version)}.</p>
<p>source SHA-256 <code>{result.source_sha256}</code></p><details><summary>Saved computational request</summary><pre>{escape(json.dumps(draws.effective_request, indent=2, ensure_ascii=False))}</pre><p>Sampling input order: <code>{escape(json.dumps(draws.input_order))}</code></p></details></section>""")
    return f"""<details class="audit"><summary>Inspect the distribution, exact numbers, and sources</summary>
<p>The middle 90% interval runs from the 5th to the 95th percentile. Tied values can put more than 90% inside these endpoints. Displayed intervals are rounded; exact values appear below.</p>
<p>This cumulative curve answers: what share of retained outcomes are at or below a value? Curves describe their own retained samples. Exact threshold counts above describe the full runs.</p>{ecdf_div}{"".join(details)}
<p>Context SHA-256 <code>{report.context_sha256}</code>. Source hashes bind the report to these files; they do not validate the assumptions.</p></details>"""


def render_explanation(report: Explanation, *, resources: str = "inline") -> RenderedArtifact:
    resource_html, resource_note, shared_asset, failure_message = _bokeh_resources(resources)
    script, plots = components(_plots(report))
    answers = "".join(
        _answer(report, scenario, index) for index, scenario in enumerate(report.scenarios)
    )
    controls = "".join(
        f'<label><input type="radio" name="scenario" value="{s.identifier}" {"checked" if i == 0 else ""}><span>{escape(s.label)}</span></label>'
        for i, s in enumerate(report.scenarios)
    )
    illustrative = (
        "Illustrative example. Inputs are synthetic, not observations."
        if report.illustrative
        else "Model-based estimate. Read the assumptions and evidence before using this result."
    )
    limits = "".join(f"<li>{escape(item)}</li>" for item in report.limitations)
    style = files(__package__).joinpath("report.css").read_text()
    interaction = files(__package__).joinpath("report.js").read_text()
    content = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(report.question)}</title><style>{style}</style></head><body><main>
<header><h1>{escape(report.question)}</h1><p class="illustrative">{illustrative}</p></header>
<fieldset id="scenario-controls" hidden><legend>Choose a saved scenario</legend><div class="scenario-options">{controls}</div></fieldset>
<div id="scenario-answers">{answers}</div>
<section class="chart-section" aria-label="Outcome intervals and target"><h2>Possible outcomes and target</h2>
<p class="target-description"><strong>Target:</strong> {escape(report.quantity)} {escape(condition(report))}.</p>
<div class="chart-key"><span>Line: middle 90% of outcomes</span><span>Circle: median</span><span>Dashed line: target</span></div>
{failure_message}{plots["interval"]}
<p>Every interval uses its scenario's full run. The horizontal scale stays the same across scenarios. Outcomes outside the interval are possible.</p></section>
{_model(report)}
<section class="limitations"><h2>What could make reality different?</h2><ul>{limits}</ul>
<p>These are simulated outcomes under the supplied assumptions, not observations of what happened. More simulations reduce sampling noise; they do not validate the model. A different random seed may shift the estimated share.</p></section>
{_audit(report, plots["ecdf"])}
<footer><p>Created with Pearl. {escape(resource_note)}</p><p>Questions and input descriptions are supplied by the author; counts and intervals come from the saved results.</p></footer>
<div id="scenario-announcement" class="sr-only" role="status" aria-live="polite"></div>
</main>{resource_html}{script}<script>{interaction}</script></body></html>"""
    summaries = tuple(
        {
            "scenario": s.identifier,
            "matched": s.threshold.matched,
            "total": s.threshold.total,
            "operator": s.threshold.operator,
            "threshold": s.threshold.value,
            "p05": s.result.summary.require_quantile(0.05),
            "p50": s.result.summary.require_quantile(0.5),
            "p95": s.result.summary.require_quantile(0.95),
        }
        for s in report.scenarios
    )
    return RenderedArtifact(
        content.encode(), "text/html", "bokeh", resources, summaries, shared_asset
    )
