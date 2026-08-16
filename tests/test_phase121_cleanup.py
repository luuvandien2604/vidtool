"""Phase 1.2.1 cleanup tests (external review follow-up).

1. family_recency/signature_recency direction fixed (was inverted; an old
   test locked the bug)
2. composition signatures ignore TEXTURE layers and are stable across
   mirror/texture attachment order
3. strategy asset needs use all_of/any_of POLICIES, not AND-sets
4. build_timeline no longer mutates VisualComposition (fresh and resumed
   runs must be identical in memory, not only on disk)
5. feasibility maps requirement_id -> beat_id via requirements; no string
   parsing of ids
"""
import json

from videotool.artifacts import ArtifactStore
from videotool.domain.assets import AssetRequirement, MediaAsset
from videotool.domain.composition import (CompositionLayer, LayerType,
                                          MotionStyle, VisualComposition)
from videotool.domain.semantic_beat import SemanticBeat, SemanticFunction
from videotool.domain.strategy import SelectionRecord
from videotool.domain.visual_history import HistoryEntry, VisualHistory, derive_signature
from videotool.editorial.feasibility import (STRATEGY_ASSET_NEEDS,
                                             StrategyAssetPolicy,
                                             policy_needs_kind,
                                             run_feasibility_pass,
                                             strategy_is_feasible)
from videotool.editorial.strategies import StrategyPlanner
from videotool.editorial.timeline import build_timeline
from videotool.domain.motion import MotionPlan
from videotool.fixtures.berlin_wall import load_episode
from videotool.pipeline.runner import EpisodeInput, PipelineRunner

# ---- 1. recency direction ---------------------------------------------------

def test_family_recency_recent_is_low_novelty():
    h = VisualHistory(max_window=10)
    h.record(HistoryEntry(beat_id="b1", visual_family="f", strategy="s",
                          composition_signature="x"))
    assert h.family_recency("f") == 0.1      # back=1 -> 1/10
    assert h.family_recency("other") == 1.0  # unseen


def test_planner_novelty_penalizes_recent_family():
    planner = StrategyPlanner()
    h = VisualHistory(max_window=10)
    h.record(HistoryEntry(beat_id="b1", visual_family="document_evidence",
                          strategy="s", composition_signature="x"))
    recent = planner._novelty(h, _cand_def("single_document_focus"))
    unseen = planner._novelty(h, _cand_def("linear_timeline"))
    assert recent < 0.2 < unseen == 1.0


def _cand_def(strategy_id):
    from videotool.editorial.strategies import STRATEGY_CATALOG
    return STRATEGY_CATALOG[strategy_id]


def test_fixture_plan_variety_survives_correct_novelty(berlin_run):
    """Correct novelty must IMPROVE, not collapse, family variety."""
    families = [c.visual_family for c in berlin_run["result"].compositions]
    assert len(set(families)) >= 5


# ---- 2. texture-independent signatures ----------------------------------------

def make_textured_comp(with_texture: bool) -> VisualComposition:
    comp = VisualComposition(composition_id="c", beat_id="b",
                             visual_family="document_evidence",
                             strategy="s", duration_sec=5.0)
    comp.layers.append(CompositionLayer(
        id="doc", type=LayerType.DOCUMENT, x=0.1, y=0.1, width=0.5,
        height=0.6, z_index=10, role="document",
        entrance=MotionStyle.SNAP_IN, exit=MotionStyle.SLIDE_OUT))
    comp.reading_order = ["doc"]
    if with_texture:
        comp.layers.append(CompositionLayer(
            id="tex", type=LayerType.TEXTURE, x=0, y=0, width=1, height=1,
            z_index=1, role="texture", entrance=MotionStyle.DISSOLVE,
            exit=MotionStyle.DISSOLVE))
    return comp


def test_signature_ignores_texture_layers():
    assert derive_signature(make_textured_comp(False)) == \
           derive_signature(make_textured_comp(True))


def test_signature_stable_across_mirror_and_texture_order():
    """The exact bug: odd variants mirrored AFTER texture attach derived a
    texture-counting signature while even variants did not."""
    a = make_textured_comp(False)
    b = make_textured_comp(True)   # texture present from the start
    for layer in b.layers:         # mirror both identically
        if layer.type != LayerType.TEXTURE:
            layer.x = round(1.0 - layer.x - layer.width, 4)
    sig_with_tex_then_mirror = derive_signature(b)
    for layer in a.layers:
        layer.x = round(1.0 - layer.x - layer.width, 4)
    sig_plain_then_mirror = derive_signature(a)
    assert sig_plain_then_mirror == sig_with_tex_then_mirror


# ---- 3. all_of/any_of policies -------------------------------------------------

def test_full_frame_archival_needs_only_one_visual():
    """The review's example: one great archival photo must be enough."""
    assert strategy_is_feasible("full_frame_archival", {"photo"})
    assert strategy_is_feasible("full_frame_archival", {"portrait"})
    assert strategy_is_feasible("full_frame_archival", {"map"})
    assert not strategy_is_feasible("full_frame_archival", set())


def test_all_of_is_strict_any_of_is_alternative():
    assert not strategy_is_feasible("portrait_plus_document", {"portrait"})
    assert not strategy_is_feasible("portrait_plus_document", {"document"})
    assert strategy_is_feasible("portrait_plus_document", {"document", "portrait"})
    assert strategy_is_feasible("portrait_plus_document", {"document", "photo"})
    assert not strategy_is_feasible("map_plus_archival", {"map"})
    assert strategy_is_feasible("map_plus_archival", {"map", "photo"})
    assert strategy_is_feasible("route_map", {"map"})
    assert strategy_is_feasible("cinematic_hold", set())  # no policy


def test_kind_equivalence_applies_inside_policies():
    assert strategy_is_feasible("archival_portrait", {"photo"})
    assert strategy_is_feasible("single_document_focus", {"document"})


def test_policy_needs_kind_semantics():
    assert policy_needs_kind("portrait_plus_document", "document")
    assert policy_needs_kind("full_frame_archival", "photo")
    assert not policy_needs_kind("cinematic_hold", "photo")
    assert not policy_needs_kind("route_map", "photo")


def test_policy_table_entries_are_policies():
    for policy in STRATEGY_ASSET_NEEDS.values():
        assert isinstance(policy, StrategyAssetPolicy)


# ---- 4. timeline never mutates compositions -------------------------------------

def test_build_timeline_does_not_mutate_compositions():
    beats = [_beat(i) for i in range(1, 3)]
    comps = [_comp(b) for b in beats]
    before = [c.to_dict() for c in comps]
    motion = MotionPlan(episode_id="ep")
    timeline = build_timeline("ep", _narration(), beats, comps, motion)
    after = [c.to_dict() for c in comps]
    assert before == after, "build_timeline must not mutate compositions"
    # transition data lives in the timeline segments instead
    assert all("transition_in" in seg and "transition_out" in seg
               for seg in timeline["segments"])
    assert timeline["segments"][0]["transition_in"] == "CUT_IN"


def test_fresh_and_resumed_runs_are_identical_in_memory(tmp_path):
    """Phase 1.2.1 regression: the old mutation made fresh runs carry
    transition data on compositions that resumed runs lacked."""
    data = load_episode()

    fresh = PipelineRunner(ArtifactStore(tmp_path / "a"), mode="final").run(
        EpisodeInput(**data))
    resumed = PipelineRunner(ArtifactStore(tmp_path / "a"), mode="final").run(
        EpisodeInput(**data))
    assert [c.to_dict() for c in fresh.compositions] == \
           [c.to_dict() for c in resumed.compositions]
    assert all(v["status"] == "resumed"
               for v in resumed.manifest["stages"].values())
    assert fresh.timeline == resumed.timeline


# ---- 5. requirement mapping without id parsing -----------------------------------

def _beat(i):
    return SemanticBeat(beat_id=f"beat_{i:04d}", start_sec=(i - 1) * 5.0,
                        end_sec=i * 5.0, narration_text="t", word_start=0,
                        word_end=2,
                        semantic_function=SemanticFunction.LOCATION_INTRODUCTION,
                        visual_intent="t")


def _comp(beat):
    return VisualComposition(composition_id=f"comp_{beat.beat_id}",
                             beat_id=beat.beat_id, visual_family="geographic_map",
                             strategy="region_map", duration_sec=5.0,
                             novelty_signature=f"sig{beat.beat_id}")


def _narration():
    from videotool.domain.narration import Narration, synthetic_word_timings
    text = "A city divided. The border opened."
    return Narration(text=text, words=synthetic_word_timings(text))


def test_feasibility_maps_beats_via_requirement_ids():
    """Requirement ids are opaque: no req_<beat>_<kind> format assumption."""
    beat = _beat(1)
    req = AssetRequirement(requirement_id="R-001/weird format", beat_id=beat.beat_id,
                           description="period map of X", kind="map",
                           strength="REQUIRED", entities=["X"])
    asset = MediaAsset(asset_id="a1", requirement_id=req.requirement_id,
                       description="map", kind="map")
    record = SelectionRecord(beat_id=beat.beat_id,
                             semantic_function="LOCATION_INTRODUCTION",
                             selected_strategy="region_map",
                             visual_family="geographic_map",
                             reason="test reason long enough for validation")

    # map resolved -> region_map stays feasible, no switch
    result = run_feasibility_pass([record], [beat], [req], [asset])
    assert result.records[0].selected_strategy == "region_map"
    assert result.adjustments == []

    # map missing -> region_map infeasible, degrade is recorded
    result2 = run_feasibility_pass([record], [beat], [req], [])
    assert result2.records[0].feasibility_note.startswith("degraded")
