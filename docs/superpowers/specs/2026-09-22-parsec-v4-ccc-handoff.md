# HANDOFF — parsec v4 task-by-task optimization, moving from Mac to CCC

Written 2026-09-22, handing off to a fresh Claude Code session in a new VS Code window on
CCC. Read this end-to-end before running anything — it combines two streams that have never
been combined before: the CCC/LSF operational knowledge from the `3x2_toy` skill-merge pilot,
and the parsec v4 `v4_t2_e1` work already built and pushed on the Mac. Nothing in this repo has
ever been run on CCC for parsec; treat that as new, unvalidated scope, not a drop-in reuse of
either side's playbook.

## Where you are

- Worktree: `/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-ps-worktrees/parsec_g2`
- Branch: `parsec_g2`, created off `origin/parsec-intake_v4` @ `da299d99` (2026-09-22) — tracks
  `origin/parsec-intake_v4`, but is its own branch so pushes here don't collide with the Mac
  side pushing to the same PR branch. `origin/parsec-intake_v4` is PR **#495** (open, not yet
  merged, last pushed 2026-09-19 by the user from the Mac).
- Naming: this follows the `intake_skillbench_c7`/`c8` worktree-per-stream convention, but
  under a **new parent directory** `cap-evolve-ps-worktrees/` (not `cap-evolve-worktrees/`) to
  keep the parsec work stream visually distinct from the skillsbench `c1`-`c9` stream, and
  `_g2` instead of a `c<n>` suffix per the user's explicit naming choice.

## Read these two documents first, in full

1. **`HANDOFF.md`** at this worktree's root — the 2026-09-09 handoff written for the *previous*
   Mac session, carrying forward v1/v2 lessons (30-task and 10-task predecessor experiments).
   The most important parts for you: the "cross-cutting lessons" section (DCO, ask-before-push,
   equal-n paired comparisons, no hardcoded personal paths, generate-every-number-once) and the
   specific traps each of v1 and v2 hit (backend-reachability gating scores by construction in
   v1, unequal trial counts inflating a delta in v2, infra errors silently counted as zero in
   both).
2. **`docs/superpowers/specs/2026-09-17-parsec-v4-task-by-task-optimization-design.md`** — the
   design doc for the phase you're picking up (`v4_t2_e1`). It explains: why v1/v2's
   inject-a-file-into-a-disposable-container pattern doesn't work for v4 (v4's capability is 8
   live prompt files served by a standing host-side `parsec-live` process, not a file read once
   at container boot); how candidate injection actually works now (overwrite
   `config/prompts/*.md` in the live clone, picked up on the next request via an mtime-keyed
   cache — no restart); the per-task project layout; and, critically, its own explicit
   **"Not CCC"** section (quoted below) — this is the exact gap your session exists to close.

## What's already built and pushed (nothing more to build for a plain rerun)

All on `origin/parsec-intake_v4` (this branch's base), commits `97bb1e9f`..`da299d99`,
2026-09-17 to 2026-09-19:

- The harbor adapter (`scripts/v4_t2_e1/common/adapters/adapter.py`) that snapshots the 8 live
  prompt files on entry, applies a candidate, yields, and restores them in a `finally` —
  isolation is hand-built here because the shared `parsec-live` process has no per-trial
  container to just discard.
- `scripts/v4_t2_e1/scaffold_projects.py` — scaffolds one cap-evolve project per task, for the
  **21 of 34 tasks** that scored a 3-trial average below 1.0 in the `v4_t1_e1` baseline sweep
  (`rhdp-parsec/v4_2026-09-16/_run/jobs/full34/progress.csv`). Train = val = test = {that task}
  for every project — deliberately no holdout at this scope (see *Phase-2 scope* in the design
  doc for why).
- `scripts/v4_t2_e1/run_one_task.py` — single-task runner, one standalone process per task, with
  an advisory lock enforcing single-lane use of the one shared `parsec-live` stack.
- `scripts/v4_t2_e1/preflight_check.py` — guards against a stale installed `cap-evolve` that
  predates `stop_at_reward` (PR #415, `d1275b32a`) silently no-op'ing that budget field.
- The optimizer `INSTRUCTIONS.md`, scoped to system-prompt-only edits across the 8 files.
- **The cost/time tracing fix the user mentioned** (`177dbb28`, 2026-09-19): Harbor's own
  `result.json` never carries real cost for `ParsecAgent`, because the agent's real LLM calls
  happen inside the already-running external `parsec-live` process, outside Harbor's
  agent-invocation metering. `run_target()` now brackets its harbor subprocess call with a UTC
  timestamp window and sums `cost_usd`/tokens out of `parsec-live`'s own
  `usage runtime=... cost_usd=...` log lines that fall in that window — this is what makes
  `capevolve.yaml`'s `max_usd: 50.0` budget guard (and any real cost reporting you do) actually
  work instead of silently reading zero.
- Per the last commits' scope (env-overriding `PARSEC_V4N`, sorting trajectories numerically,
  guarding seed snapshots against silent re-copy), this has been debugged well past a first
  smoke test — but **no `v4_t2_e1` results/progress artifacts are committed anywhere on this
  branch** (`git ls-tree -r origin/parsec-intake_v4 | grep v4_t2_e1` turns up only source and
  tests, no `progress.csv`/`results.json`/run directories). Per `HANDOFF.md`'s own stated
  discipline ("raw simulator rollouts are deliberately not committed... only derived per-task
  score vectors get committed"), any run output that exists lives in a local `_run/` directory
  on the Mac, uncommitted — **ask the user directly whether a real 21-task sweep has actually
  completed anywhere, and if so, where its results currently live**, before assuming you're
  starting the sweep from zero or that you're resuming a partially-run sweep.

Task count: **34 is correct**, not 30 — 30 was the pre-fix `v4_old` count; the corrected
`rhdp-parsec/v4_2026-09-16` bundle has 34, and 21 of those 34 scored sub-1.0 at baseline. Don't
use the 30-task figure from the 2026-09-09 doc; it's superseded.

## Not accessible from CCC — flag, don't silently substitute

The user pointed at
`/Users/boazc/workarea/Python/skillberry_ai/cap-evolve-worktrees/parsec-v4-docs/docs/specs/2026-09-21-parsec-v4-experiment-plan-design.md`
as possibly the most current design doc. **That path is Mac-local and does not exist on this
CCC filesystem** (confirmed via `ls`). Everything findable on `origin/parsec-intake_v4` tops
out at 2026-09-19 (commit `da299d99`) — one day *before* that doc's date. It's possible that doc:
(a) is genuinely newer than anything pushed and simply hasn't reached `origin` yet, or (b) is an
uncommitted local note that duplicates what's already in the pushed `2026-09-17` design doc and
`HANDOFF.md`. **Ask the user directly** whether they can push that doc (or the branch/worktree
it lives in) to `origin`, or paste its content, before assuming this handoff doc's summary of
the 09-17 doc supersedes it — don't silently proceed as if the gap doesn't matter if the user
indicates there's newer content in it.

## The actual job: port `v4_t2_e1` execution from Mac-local to CCC/LSF

This is genuinely new work, not a resubmit of the skillsbench pattern. The 2026-09-17 design
doc's own "Not CCC" section, verbatim:

> `CCC_PODMAN_SETUP.md`'s entire runbook (rootless-podman UID workarounds, the LSF batch-mode
> lessons) was built and validated for BenchFlow/SkillsBench specifically — it has never been
> exercised for bench-v4's docker-compose-based harness or its host-side `parsec-live` process,
> and porting it is new, unvalidated scope, not a drop-in reuse.

What's different about parsec v4 vs. the skillsbench/`3x2_toy` pattern you may be more familiar
with, and why each difference matters for a CCC port:

| skillsbench (`3x2_toy`, `c7`/`c8`) | parsec v4 (`v4_t2_e1`) | why it matters on CCC |
|---|---|---|
| BenchFlow gives each task its own isolated Docker container | One shared `docker-compose` topology, 5 services on **fixed** ports (8086 platform / 8087 github / 8088 icinga / 8089 cost / 8090 cloud) + one `parsec-live` uvicorn process on port 8000 + one shared trace file + one shared skills-store volume | Two concurrent LSF jobs on the same host, or even different hosts if ports aren't lane-isolated, will clobber each other's seeded data and injected prompts. Every port is env-overridable (`<SERVICE>_MCP_URL`, `PARSEC_URL`) — port-offsetting per lane is required, not optional, the moment you run more than one task at a time. |
| No live host-side process to inject into; candidate is a file read at container boot | `parsec-live` is a long-lived uvicorn process per lane; injection = overwriting `config/prompts/*.md` in its live clone | A CCC job needs to *start and keep alive* its own `parsec-live` process (and the 5-service compose stack) for its lane's duration, not just run a container and exit. Figure out whether that's one `bsub` job that starts everything and tears it down, or a separately-managed long-running service the LSF jobs talk to. |
| Podman/rootless-UID concerns (per `CCC_PODMAN_SETUP.md`) | docker-compose-based — same podman rootless-UID class of concern almost certainly applies (per-user graphroot, not per-pid — [[feedback_dedicated_hosts]]), but has **never been exercised** for this specific compose topology | Don't assume the existing podman setup doc's fixes transfer as-is; validate against this specific 5-service compose stack + the extra `parsec-live` process before trusting it. |
| Each simulated response is instant (mocked) | Every simulated tool response is **model-synthesized**, 30–60s per call (per the parsec v4 README) | Per-trial wall-clock is dominated by simulation latency, not skillsbench-style fast containers. Budget LSF job walltime expectations (or rather, the *absence* of `-W`, per below) accordingly — a task-level run here is much slower than a `3x2_toy` arm. |
| 2 tasks total | 21 target tasks (of 34), one project each | More jobs to track by exact ID; the "kill on Exit 0/1, don't trust bjobs STAT" discipline matters even more at this scale. |

### Carry forward as-is from the `3x2_toy`/skillsbench CCC playbook

These operational rules are architecture-agnostic and apply directly, unchanged:

- **One dedicated host per concurrent job** (`bsub -m <host>`), checked against `brsvs -w` for
  hidden reservations — [[feedback_dedicated_hosts]]. This matters *more* here, not less: unlike
  skillsbench's per-task Docker isolation, two parsec lanes sharing a host could also collide on
  ports/processes even with `-m` isolating them from other users' jobs, so host-per-lane and
  port-offset-per-lane are two separate, both-required isolation mechanisms.
- **Never pass `-W`** (walltime) to a `bsub` job — [[feedback_bsub_no_walltime]]. Given
  30-60s-per-simulated-call latency, a walltime limit here is even more likely to kill a job
  mid-postprocessing after it already produced a valid result than in the skillsbench case that
  rule was written for.
- **Check the job's own log, not just `bjobs`/LSF `STAT`** —
  [[feedback_check_log_not_just_lsf_status]]. The `3x2_toy` pilot's every zero-shot arm finished
  cleanly (`Exit: 0`) then sat in LSF `RUN` state indefinitely; expect the same or worse here
  given a long-lived `parsec-live` process that has no natural "exit" signal of its own.
- **Kill by exact job ID the moment a result is complete or `Exit 0`/`Exit 1` appears** —
  [[feedback_kill_on_exit_status]] and [[feedback_lsf_done_dependency]]. The cross-kill risk from
  a same-UID `bkill` in a parallel session applies doubly here since you're now running two
  concurrent work streams (skillsbench `c7`/`c8` and this parsec CCC line) under the same user.
- **Kill a saturated optimizer run once val hits 1.0** —
  [[feedback_saturated_baseline]] — `stop_at_reward: 1.0` is already wired into each task's
  `capevolve.yaml` per the design doc (PR #415), so this should fire automatically; verify it
  actually does on the first real task before trusting it across all 21.
- **`-n 1`** for jobs with no internal parallelism — [[feedback_bsub_cpu_slots]]. Each
  `run_one_task.py` invocation is single-task, single-lane by the adapter's own advisory lock;
  there's nothing to parallelize inside one job.
- **Sign off every commit from the start** (`git commit -s`) in this repo —
  [[feedback_check_ci_after_pr]] — and still run `gh pr checks` after opening any PR from this
  worktree. This branch already inherits signed commits from the Mac side; keep that going.
- **Ignore the test split** — likely does **not** apply here, unlike skillsbench
  ([[feedback_ignore_test_split]]). `v4_t2_e1`'s per-task projects deliberately set
  train=val=test to the single task (no split at all, by design, at this scope) — this is a
  different situation from skillsbench's train/val/test-all-one-task pattern, not the same one
  under a different name. Don't import the "ignore test" framing; there's no split to ignore
  here, and a later phase (`v4_t3_e1` or beyond) may reintroduce a real disjoint split per
  `HANDOFF.md`'s v1/v2 lesson ("pin a real disjoint split in the recipe if v4 does anything
  optimizer-driven").

### New, CCC-specific problems this session needs to actually solve

1. **Per-lane port-offsetting on CCC.** The Mac-side design settled on 2 local lanes with
   port-offset compose stacks. Decide the CCC equivalent: N dedicated hosts, each running its
   own full stack (own `parsec-live` + own 5-service compose project) on the *same* default
   ports (since each is a different host, no offset needed) — likely simpler than the Mac's
   single-host port-offset scheme. Confirm this reasoning against the actual scripts
   (`start-sims-v4.sh`/`start-parsec.sh`) before assuming ports don't need offsetting on CCC.
2. **Process lifecycle inside an LSF job.** A `bsub` job needs to bring up the compose stack +
   `parsec-live`, wait for both to be healthy (`curl localhost:<port>/healthz` per `HANDOFF.md`
   — remember podman reports `(unhealthy)` even when a container is fine, a known quirk not a
   real failure), run `run_one_task.py`, then tear the stack down cleanly on exit (including on
   a killed/failed job — don't leave a `parsec-live` process orphaned on a shared host).
3. **Podman on CCC for a docker-compose topology, not a single BenchFlow container.** Read
   `docs/how-to/ccc/CCC_PODMAN_SETUP.md`'s existing rootless-podman fixes, but validate them
   against this specific 5-service compose + separate uvicorn process combination — do not
   assume they transfer unchanged, per the design doc's own explicit caution.
4. **Where does `install_seeds.py`-style per-trial reseeding fit** in a CCC job — this needs to
   happen once per trial (per the adapter/`run_one_task.py` code), which is a very different
   cadence from a per-container skillsbench seed.

## Suggested first moves for this session

1. Read `HANDOFF.md` and the 2026-09-17 design doc in full (see above) before touching anything.
2. Ask the user about the 2026-09-21 doc gap and whether a 21-task sweep has already completed
   somewhere (local `_run/` on the Mac) — don't assume either way.
3. Read `docs/how-to/ccc/CCC_PODMAN_SETUP.md` (Batch/LSF mode section) fresh, and the parsec v4
   `README.md` (`rhdp-parsec/v4_2026-09-16/README.md` if reachable from this checkout, or ask
   the user for its path/content if it's Mac-local only) before writing any CCC-side script.
4. Run **one task by hand** end-to-end on one CCC host first (per `HANDOFF.md`'s own "suggested
   first move" #5 for the Mac side) — confirm the compose stack + `parsec-live` come up healthy,
   confirm cost/tracing actually reads real numbers, confirm `stop_at_reward` fires — before
   scaling to concurrent lanes or the full 21-task sweep.
5. Only after one task works cleanly on CCC, design the multi-host/multi-lane dispatch (mirroring
   `run_all_seven_parallel.sh`'s job-pool shape, per the design doc) and submit the 21-task sweep.
