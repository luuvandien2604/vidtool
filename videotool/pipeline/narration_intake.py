"""Narration Intake and Fact Verification Gate orchestration (Phase 4).

Connects Topic -> NarrationWriterProvider -> FactVerificationProvider -> Fact Gate,
producing validated Narration scripts and comprehensive FactVerificationReport artifacts.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from videotool.domain.claims import (FactVerificationReport,
                                     VerificationStatus)
from videotool.domain.narration import Narration
from videotool.providers.fact_verification import build_fact_verifier
from videotool.providers.narration_writer import build_narration_writer

logger = logging.getLogger(__name__)


class FactVerificationGateError(RuntimeError):
    """Raised when fact verification gate fails in final/strict mode."""
    pass


def evaluate_fact_verification_gate(
    report: FactVerificationReport,
    mode: str = "draft",
    allow_uncertain: bool = False,
) -> tuple[bool, list[str]]:
    """Evaluate whether fact verification report passes safety gate.

    Rules:
    - draft mode: Always passes. Generates warnings for any CONTRADICTED or UNCERTAIN claims.
    - final mode:
      - Any CONTRADICTED claim -> FAILS.
      - Any UNCERTAIN claim without `allow_uncertain` -> FAILS.
      - UNCERTAIN claims with `allow_uncertain=True` -> PASSES with warnings.
    """
    warnings: list[str] = []
    contradicted = [v for v in report.verifications if v.status == VerificationStatus.CONTRADICTED]
    uncertain = [v for v in report.verifications if v.status == VerificationStatus.UNCERTAIN]

    # Collect descriptive warnings
    for v in contradicted:
        c = next((claim for claim in report.claims if claim.claim_id == v.claim_id), None)
        claim_text = f' ("{c.text}")' if c else ""
        warnings.append(f"CONTRADICTED claim [{v.claim_id}]{claim_text}: {v.note}")

    for v in uncertain:
        c = next((claim for claim in report.claims if claim.claim_id == v.claim_id), None)
        claim_text = f' ("{c.text}")' if c else ""
        warnings.append(f"UNCERTAIN claim [{v.claim_id}]{claim_text}: {v.note}")

    if mode == "draft":
        return True, warnings

    # Final mode evaluation
    if contradicted:
        return False, [
            f"Fact Verification Gate FAILED in final mode: {len(contradicted)} contradicted claim(s) found.",
            *warnings,
        ]

    if uncertain and not allow_uncertain:
        return False, [
            f"Fact Verification Gate FAILED in final mode: {len(uncertain)} uncertain claim(s) found "
            "(use --allow-uncertain-claims to proceed).",
            *warnings,
        ]

    return True, warnings


class NarrationIntakeService:
    """Service to orchestrate AI narration writing, fact verification, and gate check."""

    def __init__(
        self,
        writer_provider_name: str = "gemini",
        verifier_provider_name: str = "gemini",
        mode: str = "draft",
        allow_uncertain_claims: bool = False,
        writer_model: str | None = None,
        verifier_model: str | None = None,
    ):
        self.writer_provider_name = writer_provider_name
        self.verifier_provider_name = verifier_provider_name
        self.mode = mode
        self.allow_uncertain_claims = allow_uncertain_claims
        self.writer_model = writer_model
        self.verifier_model = verifier_model

    def process(
        self,
        topic: str,
        target_duration_sec: float | None = None,
        language: str = "en",
        out_narration_path: str | Path | None = None,
        out_report_path: str | Path | None = None,
    ) -> tuple[Narration, FactVerificationReport]:
        """Generate narration, extract claims, verify against web search, evaluate gate, save artifacts."""
        # 1. Write narration & extract claims
        writer_kwargs = {"model": self.writer_model} if self.writer_model else {}
        writer = build_narration_writer(self.writer_provider_name, **writer_kwargs)
        narration, claims = writer.write(
            topic=topic,
            target_duration_sec=target_duration_sec,
            language=language,
        )

        # 2. Fact Verification
        verifier_kwargs = {"model": self.verifier_model} if self.verifier_model else {}
        verifier = build_fact_verifier(self.verifier_provider_name, **verifier_kwargs)
        verifications = verifier.verify(
            topic=topic,
            narration=narration,
            claims=claims,
        )

        # 3. Compile report
        verified_count = sum(1 for v in verifications if v.status == VerificationStatus.VERIFIED)
        uncertain_count = sum(1 for v in verifications if v.status == VerificationStatus.UNCERTAIN)
        contradicted_count = sum(1 for v in verifications if v.status == VerificationStatus.CONTRADICTED)

        report = FactVerificationReport(
            topic=topic,
            narration_text=narration.text,
            claims=claims,
            verifications=verifications,
            total_claims=len(claims),
            verified_count=verified_count,
            uncertain_count=uncertain_count,
            contradicted_count=contradicted_count,
            gate_mode=self.mode,
        )

        # 4. Evaluate Gate
        passed, warnings = evaluate_fact_verification_gate(
            report=report,
            mode=self.mode,
            allow_uncertain=self.allow_uncertain_claims,
        )
        report.passed_gate = passed
        report.warnings = warnings

        # 5. Persist artifacts
        if out_narration_path:
            p = Path(out_narration_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(narration.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

        if out_report_path:
            p = Path(out_report_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

        # 6. Gate Enforcement
        if not passed:
            err_msg = "\n".join(warnings)
            raise FactVerificationGateError(f"Fact Verification Gate blocked publication:\n{err_msg}")

        return narration, report


__all__ = [
    "FactVerificationGateError",
    "evaluate_fact_verification_gate",
    "NarrationIntakeService",
]
