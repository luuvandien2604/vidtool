"""Unit tests for frame plan generation (frame_plan.py).

Pure Python tests: validate normalized-to-pixel coordinate conversions,
element classification (Media, Text, Connector), Ken Burns keyframe motion,
SVG connector overlay generation, and determinism without invoking FFmpeg.
"""
from __future__ import annotations

from videotool.artifacts import ArtifactStore
from videotool.fixtures.berlin_wall import load_episode
from videotool.pipeline.runner import EpisodeInput, PipelineRunner
from videotool.render.frame_plan import (
    BeatFramePlan,
    ConnectorRenderElement,
    EpisodeFramePlan,
    MediaRenderElement,
    PixelRect,
    TextRenderElement,
    build_episode_frame_plan,
)
from videotool.render.svg_overlay import generate_svg_overlay


def test_pixel_rect_math():
    """Verify pixel rectangle center and bound calculations."""
    rect = PixelRect(x=100, y=200, width=400, height=300)
    assert rect.center_x == 300
    assert rect.center_y == 350
    assert rect.right == 500
    assert rect.bottom == 500


def test_build_episode_frame_plan_berlin(tmp_path):
    """Verify building frame plan from full berlin_wall pipeline run."""
    data = load_episode()
    store = ArtifactStore(tmp_path / "artifacts")
    runner = PipelineRunner(store, mode="final")
    result = runner.run(EpisodeInput(**data))
    assert result.ok

    timeline = store.load(result.episode_id, "timeline")
    geo_plans = store.load(result.episode_id, "semantic_geometry")
    motion = store.load(result.episode_id, "motion_plan")
    assets = store.load(result.episode_id, "media_assets")
    comps = store.load(result.episode_id, "visual_compositions")
    art = store.load(result.episode_id, "episode_art_direction")
    beats = store.load(result.episode_id, "semantic_beats")

    plan = build_episode_frame_plan(
        timeline=timeline,
        geometry_plans=geo_plans,
        motion_plan=motion,
        media_assets=assets,
        visual_compositions=comps,
        art_direction=art,
        semantic_beats=beats,
    )

    assert isinstance(plan, EpisodeFramePlan)
    assert plan.canvas_width == 1920
    assert plan.canvas_height == 1080
    assert plan.fps == 30
    assert len(plan.beats) == len(timeline["segments"])
    assert round(plan.total_duration_sec, 2) == round(timeline["total_duration_sec"], 2)

    # Check that media elements, text elements, and connectors are present across beats
    all_media = [m for b in plan.beats for m in b.media_elements]
    all_text = [t for b in plan.beats for t in b.text_elements]
    all_connectors = [c for b in plan.beats for c in b.connectors]

    assert len(all_media) > 0
    assert len(all_text) > 0
    assert len(all_connectors) > 0

    # Find geographic_map or causal_network beat and verify connectors
    connected_beats = [b for b in plan.beats if b.connectors]
    assert len(connected_beats) >= 3  # at least map, timeline, causal beats
    for cb in connected_beats:
        assert cb.svg_overlay_content is not None
        assert "<svg" in cb.svg_overlay_content
        assert "</svg>" in cb.svg_overlay_content


def test_frame_plan_determinism(tmp_path):
    """Verify build_episode_frame_plan produces deterministic output dictionary."""
    data = load_episode()
    store = ArtifactStore(tmp_path / "artifacts")
    runner = PipelineRunner(store, mode="final")
    result = runner.run(EpisodeInput(**data))

    timeline = store.load(result.episode_id, "timeline")
    geo_plans = store.load(result.episode_id, "semantic_geometry")
    motion = store.load(result.episode_id, "motion_plan")
    assets = store.load(result.episode_id, "media_assets")
    comps = store.load(result.episode_id, "visual_compositions")
    art = store.load(result.episode_id, "episode_art_direction")
    beats = store.load(result.episode_id, "semantic_beats")

    plan1 = build_episode_frame_plan(timeline, geo_plans, motion, assets, comps, art, beats)
    plan2 = build_episode_frame_plan(timeline, geo_plans, motion, assets, comps, art, beats)

    assert plan1.to_dict() == plan2.to_dict()


def test_ken_burns_emphasis_keyframes():
    """Verify Ken Burns zoom keyframes generated for emphasis motion."""
    timeline = {
        "episode_id": "test_ep",
        "canvas": {"width": 1920, "height": 1080},
        "total_duration_sec": 5.0,
        "segments": [{
            "beat_id": "b1",
            "start_sec": 0.0,
            "end_sec": 5.0,
            "visual_family": "archival_subject",
            "transition_in": "CUT_IN",
            "transition_out": "CONTINUATION",
        }],
    }
    geo_plans = [{
        "beat_id": "b1",
        "nodes": [{
            "node_id": "n1",
            "role": "PORTRAIT",
            "asset_id": "a1",
            "source_layer_id": "layer_portrait",
        }],
        "solved_placements": [{
            "node_id": "n1",
            "bounds": {"x": 0.1, "y": 0.1, "width": 0.8, "height": 0.8},
            "z_index": 0,
        }],
        "edges": [],
    }]
    motion_plan = {
        "plans": [{
            "beat_id": "b1",
            "camera_behavior": "stable",
            "events": [{
                "layer_id": "layer_portrait",
                "kind": "EMPHASIS",
                "style": "SLOW_ZOOM_IN",
                "start_sec": 1.0,
                "end_sec": 3.0,
            }],
        }],
    }
    assets = [{"asset_id": "a1", "checksum": "deadbeef", "kind": "portrait", "is_placeholder": False}]

    plan = build_episode_frame_plan(timeline, geo_plans, motion_plan, assets)
    elem = plan.beats[0].media_elements[0]
    assert elem.camera_motion == "KEN_BURNS_ZOOM_IN"
    assert elem.emphasis_start_sec == 1.0
    assert elem.emphasis_end_sec == 3.0
    assert len(elem.keyframes) >= 4
    # Keyframe scale increases at emphasis end
    assert elem.keyframes[0].scale == 1.0
    assert elem.keyframes[-1].scale > 1.0


def test_svg_overlay_generator():
    """Verify SVG vector overlay contains valid line and polygon elements."""
    conn = ConnectorRenderElement(
        connector_id="e1",
        source_node_id="n1",
        target_node_id="n2",
        relationship_type="ROUTE_TO",
        connector_style_hint="dashed",
        directed=True,
        start_px=(200.0, 300.0),
        end_px=(600.0, 300.0),
        is_dashed=True,
        stroke_width=4.0,
        color="#E6C280",
    )
    svg = generate_svg_overlay([conn], canvas_w=1920, canvas_h=1080)
    assert svg is not None
    assert '<svg xmlns="http://www.w3.org/2000/svg"' in svg
    assert '<line ' in svg
    assert 'stroke-dasharray="12,8"' in svg
    assert '<polygon ' in svg  # arrowhead


def test_staggered_entrance_and_exit_motion_events():
    """Verify nodes preserve real per-node MotionEvent entrance_sec and exit_sec."""
    timeline = {
        "episode_id": "test_staggered_ep",
        "canvas": {"width": 1920, "height": 1080},
        "total_duration_sec": 10.0,
        "segments": [{
            "beat_id": "b1",
            "start_sec": 0.0,
            "end_sec": 10.0,
            "visual_family": "paper_collage_hero",
            "transition_in": "CUT_IN",
            "transition_out": "CONTINUATION",
        }],
    }
    geo_plans = [{
        "beat_id": "b1",
        "nodes": [
            {
                "node_id": "n_hero",
                "role": "HERO",
                "asset_id": "a_hero",
                "source_layer_id": "comp_b1_hero",
            },
            {
                "node_id": "n_doc",
                "role": "DOCUMENT",
                "asset_id": "a_doc",
                "source_layer_id": "comp_b1_document",
            },
            {
                "node_id": "n_label",
                "role": "LABEL",
                "text_role": "LABEL",
                "source_layer_id": "comp_b1_headline",
            },
            {
                "node_id": "n_quote",
                "role": "QUOTE",
                "text_role": "QUOTE",
                "source_layer_id": "comp_b1_quote",
            },
        ],
        "solved_placements": [
            {
                "node_id": "n_hero",
                "bounds": {"x": 0.0, "y": 0.0, "width": 0.5, "height": 1.0},
                "z_index": 10,
            },
            {
                "node_id": "n_doc",
                "bounds": {"x": 0.5, "y": 0.0, "width": 0.5, "height": 0.5},
                "z_index": 20,
            },
            {
                "node_id": "n_label",
                "bounds": {"x": 0.05, "y": 0.05, "width": 0.4, "height": 0.2},
                "z_index": 30,
            },
            {
                "node_id": "n_quote",
                "bounds": {"x": 0.5, "y": 0.6, "width": 0.45, "height": 0.3},
                "z_index": 35,
            },
        ],
        "edges": [],
    }]
    motion_plan = {
        "plans": [{
            "beat_id": "b1",
            "camera_behavior": "stable",
            "events": [
                {
                    "layer_id": "comp_b1_hero",
                    "kind": "ENTRANCE",
                    "style": "MASK_REVEAL",
                    "start_sec": 0.0,
                    "end_sec": 0.5,
                },
                {
                    "layer_id": "comp_b1_document",
                    "kind": "ENTRANCE",
                    "style": "DOCUMENT_UNFOLD",
                    "start_sec": 3.5,
                    "end_sec": 4.0,
                },
                {
                    "layer_id": "comp_b1_document",
                    "kind": "EXIT",
                    "style": "SLIDE_OUT",
                    "start_sec": 8.0,
                    "end_sec": 8.5,
                },
                {
                    "layer_id": "comp_b1_headline",
                    "kind": "ENTRANCE",
                    "style": "UNDERLINE_REVEAL",
                    "start_sec": 1.2,
                    "end_sec": 1.6,
                },
                {
                    "layer_id": "comp_b1_quote",
                    "kind": "ENTRANCE",
                    "style": "TYPE_ON",
                    "start_sec": 4.8,
                    "end_sec": 5.2,
                },
            ],
        }],
    }
    assets = [
        {"asset_id": "a_hero", "checksum": "c_hero", "kind": "photo", "is_placeholder": False},
        {"asset_id": "a_doc", "checksum": "c_doc", "kind": "document", "is_placeholder": False},
    ]

    plan = build_episode_frame_plan(timeline, geo_plans, motion_plan, assets)
    beat = plan.beats[0]

    media_map = {m.element_id: m for m in beat.media_elements}
    text_map = {t.element_id: t for t in beat.text_elements}

    # Verify hero enters at 0.0 and stays until end (10.0)
    assert media_map["n_hero"].entrance_sec == 0.0
    assert media_map["n_hero"].exit_sec == 10.0

    # Verify document enters at 3.5s and exits at 8.0s
    assert media_map["n_doc"].entrance_sec == 3.5
    assert media_map["n_doc"].exit_sec == 8.0

    # Verify text elements have staggered entrance times
    assert text_map["n_label"].entrance_sec == 1.2
    assert text_map["n_quote"].entrance_sec == 4.8

