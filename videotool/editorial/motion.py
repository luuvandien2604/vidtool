"""Anchor-first motion scheduling with deterministic fallback and constraints."""
from __future__ import annotations

from videotool.domain.composition import LayerType, VisualComposition
from videotool.domain.motion import (CompositionMotionPlan, EventKind,
                                     MotionEvent, MotionPlan,
                                     TransitionCategory)
from videotool.domain.semantic_beat import SemanticBeat
from videotool.domain.timing import SemanticAnchor, TimingBinding
from videotool.editorial.timing import EditorialTimingPolicy

from .transitions import plan_transitions


def _event_id(composition_id: str, layer_id: str, kind: EventKind) -> str:
    return f"event:{composition_id}:{layer_id}:{kind.value.lower()}"


def _high_salience(layer) -> bool:
    return (layer.role in {"hero", "support", "map", "document", "chart"}
            or layer.type in {LayerType.IMAGE, LayerType.DOCUMENT,
                              LayerType.MAP, LayerType.CHART})


def _dependency_layers(comp: VisualComposition, layer) -> list[str]:
    if not (layer.role == "connector"
            or layer.type in {LayerType.ARROW, LayerType.LINE}):
        return []
    endpoints = []
    for relationship in comp.relationships:
        endpoints.extend([relationship.from_layer, relationship.to_layer])
    endpoints = [item for item in dict.fromkeys(endpoints)
                 if item != layer.id and comp.layer_by_id(item)]
    if endpoints and comp.visual_family == "causal_network":
        return endpoints
    prerequisites = [candidate.id for candidate in comp.layers
                     if candidate.id != layer.id
                     and (candidate.type in {LayerType.MAP, LayerType.DOCUMENT}
                          or candidate.role in {"hero", "map", "document"})]
    prerequisite_layers = [comp.layer_by_id(layer_id)
                           for layer_id in prerequisites]
    if prerequisite_layers and layer.z_index <= min(
            candidate.z_index for candidate in prerequisite_layers
            if candidate is not None):
        return []  # foundational axis/line exists before the content nodes
    return prerequisites[:2]


def _resolve_collisions(entries: list[dict], beat: SemanticBeat,
                        policy: EditorialTimingPolicy) -> None:
    high = sorted((item for item in entries if item["high"]),
                  key=lambda item: (item["start"], item["layer"].z_index,
                                    item["layer"].id))
    prior: list[float] = []
    for item in high:
        original_start = item["start"]
        start = original_start
        while len([value for value in prior
                   if start - policy.collision_window_sec < value <= start]) \
                >= policy.max_high_salience_entrances:
            start += policy.collision_stagger_sec
        item["start"] = min(start, item["latest_start"])
        if item["start"] > original_start + 1e-6:
            item["reason"] += (" Deterministically staggered to satisfy the "
                               "high-salience concurrency limit.")
        prior.append(item["start"])


def build_motion_plan(episode_id: str, beats: list[SemanticBeat],
                      compositions: list[VisualComposition],
                      anchors: list[SemanticAnchor] | None = None,
                      bindings: list[TimingBinding] | None = None,
                      policy: EditorialTimingPolicy | None = None) -> MotionPlan:
    """Schedule semantic bindings first; ``enter_at`` is fallback only."""
    policy = policy or EditorialTimingPolicy()
    anchors = anchors or []
    bindings = bindings or []
    anchor_by_id = {anchor.anchor_id: anchor for anchor in anchors}
    binding_by_layer = {(binding.composition_id, binding.layer_id): binding
                        for binding in bindings}
    beat_by_id = {beat.beat_id: beat for beat in beats}
    transitions = plan_transitions(beats)
    trans_in_by_beat = {transition.to_beat: transition
                        for transition in transitions}

    plans: list[CompositionMotionPlan] = []
    for comp in compositions:
        beat = beat_by_id[comp.beat_id]
        entries: list[dict] = []
        for layer in comp.layers:
            binding = binding_by_layer.get((comp.composition_id, layer.id))
            anchor = (anchor_by_id.get(binding.anchor_id)
                      if binding and binding.anchor_id else None)
            if layer.type == LayerType.TEXTURE:
                start = beat.start_sec
                source, confidence, anchor_id = "beat_fallback", 0.3, None
                reason = "Background texture is present from beat start."
            elif binding is not None:
                start = binding.start_sec - policy.lead_for(
                    anchor.anchor_type if anchor else None)
                source, confidence = binding.source, binding.confidence
                anchor_id, reason = binding.anchor_id, binding.reason
                if anchor is not None:
                    lead_ms = int(round(policy.lead_for(anchor.anchor_type) * 1000))
                    reason += f" Scheduled with {lead_ms}ms editorial lead."
            else:
                start = beat.start_sec + beat.duration_sec * max(
                    0.0, min(1.0, layer.enter_at))
                source, confidence, anchor_id = "beat_fallback", 0.3, None
                reason = "No timing binding; retained deterministic layer fallback."
            exit_start = max(beat.start_sec,
                             beat.end_sec - policy.exit_duration_sec)
            min_visibility = min(policy.minimum_visibility_for(layer),
                                 max(0.0, exit_start - beat.start_sec))
            latest_start = max(beat.start_sec, exit_start - min_visibility)
            entries.append({
                "layer": layer, "binding": binding, "anchor": anchor,
                "start": round(max(beat.start_sec,
                                   min(start, latest_start)), 3),
                "latest_start": round(latest_start, 3),
                "exit_start": round(exit_start, 3), "source": source,
                "confidence": confidence, "anchor_id": anchor_id,
                "reason": reason, "high": _high_salience(layer),
                "dependencies": _dependency_layers(comp, layer)})

        _resolve_collisions(entries, beat, policy)
        by_layer = {item["layer"].id: item for item in entries}
        # A connector/highlight cannot precede the completed entrance of its
        # prerequisite map/document/node.
        for item in sorted(entries, key=lambda value: (value["start"],
                                                       value["layer"].id)):
            prerequisite_ends = []
            for layer_id in item["dependencies"]:
                prerequisite = by_layer.get(layer_id)
                if prerequisite:
                    prerequisite_ends.append(
                        prerequisite["start"] + policy.entrance_duration_sec)
            if prerequisite_ends:
                prior_start = item["start"]
                item["start"] = round(min(item["exit_start"],
                                          max(item["start"],
                                              max(prerequisite_ends))), 3)
                if item["start"] > prior_start + 1e-6:
                    item["reason"] += (" Delayed until prerequisite layer "
                                       "entrance completed.")

        events: list[MotionEvent] = []
        for item in entries:
            layer = item["layer"]
            entrance_id = _event_id(comp.composition_id, layer.id,
                                    EventKind.ENTRANCE)
            depends = [_event_id(comp.composition_id, layer_id,
                                 EventKind.ENTRANCE)
                       for layer_id in item["dependencies"]]
            entrance_end = min(item["exit_start"],
                               item["start"] + policy.entrance_duration_sec)
            events.append(MotionEvent(
                layer_id=layer.id, kind=EventKind.ENTRANCE,
                style=layer.entrance.value, start_sec=round(item["start"], 3),
                end_sec=round(max(
                    item["start"] + policy.minimum_event_duration_sec,
                    entrance_end), 3),
                semantic_reason=item["reason"], event_id=entrance_id,
                anchor_id=item["anchor_id"], timing_source=item["source"],
                timing_confidence=item["confidence"], depends_on=depends))
            if layer.emphasis:
                emphasis_start = max(entrance_end,
                                     item["binding"].start_sec
                                     if item["binding"] else item["start"])
                emphasis_start = min(emphasis_start, item["exit_start"])
                events.append(MotionEvent(
                    layer_id=layer.id, kind=EventKind.EMPHASIS,
                    style=layer.emphasis.value,
                    start_sec=round(emphasis_start, 3),
                    end_sec=round(min(beat.end_sec,
                                      emphasis_start
                                      + policy.emphasis_duration_sec), 3),
                    semantic_reason=("Emphasis lands on the bound narration "
                                     "anchor after the layer is visible."),
                    event_id=_event_id(comp.composition_id, layer.id,
                                       EventKind.EMPHASIS),
                    anchor_id=item["anchor_id"], timing_source=item["source"],
                    timing_confidence=item["confidence"],
                    depends_on=[entrance_id]))
            events.append(MotionEvent(
                layer_id=layer.id, kind=EventKind.EXIT,
                style=layer.exit.value, start_sec=item["exit_start"],
                end_sec=round(beat.end_sec, 3),
                semantic_reason="Element clears as the narrated thought resolves.",
                event_id=_event_id(comp.composition_id, layer.id, EventKind.EXIT),
                timing_source="beat_boundary", timing_confidence=1.0,
                depends_on=[entrance_id]))

        events.sort(key=lambda event: (event.start_sec, event.layer_id,
                                       event.kind.value))
        incoming = trans_in_by_beat.get(comp.beat_id)
        camera = "stable"
        camera_reason = ("Documentary restraint: camera fixed; motion comes "
                         "from editorial elements.")
        if incoming and incoming.category == TransitionCategory.ZOOM_TO_DETAIL:
            camera = "slow_push"
            camera_reason = ("Incoming transition isolates detail; a single "
                             "slow push serves it.")
        plans.append(CompositionMotionPlan(
            composition_id=comp.composition_id, beat_id=comp.beat_id,
            camera_behavior=camera, camera_reason=camera_reason, events=events))

    return MotionPlan(episode_id=episode_id, plans=plans,
                      transitions=transitions)
