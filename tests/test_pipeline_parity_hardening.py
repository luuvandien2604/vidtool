"""Comprehensive Pipeline Parity & Stage Lifecycle Tests (Hardening Phase 2F).

Verifies:
1. Clean run end-to-end creates all 19 stages.
2. Immediate rerun resumes all 19 stages without recomputation.
3. Modifying downstream configuration or input cleanly invalidates affected stages
   while caching unaffected upstream stages.
"""
from __future__ import annotations

import copy

from videotool.artifacts import ArtifactStore
from videotool.fixtures.berlin_wall import load_episode
from videotool.pipeline.runner import STAGES, EpisodeInput, PipelineRunner


def test_pipeline_full_lifecycle_parity(tmp_path):
    store = ArtifactStore(tmp_path / "artifacts")
    data = load_episode()
    ep = EpisodeInput(**data)

    # 1. Clean run: all stages computed
    runner = PipelineRunner(store, mode="final")
    res1 = runner.run(ep)
    assert res1.ok, res1.validation
    stages1 = res1.manifest["stages"]
    for s in STAGES:
        assert s in stages1
        assert stages1[s]["status"] == "computed", f"{s} should be computed on first run"

    # 2. Immediate rerun: all stages resumed
    runner2 = PipelineRunner(store, mode="final")
    res2 = runner2.run(ep)
    assert res2.ok
    stages2 = res2.manifest["stages"]
    for s in STAGES:
        assert stages2[s]["status"] == "resumed", f"{s} should resume on unchanged rerun"

    # 3. Modify planner config: strategy and downstream invalidate, upstream resumes
    from videotool.editorial.strategies import PlanningConfig
    custom_cfg = PlanningConfig(max_family_streak=1)
    runner3 = PipelineRunner(store, mode="final", planner_config=custom_cfg)
    res3 = runner3.run(ep)
    assert res3.ok
    stages3 = res3.manifest["stages"]

    # Upstream stages MUST remain resumed
    assert stages3["narration_timing"]["status"] == "resumed"
    assert stages3["semantic_beats"]["status"] == "resumed"
    assert stages3["semantic_anchors"]["status"] == "resumed"
    assert stages3["episode_art_direction"]["status"] == "resumed"
    assert stages3["asset_requirements"]["status"] == "resumed"
    assert stages3["media_search_plan"]["status"] == "resumed"
    assert stages3["media_candidates"]["status"] == "resumed"
    assert stages3["media_assets"]["status"] == "resumed"

    # Strategy plan and feasibility MUST invalidate
    assert stages3["visual_strategy_plan"]["status"] == "invalidated"
    assert stages3["strategy_feasibility"]["status"] == "invalidated"
    assert stages3["visual_compositions"]["status"] == "invalidated"
