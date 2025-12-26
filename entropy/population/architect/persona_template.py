"""Persona template generation via LLM.

Generates templates for converting agent attributes into natural language
personas. Templates use Python's {attribute} format placeholders.
"""

from ...core.llm import simple_call
from ...core.models import PopulationSpec, AttributeSpec


# JSON Schema for persona template generation response
PERSONA_TEMPLATE_SCHEMA = {
    "type": "object",
    "properties": {
        "template": {
            "type": "string",
            "description": "A first-person persona template using {attribute_name} placeholders",
        },
    },
    "required": ["template"],
    "additionalProperties": False,
}


def _build_attribute_summary(attributes: list[AttributeSpec]) -> str:
    """Build a summary of available attributes for the prompt."""
    lines = []

    for attr in attributes:
        type_info = attr.type
        if attr.sampling and attr.sampling.distribution:
            dist = attr.sampling.distribution
            if hasattr(dist, "options") and dist.options:
                type_info = f"categorical: {', '.join(dist.options[:5])}"
                if len(dist.options) > 5:
                    type_info += ", ..."
        lines.append(f"- {attr.name} ({type_info}): {attr.description}")

    return "\n".join(lines)


def generate_persona_template(
    spec: PopulationSpec,
    log: bool = True,
) -> str:
    """Generate a persona template for a population spec.

    Uses LLM to create a natural, population-appropriate template that
    converts agent attributes into first-person persona narratives.

    Args:
        spec: Population specification with attributes
        log: Whether to log the LLM call

    Returns:
        Template string with {attribute} placeholders
    """
    attribute_summary = _build_attribute_summary(spec.attributes)

    prompt = f"""Generate a persona template for agents in this population:

Population: {spec.meta.description}
Geography: {spec.meta.geography or "Not specified"}

Available attributes:
{attribute_summary}

Write a 3-5 sentence first-person description using {{attribute_name}} placeholders.

Rules:
- Use ONLY attributes from the list above
- Focus on: identity, role, professional context, relevant behavioral traits
- Don't include EVERY attribute, just the most important ones for this population
- Write naturally, not like a form
- Use {{attribute_name}} syntax for placeholders (curly braces)

Example output:
"You are a {{age}}-year-old {{gender}} surgeon specializing in {{surgical_specialty}}. You work at a {{employer_type}} in {{federal_state}} with {{years_experience}} years of experience. You consider yourself {{ai_trust_level}} when it comes to AI tools in clinical practice."

Output only the template string, no explanation."""

    try:
        response = simple_call(
            prompt=prompt,
            response_schema=PERSONA_TEMPLATE_SCHEMA,
            schema_name="persona_template",
            log=log,
        )
        template = response.get("template", "")
        if template:
            return template
    except Exception:
        pass

    # Fallback if LLM fails
    return _fallback_template(spec.attributes)


def _fallback_template(attributes: list[AttributeSpec]) -> str:
    """Generic fallback if LLM fails."""
    # Pick key attributes
    key_attrs = []
    for a in attributes:
        if a.name in ("age", "gender"):
            key_attrs.insert(0, a.name)
        elif a.category in ("universal", "population_specific") and len(key_attrs) < 8:
            key_attrs.append(a.name)

    if not key_attrs:
        key_attrs = [a.name for a in attributes[:5]]

    placeholders = ", ".join(f"{{{a}}}" for a in key_attrs)
    return f"You are an agent with these characteristics: {placeholders}."


def validate_persona_template(template: str, sample_agent: dict) -> tuple[bool, str]:
    """Validate a persona template by rendering it with a sample agent.

    Args:
        template: Template string with {attribute} placeholders
        sample_agent: Sample agent dictionary with attributes

    Returns:
        Tuple of (is_valid, error_message_or_rendered_result)
    """
    try:
        result = template.format(**sample_agent)
        return True, result.strip()
    except KeyError as e:
        return False, f"Missing attribute: {e}"
    except Exception as e:
        return False, f"Template error: {str(e)}"


def refine_persona_template(
    current_template: str,
    spec: PopulationSpec,
    feedback: str,
    log: bool = True,
) -> str:
    """Refine a persona template based on user feedback.

    Args:
        current_template: The current template to refine
        spec: Population specification
        feedback: User feedback on what to change
        log: Whether to log the LLM call

    Returns:
        Refined template string
    """
    attribute_summary = _build_attribute_summary(spec.attributes)

    prompt = f"""Refine this persona template based on user feedback.

Population: {spec.meta.description}

Available attributes:
{attribute_summary}

Current template:
{current_template}

User feedback: {feedback}

Rules:
- Use ONLY attributes from the list above
- Use {{attribute_name}} syntax for placeholders
- Keep it 3-5 sentences
- Write naturally in first person

Output only the refined template string, no explanation."""

    try:
        response = simple_call(
            prompt=prompt,
            response_schema=PERSONA_TEMPLATE_SCHEMA,
            schema_name="persona_template",
            log=log,
        )
        template = response.get("template", "")
        if template:
            return template
    except Exception:
        pass

    return current_template  # Return original if refinement fails
