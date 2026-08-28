# Vox Paper Collage Visual Engine

## 1. Overview & Central Design Question

The Vox Paper Collage Visual Engine brings the signature aesthetic of modern documentary motion graphics (seen in Vox, Johnny Harris, and Lemmino) to `videotool`.

### Central Design Question & Architectural Answer

**Question:** Is the paper-collage look (a) a universal default template wrapping all beats, or (b) a dedicated composition family (`paper_collage_hero`) selected situationally alongside existing visual families?

**Architectural Decision:** **(b) A dedicated composition family (`paper_collage_hero`) + modular collage overlay primitives reusable across all visual families.**

### Rationale:
- **Editorial Pacing & Rhythm**: Documentary storytelling requires visual dynamic range. Universal left-sidebar wrapping on every 4-second cut induces visual fatigue and crowds out full-bleed maps, wide diagrams, and cinematic footage.
- **Composition Geometry Integration**:
  - `paper_collage_hero` is formally recognized by the geometry and strategy planners.
  - When active (e.g. Chapter Openers, Major Contextual Explanations, Thesis Statements), the canvas is structured into:
    - **Left Sidebar Panel ($x \in [0, 0.40]$)**: Procedural torn paper mask, chapter badge, bold headline, brush stroke, context text, gold fact box.
    - **Center Hero Layer ($x \in [0, 1.0]$)**: Full-bleed archival photograph with Ken Burns slow push.
    - **Right Inset Panel ($x \in [0.65, 0.96]$)**: Taped map card or secondary document.
    - **Bottom Highlight Banner ($x \in [0.25, 0.75]$)**: High-impact quote banner.
- **Modular Reusability**: The 7 SVG paper-collage primitives are available modularly in `videotool.render.vox_collage` so that other families (e.g. `geographic_map` or `document_evidence`) can incorporate tape strip decorations and gold fact callouts without forcing the left sidebar.

---

## 2. The 7 SVG & Render Primitives

1. **Procedural Torn-Paper Edge Mask (`generate_torn_paper_path`)**:
   - Creates a jagged, organic ripped edge along the right side of the left panel.
   - 100% deterministic: seeded by `beat_id` so that repeated renders produce identical byte-exact vector output.
2. **Vintage Paper Texture & Drop Shadow**:
   - Aged paper gradient (`#FAF8F5` $\to$ `#E7E0D2`) with drop shadow filter (`<feDropShadow dx="8" dy="4" stdDeviation="10" flood-opacity="0.6"/>`) casting a realistic shadow onto the underlying hero image.
3. **Chapter Pill Badge (`generate_chapter_pill_svg`)**:
   - Dark pill `#111111` with gold outline `#E1B400` and uppercase cream text (`CHƯƠNG 1`).
   - Derived directly from `SemanticBeat.chapter` or beat sequence ordering.
4. **Condensed Headline with Yellow Brush-Stroke Accent (`generate_brush_stroke_svg`)**:
   - Bold condensed typography (`DejaVu Sans / Liberation Sans`, weight 800).
   - Tapered procedural brush stroke polygon underneath in signature Vox Yellow (`#E1B400` / `#FFD100`).
5. **Framed Gold Fact Box (`generate_gold_fact_box_svg`)**:
   - High-contrast milestone container with gold border `#E1B400`, dark background `#121212`, date in bold gold, title, and subtitle.
   - Integrates with `StatBadgeWidget` and caption-grounding data.
6. **Tape Strip Decorations (`generate_tape_strip_svg`)**:
   - Semi-transparent rotated rectangles (`fill="rgba(248,246,230,0.65)"`, stroke `"rgba(220,213,188,0.5)"`, rotated $-15^\circ$ to $+12^\circ$) with soft shadow on inset corners.
7. **Bottom Quote Banner with Highlighted Keywords (`generate_quote_banner_svg`)**:
   - Dark brush container across bottom-center.
   - Substring keyword parsing into `<tspan>` elements with gold accent color `#E1B400`.

---

## 3. Keyword-Highlighting Grounding Mechanism

Keyword emphasis in the quote banner operates through a two-tier mechanism:

1. **AI-Enabled Grounding Path**:
   - When AI editorial director / caption authoring is enabled, explicit emphasis tokens (or key claim concepts) from `EditorialIntent` are used as the highlighted keywords.
2. **Deterministic Non-AI Fallback Path**:
   - When AI is disabled (e.g. deterministic fixture mode / offline render), the system matches named entities, dates, and locations already present in `SemanticBeat.entities` against the quote string.
   - Guarantees that keyword highlighting functions consistently without requiring an active AI API connection.

---

## 4. Recorded Architectural Decision: AI Imagery Labeling

- **Decision**: In future phases (Phase B & C) where AI-generated imagery may be used to supplement historical archival photography, **no on-screen "AI-generated" watermark or badge will be rendered**.
- This is a deliberate, recorded architectural decision reflecting the editorial requirement for clean, unencumbered cinematic presentation.
