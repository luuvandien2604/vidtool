"""Stage executor with integrity-checked resume (spec section 20, Phase 1.2).

Guarantees:
- Input fingerprint match -> artifact loads -> output hash matches -> stage validator passes.
- Valid-JSON corruption cannot silently resume.
- Failed checks cleanly recompute the stage and overwrite metadata.
"""
from __future__ import annotations

from typing import Any

from videotool.pipeline.context import PipelineContext
from videotool.pipeline.fingerprints import STAGE_VERSIONS, stable_hash
from videotool.pipeline.stage import PipelineStage


class StageExecutor:
    """Executes a pipeline stage with strict fingerprinting and resume verification."""

    def execute_stage(self, stage: PipelineStage, ctx: PipelineContext) -> Any:
        meta = ctx.load_meta()
        stage_name = stage.id
        fingerprint = stage.fingerprint(ctx)
        stage_version = getattr(stage, "version", STAGE_VERSIONS.get(stage_name))

        prior = meta.get(stage_name)
        if (
            not ctx.force
            and isinstance(prior, dict)
            and prior.get("input_fingerprint") == fingerprint
            and prior.get("stage_version") == stage_version
        ):
            payload = ctx.store.load(ctx.episode_id, stage_name)
            if payload is not None and stable_hash(payload) == prior.get("output_hash"):
                try:
                    validate_fn = getattr(stage, "validate", None)
                    valid = validate_fn(payload, ctx) if callable(validate_fn) else True
                except Exception:
                    valid = False

                if valid:
                    ctx.record_status(stage_name, "resumed", fingerprint)
                    return payload

        status = "invalidated" if (prior is not None and not ctx.force) else "computed"
        payload = stage.execute(ctx)
        ctx.store.save(ctx.episode_id, stage_name, payload)

        meta[stage_name] = {
            "input_fingerprint": fingerprint,
            "output_hash": stable_hash(payload),
            "stage_version": stage_version,
        }
        ctx.store.save(ctx.episode_id, "stage_meta", meta)
        ctx.record_status(stage_name, status, fingerprint)
        return payload
