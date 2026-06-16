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
| **eCRV** (electronic Certificate of Real Estate Value) | Arm's-length sale records, good-for-state-study flag | Statewide | The only comps that survive scrutiny — see below |
| **MetroGIS parcels** (per-county shapefiles) | Lot geometry, acreage | Both | For lot-size and proximity work |
| **Beacon / county CAMA card** | Structure detail, grade, condition (CDU) | Where published | Suburban Hennepin has no bulk SF source — owner/MLS fallback |

## The current-value trap (Hennepin)

The Hennepin GIS parcel layer carries the **prior** assessment, not the value under appeal. The appealed
26p27 value comes only from **PINS**. If you build a savings estimate off the GIS layer you are appealing
last year's number. Always confirm the current assessment-year value from PINS (Hennepin) or the current
FeatureServer fields (Ramsey) before quoting it.

> This is the same class of error to avoid that we have seen in filed packets that cite a "current
> assessed value" one or two years stale. The baseline must be the value actually under appeal for the
> assessment year you are working.

## The square-footage basis trap

Living area is **not** defined the same way across counties:

- **Ramsey** `LivingAreaSquareFeet` **includes** finished basement.
- **Hennepin / Minneapolis** SF is **above-grade only**.

A $/SF comparison that mixes the two bases is meaningless. **Never mix counties in one comp set**, and
always label which basis a figure uses. Within a county the basis is consistent, so percentile and
$/SF comparisons are valid.

## Why "good-for-state-study" sales are the only comps that count

eCRV flags whether a sale qualified for the Department of Revenue sales-ratio study — i.e., whether the
state treated it as an **arm's-length, open-market** transaction. Sales that are *excluded* (related
parties, foreclosures, partial interests, atypical financing) are not evidence of market value, and an
assessor will dismiss them instantly.

- **Use:** good-for-state-study sales within roughly one mile and 24 months, same property class, similar
  size and vintage.
- **Do not use:** sales the state excluded from its ratio study — even if the price looks favorable. A
  packet that leans on an excluded sale loses credibility with the appraiser who knows the record.

This is the difference between comps that *look* supportive and comps that *survive a conversation with
the appraiser*. (See [Packet Generation](05-packet-generation.md).)

## Practical collection order

1. Resolve the subject (address → PID) and pull its 3-year assessment history and any own-sale.
2. Pull neighborhood comps (similar SF/year within radius) with their assessed $/SF.
3. Pull good-for-state-study sales in the window.
4. Confirm the **current** assessment-year value (PINS for Hennepin).
5. Fill structure/condition detail from CAMA/Beacon or, for suburban Hennepin, owner-supplied / MLS data.

The included collectors in [`collectors/`](../collectors/) implement this for Ramsey and Hennepin.
