# Repository Audit — Phase 1 (spec section 23-A, section 33)

Date: 2026-08-17

## 1. State before Phase 1

The repository contained exactly one file:

```
golden_reference_documentary_edit_5s_FINAL.mp4   (3.7 MB, at repo root)
```

There was **no existing pipeline, no code, no configuration, no git history**.
The spec's `docs/references/golden_reference_documentary_edit_5s.mp4` path did
not exist; the video has been moved to `docs/references/` keeping its filename.

Consequences:

* Current pipeline: none.
* Current renderer architecture: none.
* Fixed-layout problems: none (nothing existed), but the spec's required
  architecture had to be built from zero with anti-template guarantees built
  in from the start.
* Systems that can be reused: none.
* Systems that require refactoring: none.
* Systems to deprecate: none.

## 2. What was inspected

* Full recursive listing of the working tree (no hidden tooling, no CI, no
  package manifests).
* Reference video inspected as the ONLY pre-existing asset; treated strictly
  as a motion-language reference (spec section 27), never as a layout source.

## 3. Audit conclusions driving the build

1. Greenfield build → architecture rules (spec sections 2, 19, 28) could be
   applied without migration constraints.
2. No AI API credentials in scope → all "AI" planning stages ship as
   deterministic heuristics behind interfaces (`videotool/ai/interfaces.py`),
   so the whole system is testable offline; LLM providers can be swapped in
   later without touching planning logic (spec section 28).
3. Zero runtime dependencies (Python stdlib only) so the pipeline runs
   anywhere; `pytest` is dev-only inside `.venv`.
4. Berlin-specific vocabulary is quarantined in
   `videotool/fixtures/berlin_wall.py` and enforced by test
   (`test_no_berlin_hardcoded_in_architecture`, spec section 31).

## 4. Pipeline diagram (as implemented)

```
Narration + word timing (fixture / future TTS)
        |
        v
HeuristicBeatAnalyzer --------------> semantic_beats.json
        |
        v
HeuristicArtDirector ----------------> episode_art_direction.json
        |
        v
StrategyPlanner (+ VisualHistory) ---> visual_strategy_plan.json
        |
        v
semantic_asset_requirements ---------> asset_requirements.json
        |
        v
CatalogAcquirer ----------------------> media_assets.json
        |
        v
Composition families (6) + history --> visual_compositions.json
        |                              visual_history.json
        v
MotionPlanner + Transitions ---------> motion_plan.json
        |
        v
TimelineComposer --------------------> timeline.json
        |
        v
Validation (beats/compositions/plan) > pipeline_manifest.json
```

Every stage loads its persisted artifact when valid and recomputes only what
is missing or corrupt (resume, spec section 20 / 23-I).
