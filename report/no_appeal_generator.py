"""No-Appeal Findings report generator.

Renders a self-contained HTML findings report for cases where the analysis
does NOT support filing an appeal. This is a client-facing explanation of
the work performed and the data showing why the current assessment stands.

The tone is plain and evidence-driven — no sales pitch, no hedging.
Style guide (see `style_guide.md`) explicitly bans certain phrases and the
use of Zillow Zestimate as "independent validation".

Public entry point: `generate_no_appeal_report(data: dict) -> str`.
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


def _pct(value, places: int = 1) -> str:
    if value is None or value == "":
        return "—"
    try:
        return f"{float(value):+.{places}f}%"
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
    bits = [address]
    if assess_year and pay_year:
        bits.append(f"Assessment {assess_year}, payable {pay_year}")
    elif assess_year:
        bits.append(f"Assessment {assess_year}")
    if pid:
        bits.append(f"PID {pid}")
    subtitle = " · ".join(b for b in bits if b)
    return sc.render_branded_header("Property Assessment Findings", subtitle)


def _build_recommendation_section(data: dict) -> str:
    summary = data.get("summary") or {}
    headline = summary.get("headline") or "No appeal recommended this year"
    body = summary.get("body") or (
        "We looked at the data and don't see an angle. The current EMV "
        "lines up with recent sales and equalization comps."
    )
    return _section(sc.render_recommendation_box("no_appeal", headline, body))


def _build_subject_section(data: dict) -> str:
    subject = data.get("subject") or {}
    parts = ["<h2>Subject Property</h2>"]
    # Per style rule: no Zillow Zestimate row on this report.
    parts.append(sc.render_subject_card(subject, beacon=None, corrections=None))

    # Show ABSF / finished basement separately if present on subject.
    extras = []
    absf = subject.get("beacon_absf") or subject.get("absf")
    basement = subject.get("basement_finished")
    if absf:
        try:
            extras.append(f"ABSF (above grade): <strong>{float(absf):,.0f} SF</strong>")
        except (TypeError, ValueError):
            pass
    if basement:
        try:
            extras.append(
                f"Finished basement: <strong>{float(basement):,.0f} SF</strong>"
            )
        except (TypeError, ValueError):
            pass
    if extras:
        parts.append(
            '<p style="margin:0.4rem 0 0;color:#555;font-size:0.95em;">'
            + " · ".join(extras)
            + "</p>"
        )
    return _section("".join(parts))


def _filter_work_items(items: list[str]) -> list[str]:
    """Drop any item that mentions Zillow (case-insensitive)."""
    out = []
    for item in items or []:
        if not item:
            continue
        if "zillow" in str(item).lower():
            continue
        out.append(str(item))
    return out


def _build_work_completed_section(data: dict) -> str:
    raw = data.get("work_completed") or []
    items = _filter_work_items(raw)
    if not items:
        return ""
    checkmark = (
        f'<span style="display:inline-block;width:1.1em;color:{sc.NAVY};'
        f'font-weight:700;">&#9745;</span>'
    )
    li_html = "".join(
        f'<li style="list-style:none;padding:0.3rem 0;'
        f'border-bottom:1px dotted {sc.BORDER};">'
        f"{checkmark} {_esc(item)}</li>"
        for item in items
    )
    body = (
        "<h2>Work Completed</h2>"
        '<p style="margin:0.3rem 0 0.6rem;color:#555;">'
        "Here's what we looked at before reaching the recommendation above."
        "</p>"
        f'<ul style="margin:0.5rem 0;padding:0;">{li_html}</ul>'
    )
    return _section(body)


def _build_assessment_section(data: dict) -> str:
    assessments = data.get("assessments")
    if not assessments:
        return ""
    meta = data.get("meta") or {}
    parts = [
        "<h2>Assessment History</h2>",
        sc.render_assessment_history_table(assessments),
    ]
    note = meta.get("county_correction_note")
    if note:
        parts.append(
            f'<p style="margin:0.5rem 0 0;color:#555;font-size:0.93em;">'
            f"{_esc(note)}</p>"
        )
    return _section("".join(parts))


def _build_findings_section(data: dict) -> str:
    findings = data.get("findings")
    if not findings:
        return ""
    parts = ["<h2>Key Findings</h2>"]
    for f in findings:
        title = f.get("title") or ""
        body = f.get("body") or ""
        color = f.get("color") or "blue"
        parts.append(sc.render_finding_callout(title, body, color))
    return _section("".join(parts))


def _build_stat_summary_section(data: dict) -> str:
    stats = data.get("stat_summary")
    if not stats:
        return ""

    # Pick up to 4 cells to display as stat blocks.
    cell_specs = [
        ("properties_analyzed", "Properties analyzed"),
        ("sales_analyzed", "Sales analyzed"),
        ("models_run", "Regression models"),
        ("comps_reviewed", "Comps reviewed"),
        ("plats_analyzed", "Plats analyzed"),
        ("years_of_history", "Years of history"),
    ]
    cells = []
    for key, label in cell_specs:
        if key in stats and stats.get(key) not in (None, ""):
            cells.append((stats.get(key), label))
        if len(cells) >= 4:
            break

    stat_blocks = ""
    if cells:
        block_html = []
        for value, label in cells:
            try:
                display = f"{int(value):,}"
            except (TypeError, ValueError):
                display = _esc(value)
            block_html.append(
                f'<div style="flex:1;min-width:120px;text-align:center;'
                f'padding:0.9rem 0.6rem;background:{sc.LIGHT};'
                f'border:1px solid {sc.BORDER};border-radius:4px;">'
                f'<div style="font-size:1.75rem;font-weight:700;color:{sc.NAVY};'
                f'line-height:1.1;">{display}</div>'
                f'<div style="font-size:0.82em;color:#555;margin-top:0.25rem;'
                f'text-transform:uppercase;letter-spacing:0.05em;">{_esc(label)}</div>'
                f"</div>"
            )
        stat_blocks = (
            f'<div class="stats" style="display:flex;flex-wrap:wrap;gap:0.75rem;'
            f'margin:0.75rem 0;">{"".join(block_html)}</div>'
        )

    # Optional small summary table — any extra string fields in the dict.
    extra_rows = []
    for key, value in stats.items():
        if any(key == k for k, _ in cell_specs):
            continue
        if value in (None, ""):
            continue
        label = key.replace("_", " ").title()
        extra_rows.append(
            f'<tr><td style="padding:4pt 8pt;color:#555;'
            f'border-bottom:1px dotted {sc.BORDER};">{_esc(label)}</td>'
            f'<td style="padding:4pt 8pt;color:{sc.NAVY};font-weight:600;'
            f'border-bottom:1px dotted {sc.BORDER};">{_esc(value)}</td></tr>'
        )
    extra_table = ""
    if extra_rows:
        extra_table = (
            f'<table style="width:100%;max-width:480px;border-collapse:collapse;'
            f'font-size:0.92em;margin:0.5rem 0 0;">'
            f'<tbody>{"".join(extra_rows)}</tbody></table>'
        )

    body = "<h2>Statistical Summary</h2>" + stat_blocks + extra_table
    return _section(body)


def _build_plat_table_section(data: dict) -> str:
    plat_table = data.get("plat_table")
    if not plat_table:
        return ""

    cols = [
        ("plat_name", "Plat"),
        ("parcel_count", "Parcels"),
        ("median_emv", "Median EMV"),
        ("median_land_psf", "Land $/SF"),
        ("median_bldg_psf", "Bldg $/SF"),
        ("median_year_built", "Median year"),
    ]

    head = "".join(
        f'<th style="padding:8pt;text-align:left;background:{sc.NAVY};'
        f'color:{sc.WHITE};">{_esc(label)}</th>'
        for _, label in cols
    )

    rows = []
    for p in plat_table:
        is_subject = bool(p.get("is_subject_plat"))
        bg = "#fff9e6" if is_subject else sc.WHITE
        name = p.get("plat_name") or ""
        if is_subject:
            name = f"{name} (subject)"
        cells = []
        for key, _ in cols:
            value = p.get(key)
            if key == "plat_name":
                display = _esc(name)
            elif key in ("median_emv", "median_land_psf", "median_bldg_psf"):
                display = _money(value)
            elif key == "parcel_count":
                try:
                    display = f"{int(value):,}" if value is not None else "—"
                except (TypeError, ValueError):
                    display = "—"
            else:
                display = _esc(value) or "—"
            weight = "font-weight:700;" if is_subject else ""
            cells.append(
                f'<td style="padding:6pt 8pt;border-bottom:1px solid {sc.BORDER};'
                f'background:{bg};color:{sc.NAVY};{weight}">{display}</td>'
            )
        rows.append(f"<tr>{''.join(cells)}</tr>")

    table_html = (
        f'<table style="width:100%;border-collapse:collapse;margin:0.75rem 0;'
        f'background:{sc.WHITE};border:1px solid {sc.BORDER};font-size:0.93em;">'
        f"<thead><tr>{head}</tr></thead>"
        f'<tbody>{"".join(rows)}</tbody></table>'
    )
    body = (
        "<h2>Plat-by-Plat Analysis</h2>"
        '<p style="margin:0.3rem 0;color:#555;">'
        "We grouped every parcel by plat and looked at the medians. "
        "The subject's plat is highlighted."
        "</p>"
        + table_html
    )
    return _section(body)


def _build_equalization_scatter_section(data: dict) -> str:
    land = data.get("land_psf_chart")
    bldg = data.get("bldg_psf_chart")
    if not land and not bldg:
        return ""

    parts = ["<h2>Equalization</h2>"]
    if land:
        parts.append("<h3>Land $/SF</h3>")
        parts.append(
            sc.render_equalization_scatter_svg(
                land.get("data") or [],
                land.get("subject_xy") or {},
                land.get("trends") or [],
            )
        )
    if bldg:
        parts.append("<h3>Building $/SF</h3>")
        parts.append(
            sc.render_equalization_scatter_svg(
                bldg.get("data") or [],
                bldg.get("subject_xy") or {},
                bldg.get("trends") or [],
            )
        )
    return _section("".join(parts))


def _build_sales_scatter_section(data: dict) -> str:
    by_plat = data.get("sales_by_plat_chart")
    clean = data.get("sales_clean_chart")
    if not by_plat and not clean:
        return ""

    parts = ["<h2>Sales Trends</h2>"]
    if by_plat:
        parts.append("<h3>Sales by plat (raw)</h3>")
        parts.append(
            sc.render_sales_scatter_svg(
                by_plat.get("sales") or [],
                by_plat.get("trends") or {},
                by_plat.get("subject_sf") or 0,
                by_plat.get("target_dates") or [],
            )
        )
    if clean:
        parts.append("<h3>Sales with outliers removed</h3>")
        parts.append(
            sc.render_sales_scatter_svg(
                clean.get("sales") or [],
                clean.get("trends") or {},
                clean.get("subject_sf") or 0,
                clean.get("target_dates") or [],
            )
        )
    return _section("".join(parts))


def _build_regression_conclusions_section(data: dict) -> str:
    rows_data = data.get("regression_conclusions")
    if not rows_data:
        return ""

    head = (
        f'<thead><tr style="background:{sc.NAVY};color:{sc.WHITE};">'
        f'<th style="padding:8pt;text-align:left;">Model</th>'
        f'<th style="padding:8pt;text-align:right;">Predicted</th>'
        f'<th style="padding:8pt;text-align:right;">Current EMV</th>'
        f'<th style="padding:8pt;text-align:right;">Δ $</th>'
        f'<th style="padding:8pt;text-align:right;">Δ %</th>'
        f"</tr></thead>"
    )
    body_rows = []
    for r in rows_data:
        pred = r.get("predicted_value")
        cur = r.get("current_emv")
        delta = r.get("delta")
        delta_pct = r.get("delta_pct")
        if delta is None and pred is not None and cur is not None:
            try:
                delta = float(pred) - float(cur)
            except (TypeError, ValueError):
                pass
        if delta_pct is None and delta is not None and cur not in (None, 0):
            try:
                delta_pct = float(delta) / float(cur) * 100
            except (TypeError, ValueError):
                pass
        delta_display = _money(delta) if delta is not None else "—"
        if delta is not None:
            try:
                sign = "+" if float(delta) >= 0 else "−"
                delta_display = f"{sign}${abs(float(delta)):,.0f}"
            except (TypeError, ValueError):
                pass
        body_rows.append(
            f'<tr>'
            f'<td style="padding:6pt 8pt;border-bottom:1px solid {sc.BORDER};'
            f'color:{sc.NAVY};font-weight:600;">{_esc(r.get("model_name"))}</td>'
            f'<td style="padding:6pt 8pt;text-align:right;'
            f'border-bottom:1px solid {sc.BORDER};">{_money(pred)}</td>'
            f'<td style="padding:6pt 8pt;text-align:right;'
            f'border-bottom:1px solid {sc.BORDER};">{_money(cur)}</td>'
            f'<td style="padding:6pt 8pt;text-align:right;'
            f'border-bottom:1px solid {sc.BORDER};">{delta_display}</td>'
            f'<td style="padding:6pt 8pt;text-align:right;'
            f'border-bottom:1px solid {sc.BORDER};">{_pct(delta_pct)}</td>'
            f"</tr>"
        )
    table_html = (
        f'<table style="width:100%;border-collapse:collapse;margin:0.5rem 0;'
        f'background:{sc.WHITE};border:1px solid {sc.BORDER};font-size:0.94em;">'
        f"{head}<tbody>{''.join(body_rows)}</tbody></table>"
    )
    body = (
        "<h3>Predicted vs Current EMV</h3>"
        '<p style="margin:0.3rem 0;color:#555;">'
        "Each row is a separate regression model. The county's EMV "
        "and each model's predicted value are side by side."
        "</p>"
        + table_html
    )
    return _section(body)


def _build_adv_columns(subject_advantages: list, comp_advantages: list) -> str:
    def _col(title: str, items: list, accent: str) -> str:
        li_html = "".join(
            f'<li style="padding:0.25rem 0;color:{sc.NAVY};">{_esc(i)}</li>'
            for i in items or []
        )
        if not li_html:
            li_html = (
                f'<li style="padding:0.25rem 0;color:#777;font-style:italic;">'
                f"None noted.</li>"
            )
        return (
            f'<div style="flex:1;min-width:240px;background:{sc.WHITE};'
            f'border:1px solid {sc.BORDER};border-left:4px solid {accent};'
            f'border-radius:4px;padding:0.85rem 1.1rem;">'
            f'<div style="font-weight:700;color:{sc.NAVY};margin-bottom:0.4rem;">'
            f"{_esc(title)}</div>"
            f'<ul style="margin:0;padding-left:1.1rem;font-size:0.94em;">'
            f"{li_html}</ul></div>"
        )

    return (
        f'<div style="display:flex;flex-wrap:wrap;gap:1rem;margin:0.75rem 0;">'
        f"{_col('Where the subject is better', subject_advantages, sc.GOLD)}"
        f"{_col('Where the comp is better', comp_advantages, sc.NAVY)}"
        f"</div>"
    )


def _build_adjustments_table(adjustments: list[dict]) -> str:
    if not adjustments:
        return ""
    rows = []
    total = 0.0
    total_ok = True
    for adj in adjustments:
        desc = adj.get("description") or ""
        amount = adj.get("amount")
        direction = adj.get("direction") or ""
        amount_display = _money(amount)
        try:
            if amount is not None:
                total += float(amount)
        except (TypeError, ValueError):
            total_ok = False
        rows.append(
            f'<tr>'
            f'<td style="padding:6pt 8pt;border-bottom:1px solid {sc.BORDER};">'
            f"{_esc(desc)}</td>"
            f'<td style="padding:6pt 8pt;border-bottom:1px solid {sc.BORDER};'
            f'color:#555;font-size:0.9em;">{_esc(direction)}</td>'
            f'<td style="padding:6pt 8pt;text-align:right;'
            f'border-bottom:1px solid {sc.BORDER};">{amount_display}</td>'
            f"</tr>"
        )
    if total_ok and rows:
        sign = "+" if total >= 0 else "−"
        total_display = f"{sign}${abs(total):,.0f}"
        rows.append(
            f'<tr style="background:{sc.LIGHT};">'
            f'<td style="padding:6pt 8pt;font-weight:700;color:{sc.NAVY};">Net adjustment</td>'
            f'<td></td>'
            f'<td style="padding:6pt 8pt;text-align:right;font-weight:700;'
            f'color:{sc.NAVY};">{total_display}</td></tr>'
        )
    return (
        f'<table style="width:100%;max-width:680px;border-collapse:collapse;'
        f'margin:0.5rem 0;background:{sc.WHITE};border:1px solid {sc.BORDER};'
        f'font-size:0.94em;">'
        f'<thead><tr style="background:{sc.NAVY};color:{sc.WHITE};">'
        f'<th style="padding:8pt;text-align:left;">Item</th>'
        f'<th style="padding:8pt;text-align:left;">Direction</th>'
        f'<th style="padding:8pt;text-align:right;">Amount</th>'
        f"</tr></thead>"
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


def _build_killer_comp_section(data: dict) -> str:
    killer = data.get("killer_comp")
    if not killer:
        return ""

    subject = data.get("subject") or {}
    photos = data.get("killer_comp_photos")
    beacon = data.get("killer_comp_beacon")

    parts = ["<h2>Best Comparable</h2>"]

    summary_line = killer.get("summary")
    if summary_line:
        parts.append(
            f'<p style="margin:0.3rem 0 0.6rem;color:#333;line-height:1.5;">'
            f"{_esc(summary_line)}</p>"
        )

    headline_rows = []
    if killer.get("address"):
        headline_rows.append(("Address", killer.get("address")))
    if killer.get("sale_price") is not None:
        headline_rows.append(("Sale price", _money(killer.get("sale_price"))))
    if killer.get("sale_date"):
        headline_rows.append(("Sale date", killer.get("sale_date")))
    if killer.get("distance_mi") is not None:
        try:
            headline_rows.append(("Distance", f"{float(killer['distance_mi']):.2f} mi"))
        except (TypeError, ValueError):
            pass
    if headline_rows:
        card_rows = "".join(
            f'<div style="display:flex;justify-content:space-between;'
            f'padding:0.25rem 0;border-bottom:1px dotted {sc.BORDER};">'
            f'<span style="color:#555;">{_esc(label)}</span>'
            f'<span style="color:{sc.NAVY};font-weight:600;">{_esc(value)}</span>'
            f"</div>"
            for label, value in headline_rows
        )
        parts.append(
            f'<div style="background:{sc.WHITE};border:1px solid {sc.BORDER};'
            f'border-left:4px solid {sc.GOLD};border-radius:4px;'
            f'padding:0.85rem 1.15rem;margin:0.75rem 0;max-width:520px;">'
            f"{card_rows}</div>"
        )

    if photos:
        parts.append(sc.render_photo_grid(photos, compact=True))

    if beacon:
        subject_beacon = beacon.get("subject") or {}
        comp_beacon = beacon.get("comp") or {}
        parts.append("<h3>Beacon side-by-side</h3>")
        parts.append(
            sc.render_beacon_comparison_table(subject_beacon, [comp_beacon])
        )

    subject_adv = killer.get("subject_advantages") or []
    comp_adv = killer.get("comp_advantages") or []
    if subject_adv or comp_adv:
        parts.append("<h3>What's different</h3>")
        parts.append(_build_adv_columns(subject_adv, comp_adv))

    adjustments = killer.get("adjustments") or []
    if adjustments:
        parts.append("<h3>Adjustment math</h3>")
        parts.append(_build_adjustments_table(adjustments))

    matters_headline = killer.get("matters_headline")
    matters_body = killer.get("matters_body")
    if matters_headline or matters_body:
        parts.append("<h3>Why this comp matters</h3>")
        parts.append(
            sc.render_recommendation_box(
                "kills_appeal",
                matters_headline or "This comp is hard to argue against",
                matters_body or "",
            )
        )

    return _section("".join(parts))


def _filter_final_bullets(bullets: list[str]) -> list[str]:
    """Drop any bullet that mentions Zestimate (case-insensitive)."""
    out = []
    for b in bullets or []:
        if not b:
            continue
        if "zestimate" in str(b).lower():
            continue
        out.append(str(b))
    return out


def _build_final_recommendation_section(data: dict) -> str:
    final = data.get("final_recommendation")
    if not final:
        return ""
    headline = final.get("headline") or "No Appeal — Assessment Supported"
    raw_bullets = final.get("bullets") or []
    bullets = _filter_final_bullets(raw_bullets)
    body_parts = []
    if final.get("body"):
        body_parts.append(f'<p style="margin:0 0 0.5rem;">{_esc(final.get("body"))}</p>')
    if bullets:
        li_html = "".join(
            f'<li style="padding:0.25rem 0;">{_esc(b)}</li>' for b in bullets
        )
        body_parts.append(
            f'<ul style="margin:0.3rem 0 0;padding-left:1.25rem;">{li_html}</ul>'
        )
    body_html = "".join(body_parts) or (
        "We looked at the data and don't see an angle this year."
    )
    return _section(
        "<h2>Final Recommendation</h2>"
        + sc.render_recommendation_box("no_appeal", headline, body_html)
    )


# -- Public entry point ---------------------------------------------------


def generate_no_appeal_report(data: dict) -> str:
    """Render the No-Appeal Findings HTML report.

    Top-level data keys this function reads:
      subject: dict (PID, address, owner_name, year_built, living_area_sf, lot_acres,
                     emv_total, emv_land, emv_building, beacon_absf, basement_finished, ...)
      summary: dict ({headline, body}) — top recommendation box content
      work_completed: list[str] — checkbox list of analytical steps performed
      assessments: list[dict] — 3-year EMV history
      findings: list[dict] — 5-6 plain-spoken finding callouts ({title, body, color})
      stat_summary: dict ({properties_analyzed, sales_analyzed, models_run, ...})
      plat_table: list[dict] — plat-by-plat analysis with subject's plat highlighted
      land_psf_chart: dict ({data, subject_xy, trends}) — equalization scatter
      bldg_psf_chart: dict ({data, subject_xy, trends}) — equalization scatter
      sales_by_plat_chart: dict ({sales, trends, subject_sf, target_dates})
      sales_clean_chart: dict ({sales, trends, subject_sf, target_dates}) — outliers removed
      regression_conclusions: list[dict] — predicted vs current EMV table rows
      killer_comp: dict — the deep-dive comp for the best comparable section
      killer_comp_photos: list[dict] — photos for the best comp section (compact grid)
      killer_comp_beacon: dict — Beacon side-by-side
      final_recommendation: dict ({headline, bullets}) — restated no-appeal box
      meta: dict (assessment_year, payable_year, generated_at, client_name)
    """
    if not isinstance(data, dict) or not data.get("subject"):
        raise ValueError("generate_no_appeal_report requires data['subject']")

    subject = data.get("subject") or {}
    meta = data.get("meta") or {}
    address = subject.get("address") or "Subject Property"
    generated_at = meta.get("generated_at") or ""

    sections = [
        _build_header(subject, meta),                         # 1
        _build_recommendation_section(data),                  # 2
        _build_subject_section(data),                         # 3
        _build_work_completed_section(data),                  # 4
        _build_assessment_section(data),                      # 5
        _build_findings_section(data),                        # 6
        _build_stat_summary_section(data),                    # 7
        _build_plat_table_section(data),                      # 8
        _build_equalization_scatter_section(data),            # 9 + 10
        _build_sales_scatter_section(data),                   # 11
        _build_regression_conclusions_section(data),          # 12
        _build_killer_comp_section(data),                     # 13
        _build_final_recommendation_section(data),            # 14
    ]
    sections_html = "".join(s for s in sections if s)

    print_css = _load_print_css()
    title = f"Assessment Findings — {html.escape(address)}"

    screen_css = (
        "body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; "
        "color: #333; margin: 0; background: #f8f9fa; }\n"
        ".container { max-width: 1100px; margin: 0 auto; padding: 1.5rem 2rem; "
        "background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }\n"
        "section { margin-bottom: 2rem; }\n"
        f"h2 {{ color: {sc.NAVY}; border-bottom: 2px solid {sc.GOLD}; "
        "padding-bottom: 0.4rem; }\n"
        f"h3 {{ color: {sc.NAVY}; margin-top: 1.2rem; }}\n"
        "table { border-collapse: collapse; width: 100%; }\n"
        "th, td { border: 1px solid #e1e4e8; padding: 6pt 8pt; text-align: left; }\n"
        "th { background: #f1f3f5; font-weight: 600; }\n"
        ".footer { text-align: center; color: #666; font-size: 0.85em; "
        "padding: 1.5rem 0; border-top: 1px solid #e1e4e8; margin-top: 2rem; }\n"
        ".footer .disclaimer { display:block; margin-top: 0.35rem; font-size: 0.82em; "
        "color: #888; }\n"
    )

    footer_line = "Residential Property Tax Appeal"
    if generated_at:
        footer_line += f" · Generated {html.escape(str(generated_at))}"
    disclaimer = (
        "This findings report summarizes our analysis of the subject parcel. "
        "Data is sourced from public county records and market comparables."
    )

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
        f'<div class="footer">{footer_line}'
        f'<span class="disclaimer">{disclaimer}</span></div>\n'
        "</div>\n"
        "</body>\n"
        "</html>\n"
    )
