"""Render the illustrative 884 Ashland sample appeal packet through the report
framework (report/appeal_generator.py), demonstrating the $/SF adjustment grid
and supported-value method.

    uv run python -m scripts.render_sample        # -> examples/sample-appeal-packet.html

Figures are real Ramsey County assessment data + the MLS sale record. Per-comp
condition is illustrative (in production it is verified from listing/CAMA review).
"""
# NOTE — this is a FIXTURE / DEMO. The data dict below was authored by reasoning
# (the reconciliation, the concluded value, the narrative) — in production an agent
# running prompts/appeal-packet.md (or no-appeal-findings.md) produces this dict from
# the collected data, and this file just renders it. The script never decides the value.

from pathlib import Path

from report.appeal_generator import generate_appeal_report

SUBJECT_SF = 1355

# Same-size neighborhood comps for the equalization building $/SF scatter.
EQ = [
    ("25 Milton St N", 1364, 274), ("778 Holly Ave", 1176, 252),
    ("771 Ashland Ave", 1254, 241), ("790 Laurel Ave", 1632, 233),
    ("872 Dayton Ave", 1596, 212), ("885 Portland Ave", 1325, 204),
    ("1047 Dayton Ave", 1400, 203), ("107 Milton St N", 1616, 201),
    ("1085 Ashland Ave", 1344, 198),
]

DATA = {
    "meta": {
        "assessment_year": 2026,
        "payable_year": 2027,
        "brand": "Residential Property Tax Appeal",
        "report_title": "Assessment Appeal Review — 884 Ashland Ave, St. Paul",
        "assessment_date": "January 2, 2026",
        "petition_deadline": "April 30, 2027",
        "tax_rate": 0.0174,  # 25p26 ETR proxy (prior-year tax ÷ EMV); see docs/09
        "sample_banner": True,
    },
    "subject": {
        "address": "884 Ashland Ave, St. Paul, MN 55104",
        "pid": "02-28-23-24-0039",
        "year_built": 1939,
        "living_area_sf": SUBJECT_SF,
        "lot_acres": 0.14,
        "plat_name": "Summit Park Addition",
        "style": "Single family (renovated)",
        "emv_total": 498600, "emv_land": 140400, "emv_building": 358200,
    },
    "assessments": [
        {"assess_year": 2024, "tax_year": 2025, "emv_land": 140400, "emv_building": 313000, "emv_total": 453400},
        {"assess_year": 2025, "tax_year": 2026, "emv_land": 140400, "emv_building": 371500, "emv_total": 511900},
        {"assess_year": 2026, "tax_year": 2027, "emv_land": 140400, "emv_building": 358200, "emv_total": 498600},
    ],
    "basis_for_appeal": [
        {"title": "The subject's own arm's-length sale governs",
         "body": "884 Ashland sold in an open-market, arm's-length transaction for <strong>$470,000 on "
                 "April 10, 2025</strong> — confirmed in the MLS record — about nine months before the "
                 "January 2, 2026 effective date. That is <strong>5.7% below</strong> the 2026 EMV of "
                 "$498,600. A property's own recent sale is the most direct evidence of its market value.",
         "color": "amber"},
        {"title": "Condition is not at issue — the home is renovated",
         "body": "Listing photos show an updated interior, so <strong>no condition deduction is claimed</strong>; "
                 "the appeal rests on the sale. Note the listing reports 2,060 SF and a 1970 build against the "
                 "county record of 1,355 SF and 1939 — flagged for verification, not relied upon.",
         "color": "amber"},
    ],
    "sales_subtitle": "Six arm's-length closed sales within ~1 mile, adjusted on a $/SF basis to indicate "
                      "subject value as of 1/2/2026. Size is resolved by applying the reconciled $/SF to the "
                      "subject's own square footage.",
    "sales_intro": "$/SF is the sale price divided by Ramsey finished SF. The subject sold at $347/SF — above "
                   "every comp — consistent with its renovated condition.",
    "recent_sales": [
        {"address": "57 Dale St N", "sale_price": 410000, "sale_date": "Jan 2026", "sf": 1476, "year_built": 1889},
        {"address": "402 Clifton St", "sale_price": 355000, "sale_date": "Aug 2025", "sf": 1751, "year_built": 1900},
        {"address": "492 Dayton Ave", "sale_price": 360000, "sale_date": "Jul 2025", "sf": 1892, "year_built": 1894},
        {"address": "742 Laurel Ave", "sale_price": 317000, "sale_date": "Aug 2025", "sf": 1140, "year_built": 1899},
        {"address": "969 Portland Ave", "sale_price": 316500, "sale_date": "Aug 2025", "sf": 1064, "year_built": 1956},
        {"address": "904 Dayton Ave", "sale_price": 553000, "sale_date": "Jan 2026", "sf": 1945, "year_built": 1901},
    ],
    "adjustment_schedule": [
        {"adjustment": "Time", "rate": "+0.25% / month to 1/2/2026", "basis": "≈3% annualized market trend"},
        {"adjustment": "Condition: Average → renovated subject", "rate": "+10% to +12%", "basis": "One grade step to the subject's renovated condition"},
        {"adjustment": "Condition: Below avg / dated → subject", "rate": "+20%", "basis": "Two steps to renovated"},
        {"adjustment": "Condition: Above avg / updated → subject", "rate": "+5%", "basis": "Partial step"},
        {"adjustment": "Size", "rate": "(handled via $/SF)", "basis": "Resolved by applying reconciled $/SF to subject SF — not a grid line"},
    ],
    "adjustment_schedule_intro": "Adjustments apply to each comp's sale <strong>$/SF</strong> (additive). "
                                 "Condition is shown illustratively for this sample; in production each comp's "
                                 "condition is verified from listing photos or the county CAMA card.",
    "adjustment_grid_subject_sf": SUBJECT_SF,
    "adjustment_grid": [
        {"address": "57 Dale St N", "descriptor": "1,476 SF / Avg", "sale_price": 410000, "sale_date": "Jan 2026", "sf": 1476, "time_pct": 0.0, "condition_pct": 10},
        {"address": "402 Clifton St", "descriptor": "1,751 SF / Below avg", "sale_price": 355000, "sale_date": "Aug 2025", "sf": 1751, "time_pct": 1.25, "condition_pct": 20},
        {"address": "492 Dayton Ave", "descriptor": "1,892 SF / Below avg", "sale_price": 360000, "sale_date": "Jul 2025", "sf": 1892, "time_pct": 1.5, "condition_pct": 20},
        {"address": "742 Laurel Ave", "descriptor": "1,140 SF / Avg", "sale_price": 317000, "sale_date": "Aug 2025", "sf": 1140, "time_pct": 1.25, "condition_pct": 12},
        {"address": "969 Portland Ave", "descriptor": "1,064 SF / Avg", "sale_price": 316500, "sale_date": "Aug 2025", "sf": 1064, "time_pct": 1.25, "condition_pct": 12},
        {"address": "904 Dayton Ave", "descriptor": "1,945 SF / Above avg", "sale_price": 553000, "sale_date": "Jan 2026", "sf": 1945, "time_pct": 0.0, "condition_pct": 5},
    ],
    "sales_reconciliation": "The adjusted $/SF cluster around a median of ~$302/SF, indicating roughly "
                            "<strong>$409,000</strong> for the subject's 1,355 SF. These inferior-condition "
                            "comps adjust upward toward the renovated subject and still land below it — the "
                            "subject's <strong>own arm's-length sale of $470,000</strong> ($347/SF) is the most "
                            "reliable single indicator and is adopted as the conservative concluded value. The "
                            "comparable evidence confirms the $498,600 EMV is high.",
    "sales_indicated_value": 409000,
    "equalization_subtitle": "Cross-check against the county's own assessment data for nine same-size "
                             "single-family homes (finished SF 1,100–1,650) nearby.",
    "land_observation": "The subject's land at $23.02/SF is essentially at the same-size neighborhood median "
                        "($24.10/SF) — well-aligned, no land inequity.",
    "building_observation": {
        "body": "The subject's building at $264/SF is about 24% above the same-size median ($212/SF), at the "
                "upper end of the range ($198–$274) — consistent with its renovated condition. Equalization is "
                "a low-weight cross-check and does not independently justify a reduction below the market sale."
    },
    "building_emv_chart": {
        "data": [{"x": sf, "y": psf, "label": f"{name} (${psf}/SF)"} for name, sf, psf in EQ],
        "subject_xy": {"x": SUBJECT_SF, "y": 264},
        "trends": [],
        "caption": "Building $/SF vs. finished SF — subject (highlighted) vs. nine same-size neighborhood "
                   "comps. Above median, within the renovated upper range.",
    },
    "conclusion": {
        "concluded_value": 470000,
        "assessment_date": "January 2, 2026",
        "petition_deadline": "April 30, 2027",
        "narrative": "The subject's own arm's-length sale of $470,000 (April 2025), confirmed in the MLS record, "
                     "is the best evidence of market value as of the effective date. The sales-comparison "
                     "approach indicates roughly $409,000 and equalization shows the assessment is modestly "
                     "aggressive on the building line — both corroborate that the $498,600 EMV is high. We "
                     "conservatively conclude the property's own sale price and request the 2026 EMV be reduced "
                     "to $470,000 (a reduction of $28,600, 5.7%). No condition adjustment is claimed.",
    },
}


def main():
    html = generate_appeal_report(DATA)
    # Prepend the illustrative-sample banner (the framework has no banner slot).
    banner = (
        '<div style="background:#fff3cd;color:#7a5c00;text-align:center;padding:0.5rem 1rem;'
        'font-size:0.85rem;border-bottom:1px solid #e6d28a;font-family:Segoe UI,system-ui,sans-serif;">'
        'ILLUSTRATIVE SAMPLE — built from public Ramsey County assessment data and the MLS sale record for '
        'one property. Not a filed appeal; per-comp condition shown illustratively.</div>'
    )
    html = html.replace("<body>", "<body>\n" + banner, 1)
    out = Path(__file__).resolve().parent.parent / "examples" / "sample-appeal-packet.html"
    out.write_text(html)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
