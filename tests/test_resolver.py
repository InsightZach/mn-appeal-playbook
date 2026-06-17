"""
Unit tests for the Ramsey address parser — the pure, no-network part of
`resolve_address`. Pins the directional-preservation fix: a directional
(N/S/E/W) must be pulled out separately, NOT stripped as a street-type suffix,
because Lexington Pkwy N and Lexington Pkwy S are genuinely separate streets and
collapsing them silently resolved 660 Lexington Pkwy S to the wrong parcel.
"""
from collectors.ramsey_residential import _split_address


def test_directional_is_preserved_separately_not_stripped():
    number, street, directional = _split_address("660 Lexington Pkwy S")
    assert number == "660"
    assert street == "LEXINGTON"      # street-type suffix (PKWY) stripped
    assert directional == "S"         # directional preserved, not dropped


def test_no_directional_returns_none():
    number, street, directional = _split_address("1024 Lincoln Ave")
    assert number == "1024"
    assert street == "LINCOLN"
    assert directional is None


def test_multiword_street_name_kept():
    number, street, directional = _split_address("565 Mount Curve Blvd")
    assert number == "565"
    assert street == "MOUNT CURVE"
    assert directional is None


def test_compound_directional():
    _, street, directional = _split_address("100 Main St NE")
    assert street == "MAIN"
    assert directional == "NE"


def test_empty_address():
    assert _split_address("") == (None, None, None)
