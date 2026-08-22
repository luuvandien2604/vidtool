"""Pipeline stage protocol and base definitions (spec section 20).

Stages are decoupled units of execution: each defines its identifier, version,
input projection fingerprint, compute function, and optional resume validator.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from videotool.pipeline.context import PipelineContext
from videotool.pipeline.fingerprints import STAGE_VERSIONS


@runtime_checkable
class PipelineStage(Protocol):
    """Protocol for discrete pipeline execution stages."""
    id: str

    @property
    def version(self) -> int | str:
        """Dynamic lookup of stage version."""
        ...

    def fingerprint(self, ctx: PipelineContext) -> str:
        """Compute deterministic SHA256 input projection hash."""
        ...

    def execute(self, ctx: PipelineContext) -> Any:
        """Execute stage computation and return JSON-serializable artifact payload."""
        ...


class BasePipelineStage:
    """Base class providing optional validator hook and dynamic version lookup."""
    id: str

    @property
    def version(self) -> int | str:
        return STAGE_VERSIONS.get(self.id, 1)

    def fingerprint(self, ctx: PipelineContext) -> str:
        raise NotImplementedError

    def execute(self, ctx: PipelineContext) -> Any:
        raise NotImplementedError

    def validate(self, payload: Any, ctx: PipelineContext) -> bool:
        """Optional semantic validator for integrity-checked resume. Returns True if valid."""
        return True
