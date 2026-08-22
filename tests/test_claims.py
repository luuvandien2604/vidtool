"""Unit tests for Phase 4 Factual Claims, Fact Verification Gate, and Providers (Offline)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from videotool.domain.claims import (ClaimType, ClaimVerification,
                                     FactVerificationReport, FactualClaim,
                                     VerificationStatus)
from videotool.domain.narration import Narration
from videotool.pipeline.narration_intake import (
    FactVerificationGateError, NarrationIntakeService,
    evaluate_fact_verification_gate)
from videotool.providers.fact_verification import (GeminiWebSearchFactVerifier,
                                                  build_fact_verifier)
from videotool.providers.narration_writer import (
    ClaudeNarrationWriterProvider, GeminiNarrationWriterProvider,
    build_narration_writer, calculate_claim_spans)


def test_claim_and_verification_serialization():
    """Verify serialization round-trips for FactualClaim, ClaimVerification, FactVerificationReport."""
    claim = FactualClaim(
        claim_id="claim_001",
        text="November 9, 1989",
        claim_type=ClaimType.DATE,
        narration_span=(0, 16),
    )
    d = claim.to_dict()
    assert d["claim_id"] == "claim_001"
    assert d["claim_type"] == "DATE"
    assert d["narration_span"] == [0, 16]

    claim_rt = FactualClaim.from_dict(d)
    assert claim_rt == claim

    verif = ClaimVerification(
        claim_id="claim_001",
        status=VerificationStatus.VERIFIED,
        confidence=0.98,
        source_urls=["https://en.wikipedia.org/wiki/Berlin_Wall"],
        note="Corroborated by historical records.",
    )
    vd = verif.to_dict()
    assert vd["status"] == "VERIFIED"
    assert vd["confidence"] == 0.98
    assert vd["source_urls"] == ["https://en.wikipedia.org/wiki/Berlin_Wall"]

    verif_rt = ClaimVerification.from_dict(vd)
    assert verif_rt == verif

    report = FactVerificationReport(
        topic="Berlin Wall",
        narration_text="November 9, 1989 was a historic day.",
        claims=[claim],
        verifications=[verif],
        total_claims=1,
        verified_count=1,
        uncertain_count=0,
        contradicted_count=0,
        passed_gate=True,
        gate_mode="final",
        warnings=[],
    )
    rd = report.to_dict()
    report_rt = FactVerificationReport.from_dict(rd)
    assert report_rt.topic == "Berlin Wall"
    assert report_rt.total_claims == 1
    assert report_rt.verified_count == 1
    assert report_rt.passed_gate is True


def test_calculate_claim_spans_python_layer():
    """Verify that Python layer computes exact character offsets from LLM verbatim snippets."""
    narration_text = (
        "On November 9, 1989, Gunter Schabowski mistakenly announced that travel restrictions "
        "were lifted immediately. Over twenty thousand East Germans gathered at Bornholmer Straße."
    )
    raw_claims = [
        {"claim_id": "c1", "text": "November 9, 1989", "claim_type": "DATE"},
        {"claim_id": "c2", "text": "Gunter Schabowski", "claim_type": "ENTITY"},
        {"claim_id": "c3", "text": "twenty thousand", "claim_type": "NUMBER"},
        {"claim_id": "c4", "text": "Bornholmer Straße", "claim_type": "ENTITY"},
        {"claim_id": "c5", "text": "Non-existent phrase", "claim_type": "EVENT"},
    ]

    spans = calculate_claim_spans(narration_text, raw_claims)
    assert len(spans) == 5

    # Check exact offsets
    assert spans[0].narration_span == (3, 19)
    assert narration_text[spans[0].narration_span[0]:spans[0].narration_span[1]] == "November 9, 1989"

    assert spans[1].narration_span == (21, 38)
    assert narration_text[spans[1].narration_span[0]:spans[1].narration_span[1]] == "Gunter Schabowski"

    assert spans[2].narration_span == (115, 130)
    assert narration_text[spans[2].narration_span[0]:spans[2].narration_span[1]] == "twenty thousand"

    assert spans[3].narration_span == (156, 173)
    assert narration_text[spans[3].narration_span[0]:spans[3].narration_span[1]] == "Bornholmer Straße"

    # Non-existent falls back gracefully
    assert spans[4].narration_span == (0, len("Non-existent phrase"))


def test_fact_verification_gate_draft_mode():
    """Draft mode proceeds with warnings regardless of contradicted or uncertain claims."""
    report = FactVerificationReport(
        topic="Test Topic",
        narration_text="Test script.",
        claims=[
            FactualClaim("c1", "Claim 1", ClaimType.EVENT),
            FactualClaim("c2", "Claim 2", ClaimType.DATE),
            FactualClaim("c3", "Claim 3", ClaimType.NUMBER),
        ],
        verifications=[
            ClaimVerification("c1", VerificationStatus.VERIFIED, 0.95),
            ClaimVerification("c2", VerificationStatus.UNCERTAIN, 0.50, note="Search thin"),
            ClaimVerification("c3", VerificationStatus.CONTRADICTED, 0.90, note="Refuted by records"),
        ],
        total_claims=3,
        verified_count=1,
        uncertain_count=1,
        contradicted_count=1,
    )

    passed, warnings = evaluate_fact_verification_gate(report, mode="draft")
    assert passed is True
    assert len(warnings) == 2
    assert any("CONTRADICTED" in w for w in warnings)
    assert any("UNCERTAIN" in w for w in warnings)


def test_fact_verification_gate_final_mode_all_verified():
    """Final mode passes cleanly when all claims are VERIFIED."""
    report = FactVerificationReport(
        topic="Test Topic",
        narration_text="Test script.",
        claims=[
            FactualClaim("c1", "Claim 1", ClaimType.EVENT),
            FactualClaim("c2", "Claim 2", ClaimType.DATE),
        ],
        verifications=[
            ClaimVerification("c1", VerificationStatus.VERIFIED, 0.95),
            ClaimVerification("c2", VerificationStatus.VERIFIED, 0.90),
        ],
        total_claims=2,
        verified_count=2,
    )

    passed, warnings = evaluate_fact_verification_gate(report, mode="final")
    assert passed is True
    assert len(warnings) == 0


def test_fact_verification_gate_final_mode_contradicted_blocks():
    """Final mode blocks loudly when any claim is CONTRADICTED."""
    report = FactVerificationReport(
        topic="Test Topic",
        narration_text="Test script.",
        claims=[
            FactualClaim("c1", "Claim 1", ClaimType.EVENT),
            FactualClaim("c2", "Claim 2 (false)", ClaimType.DATE),
        ],
        verifications=[
            ClaimVerification("c1", VerificationStatus.VERIFIED, 0.95),
            ClaimVerification("c2", VerificationStatus.CONTRADICTED, 0.99, note="Wrong year"),
        ],
        total_claims=2,
        verified_count=1,
        contradicted_count=1,
    )

    passed, warnings = evaluate_fact_verification_gate(report, mode="final", allow_uncertain=True)
    assert passed is False
    assert any("FAILED in final mode: 1 contradicted claim(s)" in w for w in warnings)


def test_fact_verification_gate_final_mode_uncertain_blocks_by_default():
    """Final mode blocks when any claim is UNCERTAIN unless overridden."""
    report = FactVerificationReport(
        topic="Test Topic",
        narration_text="Test script.",
        claims=[
            FactualClaim("c1", "Claim 1", ClaimType.EVENT),
            FactualClaim("c2", "Claim 2 (unclear)", ClaimType.NUMBER),
        ],
        verifications=[
            ClaimVerification("c1", VerificationStatus.VERIFIED, 0.95),
            ClaimVerification("c2", VerificationStatus.UNCERTAIN, 0.40, note="No citation found"),
        ],
        total_claims=2,
        verified_count=1,
        uncertain_count=1,
    )

    # Without override -> FAILS
    passed, warnings = evaluate_fact_verification_gate(report, mode="final", allow_uncertain=False)
    assert passed is False
    assert any("FAILED in final mode: 1 uncertain claim(s)" in w for w in warnings)

    # With override -> PASSES with warnings
    passed_ov, warnings_ov = evaluate_fact_verification_gate(report, mode="final", allow_uncertain=True)
    assert passed_ov is True
    assert any("UNCERTAIN claim [c2]" in w for w in warnings_ov)


def test_mock_gemini_grounding_metadata_parsing():
    """Verify GeminiWebSearchFactVerifier parses groundingMetadata and camelCase googleSearch payload."""
    verifier = GeminiWebSearchFactVerifier(api_key="mock-key")

    mock_gemini_response = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps({
                                "verifications": [
                                    {
                                        "claim_id": "c1",
                                        "status": "VERIFIED",
                                        "confidence": 0.95,
                                        "source_urls": ["https://en.wikipedia.org/wiki/Berlin_Wall"],
                                        "note": "Corroborated by historical sources.",
                                    },
                                    {
                                        "claim_id": "c2",
                                        "status": "CONTRADICTED",
                                        "confidence": 0.90,
                                        "source_urls": [],
                                        "note": "Wall fell in 1989, not 1999.",
                                    }
                                ]
                            })
                        }
                    ]
                },
                "groundingMetadata": {
                    "groundingChunks": [
                        {"web": {"uri": "https://history.state.gov/milestones/1989-1992/fall-of-berlin-wall", "title": "State Dept"}}
                    ]
                }
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_gemini_response).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    claims = [
        FactualClaim("c1", "Berlin Wall fell in 1989", ClaimType.DATE),
        FactualClaim("c2", "Berlin Wall fell in 1999", ClaimType.DATE),
    ]
    narration = Narration(text="Berlin Wall narration.")

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        verifs = verifier.verify("Berlin Wall", narration, claims)

        assert len(verifs) == 2
        assert verifs[0].status == VerificationStatus.VERIFIED
        # Checked that groundingMetadata source URLs were aggregated
        assert "https://history.state.gov/milestones/1989-1992/fall-of-berlin-wall" in verifs[0].source_urls
        assert verifs[1].status == VerificationStatus.CONTRADICTED

        # Verify request used camelCase googleSearch
        called_req = mock_urlopen.call_args[0][0]
        req_body = json.loads(called_req.data.decode("utf-8"))
        assert "googleSearch" in req_body["tools"][0]


def test_narration_intake_service_mock_flow(tmp_path):
    """Verify complete end-to-end NarrationIntakeService orchestration with mock providers."""
    # Register mock providers
    class MockWriter:
        provider_id = "mock_writer"
        def write(self, topic, target_duration_sec=None, language="en"):
            narr = Narration(text="A historic event occurred on November 9, 1989.", language=language)
            claims = [FactualClaim("c1", "November 9, 1989", ClaimType.DATE, narration_span=(26, 42))]
            return narr, claims

    class MockVerifier:
        provider_id = "mock_verifier"
        def verify(self, topic, narration, claims):
            return [
                ClaimVerification("c1", VerificationStatus.VERIFIED, 0.95, ["https://example.com/berlin"], "Verified.")
            ]

    with patch("videotool.pipeline.narration_intake.build_narration_writer", return_value=MockWriter()), \
         patch("videotool.pipeline.narration_intake.build_fact_verifier", return_value=MockVerifier()):

        out_narr = tmp_path / "narration.json"
        out_rep = tmp_path / "fact_verification_report.json"

        service = NarrationIntakeService(
            writer_provider_name="mock_writer",
            verifier_provider_name="mock_verifier",
            mode="final",
        )
        narration, report = service.process(
            topic="Berlin Wall",
            target_duration_sec=30.0,
            out_narration_path=out_narr,
            out_report_path=out_rep,
        )

        assert narration.text == "A historic event occurred on November 9, 1989."
        assert report.total_claims == 1
        assert report.verified_count == 1
        assert report.passed_gate is True

        assert out_narr.is_file()
        assert out_rep.is_file()

        # Test failure on contradicted in final mode
        class ContradictedVerifier:
            provider_id = "contra_verifier"
            def verify(self, topic, narration, claims):
                return [ClaimVerification("c1", VerificationStatus.CONTRADICTED, 0.99, note="Refuted")]

        with patch("videotool.pipeline.narration_intake.build_fact_verifier", return_value=ContradictedVerifier()):
            with pytest.raises(FactVerificationGateError):
                service.process(
                    topic="Berlin Wall",
                    out_narration_path=out_narr,
                    out_report_path=out_rep,
                )
