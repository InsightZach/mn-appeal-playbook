# Operating guide for agents working in this repo

> This file orients an AI agent (Claude Code or any agent that reads repo instructions) to work in
> `mn-appeal-playbook`. It is **self-contained** — the repo depends on no external database, service,
> account, credential, or sibling repo. If you cloned this anywhere, everything you need is here.

## What this repo is

A reproducible playbook + toolkit for **Minnesota residential property-tax appeals** (Ramsey and Hennepin
counties as worked examples). It is both a manual (`docs/`) and a runnable pipeline that turns a property
address into a defensible, branded appeal packet. See [`README.md`](README.md) for the overview.

## What you need to run it

- **Python 3.11+** and [`uv`](https://docs.astral.sh/uv/). Run everything with `uv run` (it resolves the
  environment from `pyproject.toml` / `uv.lock` — do not manage venvs by hand). Deps: `requests`, `numpy`,
  `pytest`. No API keys or secrets — the collectors hit public county ArcGIS/PINS endpoints.
- **A browser-automation capability for two steps only** (Beacon structure cards and listing/condition
  photos): the [`claude-in-chrome`](https://docs.claude.com) MCP, Playwright, or — since the parser just
  needs the page's **text** — a manual copy-paste of the page works too. Nothing else requires a browser.
- Steps 1–2 and 5 (below) run fully offline against the tracked worked examples.

## The pipeline (and the operating model)

```
collect → triage → (browser) Beacon parse → judgment.json → build_packet
```

1. `scripts/collect.py` — pull county data for an address → `collected_data.json`.
2. `scripts/triage.py` — score over-assessment signals → `analysis.json` (verdict + a comp shortlist).
3. Pull Beacon cards (browser) for the subject + shortlisted comps, then `scripts/parse_beacon.py` →
   `beacon.json` (the ABSF / finished-basement / garage split the API lacks).
4. **You** author a small `properties/<slug>/judgment.json` — the irreducible judgment: per comp, a PID +
   `role` + listing-verified quality/condition grades + the sale facts. **This is the only by-hand step.**
5. `scripts/build_packet.py` — assembles the report dict and renders the HTML packet. (For a property that
   is **not** worth appealing, `scripts/build_finding.py` is the twin: it classifies the no-appeal scenario
   from the numbers and renders the findings report — and refuses to call an appealable property "no appeal.")

**The dividing line that matters: scripts are deterministic and never conclude a value; the agent supplies
judgment.** `build_packet` *derives* the concluded value (median of the `role:central` comps) — you never
type it. Don't write a per-property render script; write a `judgment.json`. Full step-by-step orchestration
(automated steps + the human-judgment steps) is in **[`prompts/run-appeal-review.md`](prompts/run-appeal-review.md)
— start there.** The other `prompts/` files are the methodology, packet copy style, and the no-appeal path.

## Reproduce the worked examples (offline — good first run)

```bash
uv run pytest -q                                                          # 114 tests
uv run python -m scripts.build_packet properties/fulham/judgment.json --output /tmp/fulham.html
uv run python -m scripts.build_packet properties/carroll/judgment.json \
    --beacon properties/carroll/beacon.json --output /tmp/carroll.html
```

## House rules (when producing work product)

- **Don't hand-type structure** — ABSF/basement/garage come from `parse_beacon`; the conclusion is derived.
- **Worth-it test = recurring CLIENT savings** (reduction × ETR) clearing ~$1,000/yr — not a fee-vs-cost test.
  Near the floor, confirm the real ETR from the tax statement (`docs/04`, `prompts/run-appeal-review.md`).
- **Packet copy is advocacy, not a methodology essay** — see `prompts/style_guide.md` for the voice and the
  banned phrases. Don't cite automated-estimate (Zestimate-style) *values* as evidence; listing photos/detail
  are fine.
- **Verify before asserting** — condition/quality from listing photos for subject and comps; if a comp's
  photos can't be found, keep its condition adjustment conservative and say so (don't invent a delta).
