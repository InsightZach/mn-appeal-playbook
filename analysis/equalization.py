"""
Equalization analysis: land/building $/SF regression with two trend lines
(all neighborhood data + hand-selected comps), apply to subject for implied values.

Used in both Appeal Package and No-Appeal Findings reports.
"""

def compute_land_psf_trend(points: list[dict]) -> dict:
    """
    Linear regression of land $/SF vs lot size.

    Args:
        points: list of {"lot_sf": float, "land": float}
    Returns:
        {"slope": float, "intercept": float, "r2": float, "n": int}
    """
    valid = [(p["lot_sf"], p["land"] / p["lot_sf"]) for p in points if p.get("lot_sf") and p.get("land")]
    return _linear_regression(valid)


def compute_building_psf_trend(points: list[dict]) -> dict:
    """Linear regression of building $/SF vs above-grade SF."""
    valid = [(p["sf"], p["bldg"] / p["sf"]) for p in points if p.get("sf") and p.get("bldg")]
    return _linear_regression(valid)


def apply_trend_to_subject(trend: dict, lot_sf: float | None = None, sf: float | None = None) -> tuple[float, float]:
    """
    Apply a $/SF trend line to the subject's lot or building size.
    Returns (predicted_psf, predicted_total_value).
    """
    x = lot_sf if lot_sf is not None else sf
    psf = trend["slope"] * x + trend["intercept"]
    return psf, psf * x


def identify_two_clusters(points: list[dict], threshold: float = 22) -> tuple[list, list]:
    """
    Split points into high and low clusters by land $/SF.
    Used when a neighborhood has two distinct platted value tiers.
    Returns (high_cluster, low_cluster).
    """
    high = [p for p in points if p["land"] / p["lot_sf"] >= threshold]
    low = [p for p in points if p["land"] / p["lot_sf"] < threshold]
    return high, low


def _linear_regression(xy: list[tuple[float, float]]) -> dict:
    n = len(xy)
    if n < 2:
        return {"slope": 0, "intercept": 0, "r2": 0, "n": n}
    sx = sum(x for x, _ in xy)
    sy = sum(y for _, y in xy)
    sxy = sum(x * y for x, y in xy)
    sxx = sum(x * x for x, _ in xy)
    slope = (n * sxy - sx * sy) / (n * sxx - sx * sx)
    intercept = (sy - slope * sx) / n
    mean_y = sy / n
    ss_tot = sum((y - mean_y) ** 2 for _, y in xy)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in xy)
    r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
    return {"slope": slope, "intercept": intercept, "r2": r2, "n": n}
