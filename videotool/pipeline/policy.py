"""Execution Policy configuration (Phase 2F Hardening).

Defines execution policy invariants (draft vs final, caching, gate thresholds).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionPolicy:
    mode: str = "final"
    force: bool = False
    max_family_streak: int = 2
    cache_enabled: bool = True

    @property
    def allow_placeholders(self) -> bool:
        return self.mode == "draft"

    @property
    def is_final(self) -> bool:
        return self.mode == "final"

    def to_dict(self) -> dict:
        return {
            "mode": self.mode,
            "force": self.force,
            "max_family_streak": self.max_family_streak,
            "cache_enabled": self.cache_enabled,
            "allow_placeholders": self.allow_placeholders,
        }
