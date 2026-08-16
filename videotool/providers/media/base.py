"""Media provider abstraction (Phase 2A spec sections 3, 5, 39).

Planning logic never touches HTTP directly; providers are replaceable and
independently testable. A simple registry is enough - no plugin framework.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:  # annotations only; avoids an import cycle at runtime
    from videotool.editorial.media.models import MediaCandidate


class FetchedMedia:
    """Raw bytes from a provider, content-type hint, never trusted."""
    __slots__ = ("data", "content_type", "media_url")

    def __init__(self, data: bytes, content_type: str = "", media_url: str = ""):
        self.data = data
        self.content_type = content_type
        self.media_url = media_url


class MediaProvider(Protocol):
    provider_id: str
    provider_version: int

    def search(self, query_text: str, limit: int) -> list[MediaCandidate]: ...

    def fetch(self, candidate: MediaCandidate) -> FetchedMedia: ...


class ProviderError(Exception):
    """Provider-level failure (network, API, malformed response)."""


class RequestPacer:
    """Single-process request pacing so we respect provider rate limits."""

    def __init__(self, min_interval_sec: float = 0.5):
        self.min_interval_sec = min_interval_sec
        self._last = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        delta = now - self._last
        if delta < self.min_interval_sec:
            time.sleep(self.min_interval_sec - delta)
        self._last = time.monotonic()


PROVIDER_REGISTRY: dict[str, type] = {}


def register_provider(cls):
    PROVIDER_REGISTRY[cls.provider_id] = cls
    return cls


def build_provider(provider_id: str, **kwargs) -> MediaProvider:
    if provider_id not in PROVIDER_REGISTRY:
        raise KeyError(f"unknown media provider '{provider_id}' "
                       f"(have: {sorted(PROVIDER_REGISTRY)})")
    return PROVIDER_REGISTRY[provider_id](**kwargs)
