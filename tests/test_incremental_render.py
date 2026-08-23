"""Tests proving incremental per-beat re-render via BeatClipCache.

Renders berlin_wall once (cold cache — all 12 beats rendered), applies a
single-beat editorial override, re-renders, and asserts:
1. Only the affected beat was re-rendered (cache miss).
2. All other beats were reused from cache (cache hits).
3. The final video is still valid.
"""
from __future__ import annotations

import json
from pathlib import Path
import pytest

from videotool.artifacts import ArtifactStore
from videotool.fixtures import berlin_wall
from videotool.pipeline.runner import EpisodeInput, PipelineRunner
from videotool.render import render_episode
from videotool.render.beat_cache import BeatClipCache


@pytest.fixture
def planned_episode(tmp_path: Path):
    """Run the planning pipeline for berlin_wall in draft mode."""
    store = ArtifactStore(str(tmp_path / "artifacts"))
    runner = PipelineRunner(store=store, mode="draft")
    ep_data = berlin_wall.load_episode()
    runner.run(EpisodeInput(**ep_data))
    return store, ep_data["episode_id"]


@pytest.mark.render
def test_incremental_rerender_only_changed_beat(planned_episode, tmp_path: Path):
    """After a cold render, modifying one beat's override should only re-render that beat."""
    store, episode_id = planned_episode
    out_path_1 = tmp_path / "render_1.mp4"
    out_path_2 = tmp_path / "render_2.mp4"

    # -- First render: cold cache, all beats should be cache misses --
    result1 = render_episode(
        episode_id=episode_id,
        store=store,
        output_path=out_path_1,
        renderer_name="ffmpeg",
        audio_provider_name="silence",
    )

    assert out_path_1.exists()
    assert result1.duration_sec > 0
    # All beats should be cache misses on first render
    assert result1.metadata.get("beats_rendered") == 12
    assert result1.metadata.get("beats_reused") == 0

    # -- Apply a single-beat editorial override to beat_0004 --
    overrides = [
        {
            "override_id": "test_partial_rerender",
            "beat_id": "beat_0004",
            "target_id": "semantic:beat_0004:connector_endpoint:01",
            "field": "caption",
            "old_value": "Hungary",
            "new_value": "Hungarian border opened",
        }
    ]
    overrides_path = store.episode_dir(episode_id) / "editorial_overrides.json"
    overrides_path.write_text(json.dumps(overrides, indent=2), encoding="utf-8")

    # -- Second render: warm cache, only beat_0004 should be re-rendered --
    result2 = render_episode(
        episode_id=episode_id,
        store=store,
        output_path=out_path_2,
        renderer_name="ffmpeg",
        audio_provider_name="silence",
    )

    assert out_path_2.exists()
    assert result2.duration_sec > 0

    # Exactly 1 beat should be re-rendered (beat_0004)
    assert result2.metadata.get("beats_rendered") == 1, (
        f"Expected 1 beat re-rendered, got {result2.metadata.get('beats_rendered')}. "
        f"Misses: {result2.metadata.get('beat_cache_misses')}"
    )
    # The other 11 beats should be cache hits
    assert result2.metadata.get("beats_reused") == 11, (
        f"Expected 11 beats reused from cache, got {result2.metadata.get('beats_reused')}. "
        f"Hits: {result2.metadata.get('beat_cache_hits')}"
    )

    # The re-rendered beat should be beat_0004
    assert "beat_0004" in result2.metadata.get("beat_cache_misses", [])

    # All other beats should be hits
    hits = result2.metadata.get("beat_cache_hits", [])
    for beat_id in ["beat_0001", "beat_0002", "beat_0003",
                    "beat_0005", "beat_0006", "beat_0007",
                    "beat_0008", "beat_0009", "beat_0010",
                    "beat_0011", "beat_0012"]:
        assert beat_id in hits, f"{beat_id} should be a cache hit but wasn't"


@pytest.mark.render
def test_beat_clip_cache_unit(tmp_path: Path):
    """Unit test for BeatClipCache: store, lookup, and stats."""
    cache = BeatClipCache(tmp_path / "beat_cache")

    beat_dict = {"beat_id": "beat_0001", "duration_sec": 5.0, "text": "hello"}
    beat_hash = BeatClipCache.beat_content_hash(beat_dict)

    # Initially empty
    assert cache.lookup(beat_hash, "beat_0001") is None
    assert cache.misses == ["beat_0001"]
    assert cache.hits == []

    # Store a fake clip
    fake_clip = tmp_path / "fake_beat.mp4"
    fake_clip.write_bytes(b"\x00" * 100)
    result = cache.store(beat_hash, "beat_0001", fake_clip)
    assert result.hit is False
    assert result.clip_path.exists()

    # Now lookup should hit
    cache.reset_stats()
    cached = cache.lookup(beat_hash, "beat_0001")
    assert cached is not None
    assert cached.hit is True
    assert cache.hits == ["beat_0001"]
    assert cache.misses == []

    # Different content should miss
    different_dict = {"beat_id": "beat_0001", "duration_sec": 5.0, "text": "changed"}
    different_hash = BeatClipCache.beat_content_hash(different_dict)
    assert cache.lookup(different_hash, "beat_0001") is None
    assert cache.misses == ["beat_0001"]
