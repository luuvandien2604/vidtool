"""AI Editorial Director package (Phase 3A).

Provides strongly typed editorial intent models, deterministic request projection,
strict validation gates, and provider integrations.
"""
from __future__ import annotations

from .director import EditorialDirector
from .fallback import build_fallback_intent
from .models import (
    EditorialDirectorRequest,
    EditorialIntent,
    StrategyDescriptor,
    ValidationResult,
)
from .projector import EditorialContextProjector
from .prompt import EDITORIAL_DIRECTOR_PROMPT_VERSION
from .providers import (
    EditorialDirectorProvider,
    GeminiEditorialDirectorProvider,
    MockEditorialDirectorProvider,
    build_director_provider,
)
from .validator import validate_editorial_intent

__all__ = [
    "EditorialDirector",
    "EditorialDirectorRequest",
    "EditorialIntent",
    "StrategyDescriptor",
    "ValidationResult",
    "EditorialContextProjector",
    "EditorialDirectorProvider",
    "MockEditorialDirectorProvider",
    "GeminiEditorialDirectorProvider",
    "build_director_provider",
    "validate_editorial_intent",
    "build_fallback_intent",
    "EDITORIAL_DIRECTOR_PROMPT_VERSION",
]
