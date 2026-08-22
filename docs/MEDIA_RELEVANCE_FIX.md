# Media Relevance Scoring Bug Fixes Report

## 1. Executive Summary

This report documents the resolution of systemic media-matching defects identified in `videotool/editorial/media/ranking.py` and `videotool/editorial/media/query_planner.py`.

In previous renders of the `berlin_wall` documentary episode:
- Beat 3 (*Gunter Schabowski*) selected a high-resolution photo of **Fjäll cattle at Berlin Zoo** (`wikimedia:176277425`) instead of an archival human portrait.
- Beat 4 (*Hungary border opening*) selected a **1910 Austro-Hungarian ethnic composition map in Arabic script** (`wikimedia:64766890`) instead of a relevant Cold War era map.

Through metadata analysis, five distinct scoring and query construction defects were isolated and fixed in pure Python without adding heavy vision models or external dependencies.

---

## 2. Root Causes & Technical Fixes

### Fix 1: Surname extraction conflating place names with person surnames
- **Previous behavior**: `entity_match_score()` extracted surnames using `w.split()[-1]` across all entity terms in `plan.entity_terms`. For `"East Berlin"`, the last word `"berlin"` was treated as a valid person surname. As a result, any candidate mentioning Berlin in its title (including zoo animals) received a `0.6` surname entity match score.
- **Fix**: Surnames are now strictly extracted only from multi-word **person** terms (`len(term.split()) >= 2` where the term is not present in `plan.location_terms`). For location terms, matching requires full-phrase or token overlap, never surname-suffix aliasing.
- **Bonus Enhancement**: When a candidate fully matches the primary requirement entity (e.g. `"Berlin"` for a Berlin map requirement), it receives a solid `0.8` entity match even if secondary background entities in the beat are absent.

### Fix 2: Location matching lacking phrase-adjacency disambiguation
- **Previous behavior**: `location_match_score()` evaluated bag-of-words token set inclusion (`wanted <= have`). Directional phrases like `"in the east of Berlin"` matched `"East Berlin"` as `1.0` (100% location match).
- **Fix**: Location matching now enforces **exact folded phrase adjacency** (`"east berlin"` as a contiguous substring) for full credit (`1.0`). Disjoint bag-of-words token overlap without phrase match is capped at a weak partial score ($\le 0.40$).

### Fix 3: Event match circular self-satisfaction
- **Previous behavior**: When `plan.event_terms` was empty, `event_match_score()` fell back to matching tokens from the search query itself (`plan.primary_query`). Candidates were rewarded `1.0` for matching the search terms used to find them.
- **Fix**: When `plan.event_terms` is empty, `event_match_score()` returns neutral `0.5`, exactly matching the behavior of `date_match_score()` when no date is specified.

### Fix 4: Query context dropping & relational entity pairing
- **Previous behavior**: `query_planner.py` only included `entities[0]` + `kind` (`"Hungary map"`), dropping second entities (`"Austria"`) and years.
- **Fix**: Requirements with multiple entities or relational kinds maintain entity pairs in alternate queries, and 4-digit years from beat narration are preserved in `date_terms`.

### Fix 5: Language and script penalty
- **Previous behavior**: Non-Latin and foreign-language derivative assets (such as `-ar.svg` Arabic maps) had no penalty and scored `1.0` on license/source/resolution.
- **Fix**: Added `non_latin_script` soft penalty (`0.15`) in `DEFAULT_PENALTIES`. Non-Latin Unicode scripts (Arabic, Cyrillic, CJK, Hebrew) and foreign language tags receive a soft penalty, allowing Latin-script documentary assets to outrank them while retaining them as fallbacks if no other candidate exists.

### Fix 6: Unmatched portrait entity penalty
- **Fix**: For `requirement_kind == "portrait"`, candidates with missing/mismatched person entities (`entity_match < 0.5`) receive an `unmatched_portrait_entity` penalty (`0.20`), preventing non-human photos from winning on location metadata alone.

---

## 3. Before vs. After Scores

### Case 1: `req_beat_0003_portrait` (Gunter Schabowski Portrait)

| Candidate | Description | Score Before | Score After | Verdict |
|---|---|---|---|---|
| `wikimedia:1726759` | **Schabowski-portrait.jpg** (Real human portrait) | 0.5950 | **0.5950** | **#1 SELECTED** |
| `wikimedia:176277425` | **Berlin Tierpark Fjäll-Rind.jpg** (Zoo cattle) | 0.6450 | **0.3550** | **REJECTED** (-0.290 drop) |
| `wikimedia:57846205` | **Berliner Dom ... jpg** (Cathedral photo) | 0.6450 | **0.4450** | **REJECTED** |

#### Score Component Breakdown for Cattle Photo:
- `entity_match`: 0.60 $\to$ **0.20** (surname `"berlin"` removed)
- `location_match`: 1.00 $\to$ **0.40** (phrase adjacency failed: `"east of berlin"` $\ne$ `"east berlin"`)
- `penalties`: Added `unmatched_portrait_entity: 0.20`
- **Net change**: `0.6450` $\to$ **`0.3550`**

---

### Case 2: `req_beat_0004_map` (Hungary/Austria Border Map)

| Candidate | Description | Score Before | Score After | Verdict |
|---|---|---|---|---|
| `wikimedia:border_1989` | **1989 Border Opening Map** | ~0.7500 | **0.8250** | **#1 SELECTED** |
| `wikimedia:64766890` | **Austria Hungary ethnic-ar.svg** (1910 Arabic map) | 0.8001 | **0.5501** | **REJECTED** (-0.250 drop) |

#### Score Component Breakdown for 1910 Arabic Map:
- `event_match`: 1.00 $\to$ **0.50** (neutral when event_terms is empty)
- `penalties`: Added `non_latin_script: 0.15`
- **Net change**: `0.8001` $\to$ **`0.5501`**

---

## 4. Regression Test Suite

A dedicated regression test suite was created in `tests/test_media_relevance_regression.py` containing 5 test cases:
1. `test_schabowski_portrait_outscores_cattle_photo()`: Validates that `Schabowski-portrait.jpg` outscores `Berlin Tierpark Fjäll-Rind.jpg`.
2. `test_hungary_austria_1989_map_outscores_1910_arabic_map()`: Validates that 1989 Cold War map outscores 1910 Arabic map.
3. `test_location_phrase_adjacency()`: Validates that `"in the east of Berlin"` scores $\le 0.40$ for `"East Berlin"`.
4. `test_event_match_neutrality()`: Validates neutral `0.50` event score without query self-matching.
5. `test_non_latin_script_soft_penalty()`: Validates non-Latin script detection.

---

## 5. Limitations & Future Scope

While these metadata-level heuristic fixes completely solve the diagnosed failures:
- **No True Computer Vision**: A photo of a different human (e.g. another politician) with metadata claiming to be Schabowski, or an unlabeled image with misleading tags, could still score favorably.
- **Future Vision-Model Stage (Phase 4B)**: For high-stakes documentary productions, an optional secondary visual verification pass using a vision-capable LLM (e.g. Gemini Flash / Claude Sonnet) to inspect candidate thumbnail images and confirm visual subject matter can be plugged in ahead of asset acquisition.
