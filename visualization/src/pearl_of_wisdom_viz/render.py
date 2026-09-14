"""Render validated Pearl results without changing their statistical meaning."""
# ruff: noqa: E501

from __future__ import annotations

import html
import io
from collections import Counter
from dataclasses import dataclass
from typing import Any

import numpy as np
from arviz_base import from_dict
from arviz_plots import plot_dist
from bokeh.embed import components
from bokeh.models import ColumnDataSource, CustomJSHover, HoverTool
from bokeh.plotting import figure
from bokeh.resources import Resources

from .assets import publish_shared_assets
from .model import PearlResult, VisualizationError


@dataclass(frozen=True, slots=True)
class RenderedArtifact:
    content: bytes
    media_type: str
    backend: str
    resource_mode: str | None
    summaries: tuple[dict[str, Any], ...]
    shared_asset: dict[str, str] | None = None


def _text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VisualizationError(f"{label} must be nonempty")
    return value


def _axis_label(quantity: str, unit: str) -> str:
    return f"{quantity} ({unit})" if unit != "unitless" else quantity


def _summary_dict(result: PearlResult, *, label: str | None = None) -> dict[str, Any]:
    summary = result.summary
    item: dict[str, Any] = {
        "count": summary.count,
        "seed": result.metadata.get("seed", "unavailable"),
        "mean": summary.mean,
        "standard_deviation": summary.standard_deviation,
        "minimum": summary.minimum,
        "maximum": summary.maximum,
    }
    if label is not None:
        item = {
            "label": label,
            "count": summary.count,
            "seed": result.metadata.get("seed", "unavailable"),
            "p05": summary.require_quantile(0.05),
            "p50": summary.require_quantile(0.5),
            "p95": summary.require_quantile(0.95),
        }
    return item


def _ecdf(outcomes: tuple[float, ...]) -> tuple[list[float], list[float]]:
    counts = Counter(outcomes)
    values = sorted(counts)
    cumulative: list[float] = []
    seen = 0
    for value in values:
        seen += counts[value]
        cumulative.append(seen / len(outcomes))
    return values, cumulative


def _static_document(
    *,
    title: str,
    plot_html: str,
    results: tuple[PearlResult, ...],
    labels: tuple[str, ...] | None,
    quantity: str,
    unit: str,
    caveats: tuple[str, ...],
    resource_note: str,
) -> str:
    escaped_title = html.escape(title)
    rows: list[str] = []
    for index, result in enumerate(results):
        summary = result.summary
        label = labels[index] if labels is not None else "Result"
        interval_cells = ""
        if labels is not None:
            interval_cells = (
                f'<td data-label="5th percentile">{summary.require_quantile(0.05):.12g}</td>'
                f'<td data-label="Median">{summary.require_quantile(0.5):.12g}</td>'
                f'<td data-label="95th percentile">{summary.require_quantile(0.95):.12g}</td>'
            )
        rows.append(
            "<tr>"
            f"<th scope=\"row\">{html.escape(label)}</th>"
            f'<td data-label="Count">{summary.count}</td>{interval_cells}'
            f'<td data-label="Mean">{summary.mean:.12g}</td>'
            f'<td data-label="Std. dev.">{summary.standard_deviation:.12g}</td>'
            f'<td data-label="Minimum">{summary.minimum:.12g}</td>'
            f'<td data-label="Maximum">{summary.maximum:.12g}</td>'
            f'<td data-label="Seed">{html.escape(str(result.metadata.get("seed", "unavailable")))}</td>'
            "</tr>"
        )
    draw_note = ""
    if len(results) == 1 and results[0].draws is not None:
        draws = results[0].draws
        draw_note = (
            f"<p class=\"draw-note\">Retained {draws.returned} of {draws.population} draws "
            f"using <code>{html.escape(draws.selection)}</code>."
        )
        if draws.returned < draws.population:
            draw_note += " The plotted subset may omit rare outcomes."
        draw_note += "</p>"
    caveat_items = "".join(f"<li>{html.escape(item)}</li>" for item in caveats)
    interval_headers = (
        "<th>5th percentile</th><th>Median</th><th>95th percentile</th>"
        if labels is not None
        else ""
    )
    version_items = []
    for index, result in enumerate(results):
        label = labels[index] if labels is not None else "Result"
        pearl_version = result.draws.pearl_version if result.draws is not None else "unavailable"
        python_version = result.draws.python_version if result.draws is not None else "unavailable"
        version_items.append(
            f"<li>{html.escape(label)}: Pearl {html.escape(pearl_version)}, "
            f"Python {html.escape(python_version)}; source SHA-256 "
            f"<code>{html.escape(result.source_sha256)}</code></li>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escaped_title}</title>
<style>
:root{{--paper:#f7f5ef;--ink:#17212b;--muted:#53606c;--rule:#cbd2d8;--accent:#2257a6}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--ink);font-family:"Avenir Next",Avenir,"Segoe UI",sans-serif;line-height:1.5}}
main{{width:min(1120px,calc(100% - 32px));margin:0 auto;padding:40px 0 56px}}
h1,h2{{font-family:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif}} h1{{font-size:1.85rem;font-weight:600;letter-spacing:-.015em;line-height:1.15;margin:0 0 8px}} p{{max-width:72ch}}
.unit{{color:var(--muted);margin:0 0 28px}} .plot{{min-height:460px;border-block:1px solid var(--rule);padding:20px 0}}
h2{{font-size:1rem;margin:32px 0 10px}} .table-scroll{{max-width:100%;overflow-x:auto}} table{{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}}
th,td{{padding:9px 10px;border-bottom:1px solid var(--rule);text-align:right}} th:first-child{{text-align:left}}
.draw-note,.resource-note,.interpretation{{color:var(--muted)}} code{{font-family:ui-monospace,SFMono-Regular,monospace}} .versions code{{overflow-wrap:anywhere}}
a:focus-visible,button:focus-visible{{outline:3px solid var(--accent);outline-offset:3px}} ::selection{{background:#c9daf4;color:var(--ink)}}
@media(max-width:640px){{main{{width:min(100% - 20px,1120px);padding-top:24px}}.plot{{min-height:390px}}table,thead,tbody,tr,th,td{{display:block;width:100%}}thead{{display:none}}tr{{border-block:1px solid var(--rule);padding:8px 0}}th,td{{border:0;padding:5px 4px;text-align:left}}th[scope="row"]{{font-size:1rem;padding-bottom:7px}}td{{display:grid;grid-template-columns:minmax(116px,40%) 1fr;gap:12px;font-size:.88rem;font-variant-numeric:tabular-nums}}td::before{{content:attr(data-label);font-weight:600;color:var(--muted)}}}}
</style>
</head>
<body><main>
<h1>{escaped_title}</h1><p class="unit">{html.escape(quantity)} · {html.escape(unit)}</p>
<div class="plot" aria-label="{html.escape(title, quote=True)}">{plot_html}</div>
{draw_note}
<h2>Full-run summary</h2>
<div class="table-scroll" tabindex="0"><table><thead><tr><th>Scenario</th><th>Count</th>{interval_headers}<th>Mean</th><th>Std. dev.</th><th>Minimum</th><th>Maximum</th><th>Seed</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<ul class="versions">{''.join(version_items)}</ul>
<p class="interpretation">This plot reflects the supplied model assumptions. Rendering doesn't establish that the inputs are calibrated.</p>
<p class="resource-note">{html.escape(resource_note)}</p>
{f'<h2>Caveats</h2><ul>{caveat_items}</ul>' if caveat_items else ''}
</main></body></html>"""


def _bokeh_html(
    model: Any, *, resources: str, document: dict[str, Any]
) -> tuple[bytes, dict[str, str] | None]:
    shared_asset = None
    failure_message = ""
    if resources == "inline":
        resource_html = Resources(mode="inline", components=["bokeh"]).render()
        note = "BokehJS is embedded; this artifact opens offline as one file."
    elif resources == "cdn":
        resource_html = Resources(mode="cdn", components=["bokeh"]).render()
        note = "Interactive rendering requires the versioned public BokehJS CDN."
    elif resources == "shared":
        published = publish_shared_assets()
        resource_html = published.resource_html
        shared_asset = {
            "identity": published.identity,
            "location": str(published.location),
        }
        note = f"Interactive rendering uses the local shared library at {published.location}."
        failure_message = (
            '<p id="pearl-shared-error" hidden>Shared visualization library unavailable. '
            "Regenerate with inline resources for portable offline output.</p>"
        )
    else:
        raise VisualizationError(f"HTML resource mode {resources!r} is unsupported")
    script, div = components(model)
    content = _static_document(
        plot_html=f"{failure_message}{div}{resource_html}{script}",
        resource_note=note,
        **document,
    ).encode()
    return content, shared_asset


def _png_document(
    *,
    draw: Any,
    title: str,
    interpretation: str,
    details: tuple[str, ...],
) -> bytes:
    try:
        import matplotlib.pyplot as plt
    except ImportError as error:
        raise VisualizationError(
            "Matplotlib backend is unavailable; install pearl-of-wisdom-viz[matplotlib]"
        ) from error
    height = 5.8 + 0.18 * len(details)
    figure_object, axes = plt.subplots(figsize=(9, height))
    draw(axes)
    figure_object.suptitle(title, x=0.01, ha="left", fontsize=14, fontweight="bold")
    footer = "\n".join((*details, interpretation))
    figure_object.text(0.01, 0.01, footer, fontsize=7.5, color="#53606c", va="bottom")
    figure_object.tight_layout(rect=(0, min(0.32, 0.06 + 0.028 * len(details)), 1, 0.96))
    output = io.BytesIO()
    figure_object.savefig(output, format="png", dpi=160, metadata={"Title": title})
    plt.close(figure_object)
    return output.getvalue()


def render_distribution(
    result: PearlResult,
    *,
    quantity: str,
    unit: str,
    backend: str = "bokeh",
    resources: str = "inline",
    caveats: tuple[str, ...] = (),
) -> RenderedArtifact:
    quantity = _text(quantity, "quantity")
    unit = _text(unit, "unit")
    if result.draws is None:
        raise VisualizationError(
            "distribution rendering requires data.draws schema 1; rerun with return_draws=true"
        )
    values, cumulative = _ecdf(result.draws.outcomes)
    title = f"Empirical cumulative distribution of {quantity}"
    summary = (_summary_dict(result),)
    if backend == "bokeh":
        tree = from_dict(
            {"predictions": {"outcome": np.asarray(result.draws.outcomes)}},
            sample_dims=[],
            pred_dims={"outcome": ["sample"]},
        )
        plots = plot_dist(
            tree,
            var_names=["outcome"],
            group="predictions",
            sample_dims=["sample"],
            kind="ecdf",
            backend="bokeh",
            visuals={
                "credible_interval": False,
                "point_estimate": False,
                "point_estimate_text": False,
            },
        )
        plot = plots.get_viz("plot", "outcome")
        line = plots.get_viz("dist", "outcome")
        plot.sizing_mode = "stretch_width"
        plot.height = 420
        plot.toolbar_location = "right"
        line.glyph.line_color = "#2257a6"
        source = ColumnDataSource(
            {"x": values, "y": cumulative, "outcome": values, "cumulative": cumulative}
        )
        line.data_source = source
        markers = plot.scatter("outcome", "cumulative", source=source, size=6, color="#2257a6")
        exact_hover = CustomJSHover(code="return String(value)")
        plot.add_tools(
            HoverTool(
                renderers=[markers],
                tooltips=[("Outcome", "@outcome{custom}"), ("Cumulative", "@cumulative{custom}")],
                formatters={"@outcome": exact_hover, "@cumulative": exact_hover},
            )
        )
        plot.xaxis.axis_label = _axis_label(quantity, unit)
        plot.yaxis.axis_label = "Cumulative proportion"
        plot.title.text = title
        document = {
            "title": title,
            "results": (result,),
            "labels": None,
            "quantity": quantity,
            "unit": unit,
            "caveats": caveats,
        }
        content, shared_asset = _bokeh_html(plot, resources=resources, document=document)
        return RenderedArtifact(content, "text/html", backend, resources, summary, shared_asset)
    if backend == "matplotlib":
        interpretation = "Full-run summary shown; plot reflects supplied assumptions, not calibration."
        draws = result.draws
        details = (
            f"Count {result.summary.count}; mean {result.summary.mean:.12g}; std. dev. {result.summary.standard_deviation:.12g}; min {result.summary.minimum:.12g}; max {result.summary.maximum:.12g}; seed {result.metadata.get('seed', 'unavailable')}",
            f"Retained {draws.returned} of {draws.population} draws using {draws.selection}.",
            f"Pearl {draws.pearl_version}; Python {draws.python_version}.",
            *caveats,
        )

        def draw(axes: Any) -> None:
            axes.step(values, cumulative, where="post", color="#2257a6", linewidth=2)
            axes.scatter(values, cumulative, color="#2257a6", s=18)
            axes.set_xlabel(_axis_label(quantity, unit))
            axes.set_ylabel("Cumulative proportion")
            axes.set_ylim(0, 1.03)
            axes.grid(axis="y", color="#cbd2d8", linewidth=0.7)

        content = _png_document(
            draw=draw, title=title, interpretation=interpretation, details=details
        )
        return RenderedArtifact(content, "image/png", backend, None, summary)
    raise VisualizationError(f"backend {backend!r} is unsupported")


def render_forest(
    results: tuple[PearlResult, ...],
    labels: tuple[str, ...],
    *,
    quantity: str,
    unit: str,
    backend: str = "bokeh",
    resources: str = "inline",
    caveats: tuple[str, ...] = (),
) -> RenderedArtifact:
    quantity = _text(quantity, "quantity")
    unit = _text(unit, "unit")
    if not 2 <= len(results) <= 8:
        raise VisualizationError("forest requires between two and eight results")
    if len(labels) != len(results):
        raise VisualizationError("forest requires one label for each result")
    if any(not isinstance(label, str) or not label.strip() for label in labels):
        raise VisualizationError("forest labels must be nonempty")
    if len(set(labels)) != len(labels):
        raise VisualizationError("forest labels must be unique")
    summaries = tuple(
        _summary_dict(result, label=label)
        for result, label in zip(results, labels, strict=True)
    )
    title = f"Scenario intervals for {quantity}"
    if backend == "bokeh":
        source = ColumnDataSource(
            {
                "label": list(labels),
                "p05": [item["p05"] for item in summaries],
                "p50": [item["p50"] for item in summaries],
                "p95": [item["p95"] for item in summaries],
                "count": [item["count"] for item in summaries],
                "seed": [item["seed"] for item in summaries],
            }
        )
        plot = figure(
            title=title,
            y_range=list(reversed(labels)),
            height=max(320, 74 * len(labels)),
            sizing_mode="stretch_width",
            tools="pan,wheel_zoom,box_zoom,reset,save",
            x_axis_label=_axis_label(quantity, unit),
        )
        renderers = []
        for index, label in enumerate(labels):
            view_source = ColumnDataSource({key: [value[index]] for key, value in source.data.items()})
            interval = plot.segment(
                "p05", "label", "p95", "label", source=view_source, line_width=4,
                color="#2257a6", legend_label=label,
            )
            marker = plot.scatter(
                "p50", "label", source=view_source, size=11, color="#f7f5ef",
                line_color="#17212b", line_width=2, legend_label=label,
            )
            renderers.extend([interval, marker])
        plot.add_tools(
            HoverTool(
                renderers=renderers,
                tooltips=[
                    ("Scenario", "@label"), ("5th percentile", "@p05{custom}"),
                    ("Median", "@p50{custom}"), ("95th percentile", "@p95{custom}"),
                    ("Count", "@count"), ("Seed", "@seed"),
                ],
                formatters={
                    field: CustomJSHover(code="return String(value)")
                    for field in ("@p05", "@p50", "@p95")
                },
            )
        )
        plot.legend.click_policy = "hide"
        plot.legend.title = "Scenarios (click to toggle)"
        document = {
            "title": title,
            "results": results,
            "labels": labels,
            "quantity": quantity,
            "unit": unit,
            "caveats": ("Intervals show the 5th to 95th percentile range.", *caveats),
        }
        content, shared_asset = _bokeh_html(plot, resources=resources, document=document)
        return RenderedArtifact(content, "text/html", backend, resources, summaries, shared_asset)
    if backend == "matplotlib":
        lows = [item["p05"] for item in summaries]
        medians = [item["p50"] for item in summaries]
        highs = [item["p95"] for item in summaries]

        def draw(axes: Any) -> None:
            positions = list(reversed(range(len(labels))))
            axes.errorbar(
                medians,
                positions,
                xerr=[
                    [median - low for median, low in zip(medians, lows, strict=True)],
                    [high - median for median, high in zip(medians, highs, strict=True)],
                ],
                fmt="o",
                color="#2257a6",
                ecolor="#2257a6",
                capsize=5,
                linewidth=2,
            )
            axes.set_yticks(positions, labels)
            axes.set_xlabel(_axis_label(quantity, unit))
            axes.grid(axis="x", color="#cbd2d8", linewidth=0.7)

        content = _png_document(
            draw=draw,
            title=title,
            interpretation=(
                "5th to 95th percentile range from full-run summaries; "
                "plot reflects supplied assumptions, not calibration."
            ),
            details=tuple(
                f"{item['label']}: n={item['count']}, seed={item['seed']}, "
                f"p05={item['p05']:.12g}, median={item['p50']:.12g}, p95={item['p95']:.12g}"
                for item in summaries
            )
            + caveats,
        )
        return RenderedArtifact(content, "image/png", backend, None, summaries)
    raise VisualizationError(f"backend {backend!r} is unsupported")
