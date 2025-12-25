"""Tests for population sampler."""

import pytest
from entropy.population.sampler.core import sample_population, SamplingResult


class TestSampler:
    """Tests for main sampling loop."""

    def test_sample_population_basic(self, sample_spec):
        """Test sampling a valid population."""
        count = 10
        result = sample_population(spec=sample_spec, count=count, seed=42)

        assert isinstance(result, SamplingResult)
        assert len(result.agents) == count
        
        # Verify agent structure
        agent0 = result.agents[0]
        assert "_id" in agent0
        assert "age" in agent0
        assert "gender" in agent0
        assert "age_bracket" in agent0
        assert "income" in agent0

        # Verify derived attribute logic
        if agent0["age"] < 40:
            assert agent0["age_bracket"] == "Young"
        else:
            assert agent0["age_bracket"] == "Old"

    def test_sample_consistency(self, sample_spec):
        """Test reproducibility with fixed seed."""
        result1 = sample_population(spec=sample_spec, count=5, seed=123)
        result2 = sample_population(spec=sample_spec, count=5, seed=123)

        assert result1.agents == result2.agents

    def test_conditional_modifier_application(self, sample_spec):
        """Test that modifiers are applied (income depends on age)."""
        # Income has modifier: multiply 1.2 if age > 50
        # Base mean 50k.
        
        result = sample_population(spec=sample_spec, count=100, seed=42)
        
        old_agents = [a for a in result.agents if a["age"] > 50]
        young_agents = [a for a in result.agents if a["age"] <= 50]

        avg_income_old = sum(a["income"] for a in old_agents) / len(old_agents)
        avg_income_young = sum(a["income"] for a in young_agents) / len(young_agents)

        # Old agents should have roughly 20% higher income
        # Given randomness, we check for significant difference
        assert avg_income_old > avg_income_young * 1.05

    def test_missing_attribute_handling(self, sample_spec):
        """Test handling when sampling order references missing attribute."""
        sample_spec.sampling_order.append("missing_attr")
        
        # Should log warning but proceed (or crash if implementation is strict)
        # Based on code: logger.warning and continue
        result = sample_population(spec=sample_spec, count=1, seed=42)
        
        assert "missing_attr" not in result.agents[0]
