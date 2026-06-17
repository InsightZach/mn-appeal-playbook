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
from analysis.comp_regression import derive_adjustments

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


# Assessed building $/SF tier screen. The county's building $/SF (EMV_building ÷
# SF) embeds quality + condition + grade in one number — and is UNIVERSAL (every
# MN county publishes EMV-building + SF; Ramsey EMVBuilding, Hennepin BLDG_MV1).
# A subject assessed at $200/SF and a comp at $500/SF are different tiers even at
# the same size/vintage. Screening to a COARSE band around the subject's building
# $/SF drops those clear tier-offs, which avoids the LEAST-supportable adjustment
# (condition/quality — the hardest to defend under Diamond Lake). The band is
# deliberately WIDE and symmetric: we GROUP peers by assessment, then VALUE them
# by their SALES — we never conclude value off the assessment we are appealing
# (the circularity guard). A narrow band would bake in the disputed assessment.
TIER_PSF_LO = 0.60   # below this × subject building $/SF → clear lower tier (teardown)
TIER_PSF_HI = 1.50   # above this × subject building $/SF → clear higher tier (mansion/renovated)
TIER_MIN_KEEP = 3    # if the screen leaves fewer than this, fall back (don't over-narrow)


def _assessed_bpsf(rec: dict, sf_key: str = "sf") -> float | None:
    """Assessed building $/SF for a record (EMV_building ÷ SF), or None when
    either input is missing/zero. Universal tier proxy, cross-county."""
    rec_sf = rec.get(sf_key) or rec.get("living_area_sf")
    eb = rec.get("emv_building")
    if rec_sf and eb:
        return eb / rec_sf
    return None


def _tier_screen(comps: list[dict], subject_bpsf: float | None) -> tuple[list[dict], int]:
    """Drop comps whose assessed building $/SF is in a clearly different tier than
    the subject (outside [TIER_PSF_LO, TIER_PSF_HI] × subject_bpsf). Comps with no
    assessed $/SF are kept (screened only by other gates). Falls back to the
    unscreened set when the screen would leave fewer than TIER_MIN_KEEP — tier is
    the LAST dimension to relax (the expansion ladder), so a thin result keeps the
    comps and signals that the screen could not be applied. Returns (kept, n_dropped)."""
    if not subject_bpsf:
        return comps, 0
    lo, hi = TIER_PSF_LO * subject_bpsf, TIER_PSF_HI * subject_bpsf
    kept, dropped = [], 0
    for c in comps:
        bpsf = _assessed_bpsf(c)
        if bpsf is not None and not (lo <= bpsf <= hi):
            dropped += 1
        else:
            kept.append(c)
    if len(kept) < TIER_MIN_KEEP:
        return comps, 0  # don't over-narrow — relax tier last
    return kept, dropped


# Effective-age condition refinement (Ramsey only — EffectiveYearBuilt is not
# published by Hennepin/Minneapolis). Effective age = assessment year − effective
# year built; it is the assessor's condition/renovation-adjusted age. Within the
# tier + size + vintage match, prefer comps whose effective age is close to the
# subject's so the median rests on condition-comparable peers — but RANK/narrow,
# never hard-cut: when the subject is itself a condition outlier (renovated home
# in an original neighborhood, or vice versa), narrowing leaves nothing, so we
# fall back and FLAG the outlier instead — that case is the headline finding, not
# noise to suppress. The ±20yr band ≈ one condition grade-step (calibrated to the
# observed effective-age-gap distribution).
EFF_AGE_BAND = 20      # ± effective-years considered condition-comparable
EFF_AGE_MIN_KEEP = 3   # below this after narrowing → fall back + flag outlier

# Below this many matched comps the sales-comparison median is thin and the agent
# should expand the search (the expansion ladder) before relying on it.
EXPANSION_FLOOR = 5


def _effective_age(rec: dict, assess_year: int) -> float | None:
    """Assessor's condition-adjusted age (assess_year − effective_year_built),
    or None when the effective year is absent (e.g. all Hennepin comps)."""
    eyb = rec.get("effective_year_built")
    if eyb and assess_year:
        return assess_year - eyb
    return None


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
    params = data.get("params") or {}

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
        # instruction to recover the price downstream. Compute the actual horizon
        # disposition from the real sale/effective dates (same machinery as a
        # priced sale) instead of a generic 'corroborating only' boilerplate — a
        # sale that PRE-dates the effective date within the ≤2yr window is
        # potentially GOVERNING once the price is recovered, not corroborating.
        missing_date = subject.get("last_sale_date")
        yrs_before = _years_between(missing_date, assess_date)
        if yrs_before is None:
            disposition = (
                "recover price downstream (eCRV / listing); sale date does not "
                "parse — cannot place it on the relevance horizon"
            )
        elif yrs_before < 0:
            disposition = (
                "sale POST-dates the Jan 2 effective date — corroborating only "
                "for the current assessment year, never the governing floor"
            )
        elif yrs_before <= 2.0:
            disposition = (
                "sale PRE-dates the effective date by "
                f"~{yrs_before}yr (≤2yr window) — potentially GOVERNING once the "
                "price is recovered; recover it before concluding no_appeal"
            )
        elif yrs_before <= 3.5:
            disposition = (
                f"sale pre-dates the effective date by ~{yrs_before}yr — time-trend "
                "to the effective date once the price is recovered, then govern on "
                "the trended figure"
            )
        elif yrs_before <= 4.0:
            disposition = (
                f"sale pre-dates the effective date by ~{yrs_before}yr — "
                "corroborating only once recovered, not governing"
            )
        else:
            disposition = (
                f"sale pre-dates the effective date by ~{yrs_before}yr — "
                "non-evidentiary for value; note it exists but it does not set the ask"
            )
        own_sale_finding = {
            "price_missing": True,
            "sale_date": missing_date,
            "years_before_effective": yrs_before,
            "note": "subject sale present but price missing — recover price "
                    "downstream (eCRV / listing). " + disposition,
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
            # On an OUTLIER LOT the land $/SF is a size artifact (a small lot reads
            # rich, a big lot reads cheap), so the land line must NOT be allowed to
            # flip equalization_neutral to False — a small-lot subject whose land
            # $/SF exceeds p80 purely because its lot is tiny is NOT inequitably
            # assessed. When the land term is unreliable, fall back to the BUILDING
            # line alone; otherwise test both lines. equalization_neutral and
            # equalized_total_p80 (== EMV ⇒ no reduction) must never contradict.
            "equalization_neutral": bool(
                subj_bpsf <= p80_bpsf
                if lot_outlier
                else (subj_bpsf <= p80_bpsf and subj_lpsf <= p80_lpsf)
            ),
            # Documents that equalization_neutral fell back to the building line
            # only because the land line is a size artifact (lot_outlier).
            "equalization_neutral_basis": (
                "building_line_only_land_term_unreliable" if lot_outlier
                else "building_and_land"
            ),
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

    # Sales-comparison indicated value (first-class, separate from sales_convergence
    # and from equalization's assessment-$/SF median_implied_total). When the script
    # discounts/nulls the single killer comp (comp_own_emv_ratio >= 0.95), the agent
    # is otherwise left with no POSITIVE sales-indicated value to anchor on and must
    # reconcile by hand. This block gives that anchor: the size+vintage-matched
    # (lot-matched where lot is load-bearing), distressed-screened comp-SALE $/SF
    # median/mean × subject SF, PLUS the size-matched sold-comp median own_emv_ratio
    # — the single fact distinguishing subject-specific from area-wide over-assessment.
    # Legal basis is MARKET VALUE (sale $/SF), NOT Federated Mutual equalization; do
    # not fuse it with equalization's assessment-$/SF median_implied_total.
    sales_comparison_indicated = None
    if sf:
        subj_year = subject.get("year_built")
        # Arm's-length, distressed-screened, quarantine-cleaned (kc_sales is already
        # arm's-length+quarantine-clean; drop the < 0.80x own-EMV distressed records).
        distressed_pids = {d["pid"] for d in distressed_sales}
        sc_pool = [
            s for s in kc_sales
            if s.get("sale_price") and s.get("sf")
            and s.get("pid") != subject.get("pid")
            and s.get("pid") not in distressed_pids
        ]
        # Assessed building $/SF tier screen FIRST (universal quality/condition
        # proxy) — drops clear tier-offs ($200-subject vs $500-comp) so the median
        # rests on same-tier peers and the least-supportable adjustment (condition/
        # quality) is minimized. Groups by assessment; the median still VALUES off
        # sales (circularity guard). Falls back if it would over-narrow.
        subject_bpsf = _assessed_bpsf(subject, sf_key="living_area_sf") or (
            (current.get("emv_building") or 0) / sf if sf else None
        )
        sc_pool, tier_dropped = _tier_screen(sc_pool, subject_bpsf)
        # Size-matched (±30% SF).
        size_matched = [s for s in sc_pool if _in_sf_band(s.get("sf"), sf)]
        # Size + vintage-matched (±20 yr) when the subject's year_built is known.
        sv_matched = [
            s for s in size_matched
            if subj_year and s.get("year_built")
            and abs(s["year_built"] - subj_year) <= 20
        ] if subj_year else list(size_matched)
        # Lot-matched layer (where lot is load-bearing): keep separately rather than
        # narrowing the primary set, since not all sales carry lot_acres.
        sv_lot_matched = [
            s for s in sv_matched
            if lot_sf and s.get("lot_acres")
            and _in_sf_band((s["lot_acres"] or 0) * SQFT_PER_ACRE, lot_sf)
        ] if lot_sf else []

        # Effective-age condition refinement (Ramsey). Prefer comps within
        # ±EFF_AGE_BAND effective-years of the subject so the median rests on
        # condition-comparable peers. RANK/narrow, never hard-cut: if narrowing
        # leaves too few, the subject is a condition outlier — fall back and flag.
        subj_effage = _effective_age(subject, current.get("assess_year") or
                                     int(assess_date[:4]))
        comp_effages = [
            _effective_age(s, current.get("assess_year") or int(assess_date[:4]))
            for s in sv_matched
        ]
        have_effage = subj_effage is not None and any(e is not None for e in comp_effages)
        sve_matched = [
            s for s, e in zip(sv_matched, comp_effages)
            if e is not None and abs(e - subj_effage) <= EFF_AGE_BAND
        ] if have_effage else []
        # Subject is a condition outlier when effective ages exist and narrowing
        # collapses an otherwise-healthy set (its effective age sits outside the
        # neighborhood's), e.g. a renovated subject (low effective age) among
        # originals — the median is then built from materially different-condition
        # comps and points the wrong way unless corrected.
        subject_condition_outlier = bool(
            have_effage and len(sv_matched) >= 5
            and len(sve_matched) < EFF_AGE_MIN_KEEP
        )
        condition_direction = None
        if subject_condition_outlier:
            known = [e for e in comp_effages if e is not None]
            comp_eff_median = sorted(known)[len(known) // 2] if known else None
            if comp_eff_median is not None:
                condition_direction = (
                    "subject NEWER effective age than peers (assessed as updated/"
                    "renovated) — peer $/SF median UNDERSTATES the subject"
                    if subj_effage < comp_eff_median else
                    "subject OLDER effective age than peers (assessed as more "
                    "original) — peer $/SF median OVERSTATES the subject"
                )
        use_effage = have_effage and len(sve_matched) >= EFF_AGE_MIN_KEEP

        def _median(vals: list[float]) -> float | None:
            v = sorted(vals)
            return v[len(v) // 2] if v else None

        # Prefer the tightest available matched set, but report which basis was
        # used and the n so the agent can judge reliability. Effective-age-matched
        # (Ramsey condition refinement) is preferred over plain size+vintage when
        # available and not collapsed by a subject-condition outlier.
        if use_effage:
            basis_set, basis_label = sve_matched, "size+vintage+effective_age_matched"
        elif sv_matched:
            basis_set, basis_label = sv_matched, "size+vintage_matched"
        elif size_matched:
            basis_set, basis_label = size_matched, "size_matched_only"
        else:
            basis_set, basis_label = [], "none"

        # Condition-verify shortlist: the grid-driving comps the agent should
        # actually read for condition (Phase 2) — the closest ~6 by effective-age
        # proximity (Ramsey) then geographic distance. "Enough, not all": the
        # house grid only needs to bracket the subject, so verify these, not 30.
        assess_year_i = current.get("assess_year") or int(assess_date[:4])

        def _verify_key(s: dict) -> tuple:
            e = _effective_age(s, assess_year_i)
            eff_gap = abs(e - subj_effage) if (e is not None and subj_effage is not None) else 999
            return (eff_gap, s.get("distance_miles") or 999)

        condition_verify_shortlist = [
            {
                "pid": s.get("pid"),
                "address": s.get("address"),
                "effective_age": _effective_age(s, assess_year_i),
                "effective_age_gap": (
                    abs(_effective_age(s, assess_year_i) - subj_effage)
                    if (_effective_age(s, assess_year_i) is not None and subj_effage is not None)
                    else None
                ),
            }
            for s in sorted(basis_set, key=_verify_key)[:6]
        ]

        # Data-derived adjustment rates (TARE Ch. 21 statistical analysis) — a
        # multiple regression of comp sale price on the elements of comparison,
        # run on the same-tier, arm's-length, quarantine-clean pool (sc_pool, the
        # broad set, NOT the narrowed median set — regression wants the variance
        # across size/age/lot/time to estimate the marginals). The coefficients
        # are the SUPPORTABLE adjustment rates the sales-comp grid applies; each
        # carries its t-stat + reliability so the packet quotes a derived rate,
        # not a table number. Condition/quality are NOT regressed (not in the
        # data) — they come from the agent condition read.
        derived_adjustments = derive_adjustments(sc_pool, subject, assess_date)

        psf_vals = [s["sale_price"] / s["sf"] for s in basis_set]
        median_psf = _median(psf_vals)
        mean_psf = (sum(psf_vals) / len(psf_vals)) if psf_vals else None
        # Size-matched sold-comp median own_emv_ratio — subject-specific vs area-wide
        # over-assessment discriminator. ~1.0 => peers fairly assessed (over-assessment
        # is subject-specific); < ~0.90 => area-wide pocket over-assessment (equalization).
        ratio_vals = [
            s["sale_price"] / s["emv_total"]
            for s in basis_set
            if s.get("emv_total")
        ]
        median_own_emv_ratio = _median(ratio_vals)
        if median_psf is not None:
            indicated_median = round(median_psf * sf)
            indicated_mean = round(mean_psf * sf) if mean_psf is not None else None
            indicated_gap = indicated_median - current["emv_total"]
            # Explicit angle label so the SIGN of the gap is not left for the agent
            # to interpret (2090 Dayton: a POSITIVE gap next to a borderline verdict
            # reads as an angle when it is the opposite). sales_angle is True only
            # when the size+vintage-matched sales indicate a value MATERIALLY below
            # EMV (> ~2% below); at/above EMV there is no sales-based angle.
            sales_angle = bool(indicated_gap < -0.02 * current["emv_total"])
            # Lot reliability: the flat sale-$/SF median silently strips lot value.
            # When few of the matched comps actually match the subject's lot
            # (lot_matched_n low vs n), or the subject's lot is an outlier, the
            # indicated_value_median is land-contaminated and must NOT be quoted as
            # a reconciled value (a condo/tiny-lot subject projected against
            # land-bearing house $/SF, or a small-lot subject against large-lot
            # comps). Self-disclaim it the way single-model sales_convergence is.
            lot_match_weak = bool(
                (equalization or {}).get("lot_outlier")
                or (len(sv_lot_matched) == 0)
                or (len(basis_set) and len(sv_lot_matched) / len(basis_set) < 0.34)
            )
            sales_comparison_indicated = {
                "basis": basis_label,
                "n": len(basis_set),
                # Assessed building $/SF tier screen (universal quality/condition
                # proxy). subject_assessed_building_psf grounds the tier; comps
                # outside [0.60, 1.50]× it were dropped as clear tier-offs so the
                # median rests on same-tier peers (minimizes the least-supportable
                # condition/quality adjustment). 0 dropped can also mean the screen
                # fell back to avoid over-narrowing — see tier_screen_applied.
                "subject_assessed_building_psf": (
                    round(subject_bpsf, 1) if subject_bpsf else None
                ),
                "tier_screened_out": tier_dropped,
                "tier_screen_applied": tier_dropped > 0,
                # Condition refinement (effective age — Ramsey only). When the
                # basis is "...+effective_age_matched", the median rests on
                # condition-comparable peers. subject_condition_outlier flags the
                # case where the SUBJECT's condition sits outside the
                # neighborhood — then the median points the wrong way and the
                # condition_direction note says which way; the agent must verify
                # the subject. condition_verify_shortlist is the small set of
                # grid-driving comps to read for condition (Phase 2 agent step).
                "subject_effective_age": subj_effage,
                "subject_condition_outlier": subject_condition_outlier,
                "condition_direction": condition_direction,
                "condition_signal": (
                    "effective_age (Ramsey)" if have_effage
                    else "unavailable — agent condition read required (Hennepin/Mpls)"
                ),
                "condition_verify_shortlist": condition_verify_shortlist,
                # Data-derived adjustment RATES for the sales-comp grid (TARE
                # statistical analysis) — regression coefficients on this comp
                # pool, each with t-stat + reliability. The supportable rates to
                # apply (comp→subject: adjusted = price + Σ coef × (subj − comp)),
                # NOT a table default. Condition/quality are filled by the agent
                # read, not here. null when too few comps to regress.
                "derived_adjustments": derived_adjustments,
                "legal_basis": "market value (sale $/SF) — NOT Federated Mutual "
                               "equalization; do not fuse with equalization "
                               "median_implied_total",
                "median_sale_psf": round(median_psf, 1),
                "mean_sale_psf": round(mean_psf, 1) if mean_psf is not None else None,
                "indicated_value_median": indicated_median,
                "indicated_value_mean": indicated_mean,
                "indicated_gap_vs_emv": indicated_gap,
                "sales_angle": sales_angle,
                "sales_angle_note": (
                    "indicated median is BELOW EMV — sales-based angle present"
                    if sales_angle else
                    f"indicated median is AT/ABOVE EMV (gap {indicated_gap:+,}); "
                    "peers fairly assessed → NO sales-based angle"
                ),
                "lot_matched_n": len(sv_lot_matched),
                "lot_match_weak": lot_match_weak,
                "indicated_value_reliability": (
                    "directional_screen_only_do_not_quote — lot-unmatched/outlier "
                    "$/SF strips land value; reconcile on lot-comparable whole prices"
                    if lot_match_weak else "lot-matched — quotable"
                ),
                "sold_comp_median_own_emv_ratio": (
                    round(median_own_emv_ratio, 2)
                    if median_own_emv_ratio is not None else None
                ),
                # Expansion ladder — surfaced when the matched set is thin so the
                # agent widens the search in supportability order (re-run collect
                # with the widened flags). Tier is applied in triage, so the
                # collector never relaxes it — tier is held for last.
                "expansion": ({
                    "recommended": True,
                    "matched_n": len(basis_set),
                    "floor": EXPANSION_FLOOR,
                    "current_params": {
                        k: params.get(k) for k in (
                            "sales_months", "radius_sales_mi", "radius_comps_mi",
                            "year_tolerance", "sf_tolerance")
                    },
                    "ladder": [
                        "1. widen --sales-months 24->36 (then time-adjust staler sales)",
                        "2. widen --radius-sales / --radius-comps",
                        "3. widen --year-tolerance 20->30",
                        "4. widen --sf-tolerance 0.30->0.40",
                        "5. tier screen is HELD (relax only if still thin after 1-4)",
                        "then eCRV/Beacon for arm's-length sales the API missed; "
                        "if still thin, the sales approach is thin -> lean on "
                        "equalization + own sale (appeal-packet 'no tier-matched sale').",
                    ],
                } if len(basis_set) < EXPANSION_FLOOR else None),
                "note": "size+vintage-matched (lot-matched count reported separately), "
                        "distressed- and quarantine-screened sale $/SF × subject SF. "
                        "sold_comp_median_own_emv_ratio ≈ 1.0 ⇒ peers fairly assessed "
                        "(over-assessment is subject-specific); < ~0.90 ⇒ area-wide "
                        "pocket (equalization basis).",
            }

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
        #   > 4.0 yr → non-governing (raw delta already flagged meaningless above)
        # NOTE: methodology.md adds a 4.0-5.0yr band where a sale may be cited as
        # TIME-TRENDED directional corroboration (disclosed stale). The script keeps
        # the conservative >4.0yr → non-governing cutoff for VERDICT purposes (it
        # never sets the ask off a >4yr sale); the 4-5yr directional-corroboration
        # nuance is an agent-layer judgment call, not a script verdict change.
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
            # "Stale" is doctrinally reserved for the >4yr non-evidentiary band
            # (methodology.md own-sale horizon). A 2.0-3.5yr sale is GOVERNING after
            # time-trending — labeling it "stale" contradicts the doctrine the agent
            # is told to apply and invites discarding a governing trended sale.
            governing_str = (
                "governing" if trended_delta_pct < -5
                else "governing — at/above EMV, supports no-appeal"
            )
            reasons.append(f"Subject sold ${own_sale_finding['sale_price']:,.0f} on "
                           f"{own_sale_finding['sale_date']} ({yrs} yrs before effective); "
                           f"time-trended to ~${trended:,.0f} ({trended_delta_pct}% vs EMV) — "
                           f"{governing_str}")
        else:
            # Beyond ~3-4yr: corroborating only — do NOT let the own sale flip the
            # verdict on its own, and do not report the raw delta as a finding.
            # 3.5-4.0yr is corroborating-only (not "stale" — that word is reserved
            # for the >4yr non-evidentiary band); >4yr is genuinely stale but is also
            # surfaced as corroborating-only (it never flips the verdict). Label by band.
            band_str = (
                f"({yrs} yrs before effective — corroborating only, not governing)"
                if yrs <= 4.0
                else f"({yrs} yrs stale — non-evidentiary for value, corroborating only)"
            )
            reasons.append(f"Subject sold ${own_sale_finding['sale_price']:,.0f} on "
                           f"{own_sale_finding['sale_date']} {band_str}")
    # p80-equalization vs the larger supported reduction. The equalization reason
    # below headlines equalized_total_p80, but the worth_it_gate's
    # illustrative_reduction (sized later) is sourced from conv_gap and
    # median_gap_vs_emv — a different, usually LARGER number. Headlining the narrow
    # p80 figure while the gate silently sizes off a larger reduction is the
    # 1024-Lincoln trap: an agent trusting the headline runs the gate against the
    # smaller ask and may flip a genuine appeal to no_appeal. Pre-compute whether a
    # larger, supported reduction exists so the p80 reason can be annotated
    # ('smaller reduction; sales/median conclusion governs the ask') — keeping the
    # verdict reason traceable to the same governing ask the gate sizes off.
    def _p80_reason_annotation() -> str:
        if not equalization:
            return ""
        p80_total = equalization.get("equalized_total_p80")
        if p80_total is None:
            return ""
        p80_reduction = current["emv_total"] - p80_total
        # Candidate larger reductions (all from a governing/market or median basis).
        candidates = []
        med_gap = equalization.get("median_gap_vs_emv")
        if med_gap is not None and med_gap < 0:
            candidates.append(-med_gap)
        if sales_comparison_indicated and sales_comparison_indicated.get("indicated_gap_vs_emv") is not None:
            sci_gap = sales_comparison_indicated["indicated_gap_vs_emv"]
            if sci_gap < 0:
                candidates.append(-sci_gap)
        # NOTE: convergence (conv_gap) is sized LATER in the verdict flow, so it is
        # intentionally not referenced here; median + sales-comparison-indicated are
        # the reductions available at reason-build time. The worth_it_gate, sized
        # after convergence, may pick up an even larger conv reduction — that only
        # reinforces "sales/median governs", never contradicts this annotation.
        larger = max(candidates) if candidates else 0
        if larger > p80_reduction:
            return (" — p80 equalization floor (smaller reduction of "
                    f"~${p80_reduction:,.0f}; a larger ~${larger:,.0f} sales/median "
                    "reduction exists — the sales/median conclusion governs the ask)")
        return ""

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
                f"equalizing to the p80 band implies ~${equalization['equalized_total_p80']:,.0f}"
                + _p80_reason_annotation())
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
        elif bldg_pct >= 80:
            # BUILDING-side inequity is the governing equalization signal — the
            # building line drives inequity, land does not. Fire borderline only on
            # a rich building line.
            if verdict == "no_angle":
                verdict = "borderline"
            land_note = (" (land $/SF excluded — size artifact on an outlier lot)"
                         if equalization.get("land_psf_percentile_size_artifact") else "")
            reasons.append(
                f"Equalization: building $/SF at {bldg_pct}th percentile (governing line), "
                f"land $/SF at {equalization['land_psf_percentile']}th percentile of comps{land_note}")
        elif land_pct >= 80:
            # ONLY the land line is rich while the building line is mid-pack
            # (< p80). Per methodology.md "Rich-land / neutral-building pocket":
            # a high land $/SF with a neutral building line is a presumptively
            # LEGITIMATE locational premium (lake / view / corner), NOT inequity —
            # the sales conclusion governs. Do NOT fire borderline on the land line
            # alone, and label the reason so it cannot read as an angle (2090
            # Dayton: building 44th pctile + land 80th was firing borderline and
            # leading with the non-actionable land figure).
            reasons.append(
                f"Equalization: building $/SF mid-pack ({bldg_pct}th pctile) — NO building "
                f"inequity; land $/SF rich ({equalization['land_psf_percentile']}th pctile) is a "
                f"presumptively-legitimate locational premium, not a reduction lever — "
                f"sales conclusion governs")
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

    # Quotable size+vintage+lot-matched sales indication BELOW EMV is a first-class
    # angle the verdict must consult — it is the script's single most reliable
    # below-EMV market signal, and orphaning it (firing no_angle off equalization /
    # killer / convergence while sales_comparison_indicated.sales_angle is true) is
    # the failure triage-judgment.md warns about. A quotable, lot-matched indication
    # below EMV escalates to appeal_angle regardless of the killer/convergence path;
    # only the downstream worth-it gate (run-appeal-review.md Step 3) can downgrade it.
    sci_angle_live = bool(
        sales_comparison_indicated
        and sales_comparison_indicated.get("sales_angle")
        and sales_comparison_indicated.get("indicated_value_reliability")
        != "directional_screen_only_do_not_quote"
        and sales_comparison_indicated.get("lot_match_weak") is not True
    )
    if sci_angle_live:
        sci_gap = sales_comparison_indicated.get("indicated_gap_vs_emv")
        sci_med = sales_comparison_indicated.get("indicated_value_median")
        if verdict == "no_angle":
            verdict = "appeal_angle"
        reasons.append(
            f"Size+vintage+lot-matched sales indicate ~${sci_med:,.0f} "
            f"(${-sci_gap:,.0f} below EMV) — quotable sales angle"
            if sci_med is not None and sci_gap is not None
            else "Size+vintage+lot-matched sales indicate a value below EMV — quotable sales angle")

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
        # When the best comp sold AT or ABOVE its own EMV (comp_own_emv_ratio >=
        # 0.95) the county assessed THAT comp correctly — its low absolute sale is
        # just a cheaper value tier, NOT evidence the subject is fairly assessed.
        # triage-judgment.md item 2 tells the agent to DISCOUNT such a comp, so the
        # script must not headline "best comp brackets the subject at or above EMV"
        # off it. Suppress the comp as a value indicator and base the no_angle /
        # borderline reason on the size-matched pocket median own_emv_ratio and the
        # equalization-neutral result instead.
        kc_ratio = killer.get("comp_own_emv_ratio") if killer else None
        killer_comp_discounted = kc_ratio is not None and kc_ratio >= 0.95
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
        if killer and killer.get("verdict") == "kills_appeal" and conv_at_emv and not killer_comp_discounted:
            reasons.append("Best comp at EMV and sales models converge near EMV — no angle")
        elif killer_confirms and not killer_comp_discounted:
            reasons.append("Best comp brackets the subject at or above EMV — no angle")
        elif killer_comp_discounted and (
            (pocket_median_own_emv_ratio is not None and pocket_median_own_emv_ratio >= 0.95)
            or (equalization and equalization.get("equalization_neutral"))
        ):
            # Best comp discounted (sold at/above its own EMV); base the no-angle
            # reason on the size-matched pocket median own-EMV ratio and the
            # equalization-neutral result, NOT on the discounted comp.
            # GUARD: only assert "no subject-specific angle" when there is genuinely
            # no quotable below-EMV sales indication. When the pocket sold ~1.0x (peers
            # fairly assessed) AND sales_comparison_indicated is below EMV, the
            # over-assessment IS subject-specific — sci_angle_live above will already
            # have flipped the verdict to appeal_angle, so this branch is unreachable
            # in that case. The explicit not-sci_angle_live guard prevents a future
            # edit from re-emitting the factually-false "no subject-specific angle".
            pocket_str = (
                f"the size-matched pocket sold at ~{pocket_median_own_emv_ratio:.2f}x its own EMV"
                if pocket_median_own_emv_ratio is not None
                else "equalization is neutral (subject at/below the p80 peer band)"
            )
            if not sci_angle_live:
                reasons.append(
                    f"Best comp discounted (sold ~{kc_ratio:.2f}x its own EMV — cheaper value tier, "
                    f"not a fair-assessment signal); {pocket_str} — no subject-specific angle")
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
    # reduction is the best available implied gap below EMV from a DEFENSIBLE
    # basis, floored at 0.
    # Track which source the illustrative_reduction came from so the verdict
    # reason and worth_it_gate.illustrative_reduction are traceable to the SAME ask
    # (the 1024-Lincoln mismatch: the reason headlined the narrow p80 figure while
    # the gate silently sized off the larger median_gap). Two figures are
    # deliberately NOT candidates here:
    #   - the p80 equalization floor — the smaller, non-governing figure; and
    #   - the equalization MEDIAN gap — methodology.md (Equalization: band-floor
    #     neutrality, use p75–p90 not the median) forbids equalizing to the median,
    #     and the script itself relabels it `median_gap_directional_not_a_basis`.
    #     Sizing the gate off a basis the playbook forbids produced a misleading
    #     sub-EMV "illustrative reduction" (2090 Dayton / 1325 Hartford: a phantom
    #     ~$5K/$21K gate built entirely on the median artifact on fairly-assessed
    #     parcels). The gate sizes off the GOVERNING (market / sales) reduction
    #     only — sales convergence or the size+vintage-matched sales-comparison
    #     indicated value. If neither lands below EMV, no reduction is implied.
    illustrative_reduction = 0
    illustrative_reduction_source = None
    if conv_gap is not None and conv_gap < 0 and -conv_gap > illustrative_reduction:
        illustrative_reduction = -conv_gap
        illustrative_reduction_source = "sales_convergence_gap_vs_emv"
    if sales_comparison_indicated and \
            sales_comparison_indicated.get("indicated_gap_vs_emv") is not None and \
            -sales_comparison_indicated["indicated_gap_vs_emv"] > illustrative_reduction:
        illustrative_reduction = -sales_comparison_indicated["indicated_gap_vs_emv"]
        illustrative_reduction_source = "sales_comparison_indicated_gap_vs_emv"
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
        if illustrative_reduction <= 0 and verdict == "no_angle":
            # Verdict already forecloses an appeal — there is no ask to size and the
            # gate is moot. Emit n/a (terminal), not "not_yet_sized", so the analyst
            # is not prompted to size an ask that doesn't exist (run-appeal-review.md
            # Step 3 treats this as terminal).
            gate_flag = "n/a — no supportable reduction"
        elif illustrative_reduction <= 0:
            # No script-implied reduction yet but the verdict is not a hard no_angle
            # — gate cannot be sized; leave to downstream reconciliation.
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
        # Which figure the gate sized off, so the verdict reason and the gate are
        # traceable to the SAME ask. The p80 equalization floor is intentionally
        # excluded as a source — it is the smaller, non-governing figure.
        "illustrative_reduction_source": (
            illustrative_reduction_source if illustrative_reduction > 0 else None
        ),
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
        "sales_comparison_indicated": sales_comparison_indicated,
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
