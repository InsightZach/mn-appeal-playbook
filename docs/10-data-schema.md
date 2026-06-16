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
| `last_sale_date` | str/null | ISO date of last recorded sale (independent of the comp-sales window — surfaced even when older than it) | County API |
| `last_sale_price` | int/null | Last recorded sale price | County API |
| `structure` | obj/null | Hennepin/Mpls structure detail (stories, exterior, baths) when available | Mpls open data |

> **Ramsey provides no grade / condition / CAMA / structure detail.** The Ramsey collector emits **no**
> `sf_basis` field, `structure` is **null**, and comps/sales carry **no `sale_code` and no condition**. So
> for Ramsey, the methodology's **CAMA-error-correction** and **cost-to-cure** approaches (which need
> grade, condition, or basement-finish detail) **require a manual Beacon / CAMA pull** — they are **not**
> available from `collected_data.json` alone. Do not attempt a condition/CAMA argument for a Ramsey
> property without that manual pull. Hennepin/Mpls supply `structure` and `sf_basis`.

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
>
> **Arm's-length / good-for-state-study screen (Ramsey proxy).** `methodology.md` and
> [docs/04](04-triage-decision.md) require comps to be good-for-state-study; an excluded sale discredits
> the packet. Ramsey records carry **no `good_for_state_study` / `sale_type` flag**, so the collector
> cannot source one. **Sanctioned proxy until the flag exists:** drop sales priced **< ~0.80× their own
> EMV** as likely-distressed (e.g. 659 Edmund at 0.61× its own EMV is excluded), and **disclose the
> arm's-length screen you applied** in the packet (see
> [appeal-packet.md](../prompts/appeal-packet.md)). `scripts/triage.py` flags `recent_sales` whose
> sale-to-own-EMV ratio is an outlier so a distressed sale cannot silently pull the conclusion down.

## `analysis.json`

Produced by `scripts/triage.py`:

| Field | Type | Meaning |
|-------|------|---------|
| `subject` | obj | Echo of the subject, with `emv_total` set to the current year |
| `assess_date` | str | Effective date (`{assess_year}-01-02`) |
| `emv_history` | array | Per-year `emv_total`, `yoy_change`, `yoy_pct` |
| `baseline_comparison` | obj/null | The listed/source EMV vs. current, and which assessment year it matches (`--baseline-emv`) |
| `subject_own_sale` | obj/null | The subject's own arm's-length sale vs. current EMV, if any. Read from `recent_sales` *or* from the subject's own `last_sale_price`/`last_sale_date`, so an own sale older than the comp window is still surfaced. Carries `years_before_effective` (age vs. the effective date) for the time-adjustment decision. |
| `killer_comp` | obj/null | Best-scored comparable sale. `verdict` (`kills_appeal`/`confirms_fair`/`supports_appeal`/`discount`/`neutral`), `delta_pct`/`sale_vs_subject_emv_pct` (sale vs **subject** EMV), **`comp_own_emv_ratio`** (sale ÷ the comp's *own* EMV — the over-assessment gate), and **`implied_subject_value`** (comp sale $/SF × subject SF) with `implied_vs_subject_emv_pct`. `supports_appeal` only fires when the comp sold below its *own* EMV or its $/SF implies a materially lower subject value; `confirms_fair` when the comp brackets the subject at/above EMV (affirmative no-angle); `discount` when the comp is a cheaper tier the county assessed correctly (`comp_own_emv_ratio` ~0.95–1.05 — `implied_subject_value` is suppressed as unreliable). |
| `sales_convergence` | obj/null | Multi-model $/SF regression at the effective date, with spread. `verdict` is `tight`/`loose`/`single_model` (a single model can't "converge"). Carries **`convergence_gap_vs_emv`** = central − current EMV, so agreement *with EMV* is distinguishable from agreement *between models*. A `single_model`/trivially-tight result also carries **`central_label`** marking the central figure a directional screen only (not a reconciled sales value). |
| `distressed_sales` | array | Recent sales priced **< ~0.80× their own EMV** — likely-distressed outliers flagged by the arm's-length proxy screen (Ramsey has no good-for-state-study flag). Disclosure for the judgment layer, not auto-deleted. |
| `equalization` | obj/null | Subject vs. comp $/SF percentiles (building and land), the **median** and **p80** comp $/SF, `median_implied_total` with **`median_gap_vs_emv`**, the realistic **`equalized_total_p80`** (subject $/SF pulled to the p80 band × SF — the methodology reference point, not the median), and `regression_implied_total`/`regression_gap_vs_emv` when the R² gate passes. |
| `tax_economics` | obj | `etr`, `etr_proxy_source` (`prior_year_tax` / `county_default`), `savings_per_10k_reduction`, and an **`illustrative_savings`** (likely-reduction × ETR at a default reduction assumption — illustrative only, **not** a forecast or a concluded number) so the worth-it threshold can be applied even when Ramsey carries `total_tax=null`. |
| `verdict` | str | `appeal_angle` / `borderline` / `no_angle` |
| `reasons` | array | Plain-language reasons behind the verdict (defensible signals lead; the killer-comp reason discloses its `comp_own_emv_ratio` / implied-value basis) |

These two files are the inputs to the [prompts](../prompts/) — the triage-judgment prompt reads them to
produce the appeal / no-appeal call, and the packet prompt builds the narrative from them.
