"""
Identify the single strongest comparable sale that the county would lead with
in defending the assessment.

This comp can either:
  - KILL the appeal (sold near or above the subject's assessment) → no-appeal report
  - SUPPORT the appeal (sold well below the subject's assessment) → appeal package
"""


def identify_killer_comp(subject: dict, sales: list[dict]) -> dict | None:
    """
    Score each sale on similarity to subject. Highest score wins.

    Score factors (weighted):
      - Above-grade SF similarity (40%)
      - Year built proximity (15%)
      - Lot size proximity (15%)
      - Same exterior material (10%)
      - Same style (10%)
      - Recency of sale (10%)

    Returns the top-scored sale plus its verdict:
      {
        "comp": {...},
        "score": 87.3,
        "verdict": "kills_appeal" | "supports_appeal" | "neutral",
        "delta_from_emv": -6700,
        "delta_pct": -0.86
      }

    "kills_appeal" if comp sold within ±5% of the subject's EMV.
    "supports_appeal" if comp sold below the subject's EMV by >10%.
    """
    if not sales:
        return None

    scored = []
    for s in sales:
        score = _similarity_score(subject, s)
        scored.append({"comp": s, "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[0]

    sale_price = top["comp"].get("sale_price", 0)
    emv = subject.get("emv_total", 0)
    if sale_price and emv:
        delta = sale_price - emv
        delta_pct = delta / emv * 100
        if abs(delta_pct) <= 5:
            verdict = "kills_appeal"
        elif delta_pct < -10:
            verdict = "supports_appeal"
        else:
            verdict = "neutral"
        top["verdict"] = verdict
        top["delta_from_emv"] = delta
        top["delta_pct"] = delta_pct

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
    # Recency (10%)
    # Closer to assessment date is better
    # ... (date math)
    return score
