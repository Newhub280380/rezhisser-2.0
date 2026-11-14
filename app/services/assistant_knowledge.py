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


AUTOPILOT_RECIPES = ("photo_to_film", "viral_remake", "one_prompt_film")


def find_command(text: str) -> dict | None:
    match = re.match(r"\s*(/[\w-]+)", text or "")
    if not match:
        return None
    name = match.group(1).lower()
    return next((c for c in commands() if c["command"].lower() == name), None)


BEAUTYART_RULES = "products/rules/beautyart-card-rules.md"
GRAPH_RULE = (
    "Память знаний — граф: сначала search_knowledge(запрос) (1–5 узлов), потом read_knowledge(path) только нужных "
    "файлов; картинки-референсы — open_ref_image(path). Всё сразу не читать. Правила промптинга — rules.md.\n"
    "ОБЯЗАТЕЛЬНО: если задача про карточку, пост или ролик с товаром Beautyart (ZISHÉL Glam, ZISHÉL Rose Lidocaine, "
    f"MELAGENTA H.A Body, Sagitta) — прочитай {BEAUTYART_RULES} и файл продукта из products/ours/, "
    "бери только реальные фото из products/refs/ours/, упаковку не генерируй."
)


def prompt_context(category: str | None = None, user_text: str = "") -> str:
    """Knowledge block for the assistant's system prompt: a short catalogue, details are read on demand."""
    data = recipes()
    parts = [
        "Рецепты (категории): " + "; ".join(f"{r['id']} — {r['title']}: {r.get('short', '')}" for r in data["recipes"]),
        f"Видеодвижок по умолчанию: {data.get('default_engine')}, запасной: {data.get('fallback_engine')}.",
        "Автопилот (инструмент start_autopilot) умеет рецепты: " + ", ".join(AUTOPILOT_RECIPES) + ".",
        "Slash-команды (шаблоны промптов): " + ", ".join(f"{c['command']} ({c['title']})" for c in commands()),
        GRAPH_RULE,
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


# ---------------------------------------------------------------- graph memory (search + read on demand)

PRODUCTS = "products"
TEXT_SUFFIXES = {".md", ".json"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
MAX_READ_CHARS = 40_000
STOPWORDS = {"как", "для", "что", "это", "про", "мне", "нам", "или", "the", "and", "for", "with", "сделай", "нужно",
             "нужна", "нужен", "покажи", "дай"}
# Query word prefix -> extra terms (Russian <-> brand/latin spellings used in the files).
SYNONYMS = {
    "ботокс": ("botox", "ботулотоксин"), "botox": ("ботокс", "ботулотоксин"), "ботулин": ("ботулотоксин",),
    "филлер": ("filler", "гиалурон"), "гиалурон": ("ha-fillers", "филлер"), "нит": ("pdo", "thread"),
    "биоревит": ("biorevital", "скинбустер"), "скинбуст": ("biorevital",),
    "карточ": ("card", "карточк"), "card": ("карточк",), "пост": ("instagram", "card"), "сторис": ("instagram",),
    "ролик": ("video", "ролик"), "видео": ("video",), "упаковк": ("packaging", "упаковк"),
    "glam": ("zishel-glam", "glam"), "глэм": ("zishel-glam", "glam"), "глам": ("zishel-glam", "glam"),
    "зишел": ("zishel",), "rose": ("rose-lidocaine",), "роуз": ("rose-lidocaine",), "лидока": ("lidocaine",),
    "мелагент": ("melagenta",), "melagenta": ("melagenta",), "сагитт": ("sagitta",), "sagitta": ("sagitta",),
}
# Beautyart products: words that mean "this product" -> its node.
OUR_PRODUCTS = {
    "products/ours/zishel-glam.md": ("glam", "глэм", "глам"),
    "products/ours/zishel-rose-lidocaine.md": ("rose", "роуз", "lidocaine", "лидокаин"),
    "products/ours/melagenta-ha-body.md": ("melagenta", "мелагента", "h.a body"),
    "products/ours/sagitta-pdo.md": ("sagitta", "сагитта", "сагиту"),
}


def _first_heading(text: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", text, re.M)
    return match.group(1).strip() if match else fallback


def _index_descriptions() -> dict[str, tuple[str, str]]:
    """INDEX.md lines '- [title](path) — description' under '## section' -> path: (description, section)."""
    result, section = {}, ""
    for line in (KNOWLEDGE_DIR / PRODUCTS / "INDEX.md").read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
        match = re.match(r"\s*-\s*\[[^\]]*\]\(([^)]+)\)\s*[—-]\s*(.+)", line)
        if match:
            result[match.group(1)] = (match.group(2).strip(), section)
    return result


def nodes() -> list[dict]:
    """One node list for the whole knowledge folder: product graph, recipes, rules, slash commands, sources."""
    out = []
    graph = json.loads((KNOWLEDGE_DIR / PRODUCTS / "index.json").read_text(encoding="utf-8"))
    described = _index_descriptions()
    for node in graph["nodes"]:
        path = f"{PRODUCTS}/{node['path']}"
        description, section = described.get(node["path"], ("", ""))
        out.append({"path": path, "title": node["title"], "group": f"products/{node['group']}",
                    "description": description, "tags": section,
                    "links": [f"{PRODUCTS}/{link}" for link in node.get("links", [])],
                    "images": [f"{PRODUCTS}/{image}" for image in node.get("images", [])],
                    "body": _safe_text(KNOWLEDGE_DIR / path)})
    for r in recipes()["recipes"]:
        md = KNOWLEDGE_DIR / "recipes" / f"{r['id']}.md"
        out.append({"path": f"recipes/{r['id']}.md" if md.is_file() else f"recipes.json#{r['id']}",
                    "title": r["title"], "group": "recipes", "description": r.get("short", ""),
                    "tags": " ".join(r.get("trigger_examples", [])) + " " + r["id"], "links": [], "images": [],
                    "body": _safe_text(md) if md.is_file() else json.dumps(r, ensure_ascii=False)})
    for c in commands():
        out.append({"path": f"slash-commands.json#{c['command']}", "title": f"{c['command']} — {c['title']}",
                    "group": "slash-commands", "description": c.get("result") or "", "tags": c["command"],
                    "links": [], "images": [], "body": json.dumps(c, ensure_ascii=False)})
    for extra in ["rules.md", "README.md", *sorted(str(p.relative_to(KNOWLEDGE_DIR)).replace("\\", "/")
                                                  for p in (KNOWLEDGE_DIR / "sources").glob("*.md"))]:
        body = _safe_text(KNOWLEDGE_DIR / extra)
        if body:
            out.append({"path": extra, "title": _first_heading(body, extra), "group": extra.split("/")[0],
                        "description": "", "tags": "правила промптинга" if extra == "rules.md" else "",
                        "links": [], "images": [], "body": body})
    return out


def _safe_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _terms(query: str) -> list[str]:
    words = [w for w in re.findall(r"[\w.\-]+", (query or "").lower()) if len(w) >= 3 and w not in STOPWORDS]
    terms = []
    for word in words:
        stem = word[:-2] if len(word) > 6 else word  # crude Russian ending cut: «выглядит» -> «выгляд»
        terms.append(stem)
        for prefix, extra in SYNONYMS.items():
            if word.startswith(prefix):
                terms.extend(extra)
    return list(dict.fromkeys(terms))


def search(query: str, limit: int = 5) -> list[dict]:
    """Rank nodes by query terms (title > path/description/tags > body); never returns file bodies."""
    terms = _terms(query)
    scored = []
    for node in nodes():
        head = node["title"].lower()
        meta = " ".join((node["path"], node["description"], node["tags"], node["group"])).lower()
        body = node["body"].lower()
        score = sum(3 * (t in head) + 2 * (t in meta) + (t in body) for t in terms)
        if score:
            scored.append((score, node))
    scored.sort(key=lambda item: -item[0])
    found = [node for _, node in scored[:limit]]
    # Beautyart rule: any of our products in play -> the card/video rules come first, always.
    if any(n["path"].startswith("products/ours/") for n in found) or product_in_text(query):
        everything = {n["path"]: n for n in nodes()}
        ours = [n for n in found if n["path"].startswith("products/ours/")]
        ours += [everything[p] for p in product_in_text(query) if p not in [n["path"] for n in ours]]
        rest = [n for n in found if n not in ours and n["path"] != BEAUTYART_RULES]
        found = ([everything[BEAUTYART_RULES]] + ours + rest)[:max(limit, 1 + len(ours))]
    return [{k: n[k] for k in ("path", "title", "group", "description", "links", "images")} for n in found]


def product_in_text(text: str) -> list[str]:
    """Beautyart products named in free text (card/video requests, one-prompt phrases)."""
    low = (text or "").lower()
    return [path for path, words in OUR_PRODUCTS.items() if any(word in low for word in words)]


def _inside(relative: str, root: Path) -> Path:
    base = root.resolve()
    path = (base / relative.replace("\\", "/").lstrip("/")).resolve()
    if base != path and base not in path.parents:
        raise KeyError(relative)
    return path


def read(path: str) -> dict:
    """One knowledge file (or one slash command / recipe entry); paths stay inside docs/assistant-knowledge."""
    clean = (path or "").strip()
    if "#" in clean:
        file_part, key = clean.split("#", 1)
        if file_part == "slash-commands.json":
            command = next((c for c in commands() if c["command"] == key), None)
            if command:
                return {"path": clean, "text": json.dumps(command, ensure_ascii=False, indent=1)}
        if file_part == "recipes.json":
            return {"path": clean, "text": json.dumps(recipe(key), ensure_ascii=False, indent=1)}
        raise KeyError(path)
    for candidate in (clean, f"{PRODUCTS}/{clean}"):  # product links are written relative to products/
        try:
            file = _inside(candidate, KNOWLEDGE_DIR)
        except KeyError:
            continue
        if file.is_file() and file.suffix.lower() in TEXT_SUFFIXES:
            text = file.read_text(encoding="utf-8")
            return {"path": str(file.relative_to(KNOWLEDGE_DIR.resolve())).replace("\\", "/"),
                    "text": text[:MAX_READ_CHARS], "truncated": len(text) > MAX_READ_CHARS}
    raise KeyError(path)


def ref_image(path: str) -> Path:
    """A reference picture from products/refs (served to the chat, or used as a real product frame)."""
    clean = (path or "").strip().replace("\\", "/")
    for prefix in ("products/", ""):
        clean = clean[len(prefix):] if clean.startswith(prefix) else clean
    clean = clean if clean.startswith("refs/") else f"refs/{clean}"
    file = _inside(clean[len("refs/"):], KNOWLEDGE_DIR / PRODUCTS / "refs")  # never outside refs/
    if not (file.is_file() and file.suffix.lower() in IMAGE_SUFFIXES):
        raise KeyError(path)
    return file


def product_photo(product_path: str) -> Path | None:
    """Best real photo of our product: refs/ours only (cropped > cutout > anything else)."""
    node = next((n for n in nodes() if n["path"] == product_path), None)
    ours = [img for img in (node or {}).get("images", []) if "/refs/ours/" in img]
    for kind in ("_cropped", "_cutout", ""):
        for img in ours:
            if kind in Path(img).stem and "brand_mood" not in img and "_and_" not in img:
                return KNOWLEDGE_DIR / img
    return None
