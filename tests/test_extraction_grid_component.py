"""
Tests for the report's above-grade extraction grid component
(report/shared_components.render_extraction_grid) and the appeal-generator wiring
that renders it as section 4.3. Pins: the build-down math (sale − land − basement
− garage → above-grade $/SF → adjusted → indicated), the bracketed/median stats,
and that an `extraction_grid` data field actually triggers the Sales Comparison
section (the bug that silently dropped the whole grid).
"""
from report.shared_components import render_extraction_grid, render_equalization_table
from report.appeal_generator import generate_appeal_report

COMPS = [
    {"address": "1704 Eustis", "sale_price": 247_000, "land": 57_500, "absf": 1020,
     "fin_bsmt_sf": 275, "garage_sf": 240, "time_pct": 2.5, "quality_pct": 8, "condition_pct": 0},
    {"address": "1369 Brompton", "sale_price": 560_000, "land": 129_800, "absf": 1210,
     "fin_bsmt_sf": 0, "garage_sf": 484, "time_pct": 1, "quality_pct": -8, "condition_pct": -42},
]


def test_extraction_grid_build_down_and_indicated():
    html = render_extraction_grid(COMPS, subject_absf=1440, subject_land=182_600,
                                  bsmt_psf=50, gar_psf=30, econ_psf_per_sf=0.06)
    assert "<table" in html
    # 1704 Eustis: 247,000 − 57,500 − 275×50 − 240×30 = 168,550 above-grade
    assert "$168,550" in html or "168,550" in html
    # supported-value + bracket stats present
    assert "supported value" in html.lower()
    assert "brackets subject" in html.lower()


def test_extraction_grid_indicated_brackets_subject():
    # Eustis adjusts to ~$405k (low), Brompton (renovated, −42%) to ~$425k —
    # both well below the $533,800 EMV, so the subject is bracketed below it.
    html = render_extraction_grid(COMPS, 1440, 182_600)
    assert "$405," in html and ("$424," in html or "$425," in html)


def test_extraction_grid_empty_is_safe():
    assert render_extraction_grid([], 1440, 182_600) == ""


def test_extraction_grid_field_triggers_sales_section():
    """REGRESSION GUARD: the Sales Comparison section is gated on
    recent_sales/adjustment_schedule/adjustment_grid/extraction_grid. An
    extraction_grid alone must render the section (the bug dropped it silently)."""
    data = {
        "meta": {"assessment_year": 2026, "payable_year": 2027},
        "subject": {"address": "1 Test St", "living_area_sf": 1440, "emv_total": 533_800},
        "extraction_grid": {"comps": COMPS, "subject_absf": 1440, "subject_land": 182_600},
    }
    html = generate_appeal_report(data)
    assert "Sales Comparison Approach" in html
    assert "Adjustment Grid" in html


# --- Equalization grid component ---

EQ_PEERS = [
    dict(address="1546 Branston St", year_built=1941, lot_acres=0.22, emv_land=138_600, emv_building=206_000, sf=1536),
    dict(address="1573 Fulham St", year_built=1924, lot_acres=0.15, emv_land=150_400, emv_building=428_100, sf=1735),
    dict(address="2333 Chilcombe Ave", year_built=1909, lot_acres=0.15, emv_land=134_400, emv_building=385_700, sf=1220),
]
# Subject carries `living_area_sf` (the schema key), NOT `sf` — the component must
# read it so the subject's $/SF isn't $0 (regression guard for that bug).
EQ_SUBJECT = {"address": "1589 Fulham St, Lauderdale", "year_built": 1923,
              "lot_acres": 0.35, "emv_land": 182_600, "emv_building": 351_200, "living_area_sf": 1440}


def test_equalization_table_shows_peers_and_subject_with_psf():
    html = render_equalization_table(EQ_PEERS, EQ_SUBJECT)
    assert "<table" in html
    assert "1573 Fulham St" in html and "1546 Branston St" in html   # peers in the grid
    assert "(subject)" in html                                        # subject row labelled
    assert "$244" in html                                             # subject bldg $/SF 351,200/1440
    assert "Peer median assessed building" in html


def test_equalization_grid_field_triggers_section():
    data = {
        "meta": {"assessment_year": 2026, "payable_year": 2027},
        "subject": EQ_SUBJECT,
        "equalization_grid": EQ_PEERS,
    }
    html = generate_appeal_report(data)
    assert "Equalization Support" in html
    assert "Equalization Table" in html


def test_equalization_table_empty_is_safe():
    assert render_equalization_table([], EQ_SUBJECT) == ""
