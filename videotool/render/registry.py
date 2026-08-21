"""Renderer registry and factory (spec section 26).

Maps renderer backend names to concrete implementation classes.
"""
from __future__ import annotations

from typing import Type

from videotool.render.ffmpeg_renderer import FFmpegRenderer
from videotool.render.interfaces import Renderer

RENDERERS: dict[str, Type[Renderer]] = {
    "ffmpeg": FFmpegRenderer,
}


def get_renderer(name: str = "ffmpeg") -> Renderer:
    """Look up and instantiate a renderer by name."""
    cls = RENDERERS.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown renderer: '{name}'. Available renderers: {list(RENDERERS.keys())}"
        )
    return cls()
