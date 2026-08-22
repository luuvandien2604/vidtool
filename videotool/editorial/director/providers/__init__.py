"""AI Editorial Director provider implementations (Phase 3A)."""
from __future__ import annotations

from .base import EditorialDirectorProvider
from .gemini import GeminiEditorialDirectorProvider
from .mock import MockEditorialDirectorProvider

__all__ = [
    "EditorialDirectorProvider",
    "MockEditorialDirectorProvider",
    "GeminiEditorialDirectorProvider",
    "build_director_provider",
]


def build_director_provider(provider_type: str = "mock", **kwargs) -> EditorialDirectorProvider:
    """Factory to instantiate director providers."""
    if provider_type == "mock":
        return MockEditorialDirectorProvider()
    elif provider_type == "gemini":
        return GeminiEditorialDirectorProvider(**kwargs)
    raise ValueError(f"Unknown editorial director provider type: {provider_type}")
