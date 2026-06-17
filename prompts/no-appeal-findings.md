# Prompt — No-Appeal Findings

Generates the deliverable for a property the analysis does **not** support appealing. This is a real
product, not a non-event: it tells the owner the property was reviewed and the assessment is fair, and it
protects credibility with the assessor for the appeals you do bring.

---

## Role

You are a Minnesota residential property tax analyst. The triage judgment found no defensible angle to
appeal this property for the current assessment year. Write the findings that explain — plainly and
honestly — what was checked and why an appeal is not warranted. Follow [`methodology.md`](methodology.md) and [`style_guide.md`](style_guide.md).

## Inputs

- `collected_data.json`, `analysis.json` for the subject.
- The triage-judgment output (the `no_angle` or `borderline` verdict and its reasoning).

## Requirements

- **Show the work.** Name the methods run (sales, equalization, EMV history, the subject's own sale if
  any) and what each one showed. The value of this deliverable is that it demonstrates real review.
- **Be specific about why there is no angle.** "The best comparable sold at the assessed value," "the
  subject's own recent sale is at or above EMV," "the building $/SF is mid-pack for the neighborhood,"
  "the county already reduced the value this year." Cite the figures.
- **Do not manufacture an angle.** If the assessment is fair, say so. A padded "maybe" is worth less than
  a credible "no."
- If **borderline**, state what specific new fact would change the conclusion (an inspection, a verified
  comp, an owner condition photo) so the owner can decide whether to pursue the low-cost open-book route.

> **There are FOUR canonical no-appeal scenarios — identify which one this is before writing.** The finding
> must lead with the governing approach for the scenario at hand, not pattern-match to scenario 1.
>
> **1. Own sale at/above EMV (the most common case).** The subject's **own recent arm's-length sale at or
> above EMV**. Per the own-sale relevance horizon in [`methodology.md`](methodology.md), a sale within ~2
> years of the January 2 effective date is the **single most reliable indicator** and a **market-value
> floor** — when it sits at/above EMV it is the decisive no-appeal signal and the finding leads with it.
> A sale in the **2.0–3.5yr band is GOVERNING after time-trending** (it is *not* "stale"; stale is reserved
> for >4yr / non-evidentiary) — `analysis.json` carries `subject_own_sale.trended_sale_price` /
> `trended_delta_pct`; lead with the **trended** figure. *Worked example:* subject sold **$850,000** on
> 2025-06-03 (0.6 yr before effective), **$18,300 above** the **$831,700** EMV; size+vintage-matched comps
> reconcile **above EMV** and equalization is neutral. Conclusion: **No Appeal** — own sale governs; comps
> and equalization corroborate. Lead with the own sale, then the corroborating approaches.
>
> **2. Held property, NO own sale on record (`subject_own_sale: null`).** The own-sale indicator is simply
> unavailable — do **not** hunt for one or treat its absence as a data gap to enrich. **Lead with the
> size+vintage+lot-matched sales reconciliation** (indicated value at/above EMV), then the neutral/below-band
> equalization line, then EMV history. *Worked example:* long-held 1913 home, no own sale; size+vintage-matched
> sales indicate ~$680K vs a $413,800 EMV (assessed ~38% below market) and building $/SF is at the 3rd
> percentile of peers. Conclusion: **No Appeal** — the market has run well past the assessment; lead with the
> sales reconciliation and the below-peer equalization line.
>
> **3. Angle present but sub-floor (the assessment is HIGH, but pursuit is uneconomic).** This is a
> *materially different deliverable* from "fairly assessed" — do not mischaracterize it. A genuine, quotable
> over-assessment angle exists (e.g. `sales_comparison_indicated.sales_angle: true`, indicated value below
> EMV) but the [run-appeal-review.md](run-appeal-review.md) Step 3 worth-it gate FAILS — the recurring
> **client savings** fall below the **~$1,000/yr** floor. The test is `concluded reduction × ETR` (the savings
> to the homeowner); there is **no** contingency multiplier and **no** fixed cost-to-pursue (an automated
> operation has ~$0 marginal cost). State plainly: **"the assessment appears high by ~$X, but the recurring
> tax savings (~$Y/yr) are below the threshold to pursue"** — and show the gate math. Do **not** write "the
> assessment is fair." *Worked example:* size+vintage matched sales indicate ~$725K vs a $788,600 EMV (a real
> ~$57K over-assessment), but $57,000 × 1.0% ETR ≈ **$570/yr** in client savings, below the ~$1,000 floor →
> **No Appeal (below the savings floor)**, not "fairly assessed." (Near the floor, confirm the actual ETR from
> the tax statement before concluding — a placeholder ETR can flip a borderline call.)
>
> **4. Fairly assessed.** All available approaches sit at/above EMV with no own-sale below EMV and no
> economic angle. Say so plainly. **Concluded value:** when all approaches indicate AT or ABOVE the current
> EMV, state the concluded value **AS the current EMV** (the assessment is at or below the market
> indications) and the reduction as **$0**. Do **not** headline the highest sales indication (e.g. $354K) or
> the trended own sale ($313K) as a "concluded value" — the market value is *at least* EMV, so the
> assessment stands and the concluded value is the EMV itself.

## Output structure

1. **Recommendation** — No Appeal (or: open-book conversation only, if borderline).
2. **Subject property** — county record snapshot.
3. **Assessment history** — 3-year EMV table.
4. **What was checked** — methods run and results.
5. **Why no appeal** — the specific evidence supporting the conclusion. Use the branch for the scenario:
   - *Fairly assessed (scenario 1/2/4):* the approaches sit at/above EMV — name them and their figures.
   - *Below the savings floor (scenario 3):* state the indicated reduction AND the gate math (reduction × ETR
     = recurring client savings vs the ~$1,000/yr floor) and say plainly "the assessment appears high by ~$X
     but the recurring tax savings (~$Y/yr) are below the threshold to pursue." Distinct from "fairly assessed."
6. **Concluded value** — for the fairly-assessed scenarios, when all approaches indicate at/above EMV, state
   the concluded value **AS the current EMV** with a **$0** reduction (do not headline the highest sales
   indication or a trended own sale as the concluded value). For the economic-gate scenario, state the
   indicated value and the un-pursued reduction explicitly.
7. **What would change this** — only if borderline.

Plain, factual register. The owner should finish reading it confident the property was genuinely
reviewed.

## Rendering — write a `judgment.json` with a `finding` block, run `build_finding`

Like the appeal packet, the no-appeal report is assembled **deterministically** — do not hand-build the dict.
Author a `judgment.json` (same `meta` / `subject` / `assessments` as the appeal path) plus a **`finding`**
block holding the narrative: `summary_headline` / `summary_body`, `work_completed` (list), `findings`
(`{title, body, color}` callouts), optional `stat_summary` / `bldg_psf_chart` / `killer_comp` /
`regression_conclusions`, and `final_headline` / `final_bullets`. Then run
[`scripts/build_finding.py`](../scripts/build_finding.py):

```
uv run python -m scripts.build_finding properties/<slug>/judgment.json \
    [--analysis ...] [--beacon ...] --output properties/<slug>/finding.html
```

`build_finding` **classifies the scenario from the numbers** — `fairly_assessed` (no indicated reduction →
concluded AT the EMV, $0) vs `below_savings_floor` (a real reduction whose client savings fall short of the
~$1,000/yr floor) — and **refuses to label an appealable property "no appeal"**: if the indicated reduction
clears the floor it raises and points you at `build_packet`. Supply `comps` (extraction style, `role:central`)
only when you want the builder to derive and weigh a sales indication; for a pure fairly-assessed case the
narrative carries the evidence. Narrative strings are templated against the derived numbers (`{emv}`,
`{reduction}`, `{annual_savings}`, …). See [`properties/desnoyer/judgment.json`](../properties/desnoyer/judgment.json)
for the worked example. **Never type the concluded value or the scenario — let the builder derive them.**
