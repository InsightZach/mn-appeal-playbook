# Prompt — Appeal Packet

Generates the multi-method appeal packet for a property the triage judgment flagged as having an angle.
The packet is the evidence that supports the conversation with the appraiser — build it to be defensible
to a working assessor, not just persuasive to a layperson.

---

## Role

You are a Minnesota residential property tax analyst preparing an assessment appeal for the current
assessment year, effective January 2. Follow [`methodology.md`](methodology.md) exactly and write per [`style_guide.md`](style_guide.md). Lead with the
county's own data; **every adjustment must reflect the reactions of market participants** and be derived
from *this* comp set with the technique the data supports (*The Appraisal of Real Estate*, 15th ed., Ch. 21
— regression first; see [`methodology.md`](methodology.md) "Adjustment discipline"); reconcile to a value
the evidence brackets.

## Inputs

- `collected_data.json`, `analysis.json` for the subject.
- The triage-judgment output (verdict, recommended ask, caveats).
- Any owner-supplied condition evidence (photos, inspection reports, repair estimates), if available.

> **Stop-and-bounce guard.** If, on independent reconciliation, the comp-median and equalization **both**
> land at or above EMV and there is **no** own-sale below EMV, stop and route to
> [`no-appeal-findings.md`](no-appeal-findings.md) — do not manufacture a packet for a fairly-assessed
> property.

## Requirements

1. **Use the current assessment-year value as the baseline** — never a prior-year EMV. State it and its
   effective date.
2. **Use more than one method.** A bare three-comp sales grid is the weakest defensible form. Build the
   methods the evidence supports:
   - **Sales comparison (adjustment grid) — the grid MUST carry every standard line; a partial grid is not
     acceptable.** Good-for-state-study comps only. The required structure (model it on the worked example
     below):
     - **SF basis = Total Finished SF, with ABSF and finished-basement SF broken out per comp AND the
       subject.** Ramsey `LivingAreaSquareFeet` is **above-grade only** (see [Data Sources](../docs/03-data-sources.md#the-square-footage-basis-trap)); add the finished-basement SF from the assessor card / MLS
       (Total Finished SF − ABSF). Compute $/SF on **Total Finished SF**. A subject with an unfinished
       basement vs. comps with finished ones is a real difference — never divide a comp's price (which paid
       for its basement) by ABSF alone.
     - **Itemized adjustments, comp→subject, EACH a line:** **Time** (market trend to the effective date);
       **Size / economy of scale** — `(subj SF − comp SF)/comp SF × pass-through%` (a partial pass-through,
       ~30%, because the marginal SF is worth less per SF than the average — size is a GRID LINE, not a flat
       ×subject-SF); **Quality / construction grade** (± per grade step); **Condition** (± per grade step,
       calibrated to the cost-to-cure); **Lot / location** (the land differential — county land $/SF or the
       equalization land trend). Verify **condition AND quality on listing photos** for the subject and every
       load-bearing comp before grading them.
     - **Bracket the subject (mandatory).** At least one comp adjusting **up** (inferior) and one **down**
       (superior) so the conclusion is **interpolated, not extrapolated** — on BOTH the adjusted-value
       indication and the raw sale prices (a conclusion above every comp's sale price is extrapolation). Do
       not exclude every superior comp; keep one and adjust it down with supported rates.
     - **Derive every rate from the data** (regression / paired clusters — e.g. the renovated-vs-original
       cluster spread gives the condition step), apply **gross-adjustment thresholds** (>50% reduced weight;
       >100% drop), and **reconcile** to mean/median of the adjusted values.
     - **No tier-matched sale.** If **no** arm's-length sale exists within the subject's **size band
       (±30% SF)** and value tier, the sales-comparison approach yields **NO indicated value** — state the
       *absence of tier-matched sales as a finding*. Do **not** extrapolate small-home $/SF onto a large
       subject (a $/SF drawn from 2,000 SF sales projected onto a 5,000 SF subject is the size/tier
       extrapolation methodology.md forbids). Conclude on **equalization + EMV history** alone, and say
       that doing so is the correct response to the missing grid. *Worked example (high-value, no comp):*
       a $1.8M subject with **no** sold comp above ~$1M in its plat — the sales approach indicates nothing;
       the packet leads with the equalization distribution (subject's assessed $/SF vs. its peer band) and
       the EMV history, and **states plainly that no tier-matched sales exist**, rather than building a
       grid from out-of-tier sales.
     - **Condo / common-interest subject (check before treating it as a lot problem).** If the subject is
       a **condominium** (`land_use` = CONDO / `APT OWN` / CIC, or a **nominal `emv_land`**), the triage
       may fire `lot_outlier` / `land_term_unreliable` — but the subject is **not a small-lot house**, it
       owns **no deeded lot at all**. Do **NOT** "add a land adjustment" or hunt for lot-comparable house
       sales (there are none — `lot_matched_n=0`). The correct response is: the **sales-comparison approach
       is UNAVAILABLE** absent condo comps, because a house's land-bundled $/SF cannot be applied to a
       landless unit (it overstates the condo). Route to **own-sale + EMV history** and state the absence
       of condo comps as a finding (see [`methodology.md`](methodology.md) Property type / ownership form
       gate). Treat the rest of this bullet as applying only to fee-simple SFH subjects.
     - **Lot outlier / lot-value difference → use LAND EXTRACTION, not flat $/SF.** When the subject's lot
       differs from the comp set in **size** (a 5-acre subject vs quarter-acre comps) **or value** (a
       lakefront/corner premium the comps lack), the `$/SF × subject SF` projection **silently strips land
       value and is unreliable** — it credits the subject's land at the comps' increment. The fix is the
       **extraction method** (TARE Ch. 19), which the triage computes for you: subtract each comp's
       **county-assessed land** from its sale price to isolate the **building residual**, take the building
       `$/SF`, and rebuild the subject value as **building $/SF × subject SF + the subject's own assessed
       land**. This nets land out of every comp, so it is robust for any lot. Quote
       **`sales_comparison_indicated.extraction_indicated_value`** (with `extraction_n` and the building
       `$/SF` median) as the governing sales figure; report the flat $/SF as a cross-check and note it
       under/overstates a large/small-lot subject. The method leans on the **county's own land number**,
       which the assessor cannot easily disown.
       - **Land-line caveat (when extraction does NOT apply).** Extraction trusts the assessor's land
         figure. When the subject's **land line is itself the dispute** (`extraction_land_caveat` is true —
         assessed land $/SF at/above its peer band, not a small-lot artifact), the add-back re-imports the
         contested land value and extraction **overstates**. There the lever is **equalization on the land
         line** (*Federated Mutual*), not the sales approach — do not quote `extraction_indicated_value`.
       - **No subject assessed land (some Hennepin parcels):** `extraction_indicated_value` is null; the
         building `$/SF` median is still reported. Source the subject's land from PINS / the county card to
         complete the add-back, or fall back to lot-comparable sales.
   - **Equalization** — when the subject's assessed $/SF sits above its peer group (independent basis,
     *Federated Mutual*).
   - **Condition / CAMA-error correction** — where the county's grade, condition, SF, or basement finish
     is wrong for this property. The most durable argument; it corrects their own record. **Note: Ramsey's
     `collected_data.json` carries no grade / condition / CAMA / structure detail** (see
     [`docs/10-data-schema.md`](../docs/10-data-schema.md)) — this approach requires a **manual Beacon /
     CAMA pull** for Ramsey, so do not attempt a condition/CAMA argument from the collected data alone.
   - **Cost-to-cure** and **EMV cross-check** — where deferred maintenance and a land issue both apply.
3. **Reconcile by reliability — this is the judgment, and it is yours, not the script's.** Each approach
   produces a *standalone indicated value* (the sales grid's supported $/SF × subject SF; the equalization
   figure; the subject's own sale). These will often disagree. Do **not** average them and do **not**
   force the conclusion inside the comp range. Weigh each by data quality and **conclude on the strongest
   evidence**:
   - The subject's **own recent arm's-length sale is the single most reliable indicator.** When it diverges
     from the comp grid, conclude on the own sale and say why. The own sale is a **MARKET-VALUE floor**:
     never conclude a *market value* below a recent arm's-length sale of the subject — even if the adjusted
     comps point lower (inferior comps adjusted imperfectly are weaker evidence than the subject's actual
     transaction). **"Recent" is numeric, tied to [`methodology.md`](methodology.md)'s own-sale horizon:**
     within **~2 years** of the effective date the unadjusted sale governs (is the floor); at **~2–3 years**
     time-trend it to the effective date first, then treat the trended figure as the floor. **A stale own
     sale (> ~4 years before the effective date) is NOT a market-value floor and must be excluded from the
     conclusion** — note it as corroboration of direction at most; lead with current comp sales and
     equalization to set the value.
   - **Equalization carve-out (Requirement 3).** The own-sale floor governs the **market-value**
     conclusion only. An equalization (*Federated Mutual*) reduction is an **independent basis** that may
     conclude **below both market value and the own sale** — but only when assessment-level inequity is the
     **explicit, stated basis**. So for the common-looking "own sale supports the EMV, but the subject is
     assessed well above its peers" case: the market-value conclusion holds at the own sale, *and* you may
     additionally present an equalized value below it, stated as an equalization request, not as a market
     value. Say which basis the requested number rests on.
   - State each approach's standalone indicated value, then the concluded value with a one-to-two-sentence
     weighting rationale. The reader must see the judgment that produced the number.
   - *Worked example (884 Ashland — own sale present, governs market value):* the sales grid indicated
     ~$409K and equalization was roughly neutral, but the subject's own arm's-length sale was $470K.
     Concluded value = **$470K** (the own sale governs; the comps corroborate that the EMV is high but are
     not adopted below the actual sale). *(Its inverse — own sale supports EMV but equalization supports a
     reduction — is resolved by the carve-out above: conclude market value at/near the own sale, then make
     the equalization request as the independent basis for going below it.)*
   - *Worked example (no own sale — sales vs. equalization disagree):* the subject has **no** recent
     arm's-length sale of its own. The default hierarchy applies: **arm's-length comparable sales lead**
     (reconciled $/SF × subject SF), and **equalization corroborates** the comp conclusion. Equalization
     justifies going *below* the market (comp) value only when **top-percentile inequity** (e.g. building
     $/SF ≥ p90 vs peers) is the **explicit stated basis** — otherwise the comp-sales conclusion governs.
     Example: comps reconcile to $185/SF × 2,200 SF = **$407K** while the equalized building line implies
     ~$380K at p80. With a genuine p90+ building inequity you may request **$380K on the equalization
     basis**; absent that, conclude **$407K** on the sales basis. State the concluded value as **reconciled
     $/SF × subject SF**, naming the governing basis.
   - *Worked example (436 Mount Curve — STALE own sale, the SALES comparison governs):* the subject last
     sold for **$405,000 in 2002** — **~23 years** before the effective date, far outside the ~4-year
     horizon. That sale is **discarded** (it is not a floor and its raw delta vs current EMV is
     meaningless). The conclusion is set by **size-matched comparable sales**: the comp median runs
     **~$307/SF × subject SF ≈ $531K**, which governs. The 2002 sale appears, if at all, only as a note that
     the direction (EMV well above historical basis) is consistent — never as the value.
4. **QA before output:** correct owner of record; correct current-year baseline; specs match the record
   (corrections flagged as corrections); requested value matches the reconciliation; comp figures match
   the source data; dates correct.
5. **Include at least one chart.** Add a visual that makes the argument land at a glance — built as
   **inline SVG, no external libraries** (so it renders and prints anywhere). Good options: a building (or
   land) **$/SF bar chart** of the subject vs. the neighborhood comps with the subject highlighted and a
   median reference line; or a **sales adjusted-value bracket** showing each comp's adjusted value with the
   subject's own sale marked inside the range. Use the brand palette (navy `#0A2647`, gold `#d7b971`,
   orange `#e65100` for reference lines), label axes, and put the subject in gold.

## Output structure

Produce the packet narrative in this order:

1. **Summary** — subject, current EMV and effective date, requested value and the reduction, the
   one-paragraph thesis.
2. **Subject property** — county record (grade, condition, SF basis, lot, year), and actual condition as
   of the effective date with any corrections noted.
3. **Assessment history** — 3-year EMV table with YoY change.
4. **Points for discussion** — the specific CAMA / condition / land issues, each tied to evidence.
5. **Sales comparison** — comp table, adjustment grid, reconciliation.
6. **Equalization** — subject vs. neighborhood $/SF distribution, where applicable.
7. **Cost-to-cure / EMV cross-check** — where applicable.
8. **Concluded value** — the reconciled value, effective date, and the requested reduction.

Write plainly and factually, in the register of one appraiser talking to another. No filler, no
overstatement, no citing automated-estimate sources as evidence. Flag every assumption.

## Rendering — use the framework, don't hand-build HTML

The branded HTML packet is produced by the report framework in [`report/`](../report/) —
`generate_appeal_report(data)` renders every section from one data dict. The `$/SF` adjustment grid and
supported-value math live in `report/shared_components.render_adjustment_grid` (pass
`adjustment_grid_subject_sf` to switch it into $/SF mode). The equalization chart is a native scatter
(`building_emv_chart`). See [`scripts/render_sample.py`](../scripts/render_sample.py) for the complete data
contract worked end-to-end — it generates `examples/sample-appeal-packet.html`. Assemble the dict from your
analysis and call the generator; set `meta.brand` to the firm name. Do not re-implement the HTML by hand.

**Use the DERIVED rates, not authored numbers.** Build the `adjustment_schedule` and `adjustment_grid` from
the data, not by hand: pass the triage `sales_comparison_indicated.derived_adjustments` (the regression
coefficients) and the comp set to `analysis.adjustment_grid.build_adjustment_inputs(comps, subject, derived,
assess_date, condition_by_pid=...)`. It returns `adjustment_schedule` rows carrying each rate's n / R² /
t-stat / reliability and per-comp `adjustment_grid` percentages — so the packet shows a *supportable* time /
size / age / lot rate, and the `condition_pct` column carries the agent condition read from step 3b (same-
tier comps = 0; quantified comps from cost-to-cure). The grid rows include `size_pct` (total-value mode); when
you render in `$/SF` mode (`adjustment_grid_subject_sf` set) size is resolved by the reconciled $/SF and the
derived size coefficient stands as the cross-check on the flat-$/SF assumption. When
`derived_adjustments` is null (too few comps to regress), fall back to a qualitative grid and **say so**.

> **`derived_adjustments` are comp→subject DELTA rates only — never a standalone hedonic value.** Use each
> coefficient to adjust a *comp's* price toward the subject (`adjusted = comp_price + Σ coef × (subject −
> comp)`), then take the median/mean of the **adjusted comp prices**. Do **NOT** compute `intercept + Σ coef ×
> subject_feature` to get a subject value directly — `year_built` enters the regression on its raw absolute
> basis and the intercept is not standalone-interpretable, so that path yields nonsense (e.g. a negative
> multi-million-dollar "value"). The coefficients are dimensionally safe only as deltas. For a model-predicted
> subject value as a cross-check, use the **land-extraction indicated value** instead.
