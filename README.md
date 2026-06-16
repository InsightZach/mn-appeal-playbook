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

Plus the [assessor contact directory](contacts/).

## The toolkit

```
collectors/   residential data collectors for Ramsey and Hennepin (+ county scraping guides)
analysis/     over-assessment analysis: equalization, sales regression, killer comp, condition
scripts/      collect.py (gather county data) and triage.py (score + verdict)
prompts/      packet-gen, triage-judgment, no-appeal, methodology, orchestration
examples/     three sanitized 26p27 worked properties (Ramsey, Minneapolis, Minnetonka)
```

### Quick start

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
# 1. Collect county data for a property (Ramsey or Hennepin)
uv run python -m scripts.collect "884 Ashland Ave" --county ramsey --output properties/884-ashland/

# 2. Triage it — is there an appeal angle?
uv run python -m scripts.triage properties/884-ashland/collected_data.json --baseline-emv 511900
```

`collect.py` gathers the subject, three-year assessment history, neighborhood comps, and recent sales.
`triage.py` scores the over-assessment signals and returns a verdict (`appeal_angle` / `borderline` /
`no_angle`) with reasons — the screen that decides which properties get a full packet.

- **Ramsey:** resolve by address or PID via the Ramsey OpenData FeatureServer.
- **Hennepin:** combines the Hennepin GIS parcel layer, PINS (current 26p27 value), and Minneapolis
  Assessing open data; resolve by 13-digit PID for reliability.

## Notes

- Square-footage basis differs by county (Hennepin = above-grade; Ramsey = includes finished basement).
  Never mix counties in one comp set. See [Data Sources](docs/03-data-sources.md).
- The exact appeal dates for any year print on the valuation notice. Build the operating calendar in
  February, before notices land.
