"""Protocol and base definitions for AI Editorial Director providers (Phase 3A)."""
from __future__ import annotations

from typing import Protocol

from videotool.editorial.director.models import (
    EditorialDirectorRequest,
    EditorialIntent,
)


class EditorialDirectorProvider(Protocol):
    """Protocol for AI Editorial Director providers."""
    provider_id: str
    model_name: str

    def generate_intent(self, request: EditorialDirectorRequest) -> EditorialIntent:
        """Generate an editorial intent for a projected beat request."""
        ...
