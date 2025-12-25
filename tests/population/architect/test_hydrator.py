"""Tests for attribute hydration logic."""

from unittest.mock import patch, MagicMock

import pytest

from entropy.population.architect.hydrator import (
    hydrate_independent,
    hydrate_derived,
    hydrate_conditional_base,
    hydrate_conditional_modifiers,
)
from entropy.core.models import (
    DiscoveredAttribute,
    HydratedAttribute,
    SamplingConfig,
    NormalDistribution,
    GroundingInfo,
)


class TestHydrator:
    """Tests for individual hydration steps."""

    def _create_discovered(self, name, strategy, depends_on=None):
        return DiscoveredAttribute(
            name=name,
            type="int",
            category="universal",
            description="Desc",
            strategy=strategy,
            depends_on=depends_on or [],
        )

    @patch("entropy.population.architect.hydrator.agentic_research")
    def test_hydrate_independent(self, mock_research):
        """Test Step 2a: Independent attribute hydration."""
        # Mock LLM response
        mock_research.return_value = (
            {
                "attributes": [
                    {
                        "name": "age",
                        "distribution": {
                            "type": "normal",
                            "mean": 45,
                            "std": 10,
                            "min": 18,
                            "max": 90
                        },
                        "constraints": [],
                        "grounding": {"level": "strong", "method": "researched"}
                    }
                ]
            },
            ["http://source.com"]  # Sources
        )

        attrs = [self._create_discovered("age", "independent")]
        
        hydrated, sources, errors = hydrate_independent(
            attrs, "Test Pop", "Test Geo"
        )

        assert len(hydrated) == 1
        assert hydrated[0].name == "age"
        assert hydrated[0].sampling.strategy == "independent"
        assert isinstance(hydrated[0].sampling.distribution, NormalDistribution)
        assert hydrated[0].sampling.distribution.mean == 45
        assert sources == ["http://source.com"]
        assert not errors

    @patch("entropy.population.architect.hydrator.reasoning_call")
    def test_hydrate_derived(self, mock_reasoning):
        """Test Step 2b: Derived attribute hydration."""
        mock_reasoning.return_value = {
            "attributes": [
                {
                    "name": "is_senior",
                    "formula": "age > 65"
                }
            ]
        }

        attrs = [self._create_discovered("is_senior", "derived", ["age"])]
        # We need mock independent attrs for context (optional but good practice)
        indep_attrs = [
            HydratedAttribute(
                name="age", type="int", category="universal", description="Age",
                strategy="independent",
                sampling=SamplingConfig(strategy="independent"),
                grounding=GroundingInfo(level="low", method="estimated")
            )
        ]

        hydrated, errors = hydrate_derived(
            attrs, "Test Pop", independent_attrs=indep_attrs
        )

        assert len(hydrated) == 1
        assert hydrated[0].name == "is_senior"
        assert hydrated[0].sampling.formula == "age > 65"
        assert not errors

    @patch("entropy.population.architect.hydrator.agentic_research")
    def test_hydrate_conditional_base(self, mock_research):
        """Test Step 2c: Conditional base hydration."""
        mock_research.return_value = (
            {
                "attributes": [
                    {
                        "name": "income",
                        "distribution": {
                            "type": "normal",
                            "mean_formula": "age * 1000",
                            "std": 5000
                        },
                        "constraints": [],
                        "grounding": {"level": "medium"}
                    }
                ]
            },
            []
        )

        attrs = [self._create_discovered("income", "conditional", ["age"])]
        
        hydrated, sources, errors = hydrate_conditional_base(
            attrs, "Test Pop", independent_attrs=[]
        )

        assert len(hydrated) == 1
        assert hydrated[0].name == "income"
        assert hydrated[0].sampling.distribution.mean_formula == "age * 1000"
        assert not errors

    @patch("entropy.population.architect.hydrator.agentic_research")
    def test_hydrate_retry_logic(self, mock_research):
        """Test that validation failure triggers retry mechanism."""
        # This test verifies that we pass a validator to the LLM function.
        # The actual retry loop is in core/llm.py, but we check that hydration sets it up.
        
        mock_research.return_value = ({"attributes": []}, [])

        attrs = [self._create_discovered("age", "independent")]
        
        hydrate_independent(attrs, "Test Pop")

        # Check that validator was passed
        call_kwargs = mock_research.call_args.kwargs
        assert "validator" in call_kwargs
        assert callable(call_kwargs["validator"])
        
        # Manually invoke the validator to ensure it works
        validator = call_kwargs["validator"]
        
        # Test invalid data (missing type in distribution)
        valid, msg = validator({"attributes": [{"name": "age", "distribution": {}}]})
        assert not valid
        assert "ERROR" in msg or "Problem" in msg
