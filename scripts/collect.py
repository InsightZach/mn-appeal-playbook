"""
CLI: collect residential property data for an appeal review.

Usage:
    uv run python -m scripts.collect "1234 Example Ave" --county ramsey --output properties/example/
"""
import argparse
import json
import sys
from datetime import date, datetime, timedelta
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
            radius_sales_mi: float = 1.0, sales_months: int = 24) -> dict:
    """Run the full Phase 1 collection for one address. Returns the data dict."""
    if county not in COUNTY_RESOLVERS:
        raise ValueError(f"Unsupported county: {county}. Supported: {sorted(COUNTY_RESOLVERS)}")
    cr = COUNTY_RESOLVERS[county]

    subject = cr["resolve"](address)
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

    pid = subject["pid"]
    sf = subject.get("living_area_sf") or 0
    year_built = subject.get("year_built") or 0
    lat = subject["lat"]
    lon = subject["lon"]

    assessments = cr["history"](pid)

    if sf and year_built:
        comps = cr["comps"](pid=pid, sf=sf, year_built=year_built,
                            lat=lat, lon=lon, radius_miles=radius_comps_mi)
    elif county == "hennepin" and year_built:
        # Suburban Hennepin has no bulk SF source; the Hennepin collector
        # filters on year/distance alone when sf is None.
        comps = cr["comps"](pid=pid, sf=None, year_built=year_built,
                            lat=lat, lon=lon, radius_miles=radius_comps_mi)
    else:
        comps = []

    since = (date.today() - timedelta(days=sales_months * 30)).isoformat()
    sales = cr["sales"](lat=lat, lon=lon, radius_miles=radius_sales_mi, since_date=since)

    return {
        "subject": subject,
        "assessments": assessments,
        "neighborhood_comps": comps,
        "recent_sales": sales,
        "collected_at": datetime.utcnow().isoformat() + "Z",
        "county": county,
        "params": {
            "radius_comps_mi": radius_comps_mi,
            "radius_sales_mi": radius_sales_mi,
            "sales_since_date": since,
            "sf_tolerance": 0.30,
            "year_tolerance": 20,
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
    args = parser.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Resolving: {args.address}", file=sys.stderr)
    data = collect(
        args.address, args.county,
        radius_comps_mi=args.radius_comps,
        radius_sales_mi=args.radius_sales,
        sales_months=args.sales_months,
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
