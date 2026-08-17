"""Phase 2B word-aligned visual timing and pipeline regressions."""
from dataclasses import replace

import pytest

from videotool.artifacts import ArtifactStore
from videotool.domain.composition import (CompositionLayer, LayerType,
                                          MotionStyle, Relationship,
                                          VisualComposition)
from videotool.domain.motion import EventKind
from videotool.domain.narration import Narration, WordTiming, synthetic_word_timings
from videotool.domain.semantic_beat import SemanticBeat, SemanticFunction
from videotool.domain.timing import (AnchorType, NarrationTiming,
                                     SemanticAnchor, TimingBinding)
from videotool.editorial.motion import build_motion_plan
from videotool.editorial.timeline import build_subtitles
from videotool.editorial.timing import (EditorialTimingPolicy,
                                         annotate_composition_semantics,
                                         build_timing_bindings,
                                         extract_semantic_anchors,
                                         validate_anchors,
                                         validate_narration_timing,
                                         validate_timing_bindings)
from videotool.fixtures.berlin_wall import load_episode
from videotool.pipeline.fingerprints import STAGE_VERSIONS, stable_hash
from videotool.pipeline.runner import EpisodeInput, PipelineRunner
from videotool.providers.timing import DeterministicNarrationTimingProvider


def timing_for(text):
    narration = Narration(text=text, words=synthetic_word_timings(text))
    return DeterministicNarrationTimingProvider().align(narration)


def one_beat(text, **kwargs):
    timing = timing_for(text)
    defaults = dict(
        beat_id="beat-x", start_sec=timing.words[0].start_sec,
        end_sec=timing.words[-1].end_sec, narration_text=text,
        word_start=0, word_end=len(timing.words),
        semantic_function=SemanticFunction.ESTABLISHING_CONTEXT,
        visual_intent="follow the narrated concept")
    defaults.update(kwargs)
    return timing, SemanticBeat(**defaults)


def composition(beat, layers):
    return VisualComposition(
        composition_id="comp-x", beat_id=beat.beat_id,
        visual_family="geographic_map", strategy="test",
        layers=layers, duration_sec=beat.duration_sec,
        focus_target=layers[0].id if layers else "")


def test_word_timing_validation_rejects_overlap_negative_and_confidence():
    words = (WordTiming(0, "one", -0.1, 0.2),
             WordTiming(1, "two", 0.1, 0.4, 1.2))
    timing = NarrationTiming(words, 0.4, "provided", "fixture", 1)
    errors = validate_narration_timing(timing)
    assert any("invalid range" in error for error in errors)
    assert any("overlaps" in error for error in errors)
    assert any("confidence" in error for error in errors)


def test_phrase_span_uses_first_and_last_word_boundaries():
    timing, beat = one_beat("People crossed East Germany overnight.",
                            locations=["East Germany"])
    anchor = next(anchor for anchor in extract_semantic_anchors(timing, [beat])
                  if anchor.anchor_type == AnchorType.LOCATION_MENTION)
    assert anchor.word_end - anchor.word_start == 2
    assert anchor.start_sec == timing.words[2].start_sec
    assert anchor.end_sec == timing.words[3].end_sec


def test_unicode_canonical_entity_matches_surname_alias():
    timing, beat = one_beat("Schabowski answered the question.",
                            entities=["Günter Schabowski"])
    anchor = next(anchor for anchor in extract_semantic_anchors(timing, [beat])
                  if anchor.anchor_type == AnchorType.ENTITY_MENTION)
    assert anchor.text == "Günter Schabowski"
    assert anchor.resolution_source == "alias_match"
    assert anchor.start_sec == timing.words[0].start_sec


@pytest.mark.parametrize(("text", "beat_fields", "anchor_type", "term"), [
    ("Reactor Four failed.", {"entities": ["Reactor Four"]},
     AnchorType.ENTITY_MENTION, "Reactor Four"),
    ("Families left Pripyat.", {"locations": ["Pripyat"]},
     AnchorType.LOCATION_MENTION, "Pripyat"),
    ("The alarm sounded in 1989.", {"dates": ["1989"]},
     AnchorType.DATE_MENTION, "1989"),
    ("Thousands fled overnight.", {}, AnchorType.NUMBER_MENTION, "Thousands"),
    ("The evacuation began.", {}, AnchorType.EVENT_MENTION, "evacuation"),
])
def test_explicit_semantic_anchor_types(text, beat_fields, anchor_type, term):
    timing, beat = one_beat(text, **beat_fields)
    anchors = extract_semantic_anchors(timing, [beat])
    anchor = next(anchor for anchor in anchors
                  if anchor.anchor_type == anchor_type
                  and term.lower() in anchor.text.lower())
    assert anchor.resolution_source == "exact_phrase"
    assert anchor.confidence == 1.0


def test_relationship_anchor_uses_marked_semantic_fallback():
    timing, beat = one_beat(
        "Pressure rose throughout the night.", relationships=["cause"],
        semantic_function=SemanticFunction.CAUSAL_EXPLANATION)
    anchor = next(anchor for anchor in extract_semantic_anchors(timing, [beat])
                  if anchor.anchor_type == AnchorType.CAUSE)
    assert anchor.resolution_source == "semantic_fallback"
    assert anchor.confidence == 0.5


def test_missing_entity_phrase_is_not_pretended_exact():
    timing, beat = one_beat("The pressure had been building for months.",
                            entities=["the administration"])
    anchor = next(anchor for anchor in extract_semantic_anchors(timing, [beat])
                  if anchor.anchor_type == AnchorType.ENTITY_MENTION)
    assert anchor.resolution_source == "semantic_fallback"
    assert anchor.confidence < 1.0


def test_punctuation_does_not_hide_emphasis_anchor():
    timing, beat = one_beat("The rule applied immediately.")
    anchor = next(anchor for anchor in extract_semantic_anchors(timing, [beat])
                  if anchor.anchor_type == AnchorType.EMPHASIS)
    assert anchor.text == "immediately."
    assert anchor.resolution_source == "exact_phrase"


def test_anchor_validator_rejects_meta_consistent_out_of_beat_range():
    timing, beat = one_beat("A date appeared in 1989.", dates=["1989"])
    anchors = extract_semantic_anchors(timing, [beat])
    anchors[0].start_sec = beat.end_sec + 1
    assert validate_anchors(anchors, [beat], timing)


def test_semantic_layer_annotation_and_bindings_cover_every_layer():
    timing, beat = one_beat("People crossed through Hungary into Austria.",
                            locations=["Hungary", "Austria"],
                            semantic_function=SemanticFunction.GEOGRAPHIC_MOVEMENT)
    layers = [
        CompositionLayer("map", LayerType.MAP, 0, 0, 1, .8, role="map",
                         entrance=MotionStyle.MASK_REVEAL),
        CompositionLayer("route-a", LayerType.ARROW, .1, .2, .5, .02,
                         role="connector", entrance=MotionStyle.ROUTE_DRAW),
        CompositionLayer("route-b", LayerType.ARROW, .3, .4, .5, .02,
                         role="connector", entrance=MotionStyle.ROUTE_DRAW),
    ]
    comp = composition(beat, layers)
    annotate_composition_semantics(comp, beat)
    assert layers[1].semantic_refs == ["Hungary"]
    assert layers[2].semantic_refs == ["Austria"]
    anchors = extract_semantic_anchors(timing, [beat])
    bindings = build_timing_bindings([beat], [comp], anchors,
                                      EditorialTimingPolicy())
    assert not validate_timing_bindings(bindings, [beat], [comp], anchors)
    assert len(bindings) == len(layers)
    destination = next(binding for binding in bindings
                       if binding.layer_id == "route-b")
    destination_anchor = next(anchor for anchor in anchors
                              if anchor.anchor_id == destination.anchor_id)
    assert destination_anchor.text == "Austria"


def test_lead_time_clamps_to_beat_start():
    timing, beat = one_beat("Pripyat waited.", locations=["Pripyat"])
    layer = CompositionLayer("map", LayerType.MAP, 0, 0, 1, .8, role="map")
    comp = composition(beat, [layer])
    annotate_composition_semantics(comp, beat)
    anchors = extract_semantic_anchors(timing, [beat])
    bindings = build_timing_bindings([beat], [comp], anchors,
                                      EditorialTimingPolicy())
    motion = build_motion_plan("episode", [beat], [comp], anchors, bindings)
    entrance = next(event for event in motion.plans[0].events
                    if event.kind == EventKind.ENTRANCE)
    assert entrance.start_sec == beat.start_sec


def test_minimum_visibility_is_preserved_for_late_portrait_anchor():
    timing, beat = one_beat("For a long moment the room waited, then Smith spoke.",
                            entities=["Smith"])
    layer = CompositionLayer("portrait", LayerType.IMAGE, .1, .1, .5, .6,
                             role="hero")
    comp = composition(beat, [layer])
    annotate_composition_semantics(comp, beat)
    anchors = extract_semantic_anchors(timing, [beat])
    policy = EditorialTimingPolicy()
    bindings = build_timing_bindings([beat], [comp], anchors, policy)
    motion = build_motion_plan("episode", [beat], [comp], anchors, bindings,
                               policy)
    events = motion.plans[0].events
    entrance = next(event for event in events if event.kind == EventKind.ENTRANCE)
    exit_event = next(event for event in events if event.kind == EventKind.EXIT)
    available = exit_event.start_sec - beat.start_sec
    assert exit_event.start_sec - entrance.start_sec >= \
        min(policy.portrait_min_visibility_sec, available) - 0.001


def test_collision_resolution_staggers_third_high_salience_entrance():
    timing, beat = one_beat("Berlin, Moscow and Washington reacted immediately.",
                            entities=["Berlin", "Moscow", "Washington"])
    layers = [CompositionLayer(f"hero-{index}", LayerType.IMAGE,
                               .05 + index * .3, .1, .25, .5, role="hero",
                               semantic_refs=[name])
              for index, name in enumerate(beat.entities)]
    comp = composition(beat, layers)
    anchors = extract_semantic_anchors(timing, [beat])
    policy = EditorialTimingPolicy()
    # Force a genuine collision to exercise the concurrency policy itself.
    first_anchor = anchors[0]
    bindings = [TimingBinding(
        f"b-{index}", beat.beat_id, comp.composition_id, layer.id,
        layer.semantic_refs, first_anchor.anchor_id, first_anchor.start_sec,
        first_anchor.end_sec, "exact_phrase", 1.0, "collision fixture")
        for index, layer in enumerate(layers)]
    motion = build_motion_plan("episode", [beat], [comp], anchors, bindings,
                               policy)
    starts = sorted(event.start_sec for event in motion.plans[0].events
                    if event.kind == EventKind.ENTRANCE)
    assert starts[0] == starts[1]
    assert starts[2] - starts[0] > policy.collision_window_sec


@pytest.mark.parametrize(("base_type", "dependent_type"), [
    (LayerType.MAP, LayerType.ARROW),
    (LayerType.DOCUMENT, LayerType.LINE),
])
def test_event_dependencies_enforce_base_before_route_or_highlight(
        base_type, dependent_type):
    timing, beat = one_beat("The regulation applied immediately.",
                            objects=["regulation"])
    base = CompositionLayer("base", base_type, .1, .1, .7, .6,
                            z_index=10,
                            role="map" if base_type == LayerType.MAP else "document")
    dependent = CompositionLayer("dependent", dependent_type, .2, .4, .4, .03,
                                 z_index=40, role="connector")
    comp = composition(beat, [base, dependent])
    annotate_composition_semantics(comp, beat)
    anchors = extract_semantic_anchors(timing, [beat])
    bindings = build_timing_bindings([beat], [comp], anchors,
                                      EditorialTimingPolicy())
    motion = build_motion_plan("episode", [beat], [comp], anchors, bindings)
    events = {event.event_id: event for event in motion.plans[0].events}
    dependent_event = next(event for event in events.values()
                           if event.layer_id == "dependent"
                           and event.kind == EventKind.ENTRANCE)
    assert dependent_event.depends_on
    assert all(events[event_id].end_sec <= dependent_event.start_sec
               for event_id in dependent_event.depends_on)


def test_causal_connector_waits_for_relationship_nodes():
    timing, beat = one_beat(
        "Pressure caused the failure.", relationships=["caused"],
        semantic_function=SemanticFunction.CAUSAL_EXPLANATION)
    layers = [CompositionLayer("source", LayerType.LABEL, .1, .2, .2, .1,
                               z_index=20, role="support", text="Pressure"),
              CompositionLayer("effect", LayerType.LABEL, .7, .2, .2, .1,
                               z_index=20, role="hero", text="failure"),
              CompositionLayer("edge", LayerType.ARROW, .3, .25, .4, .02,
                               z_index=15, role="connector")]
    comp = composition(beat, layers)
    comp.visual_family = "causal_network"
    comp.relationships = [Relationship("source", "effect", "points_to")]
    annotate_composition_semantics(comp, beat)
    anchors = extract_semantic_anchors(timing, [beat])
    bindings = build_timing_bindings([beat], [comp], anchors,
                                      EditorialTimingPolicy())
    motion = build_motion_plan("episode", [beat], [comp], anchors, bindings)
    events = {event.event_id: event for event in motion.plans[0].events}
    edge = next(event for event in events.values()
                if event.layer_id == "edge" and event.kind == EventKind.ENTRANCE)
    assert len(edge.depends_on) == 2
    assert all(events[event_id].end_sec <= edge.start_sec
               for event_id in edge.depends_on)


def test_subtitles_share_canonical_word_boundaries():
    timing = timing_for("Southampton faced the Atlantic.")
    subtitles = build_subtitles(timing)
    assert subtitles[0]["start_sec"] == timing.words[0].start_sec
    assert subtitles[-1]["end_sec"] == timing.words[-1].end_sec


@pytest.mark.parametrize(("text", "entities", "locations", "dates", "terms"), [
    ("At 1:23 AM Reactor Four failed near Pripyat and the evacuation began.",
     ["Reactor Four"], ["Pripyat"], ["1:23 AM"],
     ["Reactor Four", "Pripyat", "1:23 AM", "evacuation"]),
    ("At 11:40 PM the Titanic struck an iceberg in the Atlantic after leaving Southampton.",
     ["Titanic"], ["Atlantic", "Southampton"], ["11:40 PM"],
     ["Titanic", "Atlantic", "Southampton", "11:40 PM", "struck"]),
])
def test_topic_generalization_anchor_coverage(text, entities, locations, dates,
                                              terms):
    timing, beat = one_beat(text, entities=entities, locations=locations,
                            dates=dates)
    anchors = extract_semantic_anchors(timing, [beat])
    for term in terms:
        assert any(term.lower() in anchor.text.lower() for anchor in anchors), term


def run_berlin(tmp_path, narration=None):
    data = load_episode()
    if narration is not None:
        data["narration"] = narration
    return PipelineRunner(ArtifactStore(tmp_path / "artifacts"), mode="final").run(
        EpisodeInput(**data))


def test_berlin_explicit_anchor_coverage_bindings_and_determinism(tmp_path):
    first = run_berlin(tmp_path)
    timing_before = first.narration_timing.to_dict()
    anchors_before = [anchor.to_dict() for anchor in first.semantic_anchors]
    bindings_before = [binding.to_dict() for binding in first.timing_bindings]
    exact = {anchor.text.lower() for anchor in first.semantic_anchors
             if anchor.resolution_source in {"exact_phrase", "alias_match"}}
    expected = {"schabowski", "berlin", "hungary", "austria", "1989",
                "regulation", "immediately,", "protests"}
    assert len([term for term in expected
                if any(term in value for value in exact)]) / len(expected) >= .8
    important = {(comp.composition_id, layer.id)
                 for comp in first.compositions for layer in comp.layers
                 if layer.role in {"hero", "support", "connector", "map",
                                   "document", "chart"}}
    bound = {(binding.composition_id, binding.layer_id)
             for binding in first.timing_bindings}
    assert important <= bound
    motion_before = first.motion.to_dict()
    second = run_berlin(tmp_path)
    assert second.narration_timing.to_dict() == timing_before
    assert [anchor.to_dict() for anchor in second.semantic_anchors] == anchors_before
    assert [binding.to_dict() for binding in second.timing_bindings] == bindings_before
    assert second.motion.to_dict() == motion_before
    assert all(second.manifest["stages"][stage]["status"] == "resumed"
               for stage in ("narration_timing", "semantic_anchors",
                             "timing_bindings", "motion_plan"))


def test_word_timing_only_change_keeps_media_and_composition_resumed(tmp_path):
    first = run_berlin(tmp_path)
    words = list(first.narration_timing.words)
    words[10] = replace(words[10], start_sec=words[10].start_sec + 0.01)
    data = load_episode()
    changed = Narration(text=data["narration"].text, words=tuple(words))
    second = run_berlin(tmp_path, changed)
    statuses = {stage: row["status"]
                for stage, row in second.manifest["stages"].items()}
    assert statuses["narration_timing"] == "invalidated"
    assert statuses["semantic_beats"] == "resumed"
    assert statuses["media_assets"] == "resumed"
    assert statuses["visual_compositions"] == "resumed"
    assert statuses["semantic_anchors"] == "invalidated"
    assert statuses["timing_bindings"] == "invalidated"
    assert statuses["motion_plan"] == "invalidated"


def test_global_boundary_retime_reuses_semantics_media_and_geometry(tmp_path):
    first = run_berlin(tmp_path)
    words = tuple(replace(word, start_sec=round(word.start_sec * 1.03, 3),
                          end_sec=round(word.end_sec * 1.03, 3))
                  for word in first.narration_timing.words)
    data = load_episode()
    result = run_berlin(
        tmp_path, Narration(text=data["narration"].text, words=words))
    statuses = {stage: row["status"]
                for stage, row in result.manifest["stages"].items()}
    assert result.ok
    assert statuses["semantic_beats"] == "resumed"
    assert statuses["media_assets"] == "resumed"
    assert statuses["visual_compositions"] == "resumed"
    assert statuses["motion_plan"] == "invalidated"
    assert result.timeline["total_duration_sec"] == words[-1].end_sec


@pytest.mark.parametrize(("stage", "mutate"), [
    ("narration_timing", lambda payload: payload["words"][0].update(start_sec=-1)),
    ("semantic_anchors", lambda payload: payload[0].update(start_sec=9999)),
    ("timing_bindings", lambda payload: payload[0].update(anchor_id="unknown")),
])
def test_meta_consistent_timing_artifact_corruption_invalidates(
        tmp_path, stage, mutate):
    run_berlin(tmp_path)
    store = ArtifactStore(tmp_path / "artifacts")
    episode_id = "berlin_wall_phase1"
    payload = store.load(episode_id, stage)
    mutate(payload)
    store.save(episode_id, stage, payload)
    meta = store.load(episode_id, "stage_meta")
    meta[stage]["output_hash"] = stable_hash(payload)
    store.save(episode_id, "stage_meta", meta)
    result = run_berlin(tmp_path)
    assert result.manifest["stages"][stage]["status"] == "invalidated"
    assert result.ok


def test_timing_stage_version_invalidation_does_not_touch_media(tmp_path):
    run_berlin(tmp_path)
    store = ArtifactStore(tmp_path / "artifacts")
    meta = store.load("berlin_wall_phase1", "stage_meta")
    for stage in ("semantic_anchors", "timing_bindings", "motion_plan"):
        meta[stage]["stage_version"] = STAGE_VERSIONS[stage] - 1
    store.save("berlin_wall_phase1", "stage_meta", meta)
    result = run_berlin(tmp_path)
    statuses = {stage: row["status"]
                for stage, row in result.manifest["stages"].items()}
    assert statuses["media_assets"] == "resumed"
    assert statuses["visual_compositions"] == "resumed"
    assert statuses["semantic_anchors"] == "invalidated"
    assert statuses["timing_bindings"] == "invalidated"
    assert statuses["motion_plan"] == "invalidated"


def test_missing_explicit_timing_uses_marked_deterministic_estimate():
    narration = Narration(text="An old city changed overnight.")
    timing = DeterministicNarrationTimingProvider().align(narration)
    assert timing.words
    assert timing.is_estimated
    assert timing.source == "deterministic_text_estimate"
    assert all(word.confidence == 0.55 for word in timing.words)
    _, beat = one_beat("An old city changed overnight.")
    estimated_beat = replace(beat, word_end=len(timing.words),
                             end_sec=timing.duration_sec,
                             entities=["old city"])
    anchor = next(anchor for anchor in
                  extract_semantic_anchors(timing, [estimated_beat])
                  if anchor.anchor_type == AnchorType.ENTITY_MENTION)
    assert anchor.resolution_source == "estimated_phrase"
    assert anchor.confidence == 0.55


def test_phase2b_production_code_has_no_fixture_topic_leaks():
    from pathlib import Path
    files = [Path("videotool/editorial/timing.py"),
             Path("videotool/editorial/motion.py"),
             Path("videotool/domain/timing.py"),
             Path("videotool/providers/timing.py")]
    forbidden = ("Berlin", "Schabowski", "Hungary", "Austria",
                 "Chernobyl", "Titanic")
    text = "\n".join(path.read_text(encoding="utf-8") for path in files)
    assert not any(term in text for term in forbidden)
