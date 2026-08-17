"""Central semantic geometry and deterministic text measurement policy."""
from __future__ import annotations

from dataclasses import dataclass

from videotool.domain.composition import LayerType
from videotool.domain.geometry import (CanvasRegion, ConstraintStrength,
                                       GeometryStyleHints, NormalizedRect,
                                       SafeZone, TextRole, VisualRole)


@dataclass(frozen=True)
class GeometryPolicy:
    edge_margin: float = 0.04
    hard_weight: float = 1.0
    strong_weight: float = 0.85
    medium_weight: float = 0.60
    weak_weight: float = 0.35
    recent_history_window: int = 5

    def safe_zones(self) -> list[SafeZone]:
        return [
            SafeZone("subtitle_safe_zone", "subtitles",
                     NormalizedRect(0.05, 0.84, 0.90, 0.15)),
            SafeZone("edge_safe_zone", "content-safe frame inside edge margins",
                     NormalizedRect(0.04, 0.04, 0.92, 0.92), True),
            SafeZone("title_safe_zone", "opening title reserve",
                     NormalizedRect(0.05, 0.04, 0.90, 0.12)),
        ]

    def strength_weight(self, strength: ConstraintStrength) -> float:
        return {
            ConstraintStrength.HARD: self.hard_weight,
            ConstraintStrength.STRONG: self.strong_weight,
            ConstraintStrength.MEDIUM: self.medium_weight,
            ConstraintStrength.WEAK: self.weak_weight,
        }[strength]

    def min_size(self, role: VisualRole) -> tuple[float, float]:
        return {
            VisualRole.HERO: (0.30, 0.28),
            VisualRole.PORTRAIT: (0.24, 0.34),
            VisualRole.DOCUMENT: (0.28, 0.34),
            VisualRole.MAP: (0.40, 0.34),
            VisualRole.QUOTE: (0.28, 0.12),
            VisualRole.LABEL: (0.12, 0.045),
            VisualRole.DATE: (0.10, 0.045),
            VisualRole.LOCATION: (0.12, 0.045),
            VisualRole.TIMELINE_NODE: (0.04, 0.04),
            VisualRole.CONNECTOR_ENDPOINT: (0.03, 0.03),
            VisualRole.BACKGROUND: (1.0, 1.0),
            VisualRole.DECORATIVE: (0.02, 0.02),
        }.get(role, (0.10, 0.06))

    def importance(self, role: VisualRole) -> float:
        return {
            VisualRole.HERO: 0.95,
            VisualRole.EVIDENCE: 0.92,
            VisualRole.DOCUMENT: 0.88,
            VisualRole.MAP: 0.88,
            VisualRole.PORTRAIT: 0.90,
            VisualRole.QUOTE: 0.92,
            VisualRole.TIMELINE_NODE: 0.72,
            VisualRole.DATA: 0.78,
            VisualRole.SUPPORT: 0.62,
            VisualRole.LOCATION: 0.58,
            VisualRole.DATE: 0.52,
            VisualRole.LABEL: 0.48,
            VisualRole.CONTEXT: 0.45,
            VisualRole.CONNECTOR_ENDPOINT: 0.55,
            VisualRole.BACKGROUND: 0.10,
            VisualRole.DECORATIVE: 0.08,
        }.get(role, 0.5)

    def salience(self, role: VisualRole) -> float:
        return {
            VisualRole.HERO: 0.95,
            VisualRole.QUOTE: 0.90,
            VisualRole.PORTRAIT: 0.88,
            VisualRole.DOCUMENT: 0.82,
            VisualRole.MAP: 0.78,
            VisualRole.EVIDENCE: 0.86,
            VisualRole.DATA: 0.78,
            VisualRole.TIMELINE_NODE: 0.62,
            VisualRole.SUPPORT: 0.55,
            VisualRole.LOCATION: 0.48,
            VisualRole.DATE: 0.40,
            VisualRole.LABEL: 0.42,
            VisualRole.CONTEXT: 0.36,
            VisualRole.CONNECTOR_ENDPOINT: 0.38,
            VisualRole.BACKGROUND: 0.08,
            VisualRole.DECORATIVE: 0.06,
        }.get(role, 0.5)

    def regions(self, role: VisualRole) -> list[CanvasRegion]:
        return {
            VisualRole.HERO: [CanvasRegion.CENTER, CanvasRegion.CENTER_LEFT],
            VisualRole.PORTRAIT: [CanvasRegion.LEFT, CanvasRegion.CENTER_LEFT],
            VisualRole.DOCUMENT: [CanvasRegion.RIGHT, CanvasRegion.CENTER_RIGHT],
            VisualRole.MAP: [CanvasRegion.CENTER, CanvasRegion.FULL],
            VisualRole.QUOTE: [CanvasRegion.RIGHT, CanvasRegion.CENTER],
            VisualRole.DATE: [CanvasRegion.TOP_RIGHT, CanvasRegion.TOP],
            VisualRole.LOCATION: [CanvasRegion.TOP_LEFT, CanvasRegion.TOP],
            VisualRole.LABEL: [CanvasRegion.TOP, CanvasRegion.CENTER_RIGHT],
            VisualRole.BACKGROUND: [CanvasRegion.FULL],
        }.get(role, [CanvasRegion.CENTER])

    def crop_policy(self, role: VisualRole, media_kind: str) -> tuple[bool, bool]:
        if role in {VisualRole.DOCUMENT, VisualRole.MAP} \
                or media_kind in {"document", "map"}:
            return False, False
        if role == VisualRole.PORTRAIT or media_kind == "portrait":
            return True, False
        return True, False

    def text_role(self, layer_type: LayerType, role: VisualRole,
                  text: str) -> TextRole | None:
        if layer_type not in {LayerType.TEXT, LayerType.LABEL}:
            return None
        if role == VisualRole.QUOTE or '"' in text or "“" in text:
            return TextRole.QUOTE
        if any(char.isdigit() for char in text):
            return TextRole.DATE if len(text) <= 16 else TextRole.NUMBER
        if role == VisualRole.LOCATION:
            return TextRole.LOCATION
        return TextRole.LABEL if layer_type == LayerType.LABEL else TextRole.CAPTION

    def measure_text(self, text: str, text_role: TextRole
                     ) -> tuple[float, float, float, int]:
        policy = {
            TextRole.TITLE: (24, 2, 0.56, 0.13),
            TextRole.QUOTE: (34, 4, 0.52, 0.11),
            TextRole.DATE: (14, 1, 0.20, 0.055),
            TextRole.NUMBER: (16, 2, 0.24, 0.08),
            TextRole.LOCATION: (20, 2, 0.28, 0.065),
            TextRole.LABEL: (24, 2, 0.32, 0.06),
            TextRole.CAPTION: (36, 3, 0.48, 0.07),
            TextRole.ANNOTATION: (28, 3, 0.38, 0.06),
        }[text_role]
        chars_per_line, max_lines, preferred_width, line_height = policy
        lines = max(1, min(max_lines,
                           (len(text.strip()) + chars_per_line - 1)
                           // chars_per_line))
        density = round(min(1.0, len(text.strip()) / max(1, chars_per_line * max_lines)), 3)
        return preferred_width, round(line_height * lines, 3), density, max_lines

    def reading_direction(self, beat, visual_family: str,
                          geometry_character: list[str],
                          hierarchy: list[str],
                          recent_context: list[str]) -> str:
        """Choose semantic flow without using coordinates or randomness."""
        del hierarchy
        if visual_family == "chronological_timeline":
            return "CHRONOLOGICAL_HORIZONTAL"
        if visual_family == "causal_network":
            return "CAUSE_TO_EFFECT"
        if visual_family == "geographic_map":
            return ("ROUTE_FLOW" if len(beat.locations) > 1
                    or beat.semantic_function.value == "GEOGRAPHIC_MOVEMENT"
                    else "SPATIAL_FOCUS")
        if visual_family == "full_frame_cinematic":
            return "OVERLAY_HIERARCHY"
        corpus = " ".join(geometry_character).lower()
        if any(hint in corpus for hint in ("right-to-left", "rtl", "right anchored")):
            return "RIGHT_TO_LEFT"
        if any(hint in corpus for hint in ("left-to-right", "ltr", "left anchored")):
            return "LEFT_TO_RIGHT"
        # Editorial history deterministically alternates portrait/document bias.
        rtl_count = sum("reading=RIGHT_TO_LEFT" in item
                        for item in recent_context)
        ltr_count = sum("reading=LEFT_TO_RIGHT" in item
                        for item in recent_context)
        return "RIGHT_TO_LEFT" if rtl_count < ltr_count else "LEFT_TO_RIGHT"

    def style_hints(self, information_density: float,
                    geometry_character: list[str],
                    preferred_reading_direction: str) -> GeometryStyleHints:
        corpus = " ".join(geometry_character).lower()
        asymmetry = 0.75 if any(word in corpus for word in
                                ("asymmetric", "off-axis", "divided")) else 0.45
        margin_scale = 0.85 if "grid" in corpus or "technical" in corpus else 1.0
        return GeometryStyleHints(
            density=max(0.0, min(1.0, information_density)),
            asymmetry=asymmetry,
            preferred_reading_direction=preferred_reading_direction,
            margin_scale=margin_scale,
            overlap_tolerance=0.0,
            grouping_tightness=0.8,
            geometry_character=list(geometry_character),
        )
