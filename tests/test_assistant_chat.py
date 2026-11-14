import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from unittest import mock

import pytest

from services import assistant_chat


def test_public_status_never_returns_key(monkeypatch):
    monkeypatch.setattr(
        assistant_chat.cloud_generation,
        "env",
        lambda name: {
            "LLM_API_KEY": "sk-secret-should-not-leak",
            "LLM_BASE_URL": "https://openrouter.ai/api/v1",
            "LLM_MODEL": "",
        }.get(name, ""),
    )
    status = assistant_chat.public_status()
    dumped = str(status)
    assert "sk-secret" not in dumped
    assert status["ready"] is True
    assert status["key_set"] is True
    assert status["model"] == assistant_chat.PRIMARY_MODEL
    assert status["fallback_model"] == assistant_chat.FALLBACK_MODEL


def test_chat_requires_key(monkeypatch):
    monkeypatch.setattr(assistant_chat.cloud_generation, "env", lambda name: "")
    with pytest.raises(assistant_chat.AssistantError) as raised:
        assistant_chat.chat({"messages": [{"role": "user", "content": "привет"}]})
    assert raised.value.status == 400
    assert "Ключ" in raised.value.detail


def test_chat_falls_back_when_primary_is_busy(monkeypatch):
    monkeypatch.setattr(
        assistant_chat.cloud_generation,
        "env",
        lambda name: {
            "LLM_API_KEY": "sk-test",
            "LLM_BASE_URL": "https://openrouter.ai/api/v1",
            "LLM_MODEL": "",
        }.get(name, ""),
    )
    calls = []

    def fake_post(url, payload, api_key, timeout=90):
        calls.append(payload["model"])
        assert api_key == "sk-test"
        assert "chat/completions" in url
        if payload["model"] == assistant_chat.PRIMARY_MODEL:
            raise assistant_chat.AssistantError("busy", status=429)
        return {"choices": [{"message": {"role": "assistant", "content": "готово"}}]}

    monkeypatch.setattr(assistant_chat, "_post_json", fake_post)
    result = assistant_chat.chat({"messages": [{"role": "user", "content": "сделай видео"}]})
    assert calls == [assistant_chat.PRIMARY_MODEL, assistant_chat.FALLBACK_MODEL]
    assert result["used_fallback"] is True
    assert result["model_used"] == assistant_chat.FALLBACK_MODEL
    assert result["message"]["content"] == "готово"


def test_legacy_minimax_model_is_ignored(monkeypatch):
    monkeypatch.setattr(
        assistant_chat.cloud_generation,
        "env",
        lambda name: "MiniMax-M2" if name == "LLM_MODEL" else "",
    )
    assert assistant_chat._primary_model() == assistant_chat.PRIMARY_MODEL
