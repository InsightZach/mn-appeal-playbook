"""
Tests for the Beacon CAMA parser — pins extraction of the ABSF / finished-basement
split (the data the Ramsey API lacks) from real Beacon get_page_text output, and
the cross-check that API LivingAreaSquareFeet == ABSF + finished basement.
"""
from analysis.beacon import parse_beacon_card, reconcile_absf

# Real Beacon get_page_text excerpts (Ramsey, 2026).
EUSTIS_1704 = """Residential Structure Description
Card
1

Yr. Built
1914

Story Height
1

Style
BUNGALOW

Exterior Wall
STUCCO

Total Rooms
5

Family Rooms
0

Total Bedrooms
3

Full Baths
2

Half Baths
0

Attic type
PT-FIN 20%

ABSF
1,020

Foundation Size
862

Basement Area Finished
175

Finished Bsmt Rec Area
100

Garage Type/Area (Sq Ft)
Detached/240
Additions
Other Building & Yard Improvements
"""

FULHAM_1589 = """Residential Structure Description
Card
1

Yr. Built
1923

Story Height
2

Style
TWO STORY

Exterior Wall
STUCCO

Total Rooms
7

Total Bedrooms
3

Full Baths
2

Half Baths
0

Attic type
NONE

ABSF
1,440

Foundation Size
720

Basement Area Finished
0

Finished Bsmt Rec Area
0

Garage Type/Area (Sq Ft)
NONE
Other Building & Yard Improvements
"""


def test_parses_eustis_with_finished_basement_and_garage():
    b = parse_beacon_card(EUSTIS_1704)
    assert b["absf"] == 1020
    assert b["basement_finished_sf"] == 175
    assert b["finished_basement_sf"] == 175
    assert b["total_finished_sf"] == 1195      # 1020 + 175
    assert b["garage_sf"] == 240
    assert b["full_baths"] == 2
    assert b["style"] == "BUNGALOW"
    assert b["exterior_wall"] == "STUCCO"


def test_parses_subject_no_basement_no_garage():
    b = parse_beacon_card(FULHAM_1589)
    assert b["absf"] == 1440
    assert b["finished_basement_sf"] == 0
    assert b["total_finished_sf"] == 1440
    assert b["garage_sf"] == 0
    assert b["stories"] == "2"


def test_reconciles_against_api_total_finished_sf():
    # API LivingAreaSquareFeet for these parcels: Eustis 1195, subject 1440.
    r1 = reconcile_absf(parse_beacon_card(EUSTIS_1704), 1195)
    assert r1["reconciles"] is True
    assert r1["absf"] == 1020 and r1["finished_basement_sf"] == 175
    r2 = reconcile_absf(parse_beacon_card(FULHAM_1589), 1440)
    assert r2["reconciles"] is True


def test_flags_mismatch():
    r = reconcile_absf(parse_beacon_card(EUSTIS_1704), 1400)  # wrong API number
    assert r["reconciles"] is False
    assert "MISMATCH" in r["note"]
