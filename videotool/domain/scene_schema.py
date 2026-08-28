"""Declarative Scene Schema (Phase 1).

Allows defining high-fidelity historical documentary scenes via declarative YAML
specifications with complete provenance, asset licenses, and animations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AssetSource:
    title: str = ""
    page_url: str = ""
    official_archive_url: str = ""
    date: str = ""
    description: str = ""
    terms_url: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> AssetSource:
        known = {"title", "page_url", "official_archive_url", "date", "description", "terms_url"}
        kws = {k: v for k, v in d.items() if k in known}
        extra = {k: v for k, v in d.items() if k not in known}
        return cls(**kws, extra=extra)


@dataclass
class AssetLicense:
    name: str = ""
    url: str = ""
    attribution: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> AssetLicense:
        known = {"name", "url", "attribution"}
        kws = {k: v for k, v in d.items() if k in known}
        extra = {k: v for k, v in d.items() if k not in known}
        return cls(**kws, extra=extra)


@dataclass
class AssetUsage:
    start: float = 0.0
    end: float = 0.0
    position: dict[str, Any] = field(default_factory=dict)
    opacity: float = 1.0
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> AssetUsage:
        known = {"start", "end", "position", "opacity"}
        kws = {k: v for k, v in d.items() if k in known}
        extra = {k: v for k, v in d.items() if k not in known}
        return cls(**kws, extra=extra)


@dataclass
class AssetAnimation:
    enter: dict[str, Any] = field(default_factory=dict)
    motion: dict[str, Any] = field(default_factory=dict)
    exit: dict[str, Any] = field(default_factory=dict)
    effects: list[str] = field(default_factory=list)
    overlays: list[Any] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> AssetAnimation:
        known = {"enter", "motion", "exit", "effects", "overlays"}
        kws = {k: v for k, v in d.items() if k in known}
        extra = {k: v for k, v in d.items() if k not in known}
        return cls(**kws, extra=extra)


@dataclass
class SceneAsset:
    id: str
    type: str  # archival_photo, vector_map_data, etc.
    role: str  # primary_visual, secondary_visual, contextual_insert, etc.
    source: AssetSource = field(default_factory=AssetSource)
    license: AssetLicense = field(default_factory=AssetLicense)
    usage: AssetUsage = field(default_factory=AssetUsage)
    animation: AssetAnimation = field(default_factory=AssetAnimation)

    @classmethod
    def from_dict(cls, d: dict) -> SceneAsset:
        src = AssetSource.from_dict(d.get("source", {}))
        lic = AssetLicense.from_dict(d.get("license", {}))
        usage = AssetUsage.from_dict(d.get("usage", {}))
        anim = AssetAnimation.from_dict(d.get("animation", {}))
        return cls(
            id=d["id"],
            type=d.get("type", "archival_photo"),
            role=d.get("role", "primary_visual"),
            source=src,
            license=lic,
            usage=usage,
            animation=anim,
        )


@dataclass
class SceneNarration:
    text: str = ""
    start: float = 0.0
    end: float = 0.0


@dataclass
class SceneDateCard:
    date: str = ""
    title: str = ""
    subtitle: str = ""


@dataclass
class SceneQuote:
    text: str = ""
    emphasis: list[str] = field(default_factory=list)


@dataclass
class SceneGraphics:
    chapter_label: dict[str, Any] = field(default_factory=dict)
    headline: dict[str, Any] = field(default_factory=dict)
    date_card: SceneDateCard = field(default_factory=SceneDateCard)
    quote: SceneQuote = field(default_factory=SceneQuote)

    @classmethod
    def from_dict(cls, d: dict) -> SceneGraphics:
        dc_data = d.get("date_card", {})
        dc = SceneDateCard(**dc_data) if isinstance(dc_data, dict) else SceneDateCard()
        q_data = d.get("quote", {})
        q = SceneQuote(**q_data) if isinstance(q_data, dict) else SceneQuote()
        return cls(
            chapter_label=d.get("chapter_label", {}),
            headline=d.get("headline", {}),
            date_card=dc,
            quote=q,
        )


@dataclass
class SceneSpec:
    version: str
    project: dict[str, Any]
    scene: dict[str, Any]
    style: dict[str, Any]
    license_policy: dict[str, Any]
    assets: list[SceneAsset]
    layout: dict[str, Any]
    graphics: SceneGraphics
    timeline: list[dict[str, Any]]
    credits: list[str]
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> SceneSpec:
        assets = [SceneAsset.from_dict(a) for a in d.get("assets", [])]
        graphics = SceneGraphics.from_dict(d.get("graphics", {}))
        return cls(
            version=str(d.get("version", "2.0")),
            project=d.get("project", {}),
            scene=d.get("scene", {}),
            style=d.get("style", {}),
            license_policy=d.get("license_policy", {}),
            assets=assets,
            layout=d.get("layout", {}),
            graphics=graphics,
            timeline=d.get("timeline", []),
            credits=d.get("credits", []),
            notes=d.get("notes", []),
        )
