"""Utilities for attribute hydration: schemas and parsers.

This module re-exports from schemas.py and parsers.py for backwards compatibility.

DEPRECATED: Import directly from schemas.py or parsers.py instead.
"""

# Re-export schemas
from .schemas import (
    build_independent_schema,
    build_derived_schema,
    build_conditional_base_schema,
    build_modifiers_schema,
)

# Re-export parsers
from .parsers import (
    sanitize_formula,
    parse_distribution,
    default_distribution,
    parse_constraints,
    parse_modifiers,
)

__all__ = [
    # Schemas
    "build_independent_schema",
    "build_derived_schema",
    "build_conditional_base_schema",
    "build_modifiers_schema",
    # Parsers
    "sanitize_formula",
    "parse_distribution",
    "default_distribution",
    "parse_constraints",
    "parse_modifiers",
]
