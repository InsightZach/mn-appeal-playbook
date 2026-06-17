# Minnesota Residential Property Tax Appeal Playbook

> A reproducible, county-by-county playbook for running residential assessment appeals in Minnesota —
> from data collection through inspection, negotiation, and escalation. **Ramsey** and **Hennepin**
> counties as worked examples.

This repository is both a **manual** (the `docs/` chapters) and a **toolkit** (runnable Python for the
two example counties). It documents the full appeal lifecycle:

```
data → triage (is it worth appealing?) → packet → submission → inspection → negotiation → escalation → reduction math
```

It is worked against the **26p27** assessment cycle (value set Jan 2, 2026; taxes payable 2027) and
structured to run live for **27p28** (value set Jan 2, 2027; payable 2028).

## Why Ramsey + Hennepin

These two counties teach the two cases any multi-jurisdiction appeal program must handle:

- **Ramsey** — assessed entirely by the county. One process, one calendar, one contact. The clean case.
- **Hennepin** — the county assesses most suburbs, but several cities self-assess (Minneapolis,
  Minnetonka, and others), each with its own appeal format and windows, all funneling to the Hennepin
  County Board. The complexity case — and the one that shows how to route and run appeals across
  jurisdictions.

## The playbook (`docs/`)

| # | Chapter | Covers |
|---|---------|--------|
| 1 | [Appeal Calendar](docs/01-appeal-calendar.md) | The annual windows, why their order matters, 26p27 actuals → 27p28 projection, backward planning |
| 2 | [Jurisdiction Map](docs/02-jurisdiction-map.md) | Finding the assessing authority; Ramsey single-authority vs. Hennepin mixed; Minneapolis vs. Minnetonka |
| 3 | [Data Sources](docs/03-data-sources.md) | County APIs, eCRV good-for-state-study sales, SF-basis and current-value traps |
| 4 | [Is the Appeal Worth It?](docs/04-triage-decision.md) | Over-assessment signals, the worth-it threshold, the honest no-appeal call |
| 5 | [Packet Generation](docs/05-packet-generation.md) | Multi-method, county-record-grounded, adjustment discipline, QA |
| 6 | [Submission](docs/06-submission.md) | Submit through engagement, **why mailing a packet to the board fails** |
| 7 | [Inspections](docs/07-inspections.md) | When they happen, setup, rep presence, owner prep, follow-through |
| 8 | [Negotiation & Escalation](docs/08-negotiation-escalation.md) | The decision gate, procedural levels and leverage, the Tax Court backstop |
| 9 | [Reduction Math](docs/09-reduction-math.md) | Tax savings = reduction × ETR; the prior-year-ETR proxy |
| 10 | [Data Schema](docs/10-data-schema.md) | Field-by-field shape and source of the collector + triage output |

Plus the [assessor contact directory](contacts/).

## The toolkit

```
collectors/   residential data collectors for Ramsey and Hennepin (+ county source & listing-enrichment guides)
analysis/     over-assessment analysis: equalization, sales regression, killer comp, condition, Beacon parser
scripts/      collect.py → triage.py → parse_beacon.py → build_packet.py (the pipeline; see Quick start)
prompts/      packet-gen, triage-judgment, no-appeal, methodology, orchestration (run-appeal-review.md)
report/       HTML packet generator (branded, $/SF adjustment grid + supported value, charts)
properties/   per-property work; the tracked judgment.json + beacon.json are runnable worked examples
contacts/     assessor contact directory (Ramsey, Hennepin county + self-assessing cities)
examples/     three sanitized 26p27 case studies + a rendered sample appeal packet (HTML)
```

### Quick start

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

The pipeline is **collect → triage → (Beacon) parse → judgment.json → build_packet**. Steps 1–2 are
deterministic; step 3 needs a browser (Beacon blocks headless HTTP); step 4 is the analyst's small judgment
file; step 5 derives the conclusion and renders the packet.

```bash
# 1. Collect county data for a property (Ramsey or Hennepin)
uv run python -m scripts.collect "2162 Carroll Ave" --county ramsey --output properties/carroll/

# 2. Triage it — is there an appeal angle? (writes analysis.json next to the input)
uv run python -m scripts.triage properties/carroll/collected_data.json

# 3. Pull the Beacon card (browser) for the subject + the comps triage shortlisted,
#    save each page's text under properties/carroll/beacon_raw/, then parse:
uv run python -m scripts.parse_beacon properties/carroll/beacon_raw \
    --subject-pid 322923440057 --collected properties/carroll/collected_data.json \
    --output properties/carroll/beacon.json

# 4. Author properties/carroll/judgment.json — the only by-hand step: per comp, a
#    PID + role + listing-verified quality/condition grades + the sale facts. (See
#    prompts/appeal-packet.md and the worked example's _doc field.)

# 5. Build the packet — the conclusion is DERIVED (median of the central comps), not typed:
uv run python -m scripts.build_packet properties/carroll/judgment.json \
    --analysis properties/carroll/analysis.json --beacon properties/carroll/beacon.json \
    --output properties/carroll/packet.html
```

`collect.py` gathers the subject, assessment history, neighborhood comps, and recent sales. `triage.py`
scores the over-assessment signals → a verdict (`appeal_angle` / `borderline` / `no_angle`) with reasons
and a comp shortlist. `parse_beacon.py` turns pulled Beacon cards into structured `beacon.json` (ABSF /
finished-basement / garage — the above-grade split the API lacks). `build_packet.py` assembles the report
dict and renders the branded HTML, deriving the concluded value itself.

**Reproduce the two worked examples (no network/browser needed — fully offline):**

```bash
uv run python -m scripts.build_packet properties/fulham/judgment.json --output /tmp/fulham.html
uv run python -m scripts.build_packet properties/carroll/judgment.json \
    --beacon properties/carroll/beacon.json --output /tmp/carroll.html
```

The end-to-end orchestration (automated steps + the human-judgment steps) is mapped in
**[`prompts/run-appeal-review.md`](prompts/run-appeal-review.md)** — start there to understand the workflow.

- **Ramsey:** resolve by address or PID via the Ramsey OpenData FeatureServer; structure from Beacon.
- **Hennepin:** combines the Hennepin GIS parcel layer, PINS (current 26p27 value), and Minneapolis
  Assessing open data; resolve by 13-digit PID for reliability.

## Notes

- **Running this with an AI agent?** See [`CLAUDE.md`](CLAUDE.md) (and [`AGENTS.md`](AGENTS.md)) for the
  self-contained operating guide — the pipeline, what the agent needs, and the house rules. The repo has no
  external database, service, or credential dependency; it runs anywhere Python + `uv` does.
- Square-footage basis differs by county (Hennepin = above-grade; Ramsey = includes finished basement).
  Never mix counties in one comp set. See [Data Sources](docs/03-data-sources.md).
- The exact appeal dates for any year print on the valuation notice. Build the operating calendar in
  February, before notices land.
