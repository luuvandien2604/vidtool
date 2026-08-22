"""Deterministic mock provider for AI Editorial Director (Phase 3A).

Generates consistent, catalog-aligned editorial proposals without network I/O.
"""
from __future__ import annotations

from videotool.editorial.director.models import (
    EditorialDirectorRequest,
    EditorialIntent,
)


class MockEditorialDirectorProvider:
    """Deterministic mock editorial director provider for testing and offline runs."""
    provider_id: str = "mock"
    model_name: str = "mock-director-v1"

    def generate_intent(self, request: EditorialDirectorRequest) -> EditorialIntent:
        streak_fam, streak_len = request.family_streak
        avoid_fams = [streak_fam] if streak_len >= 2 else []

        # Rank candidates based on semantic priorities
        candidates = [
            d for d in request.candidate_descriptors
            if d.visual_family not in avoid_fams
        ]
        if not candidates and request.candidate_descriptors:
            candidates = list(request.candidate_descriptors)

        preferred_strategies: list[str] = []
        # Prefer entity-matching strategies
        for d in candidates:
            if request.entities and "portrait" in d.strategy_id:
                preferred_strategies.append(d.strategy_id)
            elif request.locations and "map" in d.strategy_id:
                preferred_strategies.append(d.strategy_id)
            elif request.dates and "timeline" in d.strategy_id:
                preferred_strategies.append(d.strategy_id)

        # Fallback to general candidate IDs
        for d in candidates:
            if d.strategy_id not in preferred_strategies:
                preferred_strategies.append(d.strategy_id)

        preferred_families = list({
            d.visual_family for d in candidates
            if d.strategy_id in preferred_strategies
        })

        return EditorialIntent(
            beat_id=request.beat_id,
            story_role=request.semantic_function,
            visual_goal=f"Focus audience attention on {request.semantic_function.lower()} narrative context.",
            information_priority=list(request.entities or request.locations or ["context"]),
            information_density=request.information_density,
            emotional_goal="informative_documentary",
            candidate_strategies=preferred_strategies[:3],
            preferred_visual_families=preferred_families,
            avoid_visual_families=avoid_fams,
            must_show=list(request.entities[:2]),
            must_not_show=[],
            emphasis=request.entities[0] if request.entities else "",
            reason=f"Mock director prioritized {', '.join(preferred_strategies[:2])} for {request.semantic_function}.",
            confidence=0.90,
            is_fallback=False,
        )
