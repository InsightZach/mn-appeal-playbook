"""scripts/build_packet.py — the deterministic appeal-packet assembler.

This is the ONE per-property script. There is no bespoke render_<property>.py.

Given an agent-authored ``judgment.json`` — the *irreducible* judgment for one
property: which comps, their listing-verified condition/quality grades, the
confirmed adjustment rates, and the narrative beats — plus the deterministic
spine (subject + assessment history, optionally straight from ``analysis.json``),
``build_packet`` assembles the report-framework data dict and renders it through
``report.appeal_generator``:

  * the closed-sales table,
  * the adjustment schedule,
  * the above-grade extraction grid (land / finished basement / garage stripped),
  * the equalization grid + neighborhood building-$/SF trend,
  * the **derived** concluded value — the median of the central-tendency comps,
    computed here, never typed by the agent,
  * the reconciliation and worth-it economics.

The agent never hand-codes the dict and never picks the number. Narrative strings
in ``judgment.json`` are templated against the derived figures (``{concluded}``,
``{reduction}``, …) so the prose can never contradict the arithmetic.

    uv run python -m scripts.build_packet properties/fulham/judgment.json \
        [--analysis properties/fulham/analysis.json] [--output /tmp/packet.html]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from analysis.structure import resolve_structure
from report.appeal_generator import generate_appeal_report
from report.shared_components import extraction_comp_indication


# -- small deterministic helpers -----------------------------------------


def _median(vals: list[float]) -> float | None:
    s = sorted(vals)
    if not s:
        return None
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def _linfit(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Ordinary least-squares slope, intercept (pure Python — no numpy dep).
    Returns (0, mean) when x has no variance."""
    n = len(xs)
    if n == 0:
        return 0.0, 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        return 0.0, my
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
    return slope, my - slope * mx


def _round_k(v: float) -> int:
    """Round to the nearest $1,000 (the conclusion granularity)."""
    return int(round(v / 1000.0) * 1000)


def _norm_pid(pid) -> str:
    return re.sub(r"\D", "", str(pid or ""))


def _beacon_fill(rec: dict, b: dict | None) -> None:
    """Backfill a subject/comp dict's structure from its parsed Beacon card (in place).
    Maps the Beacon keys to the grid keys and uses the CONTRIBUTORY basement (finished
    + rec area) for fin_bsmt_sf — the valuation figure, not the API-reconciliation one.
    judgment-supplied values are never overwritten."""
    if not b:
        return
    mapping = (("absf", "absf"), ("contributory_basement_sf", "fin_bsmt_sf"),
               ("garage_sf", "garage_sf"), ("year_built", "year_built"))
    for src, dst in mapping:
        if rec.get(dst) is None and b.get(src) is not None:
            rec[dst] = b[src]


_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _parse_date(s: str | None) -> tuple[int, int] | None:
    """Parse 'YYYY-MM-DD' or 'Mon YYYY' (e.g. 'Aug 2024') -> (year, month). None if unparseable."""
    if not s:
        return None
    s = str(s).strip()
    m = re.match(r"(\d{4})-(\d{2})", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{4})", s)
    if m and m.group(1).lower() in _MONTHS:
        return int(m.group(2)), _MONTHS[m.group(1).lower()]
    return None


def _auto_time_pct(sale_date: str | None, effective_iso: str | None, rate_per_month: float) -> float:
    """Months between sale and the effective date × monthly rate (% of value). A sale
    BEFORE the effective date trends UP (positive); a sale after trends down."""
    sd, ed = _parse_date(sale_date), _parse_date(effective_iso)
    if not (sd and ed):
        return 0.0
    months = (ed[0] - sd[0]) * 12 + (ed[1] - sd[1])
    return round(months * float(rate_per_month), 1)


def _fmt_narrative(text: str, numbers: dict) -> str:
    """Template a narrative string against the derived numbers. Missing keys are
    left literal rather than raising, so a partial narrative still renders."""
    if not text:
        return ""
    try:
        return text.format(**numbers)
    except (KeyError, IndexError, ValueError):
        return text


# -- the assembler --------------------------------------------------------


def build_packet(judgment: dict, analysis: dict | None = None,
                 beacon: dict | None = None, collected: dict | None = None) -> dict:
    """Assemble the report-framework data dict from a vetted ``judgment`` and the
    deterministic spine. ``analysis`` (triage output) and ``beacon`` are optional
    enrichment — judgment may carry everything self-contained, or reference data
    that the spine fills. Returns the dict ready for ``generate_appeal_report``."""
    analysis = analysis or {}
    # County-routed structure: Beacon (Ramsey browser pull) and/or the Hennepin API's
    # above-grade SF already in collected_data — merged into one {subject, comps} map.
    structure = resolve_structure(beacon, collected)

    meta_in = dict(judgment.get("meta") or {})
    subj_in = dict(judgment.get("subject") or {})
    # The subject spine: judgment wins, analysis backfills (so a thin judgment.json
    # can lean on a real triage run).
    a_subj = (analysis.get("subject") or {})
    for k in ("address", "pid", "year_built", "emv_total", "emv_land",
              "emv_building", "lot_acres", "style"):
        if subj_in.get(k) is None and a_subj.get(k) is not None:
            subj_in[k] = a_subj[k]
    # Subject structure (ABSF / finished-basement / garage) from the resolver — parsed
    # or county-API-derived, never hand-typed. judgment still wins if set.
    _beacon_fill(subj_in, structure.get("subject"))

    rates = dict(judgment.get("rates") or {})
    bsmt_psf = float(rates.get("bsmt_psf", 50.0))
    gar_psf = float(rates.get("gar_psf", 30.0))
    econ = float(rates.get("econ_psf_per_sf", 0.06))

    subject_absf = float(subj_in.get("absf") or subj_in.get("living_area_sf") or 0)
    subject_land = float(subj_in.get("land") or subj_in.get("emv_land") or 0)
    subject_fin_bsmt = float(subj_in.get("fin_bsmt_sf") or 0)
    subject_garage = float(subj_in.get("garage_sf") or 0)
    emv = float(subj_in.get("emv_total") or 0)

    assess_year = meta_in.get("assessment_year") or (
        a_subj.get("assess_year") if isinstance(a_subj, dict) else None)
    effective_iso = (analysis.get("assess_date")
                     or (f"{assess_year}-01-02" if assess_year else None))

    # --- comps: join beacon structure by pid where judgment omits it ---
    comps = []
    for c in judgment.get("comps") or []:
        c = dict(c)
        pid = c.get("pid")
        _beacon_fill(c, (structure.get("comps") or {}).get(_norm_pid(pid)) if pid else None)
        # Auto time adjustment: comp may set time_pct explicitly; otherwise derive it
        # from the sale date and the effective date at the confirmed monthly rate —
        # a mechanical step the agent shouldn't hand-compute.
        if c.get("time_pct") is None:
            c["time_pct"] = _auto_time_pct(c.get("sale_date"), effective_iso,
                                           rates.get("time_pct_per_month", 0.25))
        comps.append(c)

    # Roles: central (drives the median), ceiling (capped upper bracket — in the
    # grid, not the median), context (shown in the 4.1 sales table only — e.g. a
    # too-small-to-be-a-size-comp sale kept for transparency), exclude (nowhere).
    included = [c for c in comps if c.get("role") != "exclude"]      # 4.1 sales table
    central = [c for c in included if c.get("role") == "central"]
    ceilings = [c for c in included if c.get("role") == "ceiling"]
    grid_comps = [c for c in included if c.get("role") in ("central", "ceiling")]

    # --- DERIVE the conclusion: median indicated value of the central comps ---
    def _ind(c):
        m = extraction_comp_indication(c, subject_absf, subject_land, bsmt_psf, gar_psf, econ,
                                       subject_fin_bsmt, subject_garage)
        return m["indicated_value"] if m else None

    central_inds = sorted(v for v in (_ind(c) for c in central) if v is not None)
    if not central_inds:
        raise ValueError(
            "build_packet: no central-tendency comps with indicated values — "
            "mark at least one comp role='central' in judgment.json")
    concluded = _round_k(_median(central_inds))
    concluded_mean = _round_k(sum(central_inds) / len(central_inds))
    ceiling_inds = [v for v in (_ind(c) for c in ceilings) if v is not None]
    ceiling_value = _round_k(max(ceiling_inds)) if ceiling_inds else None

    if emv <= 0:
        raise ValueError(
            "build_packet: subject emv_total is missing/zero — set it in judgment.json "
            "(or pass --analysis to backfill it). Every appeal needs the current EMV to "
            "compute the reduction and savings.")
    reduction = int(round(emv - concluded))
    reduction_pct = round(reduction / emv * 100, 1)
    tax_rate = float(meta_in.get("tax_rate") or 0.0)
    annual_savings = int(round(reduction * tax_rate)) if reduction > 0 else 0

    # --- equalization trend (assessed bldg $/SF vs SF over the peer scatter) ---
    eq_in = dict(judgment.get("equalization") or {})
    chart_peers = eq_in.get("chart_peers") or [
        {"sf": p.get("sf"), "bpsf": round((p.get("emv_building") or 0) / p["sf"]) if p.get("sf") else None,
         "label": p.get("address")}
        for p in (eq_in.get("peers") or [])
    ]
    chart_peers = [p for p in chart_peers if p.get("sf") and p.get("bpsf")]
    subject_bpsf = eq_in.get("subject_assessed_bpsf")
    if subject_bpsf is None and subject_absf and subj_in.get("emv_building"):
        subject_bpsf = round(subj_in["emv_building"] / subject_absf)
    eq_psf = eq_total = None
    slope = intercept = None
    if chart_peers and subject_absf:
        slope, intercept = _linfit([p["sf"] for p in chart_peers], [p["bpsf"] for p in chart_peers])
        eq_psf = round(intercept + slope * subject_absf)
        # A trend-implied equalization total is only emitted when the equalization
        # basis is clean enough to quote a dollar figure. When the peers' raw
        # building $/SF bundles their basement/garage (so applying it to the subject
        # would double-count against the sales conclusion that credits those), set
        # `suppress_indicated: true` and equalization stays DIRECTIONAL support — the
        # trend chart renders, but no dollar indication competes with the sales value.
        if not eq_in.get("suppress_indicated"):
            eq_total = _round_k(eq_psf * subject_absf + subject_land)
    peer_median_bpsf = round(_median([p["bpsf"] for p in chart_peers])) if chart_peers else None

    # --- numbers exposed to narrative templates (single source of truth) ---
    numbers = {
        "concluded": concluded, "concluded_mean": concluded_mean,
        "ceiling_value": ceiling_value, "emv": int(emv),
        "reduction": reduction, "reduction_pct": reduction_pct,
        "annual_savings": annual_savings, "tax_pct": round(tax_rate * 100, 2),
        "eq_psf": eq_psf, "eq_total": eq_total,
        "peer_median_bpsf": peer_median_bpsf, "subject_bpsf": subject_bpsf,
        "subject_absf": int(subject_absf), "subject_land": int(subject_land),
    }
    nar = judgment.get("narrative") or {}

    def N(key, default=""):
        return _fmt_narrative(nar.get(key, default), numbers)

    # --- assemble the framework dict ---
    data: dict = {
        "meta": {
            "assessment_year": meta_in.get("assessment_year"),
            "payable_year": meta_in.get("payable_year"),
            "brand": meta_in.get("brand", "Residential Property Tax Appeal"),
            "report_title": meta_in.get("report_title"),
            "assessment_date": meta_in.get("assessment_date"),
            "tax_rate": tax_rate,
        },
        "subject": {
            "address": subj_in.get("address"), "pid": subj_in.get("pid"),
            "year_built": subj_in.get("year_built"),
            "living_area_sf": int(subject_absf) or None,
            "lot_acres": subj_in.get("lot_acres"),
            "plat_name": subj_in.get("plat_name"),
            "style": subj_in.get("style"),
            "emv_total": int(emv) or None,
            "emv_land": int(subject_land) or None,
            "emv_building": subj_in.get("emv_building"),
        },
        "assessments": judgment.get("assessments") or [
            {"assess_year": h.get("assess_year"), "tax_year": (h.get("assess_year") or 0) + 1,
             "emv_land": h.get("emv_land"), "emv_building": h.get("emv_building"),
             "emv_total": h.get("emv_total")}
            for h in (analysis.get("emv_history") or [])
        ],
    }

    # Basis-for-appeal callouts
    basis = []
    if nar.get("subject_finding_body"):
        basis.append({"title": N("subject_finding_title"),
                      "body": N("subject_finding_body"), "color": "amber"})
    if nar.get("sales_finding_body"):
        basis.append({"title": N("sales_finding_title"),
                      "body": N("sales_finding_body"), "color": "amber"})
    if basis:
        data["basis_for_appeal"] = basis

    # Section 4 — Sales Comparison
    data["sales_subtitle"] = N("sales_subtitle")
    data["sales_intro"] = N("sales_intro")
    data["recent_sales"] = [
        {"address": c.get("address"), "sale_date": c.get("sale_date"),
         "sale_price": c.get("sale_price"), "sf": c.get("absf"),
         "year_built": c.get("year_built"), "lot_acres": c.get("lot_acres")}
        for c in included
    ]
    data["adjustment_schedule"] = judgment.get("adjustment_schedule") or _default_schedule(
        bsmt_psf, gar_psf, econ, rates)
    data["adjustment_schedule_intro"] = N(
        "adjustment_schedule_intro",
        "Adjustments are applied on an above-grade basis (below). Every rate is "
        "derived from this market or the county's assessment records, not a table.")
    data["extraction_grid"] = {
        "comps": [
            {"address": c.get("address"),
             "descriptor": f"{c.get('year_built')} · {c.get('descriptor')}"
                           if c.get("descriptor") else c.get("year_built"),
             "sale_price": c.get("sale_price"), "land": c.get("land"),
             "absf": c.get("absf"), "fin_bsmt_sf": c.get("fin_bsmt_sf") or 0,
             "garage_sf": c.get("garage_sf") or 0, "time_pct": c.get("time_pct") or 0,
             "quality_pct": c.get("quality_pct") or 0, "condition_pct": c.get("condition_pct") or 0}
            for c in grid_comps
        ],
        "subject_absf": subject_absf, "subject_land": subject_land,
        "bsmt_psf": bsmt_psf, "gar_psf": gar_psf, "econ_psf_per_sf": econ,
        "subject_fin_bsmt_sf": subject_fin_bsmt, "subject_garage_sf": subject_garage,
    }
    data["sales_reconciliation"] = N("sales_reconciliation")
    data["sales_indicated_value"] = concluded

    # Section 5 — Equalization
    if eq_in.get("peers"):
        data["equalization_subtitle"] = N("equalization_subtitle",
                                           "Cross-check against neighborhood assessment records.")
        data["equalization_grid_intro"] = N("equalization_grid_intro") or eq_in.get("intro")
        data["equalization_grid"] = eq_in["peers"]
        if eq_in.get("land_observation"):
            data["land_value_observation"] = N("equalization.land_observation") or eq_in["land_observation"]
        if eq_in.get("building_observation"):
            data["building_value_observation"] = {"body": _fmt_narrative(eq_in["building_observation"], numbers)}
        if chart_peers and slope is not None:
            data["building_emv_chart"] = {
                "data": [{"x": p["sf"], "y": p["bpsf"], "label": f"{p.get('label')} (${p['bpsf']}/SF)"}
                         for p in chart_peers],
                "subject_xy": {"x": subject_absf, "y": subject_bpsf},
                "trends": [{"slope": slope, "intercept": intercept,
                            "label": "Neighborhood trend", "color": "#d7b971"}],
                "caption": _fmt_narrative(eq_in.get("chart_caption", ""), numbers),
            }
        if eq_total is not None:
            data["equalization_indicated_value"] = eq_total
            data["equalization_indicated_note"] = _fmt_narrative(
                eq_in.get("indicated_note", ""), numbers)

    # Land $/SF regression chart (from triage's land_regression) — an independent
    # cross-check on the land line. Judgment can override with its own land_psf_chart.
    if "land_psf_chart" not in data:
        lr = analysis.get("land_regression") or {}
        if lr.get("applicable") and lr.get("chart"):
            data["land_psf_chart"] = lr["chart"]

    # Section 7 — Reconciliation + conclusion
    recon = [{"method": "Sales comparison (above-grade)", "value": concluded,
              "role": "Primary — supported market value; governs the request"}]
    if eq_total is not None:
        recon.append({"method": "Equalization (building to neighborhood trend)", "value": eq_total,
                      "role": "Support — building assessed above its neighborhood peers"})
    data["reconciliation"] = recon
    data["conclusion"] = {
        "concluded_value": concluded,
        "assessment_date": meta_in.get("assessment_date"),
        "narrative": N("conclusion"),
    }

    data["_numbers"] = numbers   # surfaced for callers/tests; ignored by the generator
    return data


def _default_schedule(bsmt_psf, gar_psf, econ, rates) -> list[dict]:
    """The standard above-grade adjustment schedule (rates confirmed in judgment)."""
    return [
        {"adjustment": "Time", "rate": rates.get("time_label", "+0.25% / month to the effective date"),
         "basis": "≈3%/yr market trend"},
        {"adjustment": "Size (economy of scale)", "rate": f"~${econ*100:.0f}/SF per 100 SF above-grade",
         "basis": "Smaller homes sell for more per foot — derived from the comp set"},
        {"adjustment": "Quality (construction grade)", "rate": rates.get("quality_label", "±5–8% per grade step"),
         "basis": "Construction grade vs. the comps"},
        {"adjustment": "Condition", "rate": rates.get("condition_label",
                                                       "0% original · −10% updated · −25% renovated (cap)"),
         "basis": "Grade steps. A fully renovated comp is capped at −25% (the credible max) and carried at "
                  "reduced weight as an upper bracket"},
        {"adjustment": "Finished basement", "rate": f"−${bsmt_psf:,.0f}/SF",
         "basis": "Contributory value; removed from each comp"},
        {"adjustment": "Garage", "rate": f"−${gar_psf:,.0f}/SF",
         "basis": "Contributory value; removed from each comp"},
        {"adjustment": "Land", "rate": "county assessed land",
         "basis": "Each comp's land removed, the subject's added back"},
    ]


def _maybe_load(path: str | None) -> dict | None:
    if not path:
        return None
    return json.loads(Path(path).read_text())


def main():
    p = argparse.ArgumentParser(description="Assemble an appeal packet from a judgment.json")
    p.add_argument("judgment", help="Path to the agent-authored judgment.json")
    p.add_argument("--analysis", default=None, help="Triage analysis.json (spine backfill)")
    p.add_argument("--beacon", default=None, help="beacon.json (comp structure by pid)")
    p.add_argument("--collected", default=None,
                   help="collected_data.json — the structure source for Hennepin (above-grade SF); "
                        "Ramsey uses --beacon instead")
    p.add_argument("--output", default=None, help="Output HTML path")
    args = p.parse_args()

    judgment = json.loads(Path(args.judgment).read_text())
    data = build_packet(judgment, _maybe_load(args.analysis),
                        _maybe_load(args.beacon), _maybe_load(args.collected))
    html = generate_appeal_report(data)

    banner = (judgment.get("meta") or {}).get("banner")
    if banner:
        banner_html = (
            '<div style="background:#fff3cd;color:#7a5c00;text-align:center;padding:0.5rem 1rem;'
            'font-size:0.85rem;border-bottom:1px solid #e6d28a;font-family:Segoe UI,system-ui,sans-serif;">'
            f"{banner}</div>")
        html = html.replace("<body>", "<body>\n" + banner_html, 1)

    out = Path(args.output) if args.output else Path(args.judgment).parent / "packet.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    n = data["_numbers"]
    print(f"Concluded ${n['concluded']:,} (median of central comps; mean ${n['concluded_mean']:,}) "
          f"— reduction ${n['reduction']:,} ({n['reduction_pct']}%), ~${n['annual_savings']:,}/yr")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
