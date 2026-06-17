"""Shared HTML rendering components for residential appeal reports.

Each function is a pure renderer: it takes data and returns an HTML string.
Styling is inlined so each fragment works without a global stylesheet. Class
names (`.finding`, `.photo-grid`, etc.) are set so `print_styles.css` selectors
still apply when the fragments are embedded in a full report document.

Brand colors:
  Navy  #0A2647
  Gold  #d7b971
  Light #f8f9fa
  Border #e1e4e8
"""

from __future__ import annotations

import base64
import html
import math
import os
from datetime import datetime
from pathlib import Path

import requests


# -- Brand ----------------------------------------------------------------

NAVY = "#0A2647"
GOLD = "#d7b971"
WHITE = "#FFFFFF"
LIGHT = "#f8f9fa"
BORDER = "#e1e4e8"
RED = "#c0392b"
GREEN = "#27ae60"
AMBER = "#d7b971"
BLUE = "#2c6e9b"
ORANGE = "#f5841f"


# -- Formatting helpers ---------------------------------------------------


def _esc(value) -> str:
    """HTML-escape a value, replacing None with em dash."""
    if value is None or value == "":
        return "&mdash;"
    return html.escape(str(value))


def _money(value, places: int = 0) -> str:
    if value is None or value == "":
        return "&mdash;"
    try:
        return f"${float(value):,.{places}f}"
    except (TypeError, ValueError):
        return "&mdash;"


def _num(value, suffix: str = "", places: int = 0) -> str:
    if value is None or value == "":
        return "&mdash;"
    try:
        return f"{float(value):,.{places}f}{suffix}"
    except (TypeError, ValueError):
        return "&mdash;"


def _sf(value) -> str:
    return _num(value, " SF", 0)


def _ac(value) -> str:
    if value is None or value == "":
        return "&mdash;"
    try:
        return f"{float(value):.2f} ac"
    except (TypeError, ValueError):
        return "&mdash;"


def _psf(sale_price, sf) -> str:
    try:
        if sale_price and sf and float(sf) > 0:
            return f"${float(sale_price) / float(sf):,.0f}"
    except (TypeError, ValueError):
        pass
    return "&mdash;"


def _pct(value, places: int = 1) -> str:
    if value is None or value == "":
        return "&mdash;"
    try:
        return f"{float(value):+.{places}f}%"
    except (TypeError, ValueError):
        return "&mdash;"


# -- 1. Branded header ---------------------------------------------------


def render_branded_header(title: str, subtitle: str = "", brand: str = "Residential Property Tax Appeal") -> str:
    """Navy/gold header band. `brand` is the firm-name/label slot — set it to
    your firm, or leave the generic default."""
    title_h = _esc(title)
    subtitle_h = _esc(subtitle) if subtitle else ""
    brand_h = _esc(brand)
    subtitle_html = (
        f'<div style="color:{GOLD};font-size:0.95rem;margin-top:0.25rem;">{subtitle_h}</div>'
        if subtitle
        else ""
    )
    return (
        f'<div class="header" style="background:{NAVY};color:{WHITE};'
        f'padding:1.25rem 2rem;border-bottom:4px solid {GOLD};">'
        f'<div class="brand" style="color:{GOLD};font-size:0.85rem;letter-spacing:0.15em;'
        f'text-transform:uppercase;font-weight:600;">{brand_h}</div>'
        f'<h1 style="margin:0.35rem 0 0 0;font-size:1.6rem;font-weight:600;color:{WHITE};">'
        f"{title_h}</h1>"
        f"{subtitle_html}"
        f"</div>"
    )


# -- 2. Subject card -----------------------------------------------------


def render_subject_card(
    subject: dict,
    beacon: dict | None = None,
    corrections: list[dict] | None = None,
) -> str:
    """Two-column card: county records vs actual condition."""
    s = subject or {}
    b = beacon or {}

    def row(label: str, value: str) -> str:
        return (
            f'<div style="display:flex;justify-content:space-between;gap:0.75rem;'
            f'padding:0.28rem 0;border-bottom:1px dotted {BORDER};">'
            f'<span style="color:#555;">{_esc(label)}</span>'
            f'<span style="color:{NAVY};font-weight:600;text-align:right;">{value}</span>'
            f"</div>"
        )

    county_rows = "".join([
        row("PID", _esc(s.get("pid"))),
        row("Address", _esc(s.get("address"))),
        row("Owner", _esc(s.get("owner_name"))),
        row("Year Built", _esc(s.get("year_built"))),
        row("Living Area", _sf(s.get("living_area_sf"))),
        row("Lot Size", _ac(s.get("lot_acres"))),
        row("Style", _esc(s.get("style"))),
        row("Plat", _esc(s.get("plat_name"))),
        row("EMV Land", _money(s.get("emv_land"))),
        row("EMV Building", _money(s.get("emv_building"))),
        row("EMV Total", _money(s.get("emv_total"))),
    ])

    if beacon:
        garage_val = b.get("garage_type") or ""
        if b.get("garage_sf"):
            garage_val = f"{garage_val} ({_num(b.get('garage_sf'))} SF)".strip()
        beacon_rows = "".join([
            row("ABSF (above grade)", _sf(b.get("absf"))),
            row("Basement Finished", _sf(b.get("basement_finished"))),
            row("Exterior", _esc(b.get("exterior"))),
            row("Full Baths", _esc(b.get("full_baths"))),
            row("Half Baths", _esc(b.get("half_baths"))),
            row("Story Height", _esc(b.get("story_height"))),
            row("Garage", _esc(garage_val) if garage_val else "&mdash;"),
        ])
        beacon_html = (
            f'<div style="flex:1;min-width:260px;">'
            f'<h3 style="margin:0 0 0.5rem;color:{NAVY};font-size:1rem;'
            f'border-bottom:2px solid {GOLD};padding-bottom:0.25rem;">Beacon Detail</h3>'
            f"{beacon_rows}</div>"
        )
    else:
        beacon_html = ""

    corrections_html = ""
    if corrections:
        rows = []
        for c in corrections:
            rows.append(
                f'<tr><td style="padding:4pt 6pt;border-bottom:1px solid {BORDER};">'
                f'{_esc(c.get("field"))}</td>'
                f'<td style="padding:4pt 6pt;border-bottom:1px solid {BORDER};color:#777;">'
                f'{_esc(c.get("county_value"))}</td>'
                f'<td style="padding:4pt 6pt;border-bottom:1px solid {BORDER};color:{NAVY};'
                f'font-weight:600;">{_esc(c.get("actual_value"))}</td>'
                f'<td style="padding:4pt 6pt;border-bottom:1px solid {BORDER};font-size:0.85em;'
                f'color:#555;">{_esc(c.get("note"))}</td></tr>'
            )
        corrections_html = (
            f'<div style="margin-top:1rem;">'
            f'<h3 style="margin:0 0 0.4rem;color:{NAVY};font-size:1rem;'
            f'border-bottom:2px solid {GOLD};padding-bottom:0.25rem;">Corrections</h3>'
            f'<table style="width:100%;border-collapse:collapse;font-size:0.9em;">'
            f'<thead><tr style="background:{LIGHT};">'
            f'<th style="text-align:left;padding:4pt 6pt;">Field</th>'
            f'<th style="text-align:left;padding:4pt 6pt;">County Value</th>'
            f'<th style="text-align:left;padding:4pt 6pt;">Actual</th>'
            f'<th style="text-align:left;padding:4pt 6pt;">Note</th>'
            f"</tr></thead>"
            f'<tbody>{"".join(rows)}</tbody></table></div>'
        )

    return (
        f'<div class="card two-col" style="background:{WHITE};border:1px solid {BORDER};'
        f'border-radius:6px;padding:1rem 1.25rem;margin:1rem 0;">'
        f'<div style="display:flex;flex-wrap:wrap;gap:1.5rem;">'
        f'<div style="flex:1;min-width:260px;">'
        f'<h3 style="margin:0 0 0.5rem;color:{NAVY};font-size:1rem;'
        f'border-bottom:2px solid {GOLD};padding-bottom:0.25rem;">County Records</h3>'
        f"{county_rows}</div>"
        f"{beacon_html}"
        f"</div>{corrections_html}</div>"
    )


# -- 3. Assessment history table -----------------------------------------


def render_assessment_history_table(assessments: list[dict]) -> str:
    """Multi-year EMV history with YoY change column."""
    if not assessments:
        return (
            f'<div style="color:#777;font-style:italic;padding:0.5rem 0;">'
            f"No assessment history available.</div>"
        )

    # Sort oldest → newest so YoY is computed going forward.
    def _key(a):
        return a.get("assess_year") or a.get("tax_year") or 0

    rows_sorted = sorted(assessments, key=_key)
    prev_total = None
    body_rows = []
    for a in rows_sorted:
        total = a.get("emv_total")
        yoy_html = "&mdash;"
        try:
            if total is not None and prev_total not in (None, 0):
                change = (float(total) - float(prev_total)) / float(prev_total) * 100
                color = RED if change > 0 else (GREEN if change < 0 else "#555")
                yoy_html = f'<span style="color:{color};font-weight:600;">{_pct(change)}</span>'
        except (TypeError, ValueError):
            pass
        body_rows.append(
            f'<tr><td style="padding:6pt 8pt;border-bottom:1px solid {BORDER};">'
            f'{_esc(a.get("tax_year"))}</td>'
            f'<td style="padding:6pt 8pt;border-bottom:1px solid {BORDER};">'
            f'{_esc(a.get("assess_year"))}</td>'
            f'<td style="padding:6pt 8pt;text-align:right;border-bottom:1px solid {BORDER};">'
            f'{_money(a.get("emv_land"))}</td>'
            f'<td style="padding:6pt 8pt;text-align:right;border-bottom:1px solid {BORDER};">'
            f'{_money(a.get("emv_building"))}</td>'
            f'<td style="padding:6pt 8pt;text-align:right;border-bottom:1px solid {BORDER};'
            f'font-weight:600;">{_money(total)}</td>'
            f'<td style="padding:6pt 8pt;text-align:right;border-bottom:1px solid {BORDER};">'
            f"{yoy_html}</td>"
            f'<td style="padding:6pt 8pt;text-align:right;border-bottom:1px solid {BORDER};">'
            f'{_money(a.get("total_tax"))}</td></tr>'
        )
        if total is not None:
            prev_total = total

    return (
        f'<table style="width:100%;border-collapse:collapse;margin:0.75rem 0;'
        f'background:{WHITE};border:1px solid {BORDER};font-size:0.95em;">'
        f'<thead><tr style="background:{NAVY};color:{WHITE};">'
        f'<th style="padding:8pt;text-align:left;">Tax Year</th>'
        f'<th style="padding:8pt;text-align:left;">Assess Year</th>'
        f'<th style="padding:8pt;text-align:right;">EMV Land</th>'
        f'<th style="padding:8pt;text-align:right;">EMV Building</th>'
        f'<th style="padding:8pt;text-align:right;">EMV Total</th>'
        f'<th style="padding:8pt;text-align:right;">YoY</th>'
        f'<th style="padding:8pt;text-align:right;">Total Tax</th>'
        f'</tr></thead><tbody>{"".join(body_rows)}</tbody></table>'
    )


# -- 4. Sales comp table --------------------------------------------------


_DEFAULT_COMP_COLUMNS = [
    "address",
    "sale_date",
    "sale_price",
    "sf",
    "year_built",
    "lot_acres",
    "emv_total",
]

_COMP_HEADERS = {
    "address": ("Address", "left"),
    "sale_date": ("Sale Date", "left"),
    "sale_price": ("Sale Price", "right"),
    "sf": ("SF", "right"),
    "year_built": ("Year Built", "right"),
    "lot_acres": ("Lot", "right"),
    "emv_total": ("EMV Total", "right"),
    "distance_mi": ("Distance", "right"),
}


def _format_comp_cell(col: str, comp: dict) -> str:
    v = comp.get(col)
    if col == "sale_price" or col == "emv_total":
        return _money(v)
    if col == "sf":
        return _sf(v)
    if col == "year_built":
        return _esc(v)
    if col == "lot_acres":
        return _ac(v)
    if col == "distance_mi":
        if v is None:
            return "&mdash;"
        try:
            return f"{float(v):.2f} mi"
        except (TypeError, ValueError):
            return "&mdash;"
    if col == "sale_date":
        return _esc(v)
    if col == "address":
        return _esc(v)
    return _esc(v)


def render_comp_table(
    comps: list[dict],
    subject: dict,
    columns: list[str] | None = None,
) -> str:
    """Sales comp table with subject row highlighted on top and $/SF computed."""
    cols = list(columns) if columns else list(_DEFAULT_COMP_COLUMNS)
    # Always include $/SF after sale_price if showing sale_price.
    show_psf = "sale_price" in cols and "sf" in cols

    def header_cell(col: str) -> str:
        label, align = _COMP_HEADERS.get(col, (col.title(), "left"))
        return f'<th style="padding:8pt;text-align:{align};">{_esc(label)}</th>'

    header_cells = [header_cell(c) for c in cols]
    if show_psf:
        # insert $/SF column after sf
        sf_idx = cols.index("sf")
        header_cells.insert(
            sf_idx + 1,
            '<th style="padding:8pt;text-align:right;">$/SF</th>',
        )

    header_row = "".join(header_cells)

    def data_row(record: dict, is_subject: bool = False) -> str:
        bg = GOLD if is_subject else "transparent"
        fw = "700" if is_subject else "400"
        color = NAVY if is_subject else "#222"
        cells = []
        for c in cols:
            _, align = _COMP_HEADERS.get(c, (c, "left"))
            value = _format_comp_cell(c, record)
            if is_subject and c in ("sale_date", "sale_price"):
                value = "&mdash;"
            cells.append(
                f'<td style="padding:6pt 8pt;text-align:{align};'
                f'border-bottom:1px solid {BORDER};color:{color};font-weight:{fw};">{value}</td>'
            )
            if show_psf and c == "sf":
                if is_subject:
                    psf_val = "&mdash;"
                else:
                    psf_val = _psf(record.get("sale_price"), record.get("sf"))
                cells.append(
                    f'<td style="padding:6pt 8pt;text-align:right;'
                    f'border-bottom:1px solid {BORDER};color:{color};font-weight:{fw};">'
                    f"{psf_val}</td>"
                )
        style = f"background:{bg};" if is_subject else ""
        return f'<tr style="{style}">{"".join(cells)}</tr>'

    body = [data_row(subject or {}, is_subject=True)]
    for c in comps or []:
        body.append(data_row(c))

    return (
        f'<table style="width:100%;border-collapse:collapse;margin:0.75rem 0;'
        f'background:{WHITE};border:1px solid {BORDER};font-size:0.95em;">'
        f'<thead><tr style="background:{NAVY};color:{WHITE};">{header_row}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table>'
    )


# -- 5. Beacon comparison table ------------------------------------------


def render_beacon_comparison_table(
    subject_beacon: dict,
    comp_beacons: list[dict],
) -> str:
    """Side-by-side Beacon cards table: subject first column, comps after."""
    rows_spec = [
        ("Address", "address"),
        ("Year Built", "year_built"),
        ("Style", "style"),
        ("Exterior", "exterior"),
        ("Story Height", "story_height"),
        ("ABSF", "absf"),
        ("Full Baths", "full_baths"),
        ("Half Baths", "half_baths"),
        ("Basement Finished SF", "basement_finished"),
        ("Garage", "garage"),
    ]

    def cell_value(record: dict, key: str) -> str:
        if record is None:
            return "&mdash;"
        if key == "absf" or key == "basement_finished":
            return _sf(record.get(key))
        if key == "garage":
            g_type_raw = record.get("garage_type") or record.get("garage") or ""
            g_type = g_type_raw.strip() if isinstance(g_type_raw, str) else str(g_type_raw)
            g_sf = record.get("garage_sf")
            if g_sf in (None, ""):
                return _esc(g_type) if g_type else "&mdash;"
            try:
                g_sf_num = float(g_sf)
                return _esc(f"{g_type} ({g_sf_num:,.0f} SF)".strip()) if g_type else _sf(g_sf_num)
            except (TypeError, ValueError):
                return _esc(f"{g_type} ({g_sf})".strip()) if g_type else _esc(g_sf)
        return _esc(record.get(key))

    all_cols = [("Subject", subject_beacon or {}, True)]
    for i, c in enumerate(comp_beacons or [], start=1):
        all_cols.append((f"Comp {i}", c, False))

    head_cells = []
    for label, _, is_subject in all_cols:
        bg = GOLD if is_subject else NAVY
        fg = NAVY if is_subject else WHITE
        head_cells.append(
            f'<th style="padding:8pt;text-align:left;background:{bg};color:{fg};">'
            f"{_esc(label)}</th>"
        )
    head = (
        f'<tr><th style="padding:8pt;text-align:left;background:{LIGHT};'
        f'color:{NAVY};">Field</th>{"".join(head_cells)}</tr>'
    )

    body_rows = []
    for row_label, key in rows_spec:
        cells = [
            f'<td style="padding:6pt 8pt;border-bottom:1px solid {BORDER};'
            f'background:{LIGHT};color:{NAVY};font-weight:600;">{_esc(row_label)}</td>'
        ]
        for _, record, is_subject in all_cols:
            bg = "#fff9e6" if is_subject else WHITE
            cells.append(
                f'<td style="padding:6pt 8pt;border-bottom:1px solid {BORDER};'
                f'background:{bg};">{cell_value(record, key)}</td>'
            )
        body_rows.append(f'<tr>{"".join(cells)}</tr>')

    return (
        f'<table style="width:100%;border-collapse:collapse;margin:0.75rem 0;'
        f'background:{WHITE};border:1px solid {BORDER};font-size:0.92em;">'
        f'<thead>{head}</thead>'
        f'<tbody>{"".join(body_rows)}</tbody></table>'
    )


# -- 6. Equalization scatter SVG -----------------------------------------


def _axis_bounds(values: list[float], pad_frac: float = 0.08) -> tuple[float, float]:
    if not values:
        return 0.0, 1.0
    lo = min(values)
    hi = max(values)
    if lo == hi:
        spread = abs(lo) * 0.1 or 1.0
        return lo - spread, hi + spread
    pad = (hi - lo) * pad_frac
    return lo - pad, hi + pad


def _linmap(v: float, a: float, b: float, c: float, d: float) -> float:
    """Map v from [a,b] to [c,d]."""
    if b == a:
        return (c + d) / 2
    return c + (v - a) * (d - c) / (b - a)


def _clip_line_to_y(x1, y1, x2, y2, ymin, ymax):
    """Clip a line segment against horizontal bounds y in [ymin, ymax].

    Returns (x1, y1, x2, y2) clipped to the y range, preserving slope.
    Returns None if the entire segment is outside the range.
    """
    if y1 == y2:
        if ymin <= y1 <= ymax:
            return x1, y1, x2, y2
        return None
    # Clip against ymin
    if (y1 < ymin) != (y2 < ymin):
        t = (ymin - y1) / (y2 - y1)
        xi = x1 + t * (x2 - x1)
        if y1 < ymin:
            x1, y1 = xi, ymin
        else:
            x2, y2 = xi, ymin
    # Clip against ymax
    if (y1 > ymax) != (y2 > ymax):
        t = (ymax - y1) / (y2 - y1)
        xi = x1 + t * (x2 - x1)
        if y1 > ymax:
            x1, y1 = xi, ymax
        else:
            x2, y2 = xi, ymax
    if (y1 < ymin and y2 < ymin) or (y1 > ymax and y2 > ymax):
        return None
    return x1, y1, x2, y2


def render_equalization_scatter_svg(
    data: list[dict],
    subject: dict,
    trends: list[dict],
) -> str:
    """Inline SVG scatter of $/SF vs SF with trend lines."""
    W, H = 640, 360
    M_L, M_R, M_T, M_B = 60, 20, 25, 45

    xs = [float(d["x"]) for d in (data or []) if d.get("x") is not None]
    ys = [float(d["y"]) for d in (data or []) if d.get("y") is not None]
    if subject and subject.get("x") is not None:
        xs.append(float(subject["x"]))
    if subject and subject.get("y") is not None:
        ys.append(float(subject["y"]))

    if not xs or not ys:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            f'style="max-width:100%;height:auto;background:{WHITE};">'
            f'<text x="{W/2}" y="{H/2}" text-anchor="middle" fill="#777">'
            f"No equalization data available.</text></svg>"
        )

    xmin, xmax = _axis_bounds(xs)
    ymin, ymax = _axis_bounds(ys)

    def sx(v: float) -> float:
        return _linmap(v, xmin, xmax, M_L, W - M_R)

    def sy(v: float) -> float:
        return _linmap(v, ymin, ymax, H - M_B, M_T)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'style="max-width:100%;height:auto;background:{WHITE};font-family:Arial,sans-serif;">',
        f'<rect x="{M_L}" y="{M_T}" width="{W - M_L - M_R}" height="{H - M_T - M_B}" '
        f'fill="{LIGHT}" stroke="{BORDER}"/>',
    ]

    # gridlines + axis ticks
    for i in range(1, 5):
        gx = M_L + (W - M_L - M_R) * i / 5
        parts.append(
            f'<line x1="{gx:.1f}" y1="{M_T}" x2="{gx:.1f}" y2="{H - M_B}" '
            f'stroke="{BORDER}" stroke-dasharray="2,3"/>'
        )
        tx = xmin + (xmax - xmin) * i / 5
        parts.append(
            f'<text x="{gx:.1f}" y="{H - M_B + 14}" text-anchor="middle" '
            f'font-size="10" fill="#555">{tx:,.0f}</text>'
        )
        gy = M_T + (H - M_T - M_B) * i / 5
        parts.append(
            f'<line x1="{M_L}" y1="{gy:.1f}" x2="{W - M_R}" y2="{gy:.1f}" '
            f'stroke="{BORDER}" stroke-dasharray="2,3"/>'
        )
        ty = ymax - (ymax - ymin) * i / 5
        parts.append(
            f'<text x="{M_L - 6}" y="{gy + 3:.1f}" text-anchor="end" '
            f'font-size="10" fill="#555">${ty:,.0f}</text>'
        )

    # trend lines
    legend_items: list[tuple[str, str]] = []
    for i, t in enumerate(trends or []):
        slope = t.get("slope")
        intercept = t.get("intercept")
        if slope is None or intercept is None:
            continue
        color = t.get("color") or [NAVY, BLUE, RED, GREEN][i % 4]
        label = t.get("label") or f"trend {i+1}"
        y1 = intercept + slope * xmin
        y2 = intercept + slope * xmax
        clipped = _clip_line_to_y(xmin, y1, xmax, y2, ymin, ymax)
        if clipped is None:
            continue
        cx1, cy1, cx2, cy2 = clipped
        parts.append(
            f'<line x1="{sx(cx1):.1f}" y1="{sy(cy1):.1f}" '
            f'x2="{sx(cx2):.1f}" y2="{sy(cy2):.1f}" '
            f'stroke="{color}" stroke-width="2" stroke-dasharray="5,4"/>'
        )
        legend_items.append((label, color))

    # data points
    for d in data or []:
        if d.get("x") is None or d.get("y") is None:
            continue
        cx = sx(float(d["x"]))
        cy = sy(float(d["y"]))
        label = _esc(d.get("label") or "")
        parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4" fill="{NAVY}" '
            f'fill-opacity="0.7" stroke="{WHITE}" stroke-width="1"><title>{label}</title></circle>'
        )

    # subject marker
    if subject and subject.get("x") is not None and subject.get("y") is not None:
        cx = sx(float(subject["x"]))
        cy = sy(float(subject["y"]))
        parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="9" fill="none" '
            f'stroke="{GOLD}" stroke-width="3"/>'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="{GOLD}" '
            f'stroke="{NAVY}" stroke-width="1.5"><title>Subject</title></circle>'
        )
        legend_items.append(("Subject", GOLD))

    # axis labels
    parts.append(
        f'<text x="{W/2}" y="{H - 8}" text-anchor="middle" font-size="11" '
        f'fill="{NAVY}" font-weight="600">Size (SF / Lot)</text>'
    )
    parts.append(
        f'<text x="16" y="{H/2}" text-anchor="middle" font-size="11" '
        f'fill="{NAVY}" font-weight="600" transform="rotate(-90 16 {H/2})">$/SF</text>'
    )

    # legend
    ly = M_T + 6
    lx = W - M_R - 150
    parts.append(
        f'<rect x="{lx}" y="{ly}" width="140" height="{14 * max(len(legend_items),1) + 8}" '
        f'fill="{WHITE}" stroke="{BORDER}" opacity="0.9"/>'
    )
    for i, (lab, col) in enumerate(legend_items):
        y = ly + 14 + i * 14
        parts.append(
            f'<line x1="{lx + 6}" y1="{y - 3}" x2="{lx + 22}" y2="{y - 3}" '
            f'stroke="{col}" stroke-width="3"/>'
            f'<text x="{lx + 28}" y="{y}" font-size="10" fill="#333">{_esc(lab)}</text>'
        )

    parts.append("</svg>")
    return "".join(parts)


# -- 7. Sales scatter SVG -------------------------------------------------


def _parse_iso(d: str) -> float | None:
    if not d:
        return None
    try:
        return datetime.fromisoformat(str(d)[:10]).timestamp()
    except ValueError:
        return None


def render_sales_scatter_svg(
    sales: list[dict],
    trends: dict,
    subject_sf: float,
    target_dates: list[str],
) -> str:
    """Inline SVG scatter: sales $/SF over time with trend lines and target guides."""
    W, H = 640, 360
    M_L, M_R, M_T, M_B = 65, 20, 25, 45

    pts: list[tuple[float, float, str]] = []
    for s in sales or []:
        ts = _parse_iso(s.get("date"))
        psf = s.get("psf")
        if ts is None or psf is None:
            continue
        pts.append((ts, float(psf), str(s.get("label") or "")))

    targets: list[float] = []
    for d in target_dates or []:
        ts = _parse_iso(d)
        if ts is not None:
            targets.append(ts)

    if not pts:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            f'style="max-width:100%;height:auto;background:{WHITE};">'
            f'<text x="{W/2}" y="{H/2}" text-anchor="middle" fill="#777">'
            f"No sales data available.</text></svg>"
        )

    xs = [p[0] for p in pts] + targets
    ys = [p[1] for p in pts]
    xmin, xmax = _axis_bounds(xs, 0.05)
    ymin, ymax = _axis_bounds(ys, 0.10)

    def sx(v: float) -> float:
        return _linmap(v, xmin, xmax, M_L, W - M_R)

    def sy(v: float) -> float:
        return _linmap(v, ymin, ymax, H - M_B, M_T)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'style="max-width:100%;height:auto;background:{WHITE};font-family:Arial,sans-serif;">',
        f'<rect x="{M_L}" y="{M_T}" width="{W - M_L - M_R}" height="{H - M_T - M_B}" '
        f'fill="{LIGHT}" stroke="{BORDER}"/>',
    ]

    # gridlines + x ticks (as years)
    for i in range(1, 5):
        gx = M_L + (W - M_L - M_R) * i / 5
        parts.append(
            f'<line x1="{gx:.1f}" y1="{M_T}" x2="{gx:.1f}" y2="{H - M_B}" '
            f'stroke="{BORDER}" stroke-dasharray="2,3"/>'
        )
        tx = xmin + (xmax - xmin) * i / 5
        lbl = datetime.fromtimestamp(tx).strftime("%Y-%m")
        parts.append(
            f'<text x="{gx:.1f}" y="{H - M_B + 14}" text-anchor="middle" '
            f'font-size="10" fill="#555">{lbl}</text>'
        )
        gy = M_T + (H - M_T - M_B) * i / 5
        parts.append(
            f'<line x1="{M_L}" y1="{gy:.1f}" x2="{W - M_R}" y2="{gy:.1f}" '
            f'stroke="{BORDER}" stroke-dasharray="2,3"/>'
        )
        ty = ymax - (ymax - ymin) * i / 5
        parts.append(
            f'<text x="{M_L - 6}" y="{gy + 3:.1f}" text-anchor="end" '
            f'font-size="10" fill="#555">${ty:,.0f}</text>'
        )

    # trend lines (each keyed: model_name -> {slope, intercept, r2})
    legend_items: list[tuple[str, str]] = []
    trend_colors = [NAVY, BLUE, GREEN, RED, ORANGE]
    for i, (name, t) in enumerate((trends or {}).items()):
        if not isinstance(t, dict):
            continue
        slope = t.get("slope")
        intercept = t.get("intercept")
        if slope is None or intercept is None:
            continue
        color = t.get("color") or trend_colors[i % len(trend_colors)]
        y1 = intercept + slope * xmin
        y2 = intercept + slope * xmax
        clipped = _clip_line_to_y(xmin, y1, xmax, y2, ymin, ymax)
        if clipped is None:
            continue
        cx1, cy1, cx2, cy2 = clipped
        parts.append(
            f'<line x1="{sx(cx1):.1f}" y1="{sy(cy1):.1f}" '
            f'x2="{sx(cx2):.1f}" y2="{sy(cy2):.1f}" '
            f'stroke="{color}" stroke-width="2" stroke-dasharray="5,4"/>'
        )
        r2 = t.get("r2")
        lab = f"{name}" + (f" (r²={float(r2):.2f})" if r2 is not None else "")
        legend_items.append((lab, color))

    # target date vertical guides + predicted markers (use first trend)
    first_trend = None
    for t in (trends or {}).values():
        if isinstance(t, dict) and t.get("slope") is not None and t.get("intercept") is not None:
            first_trend = t
            break

    for ts in targets:
        x_px = sx(ts)
        parts.append(
            f'<line x1="{x_px:.1f}" y1="{M_T}" x2="{x_px:.1f}" y2="{H - M_B}" '
            f'stroke="{GOLD}" stroke-width="1.5" stroke-dasharray="3,3"/>'
        )
        if first_trend:
            pred_psf = float(first_trend["intercept"]) + float(first_trend["slope"]) * ts
            y_px = sy(pred_psf)
            parts.append(
                f'<circle cx="{x_px:.1f}" cy="{y_px:.1f}" r="5" '
                f'fill="{GOLD}" stroke="{NAVY}" stroke-width="1.5">'
                f'<title>Predicted ${pred_psf:,.0f}/SF</title></circle>'
            )

    # data points
    for ts, psf, label in pts:
        cx = sx(ts)
        cy = sy(psf)
        parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4" fill="{NAVY}" '
            f'fill-opacity="0.7" stroke="{WHITE}" stroke-width="1">'
            f'<title>{_esc(label)}: ${psf:,.0f}/SF</title></circle>'
        )

    # axis labels
    parts.append(
        f'<text x="{W/2}" y="{H - 8}" text-anchor="middle" font-size="11" '
        f'fill="{NAVY}" font-weight="600">Sale Date</text>'
    )
    parts.append(
        f'<text x="16" y="{H/2}" text-anchor="middle" font-size="11" '
        f'fill="{NAVY}" font-weight="600" transform="rotate(-90 16 {H/2})">Sale $/SF</text>'
    )

    # subject SF annotation
    if subject_sf:
        parts.append(
            f'<text x="{W - M_R - 6}" y="{M_T + 14}" text-anchor="end" '
            f'font-size="10" fill="#555">Subject: {float(subject_sf):,.0f} SF</text>'
        )

    # legend
    if legend_items:
        ly = M_T + 6
        lx = M_L + 8
        parts.append(
            f'<rect x="{lx}" y="{ly}" width="180" height="{14 * len(legend_items) + 8}" '
            f'fill="{WHITE}" stroke="{BORDER}" opacity="0.9"/>'
        )
        for i, (lab, col) in enumerate(legend_items):
            y = ly + 14 + i * 14
            parts.append(
                f'<line x1="{lx + 6}" y1="{y - 3}" x2="{lx + 22}" y2="{y - 3}" '
                f'stroke="{col}" stroke-width="3"/>'
                f'<text x="{lx + 28}" y="{y}" font-size="10" fill="#333">{_esc(lab)}</text>'
            )

    parts.append("</svg>")
    return "".join(parts)


# -- 8. Static map --------------------------------------------------------


def _lonlat_to_mercator(lon: float, lat: float) -> tuple[float, float]:
    x = lon * 20037508.34 / 180
    y = math.log(math.tan((90 + lat) * math.pi / 360)) / (math.pi / 180)
    y = y * 20037508.34 / 180
    return x, y


def _map_fallback(message: str = "Map unavailable") -> str:
    return (
        f'<div class="map-fallback" style="width:1000px;max-width:100%;height:200px;'
        f'background:{LIGHT};border:1px solid {BORDER};border-radius:6px;'
        f'display:flex;align-items:center;justify-content:center;color:#777;'
        f'font-style:italic;margin:1rem 0;">{_esc(message)}</div>'
    )


def render_static_map(
    subject: dict,
    comps: list[dict],
    actives: list[dict] | None = None,
) -> str:
    """Base64-embedded ESRI World Street Map with CSS-positioned markers."""
    if not subject or subject.get("lat") is None or subject.get("lon") is None:
        return _map_fallback("Map unavailable (no subject coordinates)")

    try:
        pts: list[tuple[float, float]] = [
            (float(subject["lat"]), float(subject["lon"]))
        ]
        for c in comps or []:
            if c.get("lat") is not None and c.get("lon") is not None:
                pts.append((float(c["lat"]), float(c["lon"])))
        for a in actives or []:
            if a.get("lat") is not None and a.get("lon") is not None:
                pts.append((float(a["lat"]), float(a["lon"])))
    except (TypeError, ValueError):
        return _map_fallback("Map unavailable (bad coordinates)")

    lats = [p[0] for p in pts]
    lons = [p[1] for p in pts]
    pad = 0.01
    min_lat, max_lat = min(lats) - pad, max(lats) + pad
    min_lon, max_lon = min(lons) - pad, max(lons) + pad

    # Ensure a minimum visible span (single-point case).
    if max_lat - min_lat < 0.005:
        mid = (max_lat + min_lat) / 2
        min_lat, max_lat = mid - 0.005, mid + 0.005
    if max_lon - min_lon < 0.005:
        mid = (max_lon + min_lon) / 2
        min_lon, max_lon = mid - 0.005, mid + 0.005

    xmin, ymin = _lonlat_to_mercator(min_lon, min_lat)
    xmax, ymax = _lonlat_to_mercator(max_lon, max_lat)

    # Match the 1000x600 image aspect ratio so markers stay aligned.
    img_w, img_h = 1000, 600
    img_aspect = img_w / img_h
    span_x = xmax - xmin
    span_y = ymax - ymin
    if span_y == 0 or span_x / span_y > img_aspect:
        # too wide, expand y
        new_span_y = span_x / img_aspect
        cy = (ymin + ymax) / 2
        ymin = cy - new_span_y / 2
        ymax = cy + new_span_y / 2
    else:
        new_span_x = span_y * img_aspect
        cx = (xmin + xmax) / 2
        xmin = cx - new_span_x / 2
        xmax = cx + new_span_x / 2

    bbox_str = f"{xmin},{ymin},{xmax},{ymax}"
    url = (
        "https://server.arcgisonline.com/ArcGIS/rest/services/"
        "World_Street_Map/MapServer/export"
    )
    params = {
        "bbox": bbox_str,
        "bboxSR": "3857",
        "imageSR": "3857",
        "size": f"{img_w},{img_h}",
        "format": "png",
        "transparent": "false",
        "f": "image",
    }

    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        if not resp.content:
            return _map_fallback("Map unavailable (empty response)")
        img_b64 = base64.b64encode(resp.content).decode("ascii")
    except Exception:
        return _map_fallback("Map unavailable (fetch error)")

    def mk_marker(lat: float, lon: float, color: str, outline: str, label: str) -> str:
        px, py = _lonlat_to_mercator(lon, lat)
        if xmax == xmin or ymax == ymin:
            return ""
        left = (px - xmin) / (xmax - xmin) * img_w
        top = (1 - (py - ymin) / (ymax - ymin)) * img_h
        safe_label = _esc(label)
        return (
            f'<div title="{safe_label}" style="position:absolute;'
            f'left:{left - 6:.1f}px;top:{top - 6:.1f}px;width:12px;height:12px;'
            f'border-radius:50%;background:{color};border:2px solid {WHITE};'
            f'box-shadow:0 0 0 1px {outline};z-index:2;"></div>'
        )

    markers = [mk_marker(
        float(subject["lat"]),
        float(subject["lon"]),
        GOLD,
        NAVY,
        subject.get("address") or "Subject",
    )]
    for c in comps or []:
        if c.get("lat") is None or c.get("lon") is None:
            continue
        markers.append(
            mk_marker(
                float(c["lat"]),
                float(c["lon"]),
                NAVY,
                NAVY,
                c.get("address") or "Comp",
            )
        )
    for a in actives or []:
        if a.get("lat") is None or a.get("lon") is None:
            continue
        markers.append(
            mk_marker(
                float(a["lat"]),
                float(a["lon"]),
                ORANGE,
                NAVY,
                a.get("address") or "Active",
            )
        )

    return (
        f'<div style="position:relative;width:1000px;height:600px;max-width:100%;'
        f'border:1px solid {BORDER};border-radius:6px;overflow:hidden;margin:1rem 0;">'
        f'<img src="data:image/png;base64,{img_b64}" width="1000" height="600" '
        f'alt="Property location map" '
        f'style="display:block;width:100%;height:100%;object-fit:cover;"/>'
        f'{"".join(markers)}'
        f"</div>"
    )


# -- 9. Finding callout ---------------------------------------------------


_CALLOUT_PALETTE = {
    "amber": {"bg": "#fff9e6", "border": GOLD, "text": "#5a4500"},
    "green": {"bg": "#eaf7ee", "border": GREEN, "text": "#0f5132"},
    "red": {"bg": "#fdeceb", "border": RED, "text": "#701c16"},
    "blue": {"bg": "#e7f1fa", "border": BLUE, "text": "#123c5a"},
    "navy": {"bg": "#e7ecf3", "border": NAVY, "text": NAVY},
}


def render_finding_callout(title: str, body: str, color: str = "amber") -> str:
    """Highlighted finding box with inline color-coded styling.

    Title is optional — passing an empty string omits the title block.
    """
    palette = _CALLOUT_PALETTE.get(color, _CALLOUT_PALETTE["amber"])
    title_html = (
        f'<div style="font-weight:700;font-size:1.02em;margin-bottom:0.3rem;">'
        f"{_esc(title)}</div>"
        if title
        else ""
    )
    return (
        f'<div class="finding callout" style="background:{palette["bg"]};'
        f'border-left:4px solid {palette["border"]};color:{palette["text"]};'
        f'padding:0.85rem 1.15rem;margin:0.9rem 0;border-radius:4px;">'
        f"{title_html}"
        f'<div style="line-height:1.5;">{body}</div>'
        f"</div>"
    )


# -- 10. Recommendation box ----------------------------------------------


def render_recommendation_box(verdict: str, headline: str, body: str) -> str:
    """Top-of-report recommendation box — verdict drives the color."""
    v = (verdict or "").lower().strip()
    if v in ("appeal", "supports_appeal"):
        palette = {"bg": "#fdeceb", "border": RED, "title": RED, "label": "RECOMMENDATION: APPEAL"}
    elif v in ("no_appeal", "kills_appeal"):
        palette = {"bg": "#eaf7ee", "border": GREEN, "title": GREEN, "label": "RECOMMENDATION: NO APPEAL"}
    else:
        palette = {"bg": "#fff9e6", "border": GOLD, "title": "#5a4500", "label": "RECOMMENDATION"}

    return (
        f'<div class="recommendation callout" style="background:{palette["bg"]};'
        f'border-left:5px solid {palette["border"]};padding:1.1rem 1.4rem;'
        f'margin:1rem 0;border-radius:4px;">'
        f'<div style="font-size:0.8rem;letter-spacing:0.1em;text-transform:uppercase;'
        f'font-weight:700;color:{palette["title"]};margin-bottom:0.4rem;">'
        f'{_esc(palette["label"])}</div>'
        f'<div style="font-size:1.3rem;font-weight:700;color:{NAVY};'
        f'margin-bottom:0.5rem;line-height:1.3;">{_esc(headline)}</div>'
        f'<div style="color:#333;line-height:1.5;font-size:0.98em;">{body}</div>'
        f"</div>"
    )


# -- 11. Photo grid -------------------------------------------------------


def _photo_uri(path: str) -> str:
    if not path:
        return ""
    p = str(path)
    if p.startswith(("http://", "https://", "data:", "file://")):
        return p
    try:
        abs_path = Path(p).expanduser().resolve()
        return f"file://{abs_path}"
    except Exception:
        return p


def render_photo_grid(photos: list[dict], compact: bool = False) -> str:
    """Grid of photo cards. Each photo: {path, caption}."""
    if compact:
        grid_class = "comp-photo-grid"
        img_h = 110
        min_card = "150px"
        max_w = "600px"
        grid_template = f"repeat(auto-fit,minmax({min_card},1fr))"
    else:
        grid_class = "photo-grid"
        img_h = 220
        max_w = "100%"
        grid_template = "repeat(auto-fit,minmax(220px,1fr))"

    cards = []
    for p in photos or []:
        path = p.get("path") if isinstance(p, dict) else None
        caption = p.get("caption", "") if isinstance(p, dict) else ""
        uri = _photo_uri(path) if path else ""
        exists = False
        if path:
            try:
                if str(path).startswith(("http://", "https://", "data:")):
                    exists = True
                else:
                    exists = Path(str(path)).expanduser().exists()
            except Exception:
                exists = False

        if exists and uri:
            img_html = (
                f'<img src="{_esc(uri)}" alt="{_esc(caption)}" '
                f'style="width:100%;height:{img_h}px;object-fit:cover;display:block;"/>'
            )
        else:
            img_html = (
                f'<div style="width:100%;height:{img_h}px;background:{LIGHT};'
                f'display:flex;align-items:center;justify-content:center;'
                f'color:#999;font-size:0.85em;font-style:italic;">'
                f"No photo available</div>"
            )

        caption_html = (
            f'<div class="caption" style="padding:0.4rem 0.6rem;background:{NAVY};'
            f'color:{WHITE};font-size:0.82em;line-height:1.3;">'
            f"{_esc(caption)}</div>"
            if caption
            else ""
        )

        cards.append(
            f'<div class="photo-card" style="border:1px solid {BORDER};'
            f"border-radius:4px;overflow:hidden;background:{WHITE};\">"
            f"{img_html}{caption_html}</div>"
        )

    return (
        f'<div class="{grid_class}" style="display:grid;'
        f"grid-template-columns:{grid_template};"
        f'gap:0.75rem;margin:1rem 0;max-width:{max_w};">'
        f'{"".join(cards)}</div>'
    )


# -- 12. Section subtitle -------------------------------------------------


def render_section_subtitle(text: str) -> str:
    """Small italic subtitle under an h2 to state section purpose."""
    if not text:
        return ""
    return (
        f'<p class="section-sub" style="color:#666;font-size:0.92rem;'
        f'font-style:italic;margin:-0.4rem 0 0.8rem;">{_esc(text)}</p>'
    )


# -- 13. Approach-close card (Indicated Value for one approach) ----------


def render_approach_close(label: str, value, note: str = "") -> str:
    """Navy/gold card that closes a valuation approach with its indicated value.

    Pattern: 'Indicated Value — Sales Comparison Approach    $570,000'
    Optional note shown underneath in lighter text.
    """
    money = _money(value) if not isinstance(value, str) else value
    note_html = (
        f'<div class="ac-note" style="color:#dde;font-size:0.82rem;'
        f'width:100%;margin-top:0.3rem;">{_esc(note)}</div>'
        if note
        else ""
    )
    return (
        f'<div class="approach-close" style="background:{NAVY};color:{WHITE};'
        f'padding:0.9rem 1.3rem;border-radius:8px;margin:1rem 0;'
        f'display:flex;align-items:center;justify-content:space-between;'
        f'gap:1rem;flex-wrap:wrap;">'
        f'<span class="ac-label" style="color:{GOLD};font-weight:600;'
        f'font-size:0.95rem;letter-spacing:0.02em;">Indicated Value &mdash; '
        f"{_esc(label)}</span>"
        f'<span class="ac-value" style="color:{GOLD};font-weight:700;'
        f'font-size:1.5rem;">{money}</span>'
        f"{note_html}</div>"
    )


# -- 14. Adjustment schedule ---------------------------------------------


def render_adjustment_schedule(rows: list[dict]) -> str:
    """Rate table. Each row: {adjustment, rate, basis}."""
    if not rows:
        return ""
    body = []
    for r in rows:
        body.append(
            f"<tr>"
            f'<td style="padding:4pt 8pt;border-bottom:1px solid {BORDER};">'
            f'{_esc(r.get("adjustment"))}</td>'
            f'<td style="padding:4pt 8pt;border-bottom:1px solid {BORDER};'
            f'font-weight:600;color:{NAVY};white-space:nowrap;">'
            f'{_esc(r.get("rate"))}</td>'
            f'<td style="padding:4pt 8pt;border-bottom:1px solid {BORDER};'
            f'color:#555;">{_esc(r.get("basis"))}</td>'
            f"</tr>"
        )
    return (
        f'<div class="card" style="background:{WHITE};border:1px solid {BORDER};'
        f'border-radius:6px;padding:0.7rem 1rem;margin:0.6rem 0;">'
        f'<table style="width:100%;border-collapse:collapse;font-size:0.85rem;'
        f'margin:0.3rem 0;">'
        f'<thead><tr style="background:{NAVY};color:{WHITE};">'
        f'<th style="padding:6pt 8pt;text-align:left;">Adjustment</th>'
        f'<th style="padding:6pt 8pt;text-align:left;">Rate</th>'
        f'<th style="padding:6pt 8pt;text-align:left;">Basis</th>'
        f"</tr></thead>"
        f'<tbody>{"".join(body)}</tbody></table></div>'
    )


# -- 15. Adjustment grid --------------------------------------------------


def _fmt_pct(v) -> str:
    """Format a % adjustment with a sign and no unnecessary decimals."""
    if v is None:
        return "&mdash;"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "&mdash;"
    if abs(f) < 0.01:
        return "0.0%"
    sign = "+" if f > 0 else "&minus;"
    return f"{sign}{abs(f):.2f}%".rstrip("0").rstrip(".") + "%" if False else (
        f"{sign}{abs(f):.1f}%"
    )


def _median(vals: list[float]) -> float:
    sv = sorted(vals)
    n = len(sv)
    return sv[n // 2] if n % 2 else (sv[n // 2 - 1] + sv[n // 2]) / 2


def render_adjustment_grid(comps: list[dict], excluded_note: str = "", subject_sf: float | None = None) -> str:
    """Percentage-based adjustment grid.

    Each comp: {address, descriptor, sale_price, sale_date, sf,
                time_pct, size_pct, condition_pct, quality_pct, lot_pct}

    Two modes:
    - **Total-value mode** (default, `subject_sf=None`): adjustments include
      size; net % is applied to the sale price; reconciles on adjusted value.
    - **$/SF mode** (`subject_sf` provided and comps carry `sf`): adjustments
      apply to the comp's sale $/SF (size is NOT a grid line — it is resolved by
      multiplying the reconciled $/SF by the subject's SF). Each comp yields an
      adjusted $/SF and an indicated subject value (adj $/SF × subject SF); the
      supported value is the median adjusted $/SF × subject SF.
    """
    if not comps:
        return ""
    psf_mode = subject_sf is not None and any(c.get("sf") for c in comps)
    body = []
    adjusted_values: list[float] = []   # total-value mode
    adj_psfs: list[float] = []          # $/SF mode
    cell_common = f'style="padding:4pt 6pt;border-bottom:1px solid {BORDER};"'
    for c in comps:
        try:
            sale = float(c.get("sale_price") or 0)
        except (TypeError, ValueError):
            sale = 0.0
        t = float(c.get("time_pct") or 0)
        s = float(c.get("size_pct") or 0)
        cd = float(c.get("condition_pct") or 0)
        q = float(c.get("quality_pct") or 0)
        lot = float(c.get("lot_pct") or 0)
        addr = _esc(c.get("address"))
        desc = _esc(c.get("descriptor") or "")
        date = _esc(c.get("sale_date") or "")
        addr_cell = (
            f'<td {cell_common}>{addr}'
            + (f'<br><span style="font-size:0.85em;color:#666;">{desc}</span>' if desc else "")
            + "</td>"
        )
        if psf_mode:
            sf = float(c.get("sf") or 0)
            sale_psf = sale / sf if sf else 0
            net = t + cd + q + lot  # size handled by subject SF, not a grid line
            adj_psf = sale_psf * (1 + net / 100.0)
            indicated = adj_psf * float(subject_sf)
            if sf and sale:
                adj_psfs.append(adj_psf)
            body.append(
                f"<tr>{addr_cell}"
                f"<td {cell_common}>{_money(sale)}</td>"
                f"<td {cell_common}>${sale_psf:,.0f}</td>"
                f"<td {cell_common}>{date}</td>"
                f"<td {cell_common}>{_fmt_pct(t)}</td>"
                f"<td {cell_common}>{_fmt_pct(cd)}</td>"
                f"<td {cell_common}>{_fmt_pct(q)}</td>"
                f"<td {cell_common}>{_fmt_pct(lot)}</td>"
                f"<td {cell_common}>{_fmt_pct(net)}</td>"
                f"<td {cell_common}>${adj_psf:,.0f}</td>"
                f"<td {cell_common}><strong>{_money(indicated)}</strong></td>"
                f"</tr>"
            )
        else:
            net = t + s + cd + q + lot
            adj_value = sale * (1 + net / 100.0) if sale else 0
            if sale:
                adjusted_values.append(adj_value)
            body.append(
                f"<tr>{addr_cell}"
                f"<td {cell_common}>{_money(sale)}</td>"
                f"<td {cell_common}>{date}</td>"
                f"<td {cell_common}>{_fmt_pct(t)}</td>"
                f"<td {cell_common}>{_fmt_pct(s)}</td>"
                f"<td {cell_common}>{_fmt_pct(cd)}</td>"
                f"<td {cell_common}>{_fmt_pct(q)}</td>"
                f"<td {cell_common}>{_fmt_pct(lot)}</td>"
                f"<td {cell_common}>{_fmt_pct(net)}</td>"
                f"<td {cell_common}><strong>{_money(adj_value)}</strong></td>"
                f"</tr>"
            )

    def _stat(value, label):
        return (
            f'<div class="stat" style="background:{LIGHT};border-radius:6px;'
            f'padding:0.6rem;text-align:center;"><div class="value" '
            f'style="font-size:1.2rem;font-weight:700;color:{NAVY};">{value}</div>'
            f'<div class="label" style="font-size:0.78rem;color:#666;">{label}</div></div>'
        )

    stats_html = ""
    if psf_mode and adj_psfs:
        n = len(adj_psfs)
        med_psf = _median(adj_psfs)
        mean_psf = sum(adj_psfs) / n
        supported = med_psf * float(subject_sf)
        stats_html = (
            f'<div class="stats" style="display:grid;'
            f"grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:0.6rem;margin:0.6rem 0;\">"
            + _stat(f"${mean_psf:,.0f}/SF", f"Mean adjusted $/SF ({n} comps)")
            + _stat(f"${med_psf:,.0f}/SF", "Median adjusted $/SF")
            + _stat(_money(supported), f"Supported value (median adj $/SF × {float(subject_sf):,.0f} SF)")
            + "</div>"
        )
    elif adjusted_values:
        n = len(adjusted_values)
        stats_html = (
            f'<div class="stats" style="display:grid;'
            f"grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:0.6rem;margin:0.6rem 0;\">"
            + _stat(_money(sum(adjusted_values) / n), f"Mean adjusted ({n} comps)")
            + _stat(_money(_median(adjusted_values)), "Median adjusted")
            + "</div>"
        )

    excluded_html = (
        f'<p style="font-size:0.8rem;color:#666;margin-top:0.2rem;">{_esc(excluded_note)}</p>'
        if excluded_note
        else ""
    )

    if psf_mode:
        head = (
            '<th style="padding:6pt;text-align:left;">Comp</th>'
            '<th style="padding:6pt;text-align:left;">Sale Price</th>'
            '<th style="padding:6pt;text-align:left;">$/SF</th>'
            '<th style="padding:6pt;text-align:left;">Date</th>'
            '<th style="padding:6pt;text-align:left;">Time</th>'
            '<th style="padding:6pt;text-align:left;">Cond.</th>'
            '<th style="padding:6pt;text-align:left;">Qual.</th>'
            '<th style="padding:6pt;text-align:left;">Lot</th>'
            '<th style="padding:6pt;text-align:left;">Net Adj</th>'
            '<th style="padding:6pt;text-align:left;">Adj $/SF</th>'
            '<th style="padding:6pt;text-align:left;">Indicated value</th>'
        )
    else:
        head = (
            '<th style="padding:6pt;text-align:left;">Comp</th>'
            '<th style="padding:6pt;text-align:left;">Sale Price</th>'
            '<th style="padding:6pt;text-align:left;">Date</th>'
            '<th style="padding:6pt;text-align:left;">Time</th>'
            '<th style="padding:6pt;text-align:left;">Size</th>'
            '<th style="padding:6pt;text-align:left;">Cond.</th>'
            '<th style="padding:6pt;text-align:left;">Qual.</th>'
            '<th style="padding:6pt;text-align:left;">Lot</th>'
            '<th style="padding:6pt;text-align:left;">Net Adj</th>'
            '<th style="padding:6pt;text-align:left;">Adjusted Value</th>'
        )
    return (
        f'<table style="width:100%;border-collapse:collapse;font-size:0.78rem;margin:0.5rem 0;">'
        f'<thead><tr style="background:{NAVY};color:{WHITE};">{head}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table>'
        f"{excluded_html}{stats_html}"
    )


# -- 15b. Extraction adjustment grid (above-grade basis) -----------------


def render_extraction_grid(comps: list[dict], subject_absf: float, subject_land: float,
                           bsmt_psf: float = 50.0, gar_psf: float = 30.0,
                           econ_psf_per_sf: float = 0.06, note: str = "") -> str:
    """Above-grade adjustment grid for a subject whose lot / basement / garage differ
    materially from the comps (where a flat percentage-of-sale grid would blow up the
    lot line). Each comp's sale is reduced to its ABOVE-GRADE building value — remove
    land at the county's own value, plus the finished basement (× bsmt_psf) and garage
    (× gar_psf) the subject lacks — divided by the comp's ABSF, then adjusted to the
    subject for size (economy of scale), quality, condition, and time. Indicated value
    = adjusted $/SF × the subject's ABSF + the subject's own land.

    Each comp: {address, year, sale_price, land, absf, fin_bsmt_sf, garage_sf,
                time_pct, quality_pct, condition_pct, descriptor}. Returns the grid +
    the bracketed range and median indicated value (the supported value).
    """
    if not comps:
        return ""
    cell = f'style="padding:4pt 6pt;border-bottom:1px solid {BORDER};"'
    body, inds = [], []
    for c in comps:
        sale = float(c.get("sale_price") or 0)
        land = float(c.get("land") or 0)
        absf = float(c.get("absf") or 0)
        fin = float(c.get("fin_bsmt_sf") or 0)
        gar = float(c.get("garage_sf") or 0)
        if not (sale and absf):
            continue
        t, q, cd = float(c.get("time_pct") or 0), float(c.get("quality_pct") or 0), float(c.get("condition_pct") or 0)
        agval = sale - land - fin * bsmt_psf - gar * gar_psf
        agpsf = agval / absf
        size = econ_psf_per_sf * (absf - subject_absf)   # smaller comp → higher $/SF → adjust toward subject
        adj = (agpsf + size) * (1 + t / 100 + q / 100 + cd / 100)
        ind = round(adj * subject_absf + subject_land)
        inds.append(ind)
        desc = _esc(c.get("descriptor") or "")
        addr_cell = (f'<td {cell}>{_esc(c.get("address"))}'
                     + (f'<br><span style="font-size:0.82em;color:#666;">{desc}</span>' if desc else "") + "</td>")
        body.append(
            f"<tr>{addr_cell}"
            f"<td {cell}>{_money(sale)}</td><td {cell}>&minus;{_money(land)}</td>"
            f"<td {cell}>&minus;{_money(fin * bsmt_psf)}</td><td {cell}>&minus;{_money(gar * gar_psf)}</td>"
            f"<td {cell}>{_money(agval)}</td><td {cell}>{absf:,.0f}</td><td {cell}>${agpsf:,.0f}</td>"
            f"<td {cell}>{size:+.0f}</td><td {cell}>{q:+.0f}% / {cd:+.0f}%</td><td {cell}>+{t:g}%</td>"
            f"<td {cell}>${adj:,.0f}</td><td {cell}><strong>{_money(ind)}</strong></td></tr>"
        )
    if not inds:
        return ""
    srt = sorted(inds)
    med = srt[len(srt) // 2] if len(srt) % 2 else (srt[len(srt) // 2 - 1] + srt[len(srt) // 2]) / 2
    heads = ["Comparable", "Sale", "&minus; Land*", "&minus; Fin. bsmt†", "&minus; Garage†",
             "= Above-grade", "ABSF", "$/SF", "Size‡", "Qual / Cond", "Time", "Adj $/SF", "Indicated"]
    head = "".join(f'<th style="padding:5pt 6pt;text-align:left;">{h}</th>' for h in heads)
    footnote = note or (
        f"*Land at the county's own assessed value. †The subject's finished-basement and garage "
        f"(${bsmt_psf:,.0f}/SF, ${gar_psf:,.0f}/SF) are removed from each comp so above-grade is compared to "
        f"above-grade. ‡Economy of scale (~${econ_psf_per_sf*100:.0f}/SF per 100 SF)."
    )
    stat = (
        f'<div class="stats" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));'
        f'gap:0.6rem;margin:0.6rem 0;">'
        + "".join(
            f'<div class="stat" style="background:{LIGHT};border-radius:6px;padding:0.6rem;text-align:center;">'
            f'<div class="value" style="font-size:1.2rem;font-weight:700;color:{NAVY};">{v}</div>'
            f'<div class="label" style="font-size:0.78rem;color:#666;">{l}</div></div>'
            for v, l in [(f"{_money(min(inds))}–{_money(max(inds))}", f"Adjusted range ({len(inds)} comps, brackets subject)"),
                         (_money(med), "Median indicated — supported value")])
        + "</div>"
    )
    return (
        f'<table style="width:100%;border-collapse:collapse;font-size:0.74rem;margin:0.5rem 0;">'
        f'<thead><tr style="background:{NAVY};color:{WHITE};font-size:0.72rem;">{head}</tr></thead>'
        f'<tbody>{"".join(body)}</tbody></table>'
        f'<p style="font-size:0.74rem;color:#666;margin:0.2rem 0;">{footnote}</p>{stat}'
    )


# -- 16. Cost-to-cure itemized (single values, no ranges) ----------------


def render_cost_to_cure_itemized(items: list[dict]) -> str:
    """Single-value cost-to-cure table.

    Each item: {description, amount}. Total is computed.
    """
    if not items:
        return ""
    body = []
    total = 0.0
    for it in items:
        try:
            amt = float(it.get("amount") or 0)
        except (TypeError, ValueError):
            amt = 0.0
        total += amt
        body.append(
            f"<tr>"
            f'<td style="padding:4pt 8pt;border-bottom:1px solid {BORDER};">'
            f'{_esc(it.get("description"))}</td>'
            f'<td style="padding:4pt 8pt;border-bottom:1px solid {BORDER};'
            f'text-align:right;">{_money(amt)}</td>'
            f"</tr>"
        )
    body.append(
        f'<tr style="font-weight:700;background:#fff8e7;">'
        f'<td style="padding:6pt 8pt;color:{NAVY};">Total cost to cure</td>'
        f'<td style="padding:6pt 8pt;text-align:right;color:{NAVY};">'
        f"<strong>{_money(total)}</strong></td>"
        f"</tr>"
    )
    return (
        f'<div class="card" style="background:{WHITE};border:1px solid {BORDER};'
        f'border-radius:6px;padding:0.7rem 1rem;margin:0.6rem 0;">'
        f'<table style="width:100%;border-collapse:collapse;">'
        f'<thead><tr style="background:{NAVY};color:{WHITE};">'
        f'<th style="padding:6pt 8pt;text-align:left;">Item</th>'
        f'<th style="padding:6pt 8pt;text-align:right;">Cost to Cure</th>'
        f"</tr></thead>"
        f'<tbody>{"".join(body)}</tbody></table></div>'
    )


# -- 17. EMV cross-check -------------------------------------------------


def render_emv_cross_check(
    current_emv, land_adj, cost_to_cure, label: str = "Cross-check value"
) -> str:
    """County-EMV minus land adj minus cost-to-cure reconciliation table."""
    try:
        emv = float(current_emv or 0)
        la = float(land_adj or 0)
        ctc = float(cost_to_cure or 0)
    except (TypeError, ValueError):
        return ""
    xc = emv - la - ctc
    rows = [
        ("Current EMV", emv, ""),
        (
            f"Less: land adjustment",
            -la,
            "",
        ),
        (f"Less: total cost-to-cure", -ctc, ""),
    ]
    body = []
    for rlabel, rval, _note in rows:
        sign_val = f"{'&minus;' if rval < 0 else ''}{_money(abs(rval))}"
        body.append(
            f"<tr>"
            f'<td style="padding:4pt 8pt;border-bottom:1px solid {BORDER};">'
            f"{_esc(rlabel)}</td>"
            f'<td style="padding:4pt 8pt;border-bottom:1px solid {BORDER};'
            f'text-align:right;">{sign_val}</td></tr>'
        )
    body.append(
        f'<tr style="font-weight:700;background:#fff8e7;">'
        f'<td style="padding:6pt 8pt;color:{NAVY};">{_esc(label)}</td>'
        f'<td style="padding:6pt 8pt;text-align:right;color:{NAVY};">'
        f"<strong>{_money(xc)}</strong></td></tr>"
    )
    return (
        f'<div class="card" style="background:{WHITE};border:1px solid {BORDER};'
        f'border-radius:6px;padding:0.7rem 1rem;margin:0.6rem 0;">'
        f'<table style="width:100%;border-collapse:collapse;">'
        f'<thead><tr style="background:{NAVY};color:{WHITE};">'
        f'<th style="padding:6pt 8pt;text-align:left;">Step</th>'
        f'<th style="padding:6pt 8pt;text-align:right;">Value</th>'
        f"</tr></thead>"
        f'<tbody>{"".join(body)}</tbody></table></div>'
    )


# -- 18. Reconciliation table --------------------------------------------


def render_reconciliation_table(rows: list[dict]) -> str:
    """Final reconciliation across methods.

    Each row: {method, value, role}
    """
    if not rows:
        return ""
    body = []
    for r in rows:
        val = r.get("value")
        val_html = _money(val) if not isinstance(val, str) else val
        body.append(
            f"<tr>"
            f'<td style="padding:8pt 10pt;border-bottom:1px solid {BORDER};">'
            f'{_esc(r.get("method"))}</td>'
            f'<td style="padding:8pt 10pt;text-align:right;'
            f'border-bottom:1px solid {BORDER};font-weight:700;color:{NAVY};">'
            f"{val_html}</td>"
            f'<td style="padding:8pt 10pt;border-bottom:1px solid {BORDER};'
            f'color:#666;font-size:0.85rem;">{_esc(r.get("role"))}</td>'
            f"</tr>"
        )
    return (
        f'<table class="reconcile-table" style="width:100%;'
        f'border-collapse:collapse;font-size:0.95rem;margin-bottom:0.3rem;">'
        f'<thead><tr style="background:{NAVY};color:{WHITE};">'
        f'<th style="padding:8pt 10pt;text-align:left;">Method</th>'
        f'<th style="padding:8pt 10pt;text-align:right;">Indicated Value</th>'
        f'<th style="padding:8pt 10pt;text-align:left;">Role</th>'
        f"</tr></thead>"
        f'<tbody>{"".join(body)}</tbody></table>'
    )
