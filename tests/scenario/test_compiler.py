"""Tests for scenario compiler."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from entropy.scenario.compiler import create_scenario
from entropy.core.models import (
    ScenarioSpec,
    Event,
    EventType,
    SeedExposure,
    InteractionConfig,
    InteractionType,
    SpreadConfig,
    OutcomeConfig,
    ValidationResult,
    PopulationSpec,
)


class TestCompiler:
    """Tests for scenario compiler orchestrator."""

    @pytest.fixture
    def mock_files(self, tmp_path, sample_spec):
        """Create dummy input files."""
        pop_path = tmp_path / "population.yaml"
        sample_spec.to_yaml(pop_path)

        agents_path = tmp_path / "agents.json"
        with open(agents_path, "w") as f:
            json.dump([{"_id": "agent_0"}], f)

        network_path = tmp_path / "network.json"
        with open(network_path, "w") as f:
            json.dump({"meta": {"node_count": 1}, "edges": []}, f)

        return pop_path, agents_path, network_path

    @patch("entropy.scenario.compiler.validate_scenario")
    @patch("entropy.scenario.compiler.define_outcomes")
    @patch("entropy.scenario.compiler.determine_interaction_model")
    @patch("entropy.scenario.compiler.generate_seed_exposure")
    @patch("entropy.scenario.compiler.parse_scenario")
    def test_create_scenario_flow(
        self,
        mock_parse,
        mock_exposure,
        mock_interaction,
        mock_outcomes,
        mock_validate,
        mock_files,
        tmp_path,
        sample_spec
    ):
        """Test the full flow of create_scenario with mocked steps."""
        pop_path, agents_path, network_path = mock_files

        # Mock return values for each step
        mock_parse.return_value = Event(
            type=EventType.ANNOUNCEMENT,
            content="Test content",
            source="Test source",
            credibility=1.0,
            ambiguity=0.0,
            emotional_valence=0.0
        )
        
        mock_exposure.return_value = SeedExposure(channels=[], rules=[])
        
        mock_interaction.return_value = (
            InteractionConfig(primary_model=InteractionType.PASSIVE_OBSERVATION, description="Test interaction"),
            SpreadConfig(share_probability=0.5)
        )
        
        mock_outcomes.return_value = OutcomeConfig(suggested_outcomes=[])
        
        mock_validate.return_value = ValidationResult(valid=True, errors=[], warnings=[])

        # Run compiler
        output_path = tmp_path / "scenario.yaml"
        spec, result = create_scenario(
            "Test scenario description",
            pop_path,
            agents_path,
            network_path,
            output_path=output_path
        )

        assert isinstance(spec, ScenarioSpec)
        assert result.valid is True
        assert output_path.exists()
        
        # Verify inputs were loaded/called
        mock_parse.assert_called_once()
        mock_exposure.assert_called_once()
        mock_interaction.assert_called_once()
        mock_outcomes.assert_called_once()
        
        # Verify metadata
        assert spec.meta.population_spec == str(pop_path)
        assert spec.meta.agents_file == str(agents_path)
        assert spec.meta.network_file == str(network_path)

    def test_missing_files(self, tmp_path):
        """Test error when input files are missing."""
        with pytest.raises(FileNotFoundError):
            create_scenario(
                "Test",
                tmp_path / "nonexistent.yaml",
                tmp_path / "agents.json",
                tmp_path / "network.json"
            )
