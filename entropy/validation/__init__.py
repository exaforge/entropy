"""Shared validation primitives for Entropy.

This module provides low-level validation utilities used across
population specs, scenario specs, and LLM response validation.

Modules:
    expressions: Expression/formula syntax validation and name extraction
    distributions: Distribution parameter validation (weights, ranges, etc.)
"""

from .expressions import (
    BUILTIN_NAMES,
    PYTHON_KEYWORDS,
    extract_names_from_expression,
    extract_comparisons_from_expression,
    validate_expression_syntax,
)

from .distributions import (
    validate_weight_sum,
    validate_weights_options_match,
    validate_probability_range,
    validate_min_max,
    validate_std_positive,
    validate_beta_params,
    validate_options_not_empty,
)

__all__ = [
    # Expression utilities
    "BUILTIN_NAMES",
    "PYTHON_KEYWORDS",
    "extract_names_from_expression",
    "extract_comparisons_from_expression",
    "validate_expression_syntax",
    # Distribution utilities
    "validate_weight_sum",
    "validate_weights_options_match",
    "validate_probability_range",
    "validate_min_max",
    "validate_std_positive",
    "validate_beta_params",
    "validate_options_not_empty",
]
