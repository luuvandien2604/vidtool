"""Phase 1.2: Artifact Integrity & Completeness Gate tests.

Covers the three reproduced production failures plus the cleanup items:
1. valid-JSON corruption can never silently resume (output hash + stage
   validator + integrity-checked resume chain)
2. composition completeness (12 beats can never be final-ok with 11 comps)
3. plan-of-record media completeness (REQUIRED assets gate final mode)
4. motion_plan / timeline validators
5. single source of truth for mode
6. complete fallback coverage (missing records, family exceptions)
7. single FAMILIES_VERSION definition
"""
import dataclasses
import json

import pytest

from videotool.artifacts import ArtifactStore
from videotool.domain.composition import VisualComposition
from videotool.domain.motion import (CompositionMotionPlan, EventKind,
                                     MotionEvent, MotionPlan,
                                     TransitionCategory, TransitionPlan)
from videotool.domain.semantic_beat import SemanticBeat, SemanticFunction
from videotool.domain.strategy import SelectionRecord
from videotool.editorial import validation
from videotool.editorial.composition import FAMILIES
from videotool.fixtures.berlin_wall import load_episode
from videotool.pipeline.fingerprints import stable_hash
from videotool.pipeline.runner import EpisodeInput, PipelineRunner


def make_runner(tmp_path, mode="final", **kw):
    return PipelineRunner(ArtifactStore(tmp_path / "artifacts"), mode=mode, **kw)


def run_ep(tmp_path, data=None, **kw):
    data = data or load_episode()
    return make_runner(tmp_path, **kw).run(EpisodeInput(**data))


def artifact_path(tmp_path, name):
    return ArtifactStore(tmp_path / "artifacts").path_for("berlin_wall_phase1", name)


def load_json(tmp_path, name):
    with open(artifact_path(tmp_path, name)) as f:
        return json.load(f)


def save_json(tmp_path, name, payload):
    with open(artifact_path(tmp_path, name), "w") as f:
        json.dump(payload, f, indent=2)


def fix_output_hash(tmp_path, name):
    """Simulate a fully meta-consistent tamper: refresh the output hash."""
    store_meta_path = artifact_path(tmp_path, "stage_meta")
    with open(store_meta_path) as f:
        meta = json.load(f)
    with open(artifact_path(tmp_path, name)) as f:
        payload = json.load(f)
    meta[name]["output_hash"] = stable_hash(payload)
    with open(store_meta_path, "w") as f:
        json.dump(meta, f, indent=2)


def statuses(res):
    return {s: v["status"] for s, v in res.manifest["stages"].items()}


# ---- 1. resumed artifact integrity -----------------------------------------

def test_valid_json_corruption_art_direction_recomputes(tmp_path):
    """Review repro #1: motifs=[], accent={} must not silently resume."""
    run_ep(tmp_path)
    ad = load_json(tmp_path, "episode_art_direction")
    ad["visual_motifs"] = []
    ad["accent"] = {}
    save_json(tmp_path, "episode_art_direction", ad)

    res2 = run_ep(tmp_path)
    assert statuses(res2)["episode_art_direction"] == "invalidated"
    assert res2.art_direction.visual_motifs            # repaired content
    assert res2.art_direction.accent.get("primary")
    assert res2.ok


def test_valid_json_corruption_strategy_plan_never_crashes(tmp_path):
    """Review repro #2: empty selected_strategy must not KeyError the run."""
    run_ep(tmp_path)
    plan = load_json(tmp_path, "visual_strategy_plan")
    plan[0]["selected_strategy"] = ""
    plan[0]["visual_family"] = ""
    plan[0]["reason"] = ""
    save_json(tmp_path, "visual_strategy_plan", plan)

    res2 = run_ep(tmp_path)  # must not raise
    assert statuses(res2)["visual_strategy_plan"] == "invalidated"
    assert res2.preliminary_strategy_plan[0].selected_strategy
    assert res2.ok


def test_meta_consistent_corruption_caught_by_stage_validator(tmp_path):
    """Even a tamperer who fixes the output hash gets caught by the
    per-stage semantic validator on resume."""
    run_ep(tmp_path)
    ad = load_json(tmp_path, "episode_art_direction")
    ad["visual_motifs"] = []
    save_json(tmp_path, "episode_art_direction", ad)
    fix_output_hash(tmp_path, "episode_art_direction")

    res2 = run_ep(tmp_path)
    assert statuses(res2)["episode_art_direction"] == "invalidated"
    assert res2.art_direction.visual_motifs
    assert res2.ok


def test_output_hash_recorded_for_every_stage(tmp_path):
    res = run_ep(tmp_path)
    meta = load_json(tmp_path, "stage_meta")
    for stage in res.manifest["stages"]:
        entry = meta[stage]
        assert set(entry) == {"input_fingerprint", "output_hash", "stage_version"}
        assert len(entry["output_hash"]) == 16


# ---- 2. composition completeness -------------------------------------------

def test_missing_composition_in_artifact_recomputes(tmp_path):
    """Delete one composition from valid JSON -> integrity check recomputes."""
    run_ep(tmp_path)
    comps = load_json(tmp_path, "visual_compositions")
    assert len(comps) == 12
    save_json(tmp_path, "visual_compositions", comps[:11])

    res2 = run_ep(tmp_path)
    assert statuses(res2)["visual_compositions"] == "invalidated"
    assert len(res2.compositions) == 12
    assert res2.ok


def test_twelve_beats_eleven_compositions_never_final_ok():
    """Even if all integrity layers were bypassed, the completeness gate
    refuses 11 compositions for 12 beats."""
    beats = [make_beat(i) for i in range(1, 13)]
    comps = [make_comp(b) for b in beats[:11]]
    report = validation.validate_compositions(comps, beats, [], mode="final")
    assert not report.ok
    assert any("missing composition" in e for e in report.errors)


def test_duplicate_composition_per_beat_is_error():
    beats = [make_beat(1)]
    a = make_comp(beats[0])
    b = make_comp(beats[0])
    b.composition_id = "comp_other"
    b.novelty_signature = "sig_other"
    report = validation.validate_compositions([a, b], beats, [])
    assert any("exactly one required" in e for e in report.errors)


def test_unknown_beat_composition_is_error():
    beat = make_beat(1)
    comp = make_comp(beat)
    comp.beat_id = "beat_9999"
    report = validation.validate_compositions([comp], [beat], [])
    assert any("unknown beat" in e for e in report.errors)


def test_composition_duration_must_match_beat():
    beat = make_beat(1)
    comp = make_comp(beat)
    comp.duration_sec = beat.duration_sec + 2.0
    report = validation.validate_compositions([comp], [beat], [])
    assert any("does not match beat" in e for e in report.errors)


def test_crafted_consistent_missing_composition_still_caught(tmp_path):
    """Remove a composition AND fix the output hash: the stage's semantic
    validator (completeness) must refuse and recompute."""
    run_ep(tmp_path)
    comps = load_json(tmp_path, "visual_compositions")
    save_json(tmp_path, "visual_compositions", comps[:11])
    fix_output_hash(tmp_path, "visual_compositions")

    res2 = run_ep(tmp_path)
    assert statuses(res2)["visual_compositions"] == "invalidated"
    assert len(res2.compositions) == 12
    assert res2.ok


# ---- 3. media completeness gate ----------------------------------------------

def test_final_empty_catalog_fails_media_gate(tmp_path):
    data = load_episode()
    data["catalog"] = []
    res = run_ep(tmp_path, data=data, mode="final")
    assert not res.ok
    gate = res.validation["media_completeness"]
    assert not gate["ok"]
    assert any("Media Completeness Gate" in e for e in gate["errors"])
    # the failing beats are the REQUIRED map/portrait beats
    assert any("beat_0002" in e or "beat_0003" in e for e in gate["errors"])


def test_draft_empty_catalog_remains_usable(tmp_path):
    data = load_episode()
    data["catalog"] = []
    res = run_ep(tmp_path, data=data, mode="draft")
    assert res.ok
    assert any(a.is_placeholder for a in res.assets)


def test_fixture_media_gate_passes_and_uses_strengths(berlin_run):
    res = berlin_run["result"]
    assert res.validation["media_completeness"]["ok"]
    strengths = {r.strength for r in res.requirements}
    assert strengths <= {"REQUIRED", "PREFERRED", "OPTIONAL"}
    assert any(r.strength == "REQUIRED" for r in res.requirements)
    # REQUIRED requirements all resolved in the fixture
    from videotool.domain.assets import REQUIRED
    resolved = {a.requirement_id for a in res.assets if not a.is_placeholder}
    for req in res.requirements:
        if req.strength == REQUIRED:
            assert req.requirement_id in resolved, req.description


def test_gate_waived_when_planner_routes_around_missing_media(tmp_path):
    """beat_0007 (EVIDENCE, REQUIRED document) switches to a no-media
    strategy when documents are missing -> gate waived for it, and since
    every other REQUIRED asset resolves, the run stays final-ok."""
    data = load_episode()
    data["catalog"] = [c for c in data["catalog"] if c["kind"] != "document"]
    res = run_ep(tmp_path, data=data, mode="final")
    assert res.ok, res.validation
    gate_errors = res.validation["media_completeness"]["errors"]
    assert all("beat_0007" not in e for e in gate_errors), (
        "planner routed around; the document requirement must be waived")
    rec7 = next(r for r in res.strategy_plan if r.beat_id == "beat_0007")
    assert rec7.selected_strategy == "evidence_board"


def test_min_count_is_gone_from_requirements(berlin_run):
    raw = berlin_run["store"].load("berlin_wall_phase1", "asset_requirements")
    assert all("min_count" not in r for r in raw)
    assert all(r["strength"] in ("REQUIRED", "PREFERRED", "OPTIONAL")
               for r in raw)


# ---- 4. motion + timeline validators ----------------------------------------

def make_beat(i=1):
    return SemanticBeat(beat_id=f"beat_{i:04d}", start_sec=(i - 1) * 5.0,
                        end_sec=i * 5.0, narration_text="text", word_start=0,
                        word_end=3, semantic_function=SemanticFunction.EVIDENCE,
                        visual_intent="t")


def make_comp(beat):
    comp = VisualComposition(composition_id=f"comp_{beat.beat_id}",
                             beat_id=beat.beat_id, visual_family="document_evidence",
                             strategy="single_document_focus",
                             duration_sec=beat.duration_sec,
                             novelty_signature=f"sig_{beat.beat_id}")
    from videotool.domain.composition import CompositionLayer, LayerType, MotionStyle
    comp.layers.append(CompositionLayer(
        id="doc", type=LayerType.DOCUMENT, x=0.1, y=0.1, width=0.5,
        height=0.6, z_index=10, role="document",
        entrance=MotionStyle.SNAP_IN, exit=MotionStyle.SLIDE_OUT))
    return comp


def make_motion(beats, comps, events=None, transitions=None):
    plans = [CompositionMotionPlan(
        composition_id=c.composition_id, beat_id=c.beat_id,
        events=events or [MotionEvent(
            layer_id="doc", kind=EventKind.ENTRANCE, style="SNAP_IN",
            start_sec=b.start_sec + 0.1, end_sec=b.start_sec + 0.6,
            semantic_reason="r")])
        for b, c in zip(beats, comps)]
    return MotionPlan(episode_id="ep", plans=plans,
                      transitions=transitions if transitions is not None else [
                          TransitionPlan(from_beat=beats[0].beat_id,
                                         to_beat=beats[1].beat_id,
                                         category=TransitionCategory.CONTINUATION,
                                         start_sec=4.7, end_sec=5.0)
                          for a, b in zip(beats, beats[1:])])


def test_motion_validator_accepts_valid_plan(berlin_run):
    report = validation.validate_motion(berlin_run["result"].motion,
                                        berlin_run["result"].beats,
                                        berlin_run["result"].compositions)
    assert report.ok, report.errors


def test_motion_missing_plan_for_composition_is_error():
    beats = [make_beat(1), make_beat(2)]
    comps = [make_comp(b) for b in beats]
    motion = make_motion(beats, comps)
    motion.plans = motion.plans[:1]
    report = validation.validate_motion(motion, beats, comps)
    assert any("no motion plan" in e for e in report.errors)


def test_motion_unknown_layer_reference_is_error():
    beats = [make_beat(1), make_beat(2)]
    comps = [make_comp(b) for b in beats]
    motion = make_motion(beats, comps, events=[MotionEvent(
        layer_id="ghost_layer", kind=EventKind.ENTRANCE, style="SNAP_IN",
        start_sec=0.1, end_sec=0.5, semantic_reason="r")] +
        [MotionEvent(layer_id="doc", kind=EventKind.ENTRANCE, style="SNAP_IN",
                     start_sec=0.1, end_sec=0.5, semantic_reason="r")])
    report = validation.validate_motion(motion, beats, comps)
    assert any("unknown layer ghost_layer" in e for e in report.errors)


def test_motion_event_outside_beat_window_is_error():
    beats = [make_beat(1), make_beat(2)]
    comps = [make_comp(b) for b in beats]
    motion = make_motion(beats, comps, events=[MotionEvent(
        layer_id="doc", kind=EventKind.ENTRANCE, style="SNAP_IN",
        start_sec=0.1, end_sec=99.0, semantic_reason="r")])
    report = validation.validate_motion(motion, beats, comps)
    assert any("ends after beat window" in e for e in report.errors)
    neg = make_motion(beats, comps, events=[MotionEvent(
        layer_id="doc", kind=EventKind.ENTRANCE, style="SNAP_IN",
        start_sec=1.0, end_sec=0.5, semantic_reason="r")])
    assert any("ends before it starts" in e
               for e in validation.validate_motion(neg, beats, comps).errors)


def test_motion_non_adjacent_transition_is_error():
    beats = [make_beat(1), make_beat(2), make_beat(3)]
    comps = [make_comp(b) for b in beats]
    motion = make_motion(beats, comps)
    motion.transitions = [TransitionPlan(
        from_beat="beat_0001", to_beat="beat_0003",
        category=TransitionCategory.CONTINUATION, start_sec=4.7, end_sec=5.0)]
    report = validation.validate_motion(motion, beats, comps)
    assert any("not between adjacent beats" in e for e in report.errors)
    ghost = make_motion(beats, comps)
    ghost.transitions = [TransitionPlan(
        from_beat="beat_0001", to_beat="beat_9999",
        category=TransitionCategory.CONTINUATION, start_sec=4.7, end_sec=5.0)]
    assert any("unknown beat" in e
               for e in validation.validate_motion(ghost, beats, comps).errors)


def test_timeline_validator_accepts_valid(berlin_run):
    report = validation.validate_timeline(berlin_run["result"].timeline,
                                          berlin_run["result"].beats,
                                          berlin_run["result"].compositions,
                                          "final")
    assert report.ok, report.errors


def test_timeline_missing_segment_is_error():
    beats = [make_beat(1), make_beat(2)]
    comps = [make_comp(b) for b in beats]
    timeline = {"total_duration_sec": 10.0,
                "segments": [{"beat_id": "beat_0001",
                              "composition_id": comps[0].composition_id,
                              "start_sec": 0, "end_sec": 5}],
                "subtitles": []}
    report = validation.validate_timeline(timeline, beats, comps, "final")
    assert any("segments for" in e for e in report.errors)


def test_timeline_final_mode_requires_composition_ids():
    beats = [make_beat(1)]
    timeline = {"total_duration_sec": 5.0,
                "segments": [{"beat_id": "beat_0001", "composition_id": None,
                              "start_sec": 0, "end_sec": 5}],
                "subtitles": []}
    report = validation.validate_timeline(timeline, beats, [], "final")
    assert any("no composition" in e for e in report.errors)
    draft = validation.validate_timeline(timeline, beats, [], "draft")
    assert draft.ok


def test_timeline_subtitle_and_segment_timing_bounds():
    beats = [make_beat(1)]
    comp = make_comp(beats[0])
    timeline = {"total_duration_sec": 5.0,
                "segments": [{"beat_id": "beat_0001",
                              "composition_id": comp.composition_id,
                              "start_sec": -1, "end_sec": 6}],
                "subtitles": [{"start_sec": 4.0, "end_sec": 9.0, "text": "x"}]}
    report = validation.validate_timeline(timeline, beats, [comp], "final")
    assert any("invalid timing" in e for e in report.errors)
    assert any("exceeds narration duration" in e for e in report.errors)


def test_runner_qc_includes_motion_and_timeline(berlin_run):
    v = berlin_run["result"].validation
    assert "motion_plan" in v and v["motion_plan"]["ok"]
    assert "timeline" in v and v["timeline"]["ok"]


# ---- 5. mode single source of truth ------------------------------------------

def test_mode_has_single_source_of_truth():
    assert not any(f.name == "mode" for f in dataclasses.fields(EpisodeInput))
    runner = PipelineRunner(ArtifactStore("/tmp/never_used_mode"),
                            mode="draft")
    assert runner.mode == "draft"
    data = load_episode()
    assert "mode" not in data


# ---- 6. complete fallback coverage --------------------------------------------

def test_missing_strategy_record_gets_created(tmp_path, monkeypatch):
    runner = make_runner(tmp_path)
    original_select = runner.planner.select

    def dropping_select(beats, history=None):
        records = original_select(beats, history)
        return records[:-1]  # one beat left without any record

    monkeypatch.setattr(runner.planner, "select", dropping_select)
    res = runner.run(EpisodeInput(**load_episode()))
    assert len(res.preliminary_strategy_plan) == len(res.beats)
    fallback = res.preliminary_strategy_plan[-1]
    assert fallback.is_fallback and fallback.selected_strategy
    assert any("missing selection record" in r["issue"]
               for r in res.manifest["repairs"])
    assert len(res.compositions) == len(res.beats)
    assert res.ok


def test_family_exception_routed_to_deterministic_fallback(tmp_path, monkeypatch):
    def exploding(ctx):
        raise RuntimeError("family exploded")

    monkeypatch.setattr(FAMILIES["document_evidence"], "compose", exploding)
    res = run_ep(tmp_path)
    assert res.ok, res.validation
    assert any("raised RuntimeError" in r["issue"]
               for r in res.manifest["repairs"])
    doc_beats = {c.beat_id for c in res.compositions
                 if c.visual_family == "document_evidence"}
    assert doc_beats  # fixture exercises the family
    for comp in res.compositions:
        if comp.beat_id in doc_beats:
            assert comp.is_fallback  # replaced, not silently kept


# ---- 7. single FAMILIES_VERSION ------------------------------------------------

def test_families_version_has_single_definition():
    import videotool.editorial.composition as comp_pkg
    import videotool.pipeline.fingerprints as fp_pkg
    assert hasattr(comp_pkg, "FAMILIES_VERSION")
    assert not hasattr(fp_pkg, "FAMILIES_VERSION"), (
        "duplicate definition in fingerprints.py must be removed")
