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

# Effective tax rate fallback when no prior-year tax is available from the
# pipeline (Ramsey assessment records carry total_tax=null). Metro residential
# ETRs run ~1.0-1.3% of EMV; 1.15% is a documented county-default placeholder
# so the worth-it threshold can be evaluated rather than skipped. See docs/09.
DEFAULT_ETR = 0.0115


def _years_between(start_iso: str | None, end_iso: str | None) -> float | None:
    """Whole-and-fractional years between two ISO dates (None-safe)."""
    if not start_iso or not end_iso:
        return None
    from datetime import date as _d
    try:
        s = _d.fromisoformat(str(start_iso)[:10])
        e = _d.fromisoformat(str(end_iso)[:10])
    except ValueError:
        return None
    return round((e - s).days / 365.25, 1)


# Size band for "comparable" — comps/sales within ±30% of the subject's SF.
# Mirrors the killer-comp size gate and methodology.md's ±30% rule, so every
# median/percentile that feeds a conclusion is taken over a like-sized peer set.
SF_BAND = 0.30


def _in_sf_band(value_sf: float | None, subject_sf: float | None) -> bool:
    """True when value_sf is within ±SF_BAND of subject_sf (or SF is unknown —
    an unknown-SF record is not excluded by the band, only by other screens)."""
    if not subject_sf or not value_sf:
        return False
    return (1 - SF_BAND) * subject_sf <= value_sf <= (1 + SF_BAND) * subject_sf


def _psf_points(sales: list[dict]) -> list[dict]:
    pts = []
    for s in sales:
        price, sf = s.get("sale_price"), s.get("sf")
        if price and sf:
            pts.append({**s, "psf": price / sf, "date": s.get("sale_date")})
    return pts


def _quarantine_corrupt_sales(
    sales: list[dict], subject_pid: str | None
) -> tuple[list[dict], list[dict]]:
    """Drop records whose $/SF is absurd relative to the neighborhood median — a
    corrupt/bulk-deed record (e.g. a $7.2M, $3,713/SF sale on a $301K-EMV parcel)
    sitting inside the size band silently poisons every median and regression.

    A sale is quarantined when its $/SF is > 4× or < 0.25× the median $/SF of the
    other sales. The subject's own record is never quarantined (own-sale logic
    owns that judgment). Only runs when there are enough sales (≥6) for a stable
    median; otherwise the set is returned untouched. Disclosure, not deletion:
    the quarantined records are returned for the judgment layer to see.
    """
    psf_pts = [
        (s, s["sale_price"] / s["sf"])
        for s in sales
        if s.get("sale_price") and s.get("sf") and s.get("pid") != subject_pid
    ]
    if len(psf_pts) < 6:
        return list(sales), []
    psfs = sorted(p for _, p in psf_pts)
    median_psf = psfs[len(psfs) // 2]
    if median_psf <= 0:
        return list(sales), []
    hi, lo = 4.0 * median_psf, 0.25 * median_psf
    corrupt_ids = set()
    quarantined = []
    for s, psf in psf_pts:
        if psf > hi or psf < lo:
            corrupt_ids.add(id(s))
            quarantined.append({
                "pid": s.get("pid"),
                "address": s.get("address"),
                "sale_price": s.get("sale_price"),
                "sf": s.get("sf"),
                "psf": round(psf),
                "neighborhood_median_psf": round(median_psf),
                "reason": "sale $/SF is >4× or <0.25× the neighborhood median — "
                          "likely a corrupt/bulk-deed record, excluded from all "
                          "medians and regressions",
            })
    clean = [s for s in sales if id(s) not in corrupt_ids]
    return clean, quarantined


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

    # Corrupt-record quarantine FIRST — a bulk-deed/corrupt $/SF record inside the
    # size band poisons every downstream median, regression, and percentile. Drop
    # it before any of them run; the subject's own record is never quarantined.
    sales, quarantined_sales = _quarantine_corrupt_sales(sales, subject.get("pid"))

    # Arm's-length screen (docs/10). No good_for_state_study flag on Ramsey
    # records, so flag a sale priced < ~0.80x its own EMV as a likely-distressed
    # outlier — the sanctioned proxy. This is disclosure, not deletion; the
    # judgment layer decides whether to drop it from the reconciliation.
    distressed_sales = []
    for s in sales:
        sp, oemv = s.get("sale_price"), s.get("emv_total")
        if sp and oemv and sp / oemv < 0.80:
            distressed_sales.append({
                "pid": s.get("pid"),
                "address": s.get("address"),
                "sale_price": sp,
                "own_emv": oemv,
                "sale_to_own_emv_ratio": round(sp / oemv, 2),
            })

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

    # Subject's own sale — strongest possible evidence. Prefer a record in the
    # sales window (carries full sale detail), but fall back to the subject's
    # own last_sale_price/last_sale_date so an own sale that predates the comp
    # window is never silently dropped — exactly the case where it matters most.
    own_sale = next((s for s in sales if s.get("pid") == subject["pid"]), None)
    own_sale_price = None
    own_sale_date = None
    if own_sale and own_sale.get("sale_price"):
        own_sale_price = own_sale["sale_price"]
        own_sale_date = own_sale.get("sale_date")
    elif subject.get("last_sale_price"):
        own_sale_price = subject["last_sale_price"]
        own_sale_date = subject.get("last_sale_date")

    own_sale_finding = None
    if own_sale_price:
        d = own_sale_price - current["emv_total"]
        yrs_before = _years_between(own_sale_date, assess_date)
        own_sale_finding = {
            "sale_price": own_sale_price,
            "sale_date": own_sale_date,
            "delta_from_emv": d,
            "delta_pct": round(d / current["emv_total"] * 100, 1),
            "years_before_effective": yrs_before,
        }
        # A raw delta vs current EMV from a sale older than the ~4yr horizon is
        # non-evidentiary (triage-judgment.md item 1). Relabel it so the stale,
        # meaningless number cannot leak into a finding.
        if yrs_before is not None and yrs_before > 4:
            own_sale_finding["delta_pct_meaningless_stale"] = True
            own_sale_finding["delta_pct_note"] = (
                "raw delta vs current EMV is meaningless for a sale beyond the "
                "~4yr horizon — corroborating direction only, not a finding"
            )
    elif subject.get("last_sale_date"):
        # A subject sale exists but carries no price — do NOT emit null (which
        # reads as 'no own sale'). Flag the missing price so the dangling record
        # triage-judgment.md item 1 says to always address is visible, with an
        # instruction to recover the price downstream.
        own_sale_finding = {
            "price_missing": True,
            "sale_date": subject.get("last_sale_date"),
            "note": "subject sale present but price missing — recover price "
                    "downstream (eCRV / listing); if it post-dates the Jan 2 "
                    "effective date it is corroborating only for the current year",
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

    # Pocket corroboration. A lone comp that sold below its own EMV signals
    # over-assessment of the SUBJECT only if the surrounding size-matched pocket
    # is also assessed high; if the size-matched sales as a group sold at/above
    # their own EMV (pocket median ratio ≥ ~0.95), one low comp is an idiosyncratic
    # /distressed sale, not a subject angle. Compute the pocket's median
    # sale-to-own-EMV ratio over arm's-length sales within ±30% SF.
    pocket_ratios = sorted(
        s["sale_price"] / s["emv_total"]
        for s in kc_sales
        if s.get("sale_price") and s.get("emv_total")
        and _in_sf_band(s.get("sf"), sf)
    )
    pocket_median_own_emv_ratio = (
        pocket_ratios[len(pocket_ratios) // 2] if len(pocket_ratios) >= 3 else None
    )

    # Sales regression: subject plat / other plats / combined, IQR-cleaned.
    # Convergence measures agreement BETWEEN models — it is only meaningful with
    # >=2 DISTINCT models. When there are no same-plat sales, other_plats and
    # combined are built from the same input set; that is a single model, not a
    # convergence, and a trivially-tight spread (0%) must not satisfy the
    # no-angle trigger. Collapse to one model and label it single_model.
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

    # Are other_plats and combined drawn from the same input set? They are only
    # distinct models when a genuinely SEPARATE subject_plat model was actually
    # built (len(same) >= 5). When there are no same-plat sales — OR fewer than 5,
    # so no subject_plat model exists — other_plats is drawn from nearly the same
    # set as combined; that is a single model, not a convergence, and a
    # trivially-tight spread must not satisfy the no-angle trigger.
    distinct_models = len([k for k in models if k != "combined"]) >= 1 and len(models) >= 2
    if len(same) < 5 and len(models) > 1:
        # No subject_plat model was built: other_plats ≈ combined. Keep one model.
        models = {"combined": models["combined"]} if "combined" in models else models
        distinct_models = False

    convergence = multi_model_convergence(models, assess_date, sf) if (models and sf) else None
    if convergence:
        # Convergence measures agreement between MODELS; on its own it says
        # nothing about agreement with EMV. Surface the gap vs EMV so the
        # verdict can tell "tight at EMV" (no angle) from "tight below EMV"
        # (appeal angle).
        convergence["convergence_gap_vs_emv"] = round(
            convergence["central"] - current["emv_total"]
        )
        if not distinct_models:
            # A single model cannot "converge"; relabel so it can't trigger
            # the no-angle path, and ensure the directional-screen label is set
            # so the central figure can't be mistaken for a defensible ask.
            convergence["verdict"] = "single_model"
            convergence.setdefault(
                "central_label",
                "single regression model over all sizes — directional screen only, not a "
                "reconciled sales value; reconcile size-matched comps per appeal-packet.md",
            )
            # The dollar central is self-disclaimed (directional only). Keep the
            # qualitative direction (above/below EMV) but rename the gap field so
            # its non-reconciled status is unmistakable, and DO NOT let the dollar
            # central or gap feed any reason string or illustrative_reduction.
            gap = convergence.pop("convergence_gap_vs_emv", None)
            if gap is not None:
                convergence["all_sizes_regression_gap_directional"] = gap
                convergence["direction_vs_emv"] = (
                    "below EMV" if gap < 0 else "above EMV"
                )
            # For a single model do NOT leave a precise dollar `central` that a
            # less-careful reader could quote as a reconciled ask. Rename it so
            # its directional-only, non-adoptable status is unmistakable (the
            # gap above is already labelled directional).
            if "central" in convergence:
                convergence["central_directional_only_do_not_quote"] = convergence.pop(
                    "central"
                )

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
        # Size-band the building $/SF peer set (±30% SF) so the percentile, median,
        # and p80 reflect like-sized homes — an all-sizes building percentile can
        # read 81st in the full set but mid-pack among size-matched peers. Fall
        # back to the full set only when too few size-matched comps remain.
        bpsf_banded = sorted(
            p["bldg"] / p["sf"] for p in bldg_pts
            if p.get("sf") and p.get("bldg") and _in_sf_band(p.get("sf"), sf)
        )
        bpsf_all = sorted(p["bldg"] / p["sf"] for p in bldg_pts if p.get("sf") and p.get("bldg"))
        if len(bpsf_banded) >= 5:
            comp_bpsf = bpsf_banded
            building_percentile_basis = "size_matched_within_30pct"
        else:
            comp_bpsf = bpsf_all
            building_percentile_basis = "all_sizes_fallback"
        comp_lpsf = sorted(p["land"] / p["lot_sf"] for p in land_pts if p.get("lot_sf") and p.get("land"))
        subj_bpsf = (current.get("emv_building") or 0) / sf
        subj_lpsf = (current.get("emv_land") or 0) / lot_sf
        bpsf_pctile = round(sum(1 for v in comp_bpsf if v < subj_bpsf) / len(comp_bpsf) * 100)
        lpsf_pctile = round(sum(1 for v in comp_lpsf if v < subj_lpsf) / len(comp_lpsf) * 100)
        median_bpsf = comp_bpsf[len(comp_bpsf) // 2]
        median_lpsf = comp_lpsf[len(comp_lpsf) // 2]

        def _pctile(sorted_vals: list[float], q: float) -> float:
            """Nearest-rank percentile (q in 0..1)."""
            if not sorted_vals:
                return 0.0
            idx = min(len(sorted_vals) - 1, max(0, int(round(q * (len(sorted_vals) - 1)))))
            return sorted_vals[idx]

        # methodology.md says equalize to the p75-p90 BAND, not the median. Pull
        # the subject's $/SF down to the p80 peer percentile only where the
        # subject sits ABOVE it (an equalization reduction exists only when the
        # subject is above the band), else leave that line at the subject's $/SF.
        p80_bpsf = _pctile(comp_bpsf, 0.80)
        p80_lpsf = _pctile(comp_lpsf, 0.80)
        eq_bpsf = min(subj_bpsf, p80_bpsf)
        eq_lpsf = min(subj_lpsf, p80_lpsf)

        # Lot-size-outlier guard. Land $/SF is strongly non-linear with lot size;
        # applying a neighborhood-median (or trend) land $/SF to a subject whose
        # lot is far outside the comp lot distribution inflates the land term
        # well past the county's own land EMV (e.g. a 5.48-ac subject getting
        # median_lpsf × 238,709 SF >> actual emv_land). When the subject's lot is
        # outside the ~10th-90th percentile of the comp lot distribution, do NOT
        # apply a flat land $/SF to the subject's lot SF — cap the land
        # contribution at the county's own emv_land and flag the land term
        # unreliable, so a falsely-inflated implied total can't emit a
        # "no inequity / at or above EMV" reason on an outlier-lot parcel.
        comp_lot_sf = sorted(
            (c.get("lot_acres") or 0) * SQFT_PER_ACRE
            for c in comps if c.get("lot_acres")
        )
        lot_outlier = False
        if len(comp_lot_sf) >= 5:
            lot_lo, lot_hi = _pctile(comp_lot_sf, 0.10), _pctile(comp_lot_sf, 0.90)
            lot_outlier = lot_sf < lot_lo or lot_sf > lot_hi
        subj_emv_land = current.get("emv_land") or 0

        def _land_term(flat_land_value: float) -> float:
            """Land contribution to an implied total. For an outlier lot the flat
            (median or trend) land $/SF is meaningless against the subject's lot
            SF — extrapolation can both massively inflate AND go negative — so use
            the county's own land EMV instead of the extrapolated figure."""
            if lot_outlier and subj_emv_land:
                return subj_emv_land
            return flat_land_value

        median_implied = round(median_bpsf * sf + _land_term(median_lpsf * lot_sf))
        equalization = {
            "subject_building_psf": round(subj_bpsf, 1),
            "comp_median_building_psf": round(median_bpsf, 1),
            "comp_p80_building_psf": round(p80_bpsf, 1),
            "building_psf_percentile": bpsf_pctile,
            "building_percentile_basis": building_percentile_basis,
            "subject_land_psf": round(subj_lpsf, 1),
            "comp_median_land_psf": round(median_lpsf, 1),
            "comp_p80_land_psf": round(p80_lpsf, 1),
            "land_psf_percentile": lpsf_pctile,
            # On an outlier lot the land $/SF percentile is a SIZE artifact, not
            # inequity — a big lot reads low $/SF, a small lot high — so it must
            # not contribute to an equalization angle (kept here for transparency).
            "land_psf_percentile_size_artifact": lot_outlier,
            "median_implied_total": median_implied,
            "median_gap_vs_emv": median_implied - current["emv_total"],
            # Realistic p75-p90-band equalization (the methodology reference
            # point), distinct from the median which usually overstates the gap.
            "equalized_total_p80": round(eq_bpsf * sf + _land_term(eq_lpsf * lot_sf)),
            # True when the subject's building and land $/SF both sit at or below
            # the p80 band — equalizing to p80 reproduces EMV (the band-floor
            # clamp), so equalized_total_p80 == EMV means "no reduction
            # available", NOT a genuine reduced indicated value.
            "equalization_neutral": bool(subj_bpsf <= p80_bpsf and subj_lpsf <= p80_lpsf),
            "lot_outlier": lot_outlier,
            "land_term_unreliable": lot_outlier,
            "land_trend": land_trend,
            "building_trend": bldg_trend,
        }
        if land_trend["r2"] >= 0.3 and bldg_trend["r2"] >= 0.3:
            _, land_pred = apply_trend_to_subject(land_trend, lot_sf=lot_sf)
            _, bldg_pred = apply_trend_to_subject(bldg_trend, sf=sf)
            reg_total = round(bldg_pred + _land_term(land_pred))
            equalization["regression_implied_total"] = reg_total
            equalization["regression_gap_vs_emv"] = round(reg_total - current["emv_total"])

    # Verdict (methodology.md Phase 5 thresholds, minus condition which needs
    # client input, minus building-inequity which needs Beacon ABSF).
    #
    # Reason ordering: the defensible standalone signals (EMV history, own sale,
    # equalization) lead; the killer-comp reason follows and discloses its basis,
    # because a comp delta vs the SUBJECT's EMV is only an over-assessment signal
    # when the killer_comp gate (own-EMV ratio / implied value) confirms it.
    reasons, verdict = [], "no_angle"
    if len(history) > 1 and history[0]["yoy_change"] is not None and history[0]["yoy_change"] < 0:
        # A county cut already applied is a CONTRA signal — it weakens the case
        # (the county has already moved toward the owner), not a reason to appeal.
        # Tag it as a caveat so the reason-coherence filter strips it under an
        # appeal_angle verdict rather than letting it headline as reason #1 over a
        # contradictory killer-comp signal.
        reasons.append(f"{history[0]['assess_year']} EMV already declined "
                       f"${-history[0]['yoy_change']:,.0f} ({history[0]['yoy_pct']}%) from prior year "
                       f"— county already cut, weakens the case")
    if own_sale_finding and own_sale_finding.get("delta_pct") is not None and own_sale_finding["delta_pct"] < -5:
        # Gate the own-sale verdict on age (methodology.md "Own-sale relevance
        # horizon" / triage-judgment.md). years_before_effective is already
        # computed above; use it so a stale sale can't headline as the #1 live
        # signal with a raw delta the horizon rule says is non-governing.
        # Own-sale relevance horizon (methodology.md) — numeric, non-overlapping
        # bands so a sale exactly on a boundary has one unambiguous treatment:
        #   ≤ 2.0 yr → governing (unadjusted)
        #   2.0 < x ≤ 3.5 yr → time-trend to the effective date, govern on trended
        #   3.5 < x ≤ 4.0 yr → corroborating only
        #   > 4.0 yr → non-evidentiary (raw delta already flagged meaningless above)
        yrs = own_sale_finding.get("years_before_effective")
        if yrs is None or yrs <= 2:
            # Within ~2yr: unadjusted own sale is governing.
            verdict = "appeal_angle"
            reasons.append(f"Subject itself sold {own_sale_finding['delta_pct']}% below current EMV "
                           f"(${own_sale_finding['sale_price']:,.0f} on {own_sale_finding['sale_date']})")
        elif yrs <= 3.5:
            # 2-3.5yr: time-trend the sale to the effective date at the default
            # +0.25%/month rate and govern on the trended figure, not the raw delta.
            trended = round(own_sale_finding["sale_price"] * (1 + 0.0025 * 12 * yrs))
            trended_delta_pct = round((trended - current["emv_total"]) / current["emv_total"] * 100, 1)
            own_sale_finding["trended_sale_price"] = trended
            own_sale_finding["trended_delta_pct"] = trended_delta_pct
            if trended_delta_pct < -5:
                verdict = "appeal_angle"
            reasons.append(f"Subject sold ${own_sale_finding['sale_price']:,.0f} on "
                           f"{own_sale_finding['sale_date']} ({yrs} yrs stale); time-trended to "
                           f"~${trended:,.0f} ({trended_delta_pct}% vs EMV)")
        else:
            # Beyond ~3-4yr: corroborating only — do NOT let the own sale flip the
            # verdict on its own, and do not report the raw delta as a finding.
            reasons.append(f"Subject sold ${own_sale_finding['sale_price']:,.0f} on "
                           f"{own_sale_finding['sale_date']} ({yrs} yrs stale) — corroborating only, "
                           f"not governing")
    if equalization:
        bldg_pct = equalization["building_psf_percentile"]
        # On an outlier lot the land $/SF percentile is a size artifact, not
        # inequity — exclude it from angle decisions (the raw value stays in the
        # dict for transparency).
        land_pct = (
            0 if equalization.get("land_psf_percentile_size_artifact")
            else equalization["land_psf_percentile"]
        )
        gap = equalization.get("regression_gap_vs_emv")
        if gap is not None and gap < -30000:
            verdict = "appeal_angle"
            reasons.append(f"Equalization regression implies ${-gap:,.0f} below EMV")
        elif bldg_pct >= 80 and land_pct >= 80:
            verdict = "appeal_angle"
            reasons.append(
                f"Subject assessed above {min(bldg_pct, land_pct)}% "
                f"of comps on BOTH building $/SF (${equalization['subject_building_psf']}/SF vs ${equalization['comp_p80_building_psf']} at p80) "
                f"and land $/SF (${equalization['subject_land_psf']} vs ${equalization['comp_p80_land_psf']} at p80); "
                f"equalizing to the p80 band implies ~${equalization['equalized_total_p80']:,.0f}")
        elif bldg_pct >= 95 or land_pct >= 95:
            # An extreme single-axis percentile is a standalone equalization
            # angle (a 95th-percentile building $/SF is size-robust inequity);
            # it leads even when the other axis is unremarkable.
            verdict = "appeal_angle"
            if bldg_pct >= land_pct:
                reasons.append(
                    f"Subject building $/SF at {bldg_pct}th percentile of comps "
                    f"(${equalization['subject_building_psf']}/SF vs ${equalization['comp_p80_building_psf']} at p80) — standalone equalization angle")
            else:
                reasons.append(
                    f"Subject land $/SF at {equalization['land_psf_percentile']}th percentile of comps "
                    f"(${equalization['subject_land_psf']} vs ${equalization['comp_p80_land_psf']} at p80) — standalone equalization angle")
        elif bldg_pct >= 80 or land_pct >= 80:
            if verdict == "no_angle":
                verdict = "borderline"
            land_note = (" (land $/SF excluded — size artifact on an outlier lot)"
                         if equalization.get("land_psf_percentile_size_artifact") else "")
            reasons.append(
                f"Equalization: building $/SF at {bldg_pct}th percentile, "
                f"land $/SF at {equalization['land_psf_percentile']}th percentile of comps{land_note}")
        else:
            # No inequity threshold tripped. When BOTH implied totals land at or
            # above EMV, that is an explicit no-inequity confirmation (assessment
            # at or below peer level) — surface it rather than staying silent.
            reg_gap = equalization.get("regression_gap_vs_emv")
            med_gap = equalization.get("median_gap_vs_emv")
            both_at_or_above = (
                (med_gap is not None and med_gap >= 0)
                and (reg_gap is None or reg_gap >= 0)
            )
            # The "at or above EMV / no inequity" reason leans on the implied
            # totals, whose land term is meaningless for an outlier lot. When the
            # land term is unreliable, suppress this reason rather than emit a
            # flat "assessment at or below peer level" falsehood on a parcel whose
            # building line may still be over-assessed.
            if both_at_or_above and not equalization.get("land_term_unreliable"):
                reasons.append(
                    "Equalization shows no building/land inequity — median (and regression) "
                    "implied totals sit at or above EMV (assessment at or below peer level)")
    if killer and killer.get("verdict") == "supports_appeal":
        ratio = killer.get("comp_own_emv_ratio")
        ratio_str = f"{ratio:.2f}x its own EMV" if ratio is not None else "below its own EMV"
        # A lone low comp (sold below its own EMV) needs the size-matched pocket to
        # corroborate: if the pocket median sale/own-EMV ratio is ≥ ~0.95 (the
        # county assessed the pocket correctly), the single low comp is
        # idiosyncratic and must NOT alone flip the whole parcel to appeal_angle.
        lone_low_comp = ratio is not None and ratio < 0.90
        pocket_uncorroborated = (
            pocket_median_own_emv_ratio is not None
            and pocket_median_own_emv_ratio >= 0.95
        )
        if lone_low_comp and pocket_uncorroborated:
            if verdict == "no_angle":
                verdict = "borderline"
            reasons.append(
                f"Best comp {killer['comp'].get('address', killer['comp'].get('pid', '?'))} sold ${killer['comp'].get('sale_price', 0):,.0f} "
                f"= {ratio_str}, but the size-matched pocket sold at ~{pocket_median_own_emv_ratio:.2f}x its own EMV "
                f"— lone low comp not corroborated by the pocket; verify before relying on it")
        else:
            verdict = "appeal_angle"
            implied = killer.get("implied_subject_value")
            if implied is not None:
                reasons.append(
                    f"Best comp {killer['comp'].get('address', killer['comp'].get('pid', '?'))} sold ${killer['comp'].get('sale_price', 0):,.0f} "
                    f"= {ratio_str}; its $/SF implies ~${implied:,.0f} vs ${current['emv_total']:,.0f} EMV")
            else:
                reasons.append(
                    f"Best comp {killer['comp'].get('address', killer['comp'].get('pid', '?'))} sold ${killer['comp'].get('sale_price', 0):,.0f} "
                    f"= {ratio_str} ({killer['delta_pct']:.1f}% vs subject EMV)")

    # Convergence below EMV is an appeal signal, not a no-angle one. Only treat
    # tight convergence as no-angle when it lands within ~±5% of EMV; a central
    # value materially below EMV (and built from >=2 distinct models) escalates.
    conv_gap = convergence.get("convergence_gap_vs_emv") if convergence else None
    conv_tight = bool(convergence and convergence["verdict"] == "tight")
    conv_below_emv = (
        conv_tight
        and conv_gap is not None
        and current["emv_total"]
        and (conv_gap / current["emv_total"]) < -0.05
    )
    if conv_below_emv:
        if verdict == "no_angle":
            verdict = "appeal_angle"
        reasons.append(f"Sales models converge ${-conv_gap:,.0f} below EMV")

    if verdict == "no_angle":
        conv_at_emv = (
            conv_tight
            and conv_gap is not None
            and current["emv_total"]
            and abs(conv_gap / current["emv_total"]) <= 0.05
        )
        # Affirmative no_angle paths — an honest "no" should be cheap to produce
        # and must not require multi-model convergence (structurally unavailable
        # for a single-plat neighborhood). Any one of these confirms no angle.
        killer_confirms = killer and killer.get("verdict") in ("kills_appeal", "confirms_fair")
        eq_confirms = bool(
            equalization
            and equalization["building_psf_percentile"] <= 40
            and (
                (equalization.get("median_implied_total") is not None
                 and equalization["median_implied_total"] >= current["emv_total"])
                or (equalization.get("regression_implied_total") is not None
                    and equalization["regression_implied_total"] >= current["emv_total"])
            )
        )
        # Comp-sales median $/SF × subject SF at-or-above EMV. Restrict to
        # size-matched sales (±30% SF) — an all-sizes median extrapolates
        # small-home $/SF onto a large subject (or the reverse), the same error
        # the killer-comp size gate blocks. Fall back to all sales only if too few
        # size-matched remain to form a median.
        sales_confirms = False
        if sf and pts:
            banded_psf = sorted(p["psf"] for p in pts if _in_sf_band(p.get("sf"), sf))
            psf_pool = banded_psf if len(banded_psf) >= 3 else sorted(p["psf"] for p in pts)
            comp_median_psf = psf_pool[len(psf_pool) // 2]
            if comp_median_psf * sf >= current["emv_total"]:
                sales_confirms = True
        if killer and killer.get("verdict") == "kills_appeal" and conv_at_emv:
            reasons.append("Best comp at EMV and sales models converge near EMV — no angle")
        elif killer_confirms:
            reasons.append("Best comp brackets the subject at or above EMV — no angle")
        elif eq_confirms:
            reasons.append("Subject building $/SF at/below peer level and equalization implies a "
                           "total at or above EMV — no angle")
        elif sales_confirms:
            reasons.append("Comparable-sales median $/SF applied to subject SF lands at or above EMV — no angle")
        elif not reasons:
            verdict = "borderline"
            reasons.append("No single threshold tripped; needs judgment review")

    # Reason-coherence filter. The verdict is now final; the reasons list was
    # assembled incrementally and can contain a no-angle-signal line (e.g. an
    # "at or below peer level / no inequity" equalization reason emitted earlier)
    # that contradicts an appeal_angle verdict reached by a different signal.
    # A reviewer who sees reasons that contradict the verdict distrusts the whole
    # output. Drop no-angle-signal reasons when the verdict is appeal_angle (and
    # the reverse when it is no_angle), so the reasons always agree with the call.
    _NO_ANGLE_MARKERS = (
        "no angle",
        "no building/land inequity",
        "at or below peer level",
        "assessment at or below peer level",
        "emv already declined",
    )
    _APPEAL_MARKERS = (
        "below current EMV",
        "below EMV",
        "standalone equalization angle",
        "equalizing to the p80 band",
        "implies ~$",
    )

    def _is_no_angle_reason(r: str) -> bool:
        return any(m.lower() in r.lower() for m in _NO_ANGLE_MARKERS)

    def _is_appeal_reason(r: str) -> bool:
        return any(m.lower() in r.lower() for m in _APPEAL_MARKERS)

    if verdict == "appeal_angle":
        reasons = [r for r in reasons if not _is_no_angle_reason(r)]
    elif verdict == "no_angle":
        reasons = [r for r in reasons if not _is_appeal_reason(r)]

    # Tax economics so the worth-it threshold (docs/04, docs/09) can be applied
    # rather than emitting a verdict with no dollars. ETR = total_tax / EMV
    # using the most recent non-null total_tax as a prior-year proxy; if no
    # year carries tax (Ramsey common), fall back to DEFAULT_ETR. The
    # illustrative_savings below is illustrative only (we have no concluded
    # reduction at triage) so the reader sees the per-dollar economics, not a forecast.
    prior_tax = next((a.get("total_tax") for a in assessments if a.get("total_tax")), None)
    if prior_tax and current["emv_total"]:
        etr = prior_tax / current["emv_total"]
        etr_source = "prior_year_tax"
    else:
        etr = DEFAULT_ETR
        etr_source = "county_default"
    # Illustrative savings from a default reduction assumption so the worth-it
    # threshold (docs/04, docs/09) can be sized at triage — NOT a forecast and
    # NOT a concluded number (there is no reconciliation yet). The illustrative
    # reduction is the best available implied gap below EMV (convergence or
    # equalization median), floored at 0.
    illustrative_reduction = 0
    if conv_gap is not None and conv_gap < 0:
        illustrative_reduction = max(illustrative_reduction, -conv_gap)
    if equalization and equalization.get("median_gap_vs_emv") is not None:
        illustrative_reduction = max(illustrative_reduction, -equalization["median_gap_vs_emv"])
    tax_economics = {
        "etr": round(etr, 4),
        "etr_proxy_source": etr_source,
        "savings_per_10k_reduction": round(etr * 10000),
    }
    # Illustrative savings only when a non-zero implied reduction actually exists.
    # A 0 here previously read as "no savings" (a finding); emit it as null with a
    # note when nothing is implied yet so a not-yet-computed value can't be read
    # as no savings. The concluded savings is computed post-reconciliation.
    if illustrative_reduction > 0:
        tax_economics["illustrative_savings"] = round(illustrative_reduction * etr)
    else:
        tax_economics["illustrative_savings"] = None
        tax_economics["illustrative_savings_note"] = (
            "no script-implied reduction yet — not 'no savings'; compute after "
            "reconciliation"
        )

    # Worth-it gate (docs/04, docs/09) — INFORMATIONAL sizing only.
    # NOTE: the floor and contingency below are ILLUSTRATIVE PLACEHOLDERS, not
    # calibrated house/Owlue doctrine — set them per engagement. The year-1 fee
    # floor (~$450) ≈ likely reduction × ETR × contingency on a one-year hold, so
    # the minimum EMV reduction that clears it is floor / (etr * contingency). The
    # gate reports a flag for the analyst to weigh; it does NOT change the verdict,
    # and downstream judgment (run-appeal-review.md Step 3) makes the worth-it call.
    YEAR1_FEE_FLOOR_PLACEHOLDER = 450      # $/yr firm fee — set per engagement
    CONTINGENCY_PCT_PLACEHOLDER = 0.30     # share of year-1 savings — set per engagement
    min_reduction_to_clear = (
        round(YEAR1_FEE_FLOOR_PLACEHOLDER / (etr * CONTINGENCY_PCT_PLACEHOLDER))
        if etr else None
    )
    gate_flag = "unknown"
    if min_reduction_to_clear is not None:
        if illustrative_reduction <= 0:
            # No script-implied reduction yet — gate cannot be sized; leave to
            # downstream reconciliation rather than asserting pass/fail.
            gate_flag = "not_yet_sized"
        elif illustrative_reduction >= min_reduction_to_clear:
            gate_flag = "pass"
        elif illustrative_reduction >= 0.8 * min_reduction_to_clear:
            gate_flag = "borderline"
        else:
            gate_flag = "fail"
    illustrative_year1_savings = (
        round(illustrative_reduction * etr * CONTINGENCY_PCT_PLACEHOLDER)
        if illustrative_reduction > 0 else None
    )
    tax_economics["worth_it_gate"] = {
        "min_reduction_to_clear_floor": min_reduction_to_clear,
        "illustrative_reduction": illustrative_reduction if illustrative_reduction > 0 else None,
        "illustrative_year1_fee": illustrative_year1_savings,
        "year1_fee_floor_assumed": YEAR1_FEE_FLOOR_PLACEHOLDER,
        "contingency_pct_assumed": CONTINGENCY_PCT_PLACEHOLDER,
        "hold_years_assumed": 1,
        "flag": gate_flag,
        "note": "INFORMATIONAL only — does not change the verdict. Floor and "
                "contingency are illustrative placeholders (set per engagement), "
                "not calibrated doctrine. 1-year hold assumed; stipulation/Tax "
                "Court routes may assume 2 years (docs/09). The worth-it call is "
                "made downstream (run-appeal-review.md Step 3).",
    }

    # The worth-it gate is INFORMATIONAL only — it does NOT modulate the verdict.
    # The script never concludes the worth-it decision: the cost-to-pursue floor
    # and contingency are engagement economics the script cannot know (the
    # placeholder figures in worth_it_gate are illustrative assumptions, not
    # calibrated house doctrine), and the playbook's architecture reserves the
    # worth-it call for the judgment layer (run-appeal-review.md Step 3), which
    # sees the concluded ask. So the verdict stays in {appeal_angle, borderline,
    # no_angle}; the gate's `flag` is surfaced for the analyst to weigh, not to
    # silently downgrade a real angle on an unverified dollar floor.

    # Relabel non-adoptable equalization dollar fields so none can be mistaken for
    # a reconciled basis. methodology.md forbids equalizing to the median, and a
    # band-floor-neutral subject (or one whose building line sits below the p80
    # band) has no equalization reduction available — so median_gap_vs_emv is
    # directional-only and equalized_total_p80 carries no reduction. This runs
    # AFTER the verdict/economics logic that consumes the canonical keys.
    if equalization:
        not_a_basis = (
            equalization.get("equalization_neutral")
            or equalization.get("building_psf_percentile", 100) < 80
        )
        if not_a_basis:
            if "median_gap_vs_emv" in equalization:
                equalization["median_gap_directional_not_a_basis"] = equalization.pop(
                    "median_gap_vs_emv"
                )
            if "equalized_total_p80" in equalization:
                equalization["equalized_total_p80_no_reduction_available"] = (
                    equalization.pop("equalized_total_p80")
                )

    return {
        "subject": subject,
        "assess_date": assess_date,
        "emv_history": history,
        "baseline_comparison": baseline_cmp,
        "subject_own_sale": own_sale_finding,
        "killer_comp": killer,
        "sales_convergence": convergence,
        "distressed_sales": distressed_sales,
        "quarantined_sales": quarantined_sales,
        "equalization": equalization,
        "tax_economics": tax_economics,
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
