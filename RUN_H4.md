# RUN_H4 — parallel task-by-task evaluation for parsec v4

This worktree runs **evaluations**, not optimizations: "what does artifact X
score on these tasks". One task per LSF job, one dedicated compute node per
job, N jobs at a time.

The optimization counterparts live elsewhere and are unchanged —
`scripts/parsec/v4_t2_e1/` (one task at a time, single lane) and
`scripts/ccc/run_ccc_parsec_g2.sh` (all 34 tasks jointly in one process).
h4 adds only the thing neither could do: run many tasks **concurrently**.

| script | what it does |
|---|---|
| `scripts/parsec/h4/scaffold_eval_projects.py` | one cap-evolve project per task, seeded with the artifact under test |
| `scripts/parsec/h4/make_lane.sh` | build + **verify** one lane (isolated parsec-live root) |
| `scripts/parsec/h4/run_one_eval.sh` | the payload of one `bsub` job: lane, stack up, eval, stack down |
| `scripts/parsec/h4/fan_out.sh` | submit one job per task, each pinned to its own node |
| `scripts/parsec/h4/collect.py` | merge every task's `baseline.json` into `results.json` + `summary.md` |

---

## Why lanes exist (read once)

Skillsbench needed nothing like this: each of its tasks runs inside its own
ephemeral container, so the only rule was one host per job, because podman's
graphroot is per-UID-per-host (`/tmp/podman-$UID`) and two jobs on one node
corrupt each other's image store. That rule still applies here.

Parsec adds a problem skillsbench does not have. `parsec-live` is a long-lived
**host** process that re-reads the 8 agent prompts off a shared GPFS tree on
every request, and the simulation redirect appends every tool call to one trace
file. Four surfaces are therefore per-lane:

| surface | why it cannot be shared |
|---|---|
| `config/prompts/*.md` | the adapter snapshots → applies → **restores in a `finally`**. Two lanes race on the *restore*: lane A puts the original back while lane B is still mid-trial. |
| `data/agent_learnings.md` | parsec-live **writes** it at runtime and appends it to every agent prompt, so one lane's learnings contaminate another lane's bundle. |
| trace file | the agent reads its trajectory, and the adapter its cost, back out of this file. |
| `_run/skills/` | all five simulators write into it. |

A lane is a **symlink farm**, not a copy: `src/`, `.venv/` and the other
read-only trees are symlinks to the shared clone, while `config/` and `data/`
are real copies. That is ~2.8MB per lane instead of ~990MB.

It works because `src/agent/system_prompt.py` computes
`_BASE_DIR = dirname³(__file__)`, and Python leaves `__file__` unresolved
through a symlinked directory, so `_BASE_DIR` lands on the lane. **This is
narrow**: the shared venv also carries an editable-install finder whose
`MAPPING` points `src` at the *shared* tree, and it loses only because its
`install()` *appends* to `sys.meta_path`, behind the stdlib `PathFinder` that
searches `sys.path` (which uvicorn prepends cwd to). A future `pip install -e`
that prepends instead would route every lane back to the shared tree and
silently cross-contaminate the whole sweep.

`make_lane.sh` therefore **verifies** rather than assumes: it imports the way
parsec-live does and asserts the prompt dir is the lane's own, exiting 3 if not.
Never skip it.

Ports need **no** offsetting — one node per job means all six services bind the
defaults on `127.0.0.1`. That is also the only workable scheme, because
`install_seeds.py` hardcodes `localhost` and those ports.

---

## One-time setup

Already done in this worktree, listed so a fresh checkout can be repaired:

- `.env` — `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `SKILLSBENCH_TASKS_DIR`
  (the last is a vestigial guard `run_ccc_experiment.sh` checks; the path only
  needs to exist). Mode `600`.
- `simulation-harness:bench` built and saved to
  `/dccstor/knewedge2/boazc/workarea/python/simulation-harness-bench.tar`
  (`build_sim_harness.sh`). Podman storage is per-host, so each new node loads
  it from this tarball; `run_one_eval.sh` does that automatically.
- `$PARSEC_V4N/_run/skills/` populated with the five `parsec-<service>` bundles.
- A reachable `cap-evolve` CLI. This worktree has no `.venv` of its own, so
  export `CE_BIN` (below) or symlink one.

---

## Running a sweep

```bash
cd /dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-ps-worktrees/parsec-intake-h4

# bsub inherits the submitting shell's environment — export before submitting.
export PARSEC_V4N=/dccstor/knewedge2/boazc/workarea/python/rhdp-parsec/v4_2026-09-16
export LLM_API_BASE=https://ete-litellm.ai-models.vpc-int.res.ibm.com
export LLM_API_KEY=...                         # see Credentials below
export HARNESS_LLM_SIMULATION_MODEL=azure/gpt-5.4
export CE_BIN=/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve/.venv/bin/cap-evolve
```

### 1. Scaffold the suite

The artifact under test is a directory of the 8 prompt `.md` files. For the
current live baseline that is `$PARSEC_V4N/_run/parsec-live/config/prompts`; for
a candidate it is that candidate's dir under a completed run, e.g.
`.../run_optimize_fix_20260925_082813/candidates/cand_0004`.

```bash
# the baseline, all 34 tasks
python3 scripts/parsec/h4/scaffold_eval_projects.py \
    --suite-id base01 --artifact "$PARSEC_V4N/_run/parsec-live/config/prompts"

# a candidate, only the 21 that scored sub-1.0
python3 scripts/parsec/h4/scaffold_eval_projects.py \
    --suite-id cand4 --tasks targets \
    --artifact /path/to/run_optimize_fix_20260925_082813/candidates/cand_0004
```

`--tasks` takes `all` (34, default), `targets` (the 21), or a comma list. The
scaffolder refuses an artifact that is missing or has near-empty prompt files —
an incomplete bundle would otherwise be scored as a mix of the artifact and
whatever the lane already served.

### 2. Fan out

```bash
bash scripts/parsec/h4/fan_out.sh --suite-id base01 --max-concurrent 10 --dry-run
bash scripts/parsec/h4/fan_out.sh --suite-id base01 --max-concurrent 10
```

It picks `bhosts` status-`ok` nodes, drops any already running your jobs, drops
reserved nodes (the `cccxc600`–`cccxc630` `infusion` range, the known-reserved
list, and anything `brsvs -w` reports), then pins one task per node. If fewer
nodes are free than tasks it **caps the wave** rather than doubling up; rerun it
later for the rest — tasks that already have a result are skipped, so a second
invocation resumes rather than re-spends.

Logs go to `/dccstor/knewedge2/boazc/ccc_logs/<jobid>.{stdout,stderr}`.
Each wave appends a `jobid / task / host` record under
`results/h4_<suite>/_sweep/`.

### 3. Monitor

```bash
bjobs -w
tail -f results/h4_base01/<task>/cap-evolve.log
```

**A finished parsec job hangs in LSF `RUN` forever.** At 10 concurrent, zombies
holding dedicated nodes are the dominant failure mode, so sweep for them:

```bash
for j in $(bjobs -o 'jobid' -noheader 2>/dev/null); do
  lout "$j" | grep -q "Exit:     0" && echo "$j finished — bkill $j"
done
```

Any job printing `Exit:     0` is done and is only holding a node; `bkill` that
exact id. Never `bkill 0` or `bkill -u boazc` — sibling sessions share this UID.

| symptom | meaning | action |
|---|---|---|
| `baseline.json` written, job still `RUN` | payload done, post-run hang | `bkill <jobid>`, keep the result |
| no `cap-evolve.log` after ~45 min of `RUN` | stalled in podman/stack setup | `bkill <jobid>`, resubmit (fan_out picks a different node) |
| `make_lane.sh` exit 3 | lane would serve the shared bundle | do **not** rerun blindly — see "Why lanes exist" |
| every trial scores 0.0 | stack up but not activated, or `PARSEC_SIM` unset | `parsec_stack.sh status` must show all 5 `ready` |

### 4. Collect

```bash
python3 scripts/parsec/h4/collect.py --suite-id base01
# -> results/h4_base01/results.json, results/h4_base01/summary.md
```

Exit 0 means every expected task produced a result; **exit 2 means the sweep has
holes** (missing or unreadable), which is the normal mid-flight state but must
not be mistaken for a finished one.

The collector keeps two distinctions, because collapsing either yields a number
that looks fine and is wrong:

- **An errored trial is not a zero.** Infra failures land as `reward: 0.0`
  beside genuine zeros and do not distribute evenly across what you compare —
  in v1 one outage voided 16 of 60 trials in the headline cell; in v2, 8 of 90
  baseline trials errored against 0 of 90 champion trials. Tasks with
  `errored_trials > 0` are reported separately and excluded from the headline
  mean. Re-run them (`--redo`) rather than averaging them in.
- **A missing task is not a scored task.** It is listed, never averaged over.

It also reports summed task time (what one lane would have taken) next to the
slowest single task (the floor on a fully parallel sweep), and flags the
cost-metering gap below.

---

## Cautions

**Measurement precision degrades with sweep width.** Parsec's simulators are
themselves LLM-backed, so N lanes multiply load on *two* models at once —
`azure/gpt-5.4` for simulation synthesis and `claude-sonnet-4-6` for the agent.
Measured per-task movement was **±0.25 at high load versus ±0.10 at low load**,
and load dominated elapsed time. For an eval, whose whole purpose is a precise
number, that is a real cost: consider 5 lanes rather than 10, and never compare
a wide sweep's numbers against a narrow one's without saying so.

**Cost figures are a floor, not a total.** cap-evolve's runner reports
`cost_usd: 0.0` / `tokens: 0` for some runs while wall-clock is normal — a
metering gap, tracked as cap-evolve#562, not free compute. `collect.py` flags
affected tasks and labels the total `FLOOR`.

**Equal-n, paired comparisons only.** Every real error found in v1 and v2 traced
to either unequal trial counts across a delta or errored trials counted
asymmetrically. Compare suites at the same `--num-trials`, with errored tasks
re-run rather than averaged in.

**Credentials.** `LLM_API_KEY` is passed through the environment and read from
no file by design. A live LiteLLM key was previously found in cleartext in
`$PARSEC_V4N/_run/parsec-live/config/config.local.yaml` (since tightened to
`600`) and **still needs rotating**; fanning out to N nodes multiplies the
exposure. Never let that file's contents reach a run's `env_snapshot.txt`.

**Lanes persist.** They live under `$PARSEC_V4N/_run/h4-lanes/<lane>/` and are
reused across sweeps (a few MB each). `make_lane.sh <lane> --force` refreshes a
lane's `config/`, `data/` and skills store from the shared clone; the artifact
itself is installed per-run by the adapter, not by the lane.
