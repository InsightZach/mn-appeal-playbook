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
   address, owner_name, and plat): if the difference is a pure street-type correction (`Ave` → `St`),
   spot-check owner_name / plat against expectation before proceeding. **But when the resolved directional
   (N/S/E/W) or street NAME differs from the query — as opposed to a pure street-type correction — STOP.**
   Re-query the literal queried address (e.g. `SiteAddress LIKE "%660 LEXINGTON PKWY S%"`) and confirm a
   parcel with that exact directional/name exists. If a distinct parcel matches the literal query, abort
   and flag a resolver bug — do not proceed on the resolved parcel. The owner/plat spot-check is
   ineffective for an address-first lookup because it surfaces the RESOLVED (possibly wrong) parcel with
   no independent baseline to compare against. A directional swap lands on a real, different property —
   far more dangerous than a trivial `Ave` → `St` correction.
2. **Triage** — `python -m scripts.triage <dir>/collected_data.json [--baseline-emv <listed value>]`
   Scores the over-assessment signals and emits a verdict. **`--baseline-emv` is only for reconciling
   against a lagging source spreadsheet** (a listed value that may match a prior assessment year). For an
   **address-first lookup there is no source value — omit it** and rely on the assessments pulled by
   collect; `baseline_comparison: null` is the expected output in that case.
3. **Judgment** — apply [`triage-judgment.md`](triage-judgment.md) to the collected data + triage output.
   Confirm the verdict, set the recommended ask, record caveats.
   - **Worth-it threshold (after the ask is set).** `analysis.json` carries `tax_economics.etr`,
     `savings_per_10k_reduction`, and a pre-sized `tax_economics.worth_it_gate`
     (`min_reduction_to_clear_floor`, `flag`, `illustrative_reduction_source`); its `illustrative_savings` is
     illustrative only. Once the judgment sets a concluded ask, compute the actual economic gate from
     [`docs/04-triage-decision.md`](../docs/04-triage-decision.md)
     / [`docs/09-reduction-math.md`](../docs/09-reduction-math.md): `likely reduction × ETR × contingency %`
     (× years held). **Use the illustrative placeholder defaults (docs/04 — set the real numbers per
     engagement): ~30% contingency, ≈ $1,500 fully-loaded cost to pursue, ~$450 year-1-savings floor —
     `likely reduction × ETR × 30% ≥ ~$450` on a one-year hold.** A high EMV does not by itself clear the
     gate: a modest equalization-only reduction on a high-value parcel can still fail it. If it does not
     clear the cost to pursue, fall back to no-appeal
     even on a genuine angle.
     - **Run the gate against the concluded ask from the GOVERNING approach** (the appeal-packet
       reconciliation), not against the largest or smallest available figure. If multiple candidate asks
       exist (e.g. a sales conclusion and a narrower equalization p80 floor), test the gate at each and
       adopt the ask that is BOTH evidence-supported AND clears the floor — when the governing approach is
       sales, size the gate off the sales conclusion, not off the narrower equalization figure the script
       may headline.
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
     it pulls the value down. **For a sale in the 2.0–3.5yr time-trend band, apply the BELOW/ABOVE-EMV test
     to the TIME-TRENDED figure (`subject_own_sale.trended_delta_pct`), not the raw price.** A
     raw-below-EMV sale that trends to at/above EMV supports no-appeal — skip eCRV unless that trended sale
     is the sole basis for no-appeal and looks atypical. **When the subject's own sale is at or above EMV and supports no-appeal, note
     its existence and SKIP the eCRV step** — *with one exception below*: excluding a distressed/atypical
     sale would normally only make it a *low* outlier, which can only strengthen no-appeal, so the slow
     browser lookup is usually irrelevant. **Exception — an ABOVE-EMV own sale that is the SOLE basis for
     no-appeal AND looks atypical.** A non-arm's-length above-EMV sale (related-party inflated, a
     financing concession, a sale priced well above the comp-implied value, e.g. > ~1.1× the
     size+vintage-matched `sales_comparison_indicated` median) would FALSELY support no-appeal — and skipping
     the check waves it through. So skip eCRV only when the above-EMV own sale is **at/above EMV AND not an
     obvious high outlier vs the comps**; if it is the only thing standing between the parcel and an angle
     and it looks inflated, **run the eCRV/Beacon qualification check before shipping no-appeal.** **A stale own sale (>4yr horizon) never sets the ask, so its eCRV/good-for-study
     verification is never load-bearing regardless of whether it sits below EMV — skip it.**
     **Price-missing own sale that PRE-dates the effective date:** a price-missing own sale dated before the
     effective date is potentially GOVERNING and must be price-recovered (eCRV / listing) before a
     `no_appeal` finding ships — not merely flagged as a pre-submission to-do. If the price is unrecoverable
     from available sources, state that the no-appeal conclusion is CONTINGENT on the recovered sale not
     landing materially below EMV, and flag it. For **Ramsey**, the authoritative answer
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
   - **Carry the angle through a gate-failed no-appeal.** When Step 3 downgrades a genuine angle to
     `no_appeal` because the worth-it gate failed (not because the assessment is fair), route to
     [`no-appeal-findings.md`](no-appeal-findings.md) **scenario 3 (angle present but sub-floor)** and carry
     the **indicated reduction** and **governing approach** into the finding — do not collapse it to a bare
     "no_appeal" that reads as "fairly assessed." The two no-appeal narratives are materially different
     deliverables.
   - **Cross-check the verdict against the gate's reduction source.** A non-zero
     `worth_it_gate.illustrative_reduction` sourced from `sales_comparison_indicated_gap_vs_emv` means the
     script's own gate machinery already saw a below-EMV sales angle — if the headline `verdict` is
     `no_angle`/`borderline`, that is a flag the verdict may have **under-called** the angle. Reconcile the
     two before accepting the headline (this is the same field rule 0 in [`triage-judgment.md`](triage-judgment.md)
     enforces).
   - **When reconciliation concludes at or above EMV, the gate is N/A.** There is no reduction to size;
     record `no_angle` directly. `worth_it_gate.flag = "n/a — no supportable reduction"` (or
     `not_yet_sized` on an older run) is **terminal**, not an unfinished sizing step.

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
