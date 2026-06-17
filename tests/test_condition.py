"""
Tests for the condition-read support — the qualitative relative-comparison
bracket and the cost-to-cure -> grid-% converter that turn the agent's condition
read into supportable sales-grid lines. Pins: same-tier => zero adjustment,
direction signs, alias normalization, unknown => drop, and the % conversion.
"""
from analysis.condition import (
    condition_bracket, quality_bracket, condition_adjustment_pct,
    compute_condition_deductions, CONDITION_SCALE,
)


def test_same_condition_tier_needs_no_adjustment():
    b = condition_bracket("Average", "Average")
    assert b["direction"] == "similar"
    assert b["steps"] == 0
    assert b["needs_adjustment"] is False


def test_comp_inferior_adjusts_up():
    # subject is renovated (Excellent), comp is Average -> comp adjusts UP.
    b = condition_bracket("Average", "Excellent")
    assert b["direction"] == "comp_inferior"
    assert b["steps"] > 0
    assert b["needs_adjustment"] is True


def test_comp_superior_adjusts_down():
    b = condition_bracket("Good", "Fair")
    assert b["direction"] == "comp_superior"
    assert b["steps"] < 0


def test_condition_aliases_normalize():
    # "dated" -> Fair, "renovated" -> Excellent
    b = condition_bracket("dated", "renovated")
    assert b["direction"] == "comp_inferior"
    assert b["steps"] == CONDITION_SCALE.index("Excellent") - CONDITION_SCALE.index("Fair")


def test_unknown_condition_flags_drop():
    b = condition_bracket(None, "Average")
    assert b["direction"] == "unknown"
    assert b["needs_adjustment"] is None
    assert "drop" in b["basis"].lower()


def test_quality_bracket_grade_letters():
    # subject grade A, comp grade C -> comp inferior (adjust up)
    b = quality_bracket("C", "A")
    assert b["direction"] == "comp_inferior"
    assert b["steps"] == 2
    # +/- modifiers tolerated
    assert quality_bracket("C+", "B")["direction"] == "comp_inferior"


def test_quality_alias_superior_inferior():
    assert quality_bracket("inferior", "superior")["direction"] == "comp_inferior"


def test_condition_adjustment_pct_signs():
    # comp inferior -> positive cure dollars -> positive %
    assert condition_adjustment_pct(20_000, 400_000) == 5.0
    # comp superior -> negative dollars -> negative %
    assert condition_adjustment_pct(-20_000, 400_000) == -5.0
    # missing sale price -> None, never a crash
    assert condition_adjustment_pct(20_000, 0) is None


def test_cost_to_cure_still_parses_notes():
    """The existing cost-to-cure path is untouched by the new helpers."""
    d = compute_condition_deductions("gutted full bath and mold in basement")
    assert d["total_low"] > 0
    assert any("bath" in i["description"].lower() for i in d["items"])
