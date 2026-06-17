"""Render the illustrative no-appeal findings sample (530 Desnoyer Ave) by running
the deterministic builder over its judgment.json — the honest "we checked, there's
no clear angle" deliverable.

    uv run python -m scripts.render_no_appeal_sample   # -> examples/sample-no-appeal-findings.html

This is now a thin wrapper: the content lives in `properties/desnoyer/judgment.json`
and the **scenario + concluded value are DERIVED by `scripts.build_finding`** (no
central comps below EMV → fairly_assessed → concluded at the current EMV, $0
reduction), not hand-typed here. It demonstrates the discipline of testing an
equalization signal against market support: the building $/SF looks high against a
broad median, but the immediate peer group and a real arm's-length sale show the
assessment is fair. Figures are real Ramsey County assessment + sale data.
"""
import json
from pathlib import Path

from report.no_appeal_generator import generate_no_appeal_report
from scripts.build_finding import build_finding

_JUDGMENT = Path(__file__).resolve().parent.parent / "properties" / "desnoyer" / "judgment.json"


def main():
    judgment = json.loads(_JUDGMENT.read_text())
    data = build_finding(judgment)
    html = generate_no_appeal_report(data)

    banner = (judgment.get("meta") or {}).get("banner")
    if banner:
        banner_html = (
            '<div style="background:#fff3cd;color:#7a5c00;text-align:center;padding:0.5rem 1rem;'
            'font-size:0.85rem;border-bottom:1px solid #e6d28a;font-family:Segoe UI,system-ui,sans-serif;">'
            f"{banner}</div>")
        html = html.replace("<body>", "<body>\n" + banner_html, 1)

    out = Path(__file__).resolve().parent.parent / "examples" / "sample-no-appeal-findings.html"
    out.write_text(html)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
