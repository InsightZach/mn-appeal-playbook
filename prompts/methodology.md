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

Drop comps of unknown condition from the math (list them for transparency). These are starting points —
beat them with paired-sales-derived rates wherever a rate drives the conclusion.

## Equalization (independent basis in Minnesota)

Under *Federated Mutual v. Dakota County*, a property assessed above the level of comparable properties
can be reduced **even below market value**. Build it as a standalone argument when the subject's assessed
$/SF (building and/or land) sits above its peer group — not merely as a tie-breaker. Anchor it in the
neighborhood's assessed-value distribution, not a vague "peers were flat."

## Reconciliation

- Weigh the methods by data quality and buyer behavior; explain the weight in one or two sentences.
- **Reconcile to a value the evidence brackets.** Never request a number below every adjusted comp — it
  invalidates the analysis and reads as arbitrary.
- State the effective date (January 2 of the assessment year) in the conclusion.

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
