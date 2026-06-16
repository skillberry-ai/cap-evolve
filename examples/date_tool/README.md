# date_tool — a from-scratch integration where **Bob** does everything

This example demonstrates the **full cap-evolve pipeline starting from nothing**, with
**IBM Bob** as the autonomous agent for *both* jobs:

1. **Integration (the intake phase):** Bob writes the 4-method adapter that wires the
   benchmark to cap-evolve — from the scaffolded stub — until `cap-evolve check` is green.
2. **Optimization:** Bob (as the optimizer) edits the capability under test until the
   reward improves, gated honestly on a held-out split.

The capability optimized here is a **tool** (`parse_date.py`, a `tools` capability):
normalize a messy date string to ISO `YYYY-MM-DD`. The runner is a deterministic
tool-applier (no LLM), so the whole loop runs in minutes with a clean signal — ideal
for showing the *mechanics* of the pipeline end-to-end.

## Result (real run, Bob optimizer)

| stage | val reward | note |
|------|-----------|------|
| baseline (seed `parse_date.py`) | **0.125** | seed only handles ISO → 1/8 tasks |
| `cand_0001` (Bob rewrote the tool) | **1.000** | **ACCEPTED** — Δ +0.875 over baseline |
| held-out **test** (sealed, scored once) | **1.000** | confirms the val win |

Git history (one commit per iteration, `store: git`):
```
ea34584 iter 1: ACCEPT candidate cand_0001 (val 1.000, Δ +0.875)
c208d39 seed: baseline candidate
```

## Who does what — SCRIPT vs BOB vs YOU

| step | done by | artifact |
|------|---------|----------|
| 1. scaffold `.capevolve/project/` | **SCRIPT** `intake/scripts/run.py` | `adapters/adapter.py` (stub), `capevolve.yaml`, `PROJECT.md` |
| 2. provide NEEDED inputs (dataset + seed capability) | **YOU** (the user) | `tasks.jsonl`, `seed_cap/parse_date.py` |
| 3. implement the 4-method adapter + fill `capevolve.yaml` | **BOB** (autonomous) | `adapter.bob.py` (here) |
| 4. hard gate | **SCRIPT** `cap-evolve check` | `{"ok": true, "stubs": [], "problems": []}` |
| 5. baseline eval on val | **SCRIPT** `baseline` phase | `baseline.json` (val 0.125) |
| 6. propose edit from val feedback | **BOB** (optimizer) | `sample_output/optimized/parse_date.py` |
| 7. re-eval, significance gate, accept/reject | **SCRIPT** `all-at-once` + core gate | `events.jsonl`, git commit |
| 8. sealed test once + report + dashboard | **SCRIPT** `finalize` + `report` | `report.md`, `dashboard.html` |

The honesty core (splits, sealed test, `Δ > k·SE` gate, pass^k) is **all script**, in
`core/cap_evolve` — Bob cannot touch it. Bob only writes the *adapter* (step 3) and the
*capability edits* (step 6).

## What Bob actually saw and wrote

The adapter's `score()` turns each failure into optimizer feedback. Bob's optimization
prompt (`INSTRUCTIONS.md`, built by the `all-at-once` phase) contained:
```
Current val reward: 0.125. Edit the capability files ... to raise it.
## Failing tasks (learn from their feedback):
- us_slash: Input: '06/16/2026' | Expected: '2026-06-16' | Got: '06/16/2026'
- long_mdy: Input: 'June 16, 2026' | Expected: '2026-06-16' | Got: 'June 16, 2026'
- ...
```
Bob then rewrote `parse_date.py` to handle US slash, DMY dash, slash-ISO, dotted, and
long/abbreviated month names — see `sample_output/optimized/parse_date.py`. All 8 tasks
pass → val 1.0, accepted, test 1.0.

## Run it yourself
```bash
REPO=/path/to/cap-evolve
R=/tmp/date_tool_run; rm -rf $R; mkdir -p $R; cd $R

# 1) SCRIPT — intake scaffolds the project from the template
python3 $REPO/skills/phases/intake/scripts/run.py --base .capevolve

# 2) YOU — drop in the NEEDED inputs (dataset + the seed capability to optimize)
cp $REPO/examples/date_tool/tasks.jsonl .
cp -R $REPO/examples/date_tool/seed_cap .

# 3) BOB — implement the adapter from the stub until `cap-evolve check` is green.
#    (hand Bob INSTRUCTIONS.md; it writes adapters/adapter.py — see adapter.bob.py here)
export CAPEVOLVE_CORE=$REPO/core PYTHONPATH=$REPO/core:$R/.capevolve/project/adapters
export CAPEVOLVE_DT_TASKS=$R/tasks.jsonl BOBSHELL_API_KEY=...   # bob --logout && bob --accept-license once
python3 $REPO/skills/optimizers/ibm-bob/scripts/run.py --workdir $R --prompt $R/INSTRUCTIONS.md

# 4) SCRIPT — the hard gate
python3 -m cap_evolve.cli check .capevolve/project        # -> ok: true

# 5-8) SCRIPT+BOB — baseline → Bob optimizes → gate → sealed test → report + dashboard
export CAPEVOLVE_SKILLS_DIR=$REPO/skills
python3 -m cap_evolve.cli run --spec .capevolve/project/capevolve.yaml --project .capevolve/project --run-ts dt
open .capevolve/run_dt/dashboard.html
```

Splits use `split_ids.json` = all 8 tasks in train/val/test (a deliberate no-holdout
fit; the report flags the test number as a fit metric — see `intake/inputs/INPUTS.md`).
