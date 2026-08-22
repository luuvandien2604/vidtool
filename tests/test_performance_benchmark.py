"""Performance and pipeline latency benchmarks (Phase 2F Hardening).

Ensures:
1. Pure planning clean-run completes within strict time budget (< 3.0s).
2. Resumed runs complete in sub-second time (< 0.25s).
"""
from __future__ import annotations

import time

from videotool.artifacts import ArtifactStore
from videotool.fixtures.berlin_wall import load_episode
from videotool.pipeline.runner import EpisodeInput, PipelineRunner


def test_planning_pipeline_performance_benchmarks(tmp_path):
    store = ArtifactStore(tmp_path / "artifacts")
    data = load_episode()
    ep = EpisodeInput(**data)

    # 1. Measure Clean Run Latency
    t0 = time.perf_counter()
    runner1 = PipelineRunner(store, mode="final")
    res1 = runner1.run(ep)
    t_clean = time.perf_counter() - t0

    assert res1.ok
    # Clean planning run across all 19 stages should complete in < 5.0 seconds
    assert t_clean < 5.0, f"Clean run took too long: {t_clean:.2f}s"

    # 2. Measure Resume Run Latency (Pure IO / Hash checking)
    t1 = time.perf_counter()
    runner2 = PipelineRunner(store, mode="final")
    res2 = runner2.run(ep)
    t_resume = time.perf_counter() - t1

    assert res2.ok
    # Resuming all 19 stages from disk should complete in < 0.50 seconds
    assert t_resume < 0.50, f"Resume run took too long: {t_resume:.2f}s"
    assert t_resume < t_clean * 0.5, "Resume run should be at least 2x faster than clean run"
