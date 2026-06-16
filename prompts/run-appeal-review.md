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
2. **Triage** — `python -m scripts.triage <dir>/collected_data.json --baseline-emv <listed value>`
   Scores the over-assessment signals and emits a verdict.
3. **Judgment** — apply [`triage-judgment.md`](triage-judgment.md) to the collected data + triage output.
   Confirm the verdict, set the recommended ask, record caveats.
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
