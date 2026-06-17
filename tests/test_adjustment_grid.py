"""
Tests for the regression -> report-grid bridge. Pins: derived rates become
schedule rows carrying fit stats, per-comp dollar adjustments become % of sale
price in the grid, the agent condition read threads through, and the bridge
declines (empty) when the regression is unavailable so the caller can fall back.
"""
from datetime import date, timedelta

from analysis.adjustment_grid import (
    build_schedule_rows, build_grid_rows, build_adjustment_inputs,
)
from analysis.comp_regression import derive_adjustments, SQFT_PER_ACRE

EFF = "2026-01-02"


def _synthetic(n=30, b_sf=150, b_age=-800, b_lot=12, b_time=1500, intercept=100_000):
    comps = []
    for i in range(n):
        sf = 1800 + (i % 7) * 120
        age = 30 + (i % 9) * 5
        lot = 0.15 + (i % 5) * 0.03
        months = i % 12
        lot_sf = lot * SQFT_PER_ACRE
        price = intercept + b_sf * sf + b_age * age + b_lot * lot_sf + b_time * months
        price += ((i * 37) % 500) - 250
        sale_date = (date(2026, 1, 2) - timedelta(days=int(months * 30.44))).isoformat()
        comps.append({"pid": f"C{i}", "address": f"{i} Test St", "sale_price": round(price),
                      "sf": sf, "year_built": 2026 - age, "lot_acres": lot,
                      "sale_date": sale_date})
    return comps


SUBJECT = {"living_area_sf": 2100, "year_built": 1986, "parcel_acres": 0.20}


def test_schedule_rows_carry_fit_stats():
    derived = derive_adjustments(_synthetic(30), {}, EFF)
    rows = build_schedule_rows(derived)
    labels = {r["adjustment"] for r in rows}
    assert any("Size" == l or l.startswith("Size") for l in labels)
    size_row = next(r for r in rows if r["adjustment"].startswith("Size"))
    assert "/ finished SF" in size_row["rate"]
    assert "R²=" in size_row["basis"]
    assert "comps" in size_row["basis"]


def test_schedule_rows_label_effective_age():
    comps = _synthetic(20)
    for c in comps:
        c["effective_year_built"] = c["year_built"]
    derived = derive_adjustments(comps, {}, EFF)
    rows = build_schedule_rows(derived)
    assert any("Effective age" in r["adjustment"] for r in rows)


def test_grid_rows_are_percent_of_sale_price():
    derived = derive_adjustments(_synthetic(30), {}, EFF)
    comps = _synthetic(6)
    rows = build_grid_rows(comps, SUBJECT, derived, EFF)
    assert len(rows) == 6
    r0 = rows[0]
    for field in ("time_pct", "size_pct", "quality_pct", "lot_pct", "condition_pct"):
        assert field in r0
    # subject (2100 SF) is larger than the first comp (1800 SF) -> size adj up
    assert r0["size_pct"] > 0
    # percentages, not dollars: each should be a small magnitude
    assert abs(r0["size_pct"]) < 100


def test_condition_read_threads_through():
    derived = derive_adjustments(_synthetic(30), {}, EFF)
    comps = _synthetic(3)
    cond = {"C0": -8.0, "C1": 0, "C2": 5.5}
    rows = build_grid_rows(comps, SUBJECT, derived, EFF, condition_by_pid=cond)
    by_pid = {c["pid"]: r for c, r in zip(comps, rows)}
    assert by_pid["C0"]["condition_pct"] == -8.0
    assert by_pid["C1"]["condition_pct"] == 0
    assert by_pid["C2"]["condition_pct"] == 5.5


def test_bridge_declines_without_regression():
    assert build_schedule_rows(None) == []
    assert build_grid_rows(_synthetic(3), SUBJECT, None, EFF) == []
    out = build_adjustment_inputs(_synthetic(3), SUBJECT, None, EFF)
    assert out["adjustment_schedule"] == []
    assert out["adjustment_grid"] == []


def test_build_adjustment_inputs_shape():
    derived = derive_adjustments(_synthetic(30), {}, EFF)
    out = build_adjustment_inputs(_synthetic(6), SUBJECT, derived, EFF)
    assert len(out["adjustment_schedule"]) >= 1
    assert len(out["adjustment_grid"]) == 6
    assert "quotable" in (out["derived_adjustments_reliability"] or "").lower()
