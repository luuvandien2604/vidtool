"""Deterministic fallback intent generator (Phase 3A).

Generates safe, catalog-compliant default editorial intents when an AI provider
is unavailable, times out, or produces an unrecoverably invalid proposal.
"""
from __future__ import annotations

from videotool.editorial.director.models import (
    EditorialDirectorRequest,
    EditorialIntent,
)


def build_fallback_intent(
    req: EditorialDirectorRequest,
    reason: str = "Deterministic fallback intent generated due to AI director unavailability or rejection.",
) -> EditorialIntent:
    """Construct a safe fallback intent from candidate descriptors."""
    streak_fam, streak_len = req.family_streak
    candidate_ids = [
        d.strategy_id for d in req.candidate_descriptors
        if not (streak_len >= 2 and d.visual_family == streak_fam)
    ]
    if not candidate_ids and req.candidate_descriptors:
        candidate_ids = [req.candidate_descriptors[0].strategy_id]

    preferred_families = list({
        d.visual_family for d in req.candidate_descriptors
        if d.strategy_id in candidate_ids
    })

    return EditorialIntent(
        beat_id=req.beat_id,
        story_role=req.semantic_function,
        visual_goal=f"Convey {req.semantic_function.lower()} clearly with established visual pacing.",
        information_priority=list(req.entities[:2] or req.locations[:2] or ["subject"]),
        information_density=req.information_density,
        emotional_goal="neutral_informative",
        candidate_strategies=candidate_ids,
        preferred_visual_families=preferred_families,
        avoid_visual_families=[streak_fam] if streak_len >= 2 else [],
        must_show=list(req.entities[:2]),
        must_not_show=[],
        emphasis=req.entities[0] if req.entities else "",
        reason=reason,
        confidence=0.0,
        is_fallback=True,
    )
