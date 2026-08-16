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
STAGE_VERSIONS: dict[str, int] = {
    "semantic_beats": 1,
    "episode_art_direction": 1,
    "visual_strategy_plan": 1,
    "asset_requirements": 2,   # 2: strength model replaces unused min_count
    "media_assets": 1,
    "strategy_feasibility": 1,
    "visual_compositions": 2,   # 2: consumes feasibility-adjusted plan
    "visual_history": 2,
    "motion_plan": 1,
    "timeline": 1,
}


def stable_hash(*parts) -> str:
    """Deterministic content hash for JSON-serializable stage inputs."""
    blob = json.dumps(list(parts), sort_keys=True, ensure_ascii=False,
                      default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
