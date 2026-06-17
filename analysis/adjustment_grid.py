"""
Bridge the comp-set regression (analysis/comp_regression.py) into the report's
adjustment grid + schedule (report/shared_components.render_adjustment_grid /
render_adjustment_schedule).

The regression DERIVES the size / age / lot / time adjustment rates from the
comp data (TARE Ch. 21 statistical analysis) as dollar coefficients. The report
grid wants, per comp, a set of percentage-of-sale-price adjustments. This module
applies the coefficients to each comp (adjust_comp_to_subject) and expresses each
dollar adjustment as a % of that comp's sale price, so the rendered packet shows
DATA-DERIVED rates carrying their n / R² / t-stat / reliability — not authored
numbers.

Condition / quality are NOT in the regression (not in the county data). They are
supplied by the agent condition read (analysis/condition.py + the run-appeal-
review 3b step) as an optional per-comp `condition_pct` and threaded straight
through to the grid.

The mapping onto the grid's columns:
    time_per_month   -> time_pct   (Time)
    size_per_sf      -> size_pct   (Size)        [total-value grid mode]
    age_per_year     -> quality_pct (Quality)    [age / effective age is the
                                                  build-quality proxy where grade
                                                  is unpublished — methodology.md]
    lot_per_lot_sf   -> lot_pct    (Lot)
    (condition read) -> condition_pct (Cond.)
"""
from __future__ import annotations

from analysis.comp_regression import adjust_comp_to_subject

# regression coefficient key -> (grid pct field, schedule label, unit formatter)
_RATE_MAP = [
    ("time_per_month", "time_pct", "Time"),
    ("size_per_sf", "size_pct", "Size"),
    ("age_per_year", "quality_pct", "Age / effective age (build-quality proxy)"),
    ("lot_per_lot_sf", "lot_pct", "Lot"),
]


def _fmt_rate(key: str, value: float) -> str:
    """Human rate string for the schedule, in the coefficient's native unit."""
    if key == "size_per_sf":
        return f"${value:,.0f} / finished SF"
    if key == "age_per_year":
        return f"${value:,.0f} / year of age"
    if key == "lot_per_lot_sf":
        return f"${value:,.2f} / lot SF"
    if key == "time_per_month":
        return f"${value:,.0f} / month"
    return f"{value:,.2f}"


def build_schedule_rows(derived: dict | None) -> list[dict]:
    """Adjustment-schedule rows (one per derived rate) with the fit statistics
    in the basis column so the packet states a supportable rate, not an eyeball.
    Returns [] when there are no derived adjustments to show."""
    if not derived or not derived.get("coefficients"):
        return []
    coefs = derived["coefficients"]
    n = derived.get("n")
    r2 = derived.get("r2")
    age_basis = derived.get("age_basis", "year_built")
    quotable = derived.get("reliable")
    rows = []
    for key, _grid_field, label in _RATE_MAP:
        c = coefs.get(key)
        if not c:
            continue
        lbl = label
        if key == "age_per_year" and age_basis == "effective_year":
            lbl = "Effective age (condition-adjusted, build-quality proxy)"
        t = c.get("t_stat")
        rel = "supported" if c.get("reliable") else "weak (corroborate before quoting)"
        basis = (
            f"OLS regression on {n} comps, R²={r2}, t={t} — {rel}"
            + ("" if quotable else "; overall fit low-power, treat as directional")
        )
        rows.append({
            "adjustment": lbl,
            "rate": _fmt_rate(key, c.get("value")),
            "basis": basis,
        })
    return rows


def build_grid_rows(
    comps: list[dict],
    subject: dict,
    derived: dict | None,
    assess_date: str,
    condition_by_pid: dict | None = None,
    descriptor_by_pid: dict | None = None,
) -> list[dict]:
    """Per-comp total-value grid rows with DATA-DERIVED percentage adjustments.

    Each comp's dollar adjustments (from the regression coefficients applied
    comp->subject) are expressed as a % of that comp's sale price. `condition_pct`
    comes from the agent condition read (condition_by_pid), defaulting to 0 — the
    supportable outcome for a same-tier comp. Returns [] when the regression is
    unavailable (the caller falls back to authored grid input).
    """
    if not derived or not derived.get("coefficients"):
        return []
    condition_by_pid = condition_by_pid or {}
    descriptor_by_pid = descriptor_by_pid or {}
    rows = []
    for comp in comps:
        applied = adjust_comp_to_subject(comp, subject, derived, assess_date)
        if applied is None:
            continue
        sale = applied["comp_sale_price"]
        if not sale:
            continue
        adj = applied["adjustments"]   # dollars, keyed by coefficient name

        def pct(key: str) -> float:
            return round(adj.get(key, 0) / sale * 100, 2)

        pid = comp.get("pid")
        rows.append({
            "address": comp.get("address") or pid,
            "descriptor": descriptor_by_pid.get(pid, comp.get("descriptor", "")),
            "sale_price": sale,
            "sale_date": comp.get("sale_date") or "",
            "sf": comp.get("sf"),
            "time_pct": pct("time_per_month"),
            "size_pct": pct("size_per_sf"),
            "quality_pct": pct("age_per_year"),
            "lot_pct": pct("lot_per_lot_sf"),
            "condition_pct": condition_by_pid.get(pid, 0),
        })
    return rows


def build_adjustment_inputs(
    comps: list[dict],
    subject: dict,
    derived: dict | None,
    assess_date: str,
    condition_by_pid: dict | None = None,
    descriptor_by_pid: dict | None = None,
) -> dict:
    """One-shot: assemble the report data-dict fragment the appeal generator
    consumes — `adjustment_schedule` (derived rates + fit stats) and
    `adjustment_grid` (per-comp derived percentages, total-value mode). Empty
    lists when the regression is unavailable so the caller can fall back."""
    return {
        "adjustment_schedule": build_schedule_rows(derived),
        "adjustment_grid": build_grid_rows(
            comps, subject, derived, assess_date,
            condition_by_pid, descriptor_by_pid),
        "derived_adjustments_reliability": (
            derived.get("reliability_note") if derived else None),
    }
