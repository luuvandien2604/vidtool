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

    def __init__(self):
        self._stage_counter = 0

    def execute_stage(self, stage: PipelineStage, ctx: PipelineContext) -> Any:
        from videotool.observability import LogLevel, get_logger
        logger = get_logger()

        self._stage_counter += 1
        meta = ctx.load_meta()
        stage_name = stage.id
        fingerprint = stage.fingerprint(ctx)
        stage_version = getattr(stage, "version", STAGE_VERSIONS.get(stage_name))

        logger.stage_header(
            self._stage_counter,
            stage_name,
            description=getattr(stage, "__doc__", "").strip().split("\n")[0] if getattr(stage, "__doc__", "") else ""
        )
        if logger.trace:
            logger._emit(LogLevel.TRACE, f"Input Fingerprint: {fingerprint} | Stage Version: {stage_version}")

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
                    logger._emit(LogLevel.CACHE, f"HIT (Output hash: {prior.get('output_hash')[:12]}...) -> Resumed cached artifact")
                    logger.stage_complete(stage_name, status="RESUMED", details="Valid cache hit")
                    return payload

        status = "invalidated" if (prior is not None and not ctx.force) else "computed"
        logger._emit(LogLevel.INFO, f"Computing stage '{stage_name}' (status: {status})...")
        payload = stage.execute(ctx)
        ctx.store.save(ctx.episode_id, stage_name, payload)

        out_hash = stable_hash(payload)
        meta[stage_name] = {
            "input_fingerprint": fingerprint,
            "output_hash": out_hash,
            "stage_version": stage_version,
        }
        ctx.store.save(ctx.episode_id, "stage_meta", meta)
        ctx.record_status(stage_name, status, fingerprint)

        logger.log_artifact(stage_name, f"artifacts/{ctx.episode_id}/{stage_name}.json")
        logger.stage_complete(stage_name, status="COMPUTED", details=f"Output hash: {out_hash[:12]}...")
        return payload
