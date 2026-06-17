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

> **Ramsey provides no grade / condition / CAMA / structure detail** in its API — `structure` is null and
> comps/sales carry no `sale_code` and no condition. That is a limit of the **county data**, not of the
> workflow: the **CAMA-error-correction** and **cost-to-cure** approaches (which need grade, condition, or
> basement-finish detail) get that detail from the **agent-driven enrichment step**, not from
> `collected_data.json`. When a condition/CAMA argument is in play, run the
> [listing-enrichment step](../collectors/listing_enrichment.md) (owner listing → Zillow/Redfin/Realtor via
> the browser → Beacon card) and, for sale validity, the
> [eCRV verification step](03-data-sources.md#ecrv-verification). Don't assert condition from nothing — and
> don't stop at "the county data doesn't have it." Hennepin/Mpls supply `structure` and `sf_basis` directly.

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

> **These are two distinct populations with different selection criteria — do not treat them as one set.**
> `neighborhood_comps` are **size/year/distance-filtered** (similar SF, similar year built, within radius)
> and are the basis for the **equalization percentiles**. `recent_sales` are selected for **recency in the
> sales window** and are **NOT size-band-filtered** — they can span the full size/value range of the
> neighborhood. Any **sales-comparison reconciliation must size-filter `recent_sales` itself (±30% SF)**
> before use; reconciling off the unfiltered set extrapolates small-home $/SF onto a large subject (or the
> reverse). Note also that the **all-sizes sales regression in `analysis.json`
> (`sales_convergence`)** is built on the **unfiltered `recent_sales`** — which is exactly why a
> single-model `sales_convergence` is labelled a directional screen, not a reconciled value.

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
> **Arm's-length:** Hennepin carries `sale_code` in its API (the triage drops excluded / CRV sales). Ramsey
> does **not** expose it in the OpenData API — but the good-for-study determination **is** published on
> **Ramsey Beacon** (the Schneider site we already use for structure) as a sale-qualification code, e.g.
> `02-RELATIVE SALE OR RELATED BUSINESS` (an exclusion). So for Ramsey, the answer is an **agent pull**, not
> a missing data point — see the [arm's-length sources](03-data-sources.md#ecrv-verification).
>
> **Arm's-length / good-for-state-study, by source (Ramsey).** `methodology.md` and
> [docs/04](04-triage-decision.md) require comps to be good-for-state-study; an excluded sale discredits the
> packet. The Ramsey OpenData API carries no such flag, so the **script** can't source it — but the agent
> can: the **authoritative** answer is the **eCRV State-Study "Good for study"** field (`No` + a reject
> reason like `09a – Estate Sale` = excluded; the *County* Study field is separate and may differ — the
> *State* study governs). The **Ramsey Beacon** sale-qualification code is a quick inline read while pulling
> structure; the triage **`< ~0.80× own-EMV` distressed screen** is only a cheap automated fallback (e.g.
> 659 Edmund at 0.61× its own EMV is dropped). **Disclose the screen you applied** in the packet (see
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
| `killer_comp` | obj/null | Best-scored comparable sale, selected only from comps **within ±30% of the subject's SF** (and within the ~10th–90th percentile of the comp lot distribution where lot is load-bearing). `verdict` (`kills_appeal`/`confirms_fair`/`supports_appeal`/`discount`/`distressed_outlier`/`neutral`/`no_size_matched_sale`), `delta_pct`/`sale_vs_subject_emv_pct` (sale vs **subject** EMV), **`comp_own_emv_ratio`** (sale ÷ the comp's *own* EMV — the over-assessment gate), and **`implied_subject_value`** (comp sale $/SF × subject SF) with `implied_vs_subject_emv_pct`. `supports_appeal` only fires when the comp sold **below its *own* EMV** (ratio < ~0.93) — the implied-value path also requires that, so an extrapolation off a correctly-assessed comp can't fire it; `confirms_fair` when the comp brackets the subject at/above EMV (affirmative no-angle); `discount` when the comp is a cheaper tier the county assessed correctly (**`comp_own_emv_ratio` ≥ ~0.95, one-sided with no upper bound** — a comp at 1.06× its own EMV is at least as cheaper-tier as one at 1.04×; `implied_subject_value` is suppressed as unreliable); **`distressed_outlier`** when the comp sold **< ~0.75× its own EMV** (likely foreclosure/relative sale — not arm's-length, `implied_subject_value` suppressed, never drives `supports_appeal`); `no_size_matched_sale` when no sale survives the size band (`implied_subject_value` is `None`, sales comparison unavailable). A lone sub-0.90× comp does **not** flip the parcel verdict unless the **size-matched pocket** also sold below its own EMV (triage's `pocket_median_own_emv_ratio` gate). |
| `sales_convergence` | obj/null | Multi-model $/SF regression at the effective date, with spread. `verdict` is `tight`/`loose`/`single_model` (a single model can't "converge"). For a **distinct-model** result, carries **`convergence_gap_vs_emv`** = central − current EMV, so agreement *with EMV* is distinguishable from agreement *between models*. For a **`single_model`** result the dollar gap is **suppressed**: the central figure is self-disclaimed (built on the unfiltered, all-sizes `recent_sales`), so only a renamed **`all_sizes_regression_gap_directional`** (the dollar gap, directional use only) and a qualitative **`direction_vs_emv`** (`"above EMV"`/`"below EMV"`) remain, plus **`central_label`** marking the central figure a directional screen only (not a reconciled sales value). The single-model dollar central never feeds a reason string or the illustrative reduction. |
| `distressed_sales` | array | Recent sales priced **< ~0.80× their own EMV** — likely-distressed outliers flagged by the arm's-length proxy screen (Ramsey has no good-for-state-study flag). Disclosure for the judgment layer, not auto-deleted. |
| `quarantined_sales` | array | Sales **dropped before any median/regression** because their $/SF is **> 4× or < 0.25× the neighborhood median** — corrupt/bulk-deed records (e.g. a $7.2M, $3,713/SF sale on a $301K-EMV parcel; a $30K quit-claim) that would otherwise poison every $/SF figure. Each carries `psf` + `neighborhood_median_psf`. The subject's own record is never quarantined. Disclosure, not silent deletion. |
| `equalization` | obj/null | Subject vs. comp $/SF percentiles (building and land), the **median** and **p80** comp $/SF, `median_implied_total` with **`median_gap_vs_emv`**, the realistic **`equalized_total_p80`** (subject $/SF pulled to the p80 band × SF — the methodology reference point, not the median), and `regression_implied_total`/`regression_gap_vs_emv` when the R² gate passes. The building percentile/median/p80 are taken over a **size-matched (±30% SF) peer set** when ≥5 such comps exist; **`building_percentile_basis`** records `size_matched_within_30pct` vs `all_sizes_fallback`. **`equalization_neutral`** is `true` when the subject's building AND land $/SF both sit at or below the p80 band — the band-floor clamp then reproduces EMV, so `equalized_total_p80 == EMV` means **"no reduction available"**, *not* a genuine reduced indicated value (read the flag, not the number). **`lot_outlier`/`land_term_unreliable`** are `true` when the subject's lot is outside the ~10th–90th percentile of the comp lot distribution; the implied-total **land term is then capped at the county's own `emv_land`**, the "no inequity / at or above EMV" reason that depends on it is suppressed, and **`land_psf_percentile_size_artifact`** is `true` — the land $/SF percentile is then a pure size artifact (a big lot reads low $/SF, a small lot high) and is **excluded from equalization angle decisions** (kept in the dict for transparency). |
| `tax_economics` | obj | `etr`, `etr_proxy_source` (`prior_year_tax` / `county_default`), `savings_per_10k_reduction`, and an **`illustrative_savings`** (likely-reduction × ETR at a default reduction assumption — illustrative only, **not** a forecast or a concluded number) so the worth-it threshold can be applied even when Ramsey carries `total_tax=null`. Also carries a **`worth_it_gate`** (`flag` ∈ `pass`/`borderline`/`fail`/`not_yet_sized`) sized off the implied reduction — **informational only; it does NOT change the `verdict`.** Its `year1_fee_floor_assumed` / `contingency_pct_assumed` are **illustrative placeholders, not calibrated doctrine** — the worth-it call is made downstream ([run-appeal-review.md](../prompts/run-appeal-review.md) Step 3) with the real engagement economics. |
| `verdict` | str | `appeal_angle` / `borderline` / `no_angle` |
| `reasons` | array | Plain-language reasons behind the verdict (defensible signals lead; the killer-comp reason discloses its `comp_own_emv_ratio` / implied-value basis) |

These two files are the inputs to the [prompts](../prompts/) — the triage-judgment prompt reads them to
produce the appeal / no-appeal call, and the packet prompt builds the narrative from them.
