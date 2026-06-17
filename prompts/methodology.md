# Methodology Reference

The appraisal discipline behind a residential appeal. Every other prompt cites this file. The goal of
every section is one question: given the subject and its neighborhood, is there a defensible path to a
lower market value as of **January 2 of the assessment year**?

> The numeric rates below are **example defaults**. Calibrate them to your market with paired sales —
> a rate that materially drives the conclusion should be supported by local evidence, not a default.

## Grade (construction quality)

Counties rate build quality on a letter scale that drives a large share of the $/SF. A grade disagreement
is often the single highest-leverage angle.

| Grade | Meaning | Typical $/SF vs. B |
|-------|---------|--------------------|
| A | Custom / architect-designed, premium materials | +20% to +40% |
| B | Above-average, quality materials, semi-custom | baseline |
| C | Average production build | −10% to −20% |
| D | Below average, older/modest, limited updates | −20% to −35% |

If the county does not publish the grade, say so — do not invent one.

## Condition (current state, separate from grade)

| Condition | What justifies it |
|-----------|-------------------|
| Excellent | Recent full remodel, new kitchen/baths, mechanicals < 5 yrs |
| Good | Well-maintained, some updates, newer roof/HVAC |
| Average | Livable, dated but functional, normal wear |
| Fair | Visible deferred maintenance, dated systems |
| Poor | Significant deferred maintenance, functional/structural problems |

Evidence for a downgrade: listing photos, inspection reports, owner photos, visible exterior
deterioration, permits for emergency repairs.

## Comparable selection

Tighter is better, but over-filtering leaves you no comps. Rough hierarchy:

1. **Same neighborhood / plat** — a plat-mate beats a comp two neighborhoods over.
2. **±30% finished square footage** — same size band.
3. **±20 years built** — same construction era.
4. **Same style** — bungalow to bungalow, not to a split-level.
5. **Recent, arm's-length sales** — within ~2 years of the effective date; older sales need a time
   adjustment.

Relax in this order when needed: style → year → size → neighborhood. Relaxing neighborhood is last.

**Comps must be arm's-length.** Use only sales the state treated as good-for-state-study; an excluded sale
(related party, foreclosure, partial interest, atypical financing) discredits the packet.

## Adjustment discipline

- **Every adjustment needs same-type comparable support.** Per *Diamond Lake v. Hennepin County*, an
  adjustment must be backed by paired-sales or market evidence of that adjustment — not pulled from the
  air.
- **Gross-adjustment thresholds:** < 50% reliable; 50–75% reduced weight; 75–100% minimal weight;
  > 100% do not use the comp.
- **Bracket the subject** — at least one comp adjusting up and one down, so the indicated value is
  interpolated, not extrapolated.
- **Same county only** — finished-SF basis differs across counties.

### Percentage adjustment grid (example default for SFH)

For comp sets spanning 2× or more in sale price, percentage-of-sale-price adjustments scale better than
dollar adjustments. Additive across categories, applied once: `adjusted = sale × (1 + net%)`.

| Adjustment | Example rate |
|------------|-------------|
| Time | +0.25%/month (≈3%/yr) |
| Size | (subj SF − comp SF) / comp SF × 30% pass-through |
| Condition: Average → Below Avg | −15% |
| Condition: Above Avg → Below Avg | −20% |
| Quality: superior grade → subject | −10% |
| Quality: inferior grade → subject | +5% |
| Lot: standard → double | +10% to +15% |
| Age / effective age (within-band) | derive a $/SF-vs-year-built slope from the comp set itself |

Drop comps of unknown condition from the math (list them for transparency). These are starting points —
beat them with paired-sales-derived rates wherever a rate drives the conclusion.

**Age / vintage adjustment (within the selection band).** Where the comp set spans vintage *within* the
±20yr selection band, the raw $/SF median is pulled toward the older comps and understates a newer subject.
Derive a **$/SF-vs-`year_built` slope from the comp set itself** (the data supports a regression) and apply
it as an **age / effective-age adjustment** to the subject's vintage. **Where grade / condition is
unpublished (e.g. Ramsey), `year_built` is the proxy for build quality / effective age** — use it. This
turns the eyeball "these comps are older" judgment into a supportable, *Diamond Lake*-compliant adjustment
rather than an unsupported eyeball. Example: a 1994 subject against comps spanning 1957–2011 (all in-band on
size) shows a ~$100/SF vintage-driven spread the flat grid cannot resolve — the slope does.

## Equalization (independent basis in Minnesota)

Under *Federated Mutual v. Dakota County*, a property assessed above the level of comparable properties
can be reduced **even below market value**. Build it as a standalone argument when the subject's assessed
$/SF (building and/or land) sits above its peer group — not merely as a tie-breaker. Anchor it in the
neighborhood's assessed-value distribution, not a vague "peers were flat."

**Give equalization its own bounding logic — it is an independent indicated value, not a comp.** Compute
the equalized total as a standalone figure: pull the subject's assessed building $/SF down to a
**defensible peer percentile** (use the **p75–p90** band — not the median, unless the median is itself
defensible for this subject's grade/condition) **× subject SF**, plus a parallel treatment of land $/SF
where the land line is the inequity. Present the equalized total as an indicated value that the
reconciliation **may adopt below both the sales range and the subject's own sale** — but only when
assessment-level inequity is the **explicit, stated basis** (*Federated Mutual*), not as a silent
override of the sales conclusion.

**Which $/SF basis the inequity rests on.** The building-line assessed $/SF and the subject's total
EMV/SF can tell different stories — a thin building-line gap can coexist with a rich total assessment, or
the reverse. When they diverge, **prefer comparing the subject's total EMV/SF against the sold-comp total
EMV/SF distribution** — but **only when BOTH the land line and the building line sit at or above their
peer percentile band.** The total-EMV/SF basis captures land and building together, so it is only an
inequity basis when both lines are actually rich. **If the land line is at or below the peer median (the
land is fairly assessed), the inequity rests on the building line only — do NOT use the total-EMV/SF basis
to conclude lower.** A divergence where total EMV/SF reads low while the building line is rich usually
reflects a *larger lot* (more land $ spread over the building SF), not inequity; equalizing on that basis
claims a reduction the data does not support. Tie the basis choice to which line is genuinely rich, not to
which produces the lower number. **State explicitly which basis the equalized number rests on**
(building-line $/SF, land-line $/SF, or total EMV/SF) so the request is auditable.

**The band-floor neutrality rule.** An equalization **reduction exists only when the subject's $/SF is
ABOVE the percentile you equalize down to.** If the subject sits at or below the band floor (e.g. its
building $/SF is at p75, so equalizing to p75 reproduces the EMV), **equalization is neutral** — there is
no inequity to correct, and the **sales conclusion governs**. Do not present a "reduction" that
equalizing to the band would not actually produce.

**Rich-land / neutral-building pocket (between the two branches above).** When the **only** rich line is
land AND the land $/SF percentile sits inside a **bimodal high-land pocket** (lake / view / corner premium)
while the building line is **at or below** the band, equalization is **NEITHER neutral-by-band NOR an
independent below-market basis** — the land premium is **presumptively legitimate**, so the **sales
conclusion governs.** Do not claim a land reduction on that basis, and do not over-invest effort treating
it as a lever. (This is the case the "land at/below median → building-only basis" and "both lines rich →
total-EMV/SF basis" branches do not cover: a genuinely rich land line that reflects a real locational
premium, not inequity.)

## Reconciliation

- Weigh the methods by data quality and buyer behavior; explain the weight in one or two sentences.
- **The "bracket the subject / never below every adjusted comp" rule governs the SALES-COMPARISON
  conclusion only.** Within the sales grid, never reconcile to a $/SF below every adjusted comp — it
  invalidates the grid and reads as arbitrary.
- **Equalization is exempt from that floor.** Because it is an independent indicated value (above), the
  reconciliation may conclude below the sales range *and* below the subject's own sale when equalization
  is the explicit basis and the assessment-level inequity is shown. When the sales conclusion and the
  equalized value disagree, state which one governs and why — do not average them.
- State the effective date (January 2 of the assessment year) in the conclusion.

## Own-sale relevance horizon (single rule)

The subject's own arm's-length sale is the strongest single indicator, but its weight decays with age. The
bands are **numeric and non-overlapping** so a sale exactly on a boundary has one unambiguous treatment
(the triage script applies the same cutoffs):

- **≤ 2.0 years** before the effective date: the **unadjusted** own sale is governing.
- **2.0 – 3.5 years** (`2.0 < x ≤ 3.5`): **time-trend** the sale to the effective date at the default time
  rate (≈ +0.25%/month, ≈ 3%/yr — calibrate to local paired sales) and treat the trended figure as governing.
- **3.5 – 4.0 years** (`3.5 < x ≤ 4.0`): **corroborating only** — it supports the direction of the
  conclusion but does not set it; lead with current comp sales and equalization instead.
- **> 4.0 years**: **non-evidentiary for value** — note it exists, but the raw delta vs current EMV is
  meaningless; do not report it as a finding.

## EMV cross-check (reconciliation aid)

When the appeal targets both a land issue and a condition issue:

```
indicated value ≈ County EMV − land adjustment − cost-to-cure
```

Persuasive in informal review because it speaks the appraiser's language — start from their number, fix
two specific things, land here. Present it as a reconciliation check, not an independent third method, if
the cost-to-cure was sized to close the gap.

## Cost-to-cure

Itemized, single-value line items (no ranges) for the scope to bring the property to typical condition.
Round to $1,000. Itemize at least five lines. For an Average → Below-Average step, the total typically
lands around 12–20% of the median comp sale price. Each line must be a real, defensible repair scope.

## Evidence hierarchy

When sources disagree, trust in this order:

1. **The county's own data** (CAMA card, record sheet) — if the county said it, the county can't argue it.
2. **MLS listing photos/details** on recent sales, including the subject if recently listed.
3. **Recent closed arm's-length sales** (within ~2 years).
4. **Active listings** — directional, not proof.
5. **General market sources** — rate sheets, market reports.
