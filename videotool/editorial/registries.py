"""Editorial Registries for extensible visual families and strategies (Phase 2F Hardening).
"""
from __future__ import annotations

from typing import Any

from videotool.domain.semantic_beat import SemanticFunction
from videotool.domain.strategy import StrategyDefinition


class FamilyRegistry:
    """Registry of available visual composition families."""

    def __init__(self):
        self._families: dict[str, Any] = {}

    def register(self, family: Any) -> None:
        self._families[family.family_id] = family

    def get(self, family_id: str) -> Any | None:
        return self._families.get(family_id)

    def all_families(self) -> dict[str, Any]:
        return dict(self._families)


class StrategyCatalogRegistry:
    """Registry of editorial strategy definitions and semantic function candidates."""

    def __init__(
        self,
        catalog: dict[str, StrategyDefinition] | None = None,
        candidates: dict[SemanticFunction, list[str]] | None = None,
    ):
        self._catalog = dict(catalog or {})
        self._candidates = dict(candidates or {})

    def get_strategy(self, strategy_id: str) -> StrategyDefinition | None:
        return self._catalog.get(strategy_id)

    def candidates_for(self, fn: SemanticFunction) -> list[str]:
        return list(self._candidates.get(fn, ["cinematic_hold"]))
