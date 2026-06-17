# Methodology Reference

The appraisal discipline behind a residential appeal. Every other prompt cites this file. The goal of
every section is one question: given the subject and its neighborhood, is there a defensible path to a
lower market value as of **January 2 of the assessment year**?

> Any numeric rate below is an **illustrative example, not a default to apply**. Derive each rate that
> drives the conclusion from *this* comp set with the appropriate TARE technique (regression first; see
> Adjustment discipline) — a table number is never the support; the market data is.

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

**Property type / ownership form gate (check this FIRST).** A comp must be the same **ownership form** as
the subject before any other screen. The collectors return **single-family houses only** (Ramsey queries
`LandUseCode='510'`; the Hennepin collectors are SFH-oriented), so the comp/sales sets are houses
regardless of what the subject is. When the subject is a **condominium / common-interest unit** — flagged
by `land_use` containing `CONDO` / `APT OWN` / `CIC` / `COMMON INTEREST`, or by a **nominal `emv_land`**
(e.g. ≤ ~$5,000, because a condo owns no deeded lot) — a fee-simple house's sale **$/SF is land-bundled and
must NOT be applied to the landless condo unit** (it systematically OVERSTATES the condo). The reverse is
equally invalid. In that case the **sales-comparison approach yields NO indicated value** absent true condo
comps (parallel to the "No tier-matched sale" rule below): **state the absence of condo comps as a
finding**, do not project house $/SF onto the unit, and conclude on the **subject's own sale + EMV history +
equalization** (and note that any equalization land percentile is meaningless for a near-zero-land unit).
`scripts/collect.py` prints a `WARNING:` when the subject looks like a condo — do not ignore it.

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

- **Every adjustment must reflect the reactions of market participants** (*The Appraisal of Real Estate*,
  15th ed., Ch. 21). The standard is market support, not a number pulled from the air or imported from a
  table. **Support it with whichever of TARE's techniques the data allows — not paired sales alone**
  (paired data needs two sales alike in all respects but one, which is rarely findable):
  - **Statistical analysis / regression on the comp set** — the practical primary; a regression across
    SF / age (or effective year) / lot / time reads the marginal contributions off the data at once.
  - **Grouped-data analysis** — compare group means (e.g., sales by year) for a time or feature trend.
  - **Secondary-data analysis** — outside market data, *including the county assessor's*, to support a rate
    (this is the basis of our assessed-$/SF tier work).
  - **Trend analysis** — TARE's recommended tool *"when there is a limited number of closely comparable
    sales but a large number of properties with less similar characteristics"* — i.e. when pairs are scarce.
  - **Cost-related** (cost-to-cure, depreciated cost) for condition; **paired data** where a variable can
    genuinely be isolated; **qualitative** (relative-comparison / ranking) where the data won't support a
    precise number — bracket the subject as inferior/superior/similar.
- **Gross-adjustment thresholds:** < 50% reliable; 50–75% reduced weight; 75–100% minimal weight;
  > 100% do not use the comp.
- **Bracket the subject on FEATURES, not price** (TARE Ch. 21: *"it is improper to select comparable
  properties based solely on price"*) — at least one comp adjusting up and one down, so the indicated value
  is interpolated, not extrapolated.
- **Same county only** — finished-SF basis differs across counties.

### Adjustment mechanics (illustrative — DERIVE every rate from the data)

This grid shows the **mechanics only** — percentage-of-sale-price, additive across categories, applied once
(`adjusted = sale × (1 + net%)`), with the **direction** comp→subject. The magnitudes below are
**illustrative placeholders to show the shape of an adjustment — they are NOT rates to apply.** Every rate
that touches the conclusion is **derived from *this* comp set with the TARE technique the data supports**
(see Adjustment discipline above) and documented. Importing a number from this table — or any textbook/house
default — is not support; the data is.

| Adjustment | Mechanic | How to DERIVE the rate (TARE Ch. 21 technique) |
|------------|----------|------------------------------------------------|
| Time | % per month, sale→effective date | regression of $/SF on sale date, or grouped-data (year means) |
| Size | (subj SF − comp SF) / comp SF × *pass-through%* | regress $/SF (or price) on SF across the comp set |
| Age / effective age | slope on `year_built` / effective year | regress the comp set — the worked model below |
| Condition | grade step(s), comp→subject | cost-to-cure / depreciated cost; or qualitative inferior/superior bracket |
| Quality (grade) | one construction-grade step | regression incl. a grade variable; else qualitative ranking |
| Lot | premium for the subject's larger lot | regress land $/SF on lot size (the equalization land trend) |

A **multiple regression across the comp set** derives most of these at once — it is the practical primary
(paired data is one technique, rarely findable). The **age/effective-age slope below is the worked model**:
pull the rate out of the comp set, don't import it. **Drop comps of unknown condition** from the math (list
them for transparency) — and because condition/quality are the *scarcest to support*, the right move is to
**select comps that need no condition/quality adjustment** (the assessed-$/SF tier screen + effective-age
match in triage — TARE secondary-data analysis) rather than manufacture an unsupported one.

**Age / vintage adjustment (within the selection band).** Where the comp set spans vintage *within* the
±20yr selection band, the raw $/SF median is pulled toward the older comps and understates a newer subject.
Derive a **$/SF-vs-`year_built` slope from the comp set itself** (the data supports a regression) and apply
it as an **age / effective-age adjustment** to the subject's vintage. **Where grade / condition is
unpublished (e.g. Ramsey), `year_built` is the proxy for build quality / effective age** — use it. This
turns the eyeball "these comps are older" judgment into a market-derived, supportable adjustment (TARE
statistical analysis — the slope is read off this comp set) rather than an unsupported eyeball. Example: a 1994 subject against comps spanning 1957–2011 (all in-band on
size) shows a ~$100/SF vintage-driven spread the flat grid cannot resolve — the slope does.

**Lot / land handling — extraction, not flat $/SF (TARE Ch. 19).** The flat `$/SF × subject SF` projection
has **no term for the lot** — it implicitly assumes every property sits on a comparable lot, so it strips
land value whenever the subject's lot differs in **size** (a 5-acre subject vs quarter-acre comps) or
**value** (a lakefront/corner premium the comps lack). Handle this with the **extraction (allocation)
technique**: subtract each comp's **county-assessed land** from its sale price to isolate the **building
residual**, take the building `$/SF`, and rebuild the subject as **building `$/SF` × subject SF + the
subject's own assessed land**. Because land is netted out of every comp before the `$/SF`, extraction is
robust for any lot — it is the **governing sales indicator** (the triage emits
`sales_comparison_indicated.extraction_indicated_value`); the flat `$/SF` is reported as a cross-check, and
the two **converge when lots are homogeneous** (a built-in sanity check). Extraction leans on the county's
own land number — generally accurate, and hard for the assessor to disown. **Caveat:** extraction trusts
that land figure, so when the **subject's land line is itself the inequity** (assessed land $/SF above its
peer band — `extraction_land_caveat`), the add-back re-imports the contested value and extraction
overstates; there the lever is **land equalization** (*Federated Mutual*, below), not the sales approach.
The lot adjustment in the grid uses the county land `$/SF` (or the regression's lot coefficient) — one
ordinary adjustment line, not a special case.

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
- **Equalization can land EITHER below OR above the sales conclusion.** (a) When the equalized value is
  LOWER than the sales range and assessment-level inequity (*Federated Mutual*) is the explicit stated
  basis, equalization may govern and pull the conclusion below the sales range. (b) When the equalized
  value is HIGHER than (or yields a SMALLER reduction than) the sales conclusion, the SALES conclusion
  governs the request; equalization is reported only as corroboration that the assessment exceeds peer
  level — never as the requested value. In both cases the request is the largest defensible reduction
  from the GOVERNING approach; do not anchor on the equalization figure merely because the script
  headlines it.
- State the effective date (January 2 of the assessment year) in the conclusion.

## Own-sale relevance horizon (single rule)

The subject's own arm's-length sale is the strongest single indicator, but its weight decays with age. The
bands are **numeric and non-overlapping** so a sale exactly on a boundary has one unambiguous treatment
(the triage script applies the same cutoffs):

- **≤ 2.0 years** before the effective date: the **unadjusted** own sale is governing.
- **2.0 – 3.5 years** (`2.0 < x ≤ 3.5`): **time-trend** the sale to the effective date at the default time
  rate (≈ +0.25%/month, ≈ 3%/yr — calibrate to the comp set: regress $/SF on sale date) and treat the
  trended figure as governing.
- **3.5 – 4.0 years** (`3.5 < x ≤ 4.0`): **corroborating only** — it supports the direction of the
  conclusion but does not set it; lead with current comp sales and equalization instead.
- **4.0 – 5.0 years** (`4.0 < x ≤ 5.0`): **non-governing, but may be cited as TIME-TRENDED directional
  corroboration of the conclusion's direction** (disclosed as stale) — do not set the ask off it. A sale
  just past the 4.0yr line still time-trends to a figure that confirms the *direction* of the conclusion
  about the subject itself, which is more reliable than imperfectly-adjusted inferior comps; cite it as
  disclosed-stale directional support, not as the value indicator.
- **> ~5.0 years**: **non-evidentiary for value** — note it exists, but the raw delta vs current EMV is
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
