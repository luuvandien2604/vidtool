"""Opt-in live tests for AI Narration Scriptwriting and Fact Verification Grounding APIs.

Gated under `@pytest.mark.live_llm` and skipped in the default test suite.
Requires live `GEMINI_API_KEY` and/or `ANTHROPIC_API_KEY`.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from videotool.domain.claims import VerificationStatus
from videotool.pipeline.narration_intake import NarrationIntakeService
from videotool.providers.env import load_env_fallback
from videotool.providers.fact_verification import GeminiWebSearchFactVerifier
from videotool.providers.narration_writer import GeminiNarrationWriterProvider

load_env_fallback()


@pytest.mark.live_llm
def test_live_gemini_narration_writer_and_fact_verifier(tmp_path):
    """End-to-end live test of Gemini scriptwriting and Google Search fact grounding."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        pytest.skip("GEMINI_API_KEY not set in environment or .env")

    out_narr = tmp_path / "gemini_narration.json"
    out_rep = tmp_path / "gemini_fact_report.json"

    service = NarrationIntakeService(
        writer_provider_name="gemini",
        verifier_provider_name="gemini",
        mode="draft",
    )

    topic = "The Fall of the Berlin Wall in November 1989"
    narration, report = service.process(
        topic=topic,
        target_duration_sec=45.0,
        language="en",
        out_narration_path=out_narr,
        out_report_path=out_rep,
    )

    print(f"\n[LIVE TEST] Topic: {topic}")
    print(f"[LIVE TEST] Narration text ({len(narration.text.split())} words):\n{narration.text}\n")
    print(f"[LIVE TEST] Total claims extracted: {report.total_claims}")
    print(f"[LIVE TEST] Breakdown: {report.verified_count} VERIFIED, {report.uncertain_count} UNCERTAIN, {report.contradicted_count} CONTRADICTED")

    for v in report.verifications:
        c = next((claim for claim in report.claims if claim.claim_id == v.claim_id), None)
        print(f"  - [{v.claim_id}] {v.status.value} (conf: {v.confidence}): '{c.text if c else ''}'")
        if v.source_urls:
            print(f"    sources: {v.source_urls[:2]}")
        if v.note:
            print(f"    note: {v.note}")

    assert len(narration.text) > 50
    assert report.total_claims >= 2
    assert report.passed_gate is True
    assert out_narr.is_file()
    assert out_rep.is_file()


@pytest.mark.live_llm
def test_live_claude_narration_writer_and_fact_verifier(tmp_path):
    """End-to-end live test of Claude scriptwriting and web search fact verification."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set in environment or .env")

    out_narr = tmp_path / "claude_narration.json"
    out_rep = tmp_path / "claude_fact_report.json"

    service = NarrationIntakeService(
        writer_provider_name="claude",
        verifier_provider_name="claude",
        mode="draft",
    )

    topic = "Apollo 11 Moon Landing July 1969"
    narration, report = service.process(
        topic=topic,
        target_duration_sec=40.0,
        language="en",
        out_narration_path=out_narr,
        out_report_path=out_rep,
    )

    print(f"\n[LIVE CLAUDE TEST] Topic: {topic}")
    print(f"[LIVE CLAUDE TEST] Total claims: {report.total_claims}")
    print(f"[LIVE CLAUDE TEST] Breakdown: {report.verified_count} VERIFIED, {report.uncertain_count} UNCERTAIN, {report.contradicted_count} CONTRADICTED")

    assert len(narration.text) > 50
    assert report.total_claims >= 2
    assert out_narr.is_file()
    assert out_rep.is_file()
