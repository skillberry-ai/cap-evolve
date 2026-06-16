# tau2-airline experiment — Bob optimizer, gpt-oss-120b runner, full pipeline

The headline experiment: optimize the airline agent's **policy (system prompt)** *and*
**tools** with **IBM Bob** as the optimizer, against tau2-bench airline where the agent
*and* user simulator are both **gpt-oss-120b** (IBM RITS).

## Exact configuration (`acapo.yaml`)
```yaml
capabilities: [system-prompt, tools]   # policy.md (system prompt) + tools.py
capability_path: seed_caps             # seed_caps/{policy/policy.md, tools/tools.py}
optimizer_skill: ibm-bob               # Bob proposes every edit
optimizer_model: ""                    # Bob's default model
algorithm_skill: all-at-once
dataset_source: adapter
split_ids_file: split_ids.json         # all 50 tasks in train == val == test
num_trials: 5                          # 5 tau2 rollouts/task/eval (averages gpt-oss noise)
gate_mode: significant                 # accept only if Δ > k·SE on val
gate_k_se: 1.0
max_iterations: 20
store: git                             # one commit per iteration
```
- **All 50 tasks as train/val/test** (no holdout). agent-capo logs a `splits_warning`:
  *"test overlaps train/val … report it as a fit metric."* This is the requested fit
  setup, made explicit rather than silent.
- **Agent + user simulator: gpt-oss-120b** via RITS (`tau2_runtime.py`), tau2
  `max_concurrency = 7` (`TAU2_MAX_CONCURRENCY=7`).
- **Tools optimization covers every option in the `tools` skill**: Bob edits
  `tools.py`, so it can change tool **docstrings/descriptions**, **in-description
  examples**, **parameter schemas**, **implementation code**, **remove** a tool, and
  **add new tools that compose existing ones**. **Policy/system-prompt** optimization =
  Bob edits `policy/policy.md` (tau2 injects it as the agent's system prompt).

## Who does what — SCRIPT vs BOB vs YOU

| step | done by | what |
|------|---------|------|
| scaffold project | **SCRIPT** `intake/scripts/run.py` | `.agentcapo/project/` |
| tau2 adapter + runtime | **YOU / repo** | `adapter.py` (4 methods + `run_batch`) and `tau2_runtime.py` (RITS routing, tau2 concurrent runner, empty-turn retry). tau2 is complex infrastructure provided by the repo — *not* written by Bob (contrast the `date_tool` example, where Bob writes the adapter). |
| seed capabilities | **YOU / repo** | `seed_caps/policy/policy.md`, `seed_caps/tools/tools.py` |
| `acapo check` (hard gate) | **SCRIPT** | imports the adapter, 1 task × 2 trials, asserts determinism |
| baseline eval (val, 50×5) | **SCRIPT** `baseline` phase | `baseline.json` |
| **propose policy+tools edits** | **BOB** (optimizer) | edits `policy.md` + `tools.py` in each candidate dir, from val feedback (tau2 reward + missed required actions + transcript) |
| re-eval, significance gate, accept/reject | **SCRIPT** `all-at-once` + core gate | `events.jsonl`, git commit/iteration |
| sealed test + report + dashboard | **SCRIPT** `finalize` + `report` | `report.md`, `dashboard.html` |

Honesty lives entirely in `core/agent_capo` (sealed test, val-only gate, pass^k,
bootstrap CI) — Bob never touches it.

## Phases that run (the sequence `acapo run` drives)
```
intake (scaffold)  →  acapo check (gate)  →  baseline (val 50×5)
   →  all-at-once × 20  [ Bob edits policy+tools → eval val 50×5 → gate ]
   →  finalize (test 50×5, scored once)  →  report (report.md + dashboard.html)
```

## What to look for in the dashboard (`run_bobexp/dashboard.html`)
- **Score over iterations** + running best (val reward per candidate).
- **Accept / reject timeline** (green = gate-accepted edit).
- **Per-task reward heatmap** (which of the 50 airline tasks each edit fixed/broke).
- **Cost & latency** panel: RUNNER tokens/seconds (the 50×5 gpt-oss-120b conversations
  per eval) and OPTIMIZER seconds (each Bob call), plus total time and eval count.

## Scale / cost (why this is a long run)
50 tasks × 5 trials = **250 multi-turn tau2 conversations per evaluation**. With
baseline + 20 candidates + sealed test = 22 evals → **≈ 5,500 conversations** (agent +
user, both gpt-oss-120b) plus **20 Bob optimizer calls**. At `max_concurrency 7` this is
on the order of **~20 hours** of wall-clock. tau2 (`system-prompt`+`tools`) is genuinely
high-leverage — the policy and tools strongly shape the airline agent's behavior — so
unlike a low-leverage skills-bench task, the optimizer has real signal to climb here.

## How it was launched
```bash
REPO=/path/to/agent-capo
export AGENT_CAPO_CORE=$REPO/core PYTHONPATH=$REPO/core:$R/.agentcapo/project/adapters
export ACAPO_SKILLS_DIR=$REPO/skills ACAPO_TAU2_DATA=$REPO/examples/tau2_airline/data
export TAU2_MAX_CONCURRENCY=7 RITS_API_KEY=... BOBSHELL_API_KEY=...
python3 -m agent_capo.cli run --spec $P/acapo.yaml --project $P --run-ts bobexp
```
Results (baseline → best val → sealed test, Bob's accepted edits, dashboard) are
appended to this file as the run completes.
