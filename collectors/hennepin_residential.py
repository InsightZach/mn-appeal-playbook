"""Hennepin County residential property collector.

Hennepin spreads residential data across three public sources, so this
collector stitches them together:

1. **Hennepin GIS** (LAND_PROPERTY MapServer layer 1) — parcel master:
   address, owner, lat/lon, lot area, plat, year built, sale date/price,
   and the PRIOR-year assessment (LAND_MV1/BLDG_MV1/TOTAL_MV1).
   No living-area SF anywhere in this layer.

2. **Hennepin PINS** (www16.co.hennepin.mn.us/pins) — the only public
   source for the CURRENT (26p27) assessment. Plain-HTTP per-PID pages;
   `assmt=1` returns next-assessment values, base URL the prior one,
   `year=YYYY` the payable-year history.

3. **Minneapolis Assessing open data** (Assessing_Department_Parcel_Data_2025
   FeatureServer) — building characteristics for Minneapolis parcels only:
   ABOVEGROUNDAREA (above-grade SF), BASEMENTAREA, stories, exterior,
   baths. Suburban Hennepin parcels (Minnetonka etc.) have NO bulk SF
   source; their `living_area_sf` comes back None and downstream analysis
   degrades gracefully (caller may fill from Zillow for the subject).

Public API mirrors collectors.ramsey_residential:

    resolve_address(address)        -> subject dict or None
    get_assessment_history(pid)     -> list of yearly assessment dicts
    find_comps(pid, sf, year_built, lat, lon, ...) -> list of comparables
    get_recent_sales(lat, lon, ...) -> list of recent residential sales

NOTE on SF basis: Hennepin `sf` values are ABOVE-GRADE square feet
(Minneapolis ABOVEGROUNDAREA). Ramsey's LivingAreaSquareFeet includes
finished basement. Within-county comparisons stay apples-to-apples; never
mix counties in one comp set.
"""

from __future__ import annotations

import math
import re
import time
from typing import Any, Iterable

import requests

GIS_BASE = (
    "https://gis.hennepin.us/arcgis/rest/services/HennepinData/"
    "LAND_PROPERTY/MapServer/1/query"
)
MPLS_BASE = (
    "https://services.arcgis.com/afSMGVsC7QlRK1kZ/arcgis/rest/services/"
    "Assessing_Department_Parcel_Data_2025/FeatureServer/0/query"
)
PINS_BASE = "https://www16.co.hennepin.mn.us/pins/pidresult.jsp"
PAGE_SIZE = 1000
REQUEST_TIMEOUT = 60
EARTH_RADIUS_MI = 3958.7613
PINS_DELAY = 0.3  # seconds between PINS fetches
SQFT_PER_ACRE = 43560.0

GIS_FIELDS = [
    "PID", "HOUSE_NO", "FRAC_HOUSE_NO", "STREET_NM", "MUNIC_NM", "ZIP_CD",
    "OWNER_NM", "BUILD_YR", "SALE_DATE", "SALE_PRICE", "SALE_CODE_NAME",
    "PARCEL_AREA", "MKT_VAL_TOT", "ABBREV_ADDN_NM",
    "PR_TYP_NM1", "HMSTD_CD1", "LAND_MV1", "BLDG_MV1", "TOTAL_MV1",
    "TAX_TOT", "LAT", "LON",
]

MPLS_FIELDS = [
    "TAX_MAP_UFMT", "ABOVEGROUNDAREA", "BASEMENTAREA", "STORIES",
    "EXTERIORWALL", "TOTALBATHROOMS", "TOTALBEDROOMS", "YEARBUILT",
    "NEIGHBORHOOD", "PROPERTYTYPE", "CONSTRUCTIONTYPE", "GARAGESTALLS",
]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _query_features(
    base: str,
    where: str,
    fields: Iterable[str] | None = None,
    geometry: tuple[float, float, float, float] | None = None,
) -> list[dict[str, Any]]:
    """Query an ArcGIS REST endpoint, paginating to exhaustion."""
    params: dict[str, Any] = {
        "where": where,
        "outFields": ",".join(fields) if fields else "*",
        "f": "json",
        "returnGeometry": "false",
        "resultRecordCount": PAGE_SIZE,
    }
    if geometry is not None:
        xmin, ymin, xmax, ymax = geometry
        params["geometry"] = f"{xmin},{ymin},{xmax},{ymax}"
        params["geometryType"] = "esriGeometryEnvelope"
        params["inSR"] = 4326
        params["spatialRel"] = "esriSpatialRelIntersects"

    results: list[dict[str, Any]] = []
    offset = 0
    while True:
        page_params = dict(params, resultOffset=offset)
        try:
            # POST: the IN-clause queries (Minneapolis structure enrichment)
            # exceed GET URL length limits.
            resp = requests.post(base, data=page_params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise RuntimeError(f"Hennepin API request failed: {e}") from e
        except ValueError as e:
            raise RuntimeError(f"Hennepin API returned invalid JSON: {e}") from e
        if "error" in data:
            err = data["error"]
            msg = err.get("message", err) if isinstance(err, dict) else err
            raise RuntimeError(f"Hennepin API error: {msg}")
        features = data.get("features", [])
        if not features:
            break
        results.extend(f.get("attributes", {}) for f in features)
        if len(features) < PAGE_SIZE and not data.get("exceededTransferLimit"):
            break
        offset += len(features)
    return results


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return EARTH_RADIUS_MI * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _bbox_for_radius(lat: float, lon: float, radius_miles: float) -> tuple[float, float, float, float]:
    dlat = radius_miles / 69.0
    dlon = radius_miles / (69.0 * max(math.cos(math.radians(lat)), 1e-6))
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def _normalize_pid(pid: str) -> str:
    return re.sub(r"\D", "", pid or "")


def _clean(value: Any) -> Any:
    """Hennepin GIS pads strings with trailing spaces."""
    return value.strip() if isinstance(value, str) else value


# ---------------------------------------------------------------------------
# Minneapolis structure enrichment
# ---------------------------------------------------------------------------


def _mpls_structures(pids: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch Minneapolis assessing structure data for a list of 13-digit PIDs.

    Returns a mapping of pid -> structure dict. Non-Minneapolis PIDs simply
    won't appear in the result.
    """
    out: dict[str, dict[str, Any]] = {}
    for i in range(0, len(pids), 100):
        chunk = pids[i:i + 100]
        keys = ",".join(f"'p{p}'" for p in chunk)
        rows = _query_features(MPLS_BASE, f"TAX_MAP_UFMT IN ({keys})", MPLS_FIELDS)
        for r in rows:
            pid = _normalize_pid(r.get("TAX_MAP_UFMT", ""))
            sf = r.get("ABOVEGROUNDAREA") or None
            stories = r.get("STORIES")
            style = None
            if stories:
                style = {1: "ONE STORY", 1.5: "ONE AND 1/2", 1.75: "ONE AND 3/4",
                         2: "TWO STORY", 2.5: "TWO AND 1/2", 3: "THREE STORY"}.get(stories)
            out[pid] = {
                "sf": sf,
                "basement_area_sf": r.get("BASEMENTAREA"),
                "stories": stories,
                "style": style,
                "exterior": _clean(r.get("EXTERIORWALL")),
                "baths": r.get("TOTALBATHROOMS"),
                "bedrooms": r.get("TOTALBEDROOMS"),
                "garage_stalls": r.get("GARAGESTALLS"),
                "neighborhood": _clean(r.get("NEIGHBORHOOD")),
                "property_type_detail": _clean(r.get("PROPERTYTYPE")),
            }
    return out


# ---------------------------------------------------------------------------
# PINS (current-assessment values)
# ---------------------------------------------------------------------------

_PINS_HEADER_RE = re.compile(r"(\d{4})\s+Assessment\s*\(For Taxes Payable\s+(\d{4})\)")
_PINS_MONEY = r"\$([\d,]+)"


def _pins_fetch(pid: str, params: dict[str, str]) -> dict[str, Any] | None:
    """Fetch one PINS page and parse assessment year + summed values."""
    try:
        resp = requests.get(PINS_BASE, params={"pid": pid, **params}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException:
        return None
    text = re.sub(r"<[^>]+>", "|", resp.content.decode("latin-1"))
    text = re.sub(r"&nbsp;?", " ", text)
    text = re.sub(r"[\s|]*\|[\s|]*", "|", text)

    def _sum(label: str) -> float | None:
        vals = re.findall(rf"{label}:\|{_PINS_MONEY}", text)
        return sum(float(v.replace(",", "")) for v in vals) if vals else None

    # Format A — "Property information" page (assmt=1): full land/building
    # split under a "YYYY Assessment (For Taxes Payable YYYY)" header.
    m = _PINS_HEADER_RE.search(text)
    if m:
        total = _sum("Totals")
        if total is None:
            return None
        return {
            "tax_year": int(m.group(2)),
            "assess_year": int(m.group(1)),
            "emv_land": _sum("Land"),
            "emv_building": _sum("Building"),
            "emv_total": total,
            "total_tax": None,
            "special_assessment": None,
            "tax_capacity": None,
        }

    # Format B — "Value and tax summary" page (base URL / year=YYYY):
    # EMV total + net tax only, no land/building split.
    m = re.search(r"taxes\s+payable\s+(\d{4})", text)
    y = re.search(r"January 2,\s*(\d{4})", text)
    emv = re.search(rf"Estimated market value:\|{_PINS_MONEY}", text)
    tax = re.search(r"Total net tax:\|\$([\d,]+\.?\d*)", text)
    if not (m and y and emv):
        return None
    return {
        "tax_year": int(m.group(1)),
        "assess_year": int(y.group(1)),
        "emv_land": None,
        "emv_building": None,
        "emv_total": float(emv.group(1).replace(",", "")),
        "total_tax": float(tax.group(1).replace(",", "")) if tax else None,
        "special_assessment": None,
        "tax_capacity": None,
    }


def get_assessment_history(pid: str) -> list[dict[str, Any]]:
    """Three years of assessments via PINS: next (assmt=1), current (base),
    and prior (year=YYYY). Years are taken from the page header, not assumed
    from the URL params, because PINS cycles its param mapping annually."""
    pid = _normalize_pid(pid)
    results: dict[int, dict[str, Any]] = {}
    for params in ({"assmt": "1"}, {}, {"year": "2025"}):
        row = _pins_fetch(pid, params)
        if row:
            results[row["assess_year"]] = row
        time.sleep(PINS_DELAY)

    # The tax-summary pages have no land/building split; the GIS layer
    # carries the prior-year (LAND_MV1/BLDG_MV1) split — patch it in.
    gis = _query_features(GIS_BASE, f"PID = '{pid}'", GIS_FIELDS)
    if gis:
        a = gis[0]
        for row in results.values():
            if row["emv_land"] is None and row["emv_total"] == a.get("TOTAL_MV1"):
                row["emv_land"] = a.get("LAND_MV1")
                row["emv_building"] = a.get("BLDG_MV1")

    return sorted(results.values(), key=lambda r: r["assess_year"], reverse=True)


def get_current_emv(pid: str) -> dict[str, Any] | None:
    """Just the current (next-assessment) values — used for comp enrichment."""
    return _pins_fetch(_normalize_pid(pid), {"assmt": "1"})


# ---------------------------------------------------------------------------
# Record shaping
# ---------------------------------------------------------------------------


def _sale_date_iso(value: Any) -> str | None:
    """GIS SALE_DATE is a 'YYYYMM' string."""
    s = _clean(value)
    if s and re.fullmatch(r"\d{6}", str(s)):
        return f"{s[:4]}-{s[4:6]}-01"
    return None


def _address_from_attrs(a: dict[str, Any]) -> str:
    no = a.get("HOUSE_NO") or ""
    frac = _clean(a.get("FRAC_HOUSE_NO")) or ""
    street = _clean(a.get("STREET_NM")) or ""
    return " ".join(str(p) for p in (no, frac, street) if p)


def _subject_from_attrs(a: dict[str, Any], structure: dict[str, Any] | None) -> dict[str, Any]:
    area = a.get("PARCEL_AREA") or 0
    subject = {
        "pid": _normalize_pid(a.get("PID", "")),
        "address": _address_from_attrs(a),
        "city": _clean(a.get("MUNIC_NM")),
        "owner_name": _clean(a.get("OWNER_NM")),
        "lat": a.get("LAT"),
        "lon": a.get("LON"),
        "year_built": int(a["BUILD_YR"]) if _clean(a.get("BUILD_YR")) else None,
        "living_area_sf": None,
        "sf_basis": "above_grade",
        "land_use": _clean(a.get("PR_TYP_NM1")),
        "parcel_acres": round(area / SQFT_PER_ACRE, 3) if area else None,
        "plat_name": _clean(a.get("ABBREV_ADDN_NM")),
        "homestead": _clean(a.get("HMSTD_CD1")),
        "last_sale_date": _sale_date_iso(a.get("SALE_DATE")),
        "last_sale_price": a.get("SALE_PRICE") or None,
    }
    if structure:
        subject["living_area_sf"] = structure.get("sf")
        subject["structure"] = structure
    return subject


def _comp_from_attrs(a: dict[str, Any], structure: dict[str, Any] | None) -> dict[str, Any]:
    area = a.get("PARCEL_AREA") or 0
    s = structure or {}
    return {
        "pid": _normalize_pid(a.get("PID", "")),
        "address": _address_from_attrs(a),
        "city": _clean(a.get("MUNIC_NM")),
        "sf": s.get("sf"),
        "year_built": int(a["BUILD_YR"]) if _clean(a.get("BUILD_YR")) else None,
        # Prior-year (25p26) values from GIS; overwritten with 26p27 when
        # PINS enrichment runs. emv_year says which one you're holding.
        "emv_total": a.get("TOTAL_MV1") or a.get("MKT_VAL_TOT"),
        "emv_land": a.get("LAND_MV1"),
        "emv_building": a.get("BLDG_MV1"),
        "emv_year": 2025,
        "sale_price": a.get("SALE_PRICE") or None,
        "sale_date": _sale_date_iso(a.get("SALE_DATE")),
        "sale_code": _clean(a.get("SALE_CODE_NAME")),
        "style": s.get("style"),
        "exterior": s.get("exterior"),
        "lot_acres": round(area / SQFT_PER_ACRE, 3) if area else None,
        "owner_name": _clean(a.get("OWNER_NM")),
        "plat_name": _clean(a.get("ABBREV_ADDN_NM")),
        "lat": a.get("LAT"),
        "lon": a.get("LON"),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_address(address: str) -> dict[str, Any] | None:
    """Resolve an address (or a bare 13-digit PID) to a subject dict."""
    digits = _normalize_pid(address)
    if len(digits) == 13 and not re.search(r"[A-Za-z]", address):
        rows = _query_features(GIS_BASE, f"PID = '{digits}'", GIS_FIELDS)
    else:
        tokens = address.strip().upper().split()
        number = tokens[0] if tokens and tokens[0].isdigit() else None
        if not number:
            return None
        # STREET_NM holds e.g. 'W MINNEHAHA PKWY' — match on the most
        # distinctive token to dodge prefix/suffix ordering differences.
        suffixes = {
            "AVE", "AVENUE", "ST", "STREET", "RD", "ROAD", "DR", "DRIVE",
            "BLVD", "BOULEVARD", "LN", "LANE", "CT", "COURT", "WAY", "PL",
            "PLACE", "TER", "TERRACE", "CIR", "CIRCLE", "PKWY", "PARKWAY",
            "TRL", "TRAIL", "HWY", "HIGHWAY", "N", "S", "E", "W", "NE",
            "NW", "SE", "SW",
        }
        name_tokens = [t.rstrip(",") for t in tokens[1:] if t.rstrip(",") not in suffixes]
        if not name_tokens:
            return None
        key = max(name_tokens, key=len)
        rows = _query_features(
            GIS_BASE,
            f"HOUSE_NO = {int(number)} AND STREET_NM LIKE '%{key}%'",
            GIS_FIELDS,
        )
        if len(rows) > 1:
            # Disambiguate e.g. 'W MINNEHAHA PKWY' vs 'MINNEHAHA PKWY':
            # most input street tokens present in STREET_NM wins, with a
            # penalty for extra tokens the input doesn't have.
            street_tokens = {t.rstrip(",") for t in tokens[1:]}

            def _score(a: dict[str, Any]) -> tuple[int, int]:
                nm_tokens = set((_clean(a.get("STREET_NM")) or "").split())
                return (len(street_tokens & nm_tokens), -len(nm_tokens - street_tokens))

            rows.sort(key=_score, reverse=True)
    if not rows:
        return None
    attrs = rows[0]
    pid = _normalize_pid(attrs.get("PID", ""))
    structure = _mpls_structures([pid]).get(pid)
    return _subject_from_attrs(attrs, structure)


def find_comps(
    pid: str,
    sf: float | None,
    year_built: int | None,
    lat: float,
    lon: float,
    radius_miles: float = 0.5,
    sf_tolerance: float = 0.30,
    year_tolerance: int = 20,
    max_comps: int = 40,
    pins_enrich: bool = True,
) -> list[dict[str, Any]]:
    """Residential comps near the subject, filtered in Python.

    When the subject has no SF (suburban Hennepin), the SF filter is skipped
    and comps are selected on year/distance alone — flag this in any report.
    PINS enrichment swaps the GIS prior-year EMV for the current assessment
    on each kept comp (one HTTP fetch per comp, throttled).
    """
    bbox = _bbox_for_radius(lat, lon, radius_miles)
    rows = _query_features(GIS_BASE, "PR_TYP_NM1 LIKE 'RESIDENTIAL%'", GIS_FIELDS, geometry=bbox)

    pid = _normalize_pid(pid)
    candidates = []
    for a in rows:
        cpid = _normalize_pid(a.get("PID", ""))
        if cpid == pid or a.get("LAT") is None:
            continue
        dist = _haversine_miles(lat, lon, a["LAT"], a["LON"])
        if dist > radius_miles:
            continue
        yb = _clean(a.get("BUILD_YR"))
        if year_built and yb and abs(int(yb) - year_built) > year_tolerance:
            continue
        candidates.append((dist, a))
    candidates.sort(key=lambda t: t[0])

    structures = _mpls_structures([_normalize_pid(a.get("PID", "")) for _, a in candidates])

    comps: list[dict[str, Any]] = []
    for dist, a in candidates:
        cpid = _normalize_pid(a.get("PID", ""))
        comp = _comp_from_attrs(a, structures.get(cpid))
        if sf and comp["sf"] and abs(comp["sf"] - sf) / sf > sf_tolerance:
            continue
        comp["distance_miles"] = round(dist, 3)
        comps.append(comp)
        if len(comps) >= max_comps:
            break

    if pins_enrich:
        for comp in comps:
            current = get_current_emv(comp["pid"])
            if current:
                comp["emv_total"] = current["emv_total"]
                comp["emv_land"] = current["emv_land"]
                comp["emv_building"] = current["emv_building"]
                comp["emv_year"] = current["assess_year"]
            time.sleep(PINS_DELAY)
    return comps


def get_recent_sales(
    lat: float,
    lon: float,
    radius_miles: float = 1.0,
    since_date: str = "2024-06-01",
    max_sales: int = 150,
) -> list[dict[str, Any]]:
    """Recent residential sales near the subject from the GIS sale fields."""
    since_yyyymm = since_date.replace("-", "")[:6]
    bbox = _bbox_for_radius(lat, lon, radius_miles)
    where = (
        "PR_TYP_NM1 LIKE 'RESIDENTIAL%' AND SALE_PRICE > 0 "
        f"AND SALE_DATE >= '{since_yyyymm}'"
    )
    rows = _query_features(GIS_BASE, where, GIS_FIELDS, geometry=bbox)

    keep = []
    for a in rows:
        if a.get("LAT") is None:
            continue
        dist = _haversine_miles(lat, lon, a["LAT"], a["LON"])
        if dist <= radius_miles:
            keep.append((dist, a))
    keep.sort(key=lambda t: t[0])
    keep = keep[:max_sales]

    structures = _mpls_structures([_normalize_pid(a.get("PID", "")) for _, a in keep])
    sales = []
    for dist, a in keep:
        cpid = _normalize_pid(a.get("PID", ""))
        sale = _comp_from_attrs(a, structures.get(cpid))
        sale["distance_miles"] = round(dist, 3)
        sales.append(sale)
    return sales
