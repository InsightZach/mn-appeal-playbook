# Tests

Contract tests for the deterministic **script layer** — the parts that compute
signals from county data. They pin the behaviour, not the prose; the reasoning
(prompts/) is exercised by running the playbook, not by unit tests.

```bash
uv run pytest          # all
uv run pytest -q       # quiet
```

## What each file pins

| File | Contract |
|------|----------|
| `test_killer_comp.py` | A comp `supports_appeal` **only** with real over-assessment signal — it sold below its *own* EMV, or its $/SF implies a materially lower subject value. A cheaper-tier comp the county assessed correctly is `discount`, never `supports_appeal` (the regression the loop fixed). `kills_appeal` / `confirms_fair` paths; new fields (`comp_own_emv_ratio`, `implied_subject_value`). |
| `test_triage.py` | End-to-end through `triage()`: stale own sale is *corroborating only* and does not flip the verdict; a recent own sale governs; a 2-3 yr sale is time-trended; single-model convergence is `single_model` and inert; the `<0.80×` distressed screen flags outliers; equalization carries the p80-band fields; a `supports_appeal` killer flips the verdict; the documented `analysis.json` key set. |
| `test_sales_regression.py` | Regression math + the `central_label` directional-screen tag on a single (or trivially-tight) model. |
| `test_equalization.py` | Land/building $/SF trends, two-cluster split, and the degenerate-lot guard (identical lot sizes must not crash). |

## Why these and not the renderers

The render scripts are fixtures (a human/agent authors the data dict). The
*logic* that turns county data into a verdict is what can silently drift when the
prompts or analysis modules change — so that is what the suite guards. Run the
suite after any change to `analysis/` or `scripts/triage.py`, and as the
regression gate after an agent improvement loop.
