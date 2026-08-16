# Phase 1.2 — Artifact Integrity & Completeness Gate

Date: 2026-08-17 · No renderer added. Suite: **151 tests passed**.

## 1. Resumed artifact integrity

`stage_meta.json` now stores per stage:

```json
{"input_fingerprint": "...", "output_hash": "...", "stage_version": 1}
```

Resume requires the full chain to pass:

```
input fingerprint match -> artifact loads -> output hash matches
-> deserializes -> per-stage semantic validator passes -> RESUME
```

Any step fails -> the stage is recomputed (downstream fingerprints follow).
Both review reproductions are covered by regression tests:
`visual_motifs=[]` / `accent={}` and `selected_strategy=""` (previously a
KeyError crash) now invalidate + recompute instead of silently resuming.
Even an attacker who refreshes the output hash is caught by the stage
validator (`test_meta_consistent_corruption_caught_by_stage_validator`).

## 2. Composition completeness

`validate_compositions` now enforces: exactly one composition per beat, no
compositions for unknown beats, no duplicate compositions per beat,
composition duration == beat duration. `validate_timeline` enforces one
segment per beat and rejects `composition_id=None` in final mode.
12 beats / 11 compositions can never be final-ok — at the validator level
and at the final QC gate; deleting a composition from a persisted artifact
triggers recompute via the integrity chain (hash or stage validator, both
tested).

## 3. Media Completeness Gate (plan-of-record semantics)

`AssetRequirement.min_count` (unused) is replaced by an explicit strength
model: `REQUIRED` / `PREFERRED` / `OPTIONAL`, assigned semantically at
requirement generation (portrait for CHARACTER_INTRODUCTION, document for
EVIDENCE, map for LOCATION/GEOGRAPHIC_MOVEMENT are REQUIRED; atmosphere
photos are OPTIONAL; etc.).

After strategy feasibility the gate checks, in final mode only:

- REQUIRED requirement resolved (kind-equivalence portrait<->photo counts)?
- else: does the plan-of-record strategy still need that kind?
  - no (planner routed around, e.g. EVIDENCE -> `evidence_board` with no
    document) -> waived, reasonably
  - yes -> **Media Completeness Gate failure**, `ok=False`

Draft mode never gates (placeholders remain usable). Verified scenarios:
final + empty catalog -> not ok; draft + empty catalog -> ok;
document-less catalog -> ok because the evidence beat switched to a
no-media strategy; map-less catalog -> not ok because the location beat
cannot route around.

## 4. motion_plan + timeline validators

`validate_motion`: one plan per composition (no missing/duplicates), event
layer references valid, `start >= beat.start`, `end <= beat.end`,
`end >= start`, transitions reference existing adjacent beats with
non-negative duration. `validate_timeline`: one segment per beat in order,
final-mode segments carry a known composition, no negative/out-of-range
timing, subtitles stay inside narration duration. Both run in final QC
(`validation["motion_plan"]`, `validation["timeline"]`) and as resume
validators for their stages.

## 5-7. Cleanup

- Mode has one source of truth: `PipelineRunner.mode`. `EpisodeInput`
  carries episode data only (field removed).
- Missing strategy records for beats now get deterministic fallback records
  created (not just repairing malformed ones); per-beat composition family
  exceptions are caught and routed through the same deterministic
  composition fallback, with the family preserved.
- `FAMILIES_VERSION` is defined exactly once
  (`videotool/editorial/composition/__init__.py`); the duplicate in
  `fingerprints.py` is removed.

## 6. Packaging

`make test` → 151 passed. `make dist` → `videotool-src.zip` containing only
source (`videotool/`, `tests/`, `docs/`, config files) — no `.venv`, caches,
or generated artifacts.

## Files

```
new:      tests/test_phase12_integrity.py
modified: videotool/pipeline/runner.py        (integrity-checked resume,
          completeness/media/motion/timeline QC, mode ownership, fallbacks)
modified: videotool/pipeline/fingerprints.py  (stage_meta schema, no dup version)
modified: videotool/domain/assets.py          (strength model)
modified: videotool/editorial/validation.py   (completeness + 3 new validators)
modified: videotool/editorial/composition/__init__.py (strengths, sole
          FAMILIES_VERSION)
modified: videotool/editorial/feasibility.py  (public KIND_EQUIV)
modified: videotool/fixtures/berlin_wall.py   (mode removed from episode data)
updated:  tests/test_phase11_hardening.py, tests/test_generalization.py
          (semantics updated to Phase 1.2 gate behaviour)
```
