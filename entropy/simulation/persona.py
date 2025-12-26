"""Persona rendering for agent reasoning.

Converts agent attributes into natural language personas using
templates stored in the PopulationSpec.
"""

from typing import Any

from ..core.models import PopulationSpec


def render_persona(agent: dict[str, Any], template: str) -> str:
    """Render persona string from template and agent attributes.

    Uses Python's str.format() for simple {attribute} placeholder substitution.

    Args:
        agent: Agent dictionary with attributes
        template: Template string with {attribute_name} placeholders

    Returns:
        Rendered persona string
    """
    try:
        return template.format(**agent)
    except KeyError as e:
        # Missing attribute - use fallback
        return _fallback_persona(agent, missing_key=str(e))
    except Exception:
        return _fallback_persona(agent)


def _fallback_persona(agent: dict[str, Any], missing_key: str | None = None) -> str:
    """Generate a basic fallback persona when template fails."""
    parts = []

    age = agent.get("age")
    gender = agent.get("gender", "person")

    if age:
        parts.append(f"You are a {int(age)}-year-old {gender}.")
    else:
        parts.append(f"You are a {gender}.")

    # Add a few key attributes
    for key in ("role", "occupation", "specialty", "employer_type", "years_experience"):
        if key in agent and agent[key]:
            parts.append(f"Your {key.replace('_', ' ')} is {agent[key]}.")
            if len(parts) >= 4:
                break

    return " ".join(parts)


def generate_persona(
    agent: dict[str, Any],
    population_spec: PopulationSpec | None = None,
) -> str:
    """Generate a natural language persona from agent attributes.

    Uses the persona_template from the spec if available.
    Falls back to a basic description otherwise.

    Args:
        agent: Agent dictionary with attributes
        population_spec: Optional population spec containing persona_template

    Returns:
        Natural language persona string
    """
    if population_spec and population_spec.meta.persona_template:
        return render_persona(agent, population_spec.meta.persona_template)

    return _fallback_persona(agent)
