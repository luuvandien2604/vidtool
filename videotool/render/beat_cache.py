"""Content-addressed beat clip cache for incremental re-renders.

Each rendered beat clip is stored under a content hash derived from the
beat's full frame plan (geometry, text, media checksums, SVG overlay, etc.).
When the renderer encounters a beat whose hash matches a cached clip, it
copies the cached clip directly instead of invoking FFmpeg, skipping the
most expensive step in the pipeline.

Storage layout:
  <cache_root>/
    <hash_prefix[:2]>/
      <full_hash>.mp4          # the cached beat clip
      <full_hash>.meta.json    # optional metadata (beat_id, timestamp)
"""
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CacheResult:
    """Result of a cache lookup or store operation."""
    hit: bool
    clip_path: Path
    beat_hash: str
    beat_id: str


class BeatClipCache:
    """Durable, content-addressed cache for rendered beat clips."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._hits: list[str] = []
        self._misses: list[str] = []

    @staticmethod
    def beat_content_hash(beat_dict: dict[str, Any]) -> str:
        """Compute a deterministic content hash for a beat's frame plan.

        The hash covers everything that affects the rendered output:
        media element checksums, positions, text content, SVG overlay,
        timing, transitions, etc.
        """
        blob = json.dumps(beat_dict, sort_keys=True, ensure_ascii=False,
                          default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]

    def _dir(self, beat_hash: str) -> Path:
        return self.root / beat_hash[:2]

    def _clip_path(self, beat_hash: str) -> Path:
        return self._dir(beat_hash) / f"{beat_hash}.mp4"

    def _meta_path(self, beat_hash: str) -> Path:
        return self._dir(beat_hash) / f"{beat_hash}.meta.json"

    def lookup(self, beat_hash: str, beat_id: str) -> CacheResult | None:
        """Check if a cached clip exists for the given beat hash.

        Returns CacheResult with hit=True if found, None if not cached.
        """
        clip = self._clip_path(beat_hash)
        if clip.exists() and clip.stat().st_size > 0:
            self._hits.append(beat_id)
            return CacheResult(hit=True, clip_path=clip,
                               beat_hash=beat_hash, beat_id=beat_id)
        self._misses.append(beat_id)
        return None

    def store(self, beat_hash: str, beat_id: str,
              rendered_clip: Path) -> CacheResult:
        """Copy a freshly rendered beat clip into the durable cache."""
        dest = self._clip_path(beat_hash)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(rendered_clip), str(dest))

        meta = {"beat_id": beat_id, "beat_hash": beat_hash}
        self._meta_path(beat_hash).write_text(
            json.dumps(meta, indent=2), encoding="utf-8")

        return CacheResult(hit=False, clip_path=dest,
                           beat_hash=beat_hash, beat_id=beat_id)

    @property
    def hits(self) -> list[str]:
        """Beat IDs that were cache hits in this session."""
        return list(self._hits)

    @property
    def misses(self) -> list[str]:
        """Beat IDs that were cache misses (re-rendered) in this session."""
        return list(self._misses)

    def reset_stats(self) -> None:
        """Reset per-session hit/miss counters."""
        self._hits.clear()
        self._misses.clear()
