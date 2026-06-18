"""Appeal Package report generator.

Renders a self-contained HTML appeal package using the shared component
renderers in `report/shared_components.py`. The caller passes a single dict
with optional keys; sections only render when their data is present.

Public entry point: `generate_appeal_report(data: dict) -> str`.
"""

from __future__ import annotations

import html
from pathlib import Path

from report import shared_components as sc


# -- Internal helpers -----------------------------------------------------


_PRINT_CSS_PATH = Path(__file__).parent / "print_styles.css"


def _load_print_css() -> str:
    try:
        return _PRINT_CSS_PATH.read_text()
    except OSError:
        return ""


def _esc(value) -> str:
    if value is None or value == "":
        return ""
    return html.escape(str(value))


def _money(value) -> str:
    if value is None or value == "":
        return "—"
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return "—"


def _section(html_str: str) -> str:
    return f"<section>{html_str}</section>"


# -- Section builders -----------------------------------------------------


def _build_header(subject: dict, meta: dict) -> str:
    address = subject.get("address") or "Subject Property"
    pid = subject.get("pid") or ""
    assess_year = meta.get("assessment_year")
    pay_year = meta.get("payable_year")
    bits = []
    if assess_year and pay_year:
        bits.append(f"Assessment {assess_year}, payable {pay_year}")
    elif assess_year:
        bits.append(f"Assessment {assess_year}")
    if pid:
        bits.append(f"PID {pid}")
    subtitle = " · ".join(bits) if bits else address
    title = meta.get("report_title") or "Assessment Appeal Review"
    brand = meta.get("brand") or "Residential Property Tax Appeal"
    return sc.render_branded_header(title, subtitle, brand=brand)


def _build_subject_section(data: dict) -> str:
    subject = data.get("subject") or {}
    beacon = data.get("beacon_subject")
    corrections = data.get("corrections")
    photos = data.get("condition_photos")

    parts = ["<h2>Subject Property</h2>"]
    parts.append(sc.render_subject_card(subject, beacon, corrections))
    if photos:
        parts.append("<h3>Actual Condition</h3>")
        parts.append(sc.render_photo_grid(photos, compact=False))
    return _section("".join(parts))


def _yoy_note(assessments: list[dict]) -> str:
    """One-line plain-language YoY summary if there are at least 2 years."""
    if not assessments or len(assessments) < 2:
        return ""

    def _key(a):
        return a.get("assess_year") or a.get("tax_year") or 0

    rows = sorted(assessments, key=_key)
    first = rows[0].get("emv_total")
    last = rows[-1].get("emv_total")
    try:
        first_f = float(first)
        last_f = float(last)
        if first_f <= 0:
            return ""
        delta = last_f - first_f
        pct = delta / first_f * 100
        direction = "up" if delta >= 0 else "down"
        return (
            f'<p style="margin:0.4rem 0 0;color:#555;font-size:0.95em;">'
            f"EMV is {direction} {abs(pct):.1f}% "
            f"(${abs(delta):,.0f}) over the period shown.</p>"
        )
    except (TypeError, ValueError):
        return ""


def _build_assessment_section(data: dict) -> str:
    assessments = data.get("assessments")
    if not assessments:
        return ""
    parts = [
        "<h2>Assessment History</h2>",
        sc.render_assessment_history_table(assessments),
        _yoy_note(assessments),
    ]
    return _section("".join(parts))


def _build_basis_section(data: dict) -> str:
    items = data.get("basis_for_appeal") or data.get("points_for_discussion")
    if not items:
        return ""
    heading = (
        "Points for Discussion"
        if data.get("points_for_discussion") or data.get("discussion_mode")
        else "Basis for Appeal"
    )
    intro = data.get("discussion_intro")
    parts = [f"<h2>{heading}</h2>"]
    if intro:
        parts.append(f'<p style="margin:0.3rem 0 0.8rem;">{_esc(intro)}</p>')
    for item in items:
        title = item.get("title") or ""
        body = item.get("body") or ""
        color = item.get("color") or "amber"
        parts.append(sc.render_finding_callout(title, body, color))
    return _section("".join(parts))


def _build_neighbor_card(subject: dict, neighbor: dict) -> str:
    """Side-by-side subject vs neighbor (same lot, different assessment)."""
    s_emv = subject.get("emv_total")
    n_emv = neighbor.get("emv_total")
    s_sf = subject.get("living_area_sf") or subject.get("absf")
    n_sf = neighbor.get("living_area_sf") or neighbor.get("absf")

    def _psf(emv, sf):
        try:
            if emv and sf and float(sf) > 0:
                return f"${float(emv) / float(sf):,.0f}"
        except (TypeError, ValueError):
            pass
        return "—"

    s_psf = _psf(s_emv, s_sf)
    n_psf = _psf(n_emv, n_sf)

    delta_html = "—"
    try:
        if s_emv is not None and n_emv is not None:
            delta = float(s_emv) - float(n_emv)
            sign = "+" if delta >= 0 else "−"
            delta_html = f"{sign}${abs(delta):,.0f}"
    except (TypeError, ValueError):
        pass

    rows = [
        ("PID", subject.get("pid"), neighbor.get("pid")),
        ("Address", subject.get("address"), neighbor.get("address")),
        ("Year Built", subject.get("year_built"), neighbor.get("year_built")),
        ("Living Area", _esc(s_sf), _esc(n_sf)),
        ("Lot Size", subject.get("lot_acres"), neighbor.get("lot_acres")),
        ("EMV Total", _money(s_emv), _money(n_emv)),
        ("$/SF (EMV ÷ SF)", s_psf, n_psf),
    ]

    body_rows = []
    for label, sv, nv in rows:
        body_rows.append(
            f'<tr><td style="background:{sc.LIGHT};color:{sc.NAVY};'
            f'font-weight:600;padding:6pt 8pt;border-bottom:1px solid {sc.BORDER};">'
            f"{_esc(label)}</td>"
            f'<td style="padding:6pt 8pt;border-bottom:1px solid {sc.BORDER};'
            f'background:#fff9e6;color:{sc.NAVY};font-weight:600;">{_esc(sv) or "—"}</td>'
            f'<td style="padding:6pt 8pt;border-bottom:1px solid {sc.BORDER};">'
            f'{_esc(nv) or "—"}</td></tr>'
        )

    return (
        f'<div class="card" style="background:{sc.WHITE};border:1px solid {sc.BORDER};'
        f'border-radius:6px;padding:1rem 1.25rem;margin:1rem 0;">'
        f'<table style="width:100%;border-collapse:collapse;font-size:0.95em;">'
        f'<thead><tr>'
        f'<th style="background:{sc.LIGHT};color:{sc.NAVY};text-align:left;'
        f'padding:8pt;">Field</th>'
        f'<th style="background:{sc.GOLD};color:{sc.NAVY};text-align:left;'
        f'padding:8pt;">Subject</th>'
        f'<th style="background:{sc.NAVY};color:{sc.WHITE};text-align:left;'
        f'padding:8pt;">Neighbor</th>'
        f"</tr></thead>"
        f'<tbody>{"".join(body_rows)}</tbody></table>'
        f'<p style="margin:0.6rem 0 0;color:#555;font-size:0.92em;">'
        f"EMV gap subject vs neighbor: <strong>{delta_html}</strong>. "
        f"Same lot configuration, different assessment.</p>"
        f"</div>"
    )


def _build_sales_comparison_section(data: dict) -> str:
    """Section 4: Sales Comparison Approach (primary valuation method).

    Unifies the sales comp table, adjustment schedule, adjustment grid,
    reconciliation paragraph, and approach-closer card.
    """
    subject = data.get("subject") or {}
    recent_sales = data.get("recent_sales")
    adjustment_schedule = data.get("adjustment_schedule")
    adjustment_grid = data.get("adjustment_grid")
    extraction_grid = data.get("extraction_grid")
    sales_recon = data.get("sales_reconciliation")
    sales_indicated = data.get("sales_indicated_value")

    has_any = any([recent_sales, adjustment_schedule, adjustment_grid, extraction_grid])
    if not has_any:
        return ""

    parts = ["<h2>Sales Comparison Approach</h2>"]
    subtitle = data.get("sales_subtitle") or (
        "Primary valuation method. Closed sales adjusted to the subject on a "
        "percentage-of-sale-price basis."
    )
    parts.append(sc.render_section_subtitle(subtitle))

    if recent_sales:
        parts.append("<h3>4.1 &nbsp; Closed Sales</h3>")
        sales_intro = data.get("sales_intro")
        if sales_intro:
            parts.append(f'<p style="margin:0.3rem 0;">{_esc(sales_intro)}</p>')
        cols = list(sc._DEFAULT_COMP_COLUMNS)
        if any(s.get("distance_mi") is not None for s in recent_sales):
            cols.append("distance_mi")
        parts.append(sc.render_comp_table(recent_sales, subject, columns=cols))

    if adjustment_schedule:
        parts.append("<h3>4.2 &nbsp; Adjustment Schedule</h3>")
        schedule_intro = data.get("adjustment_schedule_intro") or (
            "Each adjustment is expressed as a <strong>percentage of sale "
            "price</strong>. Percentages are additive and applied to each "
            "comp's raw sale price in the grid below."
        )
        parts.append(f'<p style="margin:0.3rem 0;">{schedule_intro}</p>')
        parts.append(sc.render_adjustment_schedule(adjustment_schedule))

    if adjustment_grid:
        parts.append("<h3>4.3 &nbsp; Adjustment Grid</h3>")
        excluded = data.get("adjustment_grid_excluded_note") or ""
        grid_subject_sf = data.get("adjustment_grid_subject_sf")
        parts.append(sc.render_adjustment_grid(
            adjustment_grid, excluded_note=excluded, subject_sf=grid_subject_sf))

    if extraction_grid:
        # Above-grade extraction grid — for a subject whose lot/basement/garage differ
        # from the comps (a flat %-of-sale grid would blow up the lot line).
        parts.append("<h3>4.3 &nbsp; Adjustment Grid (above-grade basis)</h3>")
        parts.append(sc.render_extraction_grid(
            extraction_grid.get("comps") or [],
            extraction_grid.get("subject_absf"),
            extraction_grid.get("subject_land"),
            bsmt_psf=extraction_grid.get("bsmt_psf", 50.0),
            gar_psf=extraction_grid.get("gar_psf", 30.0),
            econ_psf_per_sf=extraction_grid.get("econ_psf_per_sf", 0.06),
            note=extraction_grid.get("note", ""),
            subject_fin_bsmt_sf=extraction_grid.get("subject_fin_bsmt_sf", 0.0),
            subject_garage_sf=extraction_grid.get("subject_garage_sf", 0.0),
        ))

    if sales_recon:
        parts.append("<h3>4.4 &nbsp; Reconciliation</h3>")
        parts.append(f'<p style="margin:0.3rem 0;">{sales_recon}</p>')

    if sales_indicated is not None:
        parts.append(
            sc.render_approach_close("Sales Comparison Approach", sales_indicated)
        )

    return _section("".join(parts))


def _build_equalization_section(data: dict) -> str:
    """Section 5: Equalization Support (cross-check against county data)."""
    neighbor = data.get("neighbor")
    equalization_table = data.get("equalization_table")
    equalization_grid = data.get("equalization_grid")
    # The land $/SF scatter: a `land_psf_chart` (from the land-value regression) or the
    # legacy `equalization` chart dict — same {data, subject_xy, trends, caption} shape.
    equalization = data.get("land_psf_chart") or data.get("equalization")
    building_emv_chart = data.get("building_emv_chart")
    land_observation = data.get("land_value_observation")
    building_observation = data.get("building_value_observation")
    eq_indicated = data.get("equalization_indicated_value")
    eq_note = data.get("equalization_indicated_note")

    has_any = any([
        neighbor,
        equalization_table,
        equalization_grid,
        equalization,
        building_emv_chart,
        land_observation,
        building_observation,
    ])
    if not has_any:
        return ""

    subject = data.get("subject") or {}
    parts = ["<h2>Equalization Support</h2>"]
    subtitle = data.get("equalization_subtitle") or (
        "Cross-check against the county's own assessment data for "
        "neighborhood comparables."
    )
    parts.append(sc.render_section_subtitle(subtitle))

    section_num = 1
    if equalization_grid:
        # Assessed land + building $/SF grid: the subject vs its neighborhood peers
        # on the county's own values (the Federated Mutual basis).
        parts.append(
            f"<h3>5.{section_num} &nbsp; Equalization Table &mdash; "
            f"Subject vs. Neighborhood Comparables (assessed $/SF)</h3>"
        )
        eq_grid_intro = data.get("equalization_grid_intro")
        if eq_grid_intro:
            parts.append(f'<p style="margin:0.3rem 0;">{_esc(eq_grid_intro)}</p>')
        parts.append(sc.render_equalization_table(equalization_grid, subject))
        section_num += 1

    if equalization_table:
        parts.append(
            f"<h3>5.{section_num} &nbsp; Equalization Table &mdash; "
            f"Subject vs. Neighborhood Comparables</h3>"
        )
        eq_intro = data.get("equalization_table_intro")
        if eq_intro:
            parts.append(f'<p style="margin:0.3rem 0;">{_esc(eq_intro)}</p>')
        cols = data.get("equalization_table_columns")
        parts.append(sc.render_comp_table(equalization_table, subject, columns=cols))
        section_num += 1
    elif neighbor:
        parts.append(f"<h3>5.{section_num} &nbsp; Direct Neighbor Comparison</h3>")
        parts.append(_build_neighbor_card(subject, neighbor))
        section_num += 1

    if land_observation or equalization:
        heading_title = "Land Value"
        if isinstance(land_observation, dict):
            target = land_observation.get("target")
            if target:
                heading_title += f" &mdash; Target {_money(target)}"
            body = land_observation.get("body") or ""
            parts.append(f"<h3>5.{section_num} &nbsp; {heading_title}</h3>")
            if body:
                parts.append(sc.render_finding_callout("", body, color="amber"))
        elif land_observation:
            parts.append(f"<h3>5.{section_num} &nbsp; {heading_title}</h3>")
            parts.append(
                sc.render_finding_callout("", land_observation, color="amber")
            )
        else:
            parts.append(f"<h3>5.{section_num} &nbsp; Land $/SF Trend</h3>")
        if equalization:
            parts.append(
                sc.render_equalization_scatter_svg(
                    equalization.get("data") or [],
                    equalization.get("subject_xy") or {},
                    equalization.get("trends") or [],
                    x_label=equalization.get("x_label", "Lot size (SF)"),
                )
            )
            caption = equalization.get("caption")
            if caption:
                parts.append(
                    f'<p style="font-size:0.85rem;color:#666;">{_esc(caption)}</p>'
                )
        section_num += 1

    if building_observation or building_emv_chart:
        heading_title = "Building Value"
        if isinstance(building_observation, dict):
            target = building_observation.get("target")
            if target:
                heading_title += f" &mdash; Target {_money(target)}"
            body = building_observation.get("body") or ""
            parts.append(f"<h3>5.{section_num} &nbsp; {heading_title}</h3>")
            if body:
                parts.append(sc.render_finding_callout("", body, color="red"))
        elif building_observation:
            parts.append(f"<h3>5.{section_num} &nbsp; {heading_title}</h3>")
            parts.append(
                sc.render_finding_callout("", building_observation, color="red")
            )
        else:
            parts.append(f"<h3>5.{section_num} &nbsp; Building EMV Trend</h3>")
        if building_emv_chart:
            parts.append(
                sc.render_equalization_scatter_svg(
                    building_emv_chart.get("data") or [],
                    building_emv_chart.get("subject_xy") or {},
                    building_emv_chart.get("trends") or [],
                    x_label=building_emv_chart.get("x_label", "Above-grade SF"),
                )
            )
            caption = building_emv_chart.get("caption")
            if caption:
                parts.append(
                    f'<p style="font-size:0.85rem;color:#666;">{_esc(caption)}</p>'
                )

    if eq_indicated is not None:
        parts.append(
            sc.render_approach_close(
                "Equalization Support", eq_indicated, note=eq_note or ""
            )
        )

    return _section("".join(parts))


def _build_beacon_section(data: dict) -> str:
    """Beacon card comparison — rendered as its own small section if present."""
    beacon_subject = data.get("beacon_subject")
    beacon_comps = data.get("beacon_comps")
    if not (beacon_subject and beacon_comps):
        return ""
    parts = [
        "<h2>Beacon Record Comparison</h2>",
        sc.render_beacon_comparison_table(beacon_subject, beacon_comps),
    ]
    return _section("".join(parts))


def _build_cost_to_cure_section(data: dict) -> str:
    """Section 6: Cost-to-Cure Exhibit + EMV Cross-Check.

    Uses new single-value itemization when `cost_to_cure_itemized` is present.
    Falls back to legacy low/high `condition_deductions` otherwise.
    """
    itemized = data.get("cost_to_cure_itemized")
    cross_check = data.get("emv_cross_check")
    legacy = data.get("condition_deductions")

    if not (itemized or cross_check or (legacy and legacy.get("items"))):
        return ""

    parts = ["<h2>Cost-to-Cure Exhibit</h2>"]
    subtitle = data.get("cost_to_cure_subtitle") or (
        "Itemized single-value estimates for the repair and update scope "
        "required to bring the subject to an &ldquo;Average&rdquo; condition grade."
    )
    parts.append(sc.render_section_subtitle(subtitle))

    if itemized:
        parts.append(sc.render_cost_to_cure_itemized(itemized))
    elif legacy and legacy.get("items"):
        # Legacy fallback: convert low/high → midpoint single values
        items = []
        for it in legacy.get("items") or []:
            lo = it.get("low") or 0
            hi = it.get("high") or lo
            try:
                amt = (float(lo) + float(hi)) / 2
            except (TypeError, ValueError):
                amt = lo
            items.append({"description": it.get("description"), "amount": amt})
        parts.append(sc.render_cost_to_cure_itemized(items))

    if cross_check:
        parts.append("<h3>EMV Cross-Check</h3>")
        intro = cross_check.get("intro") or (
            "Applying the two concrete adjustments from this report directly "
            "to the county's current EMV:"
        )
        parts.append(f'<p style="margin:-0.3rem 0 0.3rem;">{_esc(intro)}</p>')
        parts.append(
            sc.render_emv_cross_check(
                cross_check.get("current_emv"),
                cross_check.get("land_adjustment"),
                cross_check.get("cost_to_cure"),
                label=cross_check.get("label") or "Cross-check value",
            )
        )
        note = cross_check.get("note")
        if note:
            parts.append(
                f'<p style="font-size:0.85rem;color:#555;margin-top:0.4rem;">'
                f"{_esc(note)}</p>"
            )

    return _section("".join(parts))


def _build_final_conclusion_section(data: dict) -> str:
    """Section 7: Concluded Market Value with reconciliation table + final box."""
    conclusion = data.get("conclusion") or {}
    reconciliation = data.get("reconciliation")
    subject = data.get("subject") or {}
    meta = data.get("meta") or {}

    # Require at least conclusion data to render this section
    if not (
        conclusion
        or reconciliation
        or data.get("concluded_value")
    ):
        return ""

    parts = ["<h2>Concluded Market Value</h2>"]
    subtitle = data.get("conclusion_subtitle") or (
        "Reconciled indication from the approaches above."
    )
    parts.append(sc.render_section_subtitle(subtitle))

    if reconciliation:
        parts.append(sc.render_reconciliation_table(reconciliation))

    parts.append(_build_final_value_box(conclusion, subject, meta))

    return _section("".join(parts))


def _build_final_value_box(conclusion: dict, subject: dict, meta: dict) -> str:
    """Navy/gold final value card. Supports both single concluded_value and
    legacy final_low/final_high range.
    """
    concluded = conclusion.get("concluded_value") or conclusion.get("final_value")
    final_low = conclusion.get("final_low")
    final_high = conclusion.get("final_high")
    land = conclusion.get("land_value")
    building = conclusion.get("building_value")
    narrative = conclusion.get("narrative")
    current_emv = subject.get("emv_total")

    # Headline value
    if concluded is not None:
        value_line = _money(concluded)
    elif final_low is not None and final_high is not None:
        value_line = f"{_money(final_low)} &ndash; {_money(final_high)}"
    elif final_low is not None:
        value_line = _money(final_low)
    else:
        return ""

    # Stats grid (EMV, concluded, land/building split if available)
    stat_cells = []
    if current_emv is not None:
        stat_cells.append(
            f'<div class="stat" style="background:rgba(255,255,255,0.1);'
            f'padding:0.6rem;text-align:center;border-radius:6px;">'
            f'<div class="value" style="font-size:1.3rem;font-weight:700;'
            f'color:{sc.GOLD};">{_money(current_emv)}</div>'
            f'<div class="label" style="color:#aab;font-size:0.78rem;">'
            f"Current EMV</div></div>"
        )
    stat_cells.append(
        f'<div class="stat" style="background:rgba(255,255,255,0.1);'
        f'padding:0.6rem;text-align:center;border-radius:6px;">'
        f'<div class="value" style="font-size:1.3rem;font-weight:700;'
        f'color:{sc.GOLD};">{value_line}</div>'
        f'<div class="label" style="color:#aab;font-size:0.78rem;">'
        f"Concluded market value</div></div>"
    )
    if land is not None and building is not None:
        stat_cells.append(
            f'<div class="stat" style="background:rgba(255,255,255,0.1);'
            f'padding:0.6rem;text-align:center;border-radius:6px;">'
            f'<div class="value" style="font-size:1.3rem;font-weight:700;'
            f'color:{sc.GOLD};">{_money(land)}&nbsp;/&nbsp;{_money(building)}</div>'
            f'<div class="label" style="color:#aab;font-size:0.78rem;">'
            f"Land / building split</div></div>"
        )

    stats_html = (
        f'<div class="stats" style="display:grid;'
        f"grid-template-columns:repeat(auto-fit,minmax(150px,1fr));"
        f'gap:0.6rem;margin-top:1rem;">{"".join(stat_cells)}</div>'
    )

    narrative_html = (
        f'<p style="margin-top:1rem;color:#dde;font-size:0.95rem;">'
        f"{narrative}</p>"
        if narrative
        else ""
    )

    # Meta line (assessment date / petition deadline)
    assess_date = (
        conclusion.get("assessment_date")
        or meta.get("assessment_date_iso")
    )
    pet_deadline = (
        conclusion.get("petition_deadline")
        or meta.get("petition_deadline_iso")
    )
    meta_bits = []
    if assess_date:
        meta_bits.append(f"<strong>Assessment date:</strong> {_esc(assess_date)}")
    if pet_deadline:
        meta_bits.append(
            f"<strong>Petition deadline:</strong> {_esc(pet_deadline)}"
        )
    meta_html = (
        f'<p style="margin-top:0.8rem;color:#aab;font-size:0.9rem;">'
        f'{" &nbsp;&middot;&nbsp; ".join(meta_bits)}</p>'
        if meta_bits
        else ""
    )

    # Tax savings (if available)
    tax_savings_html = ""
    tax_rate = (meta or {}).get("tax_rate")
    try:
        if (
            tax_rate is not None
            and current_emv is not None
            and concluded is not None
        ):
            savings = (float(current_emv) - float(concluded)) * float(tax_rate)
            if savings > 0:
                tax_savings_html = (
                    f'<p style="margin-top:0.4rem;color:#dde;font-size:0.9rem;">'
                    f"Implied annual tax savings: <strong>{_money(savings)}</strong>"
                    f"</p>"
                )
        elif (
            tax_rate is not None
            and current_emv is not None
            and final_low is not None
            and final_high is not None
        ):
            current_f = float(current_emv)
            savings_low = (current_f - float(final_high)) * float(tax_rate)
            savings_high = (current_f - float(final_low)) * float(tax_rate)
            tax_savings_html = (
                f'<p style="margin-top:0.4rem;color:#dde;font-size:0.9rem;">'
                f"Implied annual tax savings: "
                f"<strong>${savings_low:,.0f}&ndash;${savings_high:,.0f}</strong>"
                f"</p>"
            )
    except (TypeError, ValueError):
        pass

    return (
        f'<div class="conclusion" style="background:{sc.NAVY};color:{sc.WHITE};'
        f'padding:1.5rem 2rem;border-left:6px solid {sc.GOLD};margin:1rem 0;'
        f'border-radius:8px;">'
        f'<h3 style="color:{sc.GOLD};margin:0 0 0.4rem;">Concluded Market Value</h3>'
        f"{stats_html}"
        f"{narrative_html}"
        f"{tax_savings_html}"
        f"{meta_html}"
        f"</div>"
    )


def _build_map_section(data: dict) -> str:
    map_data = data.get("map_data")
    if not map_data:
        return ""
    subject = data.get("subject") or {}
    if subject.get("lat") is None or subject.get("lon") is None:
        return ""
    parts = ["<h2>Location Map</h2>"]
    parts.append(
        sc.render_static_map(
            subject,
            map_data.get("comps") or [],
            map_data.get("actives") or [],
        )
    )
    return _section("".join(parts))


# -- Public entry point ---------------------------------------------------


def generate_appeal_report(data: dict) -> str:
    """Render the Appeal Package HTML report.

    `data` is a single dict with optional keys; sections only render if their
    data exists. Required: `subject`. See module docstring of the appeal
    workflow for the full key list.
    """
    if not isinstance(data, dict) or not data.get("subject"):
        raise ValueError("generate_appeal_report requires data['subject']")

    subject = data.get("subject") or {}
    meta = data.get("meta") or {}
    address = subject.get("address") or "Subject Property"
    generated_at = meta.get("generated_at") or ""

    sections = [
        _build_header(subject, meta),
        _build_subject_section(data),
        _build_assessment_section(data),
        _build_basis_section(data),
        _build_sales_comparison_section(data),
        _build_equalization_section(data),
        _build_beacon_section(data),
        _build_cost_to_cure_section(data),
        _build_final_conclusion_section(data),
        _build_map_section(data),
    ]
    sections_html = "".join(s for s in sections if s)

    print_css = _load_print_css()
    title = f"Appeal Package — {html.escape(address)}"

    screen_css = (
        "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; "
        "color: #333; margin: 0; background: #f8f9fa; }\n"
        ".container { max-width: 1100px; margin: 0 auto; padding: 1.5rem 2rem; "
        "background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }\n"
        "section { margin-bottom: 2rem; }\n"
        f"h2 {{ color: {sc.NAVY}; border-bottom: 2px solid {sc.GOLD}; "
        "padding-bottom: 0.4rem; }\n"
        f"h3 {{ color: {sc.NAVY}; margin-top: 1.2rem; }}\n"
        f".conclusion {{ background: {sc.NAVY}; color: #fff; padding: 1.5rem 2rem; "
        f"border-left: 6px solid {sc.GOLD}; }}\n"
        f".conclusion .value {{ font-size: 2rem; color: {sc.GOLD}; font-weight: 700; }}\n"
        "table { border-collapse: collapse; width: 100%; }\n"
        "td { padding: 6pt 8pt; text-align: left; }\n"
        "th { padding: 6pt 8pt; text-align: left; font-weight: 600; }\n"
        ".footer { text-align: center; color: #666; font-size: 0.85em; "
        "padding: 1.5rem 0; border-top: 1px solid #e1e4e8; margin-top: 2rem; }\n"
    )

    footer_text = meta.get("brand") or "Residential Property Tax Appeal"
    if generated_at:
        footer_text += f" · Generated {html.escape(str(generated_at))}"

    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{title}</title>\n"
        f"<style>\n{screen_css}</style>\n"
        f"<style>\n{print_css}\n</style>\n"
        "</head>\n"
        "<body>\n"
        '<div class="container">\n'
        f"{sections_html}\n"
        f'<div class="footer">{footer_text}</div>\n'
        "</div>\n"
        "</body>\n"
        "</html>\n"
    )
