"""
Contract tests for analysis/killer_comp.py.

These pin the verdict logic the self-improvement loop corrected: a comp only
*supports* an appeal when it carries real over-assessment signal (it sold below
its OWN EMV, or its $/SF implies a materially lower subject value) — NOT merely
because it sits in a cheaper value tier. The original bug compared the comp's
sale to the SUBJECT's EMV and called any low sale "supports_appeal."
"""
from analysis.killer_comp import identify_killer_comp


def _subject(emv_total=400_000, absf=2000, **kw):
    return {"emv_total": emv_total, "absf": absf, "pid": "SUBJ", **kw}


def _comp(sale_price, emv_total, absf=2000, pid="C1", **kw):
    return {"sale_price": sale_price, "emv_total": emv_total, "absf": absf,
            "sf": absf, "pid": pid, **kw}


def test_empty_sales_returns_none():
    assert identify_killer_comp(_subject(), []) is None


def test_new_fields_are_present():
    """The loop added own-EMV ratio + implied-value fields; they must surface."""
    r = identify_killer_comp(_subject(), [_comp(350_000, 400_000)])
    assert "comp_own_emv_ratio" in r
    assert "implied_subject_value" in r
    assert "implied_vs_subject_emv_pct" in r
    assert "sale_vs_subject_emv_pct" in r
    assert "verdict" in r


def test_supports_appeal_when_comp_sold_below_its_own_emv():
    """Path (a): comp sold materially below its OWN EMV → real over-assessment."""
    # ratio = 350k/400k = 0.875 (< 0.93); implied = 350k (subject SF == comp SF).
    r = identify_killer_comp(_subject(), [_comp(350_000, 400_000)])
    assert r["verdict"] == "supports_appeal"
    assert r["comp_own_emv_ratio"] < 0.93


def test_supports_appeal_when_implied_subject_value_materially_lower():
    """Path (b): comp's $/SF implies the subject worth >10% under EMV."""
    # ratio 320k/350k = 0.914 (NOT < 0.93, NOT cheaper-tier); implied 320k = -20%.
    r = identify_killer_comp(_subject(emv_total=400_000, absf=2000),
                             [_comp(320_000, 350_000, absf=2000)])
    assert r["verdict"] == "supports_appeal"
    assert r["implied_vs_subject_emv_pct"] < -10


def test_cheaper_tier_comp_is_discount_not_supports_appeal():
    """THE REGRESSION GUARD. A comp that sold below the SUBJECT's EMV but at its
    OWN EMV (county assessed it correctly) is a cheaper tier, not an
    over-assessment signal — must be 'discount', never 'supports_appeal'."""
    # Comp sold 300k = its own EMV (ratio 1.0). Smaller home (1500 SF) so its
    # $/SF implies exactly the subject's EMV, not lower.
    r = identify_killer_comp(_subject(emv_total=400_000, absf=2000),
                             [_comp(300_000, 300_000, absf=1500)])
    assert r["verdict"] == "discount"
    assert r["verdict"] != "supports_appeal"
    # implied value is suppressed as unreliable for a cheaper-tier comp.
    assert r["implied_subject_value"] is None


def test_kills_appeal_when_comp_at_subject_emv():
    """Comp sold within ±5% of the subject's EMV → no angle."""
    r = identify_killer_comp(_subject(emv_total=400_000),
                             [_comp(405_000, 410_000)])
    assert r["verdict"] == "kills_appeal"


def test_confirms_fair_when_comp_brackets_subject_above_emv():
    """Comp sold >5% above subject EMV and implies subject at/above EMV."""
    r = identify_killer_comp(_subject(emv_total=400_000, absf=2000),
                             [_comp(460_000, 450_000, absf=2000)])
    assert r["verdict"] == "confirms_fair"


def test_highest_similarity_comp_wins_selection():
    """Selection is by similarity score; the closest-matching comp is chosen."""
    subject = _subject(emv_total=400_000, absf=2000, year_built=1990,
                       lat=44.95, lon=-93.15)
    near = _comp(350_000, 400_000, absf=2010, pid="NEAR",
                 year_built=1990, lat=44.95, lon=-93.15)
    far = _comp(355_000, 400_000, absf=1200, pid="FAR",
                year_built=1955, lat=45.20, lon=-93.40)
    r = identify_killer_comp(subject, [far, near])
    assert r["comp"]["pid"] == "NEAR"
