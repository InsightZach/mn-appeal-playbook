# 10. Data Schema

`scripts/collect.py` writes one `collected_data.json` per property; `scripts/triage.py` reads it and
writes `analysis.json`. This chapter documents both shapes, the units, and which source populates each
field — so the data is usable without reading the collector code.

## `collected_data.json`

```jsonc
{
  "subject":            { ... },        // the property under appeal
  "assessments":        [ { ... } ],    // up to 3 years, newest first
  "neighborhood_comps": [ { ... } ],    // similar homes by SF/year within radius
  "recent_sales":       [ { ... } ],    // arm's-length-eligible sales in the window
  "collected_at":       "ISO-8601 UTC",
  "county":             "ramsey | hennepin",
  "params":             { ... }         // radii, tolerances, sales window used
}
```

### `subject`

| Field | Type | Meaning | Source |
|-------|------|---------|--------|
| `pid` | str | Parcel ID, normalized (no dashes) | County API |
| `address` | str | Street address | County API |
| `city` | str | Municipality | County API |
| `owner_name` | str/null | Owner of record | County API |
| `lat`, `lon` | float | WGS84 centroid | County API |
| `year_built` | int/null | Year built | County API |
| `living_area_sf` | float/null | Finished area — **basis differs by county** (see note) | County API / Mpls open data |
| `sf_basis` | str | `"includes_basement"` (Ramsey) or `"above_grade"` (Hennepin) | derived |
| `parcel_acres` | float/null | Lot size in acres | County API / MetroGIS |
| `plat_name` | str/null | Plat / addition | County API |
| `land_use` | str/null | Use/class description | County API |
| `last_sale_date` | str/null | ISO date of last recorded sale | County API |
| `last_sale_price` | int/null | Last recorded sale price | County API |
| `structure` | obj/null | Hennepin/Mpls structure detail (stories, exterior, baths) when available | Mpls open data |

### `assessments[]` (newest first)

| Field | Type | Meaning | Source |
|-------|------|---------|--------|
| `assess_year` | int | Assessment year (value set Jan 2) | County API / PINS |
| `tax_year` | int | Payable year (`assess_year` + 1) | County API / PINS |
| `emv_total` | float | Estimated market value, total | County API / **PINS (Hennepin current year)** |
| `emv_land` | float/null | EMV land portion | County API / PINS |
| `emv_building` | float/null | EMV building portion | County API / PINS |
| `total_tax` | float/null | Total property tax for that payable year | County API / PINS |
| `special_assessment` | float/null | Special assessments | County API |
| `tax_capacity` | float/null | Tax capacity | County API |

> The **current** (under-appeal) year for Hennepin comes from PINS, not the GIS API — see
> [Data Sources](03-data-sources.md). For Ramsey it comes from the FeatureServer directly.

### `neighborhood_comps[]` and `recent_sales[]`

Same shape (comps are selected for SF/year similarity; sales are selected for recency in the window):

| Field | Type | Meaning | Source |
|-------|------|---------|--------|
| `pid` | str | Comp parcel ID | County API |
| `address`, `city` | str | Comp location | County API |
| `sf` | float/null | Finished area (same county basis as subject) | County API / Mpls open data |
| `year_built` | int/null | Year built | County API |
| `emv_total` / `emv_land` / `emv_building` | float | Comp's assessed values | County API |
| `emv_year` | int | Which assessment year the EMV reflects | derived |
| `sale_price` | int/null | Recorded sale price | County sale data |
| `sale_date` | str/null | ISO sale date | County sale data |
| `sale_code` | str/null | **Hennepin only** — `WARRANTY DEED` / `OTHER – SEE CRV` / `EXCLUDED FROM RATIO STUDIES` | Hennepin GIS |
| `lot_acres` | float/null | Lot size | County API / MetroGIS |
| `lat`, `lon` | float | Location | County API |
| `distance_miles` | float | Distance from subject | derived |

> **SF basis:** Ramsey `sf`/`living_area_sf` **includes finished basement**; Hennepin/Minneapolis is
> **above-grade only**. Consistent within a county; never compare across counties.
>
> **Arm's-length:** Hennepin carries `sale_code` (the triage drops excluded / CRV sales); Ramsey has no
> such flag — verify Ramsey sales via eCRV. See [Data Sources](03-data-sources.md).

## `analysis.json`

Produced by `scripts/triage.py`:

| Field | Type | Meaning |
|-------|------|---------|
| `subject` | obj | Echo of the subject, with `emv_total` set to the current year |
| `assess_date` | str | Effective date (`{assess_year}-01-02`) |
| `emv_history` | array | Per-year `emv_total`, `yoy_change`, `yoy_pct` |
| `baseline_comparison` | obj/null | The listed/source EMV vs. current, and which assessment year it matches (`--baseline-emv`) |
| `subject_own_sale` | obj/null | The subject's own arm's-length sale vs. current EMV, if any |
| `killer_comp` | obj/null | Best-scored comparable sale, with `verdict` and `delta_pct` from EMV |
| `sales_convergence` | obj/null | Multi-model $/SF regression at the effective date, with spread |
| `equalization` | obj/null | Subject vs. comp $/SF percentiles (building and land) |
| `verdict` | str | `appeal_angle` / `borderline` / `no_angle` |
| `reasons` | array | Plain-language reasons behind the verdict |

These two files are the inputs to the [prompts](../prompts/) — the triage-judgment prompt reads them to
produce the appeal / no-appeal call, and the packet prompt builds the narrative from them.
