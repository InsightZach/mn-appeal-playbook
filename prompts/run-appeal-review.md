# Prompt — Run Appeal Review (Orchestration)

The end-to-end workflow for taking one property from raw data to a filed, negotiated appeal. It ties the
automated steps (collect, triage, generate) to the human steps (submit, inspect, negotiate, escalate)
that actually win reductions. The automated steps produce the evidence; the human steps produce the
result.

---

## Inputs

- A property: address or PID, and its county / assessing jurisdiction.
- The owner's signed authorization on file (see [Submission](../docs/06-submission.md)).

## The sequence

### Automated — produce the evidence

1. **Collect** — `python -m scripts.collect "<address-or-pid>" --county <ramsey|hennepin> --output <dir>/`
   Gathers subject, 3-year assessments, neighborhood comps, recent sales. Verify the resolved PID matches.
   **When the resolved address differs from your query** (collect prints a `WARNING:` with the resolved
   address, owner_name, and plat — e.g. an `Ave` → `St` street-type correction), **spot-check
   owner_name / plat against expectation before proceeding**; a silent street-type swap can resolve to the
   wrong parcel.
2. **Triage** — `python -m scripts.triage <dir>/collected_data.json [--baseline-emv <listed value>]`
   Scores the over-assessment signals and emits a verdict. **`--baseline-emv` is only for reconciling
   against a lagging source spreadsheet** (a listed value that may match a prior assessment year). For an
   **address-first lookup there is no source value — omit it** and rely on the assessments pulled by
   collect; `baseline_comparison: null` is the expected output in that case.
3. **Judgment** — apply [`triage-judgment.md`](triage-judgment.md) to the collected data + triage output.
   Confirm the verdict, set the recommended ask, record caveats.
   - **Worth-it threshold (after the ask is set).** `analysis.json` carries `tax_economics.etr`,
     `savings_per_10k_reduction`, and a pre-sized `tax_economics.worth_it_gate`
     (`min_reduction_to_clear_450_floor`, `flag`); its `illustrative_savings` is illustrative only. Once the
     judgment sets a concluded ask, compute the actual economic gate from
     [`docs/04-triage-decision.md`](../docs/04-triage-decision.md)
     / [`docs/09-reduction-math.md`](../docs/09-reduction-math.md): `likely reduction × ETR × contingency %`
     (× years held). **Use the house-standard defaults (docs/04): 30% contingency, ≈ $1,500 fully-loaded
     cost to pursue, ~$450 year-1-savings floor — `likely reduction × ETR × 30% ≥ ~$450` on a one-year
     hold.** A high EMV does not by itself clear the gate: a modest equalization-only reduction on a
     high-value parcel can still fail it. If it does not clear the cost to pursue, fall back to no-appeal
     even on a genuine angle.
     - **Default hold = 1 year.** Assume a **one-year hold** for the gate unless the resolution route is a
       **stipulation / Tax Court**, in which case assume **2 years**. **Never assume a multi-year hold for an
       open-book concession** ([`docs/09-reduction-math.md`](../docs/09-reduction-math.md) lines 50–51: an
       open-book concession may not hold into the following year). The hold assumption can flip the verdict
       (e.g. ~$216/yr fails on a 1-year hold but ~$647 clears stacked over 3 years), so it must be stated, not
       improvised.
     - **The gate governs the verdict — at this (judgment) step, not in the script.** A `borderline` or
       `appeal_angle` verdict from [`triage-judgment.md`](triage-judgment.md) is **PROVISIONAL until this
       gate clears.** A **sub-floor** economic result **downgrades any borderline to `no_appeal` regardless
       of the angle's merit**, and softens a marginal `appeal_angle`. The triage script surfaces an
       **informational** `tax_economics.worth_it_gate.flag` (`pass` / `borderline` / `fail` /
       `not_yet_sized`) to inform this call, but it does **not** change the script verdict — the worth-it
       decision is made here, where the concluded ask and the real engagement economics are known. Run the
       gate **before** committing to a packet, not after.
3b. **Enrich (agent-driven) — close the county-data gaps with the internet.** The collectors pull
   **county API data only**, which (especially for Ramsey) carries **no condition/grade and no
   good-for-study flag**. That is a property of the *script*, not a dead end — an **agent** fills these
   gaps with the tools we already have. Do this whenever the argument depends on it; do **not** shortcut to
   "the county data doesn't have it."
   - **Condition / CAMA detail** — when a condition, grade, or cost-to-cure argument is in play, run the
     [listing-enrichment step](../collectors/listing_enrichment.md): pull condition, photos, and structure
     from the **owner's listing first**, then Zillow / Redfin / Realtor via the browser, or a Beacon/CAMA
     card. (We did exactly this on 884 Ashland — the Zillow lookup showed a renovated interior and changed
     the conclusion.) A condition argument **requires** this evidence; never assert condition from nothing.
   - **Arm's-length / good-for-study verification** — the triage script's `< 0.80× own-EMV` screen is a
     cheap first pass, not the answer. For any **load-bearing comp** (the ones that drive the conclusion)
     and for the **subject's own sale**, verify good-for-study status (see
     [Data Sources](../docs/03-data-sources.md#ecrv-verification)). **Carve-out for the subject's OWN
     sale:** eCRV/good-for-study verification of the subject's own sale is load-bearing **only when the own
     sale is BELOW EMV and would set the ask** — there, an excluded/distressed sale must be caught before
     it pulls the value down. **When the subject's own sale is at or above EMV and supports no-appeal, note
     its existence and SKIP the eCRV step**: excluding a distressed/atypical sale would only make it a *low*
     outlier, which can only strengthen no-appeal — it cannot flip the verdict, so the slow browser lookup
     is provably irrelevant. For **Ramsey**, the authoritative answer
     is the **eCRV State-Study "Good for study"** field (`mndor.state.mn.us/ecrv_search` → Parcel ID →
     Completed → open the eCRV): **No** plus a reject reason (e.g. `09a – Estate Sale`) means excluded — and
     note the *County* Study field can read Yes while the *State* Study reads No; the **State** study is the
     one that governs. For a quick inline read, the **Ramsey Beacon** sale-qualification code (same pull as
     structure — e.g. `02-RELATIVE SALE OR RELATED BUSINESS`) flags the same exclusions. For **Hennepin**,
     the API `sale_code` already carries it. Drop any comp shown as excluded, and **disclose the screen you
     applied** in the packet.
     - **Degraded-mode fallback (Ramsey, drafting from JSON alone).** Ramsey has no good-for-study flag in
       `collected_data.json`, so a per-comp eCRV browser pull is required for load-bearing comps. If that pull
       is **not** performed (e.g. you are drafting from `collected_data.json` alone), state that the comps
       passed **only** the triage `< 0.80× own-EMV` distressed screen, **disclose that weaker screen in the
       packet as the applied qualification check**, and **flag eCRV verification as a pre-submission to-do.**
       This is acceptable for triage / packet drafting but **MUST be closed before submission** — do not
       treat the unverified comps as fully qualified.

4. **Generate** — if the verdict is an angle, run [`appeal-packet.md`](appeal-packet.md); otherwise run
   [`no-appeal-findings.md`](no-appeal-findings.md). QA the output.

### Human — produce the result

These steps are where appeals are actually won. They are not optional, and they cannot be automated away.

5. **Route by jurisdiction.** Confirm the assessing authority and appeal format for the parcel
   ([Jurisdiction Map](../docs/02-jurisdiction-map.md)): county vs. self-assessing city, Local Board vs.
   Open Book, inspection or not.
6. **Submit through engagement, in the open-book window.** Deliver the packet to the reviewing appraiser
   and open the conversation — do not mail it to the board and wait
   ([Submission](../docs/06-submission.md)).
7. **Schedule and staff the inspection** where the jurisdiction allows one. Coordinate appraiser + owner,
   be present or immediately reachable, and **own the appraiser's follow-up call**
   ([Inspections](../docs/07-inspections.md)).
8. **Negotiate the findings.** Work the CAMA / condition / land corrections to a revised value
   ([Negotiation & Escalation](../docs/08-negotiation-escalation.md)).
9. **Decide on escalation.** Accept an adequate reduction; escalate to the County Board if sustained or
   insufficient; preserve the Tax Court backstop (petition by April 30 of the payable year) for strong
   cases that do not resolve.
10. **Record the outcome** — the post-appeal EMV, the procedural level it resolved at, the estimated tax
    savings ([Reduction Math](../docs/09-reduction-math.md)), and any petition filed. This is both the
    client deliverable and next year's leverage map.

## The point

The model produces a defensible packet in minutes. The reduction comes from steps 5–10 — routing the
parcel correctly, engaging the appraiser in the right window, getting onto the property, and following
through. A program that automates 1–4 but skips 5–10 produces packets, not reductions.
