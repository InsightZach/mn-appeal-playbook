# AGENTS.md

Operating instructions for AI agents working in this repo live in **[`CLAUDE.md`](CLAUDE.md)** — read it
first. (`AGENTS.md` is the cross-tool convention; `CLAUDE.md` is the canonical content, identical in intent.)

TL;DR: self-contained Python toolkit (no external DB/service/credentials). Pipeline is
`collect → triage → parse_beacon → judgment.json → build_packet`; scripts are deterministic and never
conclude a value, the agent supplies a small `judgment.json` and `build_packet` derives the conclusion.
Start from [`prompts/run-appeal-review.md`](prompts/run-appeal-review.md). Run everything with `uv run`.
