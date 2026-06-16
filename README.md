# Minnesota Residential Property Tax Appeal Playbook

> A reproducible, county-by-county playbook for running residential assessment appeals in Minnesota —
> from data collection through inspection, negotiation, and escalation. Ramsey and Hennepin counties as
> worked examples.

**Status:** scaffolding. See the build roadmap (internal).

## What this is

A complete operating manual plus tooling for the Minnesota appeal lifecycle:

```
data → triage (is it worth appealing?) → packet → submission → inspection → negotiation → escalation → reduction math
```

Worked against the **26p27** assessment cycle (Jan 2, 2026 effective; payable 2027), structured to run
live for **27p28**.

## Contents (in progress)

- `docs/` — the playbook chapters (calendar, jurisdiction map, data, triage, packet, submission,
  inspections, negotiation/escalation, reduction math)
- `collectors/` — residential data collectors for Ramsey and Hennepin
- `analysis/` — over-assessment triage / scoring
- `prompts/` — appeal-packet generation and triage-judgment prompts
- `contacts/` — assessor contact directory by jurisdiction
- `examples/` — sanitized end-to-end worked properties

## Why Ramsey + Hennepin

Ramsey is assessed entirely by the county — the clean single-process case. Hennepin mixes county
assessing with self-assessing cities (Minneapolis, Minnetonka, and others), each with its own appeal
format and windows — the complexity case that shows how to route and run appeals across jurisdictions.
