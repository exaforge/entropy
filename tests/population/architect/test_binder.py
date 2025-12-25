"""Tests for constraint binding and dependency resolution."""

import pytest

from entropy.population.architect.binder import bind_constraints, CircularDependencyError
from entropy.core.models import (
    HydratedAttribute,
    AttributeSpec,
    SamplingConfig,
    GroundingInfo,
    NormalDistribution,
)


class TestBinder:
    """Tests for binder logic."""

    def _create_attr(self, name, depends_on=None):
        """Helper to create a dummy HydratedAttribute."""
        depends_on = depends_on or []
        strategy = "independent" if not depends_on else "conditional"
        
        return HydratedAttribute(
            name=name,
            type="int",
            category="universal",
            description="Test desc",
            strategy=strategy,
            sampling=SamplingConfig(
                strategy=strategy,
                distribution=NormalDistribution(mean=0, std=1),
                depends_on=depends_on,
            ),
            grounding=GroundingInfo(level="low", method="estimated", source="test"),
            depends_on=depends_on,
        )

    def test_linear_dependency(self):
        """Test simple A -> B -> C dependency chain."""
        # A: independent
        attr_a = self._create_attr("A", [])
        # B: depends on A
        attr_b = self._create_attr("B", ["A"])
        # C: depends on B
        attr_c = self._create_attr("C", ["B"])

        # Input order shouldn't matter
        attributes = [attr_c, attr_a, attr_b]

        specs, order, warnings = bind_constraints(attributes)

        assert not warnings
        assert len(specs) == 3
        
        # Verify order
        idx_a = order.index("A")
        idx_b = order.index("B")
        idx_c = order.index("C")

        assert idx_a < idx_b  # A before B
        assert idx_b < idx_c  # B before C

    def test_circular_dependency(self):
        """Test detection of circular dependencies (A -> B -> A)."""
        # A depends on B
        attr_a = self._create_attr("A", ["B"])
        # B depends on A
        attr_b = self._create_attr("B", ["A"])

        with pytest.raises(CircularDependencyError):
            bind_constraints([attr_a, attr_b])

    def test_unknown_dependency(self):
        """Test handling of dependencies on unknown attributes."""
        # A depends on X (unknown)
        attr_a = self._create_attr("A", ["X"])

        specs, order, warnings = bind_constraints([attr_a])

        assert len(warnings) == 1
        assert "removed unknown dependency 'X'" in warnings[0]
        
        # Dependency should be removed from spec
        assert specs[0].sampling.depends_on == []
        assert order == ["A"]

    def test_overlay_context(self):
        """Test binding with existing context (overlay mode)."""
        # Context has 'age'
        context_attr = AttributeSpec(
            name="age",
            type="int",
            category="universal",
            description="Age",
            sampling=SamplingConfig(
                strategy="independent",
                distribution=NormalDistribution(mean=40, std=10)
            ),
            grounding=GroundingInfo(level="strong", method="researched")
        )
        context = [context_attr]

        # New attribute 'tech_savviness' depends on 'age'
        attr_new = self._create_attr("tech_savviness", ["age"])

        specs, order, warnings = bind_constraints([attr_new], context=context)

        assert not warnings
        assert len(specs) == 1
        assert specs[0].name == "tech_savviness"
        # Dependency on 'age' should be preserved because it's in context
        assert specs[0].sampling.depends_on == ["age"]
        assert order == ["tech_savviness"]
