"""
Parse a Ramsey Beacon CAMA "Property Value" page into structured structure data.

Beacon is the ONLY authoritative source for the Ramsey residential structure
breakdown the OpenData API does not carry: above-grade SF (ABSF) vs finished
basement, garage, baths, attic, exterior wall. The API's LivingAreaSquareFeet is
TOTAL FINISHED (ABSF + finished basement); to compare homes correctly you need
the split, and that is Beacon-only.

Collection is browser-driven (Beacon blocks headless HTTP with a captcha): an
agent navigates to
    https://beacon.schneidercorp.com/Application.aspx?AppID=959&LayerID=18852&PageTypeID=4&PageID=8471&KeyValue={PID}
and calls claude-in-chrome get_page_text. This module parses that text — the page
is server-rendered as "Label\\nValue" pairs, so each field is the line after its
label. See collectors/beacon_scraper.md.
"""
from __future__ import annotations

import re

# Beacon label -> (output key, kind). kind: "int", "num" (comma-number), "str".
_FIELDS = [
    ("Yr. Built", "year_built", "int"),
    ("Story Height", "stories", "str"),
    ("Style", "style", "str"),
    ("Exterior Wall", "exterior_wall", "str"),
    ("Total Rooms", "total_rooms", "int"),
    ("Family Rooms", "family_rooms", "int"),
    ("Total Bedrooms", "bedrooms", "int"),
    ("Full Baths", "full_baths", "int"),
    ("Half Baths", "half_baths", "int"),
    ("Attic type", "attic", "str"),
    ("ABSF", "absf", "num"),
    ("Foundation Size", "foundation_size", "num"),
    ("Basement Area Finished", "basement_finished_sf", "num"),
    ("Finished Bsmt Rec Area", "basement_rec_sf", "num"),
    ("Garage Type/Area (Sq Ft)", "garage", "str"),
]


def _num(s: str):
    s = s.replace(",", "").strip()
    try:
        return int(float(s))
    except ValueError:
        return None


def parse_beacon_card(text: str) -> dict:
    """Parse Beacon get_page_text into a structure dict. Each labeled value is the
    next non-empty line after its label (within the Residential Structure section).

    Returns keys: year_built, stories, style, exterior_wall, total_rooms,
    family_rooms, bedrooms, full_baths, half_baths, attic, absf, foundation_size,
    basement_finished_sf, basement_rec_sf, garage, garage_sf, plus the DERIVED
    finished_basement_sf and total_finished_sf (= absf + finished_basement_sf,
    which should equal the API LivingAreaSquareFeet — a built-in cross-check).
    Missing labels come back as None.
    """
    # Scope to the structure section so a stray "ABSF" elsewhere can't mislead.
    start = text.find("Residential Structure Description")
    body = text[start:] if start != -1 else text
    end = body.find("Other Building & Yard Improvements")
    if end != -1:
        body = body[:end + 200]  # keep a little past for the garage line
    lines = [ln.strip() for ln in body.splitlines()]
    nonempty_idx = [i for i, ln in enumerate(lines) if ln]

    out: dict = {}
    for label, key, kind in _FIELDS:
        val = None
        for i, ln in enumerate(lines):
            if ln == label or ln.rstrip(":") == label:
                # next non-empty line
                for j in range(i + 1, len(lines)):
                    if lines[j]:
                        val = lines[j]
                        break
                break
        if val is None:
            out[key] = None
        elif kind == "int":
            out[key] = _num(val)
        elif kind == "num":
            out[key] = _num(val)
        else:
            out[key] = val
    # Garage SF: "Detached/240" -> 240; "NONE" -> 0
    g = out.get("garage")
    if g and g.upper() != "NONE":
        m = re.search(r"/\s*([\d,]+)", g)
        out["garage_sf"] = _num(m.group(1)) if m else None
    else:
        out["garage_sf"] = 0

    # Derived: finished basement (the SF that makes API LivingAreaSquareFeet =
    # ABSF + finished basement). The Basement Area Finished is that figure (the
    # rec area is a subset / separately valued); fall back to rec area if needed.
    fin = out.get("basement_finished_sf")
    out["finished_basement_sf"] = fin if fin is not None else out.get("basement_rec_sf")
    absf = out.get("absf")
    fb = out.get("finished_basement_sf") or 0
    out["total_finished_sf"] = (absf + fb) if absf is not None else None
    return out


def reconcile_absf(beacon: dict, api_living_area_sf: float | None) -> dict:
    """Cross-check a parsed Beacon card against the API LivingAreaSquareFeet.

    The identity API LivingAreaSquareFeet == ABSF + finished basement should hold;
    when it does we trust the split, when it doesn't we flag it so the agent looks.
    Returns {absf, finished_basement_sf, total_finished_sf, api_living_area_sf,
    reconciles (bool|None), note}.
    """
    absf = beacon.get("absf")
    fb = beacon.get("finished_basement_sf")
    total = beacon.get("total_finished_sf")
    reconciles = None
    note = "no API SF to check against"
    if api_living_area_sf is not None and total is not None:
        reconciles = abs(total - api_living_area_sf) <= 25  # rounding tolerance
        note = (
            "Beacon ABSF + finished basement matches the API total finished SF"
            if reconciles else
            f"MISMATCH: Beacon ABSF {absf} + fin bsmt {fb} = {total} vs API "
            f"{api_living_area_sf} — verify the card (addition/rec-area counting)"
        )
    return {
        "absf": absf,
        "finished_basement_sf": fb,
        "total_finished_sf": total,
        "api_living_area_sf": api_living_area_sf,
        "reconciles": reconciles,
        "note": note,
    }
