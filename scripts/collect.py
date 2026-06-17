"""
CLI: collect residential property data for an appeal review.

Usage:
    uv run python -m scripts.collect "1234 Example Ave" --county ramsey --output properties/example/
"""
import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from collectors import hennepin_residential, ramsey_residential

COUNTY_RESOLVERS = {
    "ramsey": {
        "resolve": ramsey_residential.resolve_address,
        "history": ramsey_residential.get_assessment_history,
        "comps": ramsey_residential.find_comps,
        "sales": ramsey_residential.get_recent_sales,
    },
    "hennepin": {
        "resolve": hennepin_residential.resolve_address,
        "history": hennepin_residential.get_assessment_history,
        "comps": hennepin_residential.find_comps,
        "sales": hennepin_residential.get_recent_sales,
    },
}


def collect(address: str, county: str = "ramsey", radius_comps_mi: float = 0.5,
            radius_sales_mi: float = 1.0, sales_months: int = 24,
            sf_tolerance: float = 0.30, year_tolerance: int = 20) -> dict:
    """Run the full Phase 1 collection for one address. Returns the data dict.

    The band parameters (radius, sales_months, sf_tolerance, year_tolerance) are
    the levers of the comp-expansion ladder (docs: methodology "Expanding a thin
    comp set"). When triage reports a thin matched set, widen them in the
    supportability order — time (sales_months) → radius → vintage (year_tolerance)
    → size (sf_tolerance) — holding the assessed-$/SF tier screen for last (it is
    applied in triage, so the collector never relaxes tier)."""
    if county not in COUNTY_RESOLVERS:
        raise ValueError(f"Unsupported county: {county}. Supported: {sorted(COUNTY_RESOLVERS)}")
    cr = COUNTY_RESOLVERS[county]

    try:
        subject = cr["resolve"](address)
    except ramsey_residential.AmbiguousAddressError as e:
        # The resolver refused to silently pick one of several distinct parcels
        # (e.g. a directional swap: Lexington Pkwy N vs S). Surface the candidates
        # so the analyst disambiguates the query rather than proceeding on the
        # wrong parcel (run-appeal-review.md Step 1).
        candidates = "\n".join(
            f"    {c.get('pid')}  {c.get('address')}  (owner: {c.get('owner_name')})"
            for c in e.candidates
        )
        raise RuntimeError(
            f"Address {address!r} is ambiguous — it matched "
            f"{len(e.candidates)} distinct parcels. Re-query with the exact "
            f"directional/unit. Candidates:\n{candidates}"
        ) from e
    if not subject:
        raise RuntimeError(f"Could not resolve address: {address!r}")

    # Geocode drift guard. The resolver can silently correct a street name or
    # street type (e.g. "Ave" -> "St"), which can land on the wrong parcel. When
    # the resolved address differs from the query, warn and surface the parcel's
    # owner_name + plat so the analyst can confirm the right parcel was selected
    # before proceeding (run-appeal-review.md Step 1).
    resolved_addr = (subject.get("address") or "").strip()
    if resolved_addr and resolved_addr.upper() != address.strip().upper():
        print(
            f"WARNING: resolved address '{resolved_addr}' differs from query "
            f"'{address.strip()}' — confirm the right parcel.\n"
            f"  owner_name: {subject.get('owner_name')}\n"
            f"  plat: {subject.get('plat_name')}\n"
            f"  pid: {subject.get('pid')}",
            file=sys.stderr,
        )

    # Ownership-form / property-type guard. The comp and recent-sales queries are
    # hardwired to single-family residential (Ramsey LandUseCode='510'; the
    # Hennepin collectors are likewise SFH-oriented). When the SUBJECT is NOT a
    # single-family house — most importantly a CONDOMINIUM / common-interest unit
    # (which owns no deeded lot, so its EMV carries only a nominal land value) —
    # every comp and sale returned will be a fee-simple house carrying real land
    # EMV. Applying a house's land-bundled sale $/SF to a landless condo unit
    # systematically OVERSTATES the condo. The collectors cannot supply condo
    # comps, so flag it loudly: the sales-comparison approach is NOT reliable for a
    # non-SFR subject from this data, and the analysis must lean on the subject's
    # own sale + EMV history (see prompts/methodology.md "Property type / ownership
    # form" gate).
    land_use_raw = f"{subject.get('land_use') or ''}".upper()
    emv_land = subject.get("emv_land")
    is_condo = ("CONDO" in land_use_raw or "APT OWN" in land_use_raw
                or "CIC" in land_use_raw or "COMMON INTEREST" in land_use_raw)
    is_sfr = ("SINGLE" in land_use_raw or land_use_raw in ("510", "RESIDENTIAL"))
    if is_condo or (emv_land is not None and 0 < emv_land <= 5000):
        print(
            "WARNING: subject appears to be a CONDOMINIUM / common-interest unit "
            f"(land_use='{subject.get('land_use')}', emv_land={emv_land}). The comp "
            "and recent-sales queries return SINGLE-FAMILY houses only — house "
            "sale $/SF is land-bundled and CANNOT be applied to a landless condo "
            "unit. Treat the sales-comparison approach as UNAVAILABLE absent condo "
            "comps; conclude on the subject's own sale + EMV history. "
            "(methodology.md: Property type / ownership form gate.)",
            file=sys.stderr,
        )
    elif land_use_raw and not is_sfr:
        print(
            f"WARNING: subject land_use='{subject.get('land_use')}' is not "
            "single-family residential, but the comp/recent-sales queries return "
            "SFR only. Confirm the comp set is the right property type before "
            "applying $/SF; the sales approach may be unavailable.",
            file=sys.stderr,
        )

    pid = subject["pid"]
    sf = subject.get("living_area_sf") or 0
    year_built = subject.get("year_built") or 0
    lat = subject["lat"]
    lon = subject["lon"]

    assessments = cr["history"](pid)

    if sf and year_built:
        comps = cr["comps"](pid=pid, sf=sf, year_built=year_built,
                            lat=lat, lon=lon, radius_miles=radius_comps_mi,
                            sf_tolerance=sf_tolerance, year_tolerance=year_tolerance)
    elif county == "hennepin" and year_built:
        # Suburban Hennepin has no bulk SF source; the Hennepin collector
        # filters on year/distance alone when sf is None.
        comps = cr["comps"](pid=pid, sf=None, year_built=year_built,
                            lat=lat, lon=lon, radius_miles=radius_comps_mi,
                            sf_tolerance=sf_tolerance, year_tolerance=year_tolerance)
    else:
        comps = []

    since = (date.today() - timedelta(days=sales_months * 30)).isoformat()
    sales = cr["sales"](lat=lat, lon=lon, radius_miles=radius_sales_mi, since_date=since)

    return {
        "subject": subject,
        "assessments": assessments,
        "neighborhood_comps": comps,
        "recent_sales": sales,
        "collected_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "county": county,
        "params": {
            "radius_comps_mi": radius_comps_mi,
            "radius_sales_mi": radius_sales_mi,
            "sales_months": sales_months,
            "sales_since_date": since,
            "sf_tolerance": sf_tolerance,
            "year_tolerance": year_tolerance,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Collect residential property data for an appeal review.")
    parser.add_argument("address", help="Property address (e.g., '2218 Sargent Ave')")
    parser.add_argument("--county", default="ramsey", help="County (default: ramsey)")
    parser.add_argument("--output", required=True, help="Output directory; collected_data.json will be written here")
    parser.add_argument("--radius-comps", type=float, default=0.5, help="Comp search radius miles")
    parser.add_argument("--radius-sales", type=float, default=1.0, help="Recent sales radius miles")
    parser.add_argument("--sales-months", type=int, default=24, help="Recent sales lookback months")
    # Expansion-ladder levers (widen in this supportability order when triage
    # reports a thin matched set: months → radius → year-tol → sf-tol; tier held).
    parser.add_argument("--sf-tolerance", type=float, default=0.30, help="Comp SF band, ± fraction (expansion lever, widen last)")
    parser.add_argument("--year-tolerance", type=int, default=20, help="Comp vintage band, ± years (expansion lever)")
    args = parser.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Resolving: {args.address}", file=sys.stderr)
    data = collect(
        args.address, args.county,
        radius_comps_mi=args.radius_comps,
        radius_sales_mi=args.radius_sales,
        sales_months=args.sales_months,
        sf_tolerance=args.sf_tolerance,
        year_tolerance=args.year_tolerance,
    )

    out_path = out_dir / "collected_data.json"
    out_path.write_text(json.dumps(data, indent=2))

    subject = data["subject"]
    print(f"\nCollected: {subject.get('address')}", file=sys.stderr)
    print(f"  PID: {subject.get('pid')}", file=sys.stderr)
    print(f"  Year built: {subject.get('year_built')}", file=sys.stderr)
    print(f"  Living area: {subject.get('living_area_sf')} SF", file=sys.stderr)
    print(f"  Lot: {subject.get('parcel_acres')} ac", file=sys.stderr)
    print(f"  Assessments: {len(data['assessments'])} years", file=sys.stderr)
    print(f"  Neighborhood comps: {len(data['neighborhood_comps'])}", file=sys.stderr)
    print(f"  Recent sales: {len(data['recent_sales'])}", file=sys.stderr)
    print(f"\nWrote: {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
