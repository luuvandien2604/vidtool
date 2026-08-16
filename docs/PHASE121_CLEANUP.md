# Phase 1.2.1 — Cleanup (external review follow-up)

Date: 2026-08-17 · Suite: **172 tests passed**. Five fixes + final patch, no
new features, no renderer. All issues were confirmed against the source
before fixing.

## 1. `family_recency()` was inverted (blocker)

The docstring said `0.0 = just used, 1.0 = unseen` but the formula returned
~0.92 for a family used one beat ago and near 0.0 for long-unused families —
so `visual_novelty` in the strategy planner rewarded reusing what the
audience JUST saw. An old test (`older < recent`) locked the wrong behaviour
instead of catching it. Now: `min(1.0, back / max_window)` —
just-used ≈ 0.08, unseen = 1.0. `signature_recency()` had the same inversion
and is fixed too. New regression tests assert `just_used < one_back < unseen`
and that planner novelty for a family used last beat is < 0.2 while unseen
families score 1.0. The fixture plan keeps full variety (6 families,
12/12 unique signatures) with correct scoring.

## 2. Signatures are texture-independent (blocker)

`_finish()` derived the signature BEFORE attaching the paper texture, while
mirrored odd variants re-derived it AFTER — and `derive_signature` counted
all layer types, so structurally identical compositions could differ by
signature depending on when it was computed. `derive_signature` now ignores
TEXTURE layers everywhere (type multiset, hero selection already did, and —
a second leak found by the new tests — the reading-direction check used
`len(comp.layers) > 1` including texture). Grain is brand styling, not
geometry.

## 3. Asset needs are `all_of/any_of` policies, not AND-sets (blocker)

`STRATEGY_ASSET_NEEDS: dict[str, set]` + "every need must resolve" meant
`full_frame_archival` demanded portrait AND photo AND map AND document —
so a lone excellent archival photo would be declared infeasible. Replaced
with `StrategyAssetPolicy(all_of=..., any_of=...)`: `full_frame_archival`
is `any_of(photo, portrait, document, map)`; `portrait_plus_document` is
`all_of(document) + any_of(portrait, photo)`; `map_plus_archival` is
`all_of(map) + any_of(photo, portrait)`. Kind equivalence
(portrait↔photo) applies inside policies. The Media Completeness Gate now
uses `policy_needs_kind()` instead of set intersection.

## 4. `build_timeline()` no longer mutates compositions (determinism bug)

It used to write `comp.transition_in/out` AFTER the composition and history
artifacts were saved — so a fresh run carried transition data on the
in-memory compositions that a resumed run (timeline resumed, builder never
called) lacked. Transitions are now data of the timeline/motion plan:
each timeline segment carries `transition_in`/`transition_out`, and
`VisualComposition` objects are never touched. Regression test asserts
fresh vs fully-resumed runs produce identical in-memory compositions and
timelines.

## 5. No more parsing requirement ids

`run_feasibility_pass()` used to reconstruct beat ids by splitting
`req_beat_0001_map` strings. It now takes the requirements list and uses the
`requirement_id -> beat_id` mapping from `AssetRequirement.beat_id` — ids
are opaque. Regression test feeds a requirement id like `R-001/weird format`
and verifies grouping still works.

## Files

```
modified: videotool/domain/visual_history.py      (recency direction,
          texture-independent signatures)
modified: videotool/editorial/feasibility.py      (policy model, opaque ids)
modified: videotool/editorial/validation.py       (gate uses policy_needs_kind)
modified: videotool/editorial/timeline.py         (no composition mutation)
modified: videotool/pipeline/runner.py            (pass requirements to
          feasibility)
fixed:    tests/test_visual_history.py            (un-locked the inverted
          behaviour)
new:      tests/test_phase121_cleanup.py          (17 regression tests)
```

## Final patch (second review round)

1. **Stage versions bumped for every semantics change** — the original 1.2.1
   commit changed computation without bumping `STAGE_VERSIONS`, so artifacts
   written by the old (buggy) code could resume through the new code with
   identical inputs, bypassing the entire integrity system:
   `visual_strategy_plan: 1→2` (recency direction),
   `strategy_feasibility: 1→2` (all_of/any_of),
   `visual_compositions: 2→3` + `FAMILIES_VERSION: 1→2` (signature
   semantics), `visual_history: 2→3`, `timeline: 1→2` (transitions on
   segments). Regression test simulates the exact upgrade scenario: create
   artifacts under the OLD versions (monkeypatched constants), run with the
   new code and identical inputs — bumped stages `invalidated`, untouched
   stages (`semantic_beats`, `episode_art_direction`, `asset_requirements`,
   `media_assets`) `resumed`, and `stage_meta` rewritten to the new versions.
2. **`assets_for_beat()` no longer parses requirement ids** — it took a new
   `requirements` argument and groups via `requirement_id -> beat_id`
   mapping. End-to-end regression: requirements generated with deliberately
   opaque ids (`R::beat_0003::portrait (opaque/2026)`) flow through
   acquisition → feasibility → composition binding, and the CHARACTER beat's
   portrait lands on a composition layer (`layer.asset_id` asserted).
3. **`_hero_layer()` fallback can never return a TEXTURE layer** — first
   non-texture layer only; texture-only compositions yield `hero=none`.

New tests: `tests/test_phase121_patch.py` (7 tests, including the
old-version upgrade scenario and the opaque-id end-to-end flow).
