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

Under a contingency model:

```
expected revenue  =  expected tax savings  ×  contingency %   (× years the reduction holds)
```

If expected revenue does not clear the fully-loaded cost to pursue (data, packet, inspection,
negotiation, possible escalation), the parcel is not worth a full appeal — even if it is mildly
over-assessed. See [Reduction Math](09-reduction-math.md) for the ETR mechanics, including the
prior-year-ETR proxy used before payable-year rates are published.

### Worked defaults (illustrative — set the real numbers per engagement)

The gate is a hard yes/no, so two analysts must reach the same call on the same parcel — which means the
inputs have to be fixed up front. **The figures below are illustrative placeholders to make the mechanics
concrete, not calibrated house/Owlue economics.** Replace them with the engagement's actual contingency,
cost, and floor before relying on the gate; the triage script's `worth_it_gate` carries the same
placeholders and flags itself as informational-only.

| Input | Illustrative placeholder (set per engagement) |
|-------|-----------------------------------------------|
| **Contingency %** | **~30%** of year-1 tax savings (typical contingency engagement) |
| **Fully-loaded cost to pursue** | **≈ $1,500** (data + packet + open-book engagement; add for inspection/escalation) |
| **Equivalent year-1-savings floor** | **Pursue only if `year-1 savings × contingency % ≥ ~$450`** (≈ the cost-to-pursue × contingency, the break-even on a single-year hold) |

Apply it as a single line you can actually evaluate: **`likely EMV reduction × ETR × 30% ≥ ~$450`** to
clear on a one-year hold (less if the reduction holds multiple years — multiply the savings across the
years it is expected to hold).

> **Reconcile with [docs/09](09-reduction-math.md): "high value clears easily" is only true for
> large-% reductions.** docs/09 notes a fixed % reduction on a high-value parcel produces more dollars
> than on a modest one — true, but it is the **dollar reduction**, not the EMV, that drives the gate. A
> **modest equalization-only reduction on a high-value parcel can still FAIL the gate.** *Worked example:*
> a **$1.8M** parcel at a **4.8%** reduction (≈ $86K off EMV) and a **1.3% ETR** yields ≈ $1,118/yr of tax
> savings; at **30% contingency** that is only **≈ $335/yr** — **below the ~$450 floor** on a one-year
> hold. High EMV does not by itself clear the gate; the *reduction* has to be large enough. Do not read
> docs/09's "easily does" as a blanket pass for high-value parcels on thin reductions.

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
