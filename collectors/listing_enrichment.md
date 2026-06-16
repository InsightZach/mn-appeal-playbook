# Listing Enrichment Guide (condition + corroboration)

County records tell you the assessed grade, size, and value. They do **not** tell you what the property
actually looks like today. Listing data — photos, interior detail, the sale record — fills that gap. Its
job is not only to *support* a condition argument; it is a **credibility check** that tells you which
arguments are honest before you make them to an appraiser who can pull the same listing.

## What enrichment is for

1. **Corroborate the sale.** An MLS-confirmed closing price/date turns "the county shows a sale" into
   verifiable arm's-length evidence.
2. **Support a condition argument** — when photos show real problems (gutted bath, dated kitchen, deferred
   maintenance, water damage), they are tier-2 evidence behind the county's own record.
3. **Kill a non-credible argument** — when photos show a renovated, well-kept home, a condition downgrade
   is off the table, and a "high building $/SF" equalization point is weaker (the renovation may justify
   the value). Knowing this *before* you file keeps you from making a claim the appraiser will refute in
   thirty seconds.

> A worked example: for 884 Ashland Ave (St. Paul), the listing showed a **renovated interior** and an
> MLS-confirmed **$470,000** sale. Enrichment did not add a condition angle — it removed one, and it
> corroborated the own-sale that is the real basis of the appeal. That is a success, not a dead end.

## What to gather

| Item | Why |
|------|-----|
| Sale price + date (closed) | Corroborates the arm's-length sale; cross-check against county data |
| Finished SF, beds, baths, year built | Cross-check against the county record — **discrepancies are leads** |
| Interior/exterior photos | Condition evidence (or the lack of it) |
| Listing description | "Recently renovated" vs. "needs TLC / sold as-is" — directional condition signal |
| Renovation / system age (roof, HVAC, kitchen) | Supports or refutes condition and effective-age arguments |

**Watch for record discrepancies.** Listing SF and year-built often differ from the county's. For
884 Ashland the listing showed 2,060 SF / built 1970 against the county's 1,355 SF / built 1939. A real
gross-living-area gap can be an appeal point in either direction; an effective-age vs. original-build
difference explains a value the county is defending. Note them; verify before relying on them.

## How to source it — defensibly, in priority order

Listing photos and details are **MLS-licensed content** (e.g., NorthstarMLS / MLS GRID). Source them in a
way that respects that, in this order:

1. **Owner-supplied (best).** The client has rights to their own old listing, photos, and any inspection
   report. This is the cleanest source, carries no terms-of-service issue, and the owner knows what is
   actually wrong with the house. Ask for it at onboarding.
2. **Agent / MLS sheet** the owner authorizes their agent to share.
3. **Manual review of a public listing page** for factual detail (sale price, SF, year, description).

Do **not** build an automated scraper against Zillow, Realtor.com, or an MLS — their terms prohibit it,
the markup is brittle, and republishing MLS photos has licensing limits. Enrichment is a sourced input,
not a scraping job.

## How it feeds the work

- **Triage / judgment** ([`../prompts/triage-judgment.md`](../prompts/triage-judgment.md)) — use it to
  confirm or kill the condition and equalization angles before committing to a packet.
- **Packet** ([`../prompts/appeal-packet.md`](../prompts/appeal-packet.md)) — corroborated sale, condition
  exhibits (only where the evidence supports them), and any verified record discrepancy.
- **Inspections** ([`../docs/07-inspections.md`](../docs/07-inspections.md)) — brief the owner to have the
  listing, photos, and repair documentation ready for the appraiser.
