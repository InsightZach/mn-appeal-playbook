# Prompts

The collectors and triage script gather and score the data; the **judgment** — which comps are real,
how to adjust them, what to conclude, and whether to appeal at all — is driven by the prompts here. They
encode the appraisal discipline that separates a defensible packet from a form letter.

| Prompt | Role | Stage |
|--------|------|-------|
| [`methodology.md`](methodology.md) | The appraisal reference every other prompt cites | — |
| [`triage-judgment.md`](triage-judgment.md) | Turn the raw triage score into a defensible appeal / no-appeal call | After `scripts/triage.py` |
| [`appeal-packet.md`](appeal-packet.md) | Generate the multi-method appeal packet | When the verdict is "appeal" |
| [`no-appeal-findings.md`](no-appeal-findings.md) | Generate the honest no-angle deliverable | When the verdict is "no angle" |
| [`run-appeal-review.md`](run-appeal-review.md) | End-to-end orchestration tying data → judgment → packet to the human steps | The whole cycle |

## How to use them

These are model prompts. Feed the property's `collected_data.json` and `analysis.json`
(from [`../scripts`](../scripts)) to the triage-judgment prompt, then to the packet or no-appeal prompt.
The output is the narrative analysis; pair it with the data tables your collectors produced.

> **Scope note.** These prompts ship the *framework and discipline* — the methods, the doctrine, the
> guardrails — with example adjustment rates you calibrate to your own market. They are deliberately the
> operating method, not a turnkey black box; the deeper paired-sales calibration and the production
> tuning are part of running the program, not a file to copy.
