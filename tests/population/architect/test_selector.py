"""Tests for attribute selection."""

from unittest.mock import patch, MagicMock

from entropy.population.architect.selector import select_attributes
from entropy.core.models import DiscoveredAttribute, AttributeSpec


class TestSelector:
    """Tests for attribute selection logic."""

    @patch("entropy.population.architect.selector.reasoning_call")
    def test_basic_selection(self, mock_reasoning_call):
        """Test basic attribute selection."""
        mock_reasoning_call.return_value = {
            "attributes": [
                {
                    "name": "age",
                    "type": "int",
                    "category": "universal",
                    "description": "Age in years",
                    "strategy": "independent",
                    "depends_on": [],
                },
                {
                    "name": "specialty",
                    "type": "categorical",
                    "category": "population_specific",
                    "description": "Medical specialty",
                    "strategy": "independent",
                    "depends_on": [],
                },
            ],
            "include_big_five": False,
            "notes": "Test notes",
        }

        attributes = select_attributes("surgeons", 100)

        assert len(attributes) == 2
        assert isinstance(attributes[0], DiscoveredAttribute)
        assert attributes[0].name == "age"
        assert attributes[0].strategy == "independent"

    @patch("entropy.population.architect.selector.reasoning_call")
    def test_strategy_auto_correction(self, mock_reasoning_call):
        """Test that inconsistent strategies are auto-corrected."""
        mock_reasoning_call.return_value = {
            "attributes": [
                {
                    "name": "years_experience",
                    "type": "int",
                    "category": "population_specific",
                    "description": "Experience",
                    "strategy": "independent",  # Wrong: has dependencies
                    "depends_on": ["age"],
                },
                {
                    "name": "bmi",
                    "type": "float",
                    "category": "universal",
                    "description": "BMI",
                    "strategy": "derived",  # Wrong: no dependencies
                    "depends_on": [],
                },
            ],
            "include_big_five": False,
            "notes": "Test notes",
        }

        attributes = select_attributes("surgeons", 100)

        # Should be corrected to conditional
        assert attributes[0].name == "years_experience"
        assert attributes[0].strategy == "conditional"
        assert attributes[0].depends_on == ["age"]

        # Should be corrected to independent
        assert attributes[1].name == "bmi"
        assert attributes[1].strategy == "independent"
        assert attributes[1].depends_on == []

    @patch("entropy.population.architect.selector.reasoning_call")
    def test_big_five_inclusion(self, mock_reasoning_call):
        """Test automatic inclusion of Big Five traits."""
        mock_reasoning_call.return_value = {
            "attributes": [
                {
                    "name": "age",
                    "type": "int",
                    "category": "universal",
                    "description": "Age",
                    "strategy": "independent",
                    "depends_on": [],
                }
            ],
            "include_big_five": True,
            "notes": "Test notes",
        }

        attributes = select_attributes("surgeons", 100)

        # 1 base + 5 personality traits
        assert len(attributes) == 6
        
        trait_names = {a.name for a in attributes}
        assert "openness" in trait_names
        assert "conscientiousness" in trait_names
        assert "extraversion" in trait_names
        assert "agreeableness" in trait_names
        assert "neuroticism" in trait_names

    @patch("entropy.population.architect.selector.reasoning_call")
    def test_overlay_mode_context(self, mock_reasoning_call):
        """Test overlay mode passing context."""
        mock_reasoning_call.return_value = {
            "attributes": [
                {
                    "name": "tech_adoption",
                    "type": "float",
                    "category": "context_specific",
                    "description": "Adoption",
                    "strategy": "conditional",
                    "depends_on": ["age"],  # Depends on base attribute
                }
            ],
            "include_big_five": False,
            "notes": "Test notes",
        }

        # Mock existing context
        # We need to construct AttributeSpec properly with SamplingConfig
        from entropy.core.models import SamplingConfig, GroundingInfo, NormalDistribution
        
        context = [
            AttributeSpec(
                name="age", 
                type="int", 
                category="universal", 
                description="Age", 
                sampling=SamplingConfig(strategy="independent", distribution=NormalDistribution(mean=40, std=10)), 
                grounding=GroundingInfo(level="low", method="estimated", source="test")
            )
        ]

        attributes = select_attributes(
            "AI adoption", 
            100, 
            context=context
        )

        assert len(attributes) == 1
        assert attributes[0].name == "tech_adoption"
        
        # Verify context was passed in prompt
        call_kwargs = mock_reasoning_call.call_args.kwargs
        assert "EXISTING CONTEXT" in call_kwargs["prompt"]
        assert "- age (int)" in call_kwargs["prompt"]
