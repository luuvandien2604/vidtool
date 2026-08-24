"""Renderer interfaces and protocols (spec section 26).

Decouples pure-Python timeline/frame planning from specific rendering
backends (FFmpeg, Remotion, etc.).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Protocol

if TYPE_CHECKING:
    from videotool.domain.narration import NarrationAudio
    from videotool.render.frame_plan import EpisodeFramePlan


@dataclass(frozen=True)
class RenderResult:
    output_path: Path
    duration_sec: float
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    audio_is_placeholder: bool | None = None
    audio_path: Path | None = None


class Renderer(Protocol):
    """Protocol for concrete render backends."""
    renderer_name: str

    def render(self, plan: EpisodeFramePlan, output_path: str | Path,
               cache_dir: str | Path | None = None,
               audio: NarrationAudio | None = None,
               progress_callback: Callable[[str], None] | None = None) -> RenderResult:
        """Render an EpisodeFramePlan to a media file."""
        ...
