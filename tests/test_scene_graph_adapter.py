"""Test RenderSceneGraph adapter and FramePlan roundtrip parity."""
from __future__ import annotations

from videotool.fixtures.berlin_wall import load_episode
from videotool.render.frame_plan import build_episode_frame_plan
from videotool.render.scene_graph import RenderSceneGraph


def test_scene_graph_adapter_roundtrip_parity(berlin_run):
    res = berlin_run["result"]

    frame_plan = build_episode_frame_plan(
        timeline=res.timeline,
        geometry_plans=[p.to_dict() for p in res.geometry_plans],
        motion_plan=res.motion.to_dict() if res.motion else None,
        media_assets=[a.to_dict() for a in res.assets],
        visual_compositions=[c.to_dict() for c in res.compositions],
        art_direction=res.art_direction.to_dict() if res.art_direction else None,
        semantic_beats=[b.to_dict() for b in res.beats],
    )

    # Convert to SceneGraph
    scene_graph = RenderSceneGraph.from_frame_plan(frame_plan)
    assert scene_graph.schema_version == 1
    assert scene_graph.episode_id == frame_plan.episode_id
    assert len(scene_graph.beats) == len(frame_plan.beats)

    # Convert back to FramePlan
    restored_plan = scene_graph.to_frame_plan()
    assert restored_plan.episode_id == frame_plan.episode_id
    assert restored_plan.total_duration_sec == frame_plan.total_duration_sec
    assert len(restored_plan.beats) == len(frame_plan.beats)

    # Compare each beat in detail
    for orig_beat, rest_beat in zip(frame_plan.beats, restored_plan.beats):
        assert orig_beat.beat_id == rest_beat.beat_id
        assert orig_beat.start_sec == rest_beat.start_sec
        assert orig_beat.end_sec == rest_beat.end_sec
        assert orig_beat.visual_family == rest_beat.visual_family
        assert len(orig_beat.media_elements) == len(rest_beat.media_elements)
        assert len(orig_beat.text_elements) == len(rest_beat.text_elements)
        assert len(orig_beat.connectors) == len(rest_beat.connectors)

        for om, rm in zip(orig_beat.media_elements, rest_beat.media_elements):
            assert om.element_id == rm.element_id
            assert om.asset_id == rm.asset_id
            assert om.bounds_px == rm.bounds_px
            assert len(om.keyframes) == len(rm.keyframes)
            for ok, rk in zip(om.keyframes, rm.keyframes):
                assert ok.time_offset_sec == rk.time_offset_sec
                assert ok.scale == rk.scale

        for ot, rt in zip(orig_beat.text_elements, rest_beat.text_elements):
            assert ot.element_id == rt.element_id
            assert ot.text == rt.text
            assert ot.bounds_px == rt.bounds_px
