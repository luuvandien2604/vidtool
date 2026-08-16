# Phase 1.1 Hardening Report

Date: 2026-08-17 · Follows the external review of Phase 1. Scope: lock the
five reported issues before any renderer work. No renderer was added.

Test suite: **122 passed** (`make test`).

## 1. Artifact fingerprinting + dependency invalidation (the critical bug)

**Before:** resume only checked "artifact file exists" — changing the subject
while keeping `episode_id` reused the stale Berlin art direction.

**Now:** every stage persists an input fingerprint in `stage_meta.json`
(content hash of episode inputs + upstream payload + stage version +
config). Resume happens only when fingerprints match exactly:

```
stage fingerprint = H(stage_version, episode_id, own inputs..., parent hash)
```

Because fingerprints chain through parents, a change invalidates exactly the
dependent stages — and nothing else:

| Change | Invalidates | Keeps |
|---|---|---|
| subject | episode_art_direction → visual_compositions → history/motion/timeline (when content actually changes) | beats, strategy, requirements, media |
| narration | everything | — |
| catalog / mode | media_assets → feasibility → compositions → … | beats, art direction, strategy, requirements |
| planner config | visual_strategy_plan → downstream | beats, art direction, requirements |

Manifest statuses are now `computed` / `resumed` / `invalidated` (with the
fingerprint recorded per stage). The review's draft→final case recomputes
media instead of resuming placeholders and failing late.

Note: fingerprints hash CONTENT, so e.g. a subject change whose recomputed
art direction is byte-identical keeps downstream artifacts legitimately
resumed.

Implementation: `videotool/pipeline/fingerprints.py`,
`PipelineRunner._stage()` in `videotool/pipeline/runner.py`.

## 2 + 3. Production validate/repair/fallback flow + stage-level validation

The deterministic fallbacks now run INSIDE the pipeline, stage by stage,
before anything downstream consumes them (previously they existed as
functions with unit tests only — the review was right):

* **semantic_beats**: broken function → repaired (default assigned, logged);
  individually-invalid beats dropped, both logged in `manifest.repairs`.
* **episode_art_direction**: empty motifs/accent → `fallback_art_direction`,
  logged.
* **visual_strategy_plan**: unusable selection record (empty strategy/no
  reason) → deterministic first-catalog-candidate fallback marked
  `is_fallback`, logged.
* **visual_compositions**: any composition failing validation (bounds,
  unbound assets, signature reuse, streak) → replaced by
  `deterministic_fallback_composition` KEEPING the beat's planned family
  (so the family sequence and streak guarantees are undisturbed). If
  fallbacks still fail validation, the failure surfaces at final QC —
  never hidden.
* final editorial QC unchanged as the last gate.

Every repair is recorded: `pipeline_manifest.json` → `repairs[]`.

## 4. Asset feasibility pass

New stage `strategy_feasibility` between media acquisition and composition
(the review's preferred shape: strategy intent → media → feasibility):

* `STRATEGY_ASSET_NEEDS` declares the asset kinds each strategy genuinely
  promises (portrait/document/map compounds; timeline/causal/cinematic
  strategies need none — they degrade gracefully).
* After acquisition, each selection is re-checked against the kinds that
  actually resolved for that beat. If required assets are missing, the pass
  switches to the best feasible scored candidate and records why
  (`feasibility_note` + `manifest.feasibility` + `strategy_feasibility.json`).
* Switches are streak-safe by construction: a switch is accepted only if
  the whole family sequence (fixed prefix + switch + all remaining original
  picks) respects the streak limit; otherwise the original strategy is kept
  and its family degrades (explicitly marked `degraded: …`, never silent).
* `visual_strategy_plan.json` keeps the preliminary intent;
  `strategy_feasibility.json` is the plan-of-record the composer follows.

Fixture effect: `map_plus_archival` (needs map+photo) correctly switched to
`region_map` on the map-only beat; the asset-silent turning-point beat kept
its strategy and degraded explicitly.

Also fixed en route: map requirements are no longer generated for
character/quote beats, which had let a character beat steal the geography
beat's map asset through the acquirer's no-reuse rule.

## 5. Repository hygiene

* `make clean` removes `.venv/`, `.pytest_cache/`, `__pycache__/`, `*.pyc`.
* `make dist` builds a source-only `videotool-src.zip` (no venv, no caches,
  no generated artifacts) — the packaged-.venv problem from the review
  cannot recur via the Makefile path.
* caches were purged from the tree; `.gitignore` already excludes them.

## Files touched

```
new:  videotool/pipeline/fingerprints.py
new:  videotool/editorial/feasibility.py
new:  tests/test_phase11_hardening.py
new:  Makefile, docs/PHASE11_HARDENING.md
rewritten: videotool/pipeline/runner.py   (fingerprinted stages, per-stage
          validate/repair/fallback, feasibility stage, repairs manifest)
modified:  editorial/validation.py (fallback_art_direction; family-preserving,
           position-cycled fallback composition)
modified:  editorial/composition/__init__.py (FAMILIES_VERSION,
           history_from_compositions, semantic map requirements)
modified:  domain/strategy.py (feasibility_note), cli.py (status dict print)
modified:  ai/heuristic/beat_analyzer.py (LOCATION_INTRODUCTION lead-entity
           rule replaces topic-specific suffix)
tests:     3 assertions updated for status dicts; suite now 122 tests
```

## Not done (deliberately — agreed Phase 2 scope)

Word-aligned motion timing, generative constraint-solver geometry (replacing
variant bootstrap), real media providers, renderer. These stay on the
Phase 2 plan from `docs/PHASE1_REPORT.md`.
