"""End-to-end tests for scripts/build_packet.py — the deterministic assembler.

These lock in the property the whole refactor exists to guarantee: a packet is
built from a vetted judgment.json with the conclusion DERIVED in code (median of
the central comps), not hand-typed — and every framework section renders.
"""
import json
from pathlib import Path

import pytest

from scripts.build_packet import build_packet
from report.appeal_generator import generate_appeal_report
from report.shared_components import extraction_comp_indication

FIXTURE = Path(__file__).parent.parent / "properties" / "fulham" / "judgment.json"


@pytest.fixture
def judgment():
    return json.loads(FIXTURE.read_text())


def test_fulham_fixture_present():
    assert FIXTURE.exists(), "the Fulham judgment fixture must exist as the worked example"


def test_conclusion_is_derived_median_of_central(judgment):
    data = build_packet(judgment)
    n = data["_numbers"]
    # Re-derive independently and confirm the builder used the median of the
    # central comps (not a hand-typed value).
    central = [c for c in judgment["comps"] if c.get("role") == "central"]
    inds = sorted(
        extraction_comp_indication(c, judgment["subject"]["absf"], judgment["subject"]["land"],
                                   judgment["rates"]["bsmt_psf"], judgment["rates"]["gar_psf"],
                                   judgment["rates"]["econ_psf_per_sf"])["indicated_value"]
        for c in central)
    expected = round(inds[len(inds) // 2] / 1000.0) * 1000
    assert n["concluded"] == expected == 435000
    assert n["concluded_mean"] == 427000
    # Conclusion must equal the sales-indicated value the grid renders.
    assert data["sales_indicated_value"] == n["concluded"]


def test_ceiling_comp_excluded_from_central_tendency(judgment):
    """The renovated comp is the upper bracket, never in the median."""
    data = build_packet(judgment)
    assert data["_numbers"]["ceiling_value"] is not None
    assert data["_numbers"]["ceiling_value"] > data["_numbers"]["concluded"]


def test_context_comp_in_sales_table_not_in_grid(judgment):
    """1829 Fulham (690 ABSF) appears in 4.1 for context but not in the grid."""
    data = build_packet(judgment)
    sales_addrs = {s["address"] for s in data["recent_sales"]}
    grid_addrs = {c["address"] for c in data["extraction_grid"]["comps"]}
    assert "1829 Fulham St" in sales_addrs
    assert "1829 Fulham St" not in grid_addrs


def test_reduction_and_savings_computed(judgment):
    data = build_packet(judgment)
    n = data["_numbers"]
    assert n["reduction"] == n["emv"] - n["concluded"]
    assert n["annual_savings"] == round(n["reduction"] * judgment["meta"]["tax_rate"])


def test_equalization_trend_derived(judgment):
    data = build_packet(judgment)
    assert data["equalization_indicated_value"] is not None
    assert data["building_emv_chart"]["trends"], "the neighborhood trend line must render"
    # The subject point is plotted at its assessed $/SF.
    assert data["building_emv_chart"]["subject_xy"]["y"] == 244


def test_full_render_has_every_section(judgment):
    html = generate_appeal_report(build_packet(judgment))
    for heading in ("Subject Property", "Assessment History", "Basis for Appeal",
                    "Sales Comparison Approach", "Equalization Support",
                    "Concluded Market Value"):
        assert f"<h2>{heading}</h2>" in html, f"missing section: {heading}"
    # Regression guards from the hand-tuning era.
    assert "$0/SF" not in html, "subject-row $0/SF bug must not reappear"
    assert "county's own data" not in html.lower(), "banned gotcha phrasing"


def test_narrative_numbers_are_consistent(judgment):
    """Templated narrative references the derived figures, so prose can't drift
    from the arithmetic."""
    data = build_packet(judgment)
    n = data["_numbers"]
    assert f"${n['concluded']:,}" in data["conclusion"]["narrative"]
    assert f"{n['reduction_pct']}%" in data["conclusion"]["narrative"]
