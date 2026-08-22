"""Visual history + anti-repetition domain (spec sections 10-11).

The planner must know what was recently used and penalize repetition.
Composition signatures are structural: swapping the photo must NOT defeat
repetition detection.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .composition import LayerType, VisualComposition


def derive_signature(comp: VisualComposition) -> str:
    """Deterministic structural signature of a composition.

    Derived from family, layer-type multiset, dominant (hero) layer quadrant,
    reading direction, relationship graph shape and hero asset TYPE - never
    the asset id itself, so same-layout/different-photo still collides.

    TEXTURE layers are excluded on purpose: paper grain is global brand
    styling, not composition geometry. The signature must therefore be
    identical whether it is derived before or after a texture layer is
    attached, or after any mirror transform.
    """
    def quadrant(layer) -> str:
        cx = layer.x + layer.width / 2
        cy = layer.y + layer.height / 2
        return f"{int(cy < 0.5)}{int(cx < 0.5)}"  # row-major quadrant 00..11

    layers = [l for l in comp.layers if l.type != LayerType.TEXTURE]
    type_counts: dict[str, int] = {}
    for layer in layers:
        type_counts[layer.type.value] = type_counts.get(layer.type.value, 0) + 1
    types = ",".join(f"{k}x{v}" for k, v in sorted(type_counts.items()))

    hero = _hero_layer(comp)
    hero_part = f"hero={hero.type.value}@{quadrant(hero)}" if hero else "hero=none"

    # reading direction from reading_order hero -> last positions
    direction = "none"
    if comp.reading_order and len(layers) > 1:
        first = comp.layer_by_id(comp.reading_order[0])
        last = comp.layer_by_id(comp.reading_order[-1])
        if first and last:
            dx = (last.x + last.width / 2) - (first.x + first.width / 2)
            dy = (last.y + last.height / 2) - (first.y + first.height / 2)
            direction = "LR" if abs(dx) >= abs(dy) else ("TB" if dy > 0 else "BT")

    graph = f"rel={len(comp.relationships)}:{_graph_shape(comp)}"

    hero_asset_type = "none"
    if hero is not None and hero.asset_id:
        hero_asset_type = hero.asset_id.split(":")[0] if ":" in hero.asset_id else "asset"

    return "|".join([comp.visual_family, types, hero_part, direction, graph,
                     f"asset_type={hero_asset_type}"])


def _hero_layer(comp: VisualComposition):
    for role_hint in ("hero", "support", "connector"):
        for layer in comp.layers:
            if layer.role == role_hint and layer.type != LayerType.TEXTURE:
                return layer
    # fallback: first non-texture layer; texture must never become the hero
    return next((layer for layer in comp.layers
                 if layer.type != LayerType.TEXTURE), None)


def _graph_shape(comp: VisualComposition) -> str:
    n = len(comp.relationships)
    if n == 0:
        return "flat"
    kinds = sorted({r.kind for r in comp.relationships})
    return f"{n}x{'/'.join(kinds)}"


@dataclass
class HistoryEntry:
    beat_id: str
    visual_family: str
    strategy: str
    composition_signature: str
    asset_ids: list[str] = field(default_factory=list)
    dominant_asset: str | None = None
    transition_in: str = "CONTINUATION"
    camera_behavior: str = "stable"
    color_balance: str = "neutral"
    information_density: float = 0.5

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "HistoryEntry":
        return cls(**d)


class EpisodeVisualMemory:
    """Ordered log and query engine of what the audience has recently seen."""

    def __init__(self, max_window: int = 12):
        self.entries: list[HistoryEntry] = []
        self.max_window = max_window

    # ---- queries -------------------------------------------------------
    def recent(self, n: int | None = None) -> list[HistoryEntry]:
        n = n or self.max_window
        return self.entries[-n:]

    def family_streak(self) -> tuple[str, int]:
        """(family, consecutive count ending at the latest entry)."""
        if not self.entries:
            return ("", 0)
        fam = self.entries[-1].visual_family
        streak = 0
        for e in reversed(self.entries):
            if e.visual_family == fam:
                streak += 1
            else:
                break
        return (fam, streak)

    def signature_seen_recently(self, signature: str) -> bool:
        return any(e.composition_signature == signature for e in self.recent())

    def family_recency(self, family: str) -> float:
        """Novelty of using this family now.

        1.0 = unseen in the recent window (fully novel); approaches 0.0 the
        more recently the family was on screen (back=1 -> 1/max_window).
        """
        for back, entry in enumerate(reversed(self.recent()), start=1):
            if entry.visual_family == family:
                return round(min(1.0, back / self.max_window), 4)
        return 1.0

    def signature_recency(self, signature: str) -> float:
        """Same scale as family_recency: 1.0 unseen, low = just used."""
        for back, entry in enumerate(reversed(self.recent()), start=1):
            if entry.composition_signature == signature:
                return round(min(1.0, back / self.max_window), 4)
        return 1.0

    def dominant_asset_recent(self, asset_id: str) -> bool:
        return any(e.dominant_asset == asset_id for e in self.recent(6))

    # ---- mutation ------------------------------------------------------
    def record(self, entry: HistoryEntry) -> None:
        self.entries.append(entry)
        if len(self.entries) > self.max_window * 3:
            self.entries = self.entries[-self.max_window * 2:]

    # ---- persistence ---------------------------------------------------
    def to_dict(self) -> dict:
        return {"schema_version": 1, "entries": [e.to_dict() for e in self.entries]}

    @classmethod
    def from_dict(cls, d: dict) -> "EpisodeVisualMemory":
        h = cls()
        h.entries = [HistoryEntry.from_dict(e) for e in d.get("entries", [])]
        return h


class VisualHistory(EpisodeVisualMemory):
    """Backward compatibility alias for EpisodeVisualMemory."""
    pass


class NoveltyScorer:
    """Calculates visual novelty scores against visual memory."""

    @staticmethod
    def score_family_novelty(memory: EpisodeVisualMemory, family: str) -> float:
        return memory.family_recency(family)

    @staticmethod
    def score_signature_novelty(memory: EpisodeVisualMemory, signature: str) -> float:
        return memory.signature_recency(signature)

