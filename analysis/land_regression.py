"""Single-vintage land-value regression — an independent cross-check on the county's
land assessment (and on the extraction approach's `emv_land` add-back).

Land VALUE rises with lot size, but land $/SF FALLS with it, so a flat $/SF comparison
mis-ranks a large lot (it reads "cheap" purely for being big). This regresses the
county's own assessed land on lot size across **same-assessment-year** comparables,
then reads the curve at the subject's lot size. The subject's position vs. the line is
the signal:

  * subject ON / BELOW the line  → land fairly (or conservatively) assessed — confirms
    the value; no land reduction available.
  * subject ABOVE the line       → land assessed rich for its size → argue it down to
    the line. The gap is `wiggle_room`: the defensible lower bound of a range.

**CRITICAL — single vintage.** `emv_land` must be one assessment year. Mixing 2025 and
2026 land values produces a spurious result: a 2026 subject measured against a
2025-weighted line looks rich when it isn't (the classic wrong-year trap that sinks a
careless appeal). This module filters comps to `assess_year` and refuses to mix.
"""
from __future__ import annotations

SQFT_PER_ACRE = 43560


def _ols(xs: list[float], ys: list[float]) -> tuple[float, float, float] | None:
    """Ordinary least squares → (slope, intercept, r2). None if degenerate."""
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    syy = sum((y - my) ** 2 for y in ys)
    if syy == 0:
        return b, a, 1.0
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    return b, a, 1.0 - ss_res / syy


def compute_land_regression(comps: list[dict], subject_lot_sf: float | None,
                            subject_land: float | None, assess_year: int | None,
                            min_n: int = 8, lot_lo: float = 3000.0,
                            lot_hi: float = 45000.0, neutral_band: float = 0.02) -> dict | None:
    """Regress county-assessed land on lot size for the `assess_year` comparables and
    locate the subject on the curve. Returns None when there is no subject lot/land,
    no `assess_year`, or fewer than `min_n` same-vintage comps in a sane lot range.

    Each comp needs `emv_land`, `lot_acres`, and `emv_year` (the assessment year of
    that land value). Only comps whose `emv_year == assess_year` are used."""
    if not (subject_lot_sf and subject_land and assess_year):
        return None

    pts, seen = [], set()
    for c in comps or []:
        if c.get("emv_year") != assess_year:
            continue
        pid, la, el = c.get("pid"), c.get("lot_acres"), c.get("emv_land")
        if not (la and el) or pid in seen:
            continue
        seen.add(pid)
        lot = la * SQFT_PER_ACRE
        if lot < lot_lo or lot > lot_hi or el < 20000:
            continue
        pts.append((lot, float(el), c.get("address")))
    if len(pts) < min_n:
        return {
            "applicable": False,
            "assess_year": assess_year,
            "n": len(pts),
            "note": (f"only {len(pts)} same-vintage ({assess_year}) land comps in range — "
                     "too few to regress; do NOT mix assessment years to pad it"),
        }

    lots = [p[0] for p in pts]
    lands = [p[1] for p in pts]
    psfs = [land / lot for lot, land in zip(lots, lands)]
    val_fit = _ols(lots, lands)        # land value ~ lot SF (the robust number)
    psf_fit = _ols(lots, psfs)         # land $/SF ~ lot SF (the chart's straight line)
    if not val_fit or not psf_fit:
        return None
    vb, va, vr2 = val_fit
    pb, pa, pr2 = psf_fit

    subj_psf = subject_land / subject_lot_sf
    indicated_value = round(va + vb * subject_lot_sf)            # value-fit (robust)
    indicated_psf = round((pa + pb * subject_lot_sf), 1)         # $/SF-line read
    indicated_value_from_psf = round(indicated_psf * subject_lot_sf)
    lo, hi = sorted((indicated_value, indicated_value_from_psf))
    # The subject's lot can sit OUTSIDE the comp lot range → the line is extrapolated,
    # and the two functional forms (value-linear vs $/SF-linear) fan out. Report both
    # as a defensible range rather than one false-precision number.
    extrapolated = not (min(lots) <= subject_lot_sf <= max(lots))

    if lo * (1 - neutral_band) <= subject_land <= hi * (1 + neutral_band):
        position = "within_range"      # county land sits inside the indicated band → confirmed
    elif subject_land > hi:
        position = "above"             # rich for its size → argue down to the line
    else:
        position = "below"            # conservatively assessed

    return {
        "applicable": True,
        "assess_year": assess_year,
        "n": len(pts),
        "lot_sf_range": [round(min(lots)), round(max(lots))],
        "subject_lot_extrapolated": extrapolated,
        "value_fit": {"slope": round(vb, 3), "intercept": round(va), "r2": round(vr2, 2)},
        "psf_fit": {"slope": round(pb, 5), "intercept": round(pa, 2), "r2": round(pr2, 2)},
        "subject_lot_sf": round(subject_lot_sf),
        "subject_land": round(subject_land),
        "subject_land_psf": round(subj_psf, 1),
        # Robust (value-fit) point + the defensible range spanning both functional forms.
        "indicated_land_value": indicated_value,
        "indicated_land_psf": indicated_psf,
        "indicated_land_range": [lo, hi],
        "position": position,
        # The defensible reduction to argue toward the LOWER end of the range (0 when the
        # county already sits at/below it — land confirmed, no room).
        "wiggle_room": max(0, round(subject_land - lo)),
        "chart": _land_psf_chart(pts, subject_lot_sf, subj_psf, pb, pa, assess_year),
    }


def _land_psf_chart(pts, subject_lot_sf, subject_psf, psf_slope, psf_intercept, year) -> dict:
    """Chart-ready dict for `report.shared_components.render_equalization_scatter_svg`:
    land $/SF (y) vs lot SF (x), the linear $/SF regression line, subject highlighted."""
    return {
        "data": [{"x": round(lot), "y": round(land / lot, 1),
                  "label": f"{(addr or '').split(',')[0]} (${land / lot:,.0f}/SF)"}
                 for lot, land, addr in pts],
        "subject_xy": {"x": round(subject_lot_sf), "y": round(subject_psf, 1)},
        "trends": [{"slope": psf_slope, "intercept": psf_intercept,
                    "label": "County land $/SF trend", "color": "#d7b971"}],
        "x_label": "Lot size (SF)",
        "caption": (f"County-assessed land $/SF vs. lot size, {year} comparables. Land $/SF "
                    "falls with lot size; the subject (highlighted) is read against the trend "
                    "at its own lot size."),
    }
