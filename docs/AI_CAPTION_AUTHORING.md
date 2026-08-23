# AI-Authored Captions, Shooting Script, and Feedback Revision Loop

This document outlines the architecture, data models, anti-hallucination grounding gates, shooting script artifact formats, and two-step human feedback revision loop in `videotool`.

---

## 1. Overview & Architectural Philosophy

The **AI Editorial Director** serves an advisory role in the production pipeline:
- Proposing concise, narrative-driven node captions/labels (replacing raw extracted entity tokens like `"Hungary"` with `"Borders opened through Hungary"`).
- Providing machine-readable (`shooting_script.json`) and human-readable (`shooting_script.md`) shooting scripts before full video render.
- Facilitating an audited, feedback-driven revision loop where human directors can submit free-text critiques, preview structured before/after diffs, and apply changes into durable `editorial_overrides.json` files.

---

## 2. Anti-Hallucination Grounding Validator

To prevent generative hallucinations from entering documentary infographics, every proposed caption must pass the **Strict Grounding Validator** (`videotool.editorial.director.caption_validator:validate_caption`).

```
Proposed Caption
       │
       ▼
[Length Gate] ────────────► Exceeds 8 words? ─────────► REJECT -> Fallback to Raw
       │
       ▼
[Factual Extraction] (Proper nouns, years, numbers, places)
       │
       ▼
[Corpus Verification] ────► Not in Beat Narration/Meta? ──► REJECT -> Fallback to Raw
       │
       ▼
   ACCEPTED: [ai_authored]
```

### Validation Rules:
1. **Length Constraint**: Node labels must be 1–8 words (targeting 2–6 words). Quotes must be 1–30 words.
2. **Proper Noun & Number Grounding**: Every proper noun (capitalized entity), number, date, or specific geographical location in the caption must appear (verbatim or as a recognized entity substring) in that beat's `narration_text` or semantic metadata (`entities`, `locations`, `dates`, `events`).
3. **Rejection & Fallback**: If rejected, the reason is logged, and the system automatically falls back to deterministic raw entity string extraction (`source: [raw]`).
4. **Legacy Parity**: When `editorial_ai_enabled=False` (default), 100% of text elements use raw deterministic extraction with zero LLM queries.

---

## 3. Shooting Script Artifacts

The system produces two synchronized shooting script artifacts:

### 3.1. Machine-Readable Source of Truth (`shooting_script.json`)
Contains a full hierarchical manifest of all beats and elements:
```json
{
  "episode_id": "berlin_wall_phase1",
  "total_duration_sec": 66.21,
  "beats": [
    {
      "beat_id": "beat_0004",
      "start_sec": 19.02,
      "end_sec": 26.02,
      "duration_sec": 7.00,
      "visual_family": "geographic_map",
      "strategy": "route_map",
      "narration_text": "Hungary had opened its border with Austria...",
      "elements": [
        {
          "index": 2,
          "element_id": "semantic:beat_0004:connector_endpoint:01",
          "element_type": "Text badge (LOCATION)",
          "role": "CONNECTOR_ENDPOINT",
          "display_content": "**\"Borders opened through Hungary\"**",
          "content_source": "[override]",
          "bounds_norm": "0.18,0.30,0.05,0.05",
          "entrance_sec": 19.02,
          "exit_sec": 26.02,
          "motion": "fade-in ~0.4s",
          "connects_to": "→ 03 (`ROUTE_TO`)",
          "semantic_reason": "anchor 'Hungary'"
        }
      ]
    }
  ]
}
```

### 3.2. Human-Readable 13-Column Markdown Table (`shooting_script.md`)
Rendered directly from the YAML structure into a comprehensive table:
| # | Element ID | Loại | Nội dung hiển thị | Nguồn nội dung | Asset/nguồn ảnh | Vùng đặt | Tọa độ (x,y,w,h) | Vào lúc | Ra lúc | Chuyển động | Nối tới | Lý do (semantic) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `semantic:beat_0004:map:00` | Media (map) | *(ảnh map: escape routes)* | archive | `media:2230124494f5d1a1` | CENTER | 0.08,0.08,0.84,0.66 | 0:19.02 | 0:26.02 | stable | — | importance 0.88 |
| 2 | `semantic:beat_0004:connector_endpoint:01` | Text badge (LOCATION) | **"Borders opened through Hungary"** | [override] | — | CENTER | 0.18,0.30,0.05,0.05 | 0:19.02 | 0:26.02 | fade-in ~0.4s | → 03 (`ROUTE_TO`) | anchor 'Hungary' |

---

## 4. Feedback-Driven Revision Loop

Directors can refine on-screen graphics via CLI:

### Step 1: Propose Revision
```bash
python -m videotool.cli revise berlin_wall --feedback "Beat 4: caption Hungary nên gợi cảm hơn"
```
Output:
```
================================================================================
                      EDITORIAL REVISION PROPOSAL
================================================================================
Proposal ID:   prop_fc92cf5f
Target Beat:   beat_0004
Target Node:   semantic:beat_0004:connector_endpoint:01
Field:         caption
Feedback Text: "Beat 4: caption Hungary nên gợi cảm hơn"
--------------------------------------------------------------------------------
Status:        VALID (Grounded)
Before:        "Hungary"
After:         "Borders opened through Hungary"
Rationale:     Refined Hungary location badge to describe border opening
--------------------------------------------------------------------------------
To apply this change, run:
  python -m videotool.cli revise berlin_wall --apply prop_fc92cf5f
================================================================================
```

### Step 2: Apply Revision
```bash
python -m videotool.cli revise berlin_wall --apply prop_fc92cf5f
```
Persists the approved patch into `artifacts/<episode_id>/editorial_overrides.json`.

---

## 5. Invalidation & Incremental Execution Policy

- **Fingerprinting**: `editorial_overrides.json` is hashed into stage fingerprints (`visual_strategy_plan`, `composition`, `semantic_geometry`).
- **Incremental Re-render**: Each beat clip is cached in a durable, content-addressed store (`beat_clip_cache/`) keyed by the SHA-256 hash of the beat's full frame plan (geometry, media checksums, text content, SVG overlay). On re-render after an override change, only beats whose frame-plan hash has changed are re-rendered by FFmpeg — unchanged beats reuse their cached clip files. The concat and subtitle burn-in steps always run (they are fast). Cache hit/miss stats are reported in `RenderResult.metadata` (`beats_reused`, `beats_rendered`, `beat_cache_hits`, `beat_cache_misses`).
