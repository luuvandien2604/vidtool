"""Renderer interfaces and protocols (spec section 26).

Decouples pure-Python timeline/frame planning from specific rendering
backends (FFmpeg, Remotion, etc.).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from videotool.render.frame_plan import EpisodeFramePlan


@dataclass(frozen=True)
class RenderResult:
    output_path: Path
    duration_sec: float
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class Renderer(Protocol):
    """Protocol for concrete render backends."""
    renderer_name: str

    def render(self, plan: EpisodeFramePlan, output_path: str | Path,
               cache_dir: str | Path | None = None) -> RenderResult:
        """Render an EpisodeFramePlan to a media file."""
        ...
