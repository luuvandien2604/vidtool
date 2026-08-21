"""Integration and smoke tests for the video renderer (FFmpegRenderer).

Marked with @pytest.mark.render to be excluded by default from the fast
test suite, and run via `make test-render`.
"""
from __future__ import annotations

from pathlib import Path
import pytest

from videotool.artifacts import ArtifactStore
from videotool.fixtures.berlin_wall import load_episode
from videotool.pipeline.runner import EpisodeInput, PipelineRunner
from videotool.render import (
    FFmpegRenderer,
    check_ffmpeg_available,
    get_renderer,
    probe_media_file,
    render_episode,
)


@pytest.mark.render
def test_ffmpeg_prerequisite_check():
    """Verify that FFmpeg and ffprobe availability check succeeds."""
    ok, msg = check_ffmpeg_available()
    assert ok, f"FFmpeg prerequisite check failed: {msg}"


@pytest.mark.render
def test_renderer_registry():
    """Verify renderer registry retrieves FFmpegRenderer."""
    renderer = get_renderer("ffmpeg")
    assert isinstance(renderer, FFmpegRenderer)
    assert renderer.renderer_name == "ffmpeg"

    with pytest.raises(ValueError, match="Unknown renderer"):
        get_renderer("non_existent_renderer")


@pytest.mark.render
def test_render_berlin_wall_end_to_end(tmp_path):
    """End-to-end render smoke test on the berlin_wall fixture.

    Asserts:
    1. Output MP4 file is generated.
    2. Video stream is 1920x1080 @ 30fps with h264/yuv420p.
    3. Duration matches timeline within 0.15s tolerance.
    4. Pinned encode parameters: exactly one consistent video stream without format warnings.
    5. File size is non-trivial (> 50 KB).
    """
    data = load_episode()
    store = ArtifactStore(tmp_path / "artifacts")
    runner = PipelineRunner(store, mode="draft")
    pipeline_result = runner.run(EpisodeInput(**data))
    assert pipeline_result.ok, f"Pipeline run failed: {pipeline_result.validation}"

    out_mp4 = tmp_path / "output_berlin.mp4"
    render_result = render_episode(
        episode_id=pipeline_result.episode_id,
        store=store,
        output_path=out_mp4,
        renderer_name="ffmpeg",
    )

    assert out_mp4.exists()
    assert out_mp4.stat().st_size > 50_000  # > 50 KB

    # Run ffprobe structural analysis
    meta = probe_media_file(out_mp4)
    format_info = meta.get("format", {})
    streams = meta.get("streams", [])

    # Assert exactly 1 video stream
    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    assert len(video_streams) == 1, f"Expected exactly 1 video stream, got {len(video_streams)}"

    v_stream = video_streams[0]
    assert v_stream.get("codec_name") == "h264"
    assert v_stream.get("width") == 1920
    assert v_stream.get("height") == 1080
    assert v_stream.get("pix_fmt") == "yuv420p"

    # Pinned encode parameter check (Condition 2)
    # Profile should be High and level 41 (or 4.1)
    profile = v_stream.get("profile", "")
    assert "High" in profile, f"Expected High profile, got {profile}"

    # Verify duration matches expected timeline duration
    expected_duration = pipeline_result.timeline["total_duration_sec"]
    actual_duration = float(format_info.get("duration", 0.0))
    assert abs(actual_duration - expected_duration) < 0.20, (
        f"Duration mismatch: actual {actual_duration:.2f}s vs expected {expected_duration:.2f}s"
    )
