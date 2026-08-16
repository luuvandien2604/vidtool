"""Deterministic validation of every planning artifact (spec sections 26, 29).

AI output (or any planning output) is validated before it may reach the
renderer. Invalid -> repair -> deterministic fallback. Never silently pass
broken plans downstream.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from videotool.domain.assets import MediaAsset
from videotool.domain.composition import LayerType, VisualComposition
from videotool.domain.semantic_beat import SemanticBeat
from videotool.domain.strategy import SelectionRecord

from .composition import FAMILIES
from .composition.base import intersects_safe_zone


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


def validate_beats(beats: list[SemanticBeat], narration_duration: float,
                   report: ValidationReport | None = None) -> ValidationReport:
    report = report or ValidationReport()
    if not beats:
        report.error("semantic beats missing")
        return report
    for i, beat in enumerate(beats):
        if beat.semantic_function is None:
            report.error(f"{beat.beat_id}: missing semantic function")
        if beat.duration_sec <= 0:
            report.error(f"{beat.beat_id}: non-positive duration")
        if beat.duration_sec > 9.0:
            report.warn(f"{beat.beat_id}: duration {beat.duration_sec:.1f}s exceeds 3-8s target")
        if beat.end_sec > narration_duration + 0.01:
            report.error(f"{beat.beat_id}: ends beyond narration ({beat.end_sec}s)")
        if i > 0:
            prev = beats[i - 1]
            gap = beat.start_sec - prev.end_sec
            if gap < -0.001:
                report.error(f"{beat.beat_id}: overlaps previous beat by {-gap:.3f}s")
            if gap > 1.5:
                report.warn(f"{beat.beat_id}: gap of {gap:.3f}s after previous beat")
    return report


def validate_compositions(compositions: list[VisualComposition],
                          beats: list[SemanticBeat],
                          assets: list[MediaAsset],
                          mode: str = "final",
                          max_family_streak: int = 2) -> ValidationReport:
    report = ValidationReport()
    beat_ids = {b.beat_id for b in beats}
    beat_by_id = {b.beat_id: b for b in beats}
    asset_ids = {a.asset_id for a in assets}
    seen_ids: set[str] = set()
    seen_signatures: dict[str, str] = {}

    # ---- completeness: every beat has EXACTLY one composition -------------
    comps_by_beat: dict[str, list[str]] = {}
    for comp in compositions:
        comps_by_beat.setdefault(comp.beat_id, []).append(comp.composition_id)
        if comp.beat_id not in beat_ids:
            report.error(f"{comp.composition_id}: composition for unknown beat "
                         f"{comp.beat_id}")
    for beat in beats:
        owned = comps_by_beat.get(beat.beat_id, [])
        if not owned:
            report.error(f"{beat.beat_id}: missing composition (completeness gate)")
        elif len(owned) > 1:
            report.error(f"{beat.beat_id}: {len(owned)} compositions "
                         f"({', '.join(owned)}); exactly one required")

    for comp in compositions:
        if comp.composition_id in seen_ids:
            report.error(f"duplicate composition_id {comp.composition_id}")
        seen_ids.add(comp.composition_id)
        if comp.novelty_signature in seen_signatures:
            report.error(
                f"{comp.composition_id}: exact composition signature reused "
                f"(first used by {seen_signatures[comp.novelty_signature]})")
        else:
            seen_signatures[comp.novelty_signature] = comp.composition_id
        if comp.duration_sec <= 0:
            report.error(f"{comp.composition_id}: non-positive duration")
        beat = beat_by_id.get(comp.beat_id)
        if beat is not None and abs(comp.duration_sec - beat.duration_sec) > 0.01:
            report.error(f"{comp.composition_id}: duration {comp.duration_sec}s "
                         f"does not match beat {beat.beat_id} "
                         f"({beat.duration_sec}s)")
        if comp.visual_family not in FAMILIES:
            report.error(f"{comp.composition_id}: unknown family {comp.visual_family}")
        for layer in comp.layers:
            for dim_name in ("x", "y", "width", "height"):
                v = getattr(layer, dim_name)
                if not (0.0 - 1e-6 <= v <= 1.0 + 1e-6):
                    report.error(f"{comp.composition_id}/{layer.id}: {dim_name}={v} outside [0,1]")
            if intersects_safe_zone(layer):
                report.warn(f"{comp.composition_id}/{layer.id}: critical layer overlaps subtitle safe zone")
            if layer.asset_id and layer.asset_id not in asset_ids:
                report.error(f"{comp.composition_id}/{layer.id}: unbound asset reference {layer.asset_id}")
            if layer.asset_id and layer.asset_id.startswith("placeholder:") and mode == "final":
                report.error(f"{comp.composition_id}/{layer.id}: placeholder asset in final mode")
        if not comp.focus_target:
            report.warn(f"{comp.composition_id}: no focus target")

    # family streak threshold across consecutive beats
    fam_by_beat = {c.beat_id: c.visual_family for c in compositions}
    ordered = [fam_by_beat[b.beat_id] for b in beats if b.beat_id in fam_by_beat]
    streak = 1
    for prev, cur in zip(ordered, ordered[1:]):
        streak = streak + 1 if prev == cur else 1
        if streak > max_family_streak:
            report.error(f"family '{cur}' exceeds {max_family_streak} consecutive beats")
    return report


def validate_strategy_plan(records: list[SelectionRecord],
                           beats: list[SemanticBeat]) -> ValidationReport:
    report = ValidationReport()
    by_beat = {r.beat_id: r for r in records}
    for beat in beats:
        rec = by_beat.get(beat.beat_id)
        if rec is None:
            report.error(f"{beat.beat_id}: no selected strategy")
            continue
        if not rec.selected_strategy:
            report.error(f"{beat.beat_id}: empty selected strategy")
        if not rec.reason or len(rec.reason) < 20:
            report.error(f"{beat.beat_id}: missing selection reason (explainability)")
        if rec.visual_family not in FAMILIES:
            report.error(f"{beat.beat_id}: unknown family {rec.visual_family}")
    return report


# ---- deterministic fallbacks (spec section 22) ---------------------------

# hero positions cycle so multiple fallbacks keep distinct signatures
_FALLBACK_POSITIONS = [(0.08, 0.20), (0.50, 0.20), (0.08, 0.46), (0.50, 0.46)]


def deterministic_fallback_composition(beat: SemanticBeat, index: int,
                                       assets: list[MediaAsset],
                                       family: str | None = None) -> VisualComposition:
    """Semantic-function-appropriate fallback; still a real composition.

    `family` should be the beat's planned family so a fallback never
    disturbs the family sequence (streak constraints stay satisfied).
    """
    fn = beat.semantic_function.value
    from videotool.domain.composition import CompositionLayer, MotionStyle
    cid = f"comp_{beat.beat_id}"
    comp = VisualComposition(
        composition_id=cid, beat_id=beat.beat_id,
        visual_family=family or "archival_subject", strategy="fallback",
        duration_sec=beat.duration_sec, is_fallback=True,
        composition_reason=f"deterministic fallback for {fn}")
    hero_text = beat.entities[0] if beat.entities else (
        beat.locations[0] if beat.locations else beat.narration_text[:60])
    hx, hy = _FALLBACK_POSITIONS[index % len(_FALLBACK_POSITIONS)]
    comp.layers.append(CompositionLayer(
        id=f"{cid}_hero", type=LayerType.TEXT, x=hx, y=hy, width=0.4,
        height=0.24, z_index=10, role="hero", text=str(hero_text),
        entrance=MotionStyle.TYPE_ON, exit=MotionStyle.DISSOLVE, enter_at=0.0,
        reason="Fallback identity block"))
    comp.layers.append(CompositionLayer(
        id=f"{cid}_meta", type=LayerType.LABEL, x=hx, y=hy + 0.3, width=0.4,
        height=0.1, z_index=20, role="caption",
        text=" · ".join(filter(None, [fn, beat.dates[0] if beat.dates else "",
                                      beat.locations[0] if beat.locations else ""])),
        entrance=MotionStyle.UNDERLINE_REVEAL, exit=MotionStyle.SLIDE_OUT,
        enter_at=0.4, reason="Fallback metadata strip"))
    comp.focus_target = f"{cid}_hero"
    comp.reading_order = [f"{cid}_hero", f"{cid}_meta"]
    from videotool.domain.visual_history import derive_signature
    comp.novelty_signature = derive_signature(comp)
    return comp


def fallback_art_direction(episode_id: str, subject: str):
    """Deterministic default identity when the generated one is unusable."""
    from videotool.domain.art_direction import EpisodeArtDirection
    return EpisodeArtDirection(
        episode_id=episode_id, subject=subject,
        visual_motifs=["subject-related archival material"],
        archival_language=["archival photography", "document texture"],
        geometry=["asymmetric frames", "annotative overlays"],
        typography_character=["editorial", "condensed", "institutional"],
        accent={"primary": "ink_black", "warning": "mark_red",
                "neutral": "paper_white"},
        motion_character=["tactile", "restrained", "physical", "documentary"],
        forbidden_patterns=["glossy_ui", "generic_slideshow", "constant_zoom",
                            "random_camera_motion",
                            "repeated_template_composition"],
        concept_cluster="generic",
        generation_reason="deterministic fallback: generated art direction "
                          "failed validation",
    )


def repair_beat(beat: SemanticBeat) -> SemanticBeat:
    """Schema-level repair for invalid AI beat analysis (spec section 29)."""
    from videotool.domain.semantic_beat import SemanticFunction
    if beat.semantic_function is None or beat.semantic_function not in SemanticFunction:
        beat.semantic_function = SemanticFunction.ESTABLISHING_CONTEXT
        beat.analysis_reason += " [repaired: default function assigned]"
    beat.information_density = min(1.0, max(0.0, beat.information_density))
    return beat


# ---- Phase 1.2 gates ------------------------------------------------------

def validate_media_completeness(beats, requirements, assets, records,
                                mode: str) -> ValidationReport:
    """Media Completeness Gate (plan-of-record semantics).

    A REQUIRED requirement that resolved to nothing fails final mode UNLESS
    the plan-of-record strategy for that beat no longer needs that kind
    (the planner routed around the gap). Draft mode never gates.
    """
    from videotool.domain.assets import REQUIRED
    from videotool.editorial.feasibility import (KIND_EQUIV, STRATEGY_ASSET_NEEDS,
                                                 policy_needs_kind)
    report = ValidationReport()
    if mode != "final":
        placeholders = sum(1 for a in assets if getattr(a, "is_placeholder", False))
        report.warn(f"draft mode: {placeholders} placeholder asset(s) allowed")
        return report

    resolved_kinds: dict[str, set[str]] = {}
    req_by_id = {r.requirement_id: r for r in requirements}
    for asset in assets:
        req = req_by_id.get(asset.requirement_id)
        if req is not None and not asset.is_placeholder:
            resolved_kinds.setdefault(req.beat_id, set()).add(asset.kind)
    rec_by_beat = {r.beat_id: r for r in records}

    for req in requirements:
        if req.strength != REQUIRED:
            continue
        kinds = resolved_kinds.get(req.beat_id, set())
        if req.kind in kinds:
            continue
        options = KIND_EQUIV.get(req.kind, {req.kind})
        if options & kinds:
            continue  # satisfied by an equivalent kind
        rec = rec_by_beat.get(req.beat_id)
        needs_it = bool(rec) and policy_needs_kind(rec.selected_strategy, req.kind)
        if not needs_it:
            continue  # planner routed around the missing kind entirely
        report.error(
            f"{req.beat_id}: REQUIRED {req.kind} asset unresolved "
            f"('{req.description}') and plan-of-record strategy "
            f"'{rec.selected_strategy if rec else '?'}' still needs it "
            f"(Media Completeness Gate)")
    return report


def validate_motion(motion, beats: list[SemanticBeat],
                    compositions: list[VisualComposition]) -> ValidationReport:
    """One motion plan per composition; events bound to layers and beats."""
    report = ValidationReport()
    beat_by_id = {b.beat_id: b for b in beats}
    beat_index = {b.beat_id: i for i, b in enumerate(beats)}
    comp_by_id = {c.composition_id: c for c in compositions}

    plan_comp_ids = [p.composition_id for p in motion.plans]
    for comp in compositions:
        if comp.composition_id not in plan_comp_ids:
            report.error(f"{comp.composition_id}: no motion plan (one required)")
    seen_plans: set[str] = set()
    for plan in motion.plans:
        if plan.composition_id in seen_plans:
            report.error(f"duplicate motion plan for {plan.composition_id}")
        seen_plans.add(plan.composition_id)
        comp = comp_by_id.get(plan.composition_id)
        if comp is None:
            report.error(f"motion plan for unknown composition {plan.composition_id}")
            continue
        if plan.beat_id != comp.beat_id:
            report.error(f"{plan.composition_id}: motion beat {plan.beat_id} "
                         f"!= composition beat {comp.beat_id}")
        beat = beat_by_id.get(plan.beat_id)
        if beat is None:
            report.error(f"{plan.composition_id}: motion references unknown beat")
            continue
        layer_ids = {l.id for l in comp.layers}
        for ev in plan.events:
            if ev.layer_id not in layer_ids:
                report.error(f"{plan.composition_id}: event references unknown "
                             f"layer {ev.layer_id}")
            if ev.end_sec < ev.start_sec:
                report.error(f"{plan.composition_id}: event {ev.layer_id} ends "
                             f"before it starts")
            if ev.start_sec < beat.start_sec - 1e-6:
                report.error(f"{plan.composition_id}: event {ev.layer_id} starts "
                             f"before beat window")
            if ev.end_sec > beat.end_sec + 1e-6:
                report.error(f"{plan.composition_id}: event {ev.layer_id} ends "
                             f"after beat window")
    for t in motion.transitions:
        if t.from_beat not in beat_index or t.to_beat not in beat_index:
            report.error(f"transition references unknown beat "
                         f"{t.from_beat}->{t.to_beat}")
            continue
        if beat_index[t.to_beat] != beat_index[t.from_beat] + 1:
            report.error(f"transition {t.from_beat}->{t.to_beat} is not between "
                         f"adjacent beats")
        if t.end_sec < t.start_sec:
            report.error(f"transition {t.from_beat}->{t.to_beat} has negative duration")
    return report


def validate_timeline(timeline: dict, beats: list[SemanticBeat],
                      compositions: list[VisualComposition],
                      mode: str) -> ValidationReport:
    """Timeline shape: one segment per beat, bounded timing, subtitles sane."""
    report = ValidationReport()
    comp_ids = {c.composition_id for c in compositions}
    total = float(timeline.get("total_duration_sec", 0.0))

    segments = timeline.get("segments", [])
    if len(segments) != len(beats):
        report.error(f"timeline has {len(segments)} segments for {len(beats)} beats")
    for seg, beat in zip(segments, beats):
        if seg.get("beat_id") != beat.beat_id:
            report.error(f"timeline segment order mismatch at {beat.beat_id}")
        if mode == "final" and not seg.get("composition_id"):
            report.error(f"timeline segment {beat.beat_id} has no composition "
                         f"(final mode)")
        if seg.get("composition_id") and seg["composition_id"] not in comp_ids:
            report.error(f"timeline segment {beat.beat_id} references unknown "
                         f"composition {seg['composition_id']}")
        start, end = seg.get("start_sec", -1), seg.get("end_sec", -1)
        if start < 0 or end <= start:
            report.error(f"timeline segment {beat.beat_id}: invalid timing "
                         f"{start}..{end}")
        if end > total + 1e-6:
            report.error(f"timeline segment {beat.beat_id} exceeds total duration")

    for sub in timeline.get("subtitles", []):
        start, end = sub.get("start_sec", -1), sub.get("end_sec", -1)
        if start < 0 or end <= start:
            report.error(f"subtitle '{sub.get('text', '')[:20]}': invalid timing")
        if end > total + 1e-6:
            report.error(f"subtitle '{sub.get('text', '')[:20]}' exceeds narration "
                         f"duration")
    if not segments and beats:
        report.error("timeline has no segments")
    return report
