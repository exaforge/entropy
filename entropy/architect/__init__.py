"""Architect layer for Entropy population spec generation.

The architect layer discovers attributes, researches distributions,
and builds a complete PopulationSpec without sampling.

Pipeline (Base Mode):
    Step 0: check_sufficiency() - Verify description is adequate
    Step 1: select_attributes() - Discover relevant attributes
    Step 2: hydrate_attributes() - Research distributions
    Step 3: bind_constraints() - Build dependency graph
    Step 4: build_spec() - Assemble PopulationSpec

Pipeline (Overlay Mode):
    Steps 1-3 accept a `context` parameter with existing attributes.
    New attributes can depend on context attributes in formulas/modifiers.
    Final specs are merged via PopulationSpec.merge().
"""

from .sufficiency import check_sufficiency
from .selector import select_attributes
from .hydrator import hydrate_attributes
from .binder import bind_constraints, build_spec

__all__ = [
    "check_sufficiency",
    "select_attributes",
    "hydrate_attributes",
    "bind_constraints",
    "build_spec",
]
