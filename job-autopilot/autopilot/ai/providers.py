"""Pluggable AI providers. Default is ``none`` (AI NOT CONFIGURED).

The AI is used for interpretation and narrative drafting only. Every model
output is passed through the grounding validator before it can be used.
API keys are stored in the credential vault under platform key ``ai:<provider>``.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass

import httpx
from sqlalchemy.orm import Session

from ..security.credentials import use_credential
from ..settings_store import AISettings, load, save

TIMEOUT = httpx.Timeout(120.0, connect=15.0)


class AIError(Exception):
    pass


class AINotConfigured(AIError):
    pass


class AIPrivacyBlocked(AIError):
    """Raised when candidate data would be sent without explicit permission."""


@dataclass
class Provider:
    name: str
    model: str
    base_url: str
    api_key: str | None

    def complete(self, system: str, user: str, max_tokens: int = 2000) -> str:
        raise NotImplementedError

    def health(self) -> tuple[bool, str]:
        raise NotImplementedError


class AnthropicProvider(Provider):
    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self.api_key or "", "anthropic-version": "2023-06-01", "content-type": "application/json"}

    def complete(self, system: str, user: str, max_tokens: int = 2000) -> str:
        r = httpx.post(
            f"{self.base_url or 'https://api.anthropic.com'}/v1/messages",
            headers=self._headers(),
            json={"model": self.model, "max_tokens": max_tokens, "system": system,
                  "messages": [{"role": "user", "content": user}]},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            raise AIError(f"Anthropic API HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        if data.get("stop_reason") == "refusal":
            raise AIError("Model declined the request (stop_reason=refusal)")
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")

    def health(self) -> tuple[bool, str]:
        r = httpx.get(f"{self.base_url or 'https://api.anthropic.com'}/v1/models", headers=self._headers(), timeout=30)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"
        ids = [m.get("id") for m in r.json().get("data", [])]
        return (self.model in ids or not ids), f"CONNECTED ({len(ids)} models visible; configured {self.model})"


class OpenAIProvider(Provider):
    def _headers(self) -> dict[str, str]:
        return {"authorization": f"Bearer {self.api_key or ''}", "content-type": "application/json"}

    def complete(self, system: str, user: str, max_tokens: int = 2000) -> str:
        r = httpx.post(
            f"{self.base_url or 'https://api.openai.com'}/v1/chat/completions",
            headers=self._headers(),
            json={"model": self.model, "max_completion_tokens": max_tokens,
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            raise AIError(f"OpenAI API HTTP {r.status_code}: {r.text[:300]}")
        return r.json()["choices"][0]["message"].get("content") or ""

    def health(self) -> tuple[bool, str]:
        r = httpx.get(f"{self.base_url or 'https://api.openai.com'}/v1/models", headers=self._headers(), timeout=30)
        return (r.status_code == 200, "CONNECTED" if r.status_code == 200 else f"HTTP {r.status_code}")


class OllamaProvider(Provider):
    def complete(self, system: str, user: str, max_tokens: int = 2000) -> str:
        r = httpx.post(
            f"{self.base_url or 'http://localhost:11434'}/api/chat",
            json={"model": self.model, "stream": False, "options": {"num_predict": max_tokens},
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]},
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            raise AIError(f"Ollama HTTP {r.status_code}: {r.text[:300]}")
        return r.json().get("message", {}).get("content", "")

    def health(self) -> tuple[bool, str]:
        r = httpx.get(f"{self.base_url or 'http://localhost:11434'}/api/tags", timeout=15)
        if r.status_code != 200:
            return False, f"HTTP {r.status_code}"
        names = [m.get("name") for m in r.json().get("models", [])]
        ok = any(n == self.model or n.split(":")[0] == self.model for n in names)
        return ok, "CONNECTED" if ok else f"Model {self.model} not pulled (available: {names[:5]})"


_CLASSES = {"anthropic": AnthropicProvider, "openai": OpenAIProvider, "ollama": OllamaProvider}


class ProviderHandle:
    """Resolves the configured provider; decrypts the API key only while calling."""

    def __init__(self, s: Session, user_id: int):
        self.s = s
        self.user_id = user_id
        self.settings = load(s, AISettings)

    @property
    def configured(self) -> bool:
        return self.settings.provider != "none" and bool(self.settings.model)

    def _call(self, fn):
        st = self.settings
        if not self.configured:
            raise AINotConfigured("AI provider NOT CONFIGURED")
        cls = _CLASSES[st.provider]
        if st.provider == "ollama":
            return fn(cls(st.provider, st.model, st.base_url, None))
        try:
            with use_credential(self.s, self.user_id, f"ai:{st.provider}") as (_, key):
                return fn(cls(st.provider, st.model, st.base_url, key))
        except LookupError as e:
            raise AINotConfigured(f"No API key stored for ai:{st.provider}") from e

    def complete(self, system: str, user: str, *, contains_candidate_data: bool, max_tokens: int = 2000) -> str:
        if contains_candidate_data and not self.settings.allow_candidate_data and self.settings.provider != "ollama":
            raise AIPrivacyBlocked(
                "Sending candidate data to a third-party AI provider is not permitted "
                "(enable 'allow_candidate_data' in AI settings to permit it)"
            )
        return self._call(lambda p: p.complete(system, user, max_tokens))

    def health_check(self, persist: bool = True) -> tuple[bool, str]:
        if not self.configured:
            return False, "NOT CONFIGURED"
        try:
            ok, msg = self._call(lambda p: p.health())
        except AIError as e:
            ok, msg = False, str(e)
        except httpx.HTTPError as e:
            ok, msg = False, f"UNREACHABLE: {type(e).__name__}"
        if persist:
            self.settings.last_check_ok = ok
            self.settings.last_check_message = msg
            self.settings.last_check_at = dt.datetime.now(dt.timezone.utc).isoformat()
            save(self.s, self.settings)
        return ok, msg


def extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise AIError("Model did not return JSON")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise AIError(f"Model returned invalid JSON: {e}") from e
