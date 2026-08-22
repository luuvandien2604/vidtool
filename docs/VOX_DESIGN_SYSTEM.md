# Vox Documentary Motion Graphics Design System

## 1. Executive Summary

This document specifies the Vox-style motion graphics design system and widget architecture implemented for `vidtool`.
The system provides clean, high-contrast, editorial visual communication tokens, customizable themes, and specialized vector widgets for historical timelines, milestone dates, location badges, and stat callouts.

---

## 2. Design Tokens (`videotool/render/vox_theme.py`)

### A. Color Palette Swatches

| Token Name | Hex Code | Role / Usage | Contrast Context |
|---|---|---|---|
| `BG_CREAM` | `#FAF8F5` | Primary light background | Light editorial layout |
| `BG_DARK_SLATE` | `#14171F` | Deep dark slate canvas background | Video overlay baseline |
| `BG_DARK_CARD` | `#1C202B` | Charcoal card background container | High-contrast card base |
| `ACCENT_YELLOW` | `#FFD100` | Signature Vox yellow / gold accent | Primary focus & timeline markers |
| `ACCENT_BLUE` | `#3B82F6` | Muted structural / location blue | Location badges & secondary links |
| `ACCENT_CORAL` | `#E11D48` | Muted red / coral highlight | Critical emphasis & key figures |
| `ACCENT_SAGE` | `#10B981` | Positive / verification green | Metric & status indicators |
| `TEXT_PRIMARY_LIGHT` | `#F9FAFB` | Crisp white typography | Primary text on dark cards |
| `TEXT_MUTED_LIGHT` | `#9CA3AF` | Slate secondary captions | Uppercase tracking labels |
| `BORDER_DARK` | `#374151` | Subtle container outline | 1.5px card borders |

### B. Typography Hierarchy

The font stack relies on system-verified TrueType fonts (`"DejaVu Sans, Liberation Sans, sans-serif"`):
- **Title (Large)**: `36px`, Bold (`700`)
- **Title (Medium)**: `30px`, Semibold (`600`)
- **Stat / Milestone Value**: `28px` / `22px`, Bold (`700`)
- **Body / Quote**: `20px` / `22px`, Regular / Italic
- **Uppercase Tracking Label**: `15px` (`letter-spacing: 1.2px`), Semibold (`600`)
- **Date Pill Badge**: `14px`, Bold (`700`)

---

## 3. Specialized Motion Widgets

### A. TimelineWidget (`videotool/render/widgets/timeline.py`)

Renders chronological sequences and historical milestones:
1. **Connecting Spine Line**: A dual-layered horizontal line (`stroke-width: 7.0` black shadow + `stroke-width: 3.5` `#FFD100` gold spine).
2. **Milestone Halos**: Outer ring (`r=16`, 25% opacity) + high-contrast inner core (`r=10`) + accent center dot.
3. **Date Milestone Pill**: Placed above the milestone node (`rx=15`, `#1C202B` dark background, `#FFD100` text).
4. **Event Label Card**: Placed below the milestone node (`rx=10`, `#14171F` background, left vertical accent indicator bar, drop shadow).

### B. StatBadgeWidget (`videotool/render/widgets/stat_badge.py`)

Renders key facts, standalone dates, location pins, and metric cards with pure SVG geometric vector icons:
- **`date`**: Geometric calendar outline with top binding rings and indicator dot.
- **`location`**: Smooth map pin icon with accent highlight.
- **`person` / `entity`**: Geometric user avatar vector.
- **`metric`**: Ascending 3-bar metric trend indicator.
- **Text Layout**: Two-tier card with uppercase tracking category label + large bold primary value.

---

## 4. `DATE` Role Disambiguation & Routing

To maintain strict semantic separation between timeline sequences and standalone fact callouts:
- **Timeline Routing**: When a `DATE` or `TIMELINE_NODE` is part of a `chronological_timeline` visual family or has `NodeTimeline` style in a multi-node sequence $\to$ routes to `TimelineWidget`.
- **Stat Badge Routing**: When a `DATE` node is a standalone single date fact (e.g. isolated year `"1989"`) in a non-timeline beat $\to$ routes to `StatBadgeWidget`.

---

## 5. Timed-Reveal & Overlay Architecture

- **Vector Overlay Layer (`svg_overlay.py`)**: All widget containers, geometric icons, connector spines, and milestone markers are rendered as high-precision SVG vector overlays parsed natively by FFmpeg `librsvg`.
- **Text Reveal Synchronization (`ffmpeg_renderer.py`)**: Subtitle and dialogue events respect exact `entrance_sec` and `exit_sec` offsets, ensuring seamless synchronized entrance timing without raster pixelation.
