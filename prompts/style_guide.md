# Style Guide — Appeal Report Copy

Reports go to clients and to assessors. Both want to know what you did and what you found. Neither wants
to be sold to. This guide governs the copy in every packet and no-appeal finding the prompts generate.

## Banned phrases (or use sparingly)

- "comprehensive review" → "we looked at" / "we ran"
- "virtually identical" → "comparable", "similar", or just state the dollar gap
- "near-perfect match" → "similar"
- "These are exactly the features that justify..." → "All of these would be upward adjustments..."
- "closes the door" → "is hard to argue against"
- "fully supports" → "lines up with" or just compare the numbers
- "well-supported" → "supported", or list the specifics
- "essentially identical" / "essentially matching" → state the actual gap ("$200 off", "$5K off")
- "no defensible angle" → "no clear angle"
- "the strongest evidence the county would use" → "if we filed, the county would lead with"
- **"the county's own data confirms / shows / proves..."** (and "the county can't argue with its own
  numbers", "by the county's own figures", "the county's own data") → drop the gotcha framing and **state
  the finding plainly**: "the assessment records show the building at $244/SF, above the $198 neighborhood
  median." Naming the *source* once is fine ("at the county's assessed land value"); the rhetorical "their
  OWN data" device is not — it reads as preachy and annoys the assessor.
- **Never** use the word "comprehensive."

## Write as ADVOCACY, not a methodology essay (the cardinal rule)

The packet is an **argument to the assessor that THIS property's value is too high** — not a description of
how we computed it. The reader is a working appraiser who cares about the subject's evidence, not our
process.

- **Lead with the claim and the evidence:** "the market value is ~$X because [the subject's own sale / its
  condition / comparable sales / its assessed $/SF vs peers]." State the conclusion, then support it.
- **Never name our internal machinery.** Do **not** write "extraction method," "TARE Ch. 19," "the
  regression coefficient," "our model," "the tier screen," "building-residual $/SF as the governing
  indicator," etc. Those are *how we work*, not *why the assessment is wrong*. Translate every internal
  step into plain appraisal language the assessor already uses (e.g. say "setting aside each home's land at
  the county's own land value, the building works out to $X/SF" — not "extraction (TARE Ch. 19)").
- **Smell test:** if a sentence would only make sense to someone who has read our codebase or methodology
  files, cut or rewrite it. The assessor should read an argument about their property, start to finish,
  and never learn what tools we used.

## Tone

- Write like a colleague explaining what they checked, not a brochure.
- Lead with numbers, not adjectives.
- It's fine to say "we don't see an angle" plainly — that's more credible than padding.
- First-person plural ("we pulled the data...") is fine. Use contractions.

## Things to avoid

- **Don't cite an automated-estimate (Zestimate-style) figure as "independent validation."** It reads as
  lazy. Listing *data* (basement type, fireplace, flooring, condition photos) is fine as comp evidence;
  the automated value estimate is not.
- **Don't put "for informational purposes" disclaimers in the body.** A footer line is fine.
- **Don't oversell.** Marginal case → say so. No angle → say so plainly.

## Repairs vs. upgrades

New roof/windows on a property are necessary repairs, not value-adding upgrades. Frame as:

> These were necessary repairs to stop active water damage and prevent further deterioration — not
> upgrades. They prevent loss of value; they do not create it.

Not as: "The roof and windows have been replaced, adding significant value."

## Single defensible values, no ranges

In adjustment grids, cost-to-cure exhibits, and conclusions, pick one number per line, not a range.

- **Bad:** "Basement rec area: $20,000 – $30,000"  →  **Good:** "Basement rec area rebuild: $25,000"
- **Bad:** "Concluded value: $540,000 – $600,000"  →  **Good:** "Concluded value: $570,000"

Ranges invite the appraiser to pick the low end of your costs and the high end of your value — the wrong
direction. A single defensible number invites discussion of the specific scope. The supporting paragraph
can mention sensitivity ("the band runs $555K–$625K depending on weighting"); the headline is one value.

## Calibration honesty

If you backed into a number to make two methods agree (e.g., tuned the cost-to-cure so the EMV cross-check
lands on the sales conclusion), say so. Methods can "converge" or "reconcile" — don't claim "three
independent methods all confirm" when two were calibrated. Flag suspiciously tidy agreement upfront;
better than having the appraiser catch it.

## Reconciliation honesty (the divergence case)

When the approaches disagree — e.g., the sales-comparison grid indicates one value and the subject's own
recent arm's-length sale indicates another — **do not hide it and do not split the difference
mechanically.** State both, say which is more reliable and why, and conclude on the stronger evidence. A
property's own recent arm's-length sale outweighs an adjusted set of inferior comps; never conclude a
value *below* a recent arm's-length sale of the subject. The reader should see the judgment, not a number
that appeared from nowhere. (This is the reasoning the agent supplies — see
[`run-appeal-review.md`](run-appeal-review.md).)

## Approach-closer pattern

Each valuation approach ends with a navy/gold "Indicated Value" card showing that approach's standalone
conclusion before the final reconciliation:

```
Indicated Value — Sales Comparison Approach        $409,000
```

This lets the reader (and the appraiser) see what each approach says on its own, separate from the final
concluded value.
