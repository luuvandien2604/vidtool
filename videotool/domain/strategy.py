"""Visual strategy selection models (spec section 6, 21).

Multiple candidate strategies per semantic beat; one is selected with an
explainable reason. One semantic function NEVER maps 1:1 to one layout.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class StrategyDefinition:
    strategy_id: str
    visual_family: str
    functions: tuple[str, ...]        # semantic functions this strategy serves well
    storytelling_note: str            # what it communicates editorially
    density_fit: tuple[float, float]  # (min, max) information density fit
    base_storytelling_value: float    # 0..1


@dataclass
class ScoredCandidate:
    strategy_id: str
    visual_family: str
    scores: dict = field(default_factory=dict)  # component scores
    total: float = 0.0
    rejected_reason: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "ScoredCandidate":
        return cls(**d)


@dataclass
class SelectionRecord:
    beat_id: str
    semantic_function: str
    selected_strategy: str
    visual_family: str
    reason: str
    novelty_score: float = 0.0
    rejected_recent_family: str | None = None
    candidates: list[ScoredCandidate] = field(default_factory=list)
    is_fallback: bool = False
    feasibility_note: str = ""

    def to_dict(self) -> dict:
        return {
            "beat_id": self.beat_id,
            "semantic_function": self.semantic_function,
            "selected_strategy": self.selected_strategy,
            "visual_family": self.visual_family,
            "reason": self.reason,
            "novelty_score": self.novelty_score,
            "rejected_recent_family": self.rejected_recent_family,
            "candidates": [c.to_dict() for c in self.candidates],
            "is_fallback": self.is_fallback,
            "feasibility_note": self.feasibility_note,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SelectionRecord":
        return cls(
            beat_id=d["beat_id"],
            semantic_function=d["semantic_function"],
            selected_strategy=d["selected_strategy"],
            visual_family=d["visual_family"],
            reason=d["reason"],
            novelty_score=d.get("novelty_score", 0.0),
            rejected_recent_family=d.get("rejected_recent_family"),
            candidates=[ScoredCandidate.from_dict(c) for c in d.get("candidates", [])],
            is_fallback=d.get("is_fallback", False),
            feasibility_note=d.get("feasibility_note", ""),
        )
