# parsec v4 task-by-task optimization (v4_t2_e1) — design

Written 2026-09-17. Companion to `docs/superpowers/specs/2026-09-09-parsec-v4-intake-design.md`
(the baseline-only intake design) — this doc picks up exactly where that one
left off and resolves its one deferred hard problem.

## Status of the arc so far

- **`v4_t1_e1`** (baseline / zero-shot): done. All 34 tasks in the corrected
  `rhdp-parsec/v4_2026-09-16` bundle, 3 trials each, run via the standalone
  `run_full34.py` sequential driver — **not** through cap-evolve; the
  2026-09-09 doc deliberately chose "baseline only, cap-evolve-shaped" over
  full integration. Results: `rhdp-parsec/v4_2026-09-16/_run/jobs/full34/progress.csv`.
  21 of the 34 tasks scored a 3-trial average below 1.0.
- **`v4_t2_e1`** (this doc): task-by-task optimization of those 21 tasks. This
  is the *first* real cap-evolve run for parsec v4 — the adapter, per-task
  projects, and candidate-injection path all need to be built, informed by
  the components the 2026-09-09 doc already designed (`harbor-tasks-v4/`,
  `start-sims-v4.sh`, `install_seeds.py` wiring) plus the injection mechanism
  below, which that doc explicitly left unsolved.
- **`v4_t3_e1`** (not yet designed): post-analysis / merge decision, informed
  by diffing the 21 mutations this phase produces.

## Why v1/v2's approach doesn't carry over to v4

`parsec-intake_v1` and `parsec-intake_v2` already ran real cap-evolve
optimization loops against parsec-shaped Harbor tasks (v1: 30
`traces_parsec-aap2-*` tasks; v2: 10 hand-authored tasks, one isolated
simulator per task). It's natural to ask why `v4_t2_e1` couldn't just reuse
that same intake/adapter pattern instead of ~24h of new build work
(`adapter.py`'s `apply()`/`live()`, the per-task scaffolder, the single-task
runner, the advisory lock, the pre-flight check). The answer is a difference
in what the *capability* is and where it runs, not a redesign choice made
against v1/v2 — this section exists so that difference doesn't have to be
re-derived from scratch by the next person who asks.

**v1/v2's capability was a file, injected into a container that dies.** The
capability under optimization was a `SKILL.md` package read by Harbor's
generic claude-code agent, running *inside* an ephemeral per-trial Harbor
container. cap-evolve's existing generic Harbor adapter template
(`templates/adapters/harbor/adapter.py`) already knew how to drop a
candidate's `SKILL.md` into that container at trial start — v1/v2 needed
almost no new adapter code because the injection point (a file the container
reads once at boot) and the isolation boundary (the container itself) were
both already solved problems.

**v4's capability is 8 live prompt files served by a standing process.**
`v4_t2_e1` optimizes parsec's own real, production-lineage multi-agent system
(orchestrator + 6 domain sub-agents), patched to redirect its tool calls at
the simulated backends. Per the delivered `v4_2026-09-16` package, this runs
as one long-lived host-side process (`uv run uvicorn src.app:app --host
127.0.0.1 --port 8000`) that Harbor's `ParsecAgent` POSTs HTTP requests to —
there is no per-trial container to inject a file into. The 2026-09-09 intake
design doc identified this as the blocking gap and deliberately scoped
itself to baseline-only, deferring "candidate injection into parsec's live
prompts" as explicitly out of scope. This doc's *deferred hard problem,
resolved* section above is that deferral finally being paid off: injection
turned out to mean overwriting `config/prompts/*.md` in the live clone
(picked up on the next request via the mtime-keyed cache in
`system_prompt.py`, no restart needed) — a mechanism that did not exist and
had to be designed and built, not a config toggle that was already there.

**The real tradeoff: isolation for free vs. avoided infra churn.** It's
tempting to assume the shared-process design was chosen because it makes
*scoping or merging* candidate mutations easier. It doesn't — if anything
it's the opposite. A disposable per-trial container gave isolation for
free: it just dies at the end of the trial, so nothing a candidate did
inside it can possibly leak into the next one. The shared-process design has
no such guarantee — one `parsec-live` clone and its 5 simulated-backend
containers are reused across every trial of every candidate for every one
of the 21 tasks — so isolation has to be hand-built. That's exactly what
`adapter.py`'s `live()` does: snapshot the 8 prompt files on entry, apply
the candidate, `yield`, then restore the snapshot in a `finally` — so a
crash mid-evaluation (a VPN drop, a machine sleep, a `KeyboardInterrupt`)
can't leave one candidate's mutant prompts serving the next trial
indefinitely. That hand-built restore step, and the advisory lock that
keeps two trials from ever overlapping on the one shared stack, are real
ongoing risk surface that the container-per-trial model structurally never
had.

What the shared-process design buys in exchange isn't easier merging — it's
avoiding repeated, expensive setup/teardown of a *heavyweight* real service
plus LLM-backed simulators (each simulated tool call takes the harness
30–60 seconds to synthesize, per the v4 README) on every single trial, when
the only thing that actually changes between candidates is prompt text, not
code or infrastructure. Trading free isolation for realism (the real parsec
codebase, not a stand-in agent) and fewer infra restarts is the actual
advantage — and it's inherited from the `v4_2026-09-16` benchmark package's
own architecture (delivered as a standalone, run-by-hand Harbor benchmark
with no cap-evolve integration of its own), not a decision made to move away
from v1/v2's model.

## Naming and experiment-ID scheme

`<dataset>_t<phase>_e<config>`:

- `t<phase>` — a monotonically increasing counter for the *lifecycle phase* of
  the overall experiment arc. `1` = baseline/zero-shot measurement, `2` =
  task-by-task optimization, `3` = post-merge evaluation, `4+` = whatever
  comes after. It never resets and never means "arm family."
- `e<config>` — an independent config-version tag (model, algorithm,
  hyperparameters) so the same phase can be rerun under different settings
  without an ID collision. `v4_t2_e1` is the first config tried for phase 2;
  a later `v4_t2_e2` would mean "same phase, different model/algorithm," not
  a new phase.

Modeled on the A2p skill-merge pilot's arm-table convention (one row per
arm/phase, one column per task) — see
`intake_skillbench_c7/docs/specs/a2p_experiment_plan.md` and its
`a2p_skill_merge_summary.md` for the precedent this borrows from.

## Directory-naming resolution

No renames. Concretely:

- `rhdp-parsec/v4_old/` (pre-fix, 2026-09-09 materials) and
  `rhdp-parsec/v4_2026-09-16/` (corrected, current) already disambiguate the
  two source trees; a bare `v4/` no longer exists. This is sufficient — see
  `[[reference-v4-experiment-layout]]`.
- The `parsec-intake_v4` cap-evolve worktree was checked directly
  (`find` + `git log`) and carries **no stale old-v4 build artifacts** — its
  only parsec-related commit is the 2026-09-09 docs-only design, which
  already refers to the corrected v4. There is nothing to move to a
  `parsec-intake_v4_old` directory.
- Renaming `v4_old`→`v3` was considered and rejected: there is no real "v3"
  benchmark generation between v2 and v4 — `v4_old` is a bad build of v4, not
  a distinct prior tier. Calling it v3 would manufacture a benchmark
  generation that never existed.
- Renaming to `v5` was considered and rejected (by the user, independently) —
  it would break alignment with JB's own `bench-v4`/`bench/v4` naming, which
  every task's `provenance.md` and the README cite directly.
- Going forward, confusion is prevented by tagging every new artifact path
  with its exact experiment ID (`v4_t2_e1/...`), not by renaming directories.
  New run/result directories under this phase should nest under a
  `v4_t2_e1` path segment (see *Per-task project layout* below) so "which
  experiment produced this" is answered by the path, not inferred from
  context.

## The deferred hard problem, resolved: candidate injection

The 2026-09-09 doc's stated blocker: v4's `ParsecAgent` POSTs to a **host-side**
parsec service (unlike v2's claude-code-agent-in-container model), so a
candidate has "nowhere to go" — injection would mean rewriting
`config/prompts/<agent>.md` in a live clone and restarting its uvicorn
process per candidate, "a mechanism that doesn't exist."

Direct inspection of `_run/parsec-live/src/agent/system_prompt.py` shows this
mechanism already exists, for free:

```python
def get_agent_prompt(agent_type: str) -> str:
    domain_path = _AGENT_PROMPT_FILES.get(agent_type)
    shared_mtime = _get_mtime(_SHARED_CONTEXT_PATH)
    domain_mtime = _get_mtime(domain_path)
    learnings_mtime = _get_mtime(_LEARNINGS_PATH)
    cached = _agent_prompt_cache.get(agent_type)
    if cached:
        cached_prompt, cached_shared_mt, cached_domain_mt, cached_learn_mt = cached
        if (cached_shared_mt == shared_mtime and cached_domain_mt == domain_mtime
                and cached_learn_mt == learnings_mtime):
            return cached_prompt
    # else: re-read from disk, rebuild, update cache
```

Called fresh on every request from `runner.py`, `orchestrator.py`,
`agents.py`, and `sdk_orchestrator.py` — not cached at process start. So:

- **Inject a candidate** = write the candidate's version of one or more of
  `config/prompts/*.md` to disk. Next request picks it up. No uvicorn
  restart.
- **Revert to seed** = `git checkout -- config/prompts/<file>.md` (the
  patched clone is git-clean on these files; only `orchestrator.py` and
  `tool_definitions.py` carry the unrelated sim-redirect patch).

This removes the single biggest reason the 2026-09-09 doc scoped itself to
baseline-only.

## The prompt surface: 8 files, not a monolith

`config/prompts/` holds:

| file | role | lines |
|---|---|---|
| `orchestrator.md` | routes to the 6 domain agents below | 245 |
| `shared_context.md` | prepended to all sub-agents (not the orchestrator) | 237 |
| `aap2_agent.md` | AAP2/Ansible jobs; also carries GitHub access | 521 |
| `babylon_agent.md` | Babylon catalog/provisioning; also carries GitHub access | 267 |
| `cost_agent.md` | cost queries; also covers Azure pool DB + GCP project inventory ("cloud" tasks) | 194 |
| `icinga_agent.md` | Icinga monitoring | 247 |
| `ocpv_agent.md` | OpenShift Virtualization | 128 |
| `security_agent.md` | security domain | 219 |

There is no dedicated cloud/github file — cloud tasks route through
`cost_agent.md`, and GitHub access lives inside whichever domain agent needs
it. Cross-referencing each task's `task.toml` `services=[...]` against
`orchestrator.md`'s own routing text lets a task's prompt footprint be
derived: almost always `orchestrator.md` + `shared_context.md` + one domain
file, occasionally two for cross-domain tasks (e.g.
`icinga-010-stuck-anarchysubjects` touches `icinga` + `github`).

Because these files are already disjoint on disk, most of the A2p pilot's
file-merge complexity (three-files-vs-one-collapsed-file, M1–M4 merge
methods) doesn't apply here by default — the only place a real merge
conflict *can* occur is in the 2–3 truly shared files
(`orchestrator.md`, `shared_context.md`, and `data/agent_learnings.md`, a
real but currently-empty parsec feature). Per the scope decision below, this
phase does not attempt to resolve that; it's deferred to `v4_t3_e1`.

## Phase-2 scope: pure task-by-task, no merge, no regression

For each of the 21 sub-1.0 tasks: an independent cap-evolve optimization run
with **train = val = test = {that task}**, candidate free to edit any of the
8 prompt files. No cross-task regression checking. No dependencies between
task runs. The only question phase 2 answers is: *can each task independently
reach reward 1.0?*

Explicitly deferred to later phases:

- Any regression check against the other 20 tasks.
- Any merge of the 21 resulting mutations.
- A held-out test split — with train=val=test all equal to the single task,
  a holdout is meaningless at this scope; skip it.

Only after all 21 runs complete does the next phase begin: diff the 21
mutations against the shared seed, see which files changed per task, and
decide *if and how* to merge — informed by the A2p pilot's four merge methods
(M1 mechanical union, M2 verified accumulation, M3 cap-evolve-as-merger, M4
concatenate-and-route) and its headline finding that merging itself doesn't
create or destroy value — only the optimizer's own added content does. That
analysis and decision is `v4_t3_e1`, out of scope for this doc.

## The 21 target tasks

`cloud-024-guid-to-account`, `cloud-026-gpu-abuse-triage`,
`cost-029-no-cost-rows-for-guid`, `cost-030-threshold-not-an-anomaly`,
`icinga-010-stuck-anarchysubjects`, `icinga-011-aap2-job-status-alert`,
`icinga-013-acknowledged-not-an-issue`, `icinga-014-check-script-path-moved`,
`platform-001-ee-entrypoint-rca`, `platform-002-collection-not-found-rca`,
`platform-003-tojson-dict-literal-rca`, `platform-004-events-then-config`,
`platform-005-wrong-owner-trap`, `platform-007-directory-path-fetch`,
`platform-008-log-does-not-say`, `platform-022-job-on-no-controller`,
`platform-023-splunk-guid-no-events`, `platform-031-helm-url-not-a-timeout`,
`platform-032-shared-secret-not-a-registry-outage`,
`platform-033-schema-change-not-the-oom`,
`platform-034-rate-limit-not-an-outage` — all 21 of the sub-1.0 tasks from
`v4_t1_e1`, per-task 3-trial average computed from `progress.csv`. The 4
tasks the earlier draft scope had called out as a "challenge tranche" are
included, per explicit instruction — no task is excluded from phase 2.

## Run parameters

- 5 trials per iteration, 3 iterations, per task.
- `stop_at_reward: 1.0` in each task's `capevolve.yaml` (equivalently
  `--stop-at-reward 1.0` on the CLI) — a genuine, first-class `Budget` field
  (`core/cap_evolve/rundir.py`), not something invented for this doc: added by
  `d1275b32a` / PR #415 ("Add stop_at_reward: stop optimizing once val reward
  hits the ceiling"), checked centrally in `budget_exhausted()`, fed by both
  the seed baseline eval and every accepted candidate's best val reward — so
  it fires before iteration 1 if the seed is already saturated, not only
  after an accept. The sealed test split still gets scored at finalize
  either way. Confirmed present on this worktree's own branch
  (`core/cap_evolve/{rundir,cli,dashboard}.py` all carry it) and merged to
  `origin/main`. This is the proper successor to
  `intake_skillbench_v2/ceiling_watchdog.sh` — that external poll-and-SIGTERM
  script was exactly the "manual bkill-on-saturation workaround" the PR's own
  commit message cites as the reason it added `stop_at_reward` as a
  first-class budget check instead; no external watchdog process is needed
  this phase. One pre-flight to do before the first real run: confirm
  whatever `cap-evolve` install actually executes v4_t2_e1's jobs is built
  from a checkout that includes `d1275b32a` (this worktree's `core/` does; a
  separately-installed `cap-evolve-core` package elsewhere might not — that's
  what made an earlier `--help` check on a stale install wrongly appear to
  show no such flag).
- No held-out test run (see *Phase-2 scope* above).
- Model assignment per existing convention: Opus 5 as optimizer, Sonnet 5 as
  evaluator/runtime agent.

## Per-task project layout

One cap-evolve project per task, mirroring `intake_skillbench_v2`'s
"dedicated folder per task" pattern, nested under the experiment ID:

```
parsec-intake_v4/.capevolve/v4_t2_e1/
├── common/
│   ├── adapters/               # the harbor adapter built for this phase (shared, not per-task)
│   └── optimizer/               # optimizer INSTRUCTIONS.md
├── project_cloud-024-guid-to-account/
│   ├── seed_capability/          # snapshot of the 8 prompt files as of v4_2026-09-16's patched clone
│   ├── capevolve.cloud-024-guid-to-account.yaml
│   ├── split_ids.json            # train = val = test = [this task only]
│   ├── adapters -> ../common/adapters
│   └── optimizer -> ../common/optimizer
├── project_cloud-026-gpu-abuse-triage/
├── ... (one dir per remaining task, 21 total)
```

Unlike `intake_skillbench_v2`'s per-task capability (a `SKILL.md` package per
task), the seed capability here is the shared 8-file prompt set — a task's
project starts from the *same* seed files as every other task's project; only
the optimization target (which task scores the run) differs.

## Execution mechanics and parallelism

**Key difference from the SkillsBench precedent.** `intake_skillbench_v2` and
`run_all_seven_parallel.sh` parallelize safely because BenchFlow gives each
SkillsBench task its own isolated Docker container — N tasks running at once
never share state. Bench-v4 does not have that property: per the v4 README,
the simulation harness is one `docker-compose` topology with five services on
**fixed** ports (8086 platform / 8087 github / 8088 icinga / 8089 cost / 8090
cloud), one `parsec-live` uvicorn process on port 8000, one shared
`PARSEC_SIM_TRACE` file, and one shared `skills-store` volume. Two tasks
run concurrently against this *same* stack would clobber each other's seeded
data and each other's injected candidate prompt files. `run_full34.py`
reflects this directly — it runs all 34 tasks strictly sequentially, by
construction, not by choice.

**What does parallelize.** Every port is env-overridable
(`<SERVICE>_MCP_URL`, `PARSEC_URL`), and the whole stack is just
docker-compose plus a Python process — nothing hardcodes the default ports
except as defaults. So K independent **lanes** can be stood up, each lane
being its own full stack: its own patched parsec clone + uvicorn process on
its own port, its own 5-service harness `docker-compose` project on an
offset port block, and its own trace file. K lanes give K-way task
parallelism; a job-pool dispatcher (same shape as `run_all_seven_parallel.sh`
— dispatch up to K at a time, reap finished PIDs, refill) round-robins the 21
per-task cap-evolve runs across the K lanes, one task active per lane at a
time.

**Decision: yes, parallel, and concretely 2 lanes.** This phase runs the 21
per-task cap-evolve jobs across **2 local lanes on the Mac**, not
sequentially — matching `run_all_seven_parallel.sh`'s own default
(`MAX_PAR=2`) for the same reason it chose that number: 2 lanes keeps
concurrent LLM-gateway load and simulation-harness load bounded to something
already validated, while still halving the wall-clock of a strictly serial
sweep. Mechanically: port-offset the existing `start-sims-v4.sh` /
`start-parsec.sh` scripts to produce a second full stack (its own patched
parsec clone + uvicorn process + 5-service harness `docker-compose` project,
all on an offset port block, per *What does parallelize* above), then a
job-pool dispatcher in the same shape as `run_all_seven_parallel.sh`
(dispatch up to 2 at a time, reap finished PIDs, refill) round-robins the 21
tasks across the 2 lanes. Going to 3+ lanes is not planned for this phase —
if the observed wall-clock with 2 lanes turns out to leave significant
headroom (LLM-gateway rate and harness latency, per *Local resource
watch-items* below, staying well under their limits), that's a decision for
a later `e2` config, not a mid-phase change here.

**Not CCC.** `CCC_PODMAN_SETUP.md`'s entire runbook (rootless-podman UID
workarounds, the LSF batch-mode lessons) was built and validated for
BenchFlow/SkillsBench specifically — it has never been exercised for
bench-v4's docker-compose-based harness or its host-side `parsec-live`
process, and porting it is new, unvalidated scope, not a drop-in reuse.
Given the user's own repeated preference this round for reducing moving
parts (task-by-task only, no regression, no merge, 2 lanes not N), CCC is
deferred to a later configuration/experiment regardless of what the 2-lane
local wall-clock turns out to be. If it's taken up later, the CCC doc's
operational rules remain directly applicable and worth carrying forward
as-is:
- kill a job the instant its accepted candidate hits reward 1.0, by exact
  job ID only (never a bulk `bkill`);
- poll the run's own log for a complete result, not `bjobs`/LSF `STAT` (a
  finished job can hang in `RUN` indefinitely in post-run teardown);
- one dedicated host per concurrent job (`-m <host>`, checked against
  `brsvs -w` for hidden reservations), no `-W` wall-clock limit.

**Local resource watch-items**, carried over from `intake_skillbench_v2`'s
own experience: LLM-gateway request-rate (2 lanes multiply concurrent calls
to both the simulation-synthesis model and the parsec/agent model) and the
simulation harness's own per-call latency (30–60s per simulated tool call,
per the v4 README) are more likely binding constraints than local CPU/RAM for
bench-v4's lighter (non-ML) task containers — watch these before assuming
container RAM is the ceiling.

## What's explicitly out of scope this phase

- Any cross-task regression checking or dependency between task runs.
- Any merge of the 21 resulting mutations (deferred to `v4_t3_e1`).
- A held-out test evaluation.
- Porting execution to CCC/LSF (deferred to a later configuration/experiment,
  regardless of the 2-lane local wall-clock outcome).
- Any directory rename or artifact move (per the *Directory-naming
  resolution* section — nothing needs to move).

## Open building blocks not yet built

This phase requires building, not just designing: the harbor adapter (fork of
the template, per the 2026-09-09 doc's already-sketched `adapters/adapter.py`
row, now updated to write candidate prompt files into a live clone rather
than assuming no-injection), the 21 per-task project directories, the
per-lane port-offset variants of `start-sims-v4.sh`/`start-parsec.sh`, and the
job-pool dispatcher script. None of this is started; this doc is the design
for it, not the implementation.
