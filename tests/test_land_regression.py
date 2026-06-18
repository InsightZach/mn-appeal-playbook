"""Tests for the single-vintage land-value regression cross-check."""
from analysis.land_regression import compute_land_regression, SQFT_PER_ACRE


def _comps(year, n=12, a=100_000.0, b=30.0):
    """n comps for `year` on a clean line: land = a + b*lotSF, lots 5k..16k SF."""
    out = []
    for i in range(n):
        lot_sf = 5000 + i * 1000
        out.append({"pid": f"{year}{i:03d}", "emv_year": year,
                    "lot_acres": lot_sf / SQFT_PER_ACRE, "emv_land": a + b * lot_sf,
                    "address": f"{i} Test St"})
    return out


def test_single_vintage_regression_recovers_the_line():
    subj_lot = 9000.0
    # subject land exactly on the line (a + b*lot = 100000 + 30*9000 = 370000)
    r = compute_land_regression(_comps(2026), subj_lot, 370_000.0, 2026)
    assert r["applicable"] and r["n"] == 12
    assert abs(r["value_fit"]["slope"] - 30.0) < 0.01
    assert r["value_fit"]["r2"] > 0.99
    assert r["position"] == "within_range"
    assert r["chart"]["subject_xy"] == {"x": 9000, "y": round(370000 / 9000, 1)}
    assert len(r["chart"]["data"]) == 12


def test_mixes_are_excluded_by_vintage():
    # 12 comps at 2026 + 12 stale 2025 comps on a DIFFERENT line; only 2026 used.
    comps = _comps(2026) + _comps(2025, a=40_000.0, b=20.0)
    r = compute_land_regression(comps, 9000.0, 370_000.0, 2026)
    assert r["n"] == 12                       # the 2025 comps are not mixed in
    assert abs(r["value_fit"]["slope"] - 30.0) < 0.01


def test_too_few_same_vintage_is_not_applicable():
    r = compute_land_regression(_comps(2026, n=5), 9000.0, 370_000.0, 2026)
    assert r["applicable"] is False and "too few" in r["note"]


def test_subject_above_the_line_yields_wiggle_room():
    # subject assessed well above its size-implied land → an argument to bring it down.
    r = compute_land_regression(_comps(2026), 9000.0, 480_000.0, 2026)
    assert r["position"] == "above"
    assert r["wiggle_room"] > 0
    assert r["indicated_land_range"][0] < 480_000


def test_none_inputs_return_none():
    assert compute_land_regression(_comps(2026), 9000.0, 370_000.0, None) is None
    assert compute_land_regression(_comps(2026), None, 370_000.0, 2026) is None
