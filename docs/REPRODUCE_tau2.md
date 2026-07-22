# Reproducing the tau2-bench airline run (one-command onboarding)

This reproduces the bundled [`examples/tau2_airline`](../examples/tau2_airline) end to
end: onboard **tau2-bench airline as a brand-new benchmark** (intake clones + installs
it), wire IBM RITS, build the adapter, pass the `cap-evolve check` hard gate, then run
the full **optimize → significance-gate → sealed-test → report** loop with a live
dashboard. Zero assumptions — nothing is expected to pre-exist except the credentials.

The capability under optimization is the airline **policy + tools, jointly**; the runner
is `openai/gpt-oss-120b` via IBM RITS as **both agent and user simulator**; the optimizer
is `claude-code @ claude-opus-4-6`.

## Result of the committed run

| | val reward (50 tasks · 10 trials) | Δ vs baseline |
|---|---|---|
| **Baseline** (seed policy + tools) | **0.536** | — |
| **Best candidate** (`cand_0007`) | **0.712** | **+0.176 (≈ +33% relative)** |

Metric = mean tau2 task reward in `[0,1]`. The gain accretes per iteration behind the
paired significance gate; acceptances at iters 1 (`+0.046`), 3 (`+0.052`), 5 (`+0.036`),
6 (`+0.014`), 7 (`+0.028`), the other 5 rejected as noise. The `finalize` step scored its
best candidate (`cand_0007`) **once** on the sealed split at **0.694 pass@1** (pass^2 0.584).
This example is no-holdout (train = val = test = all 50), so **val IS the fit metric**.

Every accepted iteration makes deep **in-code** tool edits (prose rules → executable
guards), not just prompt tweaks — `tools.py` grows 593 → 832 lines over the run (see five
trajectory-verified before→after examples in
[`docs/OPTIMIZATION_EXAMPLES.md`](OPTIMIZATION_EXAMPLES.md)). You can
**see the result before reproducing**: open the committed full interactive dashboard
(all 10 iterations, no backend needed) — the static UI export at
[`examples/tau2_airline/run_full/ui/`](../examples/tau2_airline/run_full/ui/) — by running
`cd examples/tau2_airline/run_full/ui && python3 -m http.server 8000` (then
http://localhost:8000), or host it on GitHub Pages / any static host; read the curated story in
[`examples/tau2_airline/DEMO.md`](../examples/tau2_airline/DEMO.md), or the raw numbers in
[`run_full/final.json`](../examples/tau2_airline/run_full/final.json).

---

## 1. Prerequisites (the only things you provide)

- **Python 3.10+** and **git**.
- **RITS credentials** in a repo-root `.env` (one level above nothing — the repo root
  itself), read automatically by the adapter's RITS shim:
  ```
  RITS_API_KEY=...
  RITS_API_URL=...
  ```
- **An optimizer**: a logged-in Claude Code session (or `ANTHROPIC_API_KEY`) for
  `claude-code @ claude-opus-4-6`.

Everything else — cap-evolve, tau2-bench, the dashboard server — is installed by
`setup.sh`.

## 2. The prompt (what a coding agent is given)

The onboarding is driven by [`examples/tau2_airline/PROMPT.md`](../examples/tau2_airline/PROMPT.md):
paste it to Claude Code at the repo root and say **"follow RUN.md."** It is the exact
intake input — capability `[system-prompt, tools]`, benchmark tau2-bench airline
(`https://github.com/sierra-research/tau2-bench`, installed via `pip install -e`), runner
`openai/gpt-oss-120b` via RITS (agent **and** user simulator), scorer = tau2's task
reward in `[0,1]`, optimizer `claude-code @ claude-opus-4-6`, algorithm `hill-climb`
(`--focus all`), all 50 tasks (no-holdout fit), `num_trials 10`, a per-iteration `$40`
cap (`--max-budget-usd`) and `$400` total.

`setup.sh` is the **executable transcript** of that intake / implement-and-check phase —
the same steps a coding agent following the prompt performs.

## 3. Reproduce in two commands

```bash
git clone <repo> cap-evolve && cd cap-evolve
# put RITS creds in ./.env (RITS_API_KEY, RITS_API_URL); be logged into Claude Code

bash examples/tau2_airline/setup.sh    # intake onboarding (see step 4)
bash examples/tau2_airline/run.sh      # full run + live capybara dashboard (see step 5)
```

## 4. What `setup.sh` does (intake / implement-and-check)

1. **Install cap-evolve** — create `.venv`, `pip install -e ./core` (CLI: `cap-evolve`),
   and (default on) install the dashboard server `./dashboard/backend`. The built
   capybara frontend is committed, so no Node is needed at runtime. Toggle with
   `--dashboard` / `--no-dashboard`.
2. **Onboard the benchmark** — clone tau2-bench (latest `main`) as a sibling
   `../tau2-bench`, `pip install -e ../tau2-bench`, and **record the resolved commit** to
   `examples/tau2_airline/run_full/TAU2_COMMIT.txt`.
3. **Scaffold + wire (the full integration)** — run the `intake` scaffold into
   `.capevolve/project`, then copy in the authored integration: the adapter
   (`adapters/adapter.py` — `tasks` + `run_batch` → tau2's runner, the batched
   `run_trials` fast path, `trajectories()` returning tau2's native trace dir, and
   `score()` reading `reward_info`), the RITS shim (`adapters/rits.py`), the editable
   seed capability (`seed_capability/` = `policy/` + `tools/` +
   `reference/data_model.py`), the capability-scoped `optimizer/INSTRUCTIONS.md`, and
   the spec (`capevolve.yaml`, which sets `capability_sources` to the data model so it
   is copied verbatim into the optimizer's workdir).
4. **Hard gate** — `cap-evolve check .capevolve/project` (verifies credentials + the
   adapter contract, incl. that `score()` is deterministic). The run refuses to
   proceed until this is green.

> **tau2-bench commit (this reproduction):** `8ebb7499622fc2be9b9d510d6f7a7653461f4f29`
> (recorded automatically in `run_full/TAU2_COMMIT.txt`; your clone of latest `main` may
> resolve to a newer commit — the recorded value is the source of truth for the run).

## 5. What `run.sh` does (optimize → finalize → report)

```bash
cap-evolve estimate --spec .../capevolve.yaml   # pre-run cost preview (spends nothing)
cap-evolve run --spec .../capevolve.yaml --project ... --run-ts full --dashboard auto
```

- **Cost preview** — `cap-evolve estimate` prints the call counts (`val × trials ×
  iterations` runner calls, `iterations` optimizer calls) and a calibrated `$` range.
- **Baseline** — score the seed policy + tools on val.
- **Each iteration** — diagnose val traces into failure clusters → the
  `claude-opus-4-6` optimizer (given the current best step's full `./trajectories/`,
  the selected capability skills both as `./guidance/<cap>/` and natively in
  `.claude/skills/`, the data model in `./guidance/sources/`, the per-task impact of
  prior edits + the passing set to protect, and the STATE/MEMORY handover) edits the
  **policy AND tools** — driven by **argument-level feedback** from the failing
  rollouts, it turns prose policy rules into **executable in-code guards inside the
  existing tool bodies** (eligibility checks, idempotency / no-op guards, route
  validation) and adds composite tools (e.g. a `get_all_reservation_details` loop) —
  under the per-iteration `--max-budget-usd 40` cap → re-evaluate ALL 10 trials in one
  batched `run_trials` pass on val (each trial its own seed → real pass^k) → the
  **paired significance gate** (`gate_k_se 0.2`, val-only) accepts or rejects →
  **commit to git**. Across the committed run `tools.py` grows 593 → 832 lines.
- **Finalize** — score the best candidate once on the sealed test split (seal-on-success).
- **Report** — `report.md` + a self-contained `dashboard.html`. The **live dashboard**
  shows per-iteration optimizer + runner **cost & time**, the one-time **intake cost**,
  the cumulative-best stair, the tasks × iterations heatmap, the diff per iteration, the
  lineage tree, and the gate decisions.

Run config (from `examples/tau2_airline/capevolve.yaml`): `hill-climb --focus all`,
`max_iterations 10`, `num_trials 10`, `split_ids_file split_ids.json` (no-holdout fit),
`gate_mode significant` `gate_k_se 0.2`, `store git`, `max_usd 400`,
`optimizer_usd_per_iter 40`, `TAU2_MAX_CONCURRENCY 125`.

## 6. Inspect the process

```bash
RD=.capevolve/run_full
git -C "$RD" log --oneline      # one commit per iteration (the whole optimization)
cat "$RD/report.md"             # baseline val → best val → sealed test (+ pass^k)
open "$RD/dashboard.html"       # KPIs, cumulative-best stair, heatmap, lineage, cost/time
cat "$RD/rejected.jsonl"        # what the honest gate rejected (optimizer memory)
```

Saved artifacts also land in [`../examples/tau2_airline/run_full/`](../examples/tau2_airline/run_full/)
(`demo.cast`, the full interactive dashboard under `ui/` — all 10 iterations, no backend
needed; serve with `python3 -m http.server 8000` in that dir or host on GitHub Pages /
any static host — `report.md`, `events.jsonl`, `TAU2_COMMIT.txt`). See
[`examples/tau2_airline/DEMO.md`](../examples/tau2_airline/DEMO.md) for the narrated walkthrough.

## 7. Notes on honest results

- **No-holdout** (train = val = test = all 50) means the headline test number is reported
  as a **fit metric** — the engine logs a `splits_warning` and the report flags it. For a
  held-out result, pin a 30/10/10 split via `split_ids.json`.
- **RITS is internal/free**, so the runner `$` is honestly `$0`; the `$400` total /
  `$40`-per-iteration budget governs the Claude optimizer, and the per-iteration cap is
  enforced by the Claude CLI itself (`--max-budget-usd`).
- On a small held-out val the paired gate will correctly refuse gains it cannot
  distinguish from noise — that is the system working, not failing. More trials or a
  larger val give a real gain the statistical power to clear the gate.

## 8. Agent-mode reproduction (held-out 30/20, litellm proxy)

The same benchmark, run in **agent orchestration mode** with the `agent-optimize` algorithm —
the conversational agent drives the loop itself (see [`AGENT_ORCHESTRATION.md`](AGENT_ORCHESTRATION.md)).
This uses the generic litellm-proxy model wiring (`adapters/model_config.py`), not RITS, so it
works with any `aws/gpt-oss-120b`-behind-a-proxy endpoint.

Project: a litellm-proxy-wired tau2 project (the local `e2e/tau2/.capevolve/project` harness — the
same adapter as `examples/tau2_airline` but importing `model_config.py` instead of `rits.py`; set it
up once alongside your proxy creds). Split: `inputs/split_ids.json` pins **30 train == 30 val**
and a disjoint **20 test** (held out). Model: `aws/gpt-oss-120b` (agent + user simulator) via the
proxy; the optimizer is the conversational agent itself (`optimizer_skill: mock`, never invoked).

```bash
# 1) credentials for the litellm-proxy path (repo-root or e2e/tau2/.env)
cat > e2e/tau2/.env <<'ENV'
MODEL=litellm_proxy/aws/gpt-oss-120b
LITELLM_PROXY_API_BASE=https://<your-litellm-proxy-host>
LITELLM_PROXY_API_KEY=<your-proxy-key>
TEMPERATURE=0.0
ENV

export CAPEVOLVE_SKILLS_DIR="$PWD/skills"
export PYTHONPATH="$PWD/e2e/tau2/.capevolve/project/adapters"
export TAU2_MAX_CONCURRENCY=15 TAU2_LLM_TIMEOUT=240 TAU2_LLM_RETRIES=2

# 2) hard gate + agent-mode check+baseline (prints the handoff, scores val baseline)
cap-evolve check e2e/tau2/.capevolve/project
cap-evolve run --spec e2e/tau2/.capevolve/project/capevolve.yaml \
               --project e2e/tau2/.capevolve/project --run-ts e2e --dashboard off
# -> {"mode":"agent","run_dir":".capevolve/run_e2e","algorithm":"agent-optimize", ...}
```

From the handoff, the agent drives the `agent-optimize` loop against `run_e2e`: it reads the
failing-task feedback, proposes a general edit to `policy.md` / `tools.py` in a candidate copy,
evaluates on **full val**, and accepts only through the paired gate — using the phase scripts:

```bash
S="$CAPEVOLVE_SKILLS_DIR"; R=e2e/tau2/.capevolve/run_e2e; P=e2e/tau2/.capevolve/project
python "$S/phases/evaluate/scripts/run.py" --run-dir "$R" --project "$P" --candidate "$R/work/cand_1" --split val --n-trials 1
python "$S/phases/gate/scripts/run.py"     --mode significant --k-se 1.0 --current <best_mean> --candidate <cand_mean> --candidate-stderr <se> --current-stderr <se>
# on accept: RunDir.snapshot + set_best + log_event (see AGENT_ORCHESTRATION.md)
python -c "from cap_evolve import RunDir; import json; print(json.dumps(RunDir.open('$R').spent.to_dict(), indent=2))"  # constraint re-read

# stop when the full-val mean clears the stop_condition, then seal test ONCE + report:
python "$S/phases/finalize/scripts/run.py" --run-dir "$R" --project "$P" --n-trials 1
python "$S/phases/report/scripts/run.py"   --run-dir "$R"
```

Deterministic comparison on the identical split (`capevolve.det.yaml`, `hill-climb`, Claude Code
optimizer via the same proxy):

```bash
cap-evolve run --spec e2e/tau2/.capevolve/project/capevolve.det.yaml \
               --project e2e/tau2/.capevolve/project --run-ts det --dashboard off
```

This produced (single-trial) val **0.50 → 0.633** (+26.7%, gate-significant) and a sealed held-out
test **0.40 → 0.55** (+37.5%), beating the deterministic run head-to-head. See [`RESULTS.md`](RESULTS.md)
for the full table incl. the stable n=3 re-evaluation and the honest caveats.
