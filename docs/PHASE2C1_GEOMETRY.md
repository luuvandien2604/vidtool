# Phase 2C.1 semantic geometry architecture

`GeometryPlan` is an unresolved semantic graph. It does not contain renderer
coordinates and does not invoke a solver.

The semantic node planner derives node inventory, groups, and directed edges
from the plan-of-record strategy and visual family, `SemanticBeat`, semantic
anchors, resolved media/requirements, and episode art-direction policy.
Bootstrap `VisualComposition` remains the Phase 2C.1 plan of record, but it is
only a compatibility input: a compatible layer may be recorded as
`source_layer_id` and may supply a timing-anchor binding. Missing or fewer
bootstrap layers never remove semantic nodes or change semantic topology.

The semantic geometry signature canonicalizes primary role and region,
ordered role hierarchy, role-based group membership, directed role-to-role
edge topology, and reading direction. Generated node IDs and topic text are
excluded, so equivalent graphs remain equivalent while chain and star
topologies remain distinct.

Reading direction is selected deterministically from family semantics,
semantic function, hierarchy, episode geometry hints, and recent semantic
geometry history. The hierarchy and `GeometryStyleHints` carry the same
resolved direction. Absolute word times are excluded from the stage input
projection, preserving timing-only resume behavior.
