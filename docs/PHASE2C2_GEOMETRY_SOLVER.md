# Phase 2C.2 generative geometry solver

Phase 2C.2 turns the unresolved semantic `GeometryPlan` from Phase 2C.1 into
a solved, renderer-independent layout artifact. It still does not render video
and does not invoke FFmpeg.

The production path is now:

```
semantic beat + strategy + media + art direction
-> semantic node/topology planning
-> deterministic candidate operators
-> hard constraint validation
-> explainable soft scoring
-> history-aware novelty scoring
-> selected solved placements
-> validated semantic_geometry artifact
```

The bootstrap `VisualComposition` remains untouched and is still available as
compatibility metadata through `source_layer_id` and timing-anchor mapping. It
does not determine semantic node inventory or solved coordinates.

## Solver model

Each solved `GeometryPlan` now carries:

- `solved_placements`: one normalized rectangle per semantic node
- `solver_candidate_count`: number of generated candidates
- `solver_score`: component scores for hard constraints, overlap, safe zones,
  hierarchy, reading flow, semantic proximity, whitespace, balance, salience,
  novelty, art direction, and total score
- `solver_explanation`: human-readable reason for the selected candidate
- `structural_geometry_signature`: texture/timing/asset-id independent solved
  geometry signature

Candidate operators include row/column timeline flow, graph-level and radial
causal placement, map endpoint placement, document containment, portrait
clusters, and full-frame overlay hierarchy. They are operators, not fixed
Berlin-specific layouts.

Hard failures cannot win selection. Resume validation rejects meta-consistent
corruption of solved placements, including out-of-canvas rectangles,
subtitle-safe-zone violations, hard overlap violations, missing placements,
and failed containment.

## Determinism and fingerprints

No randomness is used. The same semantic graph, assets, art direction and
recent geometry history produce the same solved geometry.

Versions bumped:

- `SEMANTIC_GEOMETRY_VERSION = 3`
- `GEOMETRY_SIGNATURE_VERSION = 3`
- `STAGE_VERSIONS["semantic_geometry"] = 3`

New explicit solver versions are included in the semantic geometry fingerprint:

- `GEOMETRY_SOLVER_VERSION`
- `GEOMETRY_CANDIDATE_VERSION`
- `GEOMETRY_SCORE_VERSION`

Absolute word timings remain excluded from the semantic geometry input
projection, so timing-only changes still resume geometry.
