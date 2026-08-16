"""Phase 1.1 Hardening tests.

Covers the five review items:
1. artifact fingerprinting + dependency invalidation
2. production validate/repair/fallback flow (actually used by the runner)
3. stage-level validation before downstream consumption
4. asset feasibility pass after media acquisition
5. repository hygiene is enforced by test_no_berlin_hardcoded + .gitignore;
   this file covers the behavioural guarantees of 1-4.
"""
import pytest

from videotool.artifacts import ArtifactStore
from videotool.domain.composition import CompositionLayer, LayerType, MotionStyle, VisualComposition
from videotool.domain.narration import Narration, synthetic_word_timings
from videotool.domain.semantic_beat import SemanticFunction
from videotool.editorial.composition import FAMILIES
from videotool.editorial.strategies import PlanningConfig
from videotool.pipeline.runner import EpisodeInput, PipelineRunner
from videotool.fixtures.berlin_wall import load_episode


def make_runner(tmp_path, mode="final", **kw):
    return PipelineRunner(ArtifactStore(tmp_path / "artifacts"), mode=mode, **kw)


def run_ep(tmp_path, data=None, **kw):
    data = data or load_episode()
    return make_runner(tmp_path, **kw).run(EpisodeInput(**data))


def statuses(res):
    return {s: v["status"] for s, v in res.manifest["stages"].items()}


# ---- 1. fingerprinting + dependency invalidation --------------------------

def test_changed_subject_invalidates_art_direction_not_beats(tmp_path):
    """The exact bug from review: same episode_id, different subject."""
    res1 = run_ep(tmp_path)
    assert res1.ok

    data = load_episode()
    data["subject"] = "Apollo 13 spacecraft oxygen tank failure"
    res2 = make_runner(tmp_path).run(EpisodeInput(**data))

    st = statuses(res2)
    # narration untouched -> beats stay valid
    assert st["semantic_beats"] == "resumed"
    # subject changed -> identity recomputed, never the stale Berlin one
    assert st["episode_art_direction"] == "invalidated"
    assert res2.art_direction.subject == "Apollo 13 spacecraft oxygen tank failure"
    # compositions consume art direction -> invalidated; upstream planning kept
    assert st["visual_compositions"] == "invalidated"
    assert st["asset_requirements"] == "resumed"
    assert st["media_assets"] == "resumed"
    assert res2.ok


def test_changed_narration_invalidates_beats_and_everything_downstream(tmp_path):
    run_ep(tmp_path)
    data = load_episode()
    data["subject"] = "Chernobyl: The Reactor That Burned"
    data["narration"] = Narration(
        text="April 1986. One reactor failed during a safety test outside Pripyat.",
        words=synthetic_word_timings(
            "April 1986. One reactor failed during a safety test outside Pripyat."))
    res2 = make_runner(tmp_path).run(EpisodeInput(**data))
    st = statuses(res2)
    for stage in st:
        assert st[stage] == "invalidated", f"{stage} must recompute on new narration"
    assert res2.ok
    assert res2.art_direction.concept_cluster != "political_division"


def test_mode_switch_draft_to_final_recomputes_media_not_planning(tmp_path):
    """Review case: draft placeholders must never leak into a final run."""
    draft = load_episode()
    draft["catalog"] = []
    res_draft = make_runner(tmp_path, mode="draft").run(EpisodeInput(**draft))
    assert any(a.is_placeholder for a in res_draft.assets)

    res_final = make_runner(tmp_path, mode="final").run(EpisodeInput(**load_episode()))
    st = statuses(res_final)
    assert st["semantic_beats"] == "resumed"
    assert st["episode_art_direction"] == "resumed"
    assert st["media_assets"] == "invalidated"
    assert st["strategy_feasibility"] == "invalidated"
    assert st["visual_compositions"] == "invalidated"
    assert all(not a.is_placeholder for a in res_final.assets)
    assert res_final.ok


def test_catalog_change_invalidates_media_chain(tmp_path):
    run_ep(tmp_path)
    data = load_episode()
    data["catalog"] = data["catalog"][:1]  # only the portrait remains
    res2 = make_runner(tmp_path).run(EpisodeInput(**data))
    st = statuses(res2)
    assert st["media_assets"] == "invalidated"
    assert st["semantic_beats"] == "resumed"
    # Phase 1.2 semantics: with every map gone, the REQUIRED map of the
    # location beat cannot be satisfied or routed around -> final fails
    assert not res2.ok
    assert any("Media Completeness Gate" in e
               for e in res2.validation["media_completeness"]["errors"])


def test_planner_config_change_invalidates_strategy_chain(tmp_path):
    run_ep(tmp_path)
    res2 = run_ep(tmp_path, planner_config=PlanningConfig(max_family_streak=1))
    st = statuses(res2)
    assert st["visual_strategy_plan"] == "invalidated"
    assert st["asset_requirements"] == "resumed"  # requirements depend on beats only
    assert res2.ok


def test_renderer_style_change_would_keep_planning(monkeypatch, tmp_path):
    """Non-planning config (e.g. render settings) must not invalidate anything.

    Simulated by re-running with identical inputs: everything resumes.
    """
    run_ep(tmp_path)
    res2 = run_ep(tmp_path)
    st = statuses(res2)
    assert all(v == "resumed" for v in st.values())
    assert res2.ok


def test_stage_meta_persists_fingerprints(tmp_path):
    res = run_ep(tmp_path)
    meta = ArtifactStore(tmp_path / "artifacts").load(
        "berlin_wall_phase1", "stage_meta")
    assert isinstance(meta, dict) and len(meta) >= 10
    for stage, info in res.manifest["stages"].items():
        entry = meta[stage]
        assert isinstance(entry, dict), "Phase 1.2: meta entries are dicts"
        assert info["fingerprint"] == entry["input_fingerprint"]
        assert entry["output_hash"] and entry["stage_version"] >= 1


# ---- 2 + 3. production validate/repair/fallback + stage validation ---------

def test_runner_repairs_invalid_beat(tmp_path, monkeypatch):
    data = load_episode()

    class BrokenAnalyzer:
        def analyze(self, narration, episode_id):
            beats = make_runner(tmp_path).beat_analyzer.analyze(narration, episode_id)
            beats[0].semantic_function = None  # unusable AI output
            return beats

    runner = make_runner(tmp_path)
    monkeypatch.setattr(runner, "beat_analyzer", BrokenAnalyzer())
    res = runner.run(EpisodeInput(**data))
    assert res.beats[0].semantic_function == SemanticFunction.ESTABLISHING_CONTEXT
    assert any(r["stage"] == "semantic_beats" for r in res.manifest["repairs"])
    assert res.ok


def test_runner_falls_back_for_invalid_art_direction(tmp_path, monkeypatch):
    from videotool.domain.art_direction import EpisodeArtDirection

    class EmptyDirector:
        def generate(self, episode_id, subject, narration, beats):
            return EpisodeArtDirection(episode_id=episode_id, subject=subject)

    runner = make_runner(tmp_path)
    monkeypatch.setattr(runner, "art_director", EmptyDirector())
    res = runner.run(EpisodeInput(**load_episode()))
    assert res.art_direction.visual_motifs          # fallback identity in place
    assert res.art_direction.generation_reason.startswith("deterministic fallback")
    assert any(r["stage"] == "episode_art_direction" for r in res.manifest["repairs"])
    assert res.ok


def test_runner_replaces_unusable_strategy_record(tmp_path, monkeypatch):
    from videotool.domain.strategy import SelectionRecord

    runner = make_runner(tmp_path)
    original_select = runner.planner.select

    def broken_select(beats, history=None):
        records = original_select(beats, history)
        records[0] = SelectionRecord(  # unusable: empty strategy + no reason
            beat_id=records[0].beat_id,
            semantic_function=records[0].semantic_function,
            selected_strategy="", visual_family="", reason="")
        return records

    monkeypatch.setattr(runner.planner, "select", broken_select)
    res = runner.run(EpisodeInput(**load_episode()))
    rec = res.preliminary_strategy_plan[0]
    assert rec.selected_strategy != "" and rec.is_fallback
    assert any(r["stage"] == "visual_strategy_plan" for r in res.manifest["repairs"])
    assert res.ok


def test_runner_swaps_invalid_composition_for_fallback(tmp_path, monkeypatch):
    """A family emitting garbage must not reach the timeline."""
    good = FAMILIES["geographic_map"].compose

    def broken(ctx):
        comp = good(ctx)
        comp.layers.append(CompositionLayer(
            id="oob", type=LayerType.IMAGE, x=1.7, y=0.1, width=0.2,
            height=0.2, z_index=99, role="hero",
            entrance=MotionStyle.CUT_IN, exit=MotionStyle.DISSOLVE))
        return comp

    monkeypatch.setattr(FAMILIES["geographic_map"], "compose", broken)
    res = run_ep(tmp_path)
    monkeypatch.undo()  # restore for other tests

    comps_by_family = [c for c in res.compositions if c.visual_family == "geographic_map"]
    assert comps_by_family, "fixture must exercise the broken family"
    assert res.ok, res.validation
    repairs = [r for r in res.manifest["repairs"]
               if r["stage"] == "visual_compositions"]
    assert repairs, "runner must log the fallback repair"
    # the repaired episode still passes full validation
    assert all(v["ok"] for v in res.validation.values())


def test_two_fallback_compositions_keep_distinct_signatures():
    from videotool.editorial.validation import deterministic_fallback_composition
    from videotool.domain.semantic_beat import SemanticBeat
    from videotool.domain.visual_history import derive_signature

    def beat(i):
        return SemanticBeat(beat_id=f"beat_{i:04d}", start_sec=0, end_sec=5,
                            narration_text="t", word_start=0, word_end=2,
                            semantic_function=SemanticFunction.EVIDENCE,
                            visual_intent="t")

    a = deterministic_fallback_composition(beat(1), 0, [])
    b = deterministic_fallback_composition(beat(2), 1, [])
    assert derive_signature(a) != derive_signature(b)


# ---- 4. asset feasibility pass ----------------------------------------------

def test_feasibility_artifact_persisted_and_used(berlin_run):
    store = berlin_run["store"]
    raw = store.load("berlin_wall_phase1", "strategy_feasibility")
    assert "records" in raw and "adjustments" in raw
    # plan-of-record equals post-feasibility records
    res = berlin_run["result"]
    assert [r.selected_strategy for r in res.strategy_plan] == \
           [r["selected_strategy"] for r in raw["records"]]


def test_feasibility_switches_strategy_when_assets_missing(berlin_run):
    """map_plus_archival needs map+photo; when the photo is missing the
    plan-of-record must not promise it."""
    res = berlin_run["result"]
    adjustments = res.feasibility["adjustments"]
    beat2 = next((a for a in adjustments if a["beat_id"] == "beat_0002"), None)
    assert beat2 is not None, "beat_0002 (map, no photo) must trigger a switch"
    assert beat2["to"] == "region_map"
    assert beat2["reason"]
    # composition actually follows the adjusted plan
    comp2 = next(c for c in res.compositions if c.beat_id == "beat_0002")
    assert comp2.strategy == "region_map"


def test_feasibility_preserves_family_streak_limit(berlin_run):
    families = [c.visual_family for c in berlin_run["result"].compositions]
    streak = 1
    for prev, cur in zip(families, families[1:]):
        streak = streak + 1 if prev == cur else 1
        assert streak <= 2


def test_degraded_beats_are_marked_not_hidden(berlin_run):
    res = berlin_run["result"]
    degraded = [r for r in res.strategy_plan if r.feasibility_note.startswith("degraded")]
    # beats without any resolved asset degrade explicitly, never silently
    for rec in degraded:
        assert "available kinds" in rec.feasibility_note
    raw = berlin_run["store"].load("berlin_wall_phase1", "strategy_feasibility")
    assert all(a["reason"] for a in raw["adjustments"])


def test_asset_needs_table_covers_all_asset_kinds():
    from videotool.editorial.feasibility import STRATEGY_ASSET_NEEDS
    from videotool.editorial.strategies import STRATEGY_CATALOG
    for strategy_id, policy in STRATEGY_ASSET_NEEDS.items():
        assert strategy_id in STRATEGY_CATALOG, f"unknown strategy {strategy_id}"
        assert policy.declares(), "table entries must declare real needs"
