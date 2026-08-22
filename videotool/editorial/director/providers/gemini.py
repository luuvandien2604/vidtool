"""Google Gemini provider for AI Editorial Director (Phase 3A).

Uses Python standard library `urllib` to query Google Gemini REST API.
Enforces JSON response parsing, schema repair, and robust error handling.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from videotool.editorial.director.models import (
    EditorialDirectorRequest,
    EditorialIntent,
)
from videotool.editorial.director.prompt import (
    build_beat_prompt,
    build_system_prompt,
)
from videotool.providers.env import get_gemini_api_key


def _extract_json_block(text: str) -> dict[str, Any]:
    """Extract and parse JSON object from LLM response text."""
    text = text.strip()
    # 1. Direct JSON parse
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # 2. Markdown fenced code block ```json ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        try:
            data = json.loads(match.group(1).strip())
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    # 3. Outer brace extraction
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(text[start : end + 1])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Failed to extract valid JSON from Gemini response: {text[:200]}")


class GeminiEditorialDirectorProvider:
    """Queries Gemini REST API to produce editorial proposals."""
    provider_id: str = "gemini"

    def __init__(
        self,
        # gemini-flash-latest is a Google-maintained alias that auto-updates to the current GA Flash model
        model_name: str = "gemini-flash-latest",
        api_key: str | None = None,
        timeout_sec: float = 15.0,
    ):
        self.model_name = model_name
        self._api_key = api_key
        self.timeout_sec = timeout_sec

    def _resolve_api_key(self) -> str:
        if self._api_key:
            return self._api_key
        return get_gemini_api_key()

    def generate_intent(self, request: EditorialDirectorRequest) -> EditorialIntent:
        api_key = self._resolve_api_key()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={api_key}"

        system_prompt = build_system_prompt()
        user_prompt = build_beat_prompt(request)

        payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}],
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.2,
            },
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data_bytes,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))

        # Extract text from response candidates
        candidates = resp_data.get("candidates", [])
        if not candidates:
            raise ValueError(f"Gemini returned empty candidates: {resp_data}")

        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise ValueError(f"Gemini candidate missing content parts: {candidates[0]}")

        raw_text = parts[0].get("text", "")
        parsed = _extract_json_block(raw_text)

        parsed["beat_id"] = request.beat_id
        return EditorialIntent.from_dict(parsed)
