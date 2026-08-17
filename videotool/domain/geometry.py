"""Renderer-independent semantic geometry planning models (Phase 2C.1)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum


class VisualRole(str, Enum):
    HERO = "HERO"
    SUPPORT = "SUPPORT"
    CONTEXT = "CONTEXT"
    EVIDENCE = "EVIDENCE"
    LABEL = "LABEL"
    QUOTE = "QUOTE"
    DATE = "DATE"
    LOCATION = "LOCATION"
    MAP = "MAP"
    DOCUMENT = "DOCUMENT"
    PORTRAIT = "PORTRAIT"
    ARCHIVAL_IMAGE = "ARCHIVAL_IMAGE"
    TIMELINE_NODE = "TIMELINE_NODE"
    DATA = "DATA"
    CONNECTOR_ENDPOINT = "CONNECTOR_ENDPOINT"
    BACKGROUND = "BACKGROUND"
    DECORATIVE = "DECORATIVE"


class TextRole(str, Enum):
    TITLE = "TITLE"
    LABEL = "LABEL"
    CAPTION = "CAPTION"
    QUOTE = "QUOTE"
    DATE = "DATE"
    NUMBER = "NUMBER"
    LOCATION = "LOCATION"
    ANNOTATION = "ANNOTATION"


class CanvasRegion(str, Enum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    TOP = "TOP"
    BOTTOM = "BOTTOM"
    CENTER = "CENTER"
    CENTER_LEFT = "CENTER_LEFT"
    CENTER_RIGHT = "CENTER_RIGHT"
    TOP_LEFT = "TOP_LEFT"
    TOP_RIGHT = "TOP_RIGHT"
    BOTTOM_LEFT = "BOTTOM_LEFT"
    BOTTOM_RIGHT = "BOTTOM_RIGHT"
    FULL = "FULL"


class ConstraintStrength(str, Enum):
    HARD = "HARD"
    STRONG = "STRONG"
    MEDIUM = "MEDIUM"
    WEAK = "WEAK"


class ConstraintType(str, Enum):
    INSIDE_CANVAS = "INSIDE_CANVAS"
    OUTSIDE_SAFE_ZONE = "OUTSIDE_SAFE_ZONE"
    MIN_SIZE = "MIN_SIZE"
    MAX_SIZE = "MAX_SIZE"
    ASPECT_RATIO = "ASPECT_RATIO"
    PREFER_REGION = "PREFER_REGION"
    AVOID_REGION = "AVOID_REGION"
    NEAR = "NEAR"
    FAR_FROM = "FAR_FROM"
    ALIGN = "ALIGN"
    STACK = "STACK"
    ORDER_LEFT_TO_RIGHT = "ORDER_LEFT_TO_RIGHT"
    ORDER_TOP_TO_BOTTOM = "ORDER_TOP_TO_BOTTOM"
    NO_OVERLAP = "NO_OVERLAP"
    CONTAINED_IN = "CONTAINED_IN"
    CONNECT = "CONNECT"
    ANCHOR_TO = "ANCHOR_TO"
    GROUP = "GROUP"
    BALANCE = "BALANCE"
    READING_ORDER = "READING_ORDER"


class EdgeType(str, Enum):
    CAUSES = "CAUSES"
    LEADS_TO = "LEADS_TO"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    LOCATED_IN = "LOCATED_IN"
    PART_OF = "PART_OF"
    BEFORE = "BEFORE"
    AFTER = "AFTER"
    COMPARES_WITH = "COMPARES_WITH"
    CONTRASTS_WITH = "CONTRASTS_WITH"
    EVIDENCE_FOR = "EVIDENCE_FOR"
    QUOTED_FROM = "QUOTED_FROM"
    ROUTE_TO = "ROUTE_TO"


@dataclass(frozen=True)
class NormalizedRect:
    x: float
    y: float
    width: float
    height: float

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "NormalizedRect":
        return cls(**payload)


@dataclass(frozen=True)
class CanvasSpec:
    aspect_ratio: float = 16 / 9
    width_norm: float = 1.0
    height_norm: float = 1.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "CanvasSpec":
        return cls(**payload)


@dataclass(frozen=True)
class SafeZone:
    zone_id: str
    purpose: str
    bounds: NormalizedRect
    critical_content_allowed: bool = False

    def to_dict(self) -> dict:
        return {**asdict(self), "bounds": self.bounds.to_dict()}

    @classmethod
    def from_dict(cls, payload: dict) -> "SafeZone":
        data = dict(payload)
        data["bounds"] = NormalizedRect.from_dict(data["bounds"])
        return cls(**data)


@dataclass
class VisualNode:
    node_id: str
    beat_id: str
    role: VisualRole
    semantic_refs: list[str] = field(default_factory=list)
    asset_id: str | None = None
    media_kind: str = ""
    importance: float = 0.5
    salience: float = 0.5
    preferred_regions: list[CanvasRegion] = field(default_factory=list)
    forbidden_regions: list[CanvasRegion] = field(default_factory=list)
    min_width: float = 0.08
    min_height: float = 0.05
    preferred_aspect_ratio: float | None = None
    can_crop: bool = True
    can_scale: bool = True
    can_rotate: bool = False
    text_density: float = 0.0
    reading_priority: int = 0
    timing_anchor_id: str | None = None
    text_role: TextRole | None = None
    estimated_width: float | None = None
    estimated_height: float | None = None
    max_lines: int | None = None
    source_layer_id: str | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["role"] = self.role.value
        data["preferred_regions"] = [region.value for region in self.preferred_regions]
        data["forbidden_regions"] = [region.value for region in self.forbidden_regions]
        data["text_role"] = self.text_role.value if self.text_role else None
        return data

    @classmethod
    def from_dict(cls, payload: dict) -> "VisualNode":
        data = dict(payload)
        data["role"] = VisualRole(data["role"])
        data["preferred_regions"] = [CanvasRegion(value) for value in
                                     data.get("preferred_regions", [])]
        data["forbidden_regions"] = [CanvasRegion(value) for value in
                                     data.get("forbidden_regions", [])]
        data["text_role"] = (TextRole(data["text_role"])
                             if data.get("text_role") else None)
        return cls(**data)


@dataclass
class VisualEdge:
    edge_id: str
    source_node_id: str
    target_node_id: str
    relationship_type: EdgeType
    importance: float = 0.7
    directed: bool = True
    connector_style_hint: str = ""
    reason: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["relationship_type"] = self.relationship_type.value
        return data

    @classmethod
    def from_dict(cls, payload: dict) -> "VisualEdge":
        data = dict(payload)
        data["relationship_type"] = EdgeType(data["relationship_type"])
        return cls(**data)


@dataclass
class VisualGroup:
    group_id: str
    node_ids: list[str]
    semantic_role: str
    importance: float
    preferred_region: CanvasRegion | None = None
    internal_layout_hint: str = ""
    reason: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["preferred_region"] = (self.preferred_region.value
                                    if self.preferred_region else None)
        return data

    @classmethod
    def from_dict(cls, payload: dict) -> "VisualGroup":
        data = dict(payload)
        data["preferred_region"] = (CanvasRegion(data["preferred_region"])
                                    if data.get("preferred_region") else None)
        return cls(**data)


@dataclass
class VisualHierarchy:
    primary_node_id: str
    secondary_node_ids: list[str] = field(default_factory=list)
    tertiary_node_ids: list[str] = field(default_factory=list)
    reading_order: list[str] = field(default_factory=list)
    reading_direction: str = "LEFT_TO_RIGHT"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "VisualHierarchy":
        return cls(**payload)


@dataclass
class GeometryConstraint:
    constraint_id: str
    constraint_type: ConstraintType
    node_ids: list[str]
    strength: ConstraintStrength
    weight: float
    parameters: dict = field(default_factory=dict)
    reason: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["constraint_type"] = self.constraint_type.value
        data["strength"] = self.strength.value
        return data

    @classmethod
    def from_dict(cls, payload: dict) -> "GeometryConstraint":
        data = dict(payload)
        data["constraint_type"] = ConstraintType(data["constraint_type"])
        data["strength"] = ConstraintStrength(data["strength"])
        return cls(**data)


@dataclass(frozen=True)
class GeometryStyleHints:
    density: float = 0.5
    asymmetry: float = 0.5
    preferred_reading_direction: str = "LEFT_TO_RIGHT"
    margin_scale: float = 1.0
    overlap_tolerance: float = 0.0
    grouping_tightness: float = 0.7
    geometry_character: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "GeometryStyleHints":
        return cls(**payload)


@dataclass
class GeometryPlan:
    beat_id: str
    visual_family: str
    nodes: list[VisualNode]
    groups: list[VisualGroup]
    edges: list[VisualEdge]
    hierarchy: VisualHierarchy
    constraints: list[GeometryConstraint]
    canvas: CanvasSpec
    safe_zones: list[SafeZone]
    style_hints: GeometryStyleHints
    semantic_geometry_signature: str
    recent_geometry_context: list[str] = field(default_factory=list)
    is_fallback: bool = False
    repair_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "beat_id": self.beat_id,
            "visual_family": self.visual_family,
            "nodes": [node.to_dict() for node in self.nodes],
            "groups": [group.to_dict() for group in self.groups],
            "edges": [edge.to_dict() for edge in self.edges],
            "hierarchy": self.hierarchy.to_dict(),
            "constraints": [constraint.to_dict()
                            for constraint in self.constraints],
            "canvas": self.canvas.to_dict(),
            "safe_zones": [zone.to_dict() for zone in self.safe_zones],
            "style_hints": self.style_hints.to_dict(),
            "semantic_geometry_signature": self.semantic_geometry_signature,
            "recent_geometry_context": list(self.recent_geometry_context),
            "is_fallback": self.is_fallback,
            "repair_reason": self.repair_reason,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "GeometryPlan":
        return cls(
            beat_id=payload["beat_id"],
            visual_family=payload["visual_family"],
            nodes=[VisualNode.from_dict(item) for item in payload.get("nodes", [])],
            groups=[VisualGroup.from_dict(item) for item in payload.get("groups", [])],
            edges=[VisualEdge.from_dict(item) for item in payload.get("edges", [])],
            hierarchy=VisualHierarchy.from_dict(payload["hierarchy"]),
            constraints=[GeometryConstraint.from_dict(item)
                         for item in payload.get("constraints", [])],
            canvas=CanvasSpec.from_dict(payload["canvas"]),
            safe_zones=[SafeZone.from_dict(item)
                        for item in payload.get("safe_zones", [])],
            style_hints=GeometryStyleHints.from_dict(payload["style_hints"]),
            semantic_geometry_signature=payload["semantic_geometry_signature"],
            recent_geometry_context=list(payload.get("recent_geometry_context", [])),
            is_fallback=payload.get("is_fallback", False),
            repair_reason=payload.get("repair_reason", ""),
        )


class GeometryHistory:
    """Recent semantic structure only; never stores solved coordinates."""

    def __init__(self, signatures: list[str] | None = None,
                 max_window: int = 5):
        self.signatures = list(signatures or [])
        self.max_window = max_window

    def recent(self) -> list[str]:
        return self.signatures[-self.max_window:]

    def record(self, signature: str) -> None:
        self.signatures.append(signature)

    def to_dict(self) -> dict:
        return {"signatures": list(self.signatures),
                "max_window": self.max_window}

    @classmethod
    def from_dict(cls, payload: dict) -> "GeometryHistory":
        return cls(payload.get("signatures", []), payload.get("max_window", 5))
