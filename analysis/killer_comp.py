"""
Identify the single strongest comparable sale that the county would lead with
in defending the assessment.

This comp can either:
  - KILL the appeal (sold near or above the subject's assessment) → no-appeal report
  - SUPPORT the appeal (sold well below the subject's assessment) → appeal package

A comp only *supports* an appeal when its sale carries real signal about the
subject's value — not merely because it sits in a cheaper value tier. A comp
whose own EMV roughly matched its own sale price (the county assessed it
correctly) sold low because it *is* cheaper, not because the subject is
over-assessed. The verdict therefore gates on the comp's sale-to-own-EMV ratio
and on the value its sale $/SF implies for the subject, and both are surfaced so
the judgment layer can see the basis.
"""

import math

EARTH_RADIUS_MI = 3958.7613


def identify_killer_comp(subject: dict, sales: list[dict]) -> dict | None:
    """
    Score each sale on similarity to subject. Highest score wins.

    Score factors (weighted):
      - Above-grade SF similarity (40%)
      - Year built proximity (15%)
      - Lot size proximity (15%)
      - Same exterior material (10%)
      - Same style (10%)
      - Proximity to subject (10%, haversine distance decay)

    Returns the top-scored sale plus its verdict:
      {
        "comp": {...},
        "score": 87.3,
        "verdict": "kills_appeal" | "confirms_fair" | "supports_appeal"
                   | "discount" | "neutral",
        "delta_from_emv": -6700,           # comp sale vs SUBJECT emv
        "delta_pct": -0.86,                # comp sale vs SUBJECT emv, %
        "sale_vs_subject_emv_pct": -0.86,  # alias of delta_pct, explicit name
        "comp_own_emv_ratio": 0.99,        # comp sale / comp's OWN emv (or None)
        "implied_subject_value": 412300,   # comp sale $/SF × subject SF (or None)
        "implied_vs_subject_emv_pct": -8.2 # implied_subject_value vs subject emv
      }

    Verdict logic:
      - "kills_appeal" if the comp sold within ±5% of the SUBJECT's EMV.
      - "confirms_fair" when the comp sold at-or-above the subject's EMV AND its
        $/SF implies the subject is worth at-or-above its EMV
        (implied_vs_subject_emv_pct >= ~-2%) — the comp brackets the subject at
        or above its assessment, an affirmative no-angle signal.
      - "supports_appeal" only when the sale carries real over-assessment signal:
          (a) the comp sold materially below its OWN EMV (ratio < ~0.93 — the
              county over-assessed the comp too), OR
          (b) the comp's sale $/SF applied to the subject's SF implies a value
              materially (>~10%) below the subject's EMV — AND the comp itself
              sold below its own EMV (ratio < ~0.93), so the implied figure is
              not an extrapolation off a correctly-assessed cheaper-tier comp.
      - "discount" for any cheaper-tier comp the county assessed correctly. The
        cheaper-tier test is ONE-SIDED on the high side: any comp that sold at or
        above ~0.95x its own EMV (comp_own_emv_ratio >= ~0.95, NO upper bound) is
        cheaper-tier — implied_subject_value is suppressed and the verdict is
        "discount", regardless of how far above 1.05 the ratio goes. A comp at
        1.06x its own EMV sold ABOVE its own EMV (assessed correctly, if not
        conservatively), so it is at least as cheaper-tier as one at 1.04x; the
        prior symmetric 0.95-1.05 window leaked such comps into supports_appeal.
      - "neutral" otherwise.
    """
    if not sales:
        return None

    # Hard SF (and, where lot is load-bearing, lot-acreage) size-band gate.
    # SF is only 40% of a soft similarity score, so without a hard band the
    # scorer can select a comp far outside the subject's value tier (e.g. a
    # 2,050 SF comp for a 5,147 SF subject) and extrapolate its $/SF onto the
    # subject — exactly the size/tier extrapolation methodology.md forbids.
    # Drop comps outside ±30% of the subject's above-grade SF, and (when the
    # comp set carries lot acreage) outside the ~10th-90th percentile of the
    # comp lot distribution, BEFORE scoring. If nothing survives, do not select
    # an out-of-band comp.
    subj_band_sf = subject.get("absf") or subject.get("living_area_sf")
    eligible = list(sales)
    if subj_band_sf:
        sf_banded = [
            s for s in eligible
            if (s.get("absf") or s.get("sf"))
            and 0.70 * subj_band_sf <= (s.get("absf") or s.get("sf")) <= 1.30 * subj_band_sf
        ]
        # Only enforce the SF band when at least one comp carries SF; if none do
        # (no SF data at all), fall through to scoring rather than dropping all.
        if any((s.get("absf") or s.get("sf")) for s in eligible):
            eligible = sf_banded

    subj_lot = subject.get("lot_acres")
    if subj_lot:
        lot_vals = sorted(s["lot_acres"] for s in eligible if s.get("lot_acres"))
        if len(lot_vals) >= 5:
            def _q(vals, q):
                idx = min(len(vals) - 1, max(0, int(round(q * (len(vals) - 1)))))
                return vals[idx]
            lo, hi = _q(lot_vals, 0.10), _q(lot_vals, 0.90)
            lot_banded = [
                s for s in eligible
                if not s.get("lot_acres") or lo <= s["lot_acres"] <= hi
            ]
            if lot_banded:
                eligible = lot_banded

    if not eligible:
        return {
            "comp": None,
            "score": 0.0,
            "verdict": "no_size_matched_sale",
            "implied_subject_value": None,
            "note": "no arm's-length sale within ±30% of subject SF (and "
                    "comparable lot size) — sales comparison unavailable",
        }

    scored = []
    for s in eligible:
        score = _similarity_score(subject, s)
        scored.append({"comp": s, "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[0]

    comp = top["comp"]
    sale_price = comp.get("sale_price", 0)
    emv = subject.get("emv_total", 0)
    subject_sf = subject.get("absf") or subject.get("living_area_sf")

    # Comp's sale relative to its OWN assessment — the over-assessment signal.
    comp_own_emv = comp.get("emv_total")
    comp_own_emv_ratio = None
    if sale_price and comp_own_emv:
        comp_own_emv_ratio = sale_price / comp_own_emv
    top["comp_own_emv_ratio"] = comp_own_emv_ratio

    # The comp's sale $/SF applied to the subject's SF — what the sale implies
    # for the subject, holding building size constant.
    implied_subject_value = None
    implied_vs_subject_emv_pct = None
    comp_sf = comp.get("absf") or comp.get("sf")
    if sale_price and comp_sf and subject_sf:
        implied_subject_value = sale_price / comp_sf * subject_sf
        if emv:
            implied_vs_subject_emv_pct = round(
                (implied_subject_value - emv) / emv * 100, 1
            )
    top["implied_subject_value"] = (
        round(implied_subject_value) if implied_subject_value is not None else None
    )
    top["implied_vs_subject_emv_pct"] = implied_vs_subject_emv_pct

    if sale_price and emv:
        delta = sale_price - emv
        delta_pct = delta / emv * 100
        top["delta_from_emv"] = delta
        top["delta_pct"] = delta_pct
        top["sale_vs_subject_emv_pct"] = round(delta_pct, 1)

        confirms_fair = (
            delta_pct >= -5  # sale at-or-above (within 5% above) subject EMV
            and implied_vs_subject_emv_pct is not None
            and implied_vs_subject_emv_pct >= -2
        )
        # A cheaper-tier comp the county assessed correctly (sold AT or ABOVE its
        # own EMV): its low sale reflects the tier, not subject over-assessment.
        # One-sided on the high side — no upper bound. A comp at 1.06x its own EMV
        # is at least as cheaper-tier as one at 1.04x.
        cheaper_tier = (
            comp_own_emv_ratio is not None and comp_own_emv_ratio >= 0.95
        )
        if abs(delta_pct) <= 5:
            verdict = "kills_appeal"
        elif delta_pct > 5 and confirms_fair:
            verdict = "confirms_fair"
        else:
            # supports_appeal requires real over-assessment signal, not just a
            # cheaper-tier sale: either the comp sold below its OWN EMV, or its
            # $/SF implies a materially lower value for the subject.
            sold_below_own_emv = (
                comp_own_emv_ratio is not None and comp_own_emv_ratio < 0.93
            )
            # The implied-value path only carries over-assessment signal when the
            # comp itself sold BELOW its own EMV — otherwise the implied figure is
            # an extrapolation off a comp the county assessed correctly (or a
            # cheaper-tier comp), which methodology.md forbids. Require
            # sold_below_own_emv to gate it, not merely "not cheaper_tier."
            implies_subject_lower = (
                sold_below_own_emv
                and implied_vs_subject_emv_pct is not None
                and implied_vs_subject_emv_pct < -10
            )
            if (sold_below_own_emv or implies_subject_lower) and not cheaper_tier:
                verdict = "supports_appeal"
            elif cheaper_tier:
                # County assessed the comp correctly — cheaper tier, do not rely
                # on its implied subject value.
                verdict = "discount"
                top["implied_subject_value"] = None
                top["implied_subject_value_note"] = "cheaper-tier — do not rely on"
            else:
                verdict = "neutral"
        top["verdict"] = verdict

    return top


def _similarity_score(subject: dict, sale: dict) -> float:
    """0-100 similarity score."""
    score = 0.0
    # Above-grade SF (40%)
    if subject.get("absf") and sale.get("absf"):
        sf_diff = abs(subject["absf"] - sale["absf"]) / subject["absf"]
        score += max(0, 40 * (1 - sf_diff * 2))
    # Year built (15%)
    if subject.get("year_built") and sale.get("year_built"):
        yr_diff = abs(subject["year_built"] - sale["year_built"])
        score += max(0, 15 - yr_diff * 0.5)
    # Lot size (15%)
    if subject.get("lot_acres") and sale.get("lot_acres"):
        lot_diff = abs(subject["lot_acres"] - sale["lot_acres"]) / subject["lot_acres"]
        score += max(0, 15 * (1 - lot_diff))
    # Exterior (10%)
    if subject.get("exterior") and sale.get("exterior") and subject["exterior"] == sale["exterior"]:
        score += 10
    # Style (10%)
    if subject.get("style") and sale.get("style") and subject["style"] == sale["style"]:
        score += 10
    # Proximity (10%) — a far-away cheaper-tier comp should not win selection.
    # Linear distance decay: full credit at 0 mi, zero credit at/beyond 1 mi.
    s_lat, s_lon = subject.get("lat"), subject.get("lon")
    c_lat, c_lon = sale.get("lat"), sale.get("lon")
    if None not in (s_lat, s_lon, c_lat, c_lon):
        dist = _haversine_miles(s_lat, s_lon, c_lat, c_lon)
        score += max(0, 10 * (1 - dist))
    return score


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_MI * c
