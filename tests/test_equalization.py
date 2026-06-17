"""
Contract tests for analysis/equalization.py — land/building $/SF trends and the
two-cluster split used when a neighborhood has distinct platted value tiers.
"""
from analysis.equalization import (
    compute_land_psf_trend,
    compute_building_psf_trend,
    apply_trend_to_subject,
    identify_two_clusters,
)


def test_land_trend_returns_slope_intercept_r2():
    points = [
        {"lot_sf": 6000, "land": 115_500},
        {"lot_sf": 9000, "land": 136_200},
        {"lot_sf": 12000, "land": 332_500},
        {"lot_sf": 14000, "land": 357_900},
    ]
    r = compute_land_psf_trend(points)
    assert {"slope", "intercept", "r2", "n"} <= r.keys()
    assert r["n"] == 4


def test_building_trend_skips_missing_points():
    points = [
        {"sf": 2000, "bldg": 300_000},
        {"sf": 2500, "bldg": 360_000},
        {"sf": None, "bldg": 400_000},   # skipped
        {"sf": 3000, "bldg": 420_000},
    ]
    r = compute_building_psf_trend(points)
    assert r["n"] == 3


def test_apply_trend_to_subject():
    trend = {"slope": -0.001, "intercept": 30.0, "r2": 0.5}
    psf, value = apply_trend_to_subject(trend, lot_sf=12000)
    assert psf == 18.0          # 30 - 0.001*12000
    assert value == 216_000     # 18 * 12000


def test_identify_two_clusters_by_value_tier():
    points = [
        {"lot_sf": 6000, "land": 162_000},  # $27/SF → high
        {"lot_sf": 6000, "land": 162_000},
        {"lot_sf": 6000, "land": 108_000},  # $18/SF → low
        {"lot_sf": 6000, "land": 108_000},
    ]
    high, low = identify_two_clusters(points, threshold=22)
    assert len(high) == 2
    assert len(low) == 2


def test_under_two_points_returns_zeroed_trend():
    r = compute_land_psf_trend([{"lot_sf": 6000, "land": 115_500}])
    assert r["n"] == 1
    assert r["slope"] == 0


def test_identical_lot_sizes_do_not_crash():
    """Degenerate x (every comp shares a lot size, common in a uniform plat) has
    no slope — must fall back to a flat mean, not raise ZeroDivisionError."""
    points = [{"lot_sf": 8000, "land": 110_000 + i * 1_000} for i in range(6)]
    r = compute_land_psf_trend(points)
    assert r["slope"] == 0
    assert r["n"] == 6
    assert r["intercept"] > 0  # mean of the $/SF values
