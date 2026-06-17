"""Tests for the county-routed structure resolver and Hennepin packet parity.

Ramsey gets structure from Beacon (parse_beacon → beacon.json); Hennepin gets it
straight from the API data already in collected_data.json. Both reach build_packet
through the same {subject, comps} shape — so a Hennepin packet needs NO hand-typed
ABSF/basement/garage, the same guarantee Ramsey has.
"""
from analysis.structure import structure_from_collected, resolve_structure
from scripts.build_packet import build_packet


HENNEPIN_COLLECTED = {
    "county": "hennepin",
    "subject": {
        "pid": "1234567890123", "address": "100 Mpls Ave", "year_built": 1950,
        "living_area_sf": 1800, "emv_total": 400000, "emv_land": 80000,
        "emv_building": 320000, "parcel_acres": 0.2,
        "structure": {"sf": 1800, "basement_area_sf": 900, "garage_stalls": 2,
                      "stories": 2, "style": "TWO STORY"},
    },
    "recent_sales": [
        {"pid": "1111111111111", "sf": 1750, "sale_price": 390000, "emv_land": 75000, "year_built": 1948},
        {"pid": "2222222222222", "sf": 1850, "sale_price": 420000, "emv_land": 85000, "year_built": 1952},
    ],
    "neighborhood_comps": [],
}


def test_hennepin_structure_from_collected():
    s = structure_from_collected(HENNEPIN_COLLECTED)
    # Subject above-grade SF comes straight from the API (ABOVEGROUNDAREA).
    assert s["subject"]["absf"] == 1800
    # Per-comp basement/garage aren't in the API → symmetric 0 (documented).
    assert s["subject"]["contributory_basement_sf"] == 0
    assert s["subject"]["garage_sf"] == 0
    assert s["comps"]["1111111111111"]["absf"] == 1750
    assert s["comps"]["2222222222222"]["absf"] == 1850


def test_ramsey_defers_to_beacon():
    s = structure_from_collected({"county": "ramsey", "subject": {"living_area_sf": 2091}})
    assert s["subject"] is None and s["comps"] == {}


def test_resolve_structure_beacon_wins_per_parcel():
    beacon = {"subject": {"absf": 2091, "contributory_basement_sf": 600, "garage_sf": 572},
              "comps": {"1111111111111": {"absf": 999}}}
    merged = resolve_structure(beacon, HENNEPIN_COLLECTED)
    assert merged["subject"]["absf"] == 2091                 # beacon wins for the subject
    assert merged["comps"]["1111111111111"]["absf"] == 999   # beacon wins for this comp
    assert merged["comps"]["2222222222222"]["absf"] == 1850  # collected fills the rest


def test_hennepin_packet_needs_no_hand_typed_structure():
    """A thin Hennepin judgment (comps carry only PID + sale facts + role) builds a
    packet, with ABSF joined from collected_data — the parity guarantee."""
    judgment = {
        "meta": {"assessment_year": 2026, "tax_rate": 0.013,
                 "report_title": "Test — Minneapolis"},
        "subject": {"address": "100 Mpls Ave", "pid": "1234567890123", "land": 80000,
                    "emv_total": 400000, "emv_building": 320000, "lot_acres": 0.2},
        "comps": [
            {"address": "A St", "pid": "1111111111111", "sale_price": 390000, "land": 75000, "role": "central"},
            {"address": "B St", "pid": "2222222222222", "sale_price": 420000, "land": 85000, "role": "central"},
        ],
        "narrative": {"conclusion": "Indicated about ${concluded:,}."},
    }
    data = build_packet(judgment, collected=HENNEPIN_COLLECTED)
    # Structure was joined from collected, not typed into judgment:
    assert data["extraction_grid"]["subject_absf"] == 1800
    assert all(c["absf"] for c in data["extraction_grid"]["comps"])
    assert data["_numbers"]["concluded"] > 0
