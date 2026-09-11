#!/usr/bin/env python3
"""Emit small, fail-open UserPromptSubmit hints for either supported host."""

from __future__ import annotations

import json
import sys

MAX_INPUT_BYTES = 64 * 1024
MAX_CONTEXT_CHARS = 420


def _prompt(event: object) -> str:
    if not isinstance(event, dict):
        return ""
    for key in ("prompt", "user_prompt", "message", "input"):
        value = event.get(key)
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            nested = value.get("content") or value.get("text")
            if isinstance(nested, str):
                return nested
    return ""


def _suggestions(prompt: str) -> list[str]:
    text = prompt.casefold()
    suggestions: list[str] = []
    uncertainty_terms = (
        "uncertain",
        "probability",
        "probabilistic",
        "likely",
        "likelihood",
        "confidence",
        "risk",
        "chance",
        "estimate",
    )
    investigation_terms = (
        "investigation",
        "hypothesis",
        "evidence",
        "diagnose",
        "root cause",
        "across turns",
        "resume",
        "durable",
    )
    if any(term in text for term in uncertainty_terms):
        suggestions.append(
            "Advisory: use $reasoning-under-uncertainty; choose the least complex method "
            "that can change the decision."
        )
    if any(term in text for term in investigation_terms):
        suggestions.append(
            "Advisory: use $pearl-of-wisdom for a durable record; treat Hindsight as "
            "context, never probabilistic evidence."
        )
    return suggestions[:2]


def main() -> int:
    """Read one hook event, emit bounded JSON, and never make the hook required."""
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            return 0
        event = json.loads(raw or b"{}")
        suggestions = _suggestions(_prompt(event))
        if not suggestions:
            return 0
        context = " ".join(suggestions)[:MAX_CONTEXT_CHARS]
        # Claude and Codex accept the same UserPromptSubmit context shape.
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": context,
                }
            },
            sys.stdout,
            separators=(",", ":"),
        )
        sys.stdout.write("\n")
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
