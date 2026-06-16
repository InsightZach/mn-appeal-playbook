"""
CLI: run the triage analysis on a collected_data.json and emit analysis.json.

Triage = everything Phase 4/5 of the appeal review can compute WITHOUT Beacon or
Zillow scraping: killer comp, subject's own sale, sales-regression convergence,
equalization trends, EMV history, and a verdict with reasons. Used for batch
screening (e.g., the baseline 26p27 list) before deciding which properties get the
full scrape + report treatment.

Usage:
    uv run python -m scripts.triage properties/{slug}/collected_data.json \
        [--baseline-emv 511900] [--output analysis.json]
"""
import argparse
import json
from pathlib import Path

from analysis.killer_comp import identify_killer_comp
from analysis.sales_regression import (
    compute_sales_trend,
    remove_outliers_iqr,
    multi_model_convergence,
)
from analysis.equalization import (
    compute_land_psf_trend,
    compute_building_psf_trend,
    apply_trend_to_subject,
)

SQFT_PER_ACRE = 43560


def _psf_points(sales: list[dict]) -> list[dict]:
    pts = []
    for s in sales:
        price, sf = s.get("sale_price"), s.get("sf")
        if price and sf:
            pts.append({**s, "psf": price / sf, "date": s.get("sale_date")})
    return pts


def triage(data: dict, baseline_emv: float | None = None) -> dict:
    subject = dict(data["subject"])
    assessments = sorted(data["assessments"], key=lambda a: a["assess_year"], reverse=True)
    current = assessments[0]
    subject["emv_total"] = current["emv_total"]
    assess_date = f"{current['assess_year']}-01-02"

    sf = subject.get("living_area_sf") or 0
    lot_sf = (subject.get("parcel_acres") or 0) * SQFT_PER_ACRE
    comps = data.get("neighborhood_comps", [])
    sales = data.get("recent_sales", [])

    # EMV history with YoY change
    history = []
    for i, a in enumerate(assessments):
        prior = assessments[i + 1]["emv_total"] if i + 1 < len(assessments) else None
        history.append({
            "assess_year": a["assess_year"],
            "emv_total": a["emv_total"],
            "emv_land": a.get("emv_land"),
            "emv_building": a.get("emv_building"),
            "yoy_change": (a["emv_total"] - prior) if prior else None,
            "yoy_pct": round((a["emv_total"] - prior) / prior * 100, 1) if prior else None,
        })

    # baseline's spreadsheet value is typically a PRIOR-year assessment (their
    # data source lags) — identify which year it matches rather than
    # treating it as the appealed value.
    baseline_cmp = None
    if baseline_emv:
        matched = next((a["assess_year"] for a in assessments
                        if abs(a["emv_total"] - baseline_emv) < 100), None)
        baseline_cmp = {
            "baseline_emv": baseline_emv,
            "current_emv": current["emv_total"],
            "delta": current["emv_total"] - baseline_emv,
            "baseline_value_matches_assess_year": matched,
        }

    # Subject's own sale in the sales window — strongest possible evidence
    own_sale = next((s for s in sales if s.get("pid") == subject["pid"]), None)
    own_sale_finding = None
    if own_sale and own_sale.get("sale_price"):
        d = own_sale["sale_price"] - current["emv_total"]
        own_sale_finding = {
            "sale_price": own_sale["sale_price"],
            "sale_date": own_sale.get("sale_date"),
            "delta_from_emv": d,
            "delta_pct": round(d / current["emv_total"] * 100, 1),
        }

    # identify_killer_comp scores on Beacon-shaped keys (absf, lot_acres,
    # exterior, style) — map the collected records into that shape, and keep
    # only sales we can defend as arm's-length (Ramsey records carry no sale
    # code; Hennepin's "EXCLUDED FROM RATIO STUDIES" / "OTHER – SEE CRV"
    # sales are dropped from killer-comp selection).
    structure = subject.get("structure") or {}
    kc_subject = {
        **subject,
        "absf": sf or None,
        "lot_acres": subject.get("parcel_acres"),
        "exterior": structure.get("exterior"),
        "style": structure.get("style") or subject.get("style"),
    }
    kc_sales = [
        {**s, "absf": s.get("sf")}
        for s in sales
        if s.get("sale_code") is None or s.get("sale_code") == "WARRANTY DEED"
    ]
    killer = identify_killer_comp(kc_subject, kc_sales)

    # Sales regression: subject plat / other plats / combined, IQR-cleaned
    pts = remove_outliers_iqr(_psf_points(sales), key="psf")
    plat = subject.get("plat_name")
    models = {}
    same = [p for p in pts if plat and p.get("plat_name") == plat]
    other = [p for p in pts if not plat or p.get("plat_name") != plat]
    if len(same) >= 5:
        models["subject_plat"] = compute_sales_trend(same)
    if len(other) >= 5:
        models["other_plats"] = compute_sales_trend(other)
    if len(pts) >= 5:
        models["combined"] = compute_sales_trend(pts)
    convergence = multi_model_convergence(models, assess_date, sf) if (models and sf) else None

    # Equalization vs neighborhood comps. The comps are already filtered to
    # similar SF/year/distance, so percentile rank of the subject's assessed
    # $/SF among them is the primary triage signal. The regression-implied
    # value is only trusted when the fit is real (R² gate) — neighborhood
    # scatter usually isn't linear in size.
    land_pts = [{"lot_sf": (c.get("lot_acres") or 0) * SQFT_PER_ACRE, "land": c.get("emv_land")} for c in comps]
    bldg_pts = [{"sf": c.get("sf"), "bldg": c.get("emv_building")} for c in comps]
    land_trend = compute_land_psf_trend(land_pts)
    bldg_trend = compute_building_psf_trend(bldg_pts)
    equalization = None
    if land_trend["n"] >= 5 and bldg_trend["n"] >= 5 and sf and lot_sf:
        comp_bpsf = sorted(p["bldg"] / p["sf"] for p in bldg_pts if p.get("sf") and p.get("bldg"))
        comp_lpsf = sorted(p["land"] / p["lot_sf"] for p in land_pts if p.get("lot_sf") and p.get("land"))
        subj_bpsf = (current.get("emv_building") or 0) / sf
        subj_lpsf = (current.get("emv_land") or 0) / lot_sf
        bpsf_pctile = round(sum(1 for v in comp_bpsf if v < subj_bpsf) / len(comp_bpsf) * 100)
        lpsf_pctile = round(sum(1 for v in comp_lpsf if v < subj_lpsf) / len(comp_lpsf) * 100)
        median_bpsf = comp_bpsf[len(comp_bpsf) // 2]
        median_lpsf = comp_lpsf[len(comp_lpsf) // 2]
        equalization = {
            "subject_building_psf": round(subj_bpsf, 1),
            "comp_median_building_psf": round(median_bpsf, 1),
            "building_psf_percentile": bpsf_pctile,
            "subject_land_psf": round(subj_lpsf, 1),
            "comp_median_land_psf": round(median_lpsf, 1),
            "land_psf_percentile": lpsf_pctile,
            "median_implied_total": round(median_bpsf * sf + median_lpsf * lot_sf),
            "land_trend": land_trend,
            "building_trend": bldg_trend,
        }
        if land_trend["r2"] >= 0.3 and bldg_trend["r2"] >= 0.3:
            _, land_pred = apply_trend_to_subject(land_trend, lot_sf=lot_sf)
            _, bldg_pred = apply_trend_to_subject(bldg_trend, sf=sf)
            equalization["regression_implied_total"] = round(land_pred + bldg_pred)
            equalization["regression_gap_vs_emv"] = round(land_pred + bldg_pred - current["emv_total"])

    # Verdict (methodology.md Phase 5 thresholds, minus condition which needs
    # client input, minus building-inequity which needs Beacon ABSF)
    reasons, verdict = [], "no_angle"
    if len(history) > 1 and history[0]["yoy_change"] is not None and history[0]["yoy_change"] < 0:
        reasons.append(f"{history[0]['assess_year']} EMV already declined "
                       f"${-history[0]['yoy_change']:,.0f} ({history[0]['yoy_pct']}%) from prior year")
    if own_sale_finding and own_sale_finding["delta_pct"] < -5:
        verdict = "appeal_angle"
        reasons.append(f"Subject itself sold {own_sale_finding['delta_pct']}% below current EMV "
                       f"(${own_sale_finding['sale_price']:,.0f} on {own_sale_finding['sale_date']})")
    if killer and killer.get("verdict") == "supports_appeal":
        verdict = "appeal_angle"
        reasons.append(f"Killer comp {killer['comp']['address']} sold {killer['delta_pct']:.1f}% below EMV")
    if equalization:
        gap = equalization.get("regression_gap_vs_emv")
        if gap is not None and gap < -30000:
            verdict = "appeal_angle"
            reasons.append(f"Equalization regression implies ${-gap:,.0f} below EMV")
        elif equalization["building_psf_percentile"] >= 80 and equalization["land_psf_percentile"] >= 80:
            verdict = "appeal_angle"
            reasons.append(
                f"Subject assessed above {min(equalization['building_psf_percentile'], equalization['land_psf_percentile'])}% "
                f"of comps on BOTH building $/SF (${equalization['subject_building_psf']}/SF vs ${equalization['comp_median_building_psf']} median) "
                f"and land $/SF (${equalization['subject_land_psf']} vs ${equalization['comp_median_land_psf']})")
        elif equalization["building_psf_percentile"] >= 80 or equalization["land_psf_percentile"] >= 80:
            if verdict == "no_angle":
                verdict = "borderline"
            reasons.append(
                f"Equalization: building $/SF at {equalization['building_psf_percentile']}th percentile, "
                f"land $/SF at {equalization['land_psf_percentile']}th percentile of comps")
    if verdict == "no_angle":
        if killer and killer.get("verdict") == "kills_appeal" and convergence and convergence["verdict"] == "tight":
            reasons.append("Killer comp at EMV and sales models converge tightly — no angle")
        elif not reasons:
            verdict = "borderline"
            reasons.append("No single threshold tripped; needs judgment review")

    return {
        "subject": subject,
        "assess_date": assess_date,
        "emv_history": history,
        "baseline_comparison": baseline_cmp,
        "subject_own_sale": own_sale_finding,
        "killer_comp": killer,
        "sales_convergence": convergence,
        "equalization": equalization,
        "verdict": verdict,
        "reasons": reasons,
    }


def main():
    p = argparse.ArgumentParser(description="Triage analysis on collected_data.json")
    p.add_argument("collected", help="Path to collected_data.json")
    p.add_argument("--baseline-emv", type=float, default=None, help="The baseline/listed EMV to compare against the true current value (e.g. from a source spreadsheet)")
    p.add_argument("--output", default=None, help="Output path (default: analysis.json next to input)")
    args = p.parse_args()

    data = json.loads(Path(args.collected).read_text())
    result = triage(data, baseline_emv=args.baseline_emv)

    out = Path(args.output) if args.output else Path(args.collected).parent / "analysis.json"
    out.write_text(json.dumps(result, indent=2, default=str))

    print(f"VERDICT: {result['verdict']}")
    for r in result["reasons"]:
        print(f"  - {r}")
    print(f"Wrote: {out}")


if __name__ == "__main__":
    main()
