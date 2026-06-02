from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Protocol
from urllib import error, request

DEFAULT_LOCAL_AI_TIMEOUT_SECONDS = 30.0
LIVE_LOCAL_AI_TIMEOUT_SECONDS = 2.0


@dataclass(frozen=True)
class LocalAIResult:
    ok: bool
    text: str
    error: str = ""


class LocalAIProvider(Protocol):
    def generate(self, prompt: str, model: str, timeout_seconds: float = DEFAULT_LOCAL_AI_TIMEOUT_SECONDS) -> LocalAIResult:
        ...


class DisabledLocalAIProvider:
    def generate(self, prompt: str, model: str, timeout_seconds: float = DEFAULT_LOCAL_AI_TIMEOUT_SECONDS) -> LocalAIResult:
        return LocalAIResult(ok=False, text="", error="local AI is disabled")


class OllamaProvider:
    def __init__(self, base_url: str = "http://127.0.0.1:11434") -> None:
        self.base_url = base_url.rstrip("/")

    def generate(self, prompt: str, model: str, timeout_seconds: float = DEFAULT_LOCAL_AI_TIMEOUT_SECONDS) -> LocalAIResult:
        if not model:
            return LocalAIResult(ok=False, text="", error="no Ollama model configured")
        payload = json.dumps(
            {
                "model": model,
                "prompt": _disable_thinking_prompt(prompt),
                "stream": False,
                "think": False,
                "options": {"num_predict": 8, "temperature": 0.1},
            }
        ).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (OSError, error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            return LocalAIResult(ok=False, text="", error=str(exc))
        text = str(body.get("response", "")).strip()
        return LocalAIResult(ok=bool(text), text=text, error="" if text else "empty response")


class LocalAIService:
    def __init__(self, provider_name: str, model: str, enabled: bool) -> None:
        self.provider_name = provider_name
        self.model = model
        self.enabled = enabled
        self.provider = self._provider_for(provider_name) if enabled else DisabledLocalAIProvider()

    def status(self) -> str:
        if not self.enabled:
            return "disabled"
        if self.provider_name == "ollama":
            return f"enabled: ollama model={self.model or '(not configured)'}"
        return f"unsupported provider: {self.provider_name}"

    def test(
        self,
        prompt: str = "Suggest the next word after: I will",
        timeout_seconds: float = DEFAULT_LOCAL_AI_TIMEOUT_SECONDS,
    ) -> LocalAIResult:
        if not self.enabled:
            return LocalAIResult(ok=False, text="", error="local AI is disabled")
        if self.provider_name != "ollama":
            return LocalAIResult(ok=False, text="", error=f"unsupported provider: {self.provider_name}")
        return self.provider.generate(prompt, self.model, timeout_seconds=timeout_seconds)

    def suggest_next(self, context: str, timeout_seconds: float = LIVE_LOCAL_AI_TIMEOUT_SECONDS) -> LocalAIResult:
        prompt = (
            "/no_think\n"
            "You are a desktop keyboard next-word predictor. "
            "Return only the next word or a short phrase. Do not explain. Do not include reasoning.\n\n"
            f"Context: {context[-240:]}"
        )
        return self.test(prompt, timeout_seconds=timeout_seconds)

    @staticmethod
    def _provider_for(provider_name: str) -> LocalAIProvider:
        if provider_name == "ollama":
            return OllamaProvider()
        return DisabledLocalAIProvider()


def _disable_thinking_prompt(prompt: str) -> str:
    stripped = prompt.lstrip()
    if stripped.startswith("/no_think"):
        return prompt
    return "/no_think\n" + prompt
