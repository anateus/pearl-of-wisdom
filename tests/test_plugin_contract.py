"""Contract checks for the portable plugin package."""

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
PLUGIN = ROOT / "plugins" / "pearl-of-wisdom"


def test_both_manifests_point_to_one_shared_skill_tree() -> None:
    codex = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text())
    claude = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
    assert codex["name"] == claude["name"] == "pearl-of-wisdom"
    assert codex["skills"] == claude["skills"] == "./skills/"
    assert (PLUGIN / "skills" / "reasoning-under-uncertainty" / "SKILL.md").is_file()
    assert (PLUGIN / "skills" / "pearl-of-wisdom" / "SKILL.md").is_file()


def test_hook_is_declared_for_user_prompt_submit_only() -> None:
    codex = json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text())
    claude = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text())
    assert "hooks" not in codex
    assert "hooks" not in claude
    hook_path = PLUGIN / "hooks" / "hooks.json"
    config = json.loads(hook_path.read_text())
    assert list(config["hooks"]) == ["UserPromptSubmit"]
    assert config["hooks"]["UserPromptSubmit"][0]["hooks"][0]["type"] == "command"
    assert "dispatcher.py" in config["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]


def test_routing_fixture_has_positive_negative_and_ambiguous_cases() -> None:
    fixture = json.loads((PLUGIN / "evals" / "routing-cases.json").read_text())
    labels = {case["label"] for case in fixture["cases"]}
    assert {"positive", "negative", "ambiguous"} <= labels
    assert all(case["prompt"] for case in fixture["cases"])


def test_final_answer_fixture_preserves_latency_bound_assumptions() -> None:
    fixture = json.loads((PLUGIN / "evals" / "final-answer-cases.json").read_text())
    case = fixture["cases"][0]

    assert case["id"] == "sequential-latency-bound"
    assert case["recorded_result"]["bounds_ms"] == [0, 80]
    assert set(case["recorded_assumptions"]) == {
        "additive effects",
        "nonnegative effects",
        "no time drift",
    }
    assert (
        "the sequential toggle does not eliminate time drift"
        in case["required_final_answer_claims"]
    )


def test_markdown_links_stay_inside_the_portable_plugin() -> None:
    for markdown in PLUGIN.rglob("*.md"):
        for target in _relative_markdown_targets(markdown.read_text()):
            assert (markdown.parent / target).resolve().is_file(), (
                f"Broken local link in {markdown.relative_to(PLUGIN)}: {target}"
            )


def _relative_markdown_targets(markdown: str) -> list[str]:
    targets: list[str] = []
    for fragment in markdown.split("](")[1:]:
        target = fragment.split(")", 1)[0].split("#", 1)[0]
        if target and "://" not in target and not target.startswith("#"):
            targets.append(target)
    return targets
