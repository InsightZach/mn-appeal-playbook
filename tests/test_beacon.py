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


# Real subject card with a "Finished Bsmt Rec Area" but ZERO "Basement Area Finished"
# — the case that must NOT be hand-typed: contributory basement (valuation) = 600 even
# though the API-reconciliation finished_basement_sf = 0. (2162 Carroll Ave.)
CARROLL_2162 = """Residential Structure Description
Card
1

Yr. Built
1911

Story Height
2

Style
TWO STORY

Exterior Wall
STUCCO

Total Bedrooms
5

Full Baths
2

ABSF
2,091

Foundation Size
1,071

Basement Area Finished
0

Finished Bsmt Rec Area
600

Garage Type/Area (Sq Ft)
Detached/572
Other Building & Yard Improvements
"""


def test_parses_eustis_with_finished_basement_and_garage():
    b = parse_beacon_card(EUSTIS_1704)
    assert b["absf"] == 1020
    assert b["basement_finished_sf"] == 175
    assert b["finished_basement_sf"] == 175
    assert b["total_finished_sf"] == 1195      # 1020 + 175
    assert b["contributory_basement_sf"] == 275  # 175 finished + 100 rec
    assert b["garage_sf"] == 240
    assert b["full_baths"] == 2
    assert b["style"] == "BUNGALOW"
    assert b["exterior_wall"] == "STUCCO"


def test_rec_area_counts_for_valuation_but_not_reconciliation():
    """The Carroll-subject pattern: 0 'Basement Area Finished', 600 rec area. The API
    identity uses 0 (so it reconciles to ABSF), but the extraction grid must credit the
    full 600 SF of finished basement value."""
    b = parse_beacon_card(CARROLL_2162)
    assert b["absf"] == 2091
    assert b["finished_basement_sf"] == 0          # reconciliation basis
    assert b["contributory_basement_sf"] == 600    # valuation basis (rec area)
    assert b["garage_sf"] == 572
    assert reconcile_absf(b, 2091)["reconciles"] is True


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
