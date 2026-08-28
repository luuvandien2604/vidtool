"""Vox-style design tokens and theme definitions for motion graphics and widgets.

Provides editorial color palettes, typography scale, spacing constants,
and geometric styling tokens for infographics, timeline steps, and stat badges.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class VoxColors:
    """Core editorial color tokens inspired by modern documentary motion graphics."""
    # Backgrounds
    BG_CREAM: str = "#FAF8F5"
    BG_CREAM_WARM: str = "#F3EFE6"
    BG_PAPER_LIGHT: str = "#FAF8F5"
    BG_PAPER_AGED: str = "#E7E0D2"
    BG_PAPER_DARK: str = "#161616"
    BG_DARK_SLATE: str = "#14171F"
    BG_DARK_CARD: str = "#1C202B"
    BG_DARK_OVERLAY: str = "#0F121A"

    # Accents & Highlights
    ACCENT_YELLOW: str = "#FFD100"       # Signature Vox yellow / gold
    ACCENT_GOLD: str = "#E1B400"         # Deep documentary gold accent
    ACCENT_MUSTARD: str = "#E5B800"
    ACCENT_BLUE: str = "#3B82F6"          # Secondary regional / structural accent
    ACCENT_BLUE_DEEP: str = "#2563EB"
    ACCENT_CORAL: str = "#E11D48"         # Emphasis / point of interest
    ACCENT_CORAL_DARK: str = "#BE123C"
    ACCENT_SAGE: str = "#10B981"          # Positive / verified indicator
    MAP_BLUE: str = "#24384A"             # Primary territory / allied map zone
    MAP_RED: str = "#6B302D"              # Opposing territory / eastern map zone

    # Typography & Text
    TEXT_PRIMARY_DARK: str = "#111827"   # Near-black on light backgrounds
    TEXT_SECONDARY_DARK: str = "#374151" # Charcoal secondary text
    TEXT_MUTED_DARK: str = "#6B7280"     # Slate captions / labels
    TEXT_PRIMARY_LIGHT: str = "#F9FAFB"  # Crisp white on dark backgrounds
    TEXT_SECONDARY_LIGHT: str = "#D1D5DB"
    TEXT_MUTED_LIGHT: str = "#9CA3AF"
    TEXT_PAPER_CREAM: str = "#E7E0D2"

    # Borders, Outlines & Shadows
    BORDER_LIGHT: str = "#E5E7EB"
    BORDER_DARK: str = "#374151"
    BORDER_ACCENT: str = "#FFD100"
    BORDER_GOLD: str = "#E1B400"
    SHADOW_COLOR: str = "#000000"


@dataclass(frozen=True)
class VoxTypography:
    """Typography tokens with verified system font fallback chains."""
    # System font stack verified available on render host (DejaVu Sans, Liberation Sans)
    FONT_FAMILY_PRIMARY: str = "DejaVu Sans, Liberation Sans, sans-serif"
    FONT_FAMILY_MONO: str = "DejaVu Sans Mono, Liberation Mono, monospace"

    # Font Sizes in Pixels (for 1080p canvas)
    SIZE_TITLE_XL: int = 44
    SIZE_TITLE_LG: int = 36
    SIZE_TITLE_MD: int = 30
    SIZE_TITLE_SM: int = 24
    SIZE_VALUE_LG: int = 28
    SIZE_VALUE_MD: int = 22
    SIZE_BODY: int = 20
    SIZE_BODY_SM: int = 17
    SIZE_LABEL_UPPER: int = 15
    SIZE_BADGE: int = 14
    SIZE_CAPTION: int = 12
    SIZE_CAPTION: int = 12

    # Font Weights
    WEIGHT_BOLD: int = 700
    WEIGHT_SEMIBOLD: int = 600
    WEIGHT_REGULAR: int = 400


@dataclass(frozen=True)
class VoxSpacing:
    """Spacing, radius, and line weight tokens for 1920x1080 canvas."""
    # Paddings & Margins
    PAD_XS: float = 6.0
    PAD_SM: float = 10.0
    PAD_MD: float = 16.0
    PAD_LG: float = 24.0
    PAD_XL: float = 32.0

    # Corner Radii
    RADIUS_SM: float = 6.0
    RADIUS_MD: float = 10.0
    RADIUS_LG: float = 16.0
    RADIUS_PILL: float = 999.0

    # Line & Stroke Widths
    STROKE_THIN: float = 2.0
    STROKE_STANDARD: float = 3.5
    STROKE_THICK: float = 5.0
    STROKE_OUTLINE: float = 7.0

    # Widget Dimensions
    BADGE_ICON_SIZE: float = 40.0
    TIMELINE_NODE_RADIUS: float = 10.0
    TIMELINE_HALO_RADIUS: float = 16.0
    ACCENT_BAR_WIDTH: float = 6.0


@dataclass
class VoxTheme:
    """Aggregated theme configuration for rendering components."""
    colors: VoxColors = field(default_factory=VoxColors)
    typography: VoxTypography = field(default_factory=VoxTypography)
    spacing: VoxSpacing = field(default_factory=VoxSpacing)

    def resolve_color(self, val: str | None, default: str | None = None) -> str:
        """Resolve a color string or semantic key to a validated hex color."""
        if not val:
            return default or self.colors.ACCENT_YELLOW
        if val.startswith("#") and len(val) in (4, 7, 9):
            return val
        key = val.upper().replace("-", "_")
        if hasattr(self.colors, key):
            return getattr(self.colors, key)
        return default or self.colors.ACCENT_YELLOW


# Global default theme singleton
DEFAULT_VOX_THEME = VoxTheme()
