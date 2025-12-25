"""Global fixtures for Entropy tests."""

from unittest.mock import MagicMock, patch

import pytest

from entropy.core.models import (
    PopulationSpec,
    SpecMeta,
    GroundingSummary,
    AttributeSpec,
    SamplingConfig,
    GroundingInfo,
    NormalDistribution,
    CategoricalDistribution,
    BooleanDistribution,
    Modifier,
)


@pytest.fixture
def mock_llm():
    """Mock LLM calls."""
    with patch("entropy.core.llm.simple_call") as mock_simple, \
         patch("entropy.core.llm.reasoning_call") as mock_reasoning, \
         patch("entropy.core.llm.agentic_research") as mock_research:
        yield {
            "simple": mock_simple,
            "reasoning": mock_reasoning,
            "research": mock_research,
        }


@pytest.fixture
def sample_spec():
    """Create a sample valid PopulationSpec."""
    # 1. Independent attribute: age
    age_attr = AttributeSpec(
        name="age",
        type="int",
        category="universal",
        description="Age of the agent",
        sampling=SamplingConfig(
            strategy="independent",
            distribution=NormalDistribution(mean=45, std=10, min=25, max=70),
        ),
        grounding=GroundingInfo(level="strong", method="researched", source="Census"),
    )

    # 2. Independent attribute: gender
    gender_attr = AttributeSpec(
        name="gender",
        type="categorical",
        category="universal",
        description="Gender",
        sampling=SamplingConfig(
            strategy="independent",
            distribution=CategoricalDistribution(
                options=["male", "female"], weights=[0.5, 0.5]
            ),
        ),
        grounding=GroundingInfo(level="strong", method="researched", source="Census"),
    )

    # 3. Derived attribute: age_bracket
    age_bracket_attr = AttributeSpec(
        name="age_bracket",
        type="categorical",
        category="universal",
        description="Age bracket",
        sampling=SamplingConfig(
            strategy="derived",
            formula="'Young' if age < 40 else 'Old'",
            depends_on=["age"],
        ),
        grounding=GroundingInfo(level="medium", method="computed"),
    )

    # 4. Conditional attribute: income
    income_attr = AttributeSpec(
        name="income",
        type="int",
        category="population_specific",
        description="Annual income",
        sampling=SamplingConfig(
            strategy="conditional",
            distribution=NormalDistribution(mean=50000, std=15000),
            modifiers=[
                Modifier(when="age > 50", multiply=1.2, add=0),
            ],
            depends_on=["age"],
        ),
        grounding=GroundingInfo(level="medium", method="estimated"),
    )

    return PopulationSpec(
        meta=SpecMeta(description="Sample Population", size=100),
        grounding=GroundingSummary(
            overall="medium",
            sources_count=1,
            strong_count=2,
            medium_count=2,
            low_count=0,
            sources=["Census"],
        ),
        attributes=[age_attr, gender_attr, age_bracket_attr, income_attr],
        sampling_order=["age", "gender", "age_bracket", "income"],
    )


@pytest.fixture
def sample_agents():
    """Sample list of agent dictionaries."""
    return [
        {"_id": "agent_0", "age": 35, "gender": "male", "income": 50000, "age_bracket": "Young"},
        {"_id": "agent_1", "age": 55, "gender": "female", "income": 75000, "age_bracket": "Old"},
        {"_id": "agent_2", "age": 25, "gender": "female", "income": 45000, "age_bracket": "Young"},
    ]


@pytest.fixture
def sample_network():
    """Sample network dictionary."""
    return {
        "meta": {"node_count": 3, "edge_count": 2, "avg_degree": 1.33},
        "nodes": [
            {"id": "agent_0"},
            {"id": "agent_1"},
            {"id": "agent_2"},
        ],
        "edges": [
            {"source": "agent_0", "target": "agent_1", "weight": 0.8, "edge_type": "colleague"},
            {"source": "agent_1", "target": "agent_2", "weight": 0.5, "edge_type": "friend"},
        ],
    }
