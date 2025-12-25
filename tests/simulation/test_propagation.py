"""Tests for exposure and propagation logic."""

import random
from unittest.mock import MagicMock
from datetime import datetime

import pytest

from entropy.simulation.propagation import (
    apply_seed_exposures,
    propagate_through_network,
    calculate_share_probability,
)
from entropy.core.models import (
    ScenarioSpec,
    ScenarioMeta,
    Event,
    EventType,
    SeedExposure,
    ExposureRule,
    ExposureChannel,
    SpreadConfig,
    SpreadModifier,
    InteractionConfig,
    InteractionType,
    OutcomeConfig,
    SimulationConfig,
)
from entropy.simulation.state import StateManager


class TestPropagation:
    """Tests for propagation logic."""

    @pytest.fixture
    def mock_state_manager(self):
        """Mock StateManager."""
        return MagicMock(spec=StateManager)

    @pytest.fixture
    def basic_scenario(self, sample_spec):
        """Create a basic scenario spec."""
        return ScenarioSpec(
            meta=ScenarioMeta(
                name="test_scenario",
                description="Test scenario",
                population_spec="pop.yaml",
                agents_file="agents.json",
                network_file="network.json",
                created_at=datetime.now(),
            ),
            event=Event(
                type=EventType.ANNOUNCEMENT,
                content="Test",
                source="Source",
                credibility=1.0,
                ambiguity=0.0,
                emotional_valence=0.0,
            ),
            seed_exposure=SeedExposure(
                channels=[ExposureChannel(name="email", description="Email", reach="broadcast")],
                rules=[
                    ExposureRule(channel="email", when="true", probability=1.0, timestep=0),
                    ExposureRule(channel="email", when="age > 50", probability=1.0, timestep=1),
                ],
            ),
            interaction=InteractionConfig(
                primary_model=InteractionType.PASSIVE_OBSERVATION,
                description="Test interaction"
            ),
            spread=SpreadConfig(share_probability=0.5),
            outcomes=OutcomeConfig(),
            simulation=SimulationConfig(max_timesteps=10),
        )

    def test_seed_exposure_basic(self, basic_scenario, sample_agents, mock_state_manager):
        """Test basic seed exposure application."""
        rng = random.Random(42)
        
        # Timestep 0: Rule matches all (when="true")
        count = apply_seed_exposures(0, basic_scenario, sample_agents, mock_state_manager, rng)
        
        assert count == len(sample_agents)
        assert mock_state_manager.record_exposure.call_count == len(sample_agents)

    def test_seed_exposure_conditional(self, basic_scenario, sample_agents, mock_state_manager):
        """Test conditional seed exposure (age > 50)."""
        rng = random.Random(42)
        
        # Reset mock
        mock_state_manager.record_exposure.reset_mock()
        
        # Timestep 1: Rule matches age > 50
        # In sample_agents:
        # agent_0: 35 (no)
        # agent_1: 55 (yes)
        # agent_2: 25 (no)
        
        count = apply_seed_exposures(1, basic_scenario, sample_agents, mock_state_manager, rng)
        
        assert count == 1
        # Check that it was agent_1
        args, _ = mock_state_manager.record_exposure.call_args
        assert args[0] == "agent_1"

    def test_network_propagation(self, basic_scenario, sample_agents, sample_network, mock_state_manager):
        """Test network propagation from sharers."""
        rng = random.Random(42)
        
        # Mock sharers: agent_0 will share
        mock_state_manager.get_sharers.return_value = ["agent_0"]
        
        # Network edges:
        # agent_0 -> agent_1 (weight 0.8)
        # agent_1 -> agent_2 (weight 0.5)
        
        # With base share_prob=0.5, agent_0 should share to agent_1 with 50% chance
        # For testing, we force probability to 1.0 via spread config
        basic_scenario.spread.share_probability = 1.0
        
        count = propagate_through_network(
            1, basic_scenario, sample_agents, sample_network, mock_state_manager, rng
        )
        
        # agent_0 shares to agent_1
        assert count == 1
        args, _ = mock_state_manager.record_exposure.call_args
        assert args[0] == "agent_1"

    def test_calculate_share_probability(self):
        """Test modifier application on share probability."""
        agent = {"age": 60, "role": "chief"}
        edge = {"type": "colleague", "weight": 0.8}
        rng = random.Random(42)
        
        # Base config
        config = SpreadConfig(
            share_probability=0.5,
            share_modifiers=[
                SpreadModifier(when="age > 50", multiply=1.5, add=0.0),
                SpreadModifier(when="edge_type == 'colleague'", multiply=1.0, add=0.1)
            ]
        )
        
        # Expected: 0.5 * 1.5 + 0.1 = 0.75 + 0.1 = 0.85
        prob = calculate_share_probability(agent, edge, config, rng)
        
        assert prob == 0.85