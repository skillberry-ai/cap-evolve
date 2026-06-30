# Reproducing the SkillsBench skill-package run (one-prompt onboarding)

This reproduces the bundled [`examples/skillsbench`](../examples/skillsbench) end to end:
onboard **SkillsBench as a brand-new benchmark** (intake clones it + installs the BenchFlow
CLI), wire a `claude-sonnet-4-6` agent in a **Docker** sandbox, build the adapter, pass the
`cap-evolve check` hard gate, then run the full **optimize → significance-gate → sealed-test
→ report** loop. Zero assumptions — nothing is expected to pre-exist except the prerequisites.

The capability under optimization is the four **shared office-document Agent Skills**
(`docx`/`pptx`/`xlsx`/`pdf`) the benchmark deploys to its agent; the optimizer is
`claude-code @ claude-opus-4-8`.

## Result of the run

| | pass rate | Δ vs baseline |
|---|---|---|
| **Baseline val** (seed skills, 7 tasks · 3 trials) | **0.333** | — |
| **Best candidate** (`cand_0004`) on val | **0.714** | **+0.381 (≈ +114% relative)** |
| **Baseline seed skills** on sealed **test** (3 tasks · 3 trials) | **0.556** | — |
| **Optimized skills** on sealed **test** | **0.667** | **+0.111 (held-out)** |

Metric = SkillsBench verifier pass rate (binary per task). Four iterations accepted behind
the paired gate (`+0.048, +0.190, +0.048, +0.095`); the last three rejected once the two
remaining failures were diagnosed as broken/hardcoded oracles (ceiling). The optimizer edited
all four skill bodies AND added executable scripts (`pptx/scripts/recalc.py`, `xlsx/scripts/`).
Raw numbers: [`examples/skillsbench/run_full/final.json`](../examples/skillsbench/run_full/final.json);
narrated story: [`examples/skillsbench/DEMO.md`](../examples/skillsbench/DEMO.md);
per-iteration handover: [`run_full/JOURNAL.md`](../examples/skillsbench/run_full/JOURNAL.md).

---

## 1. Prerequisites (the only things you provide)

- **Docker** (running), **`uv`**, **Python 3.10+**, **git**.
- **An optimizer:** a logged-in Claude Code session for `claude-code @ claude-opus-4-8`.
- **Agent + optimizer credentials** — the Anthropic-compatible gateway, in a repo-root `.env`
  (read automatically by `adapters/anthropic_env.py` and propagated into the Docker sandbox
  via `--agent-env`; never hardcoded):
  ```
  ANTHROPIC_BASE_URL=...
  ANTHROPIC_AUTH_TOKEN=...
  ```
  (copy these from `~/.claude/settings.json`'s `env` block). The agent under test is
  `claude-sonnet-4-6`.

Everything else — cap-evolve, the `benchflow` CLI, SkillsBench, the dashboard server — is
installed by `setup.sh`.

## 2. The prompt (what a coding agent is given)

The onboarding is driven by [`examples/skillsbench/PROMPT.md`](../examples/skillsbench/PROMPT.md):
paste it to Claude Code at the repo root and say **"follow RUN.md."** It is the exact intake
input — capability `[skill-package]` (the four shared office skills), benchmark SkillsBench
(`https://github.com/benchflow-ai/skillsbench`, run via the `bench` CLI in `--sandbox docker`),
runner `claude-sonnet-4-6`, scorer = the verifier's binary pass + gold-safe CTRF feedback,
optimizer `claude-code @ claude-opus-4-8`, algorithm `hill-climb --focus all`, 10 tasks split
train==val (7) / test (3 sealed), `num_trials 3`, a per-iteration `$40` optimizer cap.

`setup.sh` is the **executable transcript** of that intake / implement-and-check phase.

## 3. Reproduce in three commands

```bash
git clone <repo> cap-evolve && cd cap-evolve
# put gateway creds in ./.env (ANTHROPIC_BASE_URL, ANTHROPIC_AUTH_TOKEN); be logged into Claude Code

bash examples/skillsbench/setup.sh    # intake onboarding (step 4) → GREEN cap-evolve check
bash examples/skillsbench/smoke.sh    # 1 val task in Docker → a real verifier reward
bash examples/skillsbench/run.sh      # full run (7 iters · 3 trials) + dashboard (step 5)
```

## 4. What `setup.sh` does (intake / implement-and-check)

1. **Install cap-evolve** — create `.venv`, `pip install -e ./core` (CLI: `cap-evolve`), and
   the dashboard server `./dashboard/backend` (built frontend is committed; no Node needed).
2. **Onboard the benchmark** — `uv tool install benchflow` (the `bench` CLI), clone SkillsBench,
   and **record the resolved commit** to `examples/skillsbench/run_full/SKILLSBENCH_COMMIT.txt`.
3. **Scaffold + wire (the full integration)** — `intake` scaffold into `.capevolve/project`,
   then the authored integration: the adapter (`adapters/adapter.py` — `tasks`, `run_batch`
   issuing ONE `bench eval run --concurrency` over all the split's tasks with the candidate
   skills injected at `/skills`, gold-safe CTRF `score()`, multi-skill `materialize`), the
   gateway env shim (`adapters/anthropic_env.py`), the editable seed — the four shared skills
   (`docx`/`pptx`/`xlsx`/`pdf`) **extracted from the SkillsBench clone** (Anthropic-licensed,
   not vendored here; see `examples/skillsbench/seed_capability/README.md`), the
   skill-package-scoped `optimizer/INSTRUCTIONS.md`, and the spec (`capevolve.yaml`).
4. **Hard gate** — `cap-evolve check .capevolve/project` (adapter contract + deterministic
   `score()`). The run refuses to proceed until this is `{"ok": true}`.

> **SkillsBench commit (this run):** `bf3793e9ec20e9682e6f18dbf4de3c69163dc9c7`,
> `benchflow 0.6.4` (in `run_full/SKILLSBENCH_COMMIT.txt`; your clone of latest `main` may
> resolve newer — the recorded value is the source of truth).

## 5. What `run.sh` does (optimize → finalize → report)

```bash
cap-evolve estimate --spec .../capevolve.yaml                       # cost preview (spends nothing)
cap-evolve run --spec .../capevolve.yaml --project ... --run-ts full --dashboard auto
```

- **Baseline** — score the seed skills on val (7 tasks · 3 trials).
- **Each iteration** — diagnose val trajectories into failure clusters → the `claude-opus-4-8`
  optimizer (given the current best's full `./trajectories/`, the `skill-package` + `diagnose`
  skills as `./guidance/`, the cross-iteration `JOURNAL`/`LEDGER`/`RUNMAP`, and the per-task
  broke/fixed RESULT lines) edits the four skills — **and, because it is allowed to run Bash,
  it writes and verifies scripts** (not just prose) — under a per-iteration `--max-budget-usd 40`
  cap → re-evaluate all 3 trials on val via ONE parallel `bench eval run --concurrency` →
  the **paired significance gate** (`gate_k_se 0.2`, val-only) accepts/rejects → commit to git.
- **Finalize** — score **both** the baseline (seed) **and** the best candidate **once** on the
  sealed test split (seal-on-success), so the headline is the honest held-out improvement.
- **Report** — `report.md` (baseline-vs-optimized on test) + a self-contained `dashboard.html`.

Run config (`examples/skillsbench/capevolve.yaml`): `hill-climb --focus all`, `max_iterations 7`,
`num_trials 3`, `split_ids_file split_ids.json` (train==val 7 / test 3), `gate_mode paired`
`gate_k_se 0.2`, `store git`, `optimizer_skill claude-code`, `optimizer_model claude-opus-4-8`,
`optimizer_usd_per_iter 40`. Concurrency knob: `SKILLSBENCH_CONCURRENCY` (default 7).

The dashboard is decoupled from the run — start/keep it on a fixed port with
`cap-evolve dashboard --base .capevolve --port 7878` (run with `--dashboard off`), so the UI
survives the run process and avoids port contention with other concurrent runs.

## 6. Inspect the process

```bash
RD=.capevolve/run_full
cat "$RD/report.md"             # baseline val → best val → sealed test (baseline vs optimized)
python3 -c "import json;print(open('$RD/final.json').read())"  # test + test_baseline + test_delta
cat "$RD/JOURNAL.md"            # per-iteration INTENT + framework RESULT lines (broke/fixed)
git -C "$RD" log --oneline      # one commit per iteration
open "$RD/dashboard.html"       # KPIs, cumulative-best stair, heatmap, lineage, gate decisions
```

Saved artifacts are committed under
[`examples/skillsbench/run_full/`](../examples/skillsbench/run_full/).

## 7. Notes on honest results

- **train == val** (7 tasks) means val is the **fit** metric (the engine logs a
  `splits_warning`); the **test** numbers (3 held-out tasks, scored once) are the honest result.
- The agent is **stochastic**, so `num_trials 3` is what gives the paired gate real per-task
  variance — single-trial scoring made the gate reject genuine gains as noise.
- One task (`reserves-at-risk-calc`) stays 0 for baseline and optimized: the optimizer
  diagnosed its (and one val task's) oracle as internally inconsistent / hardcoded and **refused
  to overfit** — the ceiling is the benchmark's, not the optimizer's.
- The agent reaches the gateway from inside Docker via `--agent-env` (the token is briefly
  visible in the `bench` process args at runtime; it is never written to a committed file —
  `.env` is gitignored).
