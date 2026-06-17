# Hennepin Structure-Detail Guide (for Claude)

Hennepin is NOT on Beacon. Structure data comes from three places, in this
order of preference:

## 1. Minneapolis Assessing open data (bulk, automated)

Already wired into `collectors/hennepin_residential.py` via the
`Assessing_Department_Parcel_Data_2025` FeatureServer. Covers **Minneapolis
parcels only**. Provides: ABOVEGROUNDAREA (the ABSF equivalent),
BASEMENTAREA, stories, exterior wall, bath/bedroom counts, garage stalls,
construction type, assessor neighborhood. No scraping needed — `collect`
attaches it to the subject (`subject.structure`) and to every Minneapolis
comp/sale automatically.

**Limitations vs Beacon:** no grade/quality rating, no condition rating, no
finished-basement split (BASEMENTAREA is total, not finished), no garage SF.

## 2. Hennepin PINS (per-PID, automated)

`https://www16.co.hennepin.mn.us/pins/pidresult.jsp?pid={PID}`

Plain HTTP. Value/tax data only — **no structure description**. Param map
(verify against the page header, it cycles annually; current as of Jun 2026):

| Params | Returns |
|--------|---------|
| `assmt=1` | Next assessment (2026 → pay 2027), land/building split |
| (none) | Current tax summary (2025 assess → pay 2026), EMV + net tax only |
| `year=2025` | Pay-2025 summary (2024 assessment) |

## 3. Zillow / Redfin (browser, subjects only)

For **suburban Hennepin** (Minnetonka, etc.) there is no bulk SF source.
For the subject property, scrape Zillow per `collectors/zillow_helpers.md`
to get finished SF, basement type, baths. Record the source in the workfile
— Zillow SF is MLS-reported, not assessor-certified, so label it.

Suburban comps will have `sf: null`; comp selection falls back to
year-built + distance and $/SF analyses are skipped. Say so in any report.

## Assessment-year gotchas

- Hennepin GIS (`LAND_PROPERTY` layer) carries the **prior** assessment
  (LAND_MV1/BLDG_MV1) plus current-payable tax. Not the appealed value.
- The appealed 26p27 value comes ONLY from PINS `assmt=1`.
- MetroGIS parcel EMVs for Hennepin lag two years (e.g. they matched the
  2024 assessment, not the current payable year).
- `sf` everywhere in Hennepin records is **above-grade** SF. Ramsey's
  `LivingAreaSquareFeet` includes finished basement. Never mix counties in
  one comp set.

## Structure → packet (no Beacon needed)

Because Hennepin's `sf` is already above-grade (= Ramsey's Beacon `ABSF`),
**Hennepin needs no browser structure pull.** `build_packet` / `build_finding`
get the subject's and comps' ABSF straight from `collected_data.json` via the
county-routed resolver (`analysis/structure.py`) — pass `--collected` (not
`--beacon`):

```
uv run python -m scripts.build_packet properties/<slug>/judgment.json \
    --analysis properties/<slug>/analysis.json --collected properties/<slug>/collected_data.json \
    --output properties/<slug>/packet.html
```

So a Hennepin `judgment.json`, like a Ramsey one, carries **no hand-typed ABSF**.
Caveat: per-comp finished-basement and garage aren't published, so the Hennepin
grid runs a **flat above-grade comparison** (both sides 0 basement/garage —
symmetric, conservative). Suburban Hennepin (Minnetonka etc.) with `sf: null`
can't run the grid at all; lean on equalization + the own sale there. To add
precision later (per-comp basement, etc.), wire a new source into
`analysis/structure.py` — the output shape is the contract.
