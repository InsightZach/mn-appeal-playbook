"""
Condition / quality read support — the one input the comp-set regression can't
supply (condition and grade aren't in the county API data).

Two jobs:
  1. Cost-to-cure deductions from condition notes (compute_condition_deductions) —
     dollars to bring a property to typical condition. Used for the subject EMV
     cross-check and to size a quantified condition adjustment.
  2. Qualitative relative-comparison support (condition_bracket / quality_bracket
     / condition_adjustment_pct) — the agent reads the subject + the
     `condition_verify_shortlist` on the methodology house scales (Condition:
     Poor..Excellent; Grade: D..A) and this maps the read onto the sales grid.

Doctrine (TARE 15th, Ch. 21; see prompts/methodology.md "Adjustment discipline"):
condition/quality are the SCARCEST elements to support, so the right move is to
SELECT comps that need no condition adjustment (the assessed-$/SF tier screen +
effective-age match in triage already do this). When a comp is same-tier the
supportable condition adjustment is ZERO. Only quantify a condition adjustment
when a load-bearing comp genuinely diverges — and then derive it (cost-to-cure /
depreciated cost), or bracket it qualitatively. Never import a table %.
"""

# Standard cost ranges for typical residential issues
COST_TO_CURE = {
    "gutted_full_bath": (15000, 25000),
    "gutted_half_bath": (5000, 10000),
    "gutted_basement_rec_area": (20000, 30000),  # per ~400 SF
    "stripped_walls": (15000, 25000),
    "mold_remediation": (10000, 25000),
    "kitchen_remodel": (40000, 80000),
    "roof_repair_per_sq": (300, 600),
    "structural_foundation": (15000, 50000),
}


def compute_condition_deductions(notes: str | None, photos: list[str] = None) -> dict:
    """
    Parse condition notes (free text) into structured deductions.

    Returns:
      {
        "items": [
          {"description": "...", "low": int, "high": int}
        ],
        "total_low": int,
        "total_high": int
      }
    """
    if not notes:
        return {"items": [], "total_low": 0, "total_high": 0}

    items = []
    notes_lower = notes.lower()

    if "half bath" in notes_lower and ("gutted" in notes_lower or "stripped" in notes_lower):
        lo, hi = COST_TO_CURE["gutted_half_bath"]
        items.append({"description": "Half bath reconstruction", "low": lo, "high": hi})

    if "full bath" in notes_lower and ("gutted" in notes_lower or "stripped" in notes_lower):
        lo, hi = COST_TO_CURE["gutted_full_bath"]
        items.append({"description": "Full bath reconstruction", "low": lo, "high": hi})

    if "basement" in notes_lower and ("mold" in notes_lower or "stripped" in notes_lower or "gutted" in notes_lower):
        lo, hi = COST_TO_CURE["gutted_basement_rec_area"]
        items.append({"description": "Basement rec area (mold remediation)", "low": lo, "high": hi})

    if "lath" in notes_lower or "plaster" in notes_lower or "walls stripped" in notes_lower:
        lo, hi = COST_TO_CURE["stripped_walls"]
        items.append({"description": "Interior wall restoration (lath/plaster/drywall)", "low": lo, "high": hi})

    if "mold" in notes_lower:
        lo, hi = COST_TO_CURE["mold_remediation"]
        items.append({"description": "Mold remediation completion", "low": lo, "high": hi})

    return {
        "items": items,
        "total_low": sum(i["low"] for i in items),
        "total_high": sum(i["high"] for i in items),
    }


# -- Qualitative condition / quality bracket (TARE Ch. 21 relative comparison) --

# Ordinal scales from prompts/methodology.md, worst -> best. The agent assigns a
# tier off the listing/CAMA read; these let the bracket be computed mechanically.
CONDITION_SCALE = ["Poor", "Fair", "Average", "Good", "Excellent"]
QUALITY_SCALE = ["D", "C", "B", "A"]  # construction grade

# Aliases the agent might write, normalized onto the scales above.
_CONDITION_ALIASES = {
    "below average": "Fair", "below avg": "Fair", "dated": "Fair",
    "above average": "Good", "above avg": "Good", "updated": "Good",
    "renovated": "Excellent", "remodeled": "Excellent", "new": "Excellent",
    "typical": "Average", "avg": "Average",
}
_QUALITY_ALIASES = {
    "inferior": "C", "average": "B", "baseline": "B", "superior": "A",
}


def _ordinal(value, scale, aliases=None) -> int | None:
    """Index of `value` on `scale` (case-insensitive, alias-aware), or None."""
    if value is None:
        return None
    v = str(value).strip()
    lower = v.lower()
    if aliases and lower in aliases:
        v = aliases[lower]
    for i, level in enumerate(scale):
        if level.lower() == v.lower():
            return i
    # grade letters may arrive with a +/- modifier (e.g. "C+") — take the letter
    if scale is QUALITY_SCALE and v[:1].upper() in scale:
        return scale.index(v[:1].upper())
    return None


def _bracket(comp_level, subject_level, scale, aliases) -> dict:
    """Direction the COMP must move to match the subject, on an ordinal scale.
    Positive `steps` => subject is better => the comp adjusts UP toward it."""
    ci = _ordinal(comp_level, scale, aliases)
    si = _ordinal(subject_level, scale, aliases)
    if ci is None or si is None:
        return {
            "direction": "unknown", "steps": None, "needs_adjustment": None,
            "basis": "tier not established — verify or drop the comp",
        }
    steps = si - ci
    if steps == 0:
        direction = "similar"
    elif steps > 0:
        direction = "comp_inferior"   # comp worse than subject -> adjust comp UP
    else:
        direction = "comp_superior"   # comp better than subject -> adjust comp DOWN
    return {
        "direction": direction,
        "steps": steps,
        "needs_adjustment": steps != 0,
        "basis": "qualitative relative comparison (TARE Ch. 21)",
    }


def condition_bracket(comp_condition, subject_condition) -> dict:
    """Relative-comparison bracket on the Condition scale (Poor..Excellent).
    `similar` => the supportable condition adjustment is ZERO (the goal of the
    tier screen). `unknown` => drop the comp rather than guess."""
    return _bracket(comp_condition, subject_condition, CONDITION_SCALE, _CONDITION_ALIASES)


def quality_bracket(comp_quality, subject_quality) -> dict:
    """Relative-comparison bracket on the construction-grade scale (D..A)."""
    return _bracket(comp_quality, subject_quality, QUALITY_SCALE, _QUALITY_ALIASES)


def condition_adjustment_pct(cure_dollars, comp_sale_price) -> float | None:
    """Convert a derived condition magnitude (the cost-to-cure scope, in $, to
    bring the COMP's condition to the subject's) into a % of the comp's sale
    price for the grid. Sign convention follows the bracket: pass `cure_dollars`
    POSITIVE when the comp is inferior (adjust the comp UP) and NEGATIVE when the
    comp is superior (adjust it DOWN). Returns None when the sale price is missing.

    This is the supportable path to a quantified condition line — a cost-to-cure
    or depreciated-cost dollar figure expressed as a rate — NOT a table %.
    """
    if not comp_sale_price:
        return None
    return round(cure_dollars / float(comp_sale_price) * 100, 2)
