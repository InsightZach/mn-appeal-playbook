"""
Derive sales-comparison adjustment rates from the comp set itself — TARE 15th,
Ch. 21 "statistical analysis." A multiple OLS regression of comp SALE PRICE on the
elements of comparison reads the marginal market contribution of each element at
once, so the grid adjusts comps with rates pulled from THIS market rather than
imported from a table.

The coefficients ARE the adjustments: to bring a comp to the subject,
    adjusted_price = comp_price + Σ coef_k × (subject_k − comp_k)

Each rate ships with its fit statistics (n, R², t-stat, reliability flag) so the
packet can state "size = $X/SF, derived from N comps, R²=Y" — a supportable rate,
not an eyeball. Condition/quality are NOT regressed (not in the county data) —
they come from the agent condition read and cost-to-cure.
"""
from __future__ import annotations

from datetime import date

import numpy as np

SQFT_PER_ACRE = 43560
_EPOCH = date(1970, 1, 1)

# A k-predictor regression needs comfortably more rows than predictors for stable
# coefficients. Below MIN_N we don't regress; below RELIABLE_N we flag low power.
MIN_N = 8
RELIABLE_N = 15
RELIABLE_R2 = 0.35
RELIABLE_ABS_T = 2.0  # |t| ≳ 2 ≈ significant at ~95%


def _days(iso: str) -> int | None:
    try:
        return (date.fromisoformat(str(iso)[:10]) - _EPOCH).days
    except (ValueError, TypeError):
        return None


def _row(comp: dict, assess_days: int, age_basis: str, assess_year: int):
    """Build a (predictors, price) row, or None when any field is missing."""
    price = comp.get("sale_price")
    sf = comp.get("sf")
    lot_acres = comp.get("lot_acres")
    sold = _days(comp.get("sale_date"))
    if age_basis == "effective_year":
        eyb = comp.get("effective_year_built")
        age = (assess_year - eyb) if eyb else None
    else:
        yb = comp.get("year_built")
        age = (assess_year - yb) if yb else None
    if not (price and sf and lot_acres and sold is not None and age is not None):
        return None
    months_before = (assess_days - sold) / 30.44   # + = sold before effective date
    lot_sf = lot_acres * SQFT_PER_ACRE
    return [sf, age, lot_sf, months_before], float(price)


def derive_adjustments(comps: list[dict], subject: dict, assess_date: str) -> dict | None:
    """Regress comp sale price on [SF, age, lot_sf, months_before_effective] and
    return data-derived adjustment rates with fit stats. Returns None when there
    are too few complete rows to regress.

    Age uses EFFECTIVE year built when every usable comp carries it (Ramsey
    condition-adjusted age), else actual year built — reported as `age_basis`.
    """
    assess_year = int(str(assess_date)[:4])
    assess_days = _days(assess_date)
    if assess_days is None:
        return None

    # Prefer effective-year age only if (nearly) all comps carry it; else year_built.
    n_eff = sum(1 for c in comps if c.get("effective_year_built"))
    n_yb = sum(1 for c in comps if c.get("year_built"))
    age_basis = "effective_year" if n_eff >= max(MIN_N, int(0.8 * n_yb)) else "year_built"

    rows = [_row(c, assess_days, age_basis, assess_year) for c in comps]
    rows = [r for r in rows if r is not None]
    if len(rows) < MIN_N:
        return None

    X = np.array([r[0] for r in rows], dtype=float)
    y = np.array([r[1] for r in rows], dtype=float)
    n, k = X.shape
    Xd = np.column_stack([np.ones(n), X])  # intercept + k predictors

    # Guard rank-deficiency (e.g. all comps share a lot size).
    if np.linalg.matrix_rank(Xd) < Xd.shape[1]:
        return None
    XtX_inv = np.linalg.inv(Xd.T @ Xd)
    beta = XtX_inv @ Xd.T @ y
    resid = y - Xd @ beta
    dof = n - Xd.shape[1]
    if dof <= 0:
        return None
    sigma2 = float(resid @ resid) / dof
    se = np.sqrt(np.maximum(np.diag(sigma2 * XtX_inv), 0.0))
    ss_tot = float(((y - y.mean()) ** 2).sum())
    ss_res = float((resid ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    adj_r2 = 1 - (1 - r2) * (n - 1) / dof if dof > 0 else 0.0

    names = ["size_per_sf", "age_per_year", "lot_per_lot_sf", "time_per_month"]
    units = ["$ per finished SF", "$ per year of age (− = older worth less)",
             "$ per lot SF", "$ per month (sale→effective)"]
    coefs = {}
    for i, (nm, un) in enumerate(zip(names, units)):
        b = float(beta[i + 1])          # +1 skips intercept
        s = float(se[i + 1])
        t = b / s if s > 0 else 0.0
        coefs[nm] = {
            "value": round(b, 2),
            "t_stat": round(t, 2),
            "unit": un,
            "reliable": abs(t) >= RELIABLE_ABS_T,
        }

    overall_reliable = bool(n >= RELIABLE_N and r2 >= RELIABLE_R2)
    return {
        "method": "OLS multiple regression on comp sale price (TARE Ch. 21 statistical analysis)",
        "n": n,
        "r2": round(r2, 3),
        "adj_r2": round(adj_r2, 3),
        "age_basis": age_basis,
        "intercept": round(float(beta[0]), 2),
        "coefficients": coefs,
        "reliable": overall_reliable,
        "reliability_note": (
            "data-derived rates — quotable" if overall_reliable else
            f"low power (n={n}, R²={round(r2, 2)}); treat coefficients as directional, "
            "corroborate or widen the comp set before quoting"
        ),
    }


def adjust_comp_to_subject(comp: dict, subject: dict, adjustments: dict,
                           assess_date: str) -> dict | None:
    """Apply the derived coefficients to bring one comp to the subject:
    adjusted = comp_price + Σ coef × (subject − comp). Returns the adjusted price
    and the per-element adjustment breakdown, or None when inputs are missing."""
    assess_year = int(str(assess_date)[:4])
    assess_days = _days(assess_date)
    age_basis = adjustments.get("age_basis", "year_built")
    # Normalize the subject (parcel_acres/living_area_sf) into comp shape
    # (lot_acres/sf) and stamp it as a notional sale at the effective date so the
    # shared row builder can read it.
    subj_norm = {
        **subject,
        "sf": subject.get("sf") or subject.get("living_area_sf"),
        "lot_acres": subject.get("lot_acres") or subject.get("parcel_acres"),
        "sale_price": 1,
        "sale_date": assess_date,
    }
    cr = _row(comp, assess_days, age_basis, assess_year) if assess_days is not None else None
    sr = _row(subj_norm, assess_days, age_basis, assess_year) if assess_days is not None else None
    if cr is None or sr is None:
        return None
    comp_x, comp_price = cr
    subj_x, _ = sr
    c = adjustments["coefficients"]
    keys = ["size_per_sf", "age_per_year", "lot_per_lot_sf", "time_per_month"]
    breakdown = {}
    total = 0.0
    for i, key in enumerate(keys):
        delta = subj_x[i] - comp_x[i]
        adj = c[key]["value"] * delta
        breakdown[key] = round(adj)
        total += adj
    return {
        "comp_pid": comp.get("pid"),
        "comp_sale_price": comp_price,
        "adjustments": breakdown,
        "adjusted_price": round(comp_price + total),
        "gross_adjustment_pct": round(sum(abs(v) for v in breakdown.values()) / comp_price * 100, 1)
        if comp_price else None,
    }
