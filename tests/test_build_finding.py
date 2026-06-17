"""Tests for scripts/build_finding.py — the deterministic no-appeal assembler.

Locks in the property the builder exists to guarantee: the no-appeal SCENARIO and
the concluded value are derived from the numbers, and an appealable property (one
that clears the ~$1,000/yr savings floor) is REFUSED rather than mislabeled.
"""
import json
from pathlib import Path

import pytest

from scripts.build_finding import build_finding, MIN_ANNUAL_CLIENT_SAVINGS
from report.no_appeal_generator import generate_no_appeal_report

DESNOYER = Path(__file__).parent.parent / "properties" / "desnoyer" / "judgment.json"


def _subject(emv=500000):
    # absf 2000, land 100000, no basement/garage → indicated = comp_sale + 20000
    # (see test math): (sale-comp_land)/absf*absf + subj_land, comp_land 80000.
    return {"address": "1 Test St", "pid": "111", "absf": 2000, "land": 100000,
            "emv_total": emv, "emv_land": 100000, "emv_building": emv - 100000,
            "living_area_sf": 2000}


def _comp(sale):
    return {"address": "2 Test St", "pid": "222", "sale_price": sale, "land": 80000,
            "absf": 2000, "fin_bsmt_sf": 0, "garage_sf": 0,
            "time_pct": 0, "quality_pct": 0, "condition_pct": 0, "role": "central"}


def _judgment(emv, sale):
    return {"meta": {"tax_rate": 0.0135}, "subject": _subject(emv), "comps": [_comp(sale)],
            "finding": {"final_bullets": ["b"]}}


def test_desnoyer_fixture_is_fairly_assessed():
    data = build_finding(json.loads(DESNOYER.read_text()))
    n = data["_numbers"]
    assert n["scenario"] == "fairly_assessed"
    assert n["reduction"] == 0
    assert data["subject"]["emv_total"] == 836500   # concluded AT the EMV
    html = generate_no_appeal_report(data)
    assert "zestimate" not in html.lower()
    assert "<h2>Final Recommendation</h2>" in html


def test_no_central_comps_defaults_fairly_assessed():
    data = build_finding({"subject": _subject(500000), "finding": {}})
    assert data["_numbers"]["scenario"] == "fairly_assessed"
    assert data["_numbers"]["reduction"] == 0


def test_comp_above_emv_is_fairly_assessed():
    # comp sale 520000 → indicated 540000 (above EMV) → fairly assessed, $0 reduction.
    data = build_finding(_judgment(500000, 520000))
    assert data["_numbers"]["scenario"] == "fairly_assessed"
    assert data["_numbers"]["reduction"] == 0


def test_small_angle_below_floor_is_below_savings_floor():
    # comp sale 465000 → indicated 485000 → $15,000 (3%) below EMV; $15k×1.35% ≈ $202/yr < $1,000.
    data = build_finding(_judgment(500000, 465000))
    n = data["_numbers"]
    assert n["scenario"] == "below_savings_floor"
    assert n["indicated"] == 485000 and n["reduction"] == 15000
    assert n["annual_savings"] < MIN_ANNUAL_CLIENT_SAVINGS


def test_refuses_when_savings_clear_the_floor():
    # comp sale 380000 → indicated 400000 → $100,000 below EMV; $100k×1.35% = $1,350 ≥ $1,000.
    # This is an APPEAL — build_finding must refuse and point at build_packet.
    with pytest.raises(ValueError, match="build_packet"):
        build_finding(_judgment(500000, 380000))


def test_missing_emv_raises():
    j = {"subject": {"address": "x", "absf": 2000}, "finding": {}}
    with pytest.raises(ValueError, match="emv_total"):
        build_finding(j)
