"""
Tests for the assessed building $/SF tier screen — the universal (cross-county)
quality/condition proxy that groups comps into the subject's value tier so the
$/SF median minimizes the least-supportable adjustment (condition/quality).

Contract: drop clear tier-offs (a $500/SF comp vs a $200/SF subject), keep
same-tier comps, never over-narrow (fall back below TIER_MIN_KEEP), and never
conclude value off the assessment (the screen only groups; sales value).
"""
from scripts.triage import _assessed_bpsf, _tier_screen, TIER_PSF_LO, TIER_PSF_HI


def _comp(emv_building, sf=2000, pid="C"):
    return {"pid": pid, "emv_building": emv_building, "sf": sf}


def test_assessed_bpsf_computes_and_is_none_safe():
    assert _assessed_bpsf({"emv_building": 280_000, "sf": 2000}) == 140.0
    assert _assessed_bpsf({"emv_building": None, "sf": 2000}) is None
    assert _assessed_bpsf({"emv_building": 280_000, "sf": 0}) is None
    # falls back to living_area_sf
    assert _assessed_bpsf({"emv_building": 200_000, "living_area_sf": 1000}) == 200.0


def test_drops_clear_higher_tier_comp():
    """$500/SF comp vs $200/SF subject → different tier → dropped."""
    subject_bpsf = 200.0
    # same-tier comps at ~$200/SF and one mansion at $500/SF
    same = [_comp(400_000, sf=2000, pid=f"s{i}") for i in range(5)]  # $200/SF
    mansion = _comp(1_000_000, sf=2000, pid="MANSION")            # $500/SF = 2.5x
    kept, dropped = _tier_screen(same + [mansion], subject_bpsf)
    assert dropped == 1
    assert all(c["pid"] != "MANSION" for c in kept)


def test_drops_clear_lower_tier_comp():
    """A teardown well below the subject's tier is dropped."""
    subject_bpsf = 200.0
    same = [_comp(400_000, sf=2000, pid=f"s{i}") for i in range(5)]  # $200/SF
    teardown = _comp(160_000, sf=2000, pid="TEARDOWN")              # $80/SF = 0.4x
    kept, dropped = _tier_screen(same + [teardown], subject_bpsf)
    assert dropped == 1
    assert all(c["pid"] != "TEARDOWN" for c in kept)


def test_keeps_same_tier_comps_including_moderately_below():
    """The band is WIDE — a comp moderately below the subject (the over-assessment
    signal lives here) is kept, only clear tier-offs are dropped."""
    subject_bpsf = 200.0
    comps = [
        _comp(360_000, sf=2000, pid="below"),   # $180/SF = 0.9x → kept
        _comp(440_000, sf=2000, pid="above"),   # $220/SF = 1.1x → kept
        _comp(560_000, sf=2000, pid="edge"),    # $280/SF = 1.4x → kept (< 1.5)
        _comp(400_000, sf=2000, pid="at"),      # $200/SF = 1.0x → kept
    ]
    kept, dropped = _tier_screen(comps, subject_bpsf)
    assert dropped == 0
    assert len(kept) == 4


def test_falls_back_rather_than_over_narrow():
    """If the screen would leave fewer than TIER_MIN_KEEP, keep the unscreened set
    (tier is the LAST dimension to relax — the expansion ladder) and report 0."""
    subject_bpsf = 200.0
    # only 2 same-tier; 3 mansions. Screening to 2 is below TIER_MIN_KEEP → fallback.
    comps = [_comp(400_000, pid=f"s{i}") for i in range(2)] + \
            [_comp(1_000_000, pid=f"m{i}") for i in range(3)]
    kept, dropped = _tier_screen(comps, subject_bpsf)
    assert dropped == 0
    assert len(kept) == 5  # unscreened — did not over-narrow


def test_no_subject_bpsf_is_a_noop():
    comps = [_comp(1_000_000, pid="m")]
    kept, dropped = _tier_screen(comps, None)
    assert dropped == 0 and kept == comps


def test_comps_without_assessed_psf_are_kept():
    """A comp missing emv_building isn't tier-screened (other gates handle it)."""
    subject_bpsf = 200.0
    comps = [_comp(400_000, pid=f"s{i}") for i in range(4)] + \
            [{"pid": "noemv", "sf": 2000}]  # no emv_building
    kept, dropped = _tier_screen(comps, subject_bpsf)
    assert any(c["pid"] == "noemv" for c in kept)


def test_band_constants_are_wide_and_symmetric_enough():
    """Guard the circularity intent: the band must stay coarse, not a narrow
    cuff around the subject's (disputed) assessment."""
    assert TIER_PSF_LO <= 0.67   # keeps comps well below the subject
    assert TIER_PSF_HI >= 1.40   # only drops clear higher tiers
