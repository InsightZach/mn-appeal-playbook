"""
Tests for the land-extraction sales indicator (TARE Ch. 19) — the lot-size-robust
replacement for the old lot-aware whole-price machinery. Pins: the building-residual
$/SF computation, extraction as the GOVERNING sales signal, the land-line caveat that
suppresses it, and graceful fallback to flat $/SF when the subject's assessed land is
absent (e.g. a Hennepin GIS subject).
"""
from scripts.triage import triage


def _data(assessments=None, subject=None, sales=None, comps=None):
    """Minimal valid collected_data.json shape (mirrors tests/test_triage._data)."""
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


def _ext_sales(n=6, sale_price=350_000, emv_land=100_000, emv_building=270_000,
               sf=2000, year=1990, lot=0.2):
    """n size+vintage+lot-matched sales that ALSO carry the county land/building
    split, so extraction can net land out of each."""
    emv_total = emv_land + emv_building
    return [{
        "pid": f"E{i}", "address": f"{i} Ext St", "plat_name": "OTHER",
        "sale_price": sale_price, "sf": sf, "year_built": year, "lot_acres": lot,
        "emv_total": emv_total, "emv_land": emv_land, "emv_building": emv_building,
        "sale_date": f"2025-0{(i % 8) + 1}-12", "lat": 44.95, "lon": -93.15,
    } for i in range(n)]


def test_extraction_emits_building_residual_indicator():
    """building residual = sale − county assessed land; building $/SF × subject SF +
    subject assessed land. comp 350k − land 100k = 250k / 2000sf = $125/SF; × 2000 +
    subject land 120k = 370k vs 400k EMV → −30k."""
    r = triage(_data(sales=_ext_sales(sale_price=350_000, emv_land=100_000)))
    sci = r["sales_comparison_indicated"]
    assert sci["extraction_building_psf_median"] == 125.0
    assert sci["extraction_subject_land"] == 120_000
    assert sci["extraction_indicated_value"] == 370_000
    assert sci["extraction_gap_vs_emv"] == -30_000
    assert sci["extraction_angle"] is True


def test_extraction_is_the_governing_sales_signal():
    """A below-EMV extraction indication escalates the verdict and headlines the
    land-extraction basis (not the flat $/SF)."""
    r = triage(_data(sales=_ext_sales(sale_price=350_000, emv_land=100_000)))
    assert r["verdict"] == "appeal_angle"
    assert any("Land-extraction" in reason for reason in r["reasons"])


def test_extraction_no_angle_when_at_or_above_emv():
    """comp 420k − land 100k = 320k / 2000 = $160/SF; × 2000 + 120k = 440k > 400k EMV
    → no extraction angle."""
    r = triage(_data(sales=_ext_sales(
        sale_price=420_000, emv_land=100_000, emv_building=300_000)))
    sci = r["sales_comparison_indicated"]
    assert sci["extraction_indicated_value"] == 440_000
    assert sci["extraction_angle"] is False
    assert not any("Land-extraction" in reason for reason in r["reasons"])


def test_extraction_land_caveat_suppresses_angle():
    """When the subject's LAND line is itself rich (assessed land $/SF at/above the
    peer band and not a small-lot size artifact), extraction's add-back re-imports the
    contested land value, so the angle is suppressed — equalization is the lever."""
    r = triage(_data(
        assessments=[
            {"assess_year": 2026, "tax_year": 2027, "emv_total": 400_000,
             "emv_land": 250_000, "emv_building": 150_000, "total_tax": None},
            {"assess_year": 2025, "tax_year": 2026, "emv_total": 390_000,
             "emv_land": 250_000, "emv_building": 150_000, "total_tax": None},
        ],
        sales=_ext_sales(sale_price=220_000, emv_land=80_000, emv_building=160_000),
        # same low-land peers as neighborhood comps so the subject's $250k land reads
        # at the top of the land-$/SF distribution (the equalization land signal).
        comps=_ext_sales(sale_price=220_000, emv_land=80_000, emv_building=160_000)))
    sci = r["sales_comparison_indicated"]
    assert sci["extraction_land_caveat"] is True
    assert sci["extraction_gap_vs_emv"] < 0      # building residual lands below EMV
    assert sci["extraction_angle"] is False       # but the caveat suppresses the angle


def test_extraction_unavailable_falls_back_to_flat_psf():
    """No subject assessed land (Hennepin GIS) → no add-back, extraction_indicated_value
    is None, and the verdict falls back to the flat $/SF (still lot-matched here). The
    comp-derived building $/SF is still reported for the agent to complete by hand."""
    r = triage(_data(
        assessments=[
            {"assess_year": 2026, "tax_year": 2027, "emv_total": 400_000,
             "emv_land": None, "emv_building": None, "total_tax": None},
            {"assess_year": 2025, "tax_year": 2026, "emv_total": 390_000,
             "emv_land": None, "emv_building": None, "total_tax": None},
        ],
        sales=_ext_sales(sale_price=350_000, emv_land=100_000)))
    sci = r["sales_comparison_indicated"]
    assert sci["extraction_indicated_value"] is None
    assert sci["extraction_building_psf_median"] is not None
    # flat $/SF governs: 350k/2000 = $175/SF × 2000 = 350k < 400k EMV → angle
    assert r["verdict"] == "appeal_angle"
