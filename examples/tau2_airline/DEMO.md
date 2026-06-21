# Demo — onboard tau2-bench airline as a new benchmark and optimize it

This demo shows cap-evolve taking a **brand-new benchmark** (tau2-bench) from a
single **prompt** to an honest, optimized result — onboarding it through intake
(which installs the benchmark and does the full integration), wiring IBM RITS,
building the adapter, gating on `cap-evolve check`, then running the full
baseline → algorithm → significance-gate → sealed-test → report loop with a
**live dashboard**.

## What a user does (two commands)

```bash
# 0. clone the repo, put RITS creds in the repo-root .env:
#    RITS_API_KEY=...   RITS_API_URL=...
# (and be logged into Claude Code, or export ANTHROPIC_API_KEY, for the optimizer)

bash examples/tau2_airline/setup.sh    # intake onboarding: install cap-evolve + clone/install tau2-bench
                                       # + scaffold project + wire the adapter + cap-evolve check (hard gate)
bash examples/tau2_airline/run.sh      # full run: 10 iters · 50 tasks · 10 trials · concurrency 125 + live dashboard
```

`setup.sh` is the executable transcript of the **intake / implement-and-check**
phase for this benchmark (see [`PROMPT.md`](PROMPT.md) for the inputs a coding
agent is given). It installs tau2-bench *as part of onboarding* — nothing is
assumed to pre-exist.

## The run (what the cast shows)

1. **The prompt** ([`PROMPT.md`](PROMPT.md)) — the inputs: capability `[system-prompt, tools]`,
   benchmark tau2-bench airline (git URL + `pip install -e`), runner `openai/gpt-oss-120b`
   via RITS (agent **and** user simulator), scorer = tau2 reward, optimizer
   `claude-code @ claude-opus-4-6`, hill-climb, 50 tasks no-holdout, 10 trials,
   `$40`/iter (`--max-budget-usd`) / `$400` total.
2. **Intake onboarding (the full integration)** — clone + `pip install -e ../tau2-bench`
   (commit recorded in [`run_full/TAU2_COMMIT.txt`](run_full/TAU2_COMMIT.txt)), scaffold
   `.capevolve/project`, then wire the whole benchmark integration: the adapter
   (`tasks` + `run_batch` → tau2's runner + the batched `run_trials` fast path +
   `trajectories()` returning tau2's native traces + `score()` reading `reward_info`),
   the RITS shim, the editable seed (`seed_capability/` = `policy/` + `tools/` +
   `reference/data_model.py`), `capability_sources` (the data model copied to the
   optimizer), and a **capability-scoped** `optimizer/INSTRUCTIONS.md`. Then
   `cap-evolve check` → `{"ok": true}` — the hard gate that must pass before any spend.
3. **Cost preview** — `cap-evolve estimate` prints call counts (`val × trials × iters`)
   and a calibrated `$` range before spending.
4. **Optimization** — baseline on val → each iteration: diagnose val traces into
   failure clusters → the `claude-opus-4-6` optimizer (given the current best step's
   full trajectories, the selected capability skills, the per-task impact of prior
   edits + the passing set to protect, and the STATE/MEMORY handover) edits the airline
   **policy AND tools** — rewriting/adding rules and writing **code-bearing tools**
   (validation / loop / composite WRITE tools, swapped in for the raw primitives) —
   under a per-iteration `--max-budget-usd 40` cap → re-evaluate ALL 10 trials in one
   batched `run_trials` pass on val → **paired significance gate** (val-only) accepts
   or rejects → every iteration is a git commit.
5. **Finalize + report** — best candidate scored **once** on the sealed test split;
   `report.md` + a self-contained `dashboard.html`.

## Artifacts (saved in `run_full/`)

| File | What it is |
|---|---|
| `demo.cast` | asciinema recording of the whole from-scratch run |
| `dashboard.html` | self-contained dashboard (open in any browser, offline) |
| `report.md` | baseline val → best val → sealed test (+ pass^k) |
| `events.jsonl` | the full event stream (every eval, gate decision, cost) |
| `TAU2_COMMIT.txt` | the resolved tau2-bench commit (reproducibility) |

## Replay / render the recording

```bash
asciinema play examples/tau2_airline/run_full/demo.cast        # replay in a terminal
agg examples/tau2_airline/run_full/demo.cast demo.gif          # render to GIF for a video
# (the cast is long — a real optimization run; speed up / trim for the final video)
```

## Notes
- **RITS is internal/free**, so the runner `$` is honestly `$0`; the `$400`/`$40`
  budget governs the Claude optimizer. The per-iteration `$` cap is enforced by the
  Claude CLI itself (`--max-budget-usd`).
- No-holdout (train = val = test) means the headline test number is reported as a
  **fit metric** (the engine logs a `splits_warning`); for a held-out result, pin a
  30/10/10 split via `split_ids.json`.
