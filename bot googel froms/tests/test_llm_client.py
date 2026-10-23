import json

import httpx
import pytest

from engine.llm_client import OllamaClient, OllamaError


def test_check_status_requires_exact_model() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json={"models": [{"name": "qwen2.5-coder:1.5b"}]}
        )
    )
    client = OllamaClient(transport=transport)
    assert client.check_status() == (True, "Connected; model 'qwen2.5-coder:1.5b' is available.")


def test_chat_json_parses_model_content() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, json={"message": {"content": json.dumps({"answer": "test"})}}
        )
    )
    assert OllamaClient(transport=transport).chat_json("prompt") == {"answer": "test"}


def test_chat_json_rejects_invalid_json() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"message": {"content": "not json"}})
    )
    with pytest.raises(OllamaError, match="Invalid or unsuccessful"):
        OllamaClient(transport=transport).chat_json("prompt")
