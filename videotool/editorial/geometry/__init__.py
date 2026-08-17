"""Semantic geometry builders and validation (Phase 2C.1)."""

from .builder import (GEOMETRY_POLICY_VERSION, GEOMETRY_SIGNATURE_VERSION,
                      SEMANTIC_GEOMETRY_VERSION, SemanticGeometryBuilder,
                      debug_geometry_plan, geometry_input_projection,
                      semantic_geometry_signature)
from .validation import validate_geometry_plan, validate_geometry_plans

__all__ = [
    "GEOMETRY_POLICY_VERSION", "GEOMETRY_SIGNATURE_VERSION",
    "SEMANTIC_GEOMETRY_VERSION", "SemanticGeometryBuilder",
    "debug_geometry_plan", "geometry_input_projection",
    "semantic_geometry_signature",
    "validate_geometry_plan", "validate_geometry_plans",
]
