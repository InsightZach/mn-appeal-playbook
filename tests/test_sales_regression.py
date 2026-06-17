"""
Contract tests for analysis/sales_regression.py.

Pins the regression/convergence math and the loop's addition: a single model (or
a trivially-tight spread) is a directional screen, NOT a reconciled sales value,
and must carry `central_label` so it cannot be adopted as a defensible ask.
"""
from analysis.sales_regression import (
    compute_sales_trend,
    remove_outliers_iqr,
    predict_at_assessment_date,
    multi_model_convergence,
    compute_psf_from_sale,
)


def test_compute_sales_trend_returns_slope_intercept_r2():
    sales = [
        {"date": "2024-01-01", "psf": 250},
        {"date": "2024-06-01", "psf": 270},
        {"date": "2025-01-01", "psf": 280},
    ]
    trend = compute_sales_trend(sales)
    assert trend["slope"] > 0
    assert {"slope", "intercept", "r2", "n"} <= trend.keys()


def test_remove_outliers_iqr_drops_extremes():
    sales = [{"psf": p} for p in [100, 200, 250, 260, 270, 280, 290, 300, 1000]]
    clean = [s["psf"] for s in remove_outliers_iqr(sales, key="psf")]
    assert 1000 not in clean
    assert 100 not in clean


def test_predict_at_assessment_date_is_linear():
    trend = {"slope": 0.01, "intercept": 100.0, "r2": 0.5}
    v1 = predict_at_assessment_date(trend, "2025-01-01")
    v2 = predict_at_assessment_date(trend, "2026-01-01")
    assert v2 > v1  # positive slope → later date predicts higher


def test_compute_psf_from_sale_uses_override_when_given():
    sale = {"sale_price": 400_000, "sf": 1000}
    assert compute_psf_from_sale(sale) == 400.0
    assert compute_psf_from_sale(sale, subject_sf_override=2000) == 200.0


def test_compute_psf_from_sale_zero_safe():
    assert compute_psf_from_sale({"sale_price": 400_000, "sf": 0}) == 0.0


def test_two_distinct_models_converge_tight():
    models = {
        "subject_plat": {"slope": 0.001, "intercept": 100, "r2": 0.05},
        "other_plats": {"slope": 0.0009, "intercept": 105, "r2": 0.04},
        "combined": {"slope": 0.001, "intercept": 102, "r2": 0.06},
    }
    r = multi_model_convergence(models, target_date="2026-01-02", subject_sf=2881)
    assert r["spread_pct"] < 5
    assert r["verdict"] == "tight"
    # genuine multi-model agreement: NOT a directional-screen-only result.
    assert "central_label" not in r


def test_single_model_is_labeled_directional_screen_only():
    """One model cannot 'converge' — it must be tagged as a directional screen."""
    models = {"combined": {"slope": 0.001, "intercept": 100, "r2": 0.05}}
    r = multi_model_convergence(models, target_date="2026-01-02", subject_sf=2000)
    assert "central_label" in r
    assert "directional screen" in r["central_label"]


def test_trivially_tight_spread_is_also_labeled():
    """Two models that are identical (~0% spread) are not real convergence."""
    models = {
        "a": {"slope": 0.001, "intercept": 100, "r2": 0.05},
        "b": {"slope": 0.001, "intercept": 100, "r2": 0.05},
    }
    r = multi_model_convergence(models, target_date="2026-01-02", subject_sf=2000)
    assert r["spread_pct"] < 0.5
    assert "central_label" in r


def test_empty_models_is_loose_not_crash():
    r = multi_model_convergence({}, target_date="2026-01-02", subject_sf=2000)
    assert r["verdict"] == "loose"
    assert r["values"] == {}
