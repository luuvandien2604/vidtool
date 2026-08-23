# Vox Documentary Motion Graphics Design System

## 1. Executive Summary

This document specifies the Vox-style motion graphics design system and widget architecture implemented for `vidtool`.
The system provides clean, high-contrast, editorial visual communication tokens, customizable themes, and specialized vector widgets for historical timelines, milestone dates, location badges, and stat callouts.

---

## 2. Design Tokens & Color Mapping Rules (`videotool/render/vox_theme.py`)

### A. Strict Color Mapping Rules

To prevent ambiguous or conflicting color overrides:

| Color Token | Hex Code | Assigned Widget Role | Rule & Scope |
|---|---|---|---|
| `ACCENT_YELLOW` | `#FFD100` | **Primary Signature Accent** | Used for all entity cards, label cards, diagram cards, quote card borders, timeline spines (horizontal & vertical), milestone halos, date pills, and metric callouts. |
| `ACCENT_BLUE` | `#3B82F6` | **Geographical Locations** | Exclusively used for `LOCATION`-role badges, city/place markers, and geographical map pins. |
| `TEXT_PRIMARY_LIGHT` | `#F9FAFB` | Primary Typography | High-contrast text on dark card backgrounds (`#1C202B` / `#14171F`). |
| `BG_DARK_CARD` | `#1C202B` | Card Containers | Charcoal background for all node cards, stat badges, and timeline event containers. |
| `BORDER_DARK` | `#374151` | Container Borders | Subtle 1.5px structural border with `#000000` drop shadow. |

> **Architectural Invariant (Art Direction Override Immunity)**:
> Vox infographic widgets (cards, timeline spines, milestone halos, location badges, stat badges) **never** read from `episode_art_direction.accent.primary`. They draw their accent colors **exclusively** from `vox_theme.py`. Photo-based beats continue using per-topic art direction for asset grading and backdrops without contaminating infographic vector graphics.

---

## 3. Typography Hierarchy

The font stack relies on system-verified TrueType fonts (`"DejaVu Sans, Liberation Sans, sans-serif"`):
- **Title (Large)**: `36px`, Bold (`700`)
- **Title (Medium)**: `30px`, Semibold (`600`)
- **Stat / Milestone Value**: `28px` / `22px`, Bold (`700`)
- **Body / Quote**: `20px` / `22px`, Regular / Italic
- **Uppercase Tracking Label**: `15px` (`letter-spacing: 1.2px`), Semibold (`600`)
- **Date Pill Badge**: `14px`, Bold (`700`)

---

## 4. Specialized Motion Widgets

### A. TimelineWidget (`videotool/render/widgets/timeline.py`)

Renders chronological sequences and historical milestones:
1. **Multi-directional Spine Support**:
   - Automatically detects orientation ($\Delta x \ge \Delta y \implies$ horizontal; $\Delta y > \Delta x \implies$ vertical).
   - Draws a dual-layer spine: black contrast shadow (`stroke-width: 7.0`) + Vox Yellow spine (`stroke-width: 3.5`, `#FFD100`).
2. **Milestone Halos & Cores**: Outer ring (`r=16`, 25% opacity) + high-contrast inner core (`r=10`, `#FFD100`) + center dot.
3. **Date Milestone Pill**: Placed above the milestone node (`rx=15`, `#1C202B` dark background, `#FFD100` text).
4. **Event Label Card**: Placed centered on node coordinates with left vertical accent indicator bar in `#FFD100` and drop shadow.

### B. StatBadgeWidget (`videotool/render/widgets/stat_badge.py`)

Renders key facts, standalone dates, location pins, and metric cards with pure SVG geometric vector icons:
- **`date`**: Geometric calendar outline with top binding rings and indicator dot (Accent: `#FFD100`).
- **`location`**: Smooth map pin icon with accent highlight (Accent: `#3B82F6`).
- **`person` / `entity`**: Geometric user avatar vector (Accent: `#FFD100`).
- **`metric`**: Ascending 3-bar metric trend indicator (Accent: `#FFD100`).
- **Text Layout**: Two-tier card with uppercase tracking category label + large bold primary value.

---

## 5. `DATE` Role Disambiguation & Routing

To maintain strict semantic separation between timeline sequences and standalone fact callouts:
- **Timeline Routing**: When a `DATE` or `TIMELINE_NODE` is part of a `chronological_timeline` visual family or has `NodeTimeline` style in a multi-node sequence $\to$ routes to `TimelineWidget`.
- **Stat Badge Routing**: When a `DATE` node is a standalone single date fact (e.g. isolated year `"1989"`) in a non-timeline beat $\to$ routes to `StatBadgeWidget`.

---

## 6. ASS Subtitle & Vector Synchronization

- **Color Encoding**: `NodeTimeline` subtitle style is pinned to `&H0000D1FF` (Vox Yellow `#FFD100` in ASS BGR format).
- **Vector Overlay Layer (`svg_overlay.py`)**: All widget containers, geometric icons, connector spines, and milestone markers are rendered as high-precision SVG vector overlays parsed natively by FFmpeg `librsvg`.
- **Text Reveal Synchronization (`ffmpeg_renderer.py`)**: Subtitle and dialogue events respect exact `entrance_sec` and `exit_sec` offsets, ensuring seamless synchronized entrance timing without raster pixelation.
