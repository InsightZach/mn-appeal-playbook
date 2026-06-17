"""Ramsey County residential property collector.

Queries the Ramsey County GIS OpenData FeatureServer (layer 12 = Parcels) for
single-family residential data used by the appeal pipeline. Public API:

    resolve_address(address)        -> subject dict or None
    get_assessment_history(pid)     -> list of yearly assessment dicts
    find_comps(pid, sf, year_built, lat, lon, ...) -> list of comparables
    get_recent_sales(lat, lon, ...) -> list of recent residential sales

The Ramsey FeatureServer rejects queries that combine too many AND clauses
(e.g. LivingAreaSquareFeet BETWEEN ... AND YearBuilt BETWEEN ...). The
implementation works around this by:

- Using BuildingNumber/StreetName matches for address resolution with a
  SiteAddress LIKE fallback.
- Using a spatial envelope (bbox) for comp/sales queries and applying
  SF/year/distance filters in Python.
- Paginating via resultOffset/resultRecordCount up to the server's max
  record count (1000).
"""

from __future__ import annotations

import math
import re
from datetime import date as _date, datetime, timezone
from typing import Any, Iterable

import requests

API_BASE = (
    "https://maps.co.ramsey.mn.us/arcgis/rest/services/OpenData/OpenData/"
    "FeatureServer/12/query"
)
PAGE_SIZE = 1000
REQUEST_TIMEOUT = 60
EARTH_RADIUS_MI = 3958.7613
SFR_LAND_USE_CODE = "510"

# Fields we ask for on the subject lookup and comp queries. Kept as module
# constants so the query string stays consistent across callers.
SUBJECT_FIELDS = [
    "ParcelID",
    "SiteAddress",
    "OwnerName1",
    "YearBuilt",
    "LivingAreaSquareFeet",
    "ParcelAcresDeed",
    "PlatName",
    "LandUseCode",
    "LandUseCodeDescription",
    "HomeStyleDescription",
    "EMVLand",
    "EMVBuilding",
    "EMVTotal",
    "SalePrice",
    "LastSaleDate",
    "TaxYear",
    "EMVYear",
    "Latitude",
    "Longitude",
]

HISTORY_FIELDS = [
    "ParcelID",
    "TaxYear", "EMVYear", "EMVLand", "EMVBuilding", "EMVTotal",
    "TotalTax", "SpecialAssessmentDue", "TaxCapacity",
    "TaxYear1", "EMVYear1", "EMVLand1", "EMVBuilding1", "EMVTotal1",
    "TotalTax1", "SpecialAssessmentDue1",
    "TaxYear2", "EMVYear2", "EMVLand2", "EMVBuilding2", "EMVTotal2",
    "TotalTax2", "SpecialAssessmentDue2",
]

COMP_FIELDS = [
    "ParcelID",
    "SiteAddress",
    "OwnerName1",
    "LivingAreaSquareFeet",
    "YearBuilt",
    "EMVLand",
    "EMVBuilding",
    "EMVTotal",
    "SalePrice",
    "LastSaleDate",
    "HomeStyleDescription",
    "ParcelAcresDeed",
    "PlatName",
    "LandUseCode",
    "Latitude",
    "Longitude",
]


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------


def _query_api(
    where: str,
    geometry: tuple[float, float, float, float] | None = None,
    fields: Iterable[str] | None = None,
    out_sr: int = 4326,
    order_by: str | None = None,
) -> list[dict[str, Any]]:
    """Query the Ramsey FeatureServer and return all feature attributes.

    Args:
        where: SQL WHERE clause (use ``1=1`` to match all rows).
        geometry: Optional (xmin, ymin, xmax, ymax) envelope in WGS84
            coordinates. When provided, the server filters features whose
            geometry intersects the envelope.
        fields: Field names to return. Defaults to all (``*``).
        out_sr: Output spatial reference WKID. Defaults to WGS84 (4326) so
            Latitude/Longitude come back as proper decimal degrees.
        order_by: Optional ORDER BY clause (e.g. ``"LastSaleDate DESC"``).

    Returns:
        List of attribute dictionaries, one per feature.
    """
    out_fields = ",".join(fields) if fields else "*"
    params: dict[str, Any] = {
        "where": where,
        "outFields": out_fields,
        "f": "json",
        "returnGeometry": "false",
        "outSR": out_sr,
        "resultRecordCount": PAGE_SIZE,
    }
    if geometry is not None:
        xmin, ymin, xmax, ymax = geometry
        params["geometry"] = f"{xmin},{ymin},{xmax},{ymax}"
        params["geometryType"] = "esriGeometryEnvelope"
        params["inSR"] = 4326
        params["spatialRel"] = "esriSpatialRelIntersects"
    if order_by:
        params["orderByFields"] = order_by

    results: list[dict[str, Any]] = []
    offset = 0
    while True:
        page_params = dict(params, resultOffset=offset)
        try:
            resp = requests.get(API_BASE, params=page_params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise RuntimeError(f"Ramsey API request failed: {e}") from e
        except ValueError as e:  # JSON decode
            raise RuntimeError(f"Ramsey API returned invalid JSON: {e}") from e
        if "error" in data:
            err = data["error"]
            err_msg = err.get("message", err) if isinstance(err, dict) else err
            raise RuntimeError(f"Ramsey API error: {err_msg}")
        features = data.get("features", [])
        if not features:
            break
        results.extend(f.get("attributes", {}) for f in features)
        if len(features) < PAGE_SIZE or not data.get("exceededTransferLimit"):
            break
        offset += PAGE_SIZE
    return results


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_MI * c


def _bbox_for_radius(lat: float, lon: float, radius_miles: float) -> tuple[float, float, float, float]:
    """Return a (xmin, ymin, xmax, ymax) WGS84 envelope covering the radius."""
    dlat = radius_miles / 69.0  # ~69 miles per degree of latitude
    # Degrees of longitude shrink by cos(lat)
    dlon = radius_miles / (69.0 * max(math.cos(math.radians(lat)), 1e-6))
    return (lon - dlon, lat - dlat, lon + dlon, lat + dlat)


def _parse_epoch_ms(value: Any) -> str | None:
    """Convert an Esri epoch-ms timestamp to an ISO date string (YYYY-MM-DD)."""
    if value is None:
        return None
    try:
        ts = float(value) / 1000.0
    except (TypeError, ValueError):
        return None
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OverflowError, OSError, ValueError):
        return None


def _normalize_pid(pid: str) -> str:
    """Strip non-digit characters from a Ramsey PID."""
    return re.sub(r"\D", "", pid or "")


class AmbiguousAddressError(RuntimeError):
    """Raised when an address resolves to more than one distinct parcel.

    Carries the candidate subject dicts so the caller can disambiguate (e.g. by
    directional or unit) rather than silently proceeding on an arbitrary row.
    Silently returning the first row is unsafe for any address carrying a
    directional, unit, or duplicated street name (e.g. Lexington Pkwy N vs S in
    St. Paul are genuinely separate streets).
    """

    def __init__(self, address: str, candidates: list[dict[str, Any]]):
        self.address = address
        self.candidates = candidates
        super().__init__(
            f"Address {address!r} matched {len(candidates)} distinct parcels — "
            f"disambiguate before proceeding: "
            + ", ".join(
                f"{c.get('pid')} ({c.get('address')})" for c in candidates
            )
        )


# Directional tokens are NOT street-type suffixes — in St. Paul a directional
# (N/S/E/W/NE/...) distinguishes genuinely separate streets (Lexington Pkwy N vs
# Lexington Pkwy S), so it must be PRESERVED, not stripped from the match.
_DIRECTIONALS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}


def _split_address(address: str) -> tuple[str | None, str | None, str | None]:
    """Split a free-form address into ``(building_number, street_name, directional)``.

    The street name is uppercased and stripped of the common street-TYPE suffix
    tokens (AVE, ST, RD, ...) because Ramsey's ``StreetName`` field stores the bare
    street name with suffix in a separate column. Directionals (N/S/E/W/...) are
    NOT stripped from the name — they are returned separately so the caller can
    require them in the match instead of collapsing two distinct streets.
    """
    if not address:
        return None, None, None
    tokens = address.strip().upper().split()
    if not tokens:
        return None, None, None
    number = tokens[0] if tokens[0].isdigit() else None
    rest = tokens[1:] if number else tokens
    suffixes = {
        "AVE", "AVENUE", "ST", "STREET", "RD", "ROAD", "DR", "DRIVE",
        "BLVD", "BOULEVARD", "LN", "LANE", "CT", "COURT", "WAY", "PL",
        "PLACE", "TER", "TERRACE", "CIR", "CIRCLE", "PKWY", "PARKWAY",
        "TRL", "TRAIL", "HWY", "HIGHWAY",
    }
    # Pull a trailing/leading directional out separately so it can be required in
    # the WHERE match rather than dropped (which would collapse N/S/E/W streets).
    directional = next((t for t in rest if t in _DIRECTIONALS), None)
    name_tokens = [
        t for t in rest if t not in suffixes and t not in _DIRECTIONALS
    ]
    name = " ".join(name_tokens) if name_tokens else None
    return number, name, directional


def _subject_from_attrs(attrs: dict[str, Any]) -> dict[str, Any]:
    return {
        "pid": _normalize_pid(attrs.get("ParcelID", "")),
        "address": attrs.get("SiteAddress"),
        "owner_name": attrs.get("OwnerName1"),
        "lat": attrs.get("Latitude"),
        "lon": attrs.get("Longitude"),
        "year_built": attrs.get("YearBuilt"),
        "living_area_sf": attrs.get("LivingAreaSquareFeet"),
        "land_use": attrs.get("LandUseCodeDescription") or attrs.get("LandUseCode"),
        "parcel_acres": attrs.get("ParcelAcresDeed"),
        "plat_name": attrs.get("PlatName"),
        # Land EMV is the tell for a condominium / common-interest unit (a nominal
        # land value, e.g. $1,000) — surfaced so the ownership-form guard in
        # scripts/collect.py and the equalization land-line math can use it.
        "emv_land": attrs.get("EMVLand"),
        "emv_building": attrs.get("EMVBuilding"),
        "emv_total": attrs.get("EMVTotal"),
        "last_sale_price": attrs.get("SalePrice") or None,
        "last_sale_date": _parse_epoch_ms(attrs.get("LastSaleDate")),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_address(address: str) -> dict[str, Any] | None:
    """Look up a Ramsey County parcel by free-form street address.

    Returns the single matching parcel as a subject dictionary, or ``None`` when
    nothing matches. Tries a ``BuildingNumber``/``StreetName`` exact match first
    (REQUIRING the directional in the ``SiteAddress`` when the query carries one,
    so N/S/E/W variants of the same street are not collapsed) and falls back to a
    ``SiteAddress LIKE`` search.

    Raises:
        AmbiguousAddressError: when the match returns more than one DISTINCT
            parcel. The first row is never returned silently — a multi-row match
            on an address carrying a directional, unit, or duplicated street name
            is unsafe to resolve arbitrarily (e.g. Lexington Pkwy N vs S).
    """
    if not address:
        return None

    number, street, directional = _split_address(address)
    rows: list[dict[str, Any]] = []
    if number and street:
        # Escape single quotes for SQL safety
        safe_street = street.replace("'", "''")
        where = f"BuildingNumber='{number}' AND StreetName='{safe_street}'"
        # Require the directional in the SiteAddress so a directional query does
        # not match the opposite-directional parcel. Ramsey's SiteAddress carries
        # the directional inline (e.g. '660 LEXINGTON PKWY S'); a bare StreetName
        # match would return both N and S rows.
        if directional:
            where += f" AND UPPER(SiteAddress) LIKE '%{directional}%'"
        rows = _query_api(where, fields=SUBJECT_FIELDS)

    if not rows:
        like = address.strip().upper().replace("'", "''")
        where = f"UPPER(SiteAddress) LIKE '%{like}%'"
        rows = _query_api(where, fields=SUBJECT_FIELDS)

    if not rows:
        return None

    # Collapse rows to DISTINCT parcels (same PID can appear once). A multi-row
    # match across distinct PIDs must NOT silently return rows[0] — that is the
    # 660-Lexington failure (the resolver returned the N parcel for an S query).
    subjects: list[dict[str, Any]] = []
    seen_pids: set[str] = set()
    for r in rows:
        subj = _subject_from_attrs(r)
        if subj["pid"] not in seen_pids:
            seen_pids.add(subj["pid"])
            subjects.append(subj)

    if len(subjects) > 1:
        raise AmbiguousAddressError(address, subjects)
    return subjects[0]


def get_assessment_history(pid: str) -> list[dict[str, Any]]:
    """Return yearly assessment snapshots for the given parcel.

    The Ramsey FeatureServer exposes the current tax year in the ``TaxYear*``
    fields and the two prior years in ``TaxYear1*``/``TaxYear2*``. We decode
    all three into flat dicts and drop years that have no tax-year stamp.
    """
    norm = _normalize_pid(pid)
    rows = _query_api(f"ParcelID='{norm}'", fields=HISTORY_FIELDS)
    if not rows:
        return []
    attrs = rows[0]

    history: list[dict[str, Any]] = []
    for suffix in ("", "1", "2"):
        year = attrs.get(f"TaxYear{suffix}")
        if year in (None, 0):
            continue
        history.append(
            {
                "tax_year": year,
                "assess_year": attrs.get(f"EMVYear{suffix}"),
                "emv_land": attrs.get(f"EMVLand{suffix}"),
                "emv_building": attrs.get(f"EMVBuilding{suffix}"),
                "emv_total": attrs.get(f"EMVTotal{suffix}"),
                "total_tax": attrs.get(f"TotalTax{suffix}"),
                "special_assessment": attrs.get(f"SpecialAssessmentDue{suffix}"),
                # TaxCapacity is only exposed for the current year.
                "tax_capacity": attrs.get("TaxCapacity") if suffix == "" else None,
            }
        )
    history.sort(key=lambda row: row["tax_year"] or 0, reverse=True)
    return history


def _comp_from_attrs(attrs: dict[str, Any]) -> dict[str, Any]:
    return {
        "pid": _normalize_pid(attrs.get("ParcelID", "")),
        "address": attrs.get("SiteAddress"),
        "sf": attrs.get("LivingAreaSquareFeet"),
        "year_built": attrs.get("YearBuilt"),
        "emv_total": attrs.get("EMVTotal"),
        "emv_land": attrs.get("EMVLand"),
        "emv_building": attrs.get("EMVBuilding"),
        "sale_price": attrs.get("SalePrice"),
        "sale_date": _parse_epoch_ms(attrs.get("LastSaleDate")),
        "style": attrs.get("HomeStyleDescription"),
        "lot_acres": attrs.get("ParcelAcresDeed"),
        "owner_name": attrs.get("OwnerName1"),
        "plat_name": attrs.get("PlatName"),
        "lat": attrs.get("Latitude"),
        "lon": attrs.get("Longitude"),
    }


def find_comps(
    pid: str,
    sf: float,
    year_built: int,
    lat: float,
    lon: float,
    radius_miles: float = 0.5,
    max_results: int = 200,
    sf_tolerance: float = 0.30,
    year_tolerance: int = 20,
) -> list[dict[str, Any]]:
    """Find neighborhood single-family comparables for the subject parcel.

    The Ramsey API rejects queries that combine ``LivingAreaSquareFeet``
    BETWEEN with ``YearBuilt`` BETWEEN alongside land-use filters. To work
    around that, we pull all single-family dwellings (``LandUseCode='510'``)
    inside a WGS84 envelope and filter size/year/distance in Python.
    """
    bbox = _bbox_for_radius(lat, lon, radius_miles)
    norm = _normalize_pid(pid)
    rows = _query_api(
        where=f"LandUseCode='{SFR_LAND_USE_CODE}'",
        geometry=bbox,
        fields=COMP_FIELDS,
    )

    sf_min = sf * (1 - sf_tolerance)
    sf_max = sf * (1 + sf_tolerance)
    year_min = year_built - year_tolerance
    year_max = year_built + year_tolerance

    comps: list[dict[str, Any]] = []
    for attrs in rows:
        comp_pid = _normalize_pid(attrs.get("ParcelID", ""))
        if comp_pid == norm:
            continue
        comp_sf = attrs.get("LivingAreaSquareFeet") or 0
        comp_year = attrs.get("YearBuilt") or 0
        if not (sf_min <= comp_sf <= sf_max):
            continue
        if not (year_min <= comp_year <= year_max):
            continue
        comp_lat = attrs.get("Latitude")
        comp_lon = attrs.get("Longitude")
        if comp_lat is None or comp_lon is None:
            continue
        if _haversine_miles(lat, lon, comp_lat, comp_lon) > radius_miles:
            continue
        comps.append(_comp_from_attrs(attrs))

    # Sort by sale date desc (None last).
    comps.sort(key=lambda c: c.get("sale_date") or "", reverse=True)
    return comps[:max_results]


def get_recent_sales(
    lat: float,
    lon: float,
    radius_miles: float = 1.0,
    since_date: str = "2024-01-01",
    max_results: int = 500,
) -> list[dict[str, Any]]:
    """Return recent residential sales within ``radius_miles`` of (lat, lon).

    ``since_date`` is an ISO date string (``YYYY-MM-DD``). Results are
    filtered to rows whose LastSaleDate parses on or after that date and
    whose SalePrice is greater than zero.
    """
    try:
        _date.fromisoformat(since_date)
    except ValueError as e:
        raise ValueError(
            f"since_date must be ISO format (YYYY-MM-DD): {since_date!r}"
        ) from e

    bbox = _bbox_for_radius(lat, lon, radius_miles)
    rows = _query_api(
        where=f"LandUseCode='{SFR_LAND_USE_CODE}'",
        geometry=bbox,
        fields=COMP_FIELDS,
    )

    sales: list[dict[str, Any]] = []
    for attrs in rows:
        price = attrs.get("SalePrice") or 0
        if price <= 0:
            continue
        sale_date = _parse_epoch_ms(attrs.get("LastSaleDate"))
        if not sale_date or sale_date < since_date:
            continue
        comp_lat = attrs.get("Latitude")
        comp_lon = attrs.get("Longitude")
        if comp_lat is None or comp_lon is None:
            continue
        if _haversine_miles(lat, lon, comp_lat, comp_lon) > radius_miles:
            continue
        sales.append(_comp_from_attrs(attrs))

    sales.sort(key=lambda s: s.get("sale_date") or "", reverse=True)
    return sales[:max_results]
