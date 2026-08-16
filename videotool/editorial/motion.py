"""Motion planning: composition layers -> absolute, semantically-reasoned events.

Every motion event answers "why is this moving now" (spec sections 12-13).
Camera stays stable; a semantic slow push is allowed only when the incoming
transition is ZOOM_TO_DETAIL.
"""
from __future__ import annotations

from videotool.domain.composition import VisualComposition
from videotool.domain.motion import (CompositionMotionPlan, EventKind,
                                     MotionEvent, MotionPlan,
                                     TransitionCategory, TransitionPlan)
from videotool.domain.semantic_beat import SemanticBeat

from .transitions import plan_transitions

EXIT_WINDOW = 0.12  # fraction of beat reserved for exits
EMPHASIS_AT = 0.75  # fraction of beat where emphasis lands


def build_motion_plan(episode_id: str, beats: list[SemanticBeat],
                      compositions: list[VisualComposition]) -> MotionPlan:
    beat_by_id = {b.beat_id: b for b in beats}
    transitions = plan_transitions(beats)
    trans_in_by_beat = {t.to_beat: t for t in transitions}

    plans: list[CompositionMotionPlan] = []
    for comp in compositions:
        beat = beat_by_id[comp.beat_id]
        start, dur = beat.start_sec, beat.duration_sec
        events: list[MotionEvent] = []

        for layer in comp.layers:
            if layer.type.value == "TEXTURE":
                events.append(MotionEvent(
                    layer_id=layer.id, kind=EventKind.ENTRANCE,
                    style=layer.entrance.value, start_sec=round(start, 3),
                    end_sec=round(start + min(0.8, dur * 0.5), 3),
                    semantic_reason=layer.reason))
                continue
            enter_start = start + layer.enter_at * dur
            enter_end = enter_start + min(0.7, dur * 0.25)
            events.append(MotionEvent(
                layer_id=layer.id, kind=EventKind.ENTRANCE,
                style=layer.entrance.value,
                start_sec=round(enter_start, 3),
                end_sec=round(min(enter_end, start + dur), 3),
                semantic_reason=layer.reason))
            if layer.emphasis:
                emph = start + EMPHASIS_AT * dur
                events.append(MotionEvent(
                    layer_id=layer.id, kind=EventKind.EMPHASIS,
                    style=layer.emphasis.value,
                    start_sec=round(emph, 3),
                    end_sec=round(min(emph + 0.5, start + dur), 3),
                    semantic_reason="Controlled scale emphasis at the beat's focal moment"))
            events.append(MotionEvent(
                layer_id=layer.id, kind=EventKind.EXIT,
                style=layer.exit.value,
                start_sec=round(start + dur * (1 - EXIT_WINDOW), 3),
                end_sec=round(start + dur, 3),
                semantic_reason="Element clears as the thought resolves"))

        incoming = trans_in_by_beat.get(comp.beat_id)
        camera = "stable"
        camera_reason = "Documentary restraint: camera fixed; motion comes from editorial elements."
        if incoming and incoming.category == TransitionCategory.ZOOM_TO_DETAIL:
            camera = "slow_push"
            camera_reason = "Incoming transition isolates detail; a single slow push serves it."

        plans.append(CompositionMotionPlan(
            composition_id=comp.composition_id, beat_id=comp.beat_id,
            camera_behavior=camera, camera_reason=camera_reason, events=events))

    return MotionPlan(episode_id=episode_id, plans=plans, transitions=transitions)
