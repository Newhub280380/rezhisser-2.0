"""Built-in director assistant: talks to OpenRouter, never stores keys in code.

The API key is read from the same place as the Cloud LLM settings
(LLM_API_KEY / LLM_BASE_URL / LLM_MODEL in .env). Values never leave
public_status() and are not written into source files.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from services import cloud_generation

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
PRIMARY_MODEL = "qwen/qwen3-235b-a22b-2507"  # answers storyboards as plain JSON; GLM is the spare
FALLBACK_MODEL = "z-ai/glm-5.3-flash"
LEGACY_DEFAULT_MODELS = {"", "MiniMax-M2", "minimax-m2"}

SYSTEM_PROMPT = """Ты встроенный помощник Режиссёра 2.0. Человек выбирает задачу
и может прислать фото или просто описать, что нужно. Ты сам нажимаешь кнопки
внутри приложения через инструменты. Не проси человека вручную ставить слэши,
команды или длинные промпты — подбери их из библиотеки знаний и выставь сам.

Правила:
- Отвечай коротко и по-русски, простыми словами.
- Сначала открой нужный экран, потом при необходимости попроси загрузить фото
  инструментом upload_photo, выставь параметры, запусти генерацию, следи за
  очередью и в конце отдай готовый файл.
- Если ключ OpenRouter не задан, скажи открыть Настройки → Integrations → Cloud
  и вписать ключ в поле облачной LLM. Сам ключ никогда не проси прислать в чат.
- Если генерация не запустилась, верни текст ошибки из инструмента и предложи,
  что проверить (модель, фото, ключ облака).
- Не выдумывай, что ролик уже готов: сначала посмотри очередь и библиотеку.
- Если человек просит ролик из нескольких фото («вот 5 фото, сделай мини-ролик
  на 2–3 минуты»), вызови start_autopilot с recipe=photo_to_film: он сам уберёт
  фон, улучшит до 4К, напишет раскадровку, сгенерирует сцены и склеит mp4.
  «2–3 минуты» = total_seconds 150, по умолчанию 60. Ссылка на чужой ролик и
  просьба повторить его со своим героем — recipe=viral_remake с source_url.
- Если сообщение начинается со slash-команды (/hero и т. п.), возьми её шаблон
  из библиотеки знаний, подставь поля из слов человека и действуй.
"""


class AssistantError(Exception):
    def __init__(self, detail: str, status: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status = status


def _clean_base_url(url: str) -> str:
    text = (url or "").strip().rstrip("/")
    if not text:
        return DEFAULT_BASE_URL
    return text


def _primary_model() -> str:
    configured = (cloud_generation.env("LLM_MODEL") or "").strip()
    if configured and configured not in LEGACY_DEFAULT_MODELS:
        return configured
    return PRIMARY_MODEL


def _fallback_model() -> str:
    return (cloud_generation.env("LLM_FALLBACK_MODEL") or "").strip() or FALLBACK_MODEL


def _model_chain() -> list[str]:
    primary = _primary_model()
    chain = [primary]
    fallback = _fallback_model()
    if fallback not in chain:
        chain.append(fallback)
    return chain


def public_status() -> dict[str, Any]:
    """Safe status for the UI: never includes the key."""
    key_set = bool((cloud_generation.env("LLM_API_KEY") or "").strip())
    base = _clean_base_url(cloud_generation.env("LLM_BASE_URL") or "")
    return {
        "ready": key_set,
        "provider": "openrouter" if "openrouter.ai" in base else "custom",
        "base_url": base,
        "model": _primary_model(),
        "fallback_model": _fallback_model(),
        "key_set": key_set,
    }


def _chat_url(base: str) -> str:
    if base.endswith("/chat/completions"):
        return base
    return f"{base}/chat/completions"


def _post_json(url: str, payload: dict[str, Any], api_key: str, timeout: int = 90) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://local.rezhisser",
            "X-Title": "Rezhisser 2.0 Assistant",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:500]
        raise AssistantError(
            f"Модель {payload.get('model', '')} не ответила ({error.code}).",
            status=error.code if error.code in {401, 402, 404, 429, 503} else 502,
        ) from error
    except urllib.error.URLError as error:
        raise AssistantError("Нет связи с облачной моделью. Проверьте интернет.", status=502) from error


def complete(messages: list[dict[str, Any]]) -> str:
    """Plain completion (no tools, no assistant persona) for pipeline steps such as storyboards."""
    message = chat({"messages": messages}, raw=True)["message"]
    return str(message.get("content") or "")


def _last_user_text(messages: list) -> str:
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == "user" and isinstance(message.get("content"), str):
            return message["content"]
    return ""


def chat(body: dict[str, Any], *, raw: bool = False) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise AssistantError("Ожидался JSON-объект.")

    api_key = (cloud_generation.env("LLM_API_KEY") or "").strip()
    if not api_key:
        raise AssistantError(
            "Ключ OpenRouter не задан. Откройте Настройки → Integrations → Cloud и впишите его в поле облачной LLM.",
            status=400,
        )

    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        raise AssistantError("Нужен список сообщений.")

    tools = body.get("tools")
    payload_messages = [] if raw else [{"role": "system", "content": SYSTEM_PROMPT}]
    context = body.get("context")
    if not raw:
        from services import assistant_knowledge
        category = context.get("category") if isinstance(context, dict) else None
        category = category if isinstance(category, str) and category else None
        extra = [f"Сейчас выбрана категория: {category}."] if category else []
        # Knowledge comes from docs/assistant-knowledge (recipes, slash commands, rules).
        extra.append("Библиотека знаний:\n" + assistant_knowledge.prompt_context(category, _last_user_text(messages)))
        payload_messages[0]["content"] += "\n\n" + "\n".join(extra)
    payload_messages.extend(messages)

    request_body: dict[str, Any] = {
        "messages": payload_messages,
        "temperature": 0.4,
        "max_tokens": 4096,  # storyboards for 2–3 minute films run long
    }
    if isinstance(tools, list) and tools:
        request_body["tools"] = tools
        request_body["tool_choice"] = body.get("tool_choice") or "auto"

    base = _clean_base_url(cloud_generation.env("LLM_BASE_URL") or "")
    url = _chat_url(base)
    last_error: AssistantError | None = None
    used_fallback = False
    chain = _model_chain()

    for index, model in enumerate(chain):
        payload = dict(request_body)
        payload["model"] = model
        try:
            data = _post_json(url, payload, api_key)
        except AssistantError as error:
            last_error = error
            if error.status in {401}:
                raise AssistantError(
                    "Ключ OpenRouter не принят. Проверьте его в Настройках → Integrations → Cloud.",
                    status=401,
                ) from error
            if index < len(chain) - 1 and error.status in {402, 404, 429, 503, 502}:
                used_fallback = True
                continue
            raise

        choices = data.get("choices") if isinstance(data, dict) else None
        if not isinstance(choices, list) or not choices:
            last_error = AssistantError("Модель вернула пустой ответ.", status=502)
            if index < len(chain) - 1:
                used_fallback = True
                continue
            raise last_error

        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(message, dict):
            last_error = AssistantError("Модель вернула странный ответ.", status=502)
            if index < len(chain) - 1:
                used_fallback = True
                continue
            raise last_error

        return {
            "message": message,
            "model_used": model,
            "used_fallback": used_fallback or index > 0,
        }

    if last_error:
        raise last_error
    raise AssistantError("Модель не ответила.", status=502)
