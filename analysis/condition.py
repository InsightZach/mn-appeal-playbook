"""
Translate condition notes into cost-to-cure deductions.

Used by the Appeal Package generator. Not used by the No-Appeal report.
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
