"""scripts/build_finding.py — the deterministic NO-APPEAL findings assembler.

The no-appeal twin of `scripts/build_packet.py`. A no-appeal finding is still a
piece of work product an agent could fudge by hand-typing the conclusion; this
builder makes the load-bearing calls deterministic:

  * **Scenario is classified from the numbers**, not asserted —
      `fairly_assessed`   : no indicated reduction (comps/own-sale bracket the
                            subject at/above EMV, or the gap is < ~2%). Concluded
                            value = the current EMV, reduction $0.
      `below_savings_floor`: a real reduction exists, but the recurring CLIENT
                            savings (reduction × ETR) fall short of the ~$1,000/yr
                            floor — high assessment, but not worth pursuing.
  * **It REFUSES to call an appealable property "no appeal."** If an indicated
    reduction clears the $1,000/yr savings floor, build_finding raises and points
    you at build_packet — the same guardrail, the other direction.

Everything else (subject, assessment history, the work-completed list, findings
callouts, the best-comp deep dive, charts, the final recommendation) is the
agent's narrative, supplied in `judgment.json` under a `finding` block and rendered
verbatim by `report.no_appeal_generator`. Narrative strings are templated against
the derived numbers (`{emv}`, `{indicated}`, `{reduction}`, `{annual_savings}`, …).

    uv run python -m scripts.build_finding properties/<slug>/judgment.json \
        [--analysis ...] [--beacon ...] --output properties/<slug>/finding.html
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from analysis.structure import resolve_structure
from report.no_appeal_generator import generate_no_appeal_report
from report.shared_components import extraction_comp_indication
from scripts.build_packet import (
    _auto_time_pct, _beacon_fill, _fmt_narrative, _maybe_load, _median, _norm_pid,
)

# The recurring client-savings floor (mirrors triage.MIN_ANNUAL_CLIENT_SAVINGS and
# docs/04). At/above this, an appeal is worth pursuing → it is NOT a no-appeal.
MIN_ANNUAL_CLIENT_SAVINGS = 1000
DEFAULT_ETR = 0.0115
NEUTRAL_BAND = 0.02   # an indicated value within ±2% of EMV is "fairly assessed", not an angle


def build_finding(judgment: dict, analysis: dict | None = None,
                  beacon: dict | None = None, collected: dict | None = None) -> dict:
    """Assemble the no-appeal findings data dict. Classifies the scenario from the
    derived figures and raises if the property actually clears the worth-it floor
    (it would be an appeal, not a finding). Returns the dict for
    ``generate_no_appeal_report``."""
    analysis = analysis or {}
    structure = resolve_structure(beacon, collected)

    meta_in = dict(judgment.get("meta") or {})
    subj_in = dict(judgment.get("subject") or {})
    a_subj = analysis.get("subject") or {}
    for k in ("address", "pid", "year_built", "emv_total", "emv_land",
              "emv_building", "lot_acres", "plat_name", "living_area_sf"):
        if subj_in.get(k) is None and a_subj.get(k) is not None:
            subj_in[k] = a_subj[k]
    _beacon_fill(subj_in, structure.get("subject"))

    emv = float(subj_in.get("emv_total") or 0)
    if emv <= 0:
        raise ValueError("build_finding: subject emv_total is missing/zero — set it in "
                         "judgment.json or pass --analysis to backfill it.")

    # --- ETR for the savings math (triage's, else the packet display rate, else default) ---
    etr = float((analysis.get("tax_economics") or {}).get("etr")
                or meta_in.get("tax_rate") or DEFAULT_ETR)

    # --- derive the sales indication (if the agent supplied extraction comps) ---
    # Same machinery as build_packet: join structure, auto-time, extraction.
    indicated = _derive_indication(judgment, analysis, structure, subj_in, meta_in)

    # --- classify the scenario deterministically ---
    reduction = int(round(emv - indicated)) if indicated is not None else 0
    annual_savings = int(round(reduction * etr)) if reduction > 0 else 0
    if indicated is None or reduction <= NEUTRAL_BAND * emv:
        scenario = "fairly_assessed"
        concluded, reduction, annual_savings = int(emv), 0, 0
    elif annual_savings < MIN_ANNUAL_CLIENT_SAVINGS:
        scenario = "below_savings_floor"
        concluded = int(indicated)
    else:
        raise ValueError(
            f"build_finding: the indicated value ${indicated:,.0f} is ${reduction:,} "
            f"below EMV → ~${annual_savings:,}/yr in client savings, which CLEARS the "
            f"~${MIN_ANNUAL_CLIENT_SAVINGS:,} floor. This is an APPEAL, not a no-appeal "
            "finding — use scripts.build_packet.")

    numbers = {
        "emv": int(emv), "indicated": int(indicated) if indicated is not None else None,
        "reduction": reduction, "reduction_pct": round(reduction / emv * 100, 1),
        "annual_savings": annual_savings, "min_savings": MIN_ANNUAL_CLIENT_SAVINGS,
        "etr_pct": round(etr * 100, 2), "scenario": scenario,
    }
    fin = judgment.get("finding") or {}

    def N(key, default=""):
        return _fmt_narrative(fin.get(key, default), numbers)

    _default_headline = {
        "fairly_assessed": "No appeal recommended — the assessment is supported",
        "below_savings_floor": "No appeal recommended — the savings don't justify pursuing it",
    }[scenario]
    _default_summary = {
        "fairly_assessed": "We pulled the county data and the recent neighborhood sales. The current "
                           "assessment lines up with the market and the comparable assessments — we don't "
                           "see a clear angle to appeal.",
        "below_savings_floor": (
            f"The assessment looks high by about ${reduction:,} — but at the current tax rate that is only "
            f"~${annual_savings:,}/yr in savings, below the ~${MIN_ANNUAL_CLIENT_SAVINGS:,} threshold where "
            "an appeal is worth pursuing. The assessment is high; the economics are not there."),
    }[scenario]

    data: dict = {
        "meta": {
            "assessment_year": meta_in.get("assessment_year"),
            "payable_year": meta_in.get("payable_year"),
            "brand": meta_in.get("brand", "Residential Property Tax Appeal"),
            "report_title": meta_in.get("report_title"),
            "generated_at": meta_in.get("generated_at"),
            "county_correction_note": fin.get("county_correction_note"),
        },
        "subject": {
            "address": subj_in.get("address"), "pid": subj_in.get("pid"),
            "year_built": subj_in.get("year_built"),
            "living_area_sf": subj_in.get("living_area_sf") or subj_in.get("absf"),
            "lot_acres": subj_in.get("lot_acres"), "plat_name": subj_in.get("plat_name"),
            "emv_total": int(emv), "emv_land": subj_in.get("emv_land"),
            "emv_building": subj_in.get("emv_building"),
            "absf": subj_in.get("absf"), "basement_finished": subj_in.get("fin_bsmt_sf"),
        },
        "summary": {"headline": N("summary_headline", _default_headline),
                    "body": N("summary_body", _default_summary)},
        "assessments": judgment.get("assessments") or [
            {"assess_year": h.get("assess_year"), "tax_year": (h.get("assess_year") or 0) + 1,
             "emv_land": h.get("emv_land"), "emv_building": h.get("emv_building"),
             "emv_total": h.get("emv_total")}
            for h in (analysis.get("emv_history") or [])
        ],
        "work_completed": fin.get("work_completed") or [],
        "findings": [
            {"title": _fmt_narrative(f.get("title", ""), numbers),
             "body": _fmt_narrative(f.get("body", ""), numbers),
             "color": f.get("color", "blue")}
            for f in (fin.get("findings") or [])
        ],
        "final_recommendation": {
            "headline": N("final_headline", "No Appeal"),
            # No default body — the bullets carry the final rec; a default here would
            # just echo the top summary box. Render one only if the agent writes it.
            "body": N("final_body", ""),
            "bullets": [_fmt_narrative(b, numbers) for b in (fin.get("final_bullets") or [])],
        },
    }
    # Pass-through rich sections the renderer supports, when the agent supplies them.
    for k in ("stat_summary", "plat_table", "land_psf_chart", "bldg_psf_chart",
              "sales_by_plat_chart", "sales_clean_chart", "regression_conclusions",
              "killer_comp", "killer_comp_photos", "killer_comp_beacon"):
        if fin.get(k) is not None:
            data[k] = fin[k]

    data["_numbers"] = numbers
    return data


def _derive_indication(judgment, analysis, structure, subj_in, meta_in) -> float | None:
    """The indicated value used to classify the scenario. If the agent supplied
    extraction comps (role 'central'), derive the median indicated value the same
    way build_packet does (structure-joined, auto-time, basement/garage credited).
    Otherwise fall back to triage's extraction indication when it flags a sales
    angle. Returns None when there is no below-EMV indication to weigh (the common
    fairly-assessed case)."""
    rates = dict(judgment.get("rates") or {})
    bsmt_psf = float(rates.get("bsmt_psf", 50.0))
    gar_psf = float(rates.get("gar_psf", 30.0))
    econ = float(rates.get("econ_psf_per_sf", 0.06))
    s_absf = float(subj_in.get("absf") or subj_in.get("living_area_sf") or 0)
    s_land = float(subj_in.get("land") or subj_in.get("emv_land") or 0)
    s_bsmt = float(subj_in.get("fin_bsmt_sf") or 0)
    s_gar = float(subj_in.get("garage_sf") or 0)

    central = [c for c in (judgment.get("comps") or []) if c.get("role") == "central"]
    if central and s_absf:
        assess_year = meta_in.get("assessment_year")
        eff_iso = analysis.get("assess_date") or (f"{assess_year}-01-02" if assess_year else None)
        inds = []
        for c in central:
            c = dict(c)
            _beacon_fill(c, (structure.get("comps") or {}).get(_norm_pid(c.get("pid"))) if c.get("pid") else None)
            if c.get("time_pct") is None:
                c["time_pct"] = _auto_time_pct(c.get("sale_date"), eff_iso, rates.get("time_pct_per_month", 0.25))
            m = extraction_comp_indication(c, s_absf, s_land, bsmt_psf, gar_psf, econ, s_bsmt, s_gar)
            if m:
                inds.append(m["indicated_value"])
        if inds:
            return _median(inds)

    # No agent comps — defer to triage's extraction indication, but only when it
    # actually flags a below-EMV sales angle (otherwise there is nothing to weigh).
    sci = analysis.get("sales_comparison_indicated") or {}
    if sci.get("extraction_angle") and sci.get("extraction_indicated_value") is not None:
        return float(sci["extraction_indicated_value"])
    return None


def main():
    p = argparse.ArgumentParser(description="Assemble a no-appeal findings report from a judgment.json")
    p.add_argument("judgment", help="Path to the agent-authored judgment.json (with a `finding` block)")
    p.add_argument("--analysis", default=None, help="Triage analysis.json (spine + ETR backfill)")
    p.add_argument("--beacon", default=None, help="beacon.json (Ramsey comp structure by pid)")
    p.add_argument("--collected", default=None, help="collected_data.json (Hennepin structure source)")
    p.add_argument("--output", default=None, help="Output HTML path")
    args = p.parse_args()

    judgment = json.loads(Path(args.judgment).read_text())
    data = build_finding(judgment, _maybe_load(args.analysis), _maybe_load(args.beacon),
                         _maybe_load(args.collected))
    html = generate_no_appeal_report(data)

    banner = (judgment.get("meta") or {}).get("banner")
    if banner:
        banner_html = (
            '<div style="background:#fff3cd;color:#7a5c00;text-align:center;padding:0.5rem 1rem;'
            'font-size:0.85rem;border-bottom:1px solid #e6d28a;font-family:Segoe UI,system-ui,sans-serif;">'
            f"{banner}</div>")
        html = html.replace("<body>", "<body>\n" + banner_html, 1)

    out = Path(args.output) if args.output else Path(args.judgment).parent / "finding.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    n = data["_numbers"]
    if n["scenario"] == "fairly_assessed":
        print(f"Scenario: fairly_assessed — concluded ${n['emv']:,} (EMV), reduction $0.")
    else:
        print(f"Scenario: below_savings_floor — indicated ${n['indicated']:,} "
              f"(${n['reduction']:,} / {n['reduction_pct']}% below EMV) but only "
              f"~${n['annual_savings']:,}/yr savings < ${n['min_savings']:,} floor.")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
