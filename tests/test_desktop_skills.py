"""Structural contracts for shared Desktop skills, not model-routing evaluations."""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SKILLS = ROOT / "plugins" / "pearl-of-wisdom" / "skills"
NAMES = ("pearl-of-wisdom", "reasoning-under-uncertainty")
TOOLS = {
    "pearl_status",
    "pearl_example",
    "pearl_analyze",
    "pearl_create_investigation",
    "pearl_list_investigations",
    "pearl_show_investigation",
    "pearl_record",
    "pearl_promote_investigation",
}


def test_marketplace_points_to_shared_plugin_without_release_metadata() -> None:
    manifest = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    assert manifest["name"] == "pearl-of-wisdom"
    assert manifest["owner"]["name"]
    assert manifest["metadata"]["description"]
    assert len(manifest["plugins"]) == 1
    plugin = manifest["plugins"][0]
    assert plugin["name"] == "pearl-of-wisdom"
    assert plugin["source"] == "./plugins/pearl-of-wisdom"
    assert (ROOT / plugin["source"] / ".claude-plugin" / "plugin.json").is_file()
    assert plugin["description"] and plugin["author"]["name"]
    assert "version" not in plugin


@pytest.mark.parametrize("name", NAMES)
def test_loaded_skills_include_compatibility_and_chat_host_boundaries(name: str) -> None:
    text = (SKILLS / name / "SKILL.md").read_text()
    assert text.startswith(f"---\nname: {name}\ndescription:")
    assert "pearl_status()" in text
    for key in ("version", "required", "compatible", "engines", "database", "transport"):
        assert f"`{key}`" in text
    assert ">=0.4.0,<0.5.0" in text
    assert "pearl_example(engine)" in text
    assert "pearl_analyze(engine, data)" in text
    assert text.index("pearl_status()") < text.index("pearl_analyze(engine, data)")
    assert "Desktop Extensions" in text and "`.mcpb`" in text
    assert "Do not offer the Code CLI as an ordinary Chat solution" in text
    assert "In Chat, do not run shell commands, invoke `check_cli.py`," in text
    assert "Claude Code's Skill tool" in text
    assert "loaded" in text and "content" in text
    assert "Only in a shell-capable Code or Codex host without Pearl MCP tools" in text
    assert "(../../scripts/check_cli.py)" in text
    assert "`executable`" in text and "`install_command`" in text
    assert "Hindsight" in text and "optional" in text
    assert "no model" in text


def test_mcp_workflow_documents_only_exact_tools_and_no_database_input() -> None:
    text = (SKILLS / "pearl-of-wisdom" / "references" / "mcp-workflow.md").read_text()
    assert set(re.findall(r"\b(pearl_[a-z_]+)\(", text)) == TOOLS
    assert "pearl_create_investigation(status='ephemeral')" in text
    assert "pearl_record(investigation_id, kind, data, engine=None)" in text
    assert "Supply `engine` only for `analysis`, where it is required" in text
    for kind in ("context", "assumption", "evidence", "analysis"):
        assert f"`{kind}`" in text
    assert "No tool accepts a model-selected database path" in text
    assert "Neither an example nor a stateless analysis writes an investigation" in text
    assert "confirm durable status and preserved entries" in text
    assert "Do not blindly retry create, record, or promote" in text
    assert "malformed result" in text


def test_durable_loaded_skill_contains_readback_without_reference_loading() -> None:
    text = (SKILLS / "pearl-of-wisdom" / "SKILL.md").read_text()
    assert set(re.findall(r"\b(pearl_[a-z_]+)\(", text)) == TOOLS
    assert "Verify writes with `pearl_show_investigation(investigation_id)`" in text
    assert "Show again and confirm durable status" in text
    assert "Analysis is stateless: explicitly record" in text
    assert "extension configures that path, not tool arguments" in text


@pytest.mark.parametrize("engine", ("causal", "decision-analysis", "system-simulation"))
def test_cli_method_examples_have_explicit_mcp_mapping(engine: str) -> None:
    text = (SKILLS / "reasoning-under-uncertainty" / "references" / f"{engine}.md").read_text()
    assert f"pearl_example(engine='{engine}')" in text
    assert f"pearl_analyze(engine='{engine}', data=REQUEST)" in text
    assert "Do not run the CLI examples in Chat" in text
    assert "Only in shell-capable hosts without MCP tools" in text


def test_top_level_routing_maps_cli_examples_to_json_object_tools() -> None:
    for path in ("SKILL.md", "references/routing.md"):
        text = (SKILLS / "reasoning-under-uncertainty" / path).read_text()
        assert "pearl_example(engine=ENGINE)" in text
        assert "pearl_analyze(engine=ENGINE, data=REQUEST)" in text
        assert "JSON object" in text


def test_owned_markdown_has_no_em_or_en_dashes_and_valid_relative_links() -> None:
    for markdown in SKILLS.rglob("*.md"):
        text = markdown.read_text()
        assert "\u2014" not in text and "\u2013" not in text, markdown
        for target in re.findall(r"\]\(([^)]+)\)", text):
            if "://" not in target and not target.startswith("#"):
                assert (markdown.parent / target.split("#", 1)[0]).resolve().is_file(), markdown
