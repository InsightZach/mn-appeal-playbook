# Beacon Card Scraping Guide (for Claude)

Beacon ("Property Value" page) has the only authoritative residential structure description in Ramsey County. Always pull this for the subject AND each top comp before final analysis.

## URL pattern (Ramsey)

```
https://beacon.schneidercorp.com/Application.aspx?AppID=959&LayerID=18852&PageTypeID=4&PageID=8471&KeyValue={PID}
```

`{PID}` is the 12-digit ParcelID from the Ramsey API (no dashes).

## Scraping (claude-in-chrome MCP)

1. `mcp__claude-in-chrome__navigate(url=above, tabId=...)`
2. `mcp__claude-in-chrome__get_page_text(tabId=...)` — returns the full Property Value page text
3. Parse the text for these labeled values (they appear in this order):

| Field | What it is |
|-------|-----------|
| `Yr. Built` | Year built |
| `Story Height` | 1, 1.5, 2, etc. |
| `Style` | TWO STORY / BUNGALOW / etc. |
| `Exterior Wall` | STUCCO / FRAME / AL/VINYL / BRICK |
| `Total Rooms` | int |
| `Family Rooms` | int |
| `Total Bedrooms` | int |
| `Full Baths` | int |
| `Half Baths` | int |
| `Attic type` | NONE / UNFIN / PT-FIN 20% / etc. |
| `ABSF` | Above-grade square feet (NOT total living area) |
| `Foundation Size` | Basement footprint |
| `Basement Area Finished` | Finished basement SF |
| `Finished Bsmt Rec Area` | Rec area SF (separate from "finished basement") |
| `Garage Type/Area (Sq Ft)` | e.g., "Detached/768" |

## Critical: ABSF vs API LivingAreaSquareFeet

The Ramsey API's `LivingAreaSquareFeet` field includes the finished basement area. Beacon's `ABSF` is above-grade only. The difference is the `Basement Area Finished` value (or sometimes the rec area).

When building the report:
- Use Beacon ABSF for "above-grade SF" comparisons (this is what assessors use)
- Use API `LivingAreaSquareFeet` for the building $/SF figure that matches the broader equalization dataset
- Always label which figure is which to avoid confusion

## Also pull from the same page:

- **Land:** Frontage, depth, base rate, total land value
- **Additions:** Each addition line (size, type) — useful for unfinished basement portions
- **Other Buildings & Yard Improvements:** Garage details (year built, grade, condition)
- **Valuation history:** 6 years of EMV (improvement + land + total)
- **Sales history → sale-qualification code (good-for-study):** the report's sales section shows each
  sale's qualification code, e.g. `02-RELATIVE SALE OR RELATED BUSINESS` (excluded). This is the
  good-for-study determination the Ramsey OpenData API does **not** carry — pull it while you're on the
  page. Any code other than the "qualified" one means the sale was excluded from the ratio study and must
  not be used as an arm's-length comp. (See [Data Sources](../docs/03-data-sources.md#ecrv-verification).)

## Save format

Save to `properties/{safe_address}/beacon_subject.json` and `properties/{safe_address}/beacon_comp_{addr}.json`.
