"""Strategy feasibility pass (Phase 1.1, review item 3).

Order of truth: strategy INTENT is planned before media acquisition (novelty
and storytelling are decided on meaning), then this pass re-checks each
selection against the assets that ACTUALLY resolved and switches to the best
feasible candidate when required assets are missing. The plan-of-record for
composition is the adjusted plan, persisted with reasons.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from videotool.domain.assets import MediaAsset
from videotool.domain.semantic_beat import SemanticBeat
from videotool.domain.strategy import SelectionRecord
from videotool.editorial.strategies import STRATEGY_CATALOG

# asset kinds each strategy genuinely needs to deliver its editorial promise.
# strategies absent from this table degrade gracefully without assets.
STRATEGY_ASSET_NEEDS: dict[str, set[str]] = {
    "archival_portrait": {"portrait", "photo"},
    "portrait_plus_document": {"portrait", "photo", "document"},
    "portrait_plus_location": {"portrait", "photo"},
    "portrait_plus_quote": {"portrait", "photo"},
    "full_frame_archival": {"portrait", "photo", "map", "document"},
    "silhouette_to_archive_reveal": {"portrait", "photo"},
    "single_document_focus": {"document"},
    "document_stack": {"document"},
    "document_plus_quote": {"document"},
    "clip_plus_annotation": {"document", "portrait", "photo"},
    "region_map": {"map"},
    "route_map": {"map"},
    "map_plus_archival": {"map", "photo"},
    "migration_flow_map": {"map"},
}

# kinds that can substitute for each other in a pinch
KIND_EQUIV = {"portrait": {"portrait", "photo"}, "photo": {"photo", "portrait"}}
_KIND_EQUIV = KIND_EQUIV


def _kinds_available(assets: list[MediaAsset]) -> set[str]:
    return {a.kind for a in assets if not a.is_placeholder}


def strategy_is_feasible(strategy_id: str, available_kinds: set[str]) -> bool:
    needs = STRATEGY_ASSET_NEEDS.get(strategy_id, set())
    for need in needs:
        options = _KIND_EQUIV.get(need, {need})
        if not options & available_kinds:
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
                         assets: list[MediaAsset],
                         max_family_streak: int = 2) -> FeasibilityResult:
    """Adjust strategy selections to what the acquired media can deliver.

    A switch is only accepted if the resulting family sequence (this beat
    switched + all remaining ORIGINAL selections) still respects the streak
    limit; otherwise the original strategy is kept and its family degrades
    gracefully - the preliminary plan already satisfies the streak, so
    keeping it can never break the constraint.
    """
    assets_by_beat: dict[str, list[MediaAsset]] = {}
    for a in assets:
        if a.requirement_id:
            # requirement ids look like req_<beat_id>_<kind>
            parts = a.requirement_id.split("_")
            beat_id = "_".join(parts[1:3])
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
