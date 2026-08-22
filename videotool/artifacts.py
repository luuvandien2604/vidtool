"""Deterministic intermediate artifacts (spec section 20).

Backward compatibility wrapper re-exporting ArtifactStore from videotool.pipeline.artifact_store.
"""
from __future__ import annotations

from videotool.pipeline.artifact_store import ArtifactStore

__all__ = ["ArtifactStore"]
