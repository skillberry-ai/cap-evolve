# Reproducing the tau2-bench airline run (one-command onboarding)

This reproduces the bundled [`examples/tau2_airline`](../examples/tau2_airline) end to
end: onboard **tau2-bench airline as a brand-new benchmark** (intake clones + installs
it), wire IBM RITS, build the adapter, pass the `cap-evolve check` hard gate, then run
the full **optimize → significance-gate → sealed-test → report** loop with a live
dashboard. Zero assumptions — nothing is expected to pre-exist except the credentials.

The capability under optimization is the airline **policy + tools, jointly**; the runner
is `openai/gpt-oss-120b` via IBM RITS as **both agent and user simulator**; the optimizer
is `claude-code @ claude-opus-4-6`.

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

> **tau2-bench commit (this reproduction):** `5ebebbe827b455b3ed04fcb9294235c6ef4e5fd6`
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
  **policy AND tools** — including code-bearing tools — under the per-iteration
  `--max-budget-usd 40` cap → re-evaluate ALL 10 trials in one batched `run_trials`
  pass on val (each trial its own seed → real pass^k) → the **paired significance
  gate** (`gate_k_se 0.2`, val-only) accepts or rejects → **commit to git**.
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
(`demo.cast`, `dashboard.html`, `report.md`, `events.jsonl`, `TAU2_COMMIT.txt`). See
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
