# Phase 2D Report: Renderer Spike

**Date**: 2026-08-21  
**Status**: Complete  
**Artifacts Generated**: `artifacts/berlin_wall.mp4` (1920x1080@30fps, 66.20s, H.264 High Profile Level 4.1, yuv420p)  
**Test Coverage**: 401 passing tests in default suite (`make test`), 3 passing tests in render suite (`make test-render`).

---

## 1. Executive Summary

Phase 2D implements the first working video renderer for the `videotool` AI Editorial Director pipeline. Prior to Phase 2D, the pipeline was strictly planning-only, producing validated semantic artifacts from narration timing to 2D semantic geometry, motion keyframes, and timeline segments without rendering pixels.

Phase 2D introduces a modular, decoupled rendering subsystem:
1. **Pure-Python Frame Plan Engine** (`videotool.render.frame_plan`): Compiles pipeline artifacts into a deterministic, renderer-agnostic representation of visual beats, media elements, positioned typography nodes, vector connectors, and motion trajectories.
2. **Subtitles & Typography Generator** (`videotool.render.subtitles`): Synthesizes styled Advanced SubStation Alpha (`.ass`) subtitle files with strict safe-zone margins and positioned text dialogue.
3. **Vector SVG Connector Engine** (`videotool.render.svg_overlay`): Synthesizes 1920x1080 SVG vector overlays for directed/undirected relationship lines, route arrows, and endpoint markers.
4. **Concrete FFmpeg Backend** (`videotool.render.ffmpeg_renderer`): Executes per-beat isolated rendering, lossless stream-copy concatenation (`-f concat -c copy`), and subtitle burn-in.
5. **CLI & Automation**: Added `videotool.cli render` subcommand and `make test-render` / `make render` Makefile targets.

---

## 2. Environment Checks

### Condition 1: `librsvg` Decoder Verification

FFmpeg codec verification executed in the runtime environment:
```bash
$ ffmpeg -codecs | grep -i svg
ffmpeg version 6.1.1-3ubuntu5 Copyright (c) 2000-2023 the FFmpeg developers
 ...
 DEV.S. svg                  Scalable Vector Graphics (decoders: librsvg)
```
Confirmed: Native `librsvg` decoder is compiled, active, and operational in the system FFmpeg build (`/usr/bin/ffmpeg`).

### Condition 2: Pinned Encode Consistency Across Beat Clips

To satisfy lossless concatenation via FFmpeg's concat demuxer (`-f concat -c copy`), every beat clip is encoded with identical, pinned stream parameters:
- **Resolution**: `1920x1080`
- **Framerate**: `30 fps` (`-r 30`)
- **Video Codec**: `libx264` (`-c:v libx264`)
- **Profile / Level**: High profile (`-profile:v high`), Level 4.1 (`-level:v 4.1`)
- **Pixel Format**: `yuv420p` (`-pix_fmt yuv420p`)
- **Preset**: `veryfast`

Structural integrity verified via `ffprobe`:
```json
{
  "streams": [
    {
      "codec_name": "h264",
      "profile": "High",
      "width": 1920,
      "height": 1080,
      "pix_fmt": "yuv420p",
      "level": 41,
      "r_frame_rate": "30/1"
    }
  ],
  "format": {
    "duration": "66.200000",
    "size": "3470610",
    "bit_rate": "419409"
  }
}
```

---

## 3. Architecture & Rendering Pipeline

The rendering system lives in `videotool/render/` with clear separation between pure-Python planning and rendering execution:

```
videotool/render/
├── __init__.py           # Public API & render_episode convenience entry point
├── interfaces.py         # Renderer Protocol & RenderResult dataclass
├── registry.py           # Renderer backend registry (RENDERERS, get_renderer)
├── frame_plan.py         # Pure-Python frame plan builder & element models
├── subtitles.py          # ASS subtitle script & positioned text dialogue builder
├── svg_overlay.py        # Vector SVG generator for VisualEdge connectors
└── ffmpeg_renderer.py    # Concrete FFmpegRenderer implementation
```

### Element Hierarchy

- **`MediaRenderElement`**: Asset-backed image elements (resolved from `MediaCache` or styled placeholder cards). Supports Ken Burns subtle pan/zoom on emphasis motion events or `slow_push` camera motions.
- **`TextRenderElement`**: Positioned non-image nodes (`LABEL`, `QUOTE`, `TIMELINE_NODE`, `EVIDENCE`). Centered at solved pixel placement coordinates `\an5\pos(cx, cy)` via ASS subtitles.
- **`ConnectorRenderElement`**: `VisualEdge` connections between nodes (`ROUTE_TO`, `CAUSES`, `BEFORE`, `QUOTED_FROM`). Synthesized to 1920x1080 SVG with solid or dashed lines and directional arrowheads.

### 3-Pass Per-Beat Rendering Strategy

1. **Beat Clip Generation**: For each beat, FFmpeg renders an isolated MP4 clip combining background slate, scaled/cropped media assets, Ken Burns motion, SVG connector overlays, and positioned node typography.
2. **Lossless Concat**: Merges all beat clips using FFmpeg's concat demuxer (`-f concat -safe 0 -c copy`) into a unified raw episode video without generational re-encoding loss.
3. **Subtitle Burn-In**: Burns bottom narration subtitles in the designated safe zone (`x=0.05, y=0.84, w=0.90, h=0.15`) using `libass` font rendering.

---

## 4. Spot-Check Visual Validation

Thumbnails were extracted at key timestamps and visually inspected:

| Beat | Timestamp | Visual Family | Elements Inspected |
|---|---|---|---|
| **Beat 3** | `15.0s` | `archival_subject` | Centered text label `Gunter Schabowski`, bottom narration subtitle safe zone |
| **Beat 4** | `22.0s` | `geographic_map` | Map asset, "Hungary" / "Austria" / "West" text nodes, red route connector line with arrowhead |
| **Beat 6** | `32.0s` | `causal_network` | "Moscow" and "East Berlin" text nodes, vertical causal directed connector line |
| **Beat 7** | `38.0s` | `document_evidence` | Document media asset, italic quote label, evidence callout connector, bottom narration subtitle |

---

## 5. Test Suite Structure

Tests are cleanly divided between fast, deterministic pure-Python tests and opt-in FFmpeg integration tests:

| Suite | Command | Markers | Test Count | Description |
|---|---|---|---|---|
| **Default Fast Suite** | `make test` | `not live_media and not render` | **401 passed** | Pure-Python unit tests covering all 18 pipeline stages, frame planning, and ASS subtitle generation. |
| **Render Suite** | `make test-render` | `render` | **3 passed** | FFmpeg prerequisite checks, registry validation, and full end-to-end video render verification. |

---

## 6. Known Limitations

1. **Silent Video Only (Phase 2D Scope Discipline)**: Audio narration synthesis and mixing remain deferred to Phase 2E. The current renderer produces silent video with burned-in subtitles.
2. **Hard Cuts Only**: Transitions between beats are hard cuts. Dissolves, wipes, and map zooms across beat boundaries will be implemented via FFmpeg xfade transition graphs.
3. **Simple Ken Burns Trajectories**: Ken Burns motion currently implements smooth linear scale adjustments (`zoompan`). Non-linear easing (smoothstep, cubic bezier) can be integrated in future motion passes.
4. **Static Vector Overlays**: Connector lines are rendered static across the beat duration rather than progressively drawing on with `ROUTE_DRAW` stroke animation.
5. **Text/connector-only families render visually sparse**: Beats resolved primarily to `TextRenderElement`/`ConnectorRenderElement` with no backing `MediaRenderElement` (observed in `causal_network` and `chronological_timeline` beats of the `berlin_wall` fixture, e.g. beat_0005 ~27s, beat_0006 ~32s) render as floating text and thin lines on an empty canvas. There is no background shape, card, or boundary to anchor a node visually — the semantic geometry solver's placement is correct, but FFmpeg's primitive drawing tools (text + line/arrow) don't give these nodes enough visual weight compared to image-backed beats. This is expected for a spike (see `svg_overlay.py`/`ConnectorRenderElement` scope), not a bug — flagged here as a scoping input for the next phase, not something to patch within this spike.

---

## 7. Next Recommended Step

1. **Higher-Fidelity Rendering Backend for Sparse Families**: Evaluate a higher-fidelity rendering backend (e.g. Remotion / React-HTML-Canvas) scoped specifically to the families found visually thin in this spike (`causal_network`, `chronological_timeline`, and any other text/connector-dominant family), routed dynamically through the `Renderer` protocol and registry (`videotool.render.registry`) established in Phase 2D. This preserves the fast, robust FFmpeg renderer for image-backed families (`archival_subject`, `geographic_map`, `document_evidence`, `full_frame_cinematic`) without requiring a wholesale replacement.
2. **Audio Track Synthesis & Mixing**: Wire narration TTS audio and background score mixing to the final video muxing pass.
3. **Transition Matrix & Route Animation**: Implement cross-beat transitions (xfade) and progressive vector stroke animations (`ROUTE_DRAW`).
