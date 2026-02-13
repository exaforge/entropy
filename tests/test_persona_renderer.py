"""Tests for persona categorical rendering edge cases."""

from entropy.population.persona.config import CategoricalPhrasing
from entropy.population.persona.renderer import _format_categorical_value


def test_categorical_none_like_rewrites_raw_token_phrase():
    phrasing = CategoricalPhrasing(
        attribute="preferred_third_party_app",
        phrases={"none": "I access Reddit none"},
        fallback=None,
    )

    rendered = _format_categorical_value("none", phrasing)
    assert rendered == "I don't have a specific preference here"


def test_categorical_none_like_keeps_natural_phrase():
    phrasing = CategoricalPhrasing(
        attribute="preferred_third_party_app",
        phrases={"none": "I don't use any third-party app to access Reddit"},
        fallback=None,
    )

    rendered = _format_categorical_value("none", phrasing)
    assert rendered == "I don't use any third-party app to access Reddit"


def test_categorical_none_like_uses_clean_fallback():
    phrasing = CategoricalPhrasing(
        attribute="moderation_tool_dependency",
        phrases={"not_applicable": "My dependence is not_applicable"},
        fallback="This doesn't apply to me",
    )

    rendered = _format_categorical_value("not_applicable", phrasing)
    assert rendered == "This doesn't apply to me"
