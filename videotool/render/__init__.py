"""Documentary video rendering subsystem (Phase 2D Spike).

Provides renderer-independent frame planning, ASS subtitle generation,
and concrete FFmpeg video rendering backends.
"""
from __future__ import annotations

from pathlib import Path

from videotool.artifacts import ArtifactStore
from videotool.render.ffmpeg_renderer import FFmpegRenderer, check_ffmpeg_available, probe_media_file
from videotool.render.frame_plan import (BeatFramePlan, ConnectorRenderElement,
                                         EpisodeFramePlan, Keyframe,
                                         MediaRenderElement, PixelRect,
                                         TextRenderElement,
                                         build_episode_frame_plan)
from videotool.render.interfaces import Renderer, RenderResult
from videotool.render.registry import RENDERERS, get_renderer
from videotool.render.subtitles import generate_subtitles_ass
from videotool.render.svg_overlay import generate_svg_overlay


def render_episode(episode_id: str, store: ArtifactStore, output_path: str | Path,
                   renderer_name: str = "ffmpeg") -> RenderResult:
    """Convenience entry point: loads episode artifacts, builds frame plan, and renders video."""
    # Check that required artifacts exist
    timeline = store.load(episode_id, "timeline")
    if timeline is None:
        raise FileNotFoundError(
            f"Artifact 'timeline' for episode '{episode_id}' not found in {store.episode_dir(episode_id)}. "
            f"Please run the planning pipeline first: python -m videotool.cli {episode_id}"
        )

    geometry_plans = store.load(episode_id, "semantic_geometry") or []
    motion_plan = store.load(episode_id, "motion_plan") or {}
    media_assets = store.load(episode_id, "media_assets") or []
    visual_compositions = store.load(episode_id, "visual_compositions") or []
    art_direction = store.load(episode_id, "episode_art_direction") or {}
    semantic_beats = store.load(episode_id, "semantic_beats") or []

    # Build pure-Python frame plan
    plan = build_episode_frame_plan(
        timeline=timeline,
        geometry_plans=geometry_plans,
        motion_plan=motion_plan,
        media_assets=media_assets,
        visual_compositions=visual_compositions,
        art_direction=art_direction,
        semantic_beats=semantic_beats,
    )

    # Resolve renderer and cache dir
    renderer = get_renderer(renderer_name)
    cache_dir = store.root / "media_cache"

    return renderer.render(plan, output_path, cache_dir=cache_dir)


__all__ = [
    "Renderer",
    "RenderResult",
    "FFmpegRenderer",
    "RENDERERS",
    "get_renderer",
    "EpisodeFramePlan",
    "BeatFramePlan",
    "MediaRenderElement",
    "TextRenderElement",
    "ConnectorRenderElement",
    "PixelRect",
    "Keyframe",
    "build_episode_frame_plan",
    "generate_subtitles_ass",
    "generate_svg_overlay",
    "render_episode",
    "check_ffmpeg_available",
    "probe_media_file",
]
