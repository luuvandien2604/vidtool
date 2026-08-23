"""Tests for shooting script generator (JSON and 13-column Markdown tables)."""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from videotool.artifacts import ArtifactStore
from videotool.fixtures import berlin_wall
from videotool.pipeline.runner import EpisodeInput, PipelineRunner
from videotool.render.frame_plan import build_episode_frame_plan
from videotool.render.shooting_script import generate_shooting_script


@pytest.fixture
def planned_artifacts(tmp_path: Path):
    store = ArtifactStore(str(tmp_path / "artifacts"))
    runner = PipelineRunner(store=store, mode="draft")
    ep_data = berlin_wall.load_episode()
    runner.run(EpisodeInput(**ep_data))
    return store, ep_data["episode_id"]


def test_shooting_script_generation(planned_artifacts, tmp_path: Path):
    store, episode_id = planned_artifacts

    timeline = store.load(episode_id, "timeline")
    geo_plans = store.load(episode_id, "semantic_geometry") or []
    motion_plan = store.load(episode_id, "motion_plan") or {}
    media_assets = store.load(episode_id, "media_assets") or []
    visual_comps = store.load(episode_id, "visual_compositions") or []
    art_dir = store.load(episode_id, "episode_art_direction") or {}
    semantic_beats = store.load(episode_id, "semantic_beats") or []

    plan = build_episode_frame_plan(
        timeline=timeline,
        geometry_plans=geo_plans,
        motion_plan=motion_plan,
        media_assets=media_assets,
        visual_compositions=visual_comps,
        art_direction=art_dir,
        semantic_beats=semantic_beats,
    )

    out_json = tmp_path / "test_script.json"
    out_md = tmp_path / "test_script.md"

    script_data, md_text = generate_shooting_script(
        plan=plan,
        timeline=timeline,
        semantic_beats=semantic_beats,
        geometry_plans=geo_plans,
        media_assets=media_assets,
        visual_compositions=visual_comps,
        out_json_path=out_json,
        out_md_path=out_md,
    )

    assert out_json.is_file()
    assert out_md.is_file()

    # Verify JSON structure
    with open(out_json, "r", encoding="utf-8") as f:
        loaded_json = json.load(f)

    assert loaded_json["episode_id"] == episode_id
    assert len(loaded_json["beats"]) == len(semantic_beats)
    for beat in loaded_json["beats"]:
        assert "beat_id" in beat
        assert "narration_text" in beat
        assert "elements" in beat
        for el in beat["elements"]:
            assert "element_id" in el
            assert "element_type" in el
            assert "content_source" in el
            assert "entrance_sec" in el

    # Verify Markdown contains the 13 required columns
    assert "# Shooting Script:" in md_text
    assert "| # | Element ID | Loại | Nội dung hiển thị | Nguồn nội dung | Asset/nguồn ảnh | Vùng đặt | Tọa độ (x,y,w,h) | Vào lúc | Ra lúc | Chuyển động | Nối tới | Lý do (semantic) |" in md_text
    assert "### Beat 01" in md_text
    assert "*Chuyển cảnh tiếp theo:" in md_text
