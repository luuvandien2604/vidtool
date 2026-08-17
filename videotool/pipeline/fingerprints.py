"""Stage input fingerprinting + dependency invalidation (Phase 1.1).

A persisted artifact may only be resumed when the fingerprint of the inputs
it was computed FROM matches the fingerprint of the inputs we would compute
it WITH now. Because stage fingerprints chain (each includes its parents'),
changing narration/subject/catalog/mode/config invalidates exactly the
stages that (transitively) depend on the change - and nothing else.
"""
from __future__ import annotations

import hashlib
import json

# Bump a stage's version when its computation logic changes semantically;
# that alone invalidates the stage and everything downstream of it.
# Phase 1.2.1 patch: recency/policy/signature/timeline semantics changed,
# so their versions were bumped - artifacts written by older code must NOT
# resume through newer code with the same inputs.
STAGE_VERSIONS: dict[str, int] = {
    "semantic_beats": 1,
    "episode_art_direction": 1,
    "visual_strategy_plan": 2,    # 2: family_recency novelty direction fixed
    "asset_requirements": 2,      # 2: strength model replaces unused min_count
    "media_search_plan": 1,       # Phase 2A: deterministic semantic queries
    "media_candidates": 2,        # 2: isolated query diagnostics persisted
    "media_acquisition_result": 1,  # atomic assets + explanatory trace source
    "media_assets": 3,            # 3: strong semantic resume validation
    "media_acquisition_trace": 2,  # 2: lossless derivation from result bundle
    "media_attribution": 1,       # Phase 2A
    "strategy_feasibility": 2,    # 2: all_of/any_of policy semantics
    "visual_compositions": 4,     # 4: signature derived after reading_order
    "visual_history": 4,          # 4: signature semantics changed
    "motion_plan": 1,
    "timeline": 2,                # 2: transitions moved onto segments; no mutation
}


def stable_hash(*parts) -> str:
    """Deterministic content hash for JSON-serializable stage inputs."""
    blob = json.dumps(list(parts), sort_keys=True, ensure_ascii=False,
                      default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
