"""Tests for context sufficiency check."""

from unittest.mock import patch

from entropy.population.architect.sufficiency import check_sufficiency
from entropy.core.models import SufficiencyResult


class TestSufficiency:
    """Tests for sufficiency check logic."""

    @patch("entropy.population.architect.sufficiency.simple_call")
    def test_sufficient_input(self, mock_simple_call):
        """Test with sufficient input description."""
        mock_simple_call.return_value = {
            "sufficient": True,
            "size": 500,
            "geography": "Germany",
            "clarifications_needed": [],
        }

        result = check_sufficiency("500 German surgeons")

        assert isinstance(result, SufficiencyResult)
        assert result.sufficient is True
        assert result.size == 500
        assert result.geography == "Germany"
        assert result.clarifications_needed == []

        # Verify LLM call structure
        mock_simple_call.assert_called_once()
        call_kwargs = mock_simple_call.call_args.kwargs
        assert "500 German surgeons" in call_kwargs["prompt"]
        assert call_kwargs["model"] == "gpt-5-mini"

    @patch("entropy.population.architect.sufficiency.simple_call")
    def test_insufficient_input(self, mock_simple_call):
        """Test with insufficient input description."""
        mock_simple_call.return_value = {
            "sufficient": False,
            "size": 1000,
            "geography": None,
            "clarifications_needed": ["Who are the users?"],
        }

        result = check_sufficiency("users")

        assert result.sufficient is False
        assert result.clarifications_needed == ["Who are the users?"]

    @patch("entropy.population.architect.sufficiency.simple_call")
    def test_default_size_fallback(self, mock_simple_call):
        """Test fallback to default size."""
        mock_simple_call.return_value = {
            "sufficient": True,
            # LLM returns explicit None or missing size, or just copies default
            "size": 2000,  # Simulate LLM extracting a different size if it wants
            "geography": "US",
            "clarifications_needed": [],
        }

        # If LLM returns a size, we use it
        result = check_sufficiency("surgeons", default_size=1000)
        assert result.size == 2000

        # If LLM returns input default
        mock_simple_call.return_value["size"] = 1000
        result = check_sufficiency("surgeons", default_size=1000)
        assert result.size == 1000
