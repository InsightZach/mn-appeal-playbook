"""
Sales regression analysis: $/SF over time with IQR outlier removal
and multi-model convergence verdict.

Used to predict a subject's market value at the assessment date from
neighborhood sales history. Complements the equalization module, which
regresses assessed values by size.
"""

import statistics
from datetime import date

_EPOCH = date(1970, 1, 1)


def _to_day_number(iso_date: str) -> int:
    """Convert an ISO date string to days since the unix epoch."""
    return (date.fromisoformat(iso_date) - _EPOCH).days


def compute_sales_trend(
    sales: list[dict],
    date_key: str = "date",
    value_key: str = "psf",
) -> dict:
    """
    Linear regression of a value over time.

    Dates are converted to days-since-unix-epoch so slope is in
    units of (value per day). Consumers should use
    `predict_at_assessment_date` to evaluate the trend at a future date.

    Args:
        sales: list of dicts with ISO date strings under date_key and
            numeric values under value_key
        date_key: dict key for the ISO date string (default "date")
        value_key: dict key for the numeric value (default "psf")
    Returns:
        {"slope": float, "intercept": float, "r2": float, "n": int}
    """
    xy: list[tuple[float, float]] = []
    for s in sales:
        d = s.get(date_key)
        v = s.get(value_key)
        if d is None or v is None:
            continue
        xy.append((float(_to_day_number(d)), float(v)))
    return _linear_regression(xy)


def remove_outliers_iqr(
    items: list[dict],
    key: str,
    k: float = 1.5,
) -> list[dict]:
    """
    Standard IQR outlier removal.

    Computes Q1 and Q3 via `statistics.quantiles(..., method='inclusive')`
    (linear interpolation, consistent with numpy's default) and excludes
    any item whose value at `key` falls outside [Q1 - k*IQR, Q3 + k*IQR].

    Args:
        items: list of dicts
        key: dict key whose values are used for the outlier test
        k: IQR multiplier (default 1.5)
    Returns:
        Filtered list preserving original order.
    """
    values = [item[key] for item in items if item.get(key) is not None]
    if len(values) < 4:
        return list(items)
    q1, _q2, q3 = statistics.quantiles(values, n=4, method="inclusive")
    iqr = q3 - q1
    low = q1 - k * iqr
    high = q3 + k * iqr
    return [
        item
        for item in items
        if item.get(key) is not None and low <= item[key] <= high
    ]


def predict_at_assessment_date(trend: dict, assessment_date: str) -> float:
    """
    Apply a trend produced by `compute_sales_trend` to a target date.

    Uses the same days-since-unix-epoch x-axis as the fit, so the
    returned value is in the same units as the original value_key (e.g. $/SF).
    """
    x = float(_to_day_number(assessment_date))
    return trend["slope"] * x + trend["intercept"]


def multi_model_convergence(
    models: dict[str, dict],
    target_date: str,
    subject_sf: float,
) -> dict:
    """
    Evaluate multiple sales-trend models at a target date and measure convergence.

    Each model is a trend dict (slope/intercept/r2) as produced by
    `compute_sales_trend`. For each model we predict $/SF at `target_date`,
    multiply by `subject_sf` to get a dollar value, then report the spread
    across models.

    Args:
        models: mapping of model name -> trend dict
        target_date: ISO date string (assessment date)
        subject_sf: subject building SF to scale $/SF into dollars
    Returns:
        {
            "values": {model_name: dollar_value, ...},
            "spread_pct": float,  # (max - min) / mean * 100
            "central": float,     # mean of values
            "verdict": "tight" | "loose",
        }
    """
    values: dict[str, float] = {}
    for name, trend in models.items():
        psf = predict_at_assessment_date(trend, target_date)
        values[name] = psf * subject_sf

    if not values:
        return {
            "values": {},
            "spread_pct": 0.0,
            "central": 0.0,
            "verdict": "loose",
        }

    vs = list(values.values())
    central = sum(vs) / len(vs)
    spread_pct = ((max(vs) - min(vs)) / central * 100) if central else 0.0
    verdict = "tight" if spread_pct < 5 else "loose"
    result = {
        "values": values,
        "spread_pct": spread_pct,
        "central": central,
        "verdict": verdict,
    }
    # A single model (or a trivially-tight spread ~0) is a directional screen
    # over all comp sizes, NOT a reconciled, size-matched sales indication. The
    # central figure mixes small high-$/SF homes into a whole-neighborhood
    # average and can run high; de-rate it and label so a reader cannot adopt it
    # as the defensible ask. Reconcile size-matched comps per appeal-packet.md.
    if len(values) < 2 or spread_pct < 0.5:
        result["central_label"] = (
            "single regression model over all sizes — directional screen only, not a "
            "reconciled sales value; reconcile size-matched comps per appeal-packet.md"
        )
    return result


def compute_psf_from_sale(
    sale: dict,
    subject_sf_override: float | None = None,
) -> float:
    """
    Compute $/SF for a sale record.

    Uses `subject_sf_override` when provided (e.g., to hold SF constant across
    peer sales), otherwise falls back to the sale's own `sf`. Returns 0 if SF
    is missing or zero to avoid ZeroDivisionError.
    """
    price = sale.get("sale_price", 0) or 0
    sf = subject_sf_override if subject_sf_override is not None else sale.get("sf", 1)
    if not sf:
        return 0.0
    return price / sf


def _linear_regression(xy: list[tuple[float, float]]) -> dict:
    """Ordinary least squares; inlined to avoid coupling to equalization.py."""
    n = len(xy)
    if n < 2:
        return {"slope": 0, "intercept": 0, "r2": 0, "n": n}
    sx = sum(x for x, _ in xy)
    sy = sum(y for _, y in xy)
    sxy = sum(x * y for x, y in xy)
    sxx = sum(x * x for x, _ in xy)
    denom = n * sxx - sx * sx
    if denom == 0:
        return {"slope": 0, "intercept": sy / n, "r2": 0, "n": n}
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    mean_y = sy / n
    ss_tot = sum((y - mean_y) ** 2 for _, y in xy)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in xy)
    r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
    return {"slope": slope, "intercept": intercept, "r2": r2, "n": n}
