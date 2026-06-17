# 4. Is the Appeal Worth It?

Not every property should be appealed. Filing on a parcel that is fairly assessed wastes the team's time,
spends credibility with the assessor, and — under a contingency model — produces no revenue. A disciplined
program **triages every parcel first** and only builds packets for the ones with a real angle. A credible
"no, we don't see it here" is a feature: it is what lets the assessor trust the appeals you *do* bring.

## The over-assessment signals

Screen each parcel against the signals below. None is decisive alone; together they separate the
appeal-worthy from the fairly-assessed.

| Signal | What it means | Strength |
|--------|---------------|----------|
| **Subject's own recent sale below EMV** | The property itself sold (arm's-length) below its assessed value | Strongest single signal |

> **What "recent" means, and who applies it.** The **script** flags *any* own sale below EMV — it does not
> judge recency. The recency judgment (the **~2-year governing / ~4-year corroborating-only** horizon) is
> applied **downstream** by [`triage-judgment.md`](../prompts/triage-judgment.md) and
> [`methodology.md`](../prompts/methodology.md#own-sale-relevance-horizon-single-rule); a sale older than
> ~4 years is *not* a market-value floor. Read the "strongest signal" rating above as the **recent** case;
> a stale own sale is corroboration of direction at most.
| **Comparable arm's-length sales below EMV** | Good-for-state-study sales of similar homes closed below the subject's assessment | Strong |
| **Building $/SF in the top percentiles vs. peers** | Subject assessed higher per square foot than most comparable homes | Strong |
| **Land $/SF above comparable lots** | Land line is rich relative to the same block/plat | Moderate; check for value tiers |
| **EMV year-over-year jump** | A large one-year increase that outran the market | Moderate — explains *why* to appeal |
| **Equalization gap** | Subject assessed above the neighborhood ratio level | Independent basis in MN (see below) |

> **Equalization is its own basis in Minnesota.** Under *Federated Mutual v. Dakota County*, a property
> assessed above the level of comparable properties can be reduced **even below market value**. Don't
> treat equalization as a tie-breaker — it is a standalone argument when the subject is assessed higher
> than its peer group.

## The worth-it threshold

A signal is necessary but not sufficient. The expected result has to justify the work:

```
expected tax savings  =  likely EMV reduction  ×  effective tax rate (ETR)
```

**The test is the CLIENT SAVINGS, not a fee clearing a cost.** An automated (Owlue) operation has a
**~$0 marginal cost per appeal** — there is no fixed "cost to pursue" (data + packet + filing) to recover,
so the gate is **not** a fee-vs-cost break-even. It is simply: *is the recurring tax savings to the client
large enough to be worth filing?* See [Reduction Math](09-reduction-math.md) for the ETR mechanics
(including the prior-year-ETR proxy used before payable-year rates publish).

### The minimum (illustrative — set per engagement)

The gate is a hard yes/no, so the floor must be fixed up front. **The figures below are illustrative
placeholders, not calibrated Owlue economics** — replace them per engagement; the triage script's
`worth_it_gate` carries the same placeholders and flags itself informational-only.

| Input | Illustrative placeholder (set per engagement) |
|-------|-----------------------------------------------|
| **Minimum annual client savings** | **~$1,000/yr** — pursue only if `likely EMV reduction × ETR ≥ ~$1,000` |
| **Contingency %** | **~30%** of the client's savings — so the ~$1,000 floor ≈ a **~$300** year-1 firm fee |
| **NOT used** | ~~a fixed "cost to pursue"~~ — automated marginal cost is ~$0; do not subtract a loaded cost |

Apply it as a single line: **`likely EMV reduction × ETR ≥ ~$1,000/yr`** in client savings. (Multiply
across years if the reduction is expected to hold more than one.)

> **High EMV does not by itself clear the gate — it is the dollar SAVINGS that decides.** A fixed %
> reduction yields more dollars on a high-value parcel ([docs/09](09-reduction-math.md)), but a **modest
> equalization-only reduction can still fall below the $1,000/yr savings floor.** *Worked example:* a
> **$1.8M** parcel with a thin **$40K** reduction at a **1.3% ETR** is only **≈ $520/yr** of client savings
> — **below the ~$1,000 floor**, so not worth filing despite the high value. Conversely a genuine **$73K**
> reduction at **1.5% ETR** is **~$1,100/yr** — clearly worth it. The *reduction*, not the EMV, drives the
> gate; never reject a real four-figure-savings reduction because a 30%-of-savings fee looks small.

## The verdict

Triage produces one of three verdicts per parcel, with the reasons attached:

| Verdict | Meaning | Action |
|---------|---------|--------|
| **Appeal angle** | One or more strong signals; expected savings clears the threshold | Build the full packet; engage the assessor |
| **Borderline** | Mixed signals or marginal savings | Judgment call — often worth a low-cost open-book conversation but not a full packet |
| **No angle** | Assessment is supported by the evidence | Do not appeal. Document why, so the client and assessor both see the work was done. |

## Why the honest "no" matters

An appeals shop that files on everything trains assessors to discount its filings. A shop that files
selectively — and can show it passed on the fairly-assessed parcels — earns the appraiser's attention on
the cases it does bring. The no-appeal finding is also a real client deliverable: it tells the owner the
property was reviewed and the assessment is fair, which is worth saying plainly.

The included triage tool ([`analysis/`](../analysis/)) computes these signals from the collected data and
emits the verdict with reasons, so the screen is consistent across the whole list before any packet is
written.
