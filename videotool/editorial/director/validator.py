"""Strict validation layer for AI Editorial Director proposals (Phase 3A).

Enforces catalog integrity, semantic compatibility, and repetition constraints.
An AI proposal is deemed valid if and only if at least one candidate strategy
passes all domain validation gates.
"""
from __future__ import annotations

from typing import Any

from videotool.domain.strategy import StrategyDefinition
from videotool.editorial.composition import FAMILIES
from videotool.editorial.director.models import (
    EditorialDirectorRequest,
    EditorialIntent,
    ValidationResult,
)
from videotool.editorial.strategies import STRATEGY_CATALOG


def validate_editorial_intent(
    intent: EditorialIntent,
    req: EditorialDirectorRequest,
    catalog: dict[str, StrategyDefinition] | None = None,
    families: dict[str, Any] | None = None,
) -> ValidationResult:
    """Validate an AI proposal against deterministic domain rules."""
    catalog_map = catalog if catalog is not None else STRATEGY_CATALOG
    family_map = families if families is not None else FAMILIES

    accepted_strategies: list[str] = []
    rejected_strategies: list[tuple[str, str]] = []
    reasons: list[str] = []

    streak_family, streak_len = req.family_streak

    # 1. Validate proposed candidate strategies
    for sid in intent.candidate_strategies:
        s_def = catalog_map.get(sid)
        if s_def is None:
            rejected_strategies.append((sid, f"Strategy '{sid}' not in strategy catalog"))
            continue

        if s_def.visual_family not in family_map:
            rejected_strategies.append((sid, f"Visual family '{s_def.visual_family}' unknown"))
            continue

        # Check family streak constraint (e.g. max 2 consecutive beats)
        if streak_len >= 2 and s_def.visual_family == streak_family:
            rejected_strategies.append(
                (sid, f"Visual family '{streak_family}' is at consecutive streak limit ({streak_len})")
            )
            continue

        accepted_strategies.append(sid)

    # 2. Filter visual families
    valid_preferred = [f for f in intent.preferred_visual_families if f in family_map]
    valid_avoid = [f for f in intent.avoid_visual_families if f in family_map]

    # 3. Determine overall validity
    is_valid = len(accepted_strategies) > 0
    if not is_valid:
        reasons.append("No viable candidate strategies remaining after catalog and constraint filtering.")
        if rejected_strategies:
            reasons.extend([f"{sid}: {r}" for sid, r in rejected_strategies])

    return ValidationResult(
        is_valid=is_valid,
        accepted_strategies=accepted_strategies,
        rejected_strategies=rejected_strategies,
        rejection_reasons=reasons,
    )
