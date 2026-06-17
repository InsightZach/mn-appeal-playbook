"""scripts/parse_beacon.py — turn pulled Beacon page-text into a structured beacon.json.

Beacon is browser-only (it captcha-blocks headless HTTP), so the agent navigates to
each parcel's Beacon "Property Value" page and saves the claude-in-chrome
`get_page_text` output to a file named by PID. This script then parses every saved
card with `analysis.beacon.parse_beacon_card` — so ABSF / finished-basement / garage
are NEVER hand-typed into judgment.json. build_packet's `--beacon` join fills each
comp's structure from the result by PID.

Input: a directory of `*.txt` files, each the get_page_text of one Beacon card, named
`<PID>.txt` (e.g. `322923440057.txt`), OR a JSON map {pid: page_text}.

    # save each pulled card as properties/<slug>/beacon_raw/<PID>.txt, then:
    uv run python -m scripts.parse_beacon properties/<slug>/beacon_raw \
        --subject-pid 322923440057 \
        --collected properties/<slug>/collected_data.json \
        --output properties/<slug>/beacon.json

Output shape (consumed by build_packet --beacon):
    {"subject": {pid, absf, contributory_basement_sf, garage_sf, ...},
     "comps": {"<pid>": {absf, contributory_basement_sf, garage_sf, ...}, ...}}
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from analysis.beacon import parse_beacon_card, reconcile_absf


def _norm_pid(pid: str) -> str:
    """Beacon KeyValue / file names are bare digits; normalize away dashes/spaces."""
    return re.sub(r"\D", "", str(pid or ""))


def _load_cards(src: Path) -> dict[str, str]:
    """Return {pid: page_text} from a directory of <pid>.txt files or a JSON map."""
    if src.is_dir():
        return {_norm_pid(p.stem): p.read_text() for p in sorted(src.glob("*.txt"))}
    raw = json.loads(src.read_text())
    return {_norm_pid(k): v for k, v in raw.items()}


def _api_sf_by_pid(collected_path: str | None) -> dict[str, float]:
    """Map normalized PID -> API LivingAreaSquareFeet for the reconciliation check."""
    if not collected_path:
        return {}
    data = json.loads(Path(collected_path).read_text())
    out: dict[str, float] = {}
    subj = data.get("subject") or {}
    if subj.get("pid"):
        out[_norm_pid(subj["pid"])] = subj.get("living_area_sf")
    for s in (data.get("recent_sales") or []) + (data.get("neighborhood_comps") or []):
        if s.get("pid"):
            out.setdefault(_norm_pid(s["pid"]), s.get("sf"))
    return out


def parse_beacon_dir(src: Path, subject_pid: str | None = None,
                     collected_path: str | None = None) -> dict:
    cards = _load_cards(src)
    api_sf = _api_sf_by_pid(collected_path)
    spid = _norm_pid(subject_pid) if subject_pid else None
    subject, comps = None, {}
    for pid, text in cards.items():
        parsed = parse_beacon_card(text)
        parsed["pid"] = pid
        api = api_sf.get(pid)
        if api is not None:
            parsed["reconcile"] = reconcile_absf(parsed, api)
        if spid and pid == spid:
            subject = parsed
        else:
            comps[pid] = parsed
    return {"subject": subject, "comps": comps}


def main():
    p = argparse.ArgumentParser(description="Parse pulled Beacon page-text into beacon.json")
    p.add_argument("src", help="Directory of <PID>.txt cards, or a JSON map {pid: text}")
    p.add_argument("--subject-pid", default=None, help="PID of the subject (routes to the 'subject' key)")
    p.add_argument("--collected", default=None, help="collected_data.json, for the ABSF reconciliation check")
    p.add_argument("--output", default=None, help="Output beacon.json (default: beacon.json next to src)")
    args = p.parse_args()

    src = Path(args.src)
    result = parse_beacon_dir(src, args.subject_pid, args.collected)
    out = Path(args.output) if args.output else (src if src.is_dir() else src.parent) / "beacon.json"
    out.write_text(json.dumps(result, indent=2))

    n_mismatch = 0
    for pid, c in {**({result["subject"]["pid"]: result["subject"]} if result.get("subject") else {}),
                   **result["comps"]}.items():
        rec = c.get("reconcile")
        flag = ""
        if rec and rec.get("reconciles") is False:
            n_mismatch += 1
            flag = "  ⚠ ABSF MISMATCH — verify card"
        print(f"  {pid}: ABSF {c.get('absf')}, contrib bsmt {c.get('contributory_basement_sf')}, "
              f"garage {c.get('garage_sf')}{flag}")
    print(f"Wrote {out}"
          + (f"  ({n_mismatch} ABSF reconciliation mismatch(es) — check those cards)" if n_mismatch else ""))


if __name__ == "__main__":
    main()
