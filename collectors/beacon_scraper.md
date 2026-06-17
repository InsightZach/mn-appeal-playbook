# Beacon Card Scraping Guide (for Claude)

Beacon ("Property Value" page) has the only authoritative residential structure description in Ramsey County. Always pull this for the subject AND each top comp before final analysis.

**Which comps?** `scripts.triage` emits `sales_comparison_indicated.condition_verify_shortlist` — the ~8 grid-driving comps with their PIDs (`beacon_keyvalue`) and public sale facts already filled in. Pull Beacon for the subject + those PIDs; you don't choose blind.

**Never hand-type the structure.** Save each pulled page's `get_page_text` and run `scripts.parse_beacon` to produce `beacon.json`; `build_packet --beacon` joins ABSF / basement / garage into the packet by PID. Hand-transcribing ABSF/basement/garage into `judgment.json` is the error surface this avoids.

## URL pattern (Ramsey)

```
https://beacon.schneidercorp.com/Application.aspx?AppID=959&LayerID=18852&PageTypeID=4&PageID=8471&KeyValue={PID}
```

`{PID}` is the 12-digit ParcelID from the Ramsey API (no dashes).

## Scraping (claude-in-chrome MCP — browser required)

Beacon **blocks headless HTTP** (captcha / "you are unable to access"), so this must run through the
browser, not `requests`. Steps:

1. `mcp__claude-in-chrome__navigate(url=above, tabId=...)`
2. `mcp__claude-in-chrome__get_page_text(tabId=...)` — returns the full Property Value page text
3. **Save the text** to `properties/<slug>/beacon_raw/<PID>.txt` (one file per parcel; or collect them into a
   `{pid: text}` JSON map).
4. **Batch-parse** all of them at once:
   ```
   uv run python -m scripts.parse_beacon properties/<slug>/beacon_raw \
       --subject-pid <PID> --collected properties/<slug>/collected_data.json \
       --output properties/<slug>/beacon.json
   ```
   This runs `analysis/beacon.parse_beacon_card` on each card → `{absf, finished_basement_sf,
   contributory_basement_sf, total_finished_sf, garage_sf, full_baths, ...}` and reconciles
   **ABSF + finished basement == API `LivingAreaSquareFeet`** (printing any mismatch to verify). Then
   `build_packet --beacon properties/<slug>/beacon.json` fills the structure by PID. The labeled values, for
   reference:

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

### Two basement figures — don't conflate them

Beacon has **two** finished-basement fields, and they serve different purposes:

- **`Basement Area Finished`** is the figure counted in the API `LivingAreaSquareFeet` total — use it for the
  reconciliation identity (`finished_basement_sf` in the parser).
- **`Finished Bsmt Rec Area`** is finished rec space the API does **not** count but which still carries
  contributory value.

For the **extraction grid** (valuation), the finished-basement contributory SF is the **sum of both** —
`contributory_basement_sf` in the parser, which `build_packet` uses for `fin_bsmt_sf`. A subject that shows
`Basement Area Finished = 0` but `Finished Bsmt Rec Area = 600` has **600 SF** of finished-basement value,
not 0. (2162 Carroll Ave is exactly this case — crediting it shrank an apparent over-assessment by ~$30K.)

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

Raw page text → `properties/<slug>/beacon_raw/<PID>.txt` (or one `{pid: text}` JSON map). Parsed structure →
`properties/<slug>/beacon.json` (`{subject: {...}, comps: {pid: {...}}}`), produced by `scripts.parse_beacon`
and consumed by `build_packet --beacon`. `beacon.json` is sanitized public structure data and may be tracked
as a worked-example fixture; the raw `beacon_raw/` text is gitignored.
