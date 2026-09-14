"""Generate synthetic explanatory artifacts through the installed Pearl CLIs."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def assumption(label: str, unit: str, description: str) -> dict:
    return {
        "label": label,
        "unit": unit,
        "description": description,
        "evidence": {
            "status": "assumed",
            "note": "Synthetic teaching values, not observed team data.",
        },
    }


def project() -> tuple[dict, dict, list[tuple[str, str, dict, list]]]:
    request = {
        "variables": {
            "work": {"distribution": "triangular", "low": 60, "mode": 90, "high": 150},
            "capacity": {"distribution": "triangular", "low": 2.5, "mode": 3.5, "high": 4.5},
            "delay": {
                "distribution": "discrete",
                "values": [0, 5, 10],
                "probabilities": [0.6, 0.3, 0.1],
            },
        },
        "expression": "work / capacity + delay",
    }
    context = {
        "schema_version": 1,
        "illustrative": True,
        "question": "Will this project finish within 30 working days?",
        "outcome": {
            "label": "Completion time",
            "unit": "working days",
            "subject": "simulated projects",
        },
        "target": {"id": "deadline", "operator": "le", "value": 30},
        "model": {
            "explanation": (
                "Divide remaining work by effective daily capacity, then add external delay. "
                "A working day is the unit of time; this model does not predict a calendar date."
            ),
            "inputs": {
                "work": assumption(
                    "Remaining work",
                    "engineer-days",
                    "Work ranges from 60 to 150 engineer-days, with 90 the most likely value. "
                    "One engineer-day is one person's full day of work.",
                ),
                "capacity": assumption(
                    "Effective daily capacity",
                    "engineer-days per working day",
                    "The team delivers between 2.5 and 4.5 engineer-days of work per day, "
                    "most likely 3.5. This is effective output, not headcount.",
                ),
                "delay": assumption(
                    "External delay",
                    "working days",
                    "External dependencies add 0, 5, or 10 working days, "
                    "with assumed chances of 60%, 30%, and 10%.",
                ),
            },
            "limitations": [
                "Synthetic example. These assumptions have not been calibrated to a real team.",
                "Work, capacity, and external delay are sampled independently. In reality, "
                "larger projects could also reduce productivity or encounter more delays.",
                "Task dependencies, coordination costs, holidays, and changes in team capacity "
                "over time are omitted.",
                "The scope comparison assumes removing 20% of scope removes 20% of work. "
                "It does not measure the cost or value of the removed features.",
            ],
        },
    }
    scenarios = [
        ("baseline", "Current scope", request, []),
        (
            "reduced_scope",
            "20% less work",
            {**request, "expression": "0.8 * work / capacity + delay"},
            [
                {
                    "path": "expression",
                    "description": (
                        "Reduce modeled work by 20%. "
                        "Capacity and external-delay distributions stay unchanged."
                    ),
                },
            ],
        ),
    ]
    return request, context, scenarios


def budget() -> tuple[dict, dict, list[tuple[str, str, dict, list]]]:
    request = {
        "variables": {
            "people": {"distribution": "constant", "value": 12},
            "price": {"distribution": "triangular", "low": 25, "mode": 35, "high": 50},
            "travel": {
                "distribution": "discrete",
                "values": [0, 80, 150],
                "probabilities": [0.2, 0.6, 0.2],
            },
        },
        "expression": "people * price + travel",
    }
    context = {
        "schema_version": 1,
        "illustrative": True,
        "question": "Will the team outing stay within a $600 budget?",
        "outcome": {"label": "Total outing cost", "unit": "USD", "subject": "simulated outings"},
        "target": {"id": "budget", "operator": "le", "value": 600},
        "model": {
            "explanation": (
                "Multiply the number of people by the uncertain cost per person, "
                "then add shared travel costs."
            ),
            "inputs": {
                "people": assumption(
                    "People attending", "people", "Attendance is fixed within each saved scenario."
                ),
                "price": assumption(
                    "Cost per person",
                    "USD per person",
                    "Assume a cost between $25 and $50 per person, most likely $35.",
                ),
                "travel": assumption(
                    "Shared travel",
                    "USD",
                    "Shared travel costs $0, $80, or $150 "
                    "with assumed chances of 20%, 60%, and 20%.",
                ),
            },
            "limitations": [
                "Synthetic teaching example. These figures are not quotes "
                "from a venue or transport provider.",
                "Cost per person and travel costs are sampled independently. "
                "Group discounts, taxes, and extra purchases are omitted.",
            ],
        },
    }
    smaller = {
        **request,
        "variables": {**request["variables"], "people": {"distribution": "constant", "value": 10}},
    }
    scenarios = [
        ("baseline", "12 people", request, []),
        (
            "smaller_group",
            "10 people",
            smaller,
            [
                {
                    "path": "variables.people.value",
                    "description": (
                        "Reduce attendance from 12 to 10 people. "
                        "Per-person and shared-travel cost distributions stay unchanged."
                    ),
                }
            ],
        ),
    ]
    return request, context, scenarios


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--example", choices=("project", "budget"), default="project")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--resources", choices=("inline", "shared", "cdn"), default="inline")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    _, context, scenarios = (project if args.example == "project" else budget)()
    destination = args.out_dir.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    artifact_name = "project-deadline.html" if args.example == "project" else "outing-budget.html"
    outputs = ["context.json", "descriptor.json", artifact_name]
    outputs += [
        f"{identifier}.{kind}.json"
        for identifier, *_ in scenarios
        for kind in ("request", "result")
    ]
    if not args.overwrite and any((destination / name).exists() for name in outputs):
        parser.error("example outputs already exist; use --overwrite or a new --out-dir")
    context["scenarios"] = []
    for identifier, label, request, changes in scenarios:
        request = {
            **request,
            "samples": 10000,
            "seed": 7,
            "return_draws": True,
            "thresholds": {
                context["target"]["id"]: {
                    "operator": context["target"]["operator"],
                    "value": context["target"]["value"],
                }
            },
        }
        (destination / f"{identifier}.request.json").write_text(
            json.dumps(request, indent=2) + "\n"
        )
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pearl_of_wisdom.cli",
                "analyze",
                "--engine",
                "monte-carlo",
                "--data",
                json.dumps(request),
            ],
            check=True,
            capture_output=True,
        ).stdout
        source_name = f"{identifier}.result.json"
        (destination / source_name).write_bytes(result)
        context["scenarios"].append(
            {
                "id": identifier,
                "label": label,
                "source": source_name,
                "sha256": hashlib.sha256(result).hexdigest(),
                "changes": changes,
            }
        )
    context_path = destination / "context.json"
    context_path.write_text(json.dumps(context, indent=2) + "\n")
    command = [
        sys.executable,
        "-m",
        "pearl_of_wisdom_viz.cli",
        "explain",
        "--context",
        str(context_path),
        "--out",
        str(destination / artifact_name),
        "--resources",
        args.resources,
    ]
    if args.overwrite:
        command.append("--overwrite")
    descriptor = subprocess.run(command, check=True, capture_output=True).stdout
    (destination / "descriptor.json").write_bytes(descriptor)
    print(descriptor.decode(), end="")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as error:
        sys.stderr.write(error.stderr.decode() if error.stderr else str(error))
        raise SystemExit(error.returncode) from error
