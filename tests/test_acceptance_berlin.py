"""Acceptance assertions for the Berlin Wall fixture (spec sections 25-26).

Runs the full pipeline in final mode and verifies every automated assertion
required by the spec, plus the negative guarantees (no placeholder, no
unbound assets, no timing violations).
"""
from videotool.domain.semantic_beat import SemanticFunction
from videotool.pipeline.runner import STAGES


def test_validation_reports_ok(berlin_run):
    res = berlin_run["result"]
    assert res.ok
    assert all(v["ok"] for v in res.validation.values()), res.validation


def test_semantic_beats_exist_and_functions_assigned(berlin_run):
    beats = berlin_run["result"].beats
    assert len(beats) >= 8
    assert all(b.semantic_function in SemanticFunction for b in beats)


def test_episode_art_direction_exists(berlin_run):
    ad = berlin_run["result"].art_direction
    assert ad is not None and ad.visual_motifs and ad.accent["primary"]


def test_every_beat_has_a_selected_strategy(berlin_run):
    beats = berlin_run["result"].beats
    selected = {r.beat_id for r in berlin_run["result"].strategy_plan}
    assert selected == {b.beat_id for b in beats}


def test_unique_composition_ids(berlin_run):
    ids = [c.composition_id for c in berlin_run["result"].compositions]
    assert len(ids) == len(set(ids))


def test_no_exact_composition_signature_reuse(berlin_run):
    sigs = [c.novelty_signature for c in berlin_run["result"].compositions]
    assert len(sigs) == len(set(sigs)), "identical composition reuse is forbidden"


def test_same_family_respects_repetition_threshold(berlin_run):
    families = [c.visual_family for c in berlin_run["result"].compositions]
    streak = 1
    for prev, cur in zip(families, families[1:]):
        streak = streak + 1 if prev == cur else 1
        assert streak <= 2


def test_multiple_visual_strategies_selected(berlin_run):
    strategies = {r.selected_strategy for r in berlin_run["result"].strategy_plan}
    families = {c.visual_family for c in berlin_run["result"].compositions}
    assert len(strategies) >= 6, f"only {len(strategies)} strategies selected"
    assert len(families) >= 4, f"only {len(families)} visual families used"
    assert len(families) == 6, "all six phase-1 families should trigger"


def test_planner_persists_selection_reason(berlin_run):
    for rec in berlin_run["result"].strategy_plan:
        assert rec.reason and len(rec.reason) > 40
        assert rec.semantic_function in rec.reason
        assert any(c.total >= 0 for c in rec.candidates)
        # explainability artifact exists on disk
    raw = berlin_run["store"].load("berlin_wall_phase1", "visual_strategy_plan")
    assert all("reason" in r and r["reason"] for r in raw)


def test_motion_plan_exists_and_fits_narration(berlin_run):
    motion = berlin_run["result"].motion
    narration_dur = berlin_run["data"]["narration"].duration_sec
    assert motion.plans and motion.transitions
    for plan in motion.plans:
        for ev in plan.events:
            assert 0.0 <= ev.start_sec < ev.end_sec <= narration_dur + 1e-6


def test_all_timing_fits_narration_timeline(berlin_run):
    narration_dur = berlin_run["data"]["narration"].duration_sec
    beats = berlin_run["result"].beats
    timeline = berlin_run["result"].timeline
    assert beats[-1].end_sec <= narration_dur + 1e-6
    assert abs(timeline["total_duration_sec"] - narration_dur) < 0.01
    for seg in timeline["segments"]:
        assert seg["start_sec"] < seg["end_sec"]
        assert seg["end_sec"] <= narration_dur + 1e-6


def test_all_referenced_assets_are_resolvable(berlin_run):
    asset_ids = {a.asset_id for a in berlin_run["result"].assets}
    for comp in berlin_run["result"].compositions:
        for layer in comp.layers:
            if layer.asset_id:
                assert layer.asset_id in asset_ids, (
                    f"{comp.composition_id}/{layer.id}: unbound {layer.asset_id}")


def test_no_placeholder_assets_in_final_mode(berlin_run):
    for a in berlin_run["result"].assets:
        assert not a.is_placeholder
    for comp in berlin_run["result"].compositions:
        for layer in comp.layers:
            assert not (layer.asset_id or "").startswith("placeholder:")


def test_no_negative_durations_or_invalid_overlap(berlin_run):
    for b in berlin_run["result"].beats:
        assert b.end_sec > b.start_sec
    for prev, nxt in zip(berlin_run["result"].beats, berlin_run["result"].beats[1:]):
        assert nxt.start_sec >= prev.start_sec
        assert abs(nxt.start_sec - prev.end_sec) < 1e-6


def test_compositions_stay_inside_safe_frame(berlin_run):
    for comp in berlin_run["result"].compositions:
        for layer in comp.layers:
            for dim in ("x", "y", "width", "height"):
                assert -1e-6 <= getattr(layer, dim) <= 1 + 1e-6


def test_pipeline_resume_from_persisted_artifacts(berlin_run, tmp_path):
    from videotool.pipeline.runner import EpisodeInput, PipelineRunner
    from videotool.artifacts import ArtifactStore
    from videotool.fixtures.berlin_wall import load_episode

    data = load_episode()
    runner = PipelineRunner(ArtifactStore(tmp_path / "a2"), mode="final")
    runner.run(EpisodeInput(**data))

    store = ArtifactStore(tmp_path / "a2")
    store.delete("berlin_wall_phase1", "visual_compositions")
    store.delete("berlin_wall_phase1", "timeline")
    res2 = runner.run(EpisodeInput(**data))
    assert res2.manifest["stages"]["semantic_beats"]["status"] == "resumed"
    assert res2.manifest["stages"]["visual_compositions"]["status"] == "invalidated"
    assert res2.ok


def test_all_required_artifacts_on_disk(berlin_run):
    existing = set(berlin_run["store"].existing("berlin_wall_phase1"))
    for stage in STAGES:
        assert stage in existing


def test_subtitles_are_independent_and_bounded(berlin_run):
    timeline = berlin_run["result"].timeline
    subs = timeline["subtitles"]
    assert subs
    for s in subs:
        assert s["start_sec"] < s["end_sec"]
        assert s["end_sec"] - s["start_sec"] <= 4.0  # readable, not giant
        assert len(s["text"].split()) <= 8
    zone = timeline["subtitle_safe_zone"]
    assert zone["y"] + zone["height"] <= 1.0


def test_fixture_does_not_render_six_variants_of_one_composition(berlin_run):
    """Spec 25: must NOT produce six variants of the same composition."""
    comps = berlin_run["result"].compositions
    signatures = {c.novelty_signature for c in comps}
    assert len(signatures) == len(comps)
    # structural fingerprint: hero quadrant + layer type multiset
    shapes = set()
    for c in comps:
        hero = next((l for l in c.layers if l.role in ("hero", "document")), None)
        types = tuple(sorted(l.type.value for l in c.layers))
        if hero:
            shapes.add((c.visual_family, types,
                        (hero.x > 0.5, hero.y > 0.5)))
    assert len(shapes) >= len(comps) * 0.6, (
        f"compositions too homogeneous: {len(shapes)} shapes for {len(comps)} comps")
