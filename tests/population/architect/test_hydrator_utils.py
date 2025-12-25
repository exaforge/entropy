"""Tests for hydrator utilities and validation logic."""

from entropy.core.models import (
    HydratedAttribute,
    SamplingConfig,
    NormalDistribution,
    CategoricalDistribution,
    BooleanDistribution,
    Modifier,
    GroundingInfo,
)
from entropy.population.architect.hydrator_utils import (
    validate_independent_hydration,
    validate_derived_hydration,
    validate_conditional_base,
    validate_modifiers,
    validate_strategy_consistency,
    sanitize_formula,
    extract_names_from_condition,
)


class TestHydratorUtils:
    """Tests for hydrator validation functions."""

    def _create_attr(self, name, sampling):
        """Helper to create a dummy HydratedAttribute."""
        return HydratedAttribute(
            name=name,
            type="int",
            category="universal",
            description="Test desc",
            strategy=sampling.strategy,
            sampling=sampling,
            grounding=GroundingInfo(level="low", method="estimated", source="test"),
            depends_on=sampling.depends_on,
        )

    def test_sanitize_formula(self):
        """Test formula sanitization."""
        assert sanitize_formula("  age + 1  ") == "age + 1"
        assert sanitize_formula("true") == "True"
        assert sanitize_formula("false") == "False"
        assert sanitize_formula(None) is None

    def test_extract_names_from_condition(self):
        """Test variable extraction from conditions."""
        names = extract_names_from_condition("age > 18 and gender == 'male'")
        assert "age" in names
        assert "gender" in names
        assert "male" not in names  # String literal
        assert "and" not in names   # Keyword

    def test_validate_independent_valid(self):
        """Test validation of valid independent attributes."""
        attr = self._create_attr(
            name="age",
            sampling=SamplingConfig(
                strategy="independent",
                distribution=NormalDistribution(mean=30, std=5, min=18, max=100)
            )
        )
        errors = validate_independent_hydration([attr])
        assert not errors

    def test_validate_independent_invalid(self):
        """Test validation of invalid independent attributes."""
        # Case 1: Negative Std
        attr1 = self._create_attr(
            name="bad_std",
            sampling=SamplingConfig(
                strategy="independent",
                distribution=NormalDistribution(mean=30, std=-5)
            )
        )
        
        # Case 2: Min >= Max
        attr2 = self._create_attr(
            name="bad_range",
            sampling=SamplingConfig(
                strategy="independent",
                distribution=NormalDistribution(mean=30, std=5, min=100, max=50)
            )
        )
        
        # Case 3: Categorical weights sum mismatch
        # Using type='categorical' but my helper defaults to 'int', need to override if the validator checks type field.
        # But validator mostly checks distribution type.
        attr3 = HydratedAttribute(
            name="bad_weights",
            type="categorical",
            category="universal",
            description="Bad Weights",
            strategy="independent",
            sampling=SamplingConfig(
                strategy="independent",
                distribution=CategoricalDistribution(
                    options=["A", "B"], 
                    weights=[0.1, 0.1]  # Sums to 0.2
                )
            ),
            grounding=GroundingInfo(level="low", method="estimated", source="test"),
        )

        errors = validate_independent_hydration([attr1, attr2, attr3])
        assert len(errors) == 3
        assert any("std" in e for e in errors)
        assert any("min" in e and "max" in e for e in errors)
        assert any("weights sum" in e for e in errors)

    def test_validate_derived(self):
        """Test validation of derived attributes."""
        # Valid
        attr1 = self._create_attr(
            name="age_bracket",
            sampling=SamplingConfig(
                strategy="derived",
                formula="'Adult' if age >= 18 else 'Child'",
                depends_on=["age"]
            )
        )
        attr1.category = "derived"
        attr1.type = "categorical"

        # Invalid: Syntax error
        attr2 = self._create_attr(
            name="bad_syntax",
            sampling=SamplingConfig(
                strategy="derived",
                formula="if age > 10",  # Invalid python expression
                depends_on=["age"]
            )
        )

        # Invalid: Reference not in depends_on
        attr3 = self._create_attr(
            name="missing_dep",
            sampling=SamplingConfig(
                strategy="derived",
                formula="income * 2",
                depends_on=["age"]  # 'income' not declared
            )
        )

        all_names = {"age", "income", "age_bracket", "bad_syntax", "missing_dep"}
        errors = validate_derived_hydration([attr1, attr2, attr3], all_names)
        
        assert not any("age_bracket" in e for e in errors)
        assert any("bad_syntax" in e for e in errors)
        assert any("missing_dep" in e for e in errors)

    def test_validate_modifiers(self):
        """Test validation of conditional modifiers."""
        # Valid modifier
        attr = self._create_attr(
            name="income",
            sampling=SamplingConfig(
                strategy="conditional",
                distribution=NormalDistribution(mean=50000, std=10000),
                modifiers=[
                    Modifier(when="age > 50", multiply=1.5, add=0)
                ],
                depends_on=["age"]
            )
        )
        
        all_attrs = {"age": None, "income": attr}
        errors, warnings = validate_modifiers([attr], all_attrs)
        assert not errors
        assert not warnings

        # Invalid: Categorical using multiply
        attr_bad = HydratedAttribute(
            name="status",
            type="categorical",
            category="population_specific",
            description="Status",
            strategy="conditional",
            sampling=SamplingConfig(
                strategy="conditional",
                distribution=CategoricalDistribution(options=["A", "B"], weights=[0.5, 0.5]),
                modifiers=[
                    Modifier(when="age > 50", multiply=1.5)  # Invalid for categorical
                ],
                depends_on=["age"]
            ),
            grounding=GroundingInfo(level="low", method="estimated", source="test"),
            depends_on=["age"]
        )
        
        errors, warnings = validate_modifiers([attr_bad], all_attrs)
        assert len(errors) > 0
        assert any("categorical distribution cannot use multiply" in e for e in errors)

    def test_validate_strategy_consistency(self):
        """Test strategy consistency checks."""
        # Independent with depends_on (Invalid)
        attr1 = self._create_attr(
            name="bad_indep",
            sampling=SamplingConfig(
                strategy="independent",
                distribution=NormalDistribution(mean=0, std=1),
                depends_on=["age"]  # Error
            )
        )

        errors = validate_strategy_consistency([attr1])
        assert len(errors) > 0
        assert "independent strategy cannot have depends_on" in errors[0]
