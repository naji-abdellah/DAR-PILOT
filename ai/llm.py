"""Minimal LLM client for DarPilot answer generation (M3).

Two implementations:
- ``FakeLLMClient``: works offline with no API key. Builds an answer from the
  retrieved listing chunks, citing listing IDs, and refuses when nothing is
  relevant. Used for the M3 demo and tests.
- ``GeminiLLMClient``: calls the Gemini REST API when ``GEMINI_API_KEY`` is
  set. Wired up in M4 with retry/fallback to OpenRouter.

The interface is intentionally small (``generate(prompt) -> str``) so M4 can
swap in the full client without changing the RAG route.
"""

from __future__ import annotations

import os
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
            # format: - [id: 3] Villa in Palmeraie (Marrakech) 4500000 MAD
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


# ── Gemini client (real API) ───────────────────────────────────────────────

class GeminiLLMClient(LLMClient):
    """Calls the Gemini 1.5 Flash REST API (free tier)."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-flash"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model = model
        self.url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}"
            f":generateContent?key={self.api_key}"
        )

    def generate(self, prompt: str) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        try:
            resp = requests.post(self.url, json=payload, timeout=30)
            if resp.status_code == 429:
                raise RuntimeError("Gemini rate limited (429)")
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except requests.RequestException as exc:
            raise RuntimeError(f"Gemini request failed: {exc}") from exc


# ── Factory ────────────────────────────────────────────────────────────────

def get_llm_client() -> LLMClient:
    """Return a Gemini client when an API key is configured, else the fake."""
    if os.environ.get("GEMINI_API_KEY"):
        return GeminiLLMClient()
    return FakeLLMClient()
