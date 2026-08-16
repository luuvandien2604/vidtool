"""Generative composition model.

A VisualComposition is a layered, normalized-space description of what the
viewer sees during one beat and how it assembles over time. It is renderer
agnostic: the renderer consumes resolved timeline/composition plans only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class LayerType(str, Enum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    TEXT = "TEXT"
    LABEL = "LABEL"
    DOCUMENT = "DOCUMENT"
    MAP = "MAP"
    LINE = "LINE"
    ARROW = "ARROW"
    STRING = "STRING"
    SHAPE = "SHAPE"
    MASK = "MASK"
    TEXTURE = "TEXTURE"
    ICON = "ICON"
    CHART = "CHART"
    SUBTITLE_SAFE_ZONE = "SUBTITLE_SAFE_ZONE"


class MotionStyle(str, Enum):
    PAPER_SLIDE = "PAPER_SLIDE"
    SNAP_IN = "SNAP_IN"
    MASK_REVEAL = "MASK_REVEAL"
    UNDERLINE_REVEAL = "UNDERLINE_REVEAL"
    DOCUMENT_UNFOLD = "DOCUMENT_UNFOLD"
    ROUTE_DRAW = "ROUTE_DRAW"
    MARKER_LINE = "MARKER_LINE"
    PIN_CONNECT = "PIN_CONNECT"
    TYPE_ON = "TYPE_ON"
    PLACE_PHOTO = "PLACE_PHOTO"
    SCALE_EMPHASIS = "SCALE_EMPHASIS"
    CUT_IN = "CUT_IN"
    COLLAPSE = "COLLAPSE"
    SLIDE_OUT = "SLIDE_OUT"
    DISSOLVE = "DISSOLVE"


@dataclass
class CompositionLayer:
    id: str
    type: LayerType
    x: float  # normalized 0..1
    y: float
    width: float
    height: float
    rotation: float = 0.0
    z_index: int = 0
    asset_id: str | None = None
    role: str = ""            # hero / support / connector / caption / texture / chart ...
    text: str | None = None
    entrance: MotionStyle = MotionStyle.SNAP_IN
    emphasis: MotionStyle | None = None
    exit: MotionStyle = MotionStyle.SLIDE_OUT
    enter_at: float = 0.0     # fraction of beat duration when the layer enters
    reason: str = ""          # why this layer exists / why it moves now

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["type"] = self.type.value
        d["entrance"] = self.entrance.value
        d["emphasis"] = self.emphasis.value if self.emphasis else None
        d["exit"] = self.exit.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "CompositionLayer":
        d = dict(d)
        d["type"] = LayerType(d["type"])
        d["entrance"] = MotionStyle(d["entrance"])
        d["emphasis"] = MotionStyle(d["emphasis"]) if d.get("emphasis") else None
        d["exit"] = MotionStyle(d["exit"])
        return cls(**d)


@dataclass
class Relationship:
    from_layer: str
    to_layer: str
    kind: str  # connects / points_to / contrasts / annotates / groups
    label: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "Relationship":
        return cls(**d)


@dataclass
class EntranceStep:
    layer_id: str
    offset_sec: float  # absolute offset from composition start
    style: str
    reason: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, d: dict) -> "EntranceStep":
        return cls(**d)


@dataclass
class VisualComposition:
    composition_id: str
    beat_id: str
    visual_family: str
    strategy: str
    canvas: dict = field(default_factory=lambda: {"width": 1920, "height": 1080, "aspect": "16:9"})
    layers: list[CompositionLayer] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    focus_target: str = ""
    reading_order: list[str] = field(default_factory=list)
    entrance_sequence: list[EntranceStep] = field(default_factory=list)
    exit_sequence: list[EntranceStep] = field(default_factory=list)
    transition_in: str = "CONTINUATION"
    transition_out: str = "CONTINUATION"
    duration_sec: float = 0.0
    novelty_signature: str = ""
    composition_reason: str = ""   # why this arrangement (graph shape, asset mix, history)
    is_fallback: bool = False

    def layer_by_id(self, layer_id: str) -> CompositionLayer | None:
        return next((l for l in self.layers if l.id == layer_id), None)

    def to_dict(self) -> dict:
        return {
            "composition_id": self.composition_id,
            "beat_id": self.beat_id,
            "visual_family": self.visual_family,
            "strategy": self.strategy,
            "canvas": self.canvas,
            "layers": [l.to_dict() for l in self.layers],
            "relationships": [r.to_dict() for r in self.relationships],
            "focus_target": self.focus_target,
            "reading_order": self.reading_order,
            "entrance_sequence": [s.to_dict() for s in self.entrance_sequence],
            "exit_sequence": [s.to_dict() for s in self.exit_sequence],
            "transition_in": self.transition_in,
            "transition_out": self.transition_out,
            "duration_sec": self.duration_sec,
            "novelty_signature": self.novelty_signature,
            "composition_reason": self.composition_reason,
            "is_fallback": self.is_fallback,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VisualComposition":
        return cls(
            composition_id=d["composition_id"],
            beat_id=d["beat_id"],
            visual_family=d["visual_family"],
            strategy=d["strategy"],
            canvas=dict(d.get("canvas", {})),
            layers=[CompositionLayer.from_dict(l) for l in d.get("layers", [])],
            relationships=[Relationship.from_dict(r) for r in d.get("relationships", [])],
            focus_target=d.get("focus_target", ""),
            reading_order=list(d.get("reading_order", [])),
            entrance_sequence=[EntranceStep.from_dict(s) for s in d.get("entrance_sequence", [])],
            exit_sequence=[EntranceStep.from_dict(s) for s in d.get("exit_sequence", [])],
            transition_in=d.get("transition_in", "CONTINUATION"),
            transition_out=d.get("transition_out", "CONTINUATION"),
            duration_sec=d.get("duration_sec", 0.0),
            novelty_signature=d.get("novelty_signature", ""),
            composition_reason=d.get("composition_reason", ""),
            is_fallback=d.get("is_fallback", False),
        )
