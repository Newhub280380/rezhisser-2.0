"""Assistant knowledge base: docs/assistant-knowledge (recipes, slash commands, rules).

The folder is the single source: categories come from recipes.json, chat slash
commands from slash-commands.json, prompting rules from rules.md. Files are small
and read on each call, so edits to the folder apply without a restart.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

KNOWLEDGE_DIR = Path(__file__).resolve().parents[2] / "docs" / "assistant-knowledge"


def _read_json(name: str) -> dict:
    return json.loads((KNOWLEDGE_DIR / name).read_text(encoding="utf-8"))


def recipes() -> dict:
    return _read_json("recipes.json")


def recipe(recipe_id: str) -> dict:
    for item in recipes()["recipes"]:
        if item["id"] == recipe_id:
            return item
    raise KeyError(recipe_id)


def commands() -> list[dict]:
    return _read_json("slash-commands.json")["commands"]


def rules() -> str:
    return (KNOWLEDGE_DIR / "rules.md").read_text(encoding="utf-8")


def summary() -> dict[str, Any]:
    """What the chat UI shows: category chips, slash-command suggestions."""
    return {
        "categories": [
            {
                "id": r["id"],
                "title": r["title"],
                "short": r.get("short", ""),
                "steps": [s.get("tool") or s.get("what") or str(s) if isinstance(s, dict) else str(s)
                          for s in r.get("steps", [])],
                "progress_labels": r.get("progress_labels", []),
                "prompt_template": r.get("prompt_template_wan") or r.get("prompt_template") or "",
                "autopilot": r["id"] in AUTOPILOT_RECIPES,
            }
            for r in recipes()["recipes"]
        ],
        "commands": [
            {k: c.get(k) for k in ("command", "title", "result", "fields", "templates", "substitute")}
            for c in commands()
        ],
    }


AUTOPILOT_RECIPES = ("photo_to_film", "viral_remake")


def find_command(text: str) -> dict | None:
    match = re.match(r"\s*(/[\w-]+)", text or "")
    if not match:
        return None
    name = match.group(1).lower()
    return next((c for c in commands() if c["command"].lower() == name), None)


def prompt_context(category: str | None = None, user_text: str = "") -> str:
    """Knowledge block for the assistant's system prompt."""
    data = recipes()
    parts = [
        "Рецепты (категории): " + "; ".join(f"{r['id']} — {r['title']}: {r.get('short', '')}" for r in data["recipes"]),
        f"Видеодвижок по умолчанию: {data.get('default_engine')}, запасной: {data.get('fallback_engine')}.",
        "Автопилот (инструмент start_autopilot) умеет рецепты: " + ", ".join(AUTOPILOT_RECIPES) + ".",
        "Slash-команды (шаблоны промптов): " + ", ".join(f"{c['command']} ({c['title']})" for c in commands()),
        "Правила промптинга:\n" + rules(),
    ]
    if category:
        try:
            parts.append("Выбранный рецепт:\n" + json.dumps(recipe(category), ensure_ascii=False))
        except KeyError:
            pass
    command = find_command(user_text)
    if command:
        parts.append("Человек вызвал команду " + command["command"] + ":\n" + json.dumps(command, ensure_ascii=False))
    return "\n\n".join(parts)
