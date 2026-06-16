"""Render the illustrative no-appeal findings sample (530 Desnoyer Ave) through
the report framework — the honest "we checked, there's no clear angle" deliverable.

    uv run python -m scripts.render_no_appeal_sample   # -> examples/sample-no-appeal-findings.html

Demonstrates the discipline of testing an equalization signal against market
support: the building $/SF looks high against a broad median, but the immediate
peer group and a real arm's-length sale show the assessment is fair.
Figures are real Ramsey County assessment + sale data.
"""
# NOTE — this is a FIXTURE / DEMO. The data dict below was authored by reasoning
# (the reconciliation, the concluded value, the narrative) — in production an agent
# running prompts/appeal-packet.md (or no-appeal-findings.md) produces this dict from
# the collected data, and this file just renders it. The script never decides the value.

from pathlib import Path

from report.no_appeal_generator import generate_no_appeal_report

SUBJ_SF = 2369

# Building $/SF among same-size neighborhood homes (subject looks high vs the
# broad median, but mid-pack vs its immediate Otis/Pelham peers).
BLDG = [
    ("472 Otis Ave", 1940, 316), ("375 Pelham Blvd", 2310, 306),
    ("2301 Beverly Rd", 2546, 283), ("492 Otis Ave", 2579, 272),
    ("554 Glendale St", 1965, 269), ("2454 Beverly Rd", 2006, 265),
    ("586 Eustis St", 2737, 257), ("444 Otis Ave", 2252, 251),
    ("412 Otis Ave", 2397, 250),
]

DATA = {
    "meta": {
        "assessment_year": 2026, "payable_year": 2027,
        "brand": "Residential Property Tax Appeal",
        "report_title": "Assessment Review Findings — 530 Desnoyer Ave, St. Paul",
    },
    "subject": {
        "address": "530 Desnoyer Ave, St. Paul, MN 55104",
        "pid": "32-29-23-23-0151", "year_built": 1928,
        "living_area_sf": SUBJ_SF, "lot_acres": 0.16,
        "plat_name": "Desnoyer Park",
        "emv_land": 130800, "emv_building": 705700, "emv_total": 836500,
    },
    "summary": {
        "headline": "No clear angle — the assessment is supported by recent sales.",
        "body": "We pulled the county data and the recent neighborhood sales. The subject's building value "
                "per square foot looks high against a broad neighborhood median, which is worth a look — but "
                "against its immediate Otis Ave / Pelham peers it is mid-pack, and a recent arm's-length sale "
                "two blocks away supports values at this level. The county also already trimmed the 2026 EMV "
                "3.2%. We don't see a clear angle to appeal.",
    },
    "work_completed": [
        "Pulled the 3-year assessment history from Ramsey County",
        "Pulled 56 arm's-length neighborhood sales (Apr 2024 – Mar 2026)",
        "Computed the neighborhood EMV-to-sale ratio",
        "Compared the subject's land and building $/SF to same-size peers",
        "Identified the strongest comp the county would lead with",
        "Tested the building $/SF signal against actual market sales",
    ],
    "assessments": [
        {"tax_year": 2025, "assess_year": 2024, "emv_land": 130800, "emv_building": 634800, "emv_total": 765600},
        {"tax_year": 2026, "assess_year": 2025, "emv_land": 130800, "emv_building": 733000, "emv_total": 863800},
        {"tax_year": 2027, "assess_year": 2026, "emv_land": 130800, "emv_building": 705700, "emv_total": 836500},
    ],
    "findings": [
        {"title": "The county already cut the 2026 value 3.2%",
         "body": "After a 12.8% jump in 2025 ($765,600 → $863,800), the county trimmed the 2026 EMV to "
                 "$836,500 (−$27,300, −3.2%). The aggressive year was already partly corrected."},
        {"title": "Building $/SF looks high against a broad median — worth checking",
         "body": "The subject's building is assessed at $298/SF vs. a $218 same-size neighborhood median. On "
                 "its own that reads as a possible over-assessment, so we tested it against the market."},
        {"title": "...but against the immediate peer group it is mid-pack",
         "body": "The closest same-street peers run higher, not lower: 472 Otis $316/SF, 375 Pelham $306/SF, "
                 "492 Otis $272/SF. The subject's $298/SF sits inside that immediate range. The broad median "
                 "is pulled down by lower-value pockets that aren't truly comparable."},
        {"title": "A recent arm's-length sale supports the value",
         "body": "38 Otis Ave (2,170 SF, two blocks away) sold for $800,000 in April 2025 and is itself "
                 "assessed at $765,800. The subject is larger (2,369 SF); its $836,500 EMV is consistent with "
                 "that sale on a per-SF basis."},
        {"title": "Neighborhood assessments run slightly below market",
         "body": "Across 56 arm's-length sales the median EMV-to-sale ratio is 0.976 — assessments run about "
                 "2.4% below sale prices. The subject is not an outlier the other way."},
    ],
    "stat_summary": {
        "properties_analyzed": 40, "sales_analyzed": 56, "models_run": 2,
        "plats_analyzed": 1, "years_of_history": 3,
    },
    "bldg_psf_chart": {
        "data": [{"x": sf, "y": psf, "label": f"{name} (${psf}/SF)"} for name, sf, psf in BLDG],
        "subject_xy": {"x": SUBJ_SF, "y": 298},
        "trends": [],
        "caption": "Building $/SF vs. finished SF — subject (highlighted) sits inside the immediate "
                   "Otis/Pelham peer range, not above it.",
    },
    "killer_comp": {
        "address": "38 Otis Ave", "sale_price": 800000, "sale_date": "Apr 2025", "distance_mi": 0.2,
        "summary": "The strongest comp the county would lead with: a recent arm's-length sale two blocks "
                   "away, similar era, slightly smaller.",
        "subject_advantages": ["Larger (2,369 SF vs. 2,170 SF)"],
        "comp_advantages": ["More recent reference point"],
        "adjustments": [
            {"description": "Size (subject +199 SF)", "direction": "up (comp up)", "amount": 30000},
            {"description": "Sale date / time (Apr 2025 → 1/2/2026)", "direction": "up", "amount": 18000},
        ],
        "matters_headline": "Why this comp matters",
        "matters_body": "A real, recent, arm's-length sale at this value level — assessed below its own "
                        "sale price — is the evidence an appeal would have to overcome. It does not support "
                        "a reduction.",
    },
    "regression_conclusions": [
        {"model_name": "Neighborhood EMV-to-sale ratio (56 sales)", "predicted_value": 816000,
         "current_emv": 836500, "delta": -20500, "delta_pct": -2.4},
    ],
    "final_recommendation": {
        "headline": "No Appeal",
        "bullets": [
            "The 2026 EMV of $836,500 is supported by a recent arm's-length sale two blocks away.",
            "The building $/SF signal does not survive contact with the immediate peer group or the market.",
            "The county already corrected most of the 2025 jump (−3.2% for 2026).",
            "If filed, the county would lead with the 38 Otis sale, and we'd have no clear answer.",
        ],
    },
}


def main():
    html = generate_no_appeal_report(DATA)
    banner = (
        '<div style="background:#fff3cd;color:#7a5c00;text-align:center;padding:0.5rem 1rem;'
        'font-size:0.85rem;border-bottom:1px solid #e6d28a;font-family:Segoe UI,system-ui,sans-serif;">'
        'ILLUSTRATIVE SAMPLE — built from public Ramsey County assessment and sale data. Not a filed '
        'document.</div>'
    )
    html = html.replace("<body>", "<body>\n" + banner, 1)
    out = Path(__file__).resolve().parent.parent / "examples" / "sample-no-appeal-findings.html"
    out.write_text(html)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
