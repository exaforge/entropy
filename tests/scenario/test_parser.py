"""Tests for scenario parsing."""

from unittest.mock import patch, MagicMock
from entropy.scenario.parser import parse_scenario
from entropy.core.models import Event, EventType


class TestParser:
    """Tests for scenario parser."""

    @patch("entropy.scenario.parser.reasoning_call")
    def test_parse_scenario_basic(self, mock_reasoning, sample_spec):
        """Test parsing a simple scenario."""
        mock_reasoning.return_value = {
            "event_type": "announcement",
            "content": "Official announcement text",
            "source": "Company X",
            "credibility": 0.95,
            "ambiguity": 0.1,
            "emotional_valence": -0.5,
            "reasoning": "Test reasoning"
        }

        event = parse_scenario(
            "Company X announces price hike",
            sample_spec
        )

        assert isinstance(event, Event)
        assert event.type == EventType.ANNOUNCEMENT
        assert event.content == "Official announcement text"
        assert event.source == "Company X"
        assert event.credibility == 0.95
        assert event.ambiguity == 0.1
        assert event.emotional_valence == -0.5

    @patch("entropy.scenario.parser.reasoning_call")
    def test_parse_scenario_clamping(self, mock_reasoning, sample_spec):
        """Test that values are clamped to valid ranges."""
        mock_reasoning.return_value = {
            "event_type": "rumor",
            "content": "Rumor text",
            "source": "Anonymous",
            "credibility": 1.5,  # Too high, should be 1.0
            "ambiguity": -0.5,   # Too low, should be 0.0
            "emotional_valence": -2.0, # Too low, should be -1.0
            "reasoning": "Test"
        }

        event = parse_scenario("Rumor", sample_spec)

        assert event.credibility == 1.0
        assert event.ambiguity == 0.0
        assert event.emotional_valence == -1.0
