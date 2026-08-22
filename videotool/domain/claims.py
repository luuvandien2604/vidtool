"""Domain models for factual claims and fact verification (Phase 4).

Represents atomic verifiable claims extracted from AI-authored narration scripts,
verification verdicts with web search citations, and comprehensive verification reports.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ClaimType(str, Enum):
    """Category of factual claim."""
    DATE = "DATE"              # specific years, dates, timeframes
    ENTITY = "ENTITY"          # person, place, organization, landmark
    NUMBER = "NUMBER"          # statistic, measurement, quantity
    QUOTE = "QUOTE"            # attributed direct or indirect quote
    EVENT = "EVENT"            # discrete historical occurrence or policy decision


@dataclass(frozen=True)
class FactualClaim:
    """An atomic factual claim extracted verbatim from narration."""
    claim_id: str
    text: str                                # verbatim text from narration
    claim_type: ClaimType
    narration_span: tuple[int, int] = (0, 0) # character offset (start_idx, end_idx) in narration

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "claim_type": self.claim_type.value if isinstance(self.claim_type, ClaimType) else str(self.claim_type),
            "narration_span": list(self.narration_span),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FactualClaim":
        ctype = ClaimType(d["claim_type"]) if isinstance(d["claim_type"], str) else d["claim_type"]
        span = tuple(d.get("narration_span", (0, 0)))
        return cls(
            claim_id=d["claim_id"],
            text=d["text"],
            claim_type=ctype,
            narration_span=(int(span[0]), int(span[1])),
        )


class VerificationStatus(str, Enum):
    """Verdict of fact verification."""
    VERIFIED = "VERIFIED"          # corroborated by reliable search evidence
    UNCERTAIN = "UNCERTAIN"        # ambiguous, conflicting, thin, or missing evidence
    CONTRADICTED = "CONTRADICTED"  # search evidence refutes or disproves the claim


@dataclass(frozen=True)
class ClaimVerification:
    """Verification assessment for a specific factual claim."""
    claim_id: str
    status: VerificationStatus
    confidence: float              # 0.0 to 1.0
    source_urls: list[str] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "claim_id": self.claim_id,
            "status": self.status.value if isinstance(self.status, VerificationStatus) else str(self.status),
            "confidence": round(float(self.confidence), 3),
            "source_urls": list(self.source_urls),
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ClaimVerification":
        status = VerificationStatus(d["status"]) if isinstance(d["status"], str) else d["status"]
        return cls(
            claim_id=d["claim_id"],
            status=status,
            confidence=float(d.get("confidence", 0.0)),
            source_urls=list(d.get("source_urls", [])),
            note=str(d.get("note", "")),
        )


@dataclass
class FactVerificationReport:
    """Complete fact verification report artifact for an episode."""
    topic: str
    narration_text: str
    claims: list[FactualClaim] = field(default_factory=list)
    verifications: list[ClaimVerification] = field(default_factory=list)
    total_claims: int = 0
    verified_count: int = 0
    uncertain_count: int = 0
    contradicted_count: int = 0
    passed_gate: bool = True
    gate_mode: str = "draft"
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "narration_text": self.narration_text,
            "claims": [c.to_dict() for c in self.claims],
            "verifications": [v.to_dict() for v in self.verifications],
            "total_claims": self.total_claims,
            "verified_count": self.verified_count,
            "uncertain_count": self.uncertain_count,
            "contradicted_count": self.contradicted_count,
            "passed_gate": self.passed_gate,
            "gate_mode": self.gate_mode,
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "FactVerificationReport":
        return cls(
            topic=d.get("topic", ""),
            narration_text=d.get("narration_text", ""),
            claims=[FactualClaim.from_dict(c) for c in d.get("claims", [])],
            verifications=[ClaimVerification.from_dict(v) for v in d.get("verifications", [])],
            total_claims=int(d.get("total_claims", 0)),
            verified_count=int(d.get("verified_count", 0)),
            uncertain_count=int(d.get("uncertain_count", 0)),
            contradicted_count=int(d.get("contradicted_count", 0)),
            passed_gate=bool(d.get("passed_gate", True)),
            gate_mode=str(d.get("gate_mode", "draft")),
            warnings=list(d.get("warnings", [])),
        )


__all__ = [
    "ClaimType",
    "FactualClaim",
    "VerificationStatus",
    "ClaimVerification",
    "FactVerificationReport",
]
