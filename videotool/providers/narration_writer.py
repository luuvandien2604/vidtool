"""AI Narration Writer provider implementations (Phase 4).

Generates documentary voiceover scripts from topics with structured factual claim extraction.
All API communication uses Python standard library `urllib` (no external SDKs).
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Protocol

from videotool.domain.claims import ClaimType, FactualClaim
from videotool.domain.narration import Narration
from videotool.providers.env import (get_anthropic_api_key, get_gemini_api_key,
                                     load_env_fallback)


class NarrationWriterProvider(Protocol):
    """Protocol for AI narration scriptwriter and claim extractor."""
    provider_id: str

    def write(
        self,
        topic: str,
        target_duration_sec: float | None = None,
        language: str = "en",
    ) -> tuple[Narration, list[FactualClaim]]:
        ...


def calculate_claim_spans(narration_text: str, claims_raw: list[dict]) -> list[FactualClaim]:
    """Calculate character offset spans in Python to avoid LLM indexing hallucinations."""
    results: list[FactualClaim] = []
    
    for i, c in enumerate(claims_raw):
        cid = c.get("claim_id") or f"claim_{i+1:03d}"
        text = str(c.get("text", "")).strip()
        if not text:
            continue
            
        ctype_str = str(c.get("claim_type", "EVENT")).upper()
        try:
            ctype = ClaimType(ctype_str)
        except ValueError:
            ctype = ClaimType.EVENT

        # Search for verbatim occurrence in narration text
        start_idx = narration_text.find(text)
        if start_idx != -1:
            span = (start_idx, start_idx + len(text))
        else:
            # Case-insensitive / whitespace-normalized fallback
            norm_text = re.escape(re.sub(r"\s+", " ", text))
            m = re.search(norm_text, narration_text, re.IGNORECASE)
            if m:
                span = (m.start(), m.end())
            else:
                span = (0, len(text))

        results.append(FactualClaim(
            claim_id=cid,
            text=text,
            claim_type=ctype,
            narration_span=span,
        ))

    return results


def _build_writer_system_prompt() -> str:
    return (
        "You are an expert historical documentary scriptwriter and fact-checking researcher.\n"
        "Your task is to write an engaging, high-impact documentary narration script for a given topic and target duration, "
        "and systematically extract all atomic factual claims contained in the script.\n\n"
        "Guidelines for Narration:\n"
        "- Style: Cinematic, narrative-driven, authoritative, Vox/PBS Frontline style.\n"
        "- Pace: Target roughly 130-150 spoken words per minute (e.g. 90 seconds = ~200-220 words).\n"
        "- Accuracy: Use precise, historically verified facts, dates, named entities, and figures.\n\n"
        "Guidelines for Claim Extraction:\n"
        "- Enumerate every atomic factual claim that can be verified independently against historical records or reference sources.\n"
        "- Categories of claims:\n"
        "  - DATE: specific years, months, days, timeframes (e.g., 'July 20, 1969', 'in the nineteenth century').\n"
        "  - ENTITY: named historical figures, specific organizations, cities, countries, landmarks (e.g., 'Neil Armstrong', 'NASA').\n"
        "  - NUMBER: statistics, quantities, distances, measurements (e.g., '384,400 kilometers', 'over one million').\n"
        "  - QUOTE: attributed direct or indirect quotes (e.g., 'one small step for man').\n"
        "  - EVENT: discrete occurrences, decisions, policy shifts (e.g., 'the spacecraft entered lunar orbit').\n"
        "- For each claim, provide:\n"
        "  - claim_id: 'claim_001', 'claim_002', etc.\n"
        "  - text: the exact verbatim statement or phrase snippet from your written narration.\n"
        "  - claim_type: 'DATE' | 'ENTITY' | 'NUMBER' | 'QUOTE' | 'EVENT'\n"
        "- Do NOT guess or provide character offsets in the JSON. The Python layer calculates character offsets.\n\n"
        "Output strictly valid JSON with the following schema:\n"
        "{\n"
        '  "narration": "Full narration text...",\n'
        '  "claims": [\n'
        '    {"claim_id": "claim_001", "text": "verbatim snippet", "claim_type": "DATE"}\n'
        '  ]\n'
        "}"
    )


def _build_writer_user_prompt(topic: str, target_duration_sec: float | None, language: str) -> str:
    dur_sec = target_duration_sec or 60.0
    approx_words = int(dur_sec * 2.4)
    lang_name = "Vietnamese" if language == "vi" else "English"
    return (
        f"Topic: {topic}\n"
        f"Language: {lang_name} ({language})\n"
        f"Target Duration: {dur_sec:.1f} seconds (approx. {approx_words} spoken words/syllables)\n\n"
        f"Write the documentary narration script in {lang_name} and extract all verifiable factual claims."
    )


def _extract_json_dict(raw_text: str) -> dict:
    """Robustly extract and parse JSON object from LLM response text."""
    if not raw_text:
        return {}
    try:
        data = json.loads(raw_text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    fence_m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text, re.IGNORECASE)
    if fence_m:
        try:
            data = json.loads(fence_m.group(1).strip())
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    bracket_m = re.search(r"\{[\s\S]*\}", raw_text)
    if bracket_m:
        try:
            data = json.loads(bracket_m.group(0))
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    return {}


class ClaudeNarrationWriterProvider:
    """Writes documentary narration using Anthropic Claude Messages API via stdlib urllib."""
    provider_id = "claude"

    def __init__(self, model: str | None = None, api_key: str | None = None, timeout_sec: float = 60.0):
        load_env_fallback()
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "").strip()
        self.model = model or os.environ.get("ANTHROPIC_NARRATION_MODEL", "claude-sonnet-5")
        self.timeout_sec = timeout_sec

    def write(
        self,
        topic: str,
        target_duration_sec: float | None = None,
        language: str = "en",
    ) -> tuple[Narration, list[FactualClaim]]:
        if not self.api_key:
            self.api_key = get_anthropic_api_key()

        system_prompt = _build_writer_system_prompt()
        user_prompt = _build_writer_user_prompt(topic, target_duration_sec, language)

        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3,
        }

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
            "user-agent": "vidtool/0.1.0",
        }

        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Claude API request failed ({err.code}): {err_body}") from err
        except Exception as err:
            raise RuntimeError(f"Claude API network failure: {err}") from err

        # Extract text content
        content_blocks = resp_data.get("content", [])
        raw_text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")

        parsed = _extract_json_dict(raw_text)
        narration_text = parsed.get("narration", "").strip()
        claims_raw = parsed.get("claims", [])

        if not narration_text:
            raise ValueError(f"Claude did not return valid narration text: {raw_text[:200]}")

        claims = calculate_claim_spans(narration_text, claims_raw)
        narration = Narration(text=narration_text, language=language)
        return narration, claims


class GeminiNarrationWriterProvider:
    """Writes documentary narration using Google Gemini API via stdlib urllib."""
    provider_id = "gemini"

    def __init__(self, model: str | None = None, api_key: str | None = None, timeout_sec: float = 60.0):
        load_env_fallback()
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "").strip()
        # gemini-flash-latest is a Google-maintained alias that auto-updates to the current GA Flash model
        self.model = model or os.environ.get("GEMINI_NARRATION_MODEL", "gemini-flash-latest")
        self.timeout_sec = timeout_sec

    def write(
        self,
        topic: str,
        target_duration_sec: float | None = None,
        language: str = "en",
    ) -> tuple[Narration, list[FactualClaim]]:
        if not self.api_key:
            self.api_key = get_gemini_api_key()

        system_prompt = _build_writer_system_prompt()
        user_prompt = _build_writer_user_prompt(topic, target_duration_sec, language)

        payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}]
            },
            "contents": [
                {"parts": [{"text": user_prompt}]}
            ],
            "generationConfig": {
                "temperature": 0.3,
                "responseMimeType": "application/json",
            },
        }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {
            "content-type": "application/json",
            "user-agent": "vidtool/0.1.0",
        }

        resp_data = None
        last_err = None
        import time

        for attempt in range(3):
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    break
            except urllib.error.HTTPError as err:
                err_body = err.read().decode("utf-8", errors="replace")
                last_err = err
                if err.code in (429, 500, 503) and attempt < 2:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                raise RuntimeError(f"Gemini API request failed ({err.code}): {err_body}") from err
            except Exception as err:
                last_err = err
                if attempt < 2:
                    time.sleep(2.0 * (attempt + 1))
                    continue
                raise RuntimeError(f"Gemini API network failure: {err}") from err

        if resp_data is None:
            raise RuntimeError(f"Gemini API failed after 3 attempts: {last_err}")

        candidates = resp_data.get("candidates", [])
        if not candidates:
            raise ValueError(f"Gemini returned no candidates: {resp_data}")

        parts = candidates[0].get("content", {}).get("parts", [])
        raw_text = "".join(p.get("text", "") for p in parts)

        parsed = _extract_json_dict(raw_text)
        narration_text = parsed.get("narration", "").strip()
        claims_raw = parsed.get("claims", [])

        if not narration_text:
            raise ValueError(f"Gemini did not return valid narration text: {raw_text[:200]}")

        claims = calculate_claim_spans(narration_text, claims_raw)
        narration = Narration(text=narration_text, language=language)
        return narration, claims


# Provider Registry
NARRATION_WRITER_PROVIDERS: dict[str, type] = {}


def register_narration_writer(name: str, cls: type) -> None:
    """Register a narration writer provider implementation."""
    NARRATION_WRITER_PROVIDERS[name] = cls


register_narration_writer("claude", ClaudeNarrationWriterProvider)
register_narration_writer("gemini", GeminiNarrationWriterProvider)


def build_narration_writer(name: str, **kwargs) -> NarrationWriterProvider:
    """Build a narration writer provider instance from registry."""
    if name not in NARRATION_WRITER_PROVIDERS:
        raise KeyError(
            f"unknown narration writer provider '{name}' (have: {sorted(NARRATION_WRITER_PROVIDERS)})"
        )
    return NARRATION_WRITER_PROVIDERS[name](**kwargs)


__all__ = [
    "NarrationWriterProvider",
    "calculate_claim_spans",
    "ClaudeNarrationWriterProvider",
    "GeminiNarrationWriterProvider",
    "NARRATION_WRITER_PROVIDERS",
    "register_narration_writer",
    "build_narration_writer",
]
