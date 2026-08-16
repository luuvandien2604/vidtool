"""Composition orchestration: beats + strategies + assets -> compositions.

For every beat: resolve semantic asset requirements to acquired media, pick
the family for the selected strategy, demand a structurally new signature,
record a history entry. Deterministic given the same inputs.
"""
from __future__ import annotations

from videotool.domain.assets import AssetRequirement, MediaAsset
from videotool.domain.composition import VisualComposition
from videotool.domain.semantic_beat import SemanticBeat
from videotool.domain.strategy import SelectionRecord, StrategyDefinition
from videotool.domain.visual_history import HistoryEntry, VisualHistory

from .base import (CompositionContext, CompositionFamily,
                   compose_with_distinct_signature)
from .archival_subject import FAMILY as ARCHIVAL_SUBJECT
from .document_evidence import FAMILY as DOCUMENT_EVIDENCE
from .geographic_map import FAMILY as GEOGRAPHIC_MAP
from .chronological_timeline import FAMILY as CHRONOLOGICAL_TIMELINE
from .causal_network import FAMILY as CAUSAL_NETWORK
from .full_frame_cinematic import FAMILY as FULL_FRAME_CINEMATIC

FAMILIES: dict[str, CompositionFamily] = {
    f.family_id: f for f in (
        ARCHIVAL_SUBJECT, DOCUMENT_EVIDENCE, GEOGRAPHIC_MAP,
        CHRONOLOGICAL_TIMELINE, CAUSAL_NETWORK, FULL_FRAME_CINEMATIC,
    )
}

# bump when any family's arrangement logic changes (part of stage fingerprints)
FAMILIES_VERSION = 1

__all__ = [
    "FAMILIES", "CompositionContext", "CompositionFamily",
    "compose_beat",
]


def semantic_asset_requirements(beats: list[SemanticBeat]) -> list[AssetRequirement]:
    """Requirements derived from meaning, never 'N images for scene X'.

    Strength: REQUIRED requirements gate final mode (unless the
    plan-of-record strategy no longer needs that kind); PREFERRED gaps the
    planner routes around; OPTIONAL never gates.
    """
    from videotool.domain.assets import OPTIONAL, PREFERRED, REQUIRED
    reqs: list[AssetRequirement] = []
    for beat in beats:
        fn = beat.semantic_function.value
        if fn in ("CHARACTER_INTRODUCTION", "QUOTE") or (beat.entities and fn in ("TURNING_POINT", "CAUSAL_EXPLANATION")):
            who = beat.entities[0] if beat.entities else "subject"
            reqs.append(AssetRequirement(
                requirement_id=f"req_{beat.beat_id}_portrait",
                beat_id=beat.beat_id, kind="portrait",
                strength=REQUIRED if fn == "CHARACTER_INTRODUCTION" else PREFERRED,
                description=f"portrait of {who} in period context",
                entities=[who]))
        if beat.objects or fn in ("EVIDENCE", "QUOTE"):
            obj = beat.objects[0] if beat.objects else "document"
            reqs.append(AssetRequirement(
                requirement_id=f"req_{beat.beat_id}_document",
                beat_id=beat.beat_id, kind="document",
                strength=REQUIRED if fn == "EVIDENCE" else PREFERRED,
                description=f"archival {obj} related to "
                            f"{', '.join(beat.entities[:2]) or beat.narration_text[:40]}",
                entities=beat.entities[:2]))
        if beat.locations or fn in ("LOCATION_INTRODUCTION", "GEOGRAPHIC_MOVEMENT",
                                    "ESTABLISHING_CONTEXT"):
            # only location-meaningful beats request maps: a character intro
            # or a quote must not consume the geography beat's map asset
            if fn in ("LOCATION_INTRODUCTION", "GEOGRAPHIC_MOVEMENT",
                      "ESTABLISHING_CONTEXT") or not beat.entities:
                place = beat.locations[0] if beat.locations else "region"
                reqs.append(AssetRequirement(
                    requirement_id=f"req_{beat.beat_id}_map",
                    beat_id=beat.beat_id, kind="map",
                    strength=REQUIRED if fn in ("LOCATION_INTRODUCTION",
                                                "GEOGRAPHIC_MOVEMENT") else PREFERRED,
                    description=f"period map of {place}",
                    entities=[place]))
        if fn in ("ATMOSPHERE", "HOOK", "CONSEQUENCE", "SUMMARY", "REVEAL",
                  "ESCALATION") or not reqs or reqs[-1].beat_id != beat.beat_id:
            reqs.append(AssetRequirement(
                requirement_id=f"req_{beat.beat_id}_photo",
                beat_id=beat.beat_id, kind="photo",
                strength=OPTIONAL,
                description=(f"archival photograph of "
                             f"{beat.locations[0] if beat.locations else beat.events[0] if beat.events else (beat.entities[0] if beat.entities else 'the subject matter')} "
                             f"{('in ' + beat.dates[0]) if beat.dates else ''}").strip(),
                entities=beat.entities[:2]))
    return reqs


def assets_for_beat(assets: list[MediaAsset], beat_id: str) -> list[MediaAsset]:
    return [a for a in assets if a.requirement_id and
            a.requirement_id.startswith(f"req_{beat_id}_")]


def history_from_compositions(compositions: list[VisualComposition]) -> VisualHistory:
    """Deterministically rebuild the visual history artifact when missing."""
    history = VisualHistory()
    for comp in compositions:
        dominant = next((l.asset_id for l in comp.layers
                         if l.role == "hero" and l.asset_id), None)
        history.record(HistoryEntry(
            beat_id=comp.beat_id,
            visual_family=comp.visual_family,
            strategy=comp.strategy,
            composition_signature=comp.novelty_signature,
            asset_ids=[l.asset_id for l in comp.layers if l.asset_id],
            dominant_asset=dominant,
            transition_in=comp.transition_in,
            camera_behavior="stable",
        ))
    return history


def compose_beat(beat: SemanticBeat, selection: SelectionRecord,
                 strat_def: StrategyDefinition, art_direction,
                 beat_assets: list[MediaAsset], history: VisualHistory,
                 used_signatures: set[str], episode_id: str) -> VisualComposition:
    family = FAMILIES[selection.visual_family]
    ctx = CompositionContext(beat=beat, strategy=strat_def,
                             art_direction=art_direction,
                             assets=beat_assets, history=history,
                             episode_id=episode_id)
    comp = compose_with_distinct_signature(family, ctx, used_signatures)

    dominant = next((l.asset_id for l in comp.layers
                     if l.role == "hero" and l.asset_id), None)
    history.record(HistoryEntry(
        beat_id=beat.beat_id,
        visual_family=comp.visual_family,
        strategy=comp.strategy,
        composition_signature=comp.novelty_signature,
        asset_ids=[l.asset_id for l in comp.layers if l.asset_id],
        dominant_asset=dominant,
        transition_in=comp.transition_in,
        camera_behavior="stable",
        information_density=beat.information_density,
    ))
    used_signatures.add(comp.novelty_signature)
    return comp
