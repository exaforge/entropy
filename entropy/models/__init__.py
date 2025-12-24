"""Data models for Entropy.

This package contains all Pydantic models used across the system:
- spec.py: Population specs, attributes, distributions, sampling configs
- scenario.py: Scenario specs, events, exposure rules, interaction models
- simulation.py: (Future) Agent runtime and network simulation models
"""

from .spec import (
    # Grounding
    GroundingInfo,
    GroundingSummary,
    # Distributions
    NormalDistribution,
    LognormalDistribution,
    UniformDistribution,
    BetaDistribution,
    CategoricalDistribution,
    BooleanDistribution,
    Distribution,
    # Modifiers
    NumericModifier,
    CategoricalModifier,
    BooleanModifier,
    Modifier,
    # Sampling
    SamplingConfig,
    Constraint,
    # Attributes
    AttributeSpec,
    DiscoveredAttribute,
    HydratedAttribute,
    # Spec
    SpecMeta,
    PopulationSpec,
    # Pipeline types
    SufficiencyResult,
)

__all__ = [
    # Grounding
    "GroundingInfo",
    "GroundingSummary",
    # Distributions
    "NormalDistribution",
    "LognormalDistribution",
    "UniformDistribution",
    "BetaDistribution",
    "CategoricalDistribution",
    "BooleanDistribution",
    "Distribution",
    # Modifiers
    "NumericModifier",
    "CategoricalModifier",
    "BooleanModifier",
    "Modifier",
    # Sampling
    "SamplingConfig",
    "Constraint",
    # Attributes
    "AttributeSpec",
    "DiscoveredAttribute",
    "HydratedAttribute",
    # Spec
    "SpecMeta",
    "PopulationSpec",
    # Pipeline types
    "SufficiencyResult",
]
