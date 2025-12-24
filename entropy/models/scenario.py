"""Scenario models re-exported for convenience.

This module re-exports all scenario-related models from entropy.scenario.models
for cleaner imports:

    from entropy.models.scenario import ScenarioSpec, Event
    # instead of:
    from entropy.scenario.models import ScenarioSpec, Event
"""

from ..scenario.models import (
    # Event
    EventType,
    Event,
    # Exposure
    ExposureChannel,
    ExposureRule,
    SeedExposure,
    # Interaction
    InteractionType,
    InteractionConfig,
    SpreadModifier,
    SpreadConfig,
    # Outcomes
    OutcomeType,
    OutcomeDefinition,
    OutcomeConfig,
    # Simulation
    TimestepUnit,
    SimulationConfig,
    # Scenario
    ScenarioMeta,
    ScenarioSpec,
    # Validation
    ValidationError,
    ValidationWarning,
    ValidationResult,
)

__all__ = [
    # Event
    "EventType",
    "Event",
    # Exposure
    "ExposureChannel",
    "ExposureRule",
    "SeedExposure",
    # Interaction
    "InteractionType",
    "InteractionConfig",
    "SpreadModifier",
    "SpreadConfig",
    # Outcomes
    "OutcomeType",
    "OutcomeDefinition",
    "OutcomeConfig",
    # Simulation
    "TimestepUnit",
    "SimulationConfig",
    # Scenario
    "ScenarioMeta",
    "ScenarioSpec",
    # Validation
    "ValidationError",
    "ValidationWarning",
    "ValidationResult",
]
