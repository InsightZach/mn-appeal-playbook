# eCRV Reject-Reason Codes (good-for-state-study)

When eCRV's **State Study → "Good for study"** reads **No**, it carries a **reject-reason code** — the MN
Department of Revenue's reason the sale was excluded from the state sales-ratio study. **Any reject reason
means the sale is not good-for-state-study, so it is not a usable arm's-length comp** (list it for
transparency, exclude it from the math). See [Data Sources](03-data-sources.md#ecrv-verification) for how
to pull the field.

> **Why this matters:** in a 2019–2026 metro eCRV sample, only about **48% of recorded sales were
> good-for-state-study** — the majority carried a reject reason. You cannot grab a low sale and assume it's
> a comp; roughly half the time it's excluded. Verify anything load-bearing.

## The codes most likely to kill a comp (non-arm's-length / distressed)

These are the ones to watch — the sale price doesn't reflect open-market value:

| Code | Reject reason | What it means |
|------|---------------|---------------|
| 02 | Relative Sale | Sold to a relative / related business — not arm's-length |
| 03a | Exempt Party Sale | A party is tax-exempt (church, nonprofit, etc.) |
| 03b | Government Agency Sale | Gov't buyer/seller |
| 04 | Partial Interest Sale | Only a fractional interest changed hands |
| 09a | Estate Sale | Probate / estate — seller not a typical market seller |
| 10 | Prior Interest Sale | Buyer already held an interest |
| 15a | Forced Sale | Compelled sale |
| 15b | Foreclosure | Lender-driven |
| 15c | Legal Action | Court / litigation driven |
| 15d | Short Sale | Sold for less than the mortgage owed |
| 20 | Leaseback | Sale-leaseback, price reflects the lease not the fee |
| 21 | Bank Sale (incl. HUD) | REO / bank-owned |
| 22 | Below Minimum Down Payment | Atypical terms |
| 23 | Sale Under Minimum | Below the study's minimum price |
| 26 | Non-open Market that Results in a Non-typical Sale | Catch-all for non-market deals |

## Adjustment / data-quality rejects (price exists but isn't clean)

| Code | Reject reason |
|------|---------------|
| 05 | Statutory Classification Change |
| 06a / 06b / 06c | Income Guarantees / Non-cash Financing / Unusual Financing |
| 07a / 07b | Physical Change / Renovation for imminent resale (flip) |
| 08a / 08b | Correction Deed / Quit Claim Deed |
| 09c | Trade |
| 14a / 14b | Contract Payoff / Mortgage Assumption |
| 16a / 16b | Split or Combined Sales / Value Not Available |
| 17 | Excessive Non-Real Property (price includes personal property, business, etc.) |
| 18a / 18b | Default on contract for deed / Rewrite of Terms |
| 19 | Relocation |
| 24 | Multi-County Sale |
| 25a / 25b | Agricultural Preserve / Assessment Agreement |
| 27 | Court-Ordered Value |
| 29 | Allocated Sale Price |
| 30 | Assessor-Restricted Value |
| 31 | Assemblage (bought to combine with adjacent parcel) |
| 12 | PTCO Instructed |
| Old Sale - 01 | Sale too old for the current study |

## How to use it

- **State Study "Good for study" = Yes** → usable arm's-length comp.
- **= No** → read the code. **Any** of the above = exclude the sale as a comp. The most common comp-killers
  in residential work are **02 (relative), 09a (estate), 10 (prior interest), 15b (foreclosure),
  21 (bank), 26 (non-open market)**, and **07a/07b (physical change / flip)** — a flip is *especially*
  tempting because the price looks like a clean market sale, but the renovation between buy and resell
  makes it non-comparable.
- Note the separate **County Study** field can read Yes while the **State Study** reads No; the **State**
  study governs arm's-length comps.

*(Code list and prevalence from the MN DOR eCRV record set; codes are the DOR sales-ratio-study reject
taxonomy. Reconfirm against the eCRV detail page for any specific sale.)*
