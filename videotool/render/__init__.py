"""Documentary video rendering subsystem (Phase 2D/2E/2F).

Provides renderer-independent frame planning, ASS subtitle generation,
audio synthesis plumbing (silence + Azure Speech TTS), and concrete FFmpeg video rendering backends.
"""
from __future__ import annotations

from pathlib import Path

from videotool.artifacts import ArtifactStore
from videotool.domain.narration import Narration, NarrationAudio
from videotool.domain.timing import NarrationTiming
from videotool.providers.audio import (AUDIO_PROVIDERS,
                                       AzureSpeechAudioProvider,
                                       NarrationAudioProvider,
                                       SyntheticSilenceAudioProvider,
                                       build_audio_provider,
                                       register_audio_provider)
from videotool.render.ffmpeg_renderer import (FFmpegRenderer,
                                             check_ffmpeg_available,
                                             probe_media_file)
from videotool.render.frame_plan import (BeatFramePlan, ConnectorRenderElement,
                                         EpisodeFramePlan, Keyframe,
                                         MediaRenderElement, PixelRect,
                                         TextRenderElement,
                                         build_episode_frame_plan)
from videotool.render.interfaces import Renderer, RenderResult
from videotool.render.registry import RENDERERS, get_renderer
from videotool.render.subtitles import generate_subtitles_ass
from videotool.render.svg_overlay import generate_svg_overlay
from videotool.render.vox_theme import (DEFAULT_VOX_THEME, VoxColors,
                                        VoxSpacing, VoxTheme, VoxTypography)
from videotool.render.widgets import (StatBadgeItem, StatBadgeWidget,
                                      TimelineNodeItem, TimelineWidget)


def render_episode(episode_id: str, store: ArtifactStore, output_path: str | Path,
                   renderer_name: str = "ffmpeg",
                   audio_provider_name: str | None = "silence",
                   click_track: bool = False,
                   voice: str | None = None,
                   audio: NarrationAudio | None = None) -> RenderResult:
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

    # Audio synthesis handling
    if audio is None and audio_provider_name and audio_provider_name.lower() != "none":
        timing_data = store.load(episode_id, "narration_timing")
        narration_data = store.load(episode_id, "narration")

        if timing_data:
            timing = NarrationTiming.from_dict(timing_data)
        else:
            timing = NarrationTiming(
                words=(),
                duration_sec=plan.total_duration_sec,
                source="timeline_plan_fallback",
                provider="timeline",
                provider_version=1,
            )

        if narration_data and narration_data.get("text"):
            narration = Narration.from_dict(narration_data)
        elif timing.words:
            narration = Narration(text=" ".join(w.text for w in timing.words), words=timing.words)
        else:
            narration = Narration(text="")

        kwargs = {}
        if audio_provider_name == "silence":
            kwargs["click_track"] = click_track
        elif audio_provider_name == "azure":
            if voice:
                kwargs["voice"] = voice
            kwargs["cache_dir"] = store.root / "tts_cache"

        provider = build_audio_provider(audio_provider_name, **kwargs)
        audio_dest = store.episode_dir(episode_id) / "narration_audio.wav"
        audio = provider.synthesize(narration, timing, out_path=audio_dest, timeline=timeline)

    # Resolve renderer and cache dir
    renderer = get_renderer(renderer_name)
    cache_dir = store.root / "media_cache"

    return renderer.render(plan, output_path, cache_dir=cache_dir, audio=audio)


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
    "NarrationAudio",
    "NarrationAudioProvider",
    "SyntheticSilenceAudioProvider",
    "AzureSpeechAudioProvider",
    "AUDIO_PROVIDERS",
    "register_audio_provider",
    "build_audio_provider",
    "DEFAULT_VOX_THEME",
    "VoxTheme",
    "VoxColors",
    "VoxTypography",
    "VoxSpacing",
    "TimelineWidget",
    "TimelineNodeItem",
    "StatBadgeWidget",
    "StatBadgeItem",
]
