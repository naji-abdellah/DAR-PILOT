"""LLM client for DarPilot with retry, fallback, and multiple providers (M4).

Implementations:
- ``FakeLLMClient``: offline, template-based, no API key. Used for tests and
  graceful degradation when all live providers fail.
- ``GeminiLLMClient``: calls the Gemini REST API (free tier).
- ``OpenRouterLLMClient``: calls OpenRouter (free models as backup).

The factory ``get_llm_client()`` returns a resilient client that retries with
exponential backoff on 429/503 and falls back through the provider chain.
"""

from __future__ import annotations

import os
import time
import random
from typing import List, Optional

import requests


class LLMClient:
    """Interface: generate an answer from a prompt."""

    def generate(self, prompt: str) -> str:
        raise NotImplementedError


# ── Fake client (offline, no API key) ──────────────────────────────────────

class FakeLLMClient(LLMClient):
    """Template-based answer generator.

    Expects a prompt that contains a ``Listings:`` section (one line per
    retrieved chunk, prefixed with ``- [id: N]``) and a ``Question:`` line.
    Composes an answer citing the relevant listing IDs, in the question's
    language, or refuses when no listings are provided.
    """

    def generate(self, prompt: str) -> str:
        listings = self._parse_listings(prompt)
        question = self._parse_question(prompt)
        french = self._looks_french(question)

        if not listings:
            return (
                "Je n'ai trouv aucune annonce correspondant votre recherche."
                if french
                else "I couldn't find any listings matching your search."
            )

        ids = ", ".join(str(l["id"]) for l in listings)
        titles = "; ".join(f"[id: {l['id']}] {l['title']}" for l in listings[:5])
        if french:
            return (
                "Voici les annonces qui correspondent le mieux : "
                f"{titles}. (Références d'annonces citées : [{ids}])"
            )
        return (
            "Here are the listings that best match your search: "
            f"{titles}. (Listing IDs cited: [{ids}])"
        )

    @staticmethod
    def _parse_listings(prompt: str) -> List[dict]:
        listings: List[dict] = []
        for line in prompt.splitlines():
            line = line.strip()
            if not line.startswith("- [id: "):
                continue
            try:
                head = line.split("]")[0].split("[id: ")[1]
                rest = line.split("]", 1)[1].strip()
                title = rest.split("(")[0].strip()
                listings.append({"id": int(head), "title": title})
            except (ValueError, IndexError):
                continue
        return listings

    @staticmethod
    def _parse_question(prompt: str) -> str:
        for line in prompt.splitlines():
            if line.startswith("Question:"):
                return line.split(":", 1)[1].strip()
        return ""

    @staticmethod
    def _looks_french(text: str) -> bool:
        french_markers = ("louer", "vente", "appartement", "villa", "studio",
                          "riad", "marrakech", "casablanca", "cher", "bonjour")
        lowered = text.lower()
        return any(m in lowered for m in french_markers)


# ── Base retry/fallback logic ──────────────────────────────────────────────

class BaseLiveLLMClient(LLMClient):
    """Base class for live LLM providers with retry/backoff."""

    RETRY_STATUS_CODES = {429, 503}
    MAX_RETRIES = 3
    BASE_DELAY = 1.0  # seconds
    MAX_DELAY = 30.0

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "",
        timeout: int = 30,
    ):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def _retry_with_backoff(self, func, *args, **kwargs):
        """Execute func with exponential backoff on retryable errors."""
        last_exception = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                return func(*args, **kwargs)
            except RuntimeError as exc:
                last_exception = exc
                # Check if it's a retryable error (429 or 503)
                if "429" in str(exc) or "503" in str(exc):
                    if attempt < self.MAX_RETRIES:
                        delay = min(
                            self.BASE_DELAY * (2 ** attempt) + random.uniform(0, 0.5),
                            self.MAX_DELAY,
                        )
                        time.sleep(delay)
                        continue
                raise
        raise last_exception


# ── Gemini client (real API) ───────────────────────────────────────────────

class GeminiLLMClient(BaseLiveLLMClient):
    """Calls the Gemini 1.5 Flash REST API (free tier).

    Uses ``x-goog-api-key`` header instead of query parameter to avoid
    leaking the API key in logs/URLs.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-1.5-flash",
        timeout: int = 30,
    ):
        super().__init__(api_key, model, timeout)
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}"
            f":generateContent"
        )

    def generate(self, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")

        def _call():
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key,
            }
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
            resp = requests.post(self.url, json=payload, headers=headers, timeout=self.timeout)
            if resp.status_code in self.RETRY_STATUS_CODES:
                raise RuntimeError(f"Gemini rate limited ({resp.status_code})")
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

        return self._retry_with_backoff(_call)


# ── OpenRouter client (backup) ─────────────────────────────────────────────

class OpenRouterLLMClient(BaseLiveLLMClient):
    """Calls OpenRouter API (free models as backup)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "meta-llama/llama-3.2-3b-instruct:free",
        timeout: int = 30,
    ):
        super().__init__(api_key, model, timeout)
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self.url = "https://openrouter.ai/api/v1/chat/completions"

    def generate(self, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not set")

        def _call():
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://darpilot.local",
                "X-Title": "DarPilot",
            }
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 500,
            }
            resp = requests.post(self.url, json=payload, headers=headers, timeout=self.timeout)
            if resp.status_code in self.RETRY_STATUS_CODES:
                raise RuntimeError(f"OpenRouter rate limited ({resp.status_code})")
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

        return self._retry_with_backoff(_call)


# ── Resilient client with provider fallback ────────────────────────────────

class ResilientLLMClient(LLMClient):
    """Wraps multiple providers with retry/backoff and fallback chain."""

    def __init__(self, providers: Optional[List[LLMClient]] = None):
        self.providers = providers or self._default_providers()

    def _default_providers(self) -> List[LLMClient]:
        providers: List[LLMClient] = []
        if os.environ.get("GEMINI_API_KEY"):
            providers.append(GeminiLLMClient())
        if os.environ.get("OPENROUTER_API_KEY"):
            providers.append(OpenRouterLLMClient())
        # Fake client is always last as ultimate fallback
        providers.append(FakeLLMClient())
        return providers

    def generate(self, prompt: str) -> str:
        last_exception = None
        for provider in self.providers:
            try:
                return provider.generate(prompt)
            except Exception as exc:
                last_exception = exc
                # Check if it's a retryable error (429 or 503)
                error_str = str(exc)
                is_retryable = "429" in error_str or "503" in error_str
                # For 404 (invalid key/model) and other client errors, fall through
                is_client_error = "40" in error_str and "429" not in error_str
                # Fake client never fails, but if it does, don't retry
                is_fake = isinstance(provider, FakeLLMClient)
                
                if is_retryable and not is_fake:
                    # Retryable error but we already retried in the provider
                    # Fall through to next provider
                    continue
                # For all other errors (including 404), fall through to next provider
                continue
        # If all live providers failed, the fake client is the last in the chain
        return self.providers[-1].generate(prompt)


# ── Factory ────────────────────────────────────────────────────────────────

def get_llm_client() -> LLMClient:
    """Return a resilient client with provider fallback chain."""
    return ResilientLLMClient()