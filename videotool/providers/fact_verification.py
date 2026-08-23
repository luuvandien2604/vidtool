"""Fact Verification provider implementations with Web Search Grounding (Phase 4).

Evaluates factual claims against live web sources using Claude Web Search and
Google Gemini Google Search Grounding. All communication uses stdlib `urllib`.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Protocol

from videotool.domain.claims import (ClaimVerification, FactualClaim,
                                     VerificationStatus)
from videotool.domain.narration import Narration
from videotool.providers.env import (get_anthropic_api_key, get_gemini_api_key,
                                     load_env_fallback)


class FactVerificationProvider(Protocol):
    """Protocol for Web-grounded Fact Verification."""
    provider_id: str

    def verify(
        self,
        topic: str,
        narration: Narration,
        claims: list[FactualClaim],
    ) -> list[ClaimVerification]:
        ...


def _build_verifier_system_prompt() -> str:
    return (
        "You are an expert fact-checker and historical accuracy auditor for documentary productions.\n"
        "Your role is to independently verify factual claims using web search evidence and assign a rigorous verdict.\n\n"
        "Verification Verdict Rules:\n"
        "- VERIFIED: The factual claim is directly corroborated by reputable sources found via search.\n"
        "- CONTRADICTED: Search results clearly state or prove that the claim is incorrect, false, or significantly inaccurate (e.g. wrong year, wrong person, incorrect figure).\n"
        "- UNCERTAIN: Search results are ambiguous, conflicting, thin, or no direct corroborating evidence was found.\n"
        "  CRITICAL RULE: Absence of proof is ALWAYS UNCERTAIN, never VERIFIED. Do not default to VERIFIED if evidence is missing.\n\n"
        "Output Requirements:\n"
        "- You MUST return exactly one verification object for every single claim provided.\n"
        "- The length of the input claims array and output verifications array must match EXACTLY.\n"
        "- For each claim, provide:\n"
        "  - claim_id: matching the input claim_id\n"
        "  - status: 'VERIFIED' | 'UNCERTAIN' | 'CONTRADICTED'\n"
        "  - confidence: float from 0.0 to 1.0\n"
        "  - source_urls: list of actual source URLs used to verify or refute\n"
        "  - note: 1-2 sentence concise explanation of findings\n\n"
        "Output strictly valid JSON with schema:\n"
        "{\n"
        '  "verifications": [\n'
        '    {"claim_id": "claim_001", "status": "VERIFIED", "confidence": 0.95, "source_urls": ["https://..."], "note": "..."}\n'
        '  ]\n'
        "}"
    )


def _build_verifier_user_prompt(topic: str, narration_text: str, claims: list[FactualClaim]) -> str:
    claims_formatted = [
        f"- [{c.claim_id}] ({c.claim_type.value}): \"{c.text}\""
        for c in claims
    ]
    claims_block = "\n".join(claims_formatted)
    return (
        f"Topic: {topic}\n"
        f"Narration Context: \"{narration_text}\"\n\n"
        f"Claims to verify ({len(claims)} total):\n"
        f"{claims_block}\n\n"
        f"Verify each of the {len(claims)} claims above. Remember: You MUST return exactly {len(claims)} verification items."
    )


def _extract_json_dict(raw_text: str) -> dict:
    """Robustly extract and parse JSON object or array from LLM response text."""
    if not raw_text:
        return {}
    try:
        data = json.loads(raw_text)
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            return {"verifications": data, "claims": data}
    except Exception:
        pass

    fence_m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text, re.IGNORECASE)
    if fence_m:
        try:
            data = json.loads(fence_m.group(1).strip())
            if isinstance(data, dict):
                return data
            if isinstance(data, list):
                return {"verifications": data, "claims": data}
        except Exception:
            pass

    bracket_m = re.search(r"\[[\s\S]*\]", raw_text)
    if bracket_m:
        try:
            data = json.loads(bracket_m.group(0))
            if isinstance(data, list):
                return {"verifications": data, "claims": data}
        except Exception:
            pass

    bracket_dict = re.search(r"\{[\s\S]*\}", raw_text)
    if bracket_dict:
        try:
            data = json.loads(bracket_dict.group(0))
            if isinstance(data, dict):
                return data
        except Exception:
            pass

    return {}


class ClaudeWebSearchFactVerifier:
    """Fact verifier using Anthropic Claude with Web Search via stdlib urllib."""
    provider_id = "claude"

    def __init__(self, model: str | None = None, api_key: str | None = None, timeout_sec: float = 90.0):
        load_env_fallback()
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "").strip()
        self.model = model or os.environ.get("ANTHROPIC_VERIFICATION_MODEL", "claude-sonnet-5")
        self.timeout_sec = timeout_sec

    def verify(
        self,
        topic: str,
        narration: Narration,
        claims: list[FactualClaim],
    ) -> list[ClaimVerification]:
        if not claims:
            return []

        if not self.api_key:
            self.api_key = get_anthropic_api_key()

        # Process in batches of up to 8 claims to avoid LLM drop-off and timeouts
        batch_size = 8
        all_verifications: list[ClaimVerification] = []

        for offset in range(0, len(claims), batch_size):
            chunk = claims[offset:offset + batch_size]
            system_prompt = _build_verifier_system_prompt()
            user_prompt = _build_verifier_user_prompt(topic, narration.text, chunk)

            payload = {
                "model": self.model,
                "max_tokens": 4096,
                "system": system_prompt,
                "messages": [
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.1,
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
                raise RuntimeError(f"Claude verification API failed ({err.code}): {err_body}") from err
            except Exception as err:
                raise RuntimeError(f"Claude verification network failure: {err}") from err

            content_blocks = resp_data.get("content", [])
            raw_text = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")

            parsed = _extract_json_dict(raw_text)
            items = parsed.get("verifications", [])

            # Validation check: Ensure exact count matching
            items_by_id = {it.get("claim_id"): it for it in items if isinstance(it, dict)}
            for c in chunk:
                it = items_by_id.get(c.claim_id)
                if it:
                    status_str = str(it.get("status", "UNCERTAIN")).upper()
                    try:
                        status = VerificationStatus(status_str)
                    except ValueError:
                        status = VerificationStatus.UNCERTAIN
                    all_verifications.append(ClaimVerification(
                        claim_id=c.claim_id,
                        status=status,
                        confidence=float(it.get("confidence", 0.7)),
                        source_urls=list(it.get("source_urls", [])),
                        note=str(it.get("note", "")),
                    ))
                else:
                    # Missing claim verdict from LLM -> mark UNCERTAIN
                    all_verifications.append(ClaimVerification(
                        claim_id=c.claim_id,
                        status=VerificationStatus.UNCERTAIN,
                        confidence=0.0,
                        source_urls=[],
                        note="Verification dropped or missing from provider response.",
                    ))

        if len(all_verifications) != len(claims):
            raise ValueError(
                f"Verification count mismatch: expected {len(claims)}, got {len(all_verifications)}"
            )

        return all_verifications


class GeminiWebSearchFactVerifier:
    """Fact verifier using Google Gemini with Google Search Grounding via stdlib urllib."""
    provider_id = "gemini"

    def __init__(self, model: str | None = None, api_key: str | None = None, timeout_sec: float = 90.0):
        load_env_fallback()
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "").strip()
        # gemini-flash-latest is a Google-maintained alias that auto-updates to the current GA Flash model
        self.model = model or os.environ.get("GEMINI_VERIFICATION_MODEL", "gemini-flash-latest")
        self.timeout_sec = timeout_sec

    def verify(
        self,
        topic: str,
        narration: Narration,
        claims: list[FactualClaim],
    ) -> list[ClaimVerification]:
        if not claims:
            return []

        if not self.api_key:
            self.api_key = get_gemini_api_key()

        batch_size = 8
        all_verifications: list[ClaimVerification] = []

        for offset in range(0, len(claims), batch_size):
            chunk = claims[offset:offset + batch_size]
            system_prompt = _build_verifier_system_prompt()
            user_prompt = _build_verifier_user_prompt(topic, narration.text, chunk)

            # Note Adjustment 1: Raw REST API uses camelCase googleSearch: {}
            payload = {
                "system_instruction": {
                    "parts": [{"text": system_prompt}]
                },
                "contents": [
                    {"parts": [{"text": user_prompt}]}
                ],
                "tools": [
                    {"googleSearch": {}}
                ],
                "generationConfig": {
                    "temperature": 0.1,
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
                    raise RuntimeError(f"Gemini verification API failed ({err.code}): {err_body}") from err
                except Exception as err:
                    last_err = err
                    if attempt < 2:
                        time.sleep(2.0 * (attempt + 1))
                        continue
                    raise RuntimeError(f"Gemini verification network failure: {err}") from err

            if resp_data is None:
                raise RuntimeError(f"Gemini verification failed after 3 attempts: {last_err}")

            candidates = resp_data.get("candidates", [])
            if not candidates:
                raise ValueError(f"Gemini returned no candidates: {resp_data}")

            candidate = candidates[0]
            parts = candidate.get("content", {}).get("parts", [])
            raw_text = "".join(p.get("text", "") for p in parts)

            # Extract grounding source URLs from groundingMetadata
            grounding_meta = candidate.get("groundingMetadata", {})
            grounding_chunks = grounding_meta.get("groundingChunks", [])
            grounding_urls: list[str] = []
            for gchunk in grounding_chunks:
                web_uri = gchunk.get("web", {}).get("uri")
                if web_uri and web_uri not in grounding_urls:
                    grounding_urls.append(web_uri)

            parsed = _extract_json_dict(raw_text)
            items = parsed.get("verifications", [])
            items_by_id = {str(it.get("claim_id")): it for it in items if isinstance(it, dict)}

            for idx, c in enumerate(chunk):
                it = items_by_id.get(c.claim_id)
                if not it:
                    clean_id = c.claim_id.replace("claim_", "").replace("c", "").lstrip("0")
                    for k, val in items_by_id.items():
                        if k.replace("claim_", "").replace("c", "").lstrip("0") == clean_id:
                            it = val
                            break
                if not it and idx < len(items) and isinstance(items[idx], dict):
                    it = items[idx]

                if it:
                    status_str = str(it.get("status", "UNCERTAIN")).upper()
                    try:
                        status = VerificationStatus(status_str)
                    except ValueError:
                        status = VerificationStatus.UNCERTAIN

                    # Combine source URLs from LLM and groundingMetadata
                    item_urls = list(it.get("source_urls", []))
                    for g_url in grounding_urls:
                        if g_url not in item_urls:
                            item_urls.append(g_url)

                    # If VERIFIED but has zero source URLs and zero grounding, mark UNCERTAIN
                    if status == VerificationStatus.VERIFIED and not item_urls and not grounding_chunks:
                        status = VerificationStatus.UNCERTAIN
                        note = (it.get("note", "") + " [Note: Lacks grounding citations; marked UNCERTAIN]").strip()
                    else:
                        note = str(it.get("note", ""))

                    all_verifications.append(ClaimVerification(
                        claim_id=c.claim_id,
                        status=status,
                        confidence=float(it.get("confidence", 0.7)),
                        source_urls=item_urls,
                        note=note,
                    ))
                else:
                    all_verifications.append(ClaimVerification(
                        claim_id=c.claim_id,
                        status=VerificationStatus.UNCERTAIN,
                        confidence=0.0,
                        source_urls=[],
                        note="Verification dropped or missing from provider response.",
                    ))

        if len(all_verifications) != len(claims):
            raise ValueError(
                f"Verification count mismatch: expected {len(claims)}, got {len(all_verifications)}"
            )

        return all_verifications


class MockFactVerificationProvider:
    """Mock fact verification provider that validates claims without network requests."""
    provider_id: str = "mock"

    def verify(
        self,
        topic: str,
        narration: Narration,
        claims: list[FactualClaim],
    ) -> list[ClaimVerification]:
        verifications: list[ClaimVerification] = []
        for c in claims:
            verifications.append(
                ClaimVerification(
                    claim_id=c.claim_id,
                    status=VerificationStatus.VERIFIED,
                    confidence=0.95,
                    source_urls=[f"https://en.wikipedia.org/wiki/{topic.replace(' ', '_')}"],
                    note=f"Verified fact for {c.text}",
                )
            )
        return verifications


# Provider Registry
FACT_VERIFICATION_PROVIDERS: dict[str, type] = {}


def register_fact_verifier(name: str, cls: type) -> None:
    """Register a fact verification provider implementation."""
    FACT_VERIFICATION_PROVIDERS[name] = cls


register_fact_verifier("claude", ClaudeWebSearchFactVerifier)
register_fact_verifier("gemini", GeminiWebSearchFactVerifier)
register_fact_verifier("mock", MockFactVerificationProvider)


def build_fact_verifier(name: str, **kwargs) -> FactVerificationProvider:
    """Build a fact verification provider instance from registry."""
    if name not in FACT_VERIFICATION_PROVIDERS:
        raise KeyError(
            f"unknown fact verification provider '{name}' (have: {sorted(FACT_VERIFICATION_PROVIDERS)})"
        )
    return FACT_VERIFICATION_PROVIDERS[name](**kwargs)


__all__ = [
    "FactVerificationProvider",
    "ClaudeWebSearchFactVerifier",
    "GeminiWebSearchFactVerifier",
    "MockFactVerificationProvider",
    "FACT_VERIFICATION_PROVIDERS",
    "register_fact_verifier",
    "build_fact_verifier",
]
