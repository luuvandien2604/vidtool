"""Strategy feasibility pass (Phase 1.1, hardened in Phase 1.2.1).

Order of truth: strategy INTENT is planned before media acquisition (novelty
and storytelling are decided on meaning), then this pass re-checks each
selection against the assets that ACTUALLY resolved and switches to the best
feasible candidate when required assets are missing. The plan-of-record for
composition is the adjusted plan, persisted with reasons.

Phase 1.2.1: asset needs use an all_of/any_of POLICY, not a set (a set
silently meant AND - e.g. a strategy promising "one strong archival frame"
was declared infeasible unless portrait+photo+map+document ALL resolved).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from videotool.domain.assets import AssetRequirement, MediaAsset
from videotool.domain.semantic_beat import SemanticBeat
from videotool.domain.strategy import SelectionRecord
from videotool.editorial.strategies import STRATEGY_CATALOG


@dataclass(frozen=True)
class StrategyAssetPolicy:
    """What a strategy genuinely needs to deliver its editorial promise.

    all_of: every kind must resolve (kind equivalence applies).
    any_of: at least one must resolve. Empty policy = degrades gracefully.
    """
    all_of: tuple[str, ...] = ()
    any_of: tuple[str, ...] = ()

    def declares(self) -> bool:
        return bool(self.all_of or self.any_of)


# asset policies per strategy; strategies absent from this table degrade
# gracefully without assets.
STRATEGY_ASSET_NEEDS: dict[str, StrategyAssetPolicy] = {
    "archival_portrait": StrategyAssetPolicy(any_of=("portrait", "photo")),
    "portrait_plus_document": StrategyAssetPolicy(all_of=("document",),
                                                  any_of=("portrait", "photo")),
    "portrait_plus_location": StrategyAssetPolicy(any_of=("portrait", "photo")),
    "portrait_plus_quote": StrategyAssetPolicy(any_of=("portrait", "photo")),
    "full_frame_archival": StrategyAssetPolicy(any_of=("photo", "portrait",
                                                       "document", "map")),
    "silhouette_to_archive_reveal": StrategyAssetPolicy(any_of=("portrait", "photo")),
    "single_document_focus": StrategyAssetPolicy(all_of=("document",)),
    "document_stack": StrategyAssetPolicy(all_of=("document",)),
    "document_plus_quote": StrategyAssetPolicy(all_of=("document",)),
    "clip_plus_annotation": StrategyAssetPolicy(any_of=("document", "photo",
                                                        "portrait")),
    "region_map": StrategyAssetPolicy(all_of=("map",)),
    "route_map": StrategyAssetPolicy(all_of=("map",)),
    "map_plus_archival": StrategyAssetPolicy(all_of=("map",),
                                              any_of=("photo", "portrait")),
    "migration_flow_map": StrategyAssetPolicy(all_of=("map",)),
    "paper_collage_opener": StrategyAssetPolicy(any_of=("photo", "portrait", "map", "document")),
    "editorial_collage_quote": StrategyAssetPolicy(any_of=("photo", "portrait", "document")),
}

# kinds that can substitute for each other in a pinch
KIND_EQUIV = {"portrait": {"portrait", "photo"}, "photo": {"photo", "portrait"}}


def _kinds_available(assets: list[MediaAsset]) -> set[str]:
    return {a.kind for a in assets if not a.is_placeholder}


def _satisfied(kind: str, available_kinds: set[str]) -> bool:
    options = KIND_EQUIV.get(kind, {kind})
    return bool(options & available_kinds)


def policy_needs_kind(strategy_id: str, kind: str) -> bool:
    """True when the strategy's declared promise includes this kind."""
    policy = STRATEGY_ASSET_NEEDS.get(strategy_id)
    if policy is None:
        return False
    return kind in policy.all_of or kind in policy.any_of


def strategy_is_feasible(strategy_id: str, available_kinds: set[str]) -> bool:
    policy = STRATEGY_ASSET_NEEDS.get(strategy_id)
    if policy is None or not policy.declares():
        return True
    if not all(_satisfied(k, available_kinds) for k in policy.all_of):
        return False
    if policy.any_of and not any(_satisfied(k, available_kinds)
                                 for k in policy.any_of):
        return False
    return True


@dataclass
class FeasibilityResult:
    records: list[SelectionRecord] = field(default_factory=list)
    adjustments: list[dict] = field(default_factory=list)


def _streak_safe(families: list[str], max_streak: int) -> bool:
    streak = 1
    for prev, cur in zip(families, families[1:]):
        streak = streak + 1 if prev == cur else 1
        if streak > max_streak:
            return False
    return True


def run_feasibility_pass(records: list[SelectionRecord],
                         beats: list[SemanticBeat],
                         requirements: list[AssetRequirement],
                         assets: list[MediaAsset],
                         max_family_streak: int = 2) -> FeasibilityResult:
    """Adjust strategy selections to what the acquired media can deliver.

    A switch is only accepted if the resulting family sequence (this beat
    switched + all remaining ORIGINAL selections) still respects the streak
    limit; otherwise the original strategy is kept and its family degrades
    gracefully - the preliminary plan already satisfies the streak, so
    keeping it can never break the constraint.

    Beat grouping uses the requirements' own beat_id (never parsed from the
    requirement id - ids are opaque).
    """
    beat_of_requirement = {r.requirement_id: r.beat_id for r in requirements}
    assets_by_beat: dict[str, list[MediaAsset]] = {}
    for a in assets:
        beat_id = beat_of_requirement.get(a.requirement_id) if a.requirement_id else None
        if beat_id:
            assets_by_beat.setdefault(beat_id, []).append(a)

    original_families = [r.visual_family for r in records]
    adjusted: list[SelectionRecord] = []
    adjustments: list[dict] = []

    def switch_safe(index: int, family: str) -> bool:
        """A switch must keep the WHOLE sequence legal: beats already fixed,
        the switched family, and every remaining original selection."""
        seq = ([a.visual_family for a in adjusted] + [family] +
               original_families[index + 1:])
        return _streak_safe(seq, max_family_streak)

    for i, rec in enumerate(records):
        kinds = _kinds_available(assets_by_beat.get(rec.beat_id, []))
        original_feasible = strategy_is_feasible(rec.selected_strategy, kinds)

        if original_feasible:
            # keeping the original is always streak-legal (the preliminary
            # plan satisfied it and every accepted switch was checked against
            # exactly this continuation)
            chosen = rec
        else:
            chosen = None
            for cand in sorted(rec.candidates, key=lambda c: -c.total):
                if not strategy_is_feasible(cand.strategy_id, kinds):
                    continue
                if cand.strategy_id == rec.selected_strategy:
                    chosen = rec
                    break
                if not switch_safe(i, cand.visual_family):
                    continue
                chosen = SelectionRecord(
                    beat_id=rec.beat_id,
                    semantic_function=rec.semantic_function,
                    selected_strategy=cand.strategy_id,
                    visual_family=cand.visual_family,
                    reason=(rec.reason +
                            f" [feasibility] switched from '{rec.selected_strategy}' "
                            f"to '{cand.strategy_id}': required assets missing "
                            f"(available kinds: {sorted(kinds) or 'none'})."),
                    novelty_score=rec.novelty_score,
                    rejected_recent_family=rec.rejected_recent_family,
                    candidates=rec.candidates,
                    feasibility_note=(
                        f"switched: {rec.selected_strategy} -> {cand.strategy_id} "
                        f"(missing assets)"),
                )
                break
            if chosen is None:
                # nothing feasible (or every switch would break the streak):
                # keep the intent and let the family degrade gracefully
                chosen = rec
                chosen.feasibility_note = (
                    f"degraded: no candidate fully feasible "
                    f"(available kinds: {sorted(kinds) or 'none'})")

        if chosen is not rec or chosen.feasibility_note:
            adjustments.append({
                "beat_id": rec.beat_id,
                "from": rec.selected_strategy,
                "to": chosen.selected_strategy,
                "reason": chosen.feasibility_note or "streak guard",
            })
        adjusted.append(chosen)

    return FeasibilityResult(records=adjusted, adjustments=adjustments)
