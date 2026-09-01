# C4 HANDOFF — re-run the 10 partial-lift tasks

**Status as of 2026-08-31:** design/handoff only. No `c4` worktree exists yet. No runs
have been started. Whoever picks this up sets the exact budget/iteration parameters
(the owner will do this themselves) — this file specifies *what must be true*, not the
numbers.

## Mission

10/87 tasks (11.5%) improved over seed but did **not** reach 1.0 in the original 4
iterations — the most tractable remaining headroom, since cap-evolve already has a
working lever on each of them (unlike the 10 NO_SIGNAL tasks, which stayed at 0.0 with
no lever at all — out of scope here, see bottom).

**Success** = any task crossing reward ≥ 0.999 on the **test** split (not val — val
has already shown it can overstate; see the table below).

## The 10 tasks

Verified against `results.json` with the filter `best > seed + 1e-6 and best < 0.999`,
all currently `status=DONE`, `iters_spent=4`. Ordered by apparent headroom:

| task | category / subcategory | seed | best (val) | final_test | note |
|---|---|---|---|---|---|
| fix-erlang-ssh-cve | cybersecurity / vulnerability-analysis | 0.600 | 0.900 | **1.0** | already solved on test — re-verify, may not even need a re-run |
| setup-fuzzing-py | cybersecurity / fuzzing | 0.364 | 0.549 | 0.881 | test > val already; real headroom, gate was the limiter |
| energy-market-pricing | industrial-physical-systems / electricity-market-pricing | 0.000 | 0.900 | 0.8 | |
| flink-query | software-engineering / implementation | 0.000 | 0.900 | 0.9 | |
| shock-analysis-demand | finance-economics / macroeconomic-analysis | 0.000 | 0.900 | 0.9 | |
| latex-formula-extraction | office-white-collar / pdf-formula-extraction | 0.200 | 0.800 | 0.8 | |
| organize-messy-files | office-white-collar / document-classification | 0.500 | 0.900 | — (not recorded) | |
| invoice-fraud-detection | finance-economics / fraud-detection | 0.300 | 0.400 | — (not recorded) | least headroom found so far |
| shock-analysis-supply | finance-economics / macroeconomic-analysis | 0.000 | 0.300 | 0.2 | least headroom |
| crystallographic-wyckoff-position-analysis | natural-science / crystallography | 0.626 | 0.835 | **0.317** | ⚠️ val/test divergence — probable val overfit; more iterations may make test *worse*, treat as diagnostic not headroom |

Source projects: 5 tasks live in `intake_skillbench_c2`, 4 in `intake_skillbench_c3`,
`invoice-fraud-detection` in `intake_skillbench_c1` (tag `c1-tA`).

## Step 1 — create the worktree

Run from the repo root. **Note:** `cap-evolve-worktrees/` is a *sibling* of the repo,
not inside it — don't nest the `git worktree add` path under `cap-evolve/`.

```bash
cd /dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve
git worktree add -b intake_skillbench_c4 \
  /dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-worktrees/intake_skillbench_c4 \
  main
```

This gives c4 its own full checkout of `core/cap_evolve/`, isolated from c1/c2/c3 — safe
to modify without affecting the sibling worktrees or being affected by them.

## Step 2 — populate the 10 project dirs + secrets

Each task's cap-evolve project (adapter, seed skill, spec, split ids — untracked,
~118K each) already exists in c2/c3. Copy them in rather than re-authoring:

```bash
C4=/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-worktrees/intake_skillbench_c4
C2=/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-worktrees/intake_skillbench_c2
C3=/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-worktrees/intake_skillbench_c3

mkdir -p "$C4/.capevolve"
for t in energy-market-pricing organize-messy-files shock-analysis-demand \
         shock-analysis-supply; do
  cp -r "$C2/.capevolve/project_$t" "$C4/.capevolve/"
done
for t in fix-erlang-ssh-cve flink-query crystallographic-wyckoff-position-analysis \
         latex-formula-extraction setup-fuzzing-py; do
  cp -r "$C3/.capevolve/project_$t" "$C4/.capevolve/"
done
# invoice-fraud-detection lives in c1 (tag c1-tA) — locate and copy similarly.

cp "$C3/.env" "$C4/.env"   # NEVER commit this — it's gitignored, keep it that way
```

Also confirm reachable (should already be true, shared across worktrees):
- SkillsBench clone: `.../skillberry_ai/cap-evolve-benchmarks/skillsbench/` @ `9a1f4dd5`
- `bench` CLI: `~/.local/bin/bench` (benchflow 0.6.5)
- On a fresh compute node: re-source `/dccstor/knewedge2/boazc/workarea/python/setup_podman.sh`
  before any run — podman graphroot/socket state is host-local.

## Step 3 — venv: read this before running anything

**Finding from this session:** there is currently **one shared venv**, at
`cap-evolve/.venv`, and it resolves `import cap_evolve` to **main's**
`core/cap_evolve/`:

```
$ cap-evolve/.venv/bin/python -c "import cap_evolve; print(cap_evolve.__file__)"
/…/skillberry_ai/cap-evolve/core/cap_evolve/__init__.py
```

None of c1/c2/c3 has ever had its own `.venv` — every run so far has executed **main's**
harness code, whatever commit main happened to be at that day.

This matters for c4 specifically:
- **If c4 makes no code change** to `core/cap_evolve/`: using the shared
  `cap-evolve/.venv` is fine and consistent with how c1/c2/c3 ran.
- **If c4 changes harness behavior at all** (e.g. anything touching the ground-truth
  isolation question below): it **must** build its own venv with an editable install of
  **c4's own** `./core`, e.g. `uv venv .venv && uv pip install -e core[dev]` run from
  inside `intake_skillbench_c4/`. Using the shared venv in that case makes the edit a
  silent no-op — the run would still execute main's unmodified code.
- Either way: **never edit `cap-evolve/core/` in the main repo** — c1/c2/c3 (and anyone
  else) share it.

## Step 4 — ground-truth isolation (the headline requirement)

Requirement as given: *"the trained skills (the optimizer) do not have access to the
ground-truth… It should only get the reward from the evaluator."*

**This is already true, by design, for all 10 tasks — verified below.** Re-verify
rather than trust this doc; the paths are given so you can check yourself.

**Already gold-safe by construction**, in every `.capevolve/project_<task>/adapters/adapter.py`:
- `score()` (~line 284) reads the recorded reward + CTRF from `rollout.metadata`; it
  never re-invokes the verifier or touches a gold/oracle file.
- `_build_feedback()` (~line 467) states the contract explicitly: *"Gold-SAFE: we never
  read the oracle/solve.sh/gold output — only the failing test name + its message."*
- Empirically confirmed this session: searching a completed run's entire `bench_jobs/`
  tree for `test_*.py`, `solve.sh`, `gold*`, `oracle*` returned **zero hits**. The
  verifier directories the optimizer can see contain only the agent's own produced
  artifacts, the CTRF report, and `test-stdout.txt` — never the benchmark's held-out
  test code or answer key.

**What the optimizer *does* see (reward-derived, not gold — matches what was asked
for):**
- aggregate val reward + per-task reward: `harness.py` `_focus_instructions` (~1763),
  `_fmt` (~1544), `_algorithm_brief` (~1583)
- per-iteration val + Δ-vs-parent: `LEDGER.md` (built ~755), `RUNMAP.md` (~864)
- full per-trial `trial_rewards` and the complete CTRF (every test name, pass/fail,
  assertion message) via rollout JSONs copied into `work/<cand>/trajectories/`
- `RUNMAP.md` also points the optimizer at the read-only run dir "if you need
  `rollouts/<split>/` traces or the git log" — i.e. it *can* go look at more detail than
  what's summarized, but still only reward-derived detail, never gold.

**One bounded grey area, named honestly rather than silently changed:** a CTRF
assertion message for a *failing* test can embed the value the test expected. That's
the evaluator telling the agent what it got wrong — richer than a bare scalar reward,
and arguably the same kind of channel EvoSkill's isolated surrogate verifier is designed
to avoid. It is **not** gold-file access. If you (the person picking this up) want
stricter isolation than "reward + failing-test-names + assertion messages," that's a
deliberate scope decision to make explicitly, not something to patch as a bug — flag it
back rather than quietly editing `_build_feedback()`.

**No config flag exists** for any of this. `rundir.py`'s `Budget` dataclass has exactly
five fields (`max_iterations`, `max_metric_calls`, `max_usd`, `stall`,
`max_optimizer_usd`) — nothing reward-related. There's also **no stop-on-max-reward
parameter**: `stall: N` (currently `0`/disabled in every task's spec) is the closest
substitute — at val=1.0 the paired-SE gate rejects every candidate, so `stall: 1-2`
approximates "stop once you've hit the ceiling," if that's a knob you want to set.

## Step 5 — run

One task at a time; give each a unique `--run-ts`.

```bash
source .venv/bin/activate            # c4's own venv, or the shared cap-evolve/.venv — see Step 3
export $(grep -v '^#' .env | xargs)

cap-evolve run \
  --spec    .capevolve/project_<TASK>/capevolve.<TASK>.yaml \
  --project .capevolve/project_<TASK> \
  --run-ts  task_<TASK>_c4v1 \
  --max-iterations <SET BY OWNER>
```

Current per-task spec defaults you're starting from (already in each task's yaml,
change if you want a different bar): `num_trials: 10`, `gate_mode: paired`,
`gate_k_se: 0.2`, `max_iterations: 4`, `stall: 0`, `max_usd: 250`,
`max_optimizer_usd: 150`. Current models: agent/evaluator `claude-sonnet-5` (from
`.env`), optimizer `claude-opus-4-8` (per-task yaml `optimizer_model`) — unless you're
also folding in the separate Opus 4.6 migration, which is a different item, not part of
this handoff.

## Step 6 — record results

Report **test** reward, not val (see the crystallographic-wyckoff warning above — val
can overstate). Append rows to `results.json` with `source: c4-v1` so they're
distinguishable from the original c1/c2/c3 numbers.

## Standing rules (carry over, unchanged)

- `bsub -m <dedicated_host>` per job — podman graphroot is per-user, not per-pid;
  packing two jobs on one host corrupts state.
- `bkill` by **exact job ID only**, never a wildcard — sibling Claude sessions share the
  UID, and a bulk kill catches their jobs too.
- If a task's val hits 1.0 at seed, kill that run — no room left for the optimizer to
  improve.
- **Never** push to public git remotes without explicit approval.
- `.env` is gitignored — don't commit it, in c4 or anywhere else.

## Out of scope for c4 (handled separately / already parked)

- The 10 NO_SIGNAL tasks (seed=0.0 and every candidate=0.0 — no lever at all).
- The Opus 4.6 migration for optimizer + evaluator.
- Executing the train/test-split-by-shared-skill proposal (design delivered in
  `../docs/train_test_split_proposal.md`, execution deferred).
- Any edit to `heatmap.html` / `summary.md` / `evoskill_comparison_chart.html`, including
  the known `r.blocked`→`no_signal` JS field-rename bug and the 63/87-vs-64/87 pass-rate
  discrepancy — both intentionally left as-is for now.
