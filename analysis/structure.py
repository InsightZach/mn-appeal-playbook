"""County-routed structure resolver.

The extraction grid needs each property's **above-grade** structure (ABSF +,
where available, finished-basement and garage SF). Different counties expose that
differently, so this module routes by county and emits ONE common shape — the same
`{subject, comps: {pid: {absf, contributory_basement_sf, garage_sf, year_built}}}`
that `scripts/parse_beacon` produces and that `build_packet` / `build_finding` join
by PID. Downstream code never has to know which county it is.

- **Ramsey** — the API's `living_area_sf` bundles the basement (no above-grade
  split), so structure comes from a Beacon card pull → `parse_beacon` → `beacon.json`.
  This module DEFERS for Ramsey (returns nothing) — use the Beacon path.
- **Hennepin / Minneapolis** — the API already returns `ABOVEGROUNDAREA` (above-grade
  SF) on the subject and above-grade `sf` on every comp, so we map it here directly —
  no browser pull. Per-comp finished-basement and garage are NOT in the API, so the
  Hennepin grid runs a **symmetric flat above-grade comparison** (both sides carry 0
  basement/garage — i.e. we assume subject and comps carry comparable basement/garage
  rather than inventing one-sided adjustments). That's a precision limitation, and it
  is conservative for the taxpayer.

Plugging in a new source (Minneapolis parcel open data for per-comp basement, MN
Geospatial Commons, listing SF, a third-party platform) is a new branch here — the
output shape is the contract; nothing downstream changes.
"""
from __future__ import annotations

import re


def _norm_pid(pid) -> str:
    return re.sub(r"\D", "", str(pid or ""))


def _hennepin_subject(subject: dict) -> dict | None:
    """Map a Hennepin/Mpls subject's collected structure into the common shape.
    Above-grade SF is authoritative; basement/garage are left at 0 (see module note —
    symmetric with the comps, which carry no per-parcel basement/garage)."""
    st = subject.get("structure") or {}
    absf = st.get("sf") or subject.get("living_area_sf")
    if not absf:
        return None  # suburban Hennepin (e.g. Minnetonka) has no bulk SF — grid can't run
    return {
        "absf": absf,
        "contributory_basement_sf": 0,
        "garage_sf": 0,
        "year_built": subject.get("year_built"),
    }


def _hennepin_comp(comp: dict) -> dict | None:
    absf = comp.get("sf")
    if not absf:
        return None
    return {
        "absf": absf,
        "contributory_basement_sf": 0,
        "garage_sf": 0,
        "year_built": comp.get("year_built"),
    }


def structure_from_collected(collected: dict | None) -> dict:
    """Derive the common structure map from a `collected_data.json`, routed by county.
    Returns `{subject: dict|None, comps: {pid: dict}}`. For counties whose API lacks an
    above-grade split (Ramsey), returns empties so the caller falls back to Beacon."""
    collected = collected or {}
    county = (collected.get("county") or "").lower()
    if county != "hennepin":
        # Ramsey (and anything else without an above-grade API field) → use Beacon.
        return {"subject": None, "comps": {}}

    comps: dict[str, dict] = {}
    for c in (collected.get("recent_sales") or []) + (collected.get("neighborhood_comps") or []):
        pid = _norm_pid(c.get("pid"))
        if pid and pid not in comps:
            mapped = _hennepin_comp(c)
            if mapped:
                comps[pid] = mapped
    return {"subject": _hennepin_subject(collected.get("subject") or {}), "comps": comps}


def resolve_structure(beacon: dict | None, collected: dict | None) -> dict:
    """Merge the structure sources into one `{subject, comps}` map. An explicit
    `beacon.json` (a real Beacon pull) WINS per parcel; collected-derived structure
    (the Hennepin API) fills whatever Beacon didn't supply. Either may be empty."""
    beacon = beacon or {}
    derived = structure_from_collected(collected)
    comps = {**derived.get("comps", {}), **(beacon.get("comps") or {})}
    subject = beacon.get("subject") or derived.get("subject")
    return {"subject": subject, "comps": comps}
