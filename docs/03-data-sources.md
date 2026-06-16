# 3. Data Sources

An appeal is only as good as the data behind it. The strongest argument is always built from the
**county's own records** plus **arm's-length sales the county itself trusts**. This chapter lists the
residential data sources for the two example counties and the traps that produce wrong conclusions.

## Source table

| Source | Provides | County | Notes |
|--------|----------|--------|-------|
| **Ramsey OpenData FeatureServer** (parcels layer) | Subject, neighborhood comps, recent sales, 3-year assessments | Ramsey | `LivingAreaSquareFeet` **includes finished basement** |
| **Hennepin GIS — LAND_PROPERTY layer** | Parcel master, owner, lot, sales, prior-year EMV | Hennepin | Current (appealed) value is *not* here — see PINS |
| **Hennepin PINS** (`pidresult.jsp`) | Current 26p27 assessment value | Hennepin | Plain HTTP; two page formats (assessment vs. tax summary) |
| **Minneapolis Assessing open data** | Above-grade SF, year built, baths, exterior, stories | Hennepin (Mpls only) | Minneapolis parcels only; no finished-basement split |
| **County sale data** (Ramsey FeatureServer / Hennepin GIS sale fields) | Recent sale price + date; Hennepin also a **sale code** | Both | What the collectors actually use for comps — see the sales section below |
| **eCRV** (electronic Certificate of Real Estate Value) | Arm's-length sale records + good-for-state-study flag | Statewide (MN DOR) | The gold standard for arm's-length comps; **documented here, not yet collected** — see below |
| **MetroGIS parcels** (per-county shapefiles) | Lot geometry, acreage | Both | For lot-size and proximity work |
| **Beacon / county CAMA card** | Structure detail, grade, condition (CDU) | Where published | Suburban Hennepin has no bulk SF source — owner/MLS fallback |

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

Living area is **not** defined the same way across counties:

- **Ramsey** `LivingAreaSquareFeet` **includes** finished basement.
- **Hennepin / Minneapolis** SF is **above-grade only**.

A $/SF comparison that mixes the two bases is meaningless. **Never mix counties in one comp set**, and
always label which basis a figure uses. Within a county the basis is consistent, so percentile and
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
| **Ramsey** | sale price and date only — **no good-for-study or sale-code flag** | None at the data layer; arm's-length status must be judged manually (or via eCRV) |

So Hennepin comps are filtered to a defensible arm's-length set automatically; **Ramsey comps are not**,
and a reviewer should sanity-check any Ramsey comp against eCRV before relying on it.

**The eCRV upgrade (documented, not built).** eCRV is MN DOR's authoritative record of every qualifying
sale, with the good-for-study determination attached. Pulling comps directly from eCRV — rather than
inferring from county sale codes — is the way to put every comp on solid arm's-length footing, and it is
the only way to get a good-for-study signal for **Ramsey** at all. To verify a sale via eCRV:

1. Look up the sale in the public eCRV system by PID or address.
2. Confirm it is **good-for-state-study** (not excluded), and read the stated terms (financing, personal
   property, related-party indicators).
3. Use it as a comp only if it clears that check; otherwise list it for transparency and exclude it from
   the math.

A dedicated eCRV collector is a natural next addition; the current toolkit treats county sale data +
Hennepin sale codes as the working approximation and eCRV as the verification/upgrade path.

## Practical collection order

1. Resolve the subject (address → PID) and pull its 3-year assessment history and any own-sale.
2. Pull neighborhood comps (similar SF/year within radius) with their assessed $/SF.
3. Pull recent sales in the window; filter to arm's-length (Hennepin sale codes; verify Ramsey via eCRV).
4. Confirm the **current** assessment-year value (PINS for Hennepin; FeatureServer for Ramsey).
5. Fill structure/condition detail from CAMA/Beacon or, for suburban Hennepin, owner-supplied / MLS data.

The included collectors in [`collectors/`](../collectors/) implement this for Ramsey and Hennepin. See
the [data schema](10-data-schema.md) for the exact shape and source of every field they emit.
