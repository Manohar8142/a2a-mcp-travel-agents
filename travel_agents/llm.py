"""Pluggable LLM providers: Gemini, Groq, OpenAI, or an offline mock.

Agents use two operations: ``extract`` (natural language -> JSON fields) and ``write``
(free text, e.g. the final itinerary summary).
"""
from __future__ import annotations

import json
import os
import re
from datetime import date, timedelta
from typing import Protocol

import httpx

EXTRACT_PROMPT = """Extract the trip request as JSON with exactly these keys:
origin (city), destination (city), depart_date (YYYY-MM-DD), nights (int), travelers (int),
traveler_name (string or null), max_hotel_price (number or null), book (true if the user asked to book).
Today is {today}. Return only JSON.

Request: {text}"""


class LLM(Protocol):
    def extract(self, text: str) -> dict: ...
    def write(self, prompt: str) -> str: ...


def _parse_json(raw: str) -> dict:
    m = re.search(r"\{.*\}", raw, re.S)
    return json.loads(m.group(0)) if m else {}


class OpenAICompatibleLLM:
    """OpenAI or Groq (both expose /chat/completions)."""

    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.model = model
        self._client = httpx.Client(base_url=base_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=60)

    def _chat(self, prompt: str, json_mode: bool = False) -> str:
        body = {"model": self.model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        r = self._client.post("/chat/completions", json=body)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def extract(self, text: str) -> dict:
        return _parse_json(self._chat(EXTRACT_PROMPT.format(today=date.today(), text=text), json_mode=True))

    def write(self, prompt: str) -> str:
        return self._chat(prompt)


class GeminiLLM:
    def __init__(self, api_key: str, model: str) -> None:
        from google import genai  # pip install google-genai

        self._client = genai.Client(api_key=api_key)
        self.model = model

    def extract(self, text: str) -> dict:
        r = self._client.models.generate_content(
            model=self.model,
            contents=EXTRACT_PROMPT.format(today=date.today(), text=text),
            config={"response_mime_type": "application/json"},
        )
        return _parse_json(r.text)

    def write(self, prompt: str) -> str:
        return self._client.models.generate_content(model=self.model, contents=prompt).text


class MockLLM:
    """Regex parser + template writer. Deterministic, offline."""

    def extract(self, text: str) -> dict:
        t = text.lower()
        route = re.search(r"from\s+([a-z]+)\s+to\s+([a-z]+)", t)
        when = re.search(r"\d{4}-\d{2}-\d{2}", t)
        nights = re.search(r"(\d+)\s*nights?", t)
        people = re.search(r"(\d+)\s*(?:travell?ers|people|adults|guests|of us)", t)
        name = re.search(r"(?:my name is|name:|for traveller|for traveler)\s+([a-z]+(?:\s[a-z]+)?)", t)
        budget = re.search(r"(?:under|below|max)\s*\$?\s*(\d+)", t)
        return {
            "origin": route.group(1) if route else None,
            "destination": route.group(2) if route else None,
            "depart_date": when.group(0) if when else (date.today() + timedelta(days=14)).isoformat(),
            "nights": int(nights.group(1)) if nights else 2,
            "travelers": int(people.group(1)) if people else 1,
            "traveler_name": name.group(1).title() if name else None,
            "max_hotel_price": float(budget.group(1)) if budget else None,
            "book": bool(re.search(r"\bbook\b", t)),
        }

    def write(self, prompt: str) -> str:
        # The orchestrator puts a ready-made factual draft after "DRAFT:"; the mock returns it as-is.
        return prompt.split("DRAFT:", 1)[-1].strip()


def get_llm(provider: str | None = None) -> LLM:
    provider = (provider or os.getenv("LLM_PROVIDER", "mock")).lower()
    if provider == "gemini":
        return GeminiLLM(os.environ["GEMINI_API_KEY"], os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    if provider == "groq":
        return OpenAICompatibleLLM(os.environ["GROQ_API_KEY"], "https://api.groq.com/openai/v1", os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
    if provider == "openai":
        return OpenAICompatibleLLM(os.environ["OPENAI_API_KEY"], "https://api.openai.com/v1", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))
    return MockLLM()
