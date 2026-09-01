# C5 HANDOFF — zero-shot skill-transfer pilot (train/test split by shared skill)

**Status as of 2026-09-01:** design/handoff only. No `c5` worktree exists yet. No runs
have been started. The 8 pilot fold-runs below are fully scoped and their project dirs
are **already built** (living in `c2`/`c3` — you just need to copy them in).

**You can ask the person who owns this session (boazc) for more information at any
point** — if a path, a number, or an instruction below turns out to be stale or wrong
once you check it yourself, say so and ask rather than guessing your way past it. This
doc was written by a prior Claude session working from the same repo; it isn't gospel.

## Mission

Full design: [`../docs/train_test_split_proposal.md`](../docs/train_test_split_proposal.md).
Already-scoped pilot list: [`../docs/transfer_eval_runs.md`](../docs/transfer_eval_runs.md).
Read both before starting — this handoff summarizes them but they're the source of truth.

The question: do skills cap-evolve evolves on one task **transfer** to a different task
that plausibly shares the same underlying domain skill, or are they overfit to the task
they were evolved on? For each of the two highest-priority subcategory groups from the
proposal — groups where at least one task showed real optimizer lift (`best > seed`) —
take the **winning skill** from a *train* task's completed run, freeze it, drop it
unmodified into a *test* task's project as `seed_capability/`, and score it **zero-shot**
(`--max-iterations 0`, baseline-only, no optimizer loop) on that test task's own val/test
split. Compare the transferred skill's reward to the test task's own **native seed
baseline** (already recorded in `results.json`).

## The 8 fold-runs (from `transfer_eval_runs.md`)

| # | train (skill source) | test (target) | project dir (already built) | source worktree |
|---|---|---|---|---|
| 1 | shock-analysis-demand | shock-analysis-supply | `.capevolve/project_shock-analysis-supply_from_shock-analysis-demand` | c2 |
| 2 | shock-analysis-demand | weighted-gdp-calc | `.capevolve/project_weighted-gdp-calc_from_shock-analysis-demand` | c2 |
| 3 | shock-analysis-supply | shock-analysis-demand | `.capevolve/project_shock-analysis-demand_from_shock-analysis-supply` | c2 |
| 4 | shock-analysis-supply | weighted-gdp-calc | `.capevolve/project_weighted-gdp-calc_from_shock-analysis-supply` | c2 |
| 5 | weighted-gdp-calc | shock-analysis-demand | `.capevolve/project_shock-analysis-demand_from_weighted-gdp-calc` | c2 |
| 6 | weighted-gdp-calc | shock-analysis-supply | `.capevolve/project_shock-analysis-supply_from_weighted-gdp-calc` | c2 |
| 7 | exam-block-sequencing | paratransit-routing | `.capevolve/project_paratransit-routing_from_exam-block-sequencing` | c3 |
| 8 | paratransit-routing | exam-block-sequencing | `.capevolve/project_exam-block-sequencing_from_paratransit-routing` | c3 |

Own-skill (native) baselines to compare against, from `results.json`:
- shock-analysis-demand: seed=0.0 / final_test=0.9
- shock-analysis-supply: seed=0.0 / final_test=0.2
- weighted-gdp-calc: seed=0.8 / best=1.0 (KILLED_ceiling, no final_test recorded)
- exam-block-sequencing: seed=0.1 / best=1.0 (KILLED_ceiling)
- paratransit-routing: seed=0.0 / best=1.0 (KILLED_ceiling)

For #7/#8, "success" isn't hitting 1.0 again — it's whether the *other* task's skill
lifts these off their own low seed at all.

## Step 1 — create the worktree

Run from the repo root, mirroring how c2/c3/c4 were created — a sibling of the repo, not
nested inside it:

```bash
cd /dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve
git worktree add -b intake_skillbench_c5 \
  /dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-worktrees/intake_skillbench_c5 \
  main
```

## Step 2 — populate

None of this is tracked by git (it's all gitignored `.capevolve/` state, secrets, and
untracked helper scripts) — copy it in from the sibling worktrees rather than
re-authoring:

```bash
C5=/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-worktrees/intake_skillbench_c5
C2=/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-worktrees/intake_skillbench_c2
C3=/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-worktrees/intake_skillbench_c3
C4=/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-worktrees/intake_skillbench_c4

# 1. The 8 pre-built transfer project dirs
mkdir -p "$C5/.capevolve"
for t in shock-analysis-supply_from_shock-analysis-demand \
         weighted-gdp-calc_from_shock-analysis-demand \
         shock-analysis-demand_from_shock-analysis-supply \
         weighted-gdp-calc_from_shock-analysis-supply \
         shock-analysis-demand_from_weighted-gdp-calc \
         shock-analysis-supply_from_weighted-gdp-calc; do
  cp -r "$C2/.capevolve/project_$t" "$C5/.capevolve/"
done
for t in paratransit-routing_from_exam-block-sequencing \
         exam-block-sequencing_from_paratransit-routing; do
  cp -r "$C3/.capevolve/project_$t" "$C5/.capevolve/"
done

# 2. Secrets — NEVER commit this, it's gitignored, keep it that way
cp "$C4/.env" "$C5/.env"

# 3. CCC job-submission scripts. Best-of-both: c4's submit_ccc_experiment.sh has
#    --host support and the correct "normal" default queue (c3's/c2's copy still
#    defaults to "x86_6h", which does NOT work on this cluster — see Step 4); c3's
#    setup_podman.sh is the superset with the extra python-slim/ubuntu-20.04/
#    bugswarm/oss-fuzz base-image patches. Take both, don't mix-and-match further.
mkdir -p "$C5/scripts/ccc"
cp "$C4/scripts/ccc/run_ccc_experiment.sh" "$C4/scripts/ccc/submit_ccc_experiment.sh" \
   "$C4/scripts/ccc/run_ccc_smoke.sh" "$C5/scripts/ccc/"
cp "$C3/scripts/ccc/setup_podman.sh" "$C3/scripts/ccc/generate_task_project.sh" \
   "$C5/scripts/ccc/"
chmod +x "$C5"/scripts/ccc/*.sh
```

Also confirm reachable (shared across worktrees, should already be true):
- SkillsBench clone: `.../skillberry_ai/cap-evolve-benchmarks/skillsbench/`
- `bench` CLI: `~/.local/bin/bench` (benchflow 0.6.5)

## Step 3 — venv

This experiment makes **no changes to `core/cap_evolve/`** — it only runs existing spec
files with `--max-iterations 0`. That means the shared `cap-evolve/.venv` is fine to use,
consistent with how c1/c2/c3 ran. Verify before trusting it:

```bash
cap-evolve/.venv/bin/python -c "import cap_evolve; print(cap_evolve.__file__)"
```

If at any point you find yourself editing `core/cap_evolve/` (you shouldn't need to for
this task) — **never edit it in the main repo**, c1/c2/c3/c4 share it; build c5 its own
venv first (`uv venv .venv && uv pip install -e core[dev]` from inside `intake_skillbench_c5/`).

## Step 4 — how to run jobs on CCC (this section was missing from C4's handoff)

CCC is IBM's internal compute cluster; jobs are scheduled with **LSF** (`bsub`/`bjobs`/
`bkill`), not run inline on the login node. Every job needs podman's rootless-container
workarounds set up fresh on whatever compute host it lands on — that's what
`scripts/ccc/run_ccc_experiment.sh` does for you *inside* the job; you don't need to
`ssh` anywhere or set that up by hand.

**Before submitting anything**, activate a venv with `cap-evolve` on `PATH` in your
submitting shell — `bsub` jobs inherit the environment of the shell that calls `bsub`:

```bash
source /dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve/.venv/bin/activate
cd /dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-worktrees/intake_skillbench_c5
```

### Option A (recommended) — the `submit_ccc_experiment.sh` wrapper

Builds the `bsub` command for you, including host pinning:

```bash
bash scripts/ccc/submit_ccc_experiment.sh \
    --suite-id transfer_eval_v1 \
    --run-id  transfer_<train>_to_<test>_v1 \
    --max-iterations 0 \
    --spec    ".capevolve/project_<test>_from_<train>/capevolve.<test>.yaml" \
    --project ".capevolve/project_<test>_from_<train>" \
    --queue normal \
    --host  <dedicated_host>
```

Add `--dry-run` first to print the exact `bsub` invocation without submitting, so you can
sanity-check paths before spending a job slot. Run `bash scripts/ccc/submit_ccc_experiment.sh`
with no args, or read the comment header at the top of the file, for the full flag list
(`--memory`, `--walltime`, `--cpus`, `--extra-args` are also available).

**Important — the script's own `--queue` default is stale.** It defaults to `x86_6h`,
which is not a submittable queue on this cluster. Always pass `--queue normal` explicitly
(see below) until/unless someone fixes the default.

### Option B — raw `bsub`, if you want full manual control

```bash
bsub -q normal -M 64G -n 4 -W 2:00 -m <dedicated_host> \
    -J capevolve_transfer_<train>_to_<test> \
    -oo /dccstor/knewedge2/boazc/ccc_logs/%J.stdout \
    -eo /dccstor/knewedge2/boazc/ccc_logs/%J.stderr \
    bash scripts/ccc/run_ccc_experiment.sh \
        --suite-id transfer_eval_v1 \
        --run-ts  transfer_<train>_to_<test>_v1 \
        --max-iterations 0 \
        --spec    ".capevolve/project_<test>_from_<train>/capevolve.<test>.yaml" \
        --project ".capevolve/project_<test>_from_<train>"
```

Flag meanings (all confirmed against real usage in this repo, not guessed):
- `-q normal` — the **only** submittable non-idle queue on this cluster. `x86_1h` /
  `x86_6h` from older docs/scripts do not exist here — don't use them.
- `-M 64G -n 4 -W 2:00` — memory, CPU slots, wall-clock limit (`H:MM`). These runs are
  `--max-iterations 0` (single eval, no optimizer loop), so 2:00 is generous; shrink if
  you want to pack more jobs through the queue.
- `-m <dedicated_host>` — **required**, not optional. Podman's `graphroot`/`runroot`
  live under host-local `/tmp`, keyed **per user, not per job** — two jobs landing on the
  same host at the same time corrupt each other's podman state. Pick a free host with
  `bhosts -w` (look for a low/no job count) and give each *concurrently running* job a
  distinct one. Sequential jobs can reuse a host once the earlier one has finished.
- `-J <name>` — job name, shown in `bjobs`; make it descriptive (`capevolve_transfer_<train>_to_<test>`)
  since you'll have 8 of these in flight.
- `-oo`/`-eo` — raw LSF stdout/stderr, written to `/dccstor/knewedge2/boazc/ccc_logs/%J.{stdout,stderr}`
  (`%J` = LSF job ID). Use the `/dccstor/...` path, not `/tmp` — `/tmp` is host-local and
  unreadable once you're on a different node or login session.

### What happens inside the job

`run_ccc_experiment.sh`: sources `setup_podman.sh` (private dbus, rootless-podman apt/chown
workarounds, patched base images — all idempotent, safe to re-run), loads `.env` secrets,
resolves the `cap-evolve` binary from `PATH` (your activated venv) or `$CAP_EVOLVE_BIN`,
then runs `cap-evolve run --spec ... --project ... --max-iterations 0`. Structured output
lands under, inside the c5 worktree:

```
results/<suite-id>/<run-id>/setup.log          # setup_podman.sh output
results/<suite-id>/<run-id>/cap-evolve.log     # cap-evolve stdout+stderr
results/<suite-id>/<run-id>/env_snapshot.txt   # host, LSF vars, redacted .env, git commit, podman info
results/<suite-id>/<run-id>/run/               # symlink to .capevolve/run_<run-ts>/ (state.json, rollouts, etc.)
```

`<run-id>` is the LSF job ID (`$LSB_JOBID`) when submitted via `bsub`/the wrapper, or
`local_<timestamp>` if you ever run the script directly without LSF.

### Checking on jobs

```bash
bjobs -w            # all your running/pending jobs, wide format
bjobs -l <jobid>     # full detail on one job
tail -f /dccstor/knewedge2/boazc/ccc_logs/<jobid>.stdout   # live log
```

There's no wait/poll helper in this repo (no `bwait`) — checking is manual: re-run
`bjobs -w` or tail the log.

### Killing a job

```bash
bkill <exact_jobid>
```

**Never** a wildcard, never `bkill 0`, never `bkill -u boazc` — sibling Claude Code
sessions on this account share your UID, and a bulk kill takes their jobs down too.

## Step 5 — run the 8 folds

Run one at a time, or several in parallel each on its own `--host` (check `bhosts -w`
first). `--max-iterations 0` runs are cheap — a single baseline eval, no optimizer loop —
so parallelizing across hosts is reasonable if slots are free.

For each row in the table in "Mission" above, substitute `<train>`/`<test>` into either
the Option A or Option B command. Example for fold #1:

```bash
bash scripts/ccc/submit_ccc_experiment.sh \
    --suite-id transfer_eval_v1 \
    --run-id  transfer_shock-analysis-demand_to_shock-analysis-supply_v1 \
    --max-iterations 0 \
    --spec    ".capevolve/project_shock-analysis-supply_from_shock-analysis-demand/capevolve.shock-analysis-supply.yaml" \
    --project ".capevolve/project_shock-analysis-supply_from_shock-analysis-demand" \
    --queue normal \
    --host  <dedicated_host>
```

## Step 6 — record results

Report the **test** reward from each fold-run against the test task's own **native seed
baseline** (table above). Append rows to `results.json` with `source: transfer-eval-v1`,
per the convention `C4_HANDOFF.md` set.

**Coordination note:** the canonical `results.json` lives only in the
`results/skillsbench-task-by-task-87` worktree (`intake_skillbench_c1`), not in c2/c3/c4/c5
— it was never copied because it's the single shared results ledger. Before writing into
it directly from c5: check whether a session is actively using the c1 worktree right now
(ask the user), since two sessions editing the same file concurrently can silently drop
each other's writes. If in doubt, keep your 8 new rows in a local file under
`c5/results/transfer_eval_v1_results.json` instead, and ask the user to merge them into
the canonical `results.json` by hand.

## Step 7 — optional: extend beyond the pilot (not required, ask first)

If this pilot is informative and you're asked to continue, `train_test_split_proposal.md`
lists more groups (priority 3+: cybersecurity/vulnerability-analysis, cybersecurity/fuzzing,
and others) whose project dirs are **not** built yet — you'd need to copy the winning
skill out of the train task's completed run and author a new
`project_<test>_from_<train>/` dir (spec + `seed_capability/`) before you can run them.
`scripts/ccc/generate_task_project.sh` (copied into c5 above, from c3) may help scaffold
this — read it first, it wasn't written for this exact purpose and may need adapting.
Ask the user before spending time on this; the proposal itself says to decide whether to
scale up only after seeing the priority-1/2 pilot results.

## Standing rules (carry over, unchanged)

- `bsub -m <dedicated_host>` per job — podman graphroot is per-user, not per-pid; packing
  two jobs on one host corrupts state.
- `bkill` by **exact job ID only**, never a wildcard — sibling Claude sessions share the
  UID, and a bulk kill catches their jobs too.
- **Never** push to public git remotes without explicit approval.
- `.env` is gitignored — don't commit it, in c5 or anywhere else.
- **Never** edit `cap-evolve/core/` in the main repo directly — c1/c2/c3/c4 all share it.
- If something about this handoff doesn't match what you find on disk, **ask the user**
  rather than silently working around it or guessing — paths and script versions drift
  between worktrees faster than handoff docs get updated.

## Out of scope for c5

- Building project dirs for priority-3+ groups (see Step 7 — ask before doing this).
- Anything to do with the 10 partial-lift or 10 NO_SIGNAL tasks from `C4_HANDOFF.md` —
  unrelated experiment, different worktree (`c4`).
- The Opus 4.6 → newer-model migration for optimizer/evaluator — separate item.
