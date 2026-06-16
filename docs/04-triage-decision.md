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
