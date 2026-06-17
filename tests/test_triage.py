"""
Integration-contract tests for scripts/triage.py.

These pin the behaviours the self-improvement loop corrected, end-to-end through
the triage() function:
  - the subject's own sale is surfaced even when it predates the comp window,
    and a STALE own sale (>3-4 yrs) is "corroborating only" — it must NOT flip
    the verdict to appeal by itself;
  - a recent own sale (<2 yrs) below EMV governs → appeal_angle;
  - a 2-3 yr own sale is time-trended;
  - convergence requires >=2 DISTINCT models; a single model is labelled
    `single_model` and cannot trigger the no-angle path;
  - the distressed-sale (<0.80x own EMV) screen flags outliers;
  - equalization carries the p80-band fields;
  - a `supports_appeal` killer comp flips the verdict.

Each test isolates one signal by feeding only the data that signal needs, so the
asserted verdict is attributable to it.
"""
from scripts.triage import triage


def _data(assessments=None, subject=None, comps=None, sales=None):
    """Minimal valid collected_data.json shape. Defaults produce a quiet
    no-angle baseline: flat/rising EMV, no comps, no sales."""
    base_subject = {
        "pid": "SUBJ", "address": "1 Test St", "city": "St Paul",
        "living_area_sf": 2000, "parcel_acres": 0.2, "plat_name": "PLAT_X",
        "year_built": 1990, "lat": 44.95, "lon": -93.15, "structure": None,
        "last_sale_price": None, "last_sale_date": None,
    }
    if subject:
        base_subject.update(subject)
    return {
        "subject": base_subject,
        # newest first; rising so the EMV-decline reason does not fire by default
        "assessments": assessments or [
            {"assess_year": 2026, "tax_year": 2027, "emv_total": 400_000,
             "emv_land": 120_000, "emv_building": 280_000, "total_tax": None},
            {"assess_year": 2025, "tax_year": 2026, "emv_total": 380_000,
             "emv_land": 110_000, "emv_building": 270_000, "total_tax": None},
        ],
        "neighborhood_comps": comps or [],
        "recent_sales": sales or [],
        "county": "ramsey",
    }


# ---------------------------------------------------------------------------
# Subject's own sale
# ---------------------------------------------------------------------------

def test_stale_own_sale_is_corroborating_only_and_does_not_flip_verdict():
    """An 11-yr-old own sale 25% under EMV must surface but NOT create an angle."""
    r = triage(_data(subject={
        "last_sale_price": 300_000, "last_sale_date": "2014-12-01",
    }))
    assert r["subject_own_sale"] is not None
    assert r["subject_own_sale"]["years_before_effective"] > 4
    assert any("corroborating only" in reason for reason in r["reasons"])
    # The stale sale alone is not an appeal angle.
    assert r["verdict"] == "no_angle"


def test_recent_own_sale_below_emv_governs():
    """An own sale <2 yrs old and >5% below EMV governs → appeal_angle."""
    r = triage(_data(sales=[
        {"pid": "SUBJ", "address": "1 Test St", "sale_price": 340_000,
         "sale_date": "2025-06-01", "sf": None, "emv_total": None},
    ]))
    assert r["verdict"] == "appeal_angle"
    assert any("below current EMV" in reason for reason in r["reasons"])


def test_mid_age_own_sale_is_time_trended():
    """A 2-3 yr own sale is time-trended to the effective date."""
    r = triage(_data(sales=[
        {"pid": "SUBJ", "address": "1 Test St", "sale_price": 360_000,
         "sale_date": "2023-07-02", "sf": None, "emv_total": None},
    ]))
    finding = r["subject_own_sale"]
    assert finding is not None
    assert "trended_sale_price" in finding
    assert finding["trended_sale_price"] > finding["sale_price"]
    assert "trended_delta_pct" in finding


# ---------------------------------------------------------------------------
# Sales convergence
# ---------------------------------------------------------------------------

def _sales_no_plat(n=6, base_psf=200, price_sf=2000):
    """n arm's-length sales with SF + dates but no matching plat → single model."""
    out = []
    for i in range(n):
        out.append({
            "pid": f"S{i}", "address": f"{i} Other St", "plat_name": "OTHER",
            "sale_price": int((base_psf + i) * price_sf), "sf": price_sf,
            "sale_date": f"2025-0{(i % 8) + 1}-15", "emv_total": None,
            "lat": 44.95, "lon": -93.15,
        })
    return out


def test_single_model_convergence_is_labeled_and_inert():
    """No same-plat sales → one model → verdict single_model, never no-angle."""
    r = triage(_data(sales=_sales_no_plat()))
    conv = r["sales_convergence"]
    assert conv is not None
    assert conv["verdict"] == "single_model"
    assert "central_label" in conv
    assert "convergence_gap_vs_emv" in conv
    # a single model must not emit a "models converge ... EMV" reason
    assert not any("converge" in reason.lower() for reason in r["reasons"])


def test_two_distinct_plats_allow_real_convergence():
    """>=5 same-plat AND >=5 other-plat sales → distinct models, not single."""
    same = [{
        "pid": f"P{i}", "address": f"{i} Plat St", "plat_name": "PLAT_X",
        "sale_price": int((200 + i) * 2000), "sf": 2000,
        "sale_date": f"2025-0{(i % 8) + 1}-10", "emv_total": None,
        "lat": 44.95, "lon": -93.15,
    } for i in range(5)]
    other = _sales_no_plat(n=5)
    r = triage(_data(sales=same + other))
    assert r["sales_convergence"]["verdict"] != "single_model"


# ---------------------------------------------------------------------------
# Distressed-sale screen
# ---------------------------------------------------------------------------

def test_distressed_sale_below_80pct_own_emv_is_flagged():
    r = triage(_data(sales=[
        {"pid": "D1", "address": "9 Distress St", "sale_price": 200_000,
         "emv_total": 300_000, "sf": 1800, "sale_date": "2025-05-01"},
    ]))
    flagged = r["distressed_sales"]
    assert len(flagged) == 1
    assert flagged[0]["pid"] == "D1"
    assert flagged[0]["sale_to_own_emv_ratio"] < 0.80


# ---------------------------------------------------------------------------
# Equalization p80 band
# ---------------------------------------------------------------------------

def _comps(n=6):
    """n neighborhood comps with the fields equalization needs."""
    out = []
    for i in range(n):
        out.append({
            "pid": f"C{i}", "address": f"{i} Comp St",
            "sf": 1900 + i * 20, "emv_building": 250_000 + i * 5_000,
            "lot_acres": 0.18 + i * 0.01, "emv_land": 100_000 + i * 2_000,
            "lat": 44.95, "lon": -93.15,
        })
    return out


def test_equalization_carries_p80_band_fields():
    r = triage(_data(comps=_comps()))
    eq = r["equalization"]
    assert eq is not None
    for key in ("comp_p80_building_psf", "comp_p80_land_psf",
                "equalized_total_p80", "median_gap_vs_emv",
                "building_psf_percentile"):
        assert key in eq


# ---------------------------------------------------------------------------
# Killer comp drives the verdict
# ---------------------------------------------------------------------------

def test_supports_appeal_killer_comp_flips_verdict():
    """A comp that sold below its OWN EMV (real over-assessment) → appeal_angle."""
    r = triage(_data(sales=[
        {"pid": "K1", "address": "5 Killer St", "sale_price": 350_000,
         "emv_total": 400_000, "sf": 2000, "sale_date": "2025-04-01",
         "lat": 44.95, "lon": -93.15},
    ]))
    assert r["killer_comp"]["verdict"] == "supports_appeal"
    assert r["verdict"] == "appeal_angle"
    assert any("Best comp" in reason for reason in r["reasons"])


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------

def test_triage_emits_the_documented_top_level_keys():
    """docs/10-data-schema.md analysis.json contract."""
    r = triage(_data())
    for key in ("subject", "assess_date", "emv_history", "subject_own_sale",
                "killer_comp", "sales_convergence", "distressed_sales",
                "equalization", "tax_economics", "verdict", "reasons"):
        assert key in r
    assert r["verdict"] in ("appeal_angle", "borderline", "no_angle")
    assert r["tax_economics"]["etr_proxy_source"] in (
        "prior_year_tax", "county_default")
