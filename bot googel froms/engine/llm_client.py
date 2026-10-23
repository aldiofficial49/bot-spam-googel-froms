import json
import time
from typing import Any

import httpx


class OllamaError(RuntimeError):
    """A visible, actionable Ollama connection or response error."""


class OllamaClient:
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5-coder:1.5b",
        timeout: float = 60,
        max_retries: int = 2,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self._transport = transport

    def _get_client(self) -> httpx.Client:
        return httpx.Client(timeout=self.timeout, transport=self._transport)

    def check_status(self) -> tuple[bool, str]:
        try:
            with self._get_client() as client:
                response = client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return False, f"Ollama is unavailable at {self.base_url}: {exc}"

        if not isinstance(payload, dict) or not isinstance(payload.get("models"), list):
            return False, "Ollama returned an unexpected model-list response."
        models = payload["models"]
        if any(not isinstance(item, dict) for item in models):
            return False, "Ollama returned an invalid model-list entry."
        installed = {model.get("name") for model in models}
        if self.model not in installed:
            return False, f"Model '{self.model}' is not installed. Run: ollama pull {self.model}"
        return True, f"Connected; model '{self.model}' is available."

    def chat_json(
        self, prompt: str, *, temperature: float = 0.7, seed: int | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
            "options": {"temperature": temperature},
        }
        if seed is not None:
            payload["options"]["seed"] = seed

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                with self._get_client() as client:
                    response = client.post(f"{self.base_url}/api/chat", json=payload)
                    response.raise_for_status()
                    envelope = response.json()
                if not isinstance(envelope, dict) or not isinstance(envelope.get("message"), dict):
                    raise OllamaError("Ollama returned an unexpected chat response.")
                content = envelope["message"].get("content")
                if not isinstance(content, str) or not content.strip():
                    raise OllamaError("Ollama returned an empty chat response.")
                parsed = json.loads(content)
                if not isinstance(parsed, dict):
                    raise OllamaError("Ollama returned JSON, but it was not an object.")
                return parsed
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(min(0.25 * (2**attempt), 1.0))
            except (httpx.HTTPStatusError, ValueError, KeyError, TypeError) as exc:
                raise OllamaError(f"Invalid or unsuccessful Ollama response: {exc}") from exc

        raise OllamaError(f"Ollama request failed after bounded retries: {last_error}") from last_error
