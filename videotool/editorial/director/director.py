"""AI Editorial Director coordinator (Phase 3A).

Coordinates request projection, provider execution, strict validation,
and graceful fallback generation per semantic beat.
"""
from __future__ import annotations

import logging
from typing import Any

from videotool.editorial.director.fallback import build_fallback_intent
from videotool.editorial.director.models import (
    EditorialDirectorRequest,
    EditorialIntent,
    ValidationResult,
)
from videotool.editorial.director.providers import (
    EditorialDirectorProvider,
    MockEditorialDirectorProvider,
)
from videotool.editorial.director.validator import validate_editorial_intent

logger = logging.getLogger(__name__)


class EditorialDirector:
    """Coordinates AI proposal generation and validation for editorial decisions."""

    def __init__(self, provider: EditorialDirectorProvider | None = None):
        self.provider = provider or MockEditorialDirectorProvider()

    def propose(
        self,
        request: EditorialDirectorRequest,
        catalog: dict[str, Any] | None = None,
        families: dict[str, Any] | None = None,
    ) -> tuple[EditorialIntent, ValidationResult]:
        """Generate and validate an editorial proposal for a single beat request."""
        # 1. Call provider with robust exception handling
        try:
            raw_intent = self.provider.generate_intent(request)
        except Exception as exc:
            logger.warning(
                "Editorial director provider '%s' failed on beat '%s': %s",
                self.provider.provider_id,
                request.beat_id,
                exc,
            )
            fallback_intent = build_fallback_intent(
                request, reason=f"Provider '{self.provider.provider_id}' error: {exc}"
            )
            val_res = ValidationResult(
                is_valid=False,
                accepted_strategies=[],
                rejected_strategies=[],
                rejection_reasons=[f"Provider exception: {type(exc).__name__}: {exc}"],
            )
            return fallback_intent, val_res

        # 2. Strict validation against deterministic domain rules
        val_res = validate_editorial_intent(raw_intent, request, catalog, families)

        # 3. If proposal is valid (has at least 1 viable candidate), return it
        if val_res.is_valid:
            # Prune any rejected strategies from intent candidate list
            raw_intent.candidate_strategies = val_res.accepted_strategies
            return raw_intent, val_res

        # 4. If proposal is unrecoverably invalid, return deterministic fallback
        reason_summary = "; ".join(val_res.rejection_reasons)
        logger.info(
            "Editorial proposal for beat '%s' rejected by validator: %s",
            request.beat_id,
            reason_summary,
        )
        fallback_intent = build_fallback_intent(
            request, reason=f"Validation failed: {reason_summary}"
        )
        return fallback_intent, val_res
