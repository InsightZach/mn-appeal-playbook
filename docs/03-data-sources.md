# 3. Data Sources

An appeal is only as good as the data behind it. The strongest argument is always built from the
**county's own records** plus **arm's-length sales the county itself trusts**. This chapter lists the
residential data sources for the two example counties and the traps that produce wrong conclusions.

## Source table

| Source | Provides | County | Notes |
|--------|----------|--------|-------|
| **Ramsey OpenData FeatureServer** (parcels layer) | Subject, neighborhood comps, recent sales, 3-year assessments, **`BasementYN` / `Stories` / `BedRoom` / `GarageSquareFeet` / `ExteriorWallDescription`** | Ramsey | `LivingAreaSquareFeet` = **Total Finished SF** (above-grade ABSF **+** finished basement). The API carries **no ABSF / finished-basement split** — that (and garage/baths/attic detail) is **Beacon-only** (see [Beacon guide](../collectors/beacon_scraper.md)) |
| **Hennepin GIS — LAND_PROPERTY layer** | Parcel master, owner, lot, sales, prior-year EMV | Hennepin | Current (appealed) value is *not* here — see PINS |
| **Hennepin PINS** (`pidresult.jsp`) | Current 26p27 assessment value | Hennepin | Plain HTTP; two page formats (assessment vs. tax summary) |
| **Minneapolis Assessing open data** | Above-grade SF, year built, baths, exterior, stories | Hennepin (Mpls only) | Minneapolis parcels only; no finished-basement split |
| **County sale data** (Ramsey FeatureServer / Hennepin GIS sale fields) | Recent sale price + date; Hennepin also a **sale code** | Both | What the collectors actually use for comps — see the sales section below |
| **eCRV** (electronic Certificate of Real Estate Value) | Arm's-length sale records + good-for-state-study flag | Statewide (MN DOR) | The gold standard for arm's-length comps; **documented here, not yet collected** — see below |
| **MetroGIS parcels** (per-county shapefiles) | Lot geometry, acreage | Both | For lot-size and proximity work |
| **Beacon / county CAMA card** | Structure detail, grade, condition (CDU) | Where published | Suburban Hennepin has no bulk SF source — owner/MLS fallback |
| **Listing data** (owner-supplied / MLS) | Photos, interior detail, sale corroboration, condition | Both | Sourced, not scraped — see [listing enrichment guide](../collectors/listing_enrichment.md) |
| **EffectiveYearBuilt** (assessor's condition-adjusted age) | Effective age — a renovation/condition-adjusted vintage | Ramsey (API) | Ramsey only; Hennepin/Mpls don't publish it. Drives the effective-age comp refinement (below) |

## Condition and quality signals — the cross-county tier, plus Ramsey's effective age

Condition and construction grade drive a large share of $/SF, but they are the **scarcest elements to
support** and (in Ramsey) absent from the API. The toolkit handles this in three layers, weakest data need
first:

1. **Assessed building $/SF as a universal tier proxy (both counties).** `emv_building ÷ SF` is the
   county's own implied quality/condition signal, available everywhere. `scripts/triage.py` uses it as the
   primary comp **tier screen** — comps outside ~0.60–1.50× the subject's building $/SF are dropped so the
   sales median rests on same-tier peers (`sales_comparison_indicated.subject_assessed_building_psf` /
   `tier_screened_out`). This is **TARE secondary-data analysis** (the assessor's data supporting a
   selection), and it groups by assessment while valuing by sales — never concluding off the disputed value.
2. **EffectiveYearBuilt — condition refinement (Ramsey only).** Where published, the assessor's
   condition-adjusted age narrows the median to condition-comparable peers and flags the case where the
   **subject itself** is the condition outlier (`subject_condition_outlier` + a direction note). Hennepin/
   Mpls don't publish it, which is exactly why the assessed-$/SF tier — not effective age — is the universal
   gate.
3. **The agent condition read (both counties).** For the load-bearing comps the triage shortlists
   (`condition_verify_shortlist`) and the subject, the agent reads actual condition from listing/CAMA detail
   and assigns a tier on the methodology house scales — see the [listing enrichment guide](../collectors/listing_enrichment.md)
   and `run-appeal-review.md` step 3b. A same-tier comp needs **no** condition adjustment (the goal); a
   divergent load-bearing comp is quantified by cost-to-cure, never an imported table %.

## Which source has the *new* assessment, and when

The single most important data-timing fact in Minnesota: **the API that serves a parcel does not carry
the new assessment during the months you are appealing it.**

| Window | Where the new (under-appeal) value lives | Where the GIS/parcel API points |
|--------|------------------------------------------|---------------------------------|
| **Jan – ~June** (appeal season) | **PINS** (`assmt=1`) for Hennepin; current FeatureServer fields for Ramsey | Hennepin GIS still serves the **prior** year — the new value is not finalized |
| **~July onward** (post county board) | The value is finalized and **no longer "new"** | The GIS/parcel API now carries it as the current assessment |

So during the exact window you need it — January through June — the Hennepin GIS API is the *wrong* place
to read the value under appeal; you must use **PINS**. After the county boards finish (~July), the
finalized value flows into the API because at that point it is simply the current assessment. The Hennepin
collector already routes around this (it reads the current value from PINS, not the GIS layer); Ramsey's
FeatureServer exposes the current-year fields directly.

> **The baseline trap:** build a savings estimate off the GIS API in the spring and you are appealing last
> year's number. We have seen filed packets cite a "current assessed value" that was one or two years
> stale for exactly this reason. Always confirm the value is for the assessment year under appeal.

## The square-footage basis trap

Living area is **not** defined the same way across counties, and within Ramsey the API's SF blends
above-grade and basement:

- **Ramsey** `LivingAreaSquareFeet` = **Total Finished SF = above-grade (ABSF) + finished basement.**
  (Verified against Beacon CAMA cards: 1704 Eustis API 1,195 = ABSF 1,020 + 175 finished basement;
  1589 Fulham API 1,440 = ABSF 1,440 + 0.) The API gives `BasementYN` (yes/no) but **not** the ABSF /
  finished-basement split — that is **Beacon-only** ([Beacon guide](../collectors/beacon_scraper.md)).
- **Hennepin / Minneapolis** SF is **above-grade only**.

**The basement trap.** A comp's sale price paid for its finished basement too, so two homes with the same
Total Finished SF are not comparable if one is mostly above-grade and the other carries a big finished
basement (basement SF is worth less than above-grade). Pull **ABSF + finished-basement SF from Beacon** for
the subject and every load-bearing comp, show them broken out, and adjust the difference. A subject with an
unfinished basement vs. comps with finished basements (and garages) is a real, value-lowering adjustment.
A $/SF comparison that mixes counties — or that ignores the basement/garage split — is meaningless. **Never
mix counties in one comp set**, and always label which basis a figure uses. Within a county the basis is consistent, so percentile and
$/SF comparisons are valid.

## Sales: what counts, what the toolkit collects, and the eCRV upgrade

**The standard.** Only **arm's-length, open-market** sales are evidence of market value. The Department of
Revenue's sales-ratio study flags exactly these as **good-for-state-study**; sales it *excludes* (related
parties, foreclosures, partial interests, atypical financing) will be dismissed by any appraiser who knows
the record. A comp that *looks* supportive but was excluded from the ratio study is worse than no comp.

**What the included collectors actually use today.** The toolkit pulls **county-provided sale data**, not
eCRV, and approximates the good-for-study standard with the data each county exposes:

| County | Sale data available | Arm's-length filter |
|--------|---------------------|---------------------|
| **Hennepin** | sale price, date, and a **sale code** (`WARRANTY DEED`, `OTHER – SEE CRV`, `EXCLUDED FROM RATIO STUDIES`) | The triage keeps `WARRANTY DEED` and drops excluded / CRV sales — a solid proxy for good-for-study |
| **Ramsey** | sale price and date in the **API**; the good-for-study sale-qualification code is on **Ramsey Beacon** (e.g. `02-RELATIVE SALE OR RELATED BUSINESS`), not the API | Pull the Beacon sale code (agent/browser, same Beacon as structure) or verify via eCRV |

So Hennepin comps are filtered to a defensible arm's-length set automatically from the API; **Ramsey comps
are not filtered by the script** — but the good-for-study answer is one agent pull away (Ramsey Beacon's
sale-qualification code, or eCRV). Verify any load-bearing Ramsey comp before relying on it.

### Arm's-length verification — Beacon + eCRV (agent-driven) {#ecrv-verification}

The Ramsey OpenData API has no good-for-study flag (149 fields, only `SalePrice` / `LastSaleDate` for
sales) — but the determination **is published**, so this is an **agent pull**, not a missing data point.

**eCRV is the authoritative source (public, no login).** MN DOR's eCRV public search returns the state's
own good-for-study determination on every completed sale:

- **Search:** `mndor.state.mn.us/ecrv_search` → **Parcel ID** tab → Search Type **Completed**, pick the
  **County**, enter the parcel ID → Submit. The results list every eCRV (sale) for that parcel by date;
  click the **eCRV ID** to open the detail.
- **Read on the detail page** (under *County Data Information*):
  - **County Recommendation for State Study → "Good for study"** — **this is the field that governs an
    arm's-length comp** (it's the *state* sales-ratio study). If **No**, read the **Reject reason** code
    (e.g. `09a – Estate Sale`, relative/related-party, foreclosure, atypical financing) and **do not use
    the sale as a comp.** The full DOR reject-reason taxonomy — and which codes are the common comp-killers
    — is in [eCRV reject-reason codes](ecrv-reject-reasons.md). (Only ~48% of recorded sales pass the state
    study, so this check matters.)
  - Note the **County Study** "Good for study" is a *separate* field and can say **Yes** while the State
    Study says **No** — don't confuse them; the **State** study is the one for arm's-length comps.
  - The page also gives **deed type** (e.g. *Probate Deed*), **sale net amount**, year built, and the
    **county assessment at the time of sale** (land / building / total, assessment year) — useful for
    judging the sale and for the comp's own-EMV ratio.
  - *Worked example:* parcel `052823430032`, sale 2020-08-12, **$715,000**, *Probate Deed* — County Study
    **Yes**, but **State Study No, reject 09a – Estate Sale**. So this is **not** a usable arm's-length
    comp despite a clean-looking price.

**Ramsey Beacon** (the Schneider site we already pull for structure) shows the same exclusion as a
**sale-qualification code** on its sales-history section — e.g. `02-RELATIVE SALE OR RELATED BUSINESS`.
Grab it inline while pulling grade/condition for a quick first read; confirm anything load-bearing in eCRV.

The triage script's `< 0.80× own-EMV` distressed screen is only a cheap automated first pass.

**When a comp is load-bearing (it drives the conclusion) — and for the subject's own sale —** verify the
**State Study good-for-study** in eCRV, use the sale only if it clears, otherwise list it for transparency
and exclude it from the math, and **disclose the screen applied** in the packet. Same agent-enrichment
principle as listing condition: the **script** gives county data, the **agent** verifies it at the
authoritative source. A bulk eCRV *collector* is a possible future add; today it's an agent step on the
comps that carry weight. See the enrichment step in [`run-appeal-review.md`](../prompts/run-appeal-review.md).

## Practical collection order

1. Resolve the subject (address → PID) and pull its 3-year assessment history and any own-sale.
2. Pull neighborhood comps (similar SF/year within radius) with their assessed $/SF.
3. Pull recent sales in the window; filter to arm's-length (Hennepin sale codes; verify Ramsey via eCRV).
4. Confirm the **current** assessment-year value (PINS for Hennepin; FeatureServer for Ramsey).
5. Fill structure/condition detail from CAMA/Beacon, then enrich with listing data (owner-supplied
   first) to corroborate the sale, test the condition angle, and catch SF/year discrepancies — see the
   [listing enrichment guide](../collectors/listing_enrichment.md).

> **Request the full property record card early.** Where the qualitative grades (quality, CDU/condition)
> aren't in the online data — common for county-assessed Hennepin — submit a records request to the
> assessor for the field card at the start, not after the packet is built. Those inputs are the
> residential appeal's first lever: see **[The Property Record Card (CAMA Inputs)](field-card.md)**.

The included collectors in [`collectors/`](../collectors/) implement this for Ramsey and Hennepin. See
the [data schema](10-data-schema.md) for the exact shape and source of every field they emit.
