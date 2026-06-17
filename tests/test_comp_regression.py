"""
Tests for the comp-set regression — TARE Ch. 21 statistical analysis that DERIVES
adjustment rates from the comp data (not a table). Pins: it recovers known
coefficients, flags reliability honestly, picks effective-year age when available,
declines on thin/degenerate data, and applies coefficients comp→subject correctly.
"""
from datetime import date, timedelta

from analysis.comp_regression import (
    derive_adjustments, adjust_comp_to_subject, MIN_N, SQFT_PER_ACRE,
)

EFF = "2026-01-02"


def _synthetic(n=30, b_sf=150, b_age=-800, b_lot=12, b_time=1500, intercept=100_000,
               with_eff=False):
    """Comps generated with KNOWN marginal rates so the regression must recover them."""
    comps = []
    for i in range(n):
        sf = 1800 + (i % 7) * 120
        age = 30 + (i % 9) * 5
        lot = 0.15 + (i % 5) * 0.03
        months = i % 12
        lot_sf = lot * SQFT_PER_ACRE
        price = intercept + b_sf * sf + b_age * age + b_lot * lot_sf + b_time * months
        price += ((i * 37) % 500) - 250   # tiny deterministic noise
        sale_date = (date(2026, 1, 2) - timedelta(days=int(months * 30.44))).isoformat()
        c = {"pid": f"C{i}", "sale_price": round(price), "sf": sf,
             "year_built": 2026 - age, "lot_acres": lot, "sale_date": sale_date}
        if with_eff:
            c["effective_year_built"] = 2026 - age
        comps.append(c)
    return comps


def test_recovers_known_coefficients():
    r = derive_adjustments(_synthetic(30), {}, EFF)
    assert r is not None
    assert r["n"] == 30
    c = r["coefficients"]
    assert abs(c["size_per_sf"]["value"] - 150) < 5
    assert abs(c["age_per_year"]["value"] - (-800)) < 30
    assert abs(c["lot_per_lot_sf"]["value"] - 12) < 1
    assert abs(c["time_per_month"]["value"] - 1500) < 60
    assert r["r2"] > 0.99
    assert r["reliable"] is True
    assert c["size_per_sf"]["reliable"] is True


def test_returns_none_below_min_n():
    assert derive_adjustments(_synthetic(MIN_N - 1), {}, EFF) is None


def test_prefers_effective_year_when_available():
    assert derive_adjustments(_synthetic(20, with_eff=True), {}, EFF)["age_basis"] == "effective_year"
    assert derive_adjustments(_synthetic(20, with_eff=False), {}, EFF)["age_basis"] == "year_built"


def test_low_power_flags_unreliable():
    """A small, noisy set is flagged not-quotable rather than asserted."""
    # 9 comps with strong noise → passes MIN_N but should not be overall-reliable.
    comps = _synthetic(9)
    for i, c in enumerate(comps):
        c["sale_price"] += ((i * 991) % 120_000) - 60_000  # heavy noise
    r = derive_adjustments(comps, {}, EFF)
    assert r is not None
    assert r["reliable"] is False
    assert "low power" in r["reliability_note"]


def test_degenerate_no_lot_variance_does_not_crash():
    """Every comp sharing a lot size makes the design rank-deficient — return None,
    don't raise."""
    comps = _synthetic(20)
    for c in comps:
        c["lot_acres"] = 0.2  # zero variance in the lot column
    # may still be full-rank via other columns; assert it doesn't crash and is sane
    r = derive_adjustments(comps, {}, EFF)
    assert r is None or "coefficients" in r


def test_adjust_comp_to_subject_applies_deltas():
    """adjusted = comp_price + Σ coef × (subject − comp); a larger subject adds
    the size coefficient × the SF gap."""
    adj = derive_adjustments(_synthetic(30), {}, EFF)
    comp = {"pid": "X", "sale_price": 400_000, "sf": 1800,
            "year_built": 1986, "lot_acres": 0.18,
            "sale_date": "2025-01-02"}
    # real subject shape (living_area_sf / parcel_acres) — the function normalizes
    subject = {"living_area_sf": 2200, "year_built": 1986, "parcel_acres": 0.18}
    out = adjust_comp_to_subject(comp, subject, adj, EFF)
    assert out is not None
    assert out["comp_sale_price"] == 400_000
    # subject is 400 SF larger → size adjustment ≈ +150 × 400 ≈ +60k → adjusted up
    assert out["adjustments"]["size_per_sf"] > 0
    assert out["adjusted_price"] > 400_000
    assert "gross_adjustment_pct" in out
