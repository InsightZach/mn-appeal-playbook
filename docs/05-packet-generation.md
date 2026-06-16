# 5. Producing the Appeal Packet

The packet is the evidence that supports a conversation with the appraiser. It is not a form letter and
it is not, by itself, what wins the appeal — the conversation and inspection do that (see
[Submission](06-submission.md) and [Inspections](07-inspections.md)). But a strong packet sets the
anchor, frames the discussion, and gives the appraiser something defensible to act on.

## Build from the county's own data

The least rebuttable argument corrects the **assessor's own records**. Lead with the county's CAMA inputs
— grade, condition (CDU), square footage, basement finish, land line — and show where they are wrong for
*this* property as of January 2 of the assessment year. An appraiser can argue with your comp selection;
it is much harder to argue with a correction to their own data sheet.

> **Pull the listing before you commit to a method.** Owner-supplied or public listing data corroborates
> the sale and tells you whether a condition argument is credible. Photos of a renovated home kill a
> condition downgrade (and weaken a "high $/SF" equalization point); photos of a distressed home are the
> backbone of one. Test the angle against the evidence an appraiser can also see — see the
> [listing enrichment guide](../collectors/listing_enrichment.md).

## Use more than one method

A sales-comparison letter with three comps is the weakest defensible form of appeal. Build the methods the
evidence supports:

| Method | When it applies | Notes |
|--------|-----------------|-------|
| **Sales comparison** | Always, if good comps exist | Good-for-state-study sales only; bracket the subject; adjust with same-type support |
| **Equalization** | Subject assessed above neighborhood ratio | Independent basis in MN (*Federated Mutual*); can reduce below market |
| **Condition / CAMA-error attack** | County data overstates grade, condition, or size | The most durable argument — corrects their record |
| **Cost-to-cure** | Deferred maintenance / functional problems | Itemized scope to bring the property to typical condition |
| **EMV cross-check** | Land + condition issues both present | Start from the county's EMV, subtract the land and cost-to-cure corrections |

Match the method to the property. Not every parcel needs all five; every parcel needs more than a bare
sales grid.

## Comparable selection and adjustment discipline

- **Comps must be arm's-length** (good-for-state-study). An excluded sale used as a comp discredits the
  packet.
- **Bracket the subject** — at least one comp adjusting up and one adjusting down, so the indicated value
  is interpolated, not extrapolated.
- **Adjustments need same-type support.** Under *Diamond Lake v. Hennepin County*, an adjustment has to be
  backed by paired-sales or market evidence of that adjustment — you cannot pull a number from the air.
  Heavily adjusted comps (gross adjustments over ~50%) get reduced weight; over ~100%, drop the comp.
- **Same county only.** Square-footage basis differs across counties (see [Data Sources](03-data-sources.md)).

## Reconcile to a defensible number — and never below your own evidence

The requested value must sit **within** the range your comps support. Asking for a number *below* every
adjusted comp invalidates the analysis that produced it and signals to the appraiser that the ask is
arbitrary. Reconcile to a value the packet's own evidence brackets, and state the basis for the weight
given to each method.

## Quality control

Before a packet goes out, verify:

- **Correct baseline** — the value under appeal is the **current** assessment-year EMV, not a prior year.
- **Correct owner** — the actual owner of record, not the filing entity.
- **Correct specs** — square footage, bed/bath, year built match the records (and your corrections are
  flagged as corrections).
- **Internal consistency** — the requested value matches the reconciliation; the comp figures match the
  source data; dates are right.

A single factual error — a wrong owner name, a stale baseline, an unverifiable comp — is what an appraiser
seizes on to dismiss the whole filing. QA is not optional.

## Tooling

The [`prompts/`](../prompts/) directory contains the generation prompts for the appeal packet and the
no-appeal findings, plus the triage-judgment rubric. They are designed to run on the collected county data
([`collectors/`](../collectors/)) and the triage output ([`analysis/`](../analysis/)), so the packet is
grounded in the same records the assessor holds.
