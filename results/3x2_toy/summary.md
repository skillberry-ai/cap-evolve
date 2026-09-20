# A2p skill-merge pilot — cross-task skill merging, single-file collapse, and re-optimization

_Generated 2026-09-16 · 2 tasks (`energy-market-pricing`, `grid-dispatch-operator`) ·
10 arms · dedicated LSF host per job (CCC) · Sonnet-5/Opus-5 agent · worktree
`intake_skillbench_c7`, full narrative in `docs/specs/a2p_experiment_plan.md`._

**Status: all 10 arms complete.**

## What the experiment asks

`dc-power-flow`, `economic-dispatch`, and `power-flow-data` are three skills that
`energy-market-pricing` and `grid-dispatch-operator` both edited during their own
independent cap-evolve optimization runs — a conflicted-skill case per
`insights/SKILLS_TASKS_MAP.md` Table E. This pilot asks three related questions about that
conflict:

1. **Does a skill optimized for one task transfer to the other, zero-shot?**
2. **Can the two tasks' variants be merged into one package (or one single-file skill) that
   serves both, without a further optimizer pass?**
3. **If you optimize a merged/collapsed skill directly — jointly on both tasks, or
   independently per task — does that reach the same ceiling as optimizing each task's own
   three separate files, and does merging two such optimized mutations afterward lose
   anything?**

Every arm is either **zero-shot** (`zs`, `--max-iterations 0`, no optimizer touch after
whatever produced the seeded skill) or a **real optimization run** (`opt`,
`--max-iterations ≥ 1`).

## Results

**Section A — three separate skill files** (`dc-power-flow`, `economic-dispatch`,
`power-flow-data` kept as distinct `SKILL.md` packages)

| Arm | Description | Mode | energy-market-pricing | grid-dispatch-operator | Average |
|---|---|---|---:|---:|---:|
| 1 | Native seed — each task's own skills, before any optimization | zs | 0.0 | 0.0 | 0.0 |
| 3 | Native optimized — each task's own skills, after its own optimization run | opt | 0.9 | 1.0 | 0.95 |
| 4 | Cross-task transfer — the *other* task's optimized donor skills, no adaptation | zs | 0.7 | 0.8 | 0.75 |
| 5 | Merged bundle — both tasks' optimized donor skills unioned into 3 files, no further optimization | zs | 1.0 | 1.0 | 1.0 |
| 6 | Merged bundle, then jointly optimized further on both tasks | opt | 1.0 | 1.0 | 1.0 |

**Section B — single merged skill** (`power-system-optimization`, the three files
collapsed into one)

| Arm | Description | Mode | energy-market-pricing | grid-dispatch-operator | Average |
|---|---|---|---:|---:|---:|
| 2 | Pure seed-stage merge — collapse the three *never-optimized* seed files into one, no optimization at all | zs | 0.0 | 0.0 | 0.0 |
| 7 | Collapse the three *already per-task-optimized* donor files into one, no further optimization | zs | 0.9 | 1.0 | 0.95 |
| 8 | Start from the seed-merge (Arm 2) and optimize it jointly on both tasks | opt | 1.0 | 1.0 | 1.0 |
| 9 | Start from the seed-merge (Arm 2) and optimize it independently per task (two separate runs) | opt | 1.0 | 1.0 | 1.0 |
| 10 | Merge the two Arm-9 per-task mutations back into one file, score zero-shot, no further optimization | zs | 1.0 | 1.0 | 1.0 |

## Reading of all 10 arms

- **Collapsing three files into one, on its own, neither helps nor hurts.** Arm 2 (seed
  merge, no optimization) scores 0.0/0.0 — identical to Arm 1's native-seed floor. The two
  sections track each other arm-for-arm: 1≈2, 3≈9, 5≈7, 6≈8.
- **Every lift above the 0.0 floor comes from optimizer-added content reaching the skill —
  environment hardening, DC-model-fidelity guardrails, task-specific solver scripts — not
  from the act of merging or collapsing files.** This shows up identically whether the
  content arrives via cross-task transfer (Arm 4), a static merge of already-optimized
  donors (Arms 5, 7), a fresh optimization pass on the merged/collapsed file (Arms 6, 8, 9),
  or a second merge of two already-optimized mutations (Arm 10).
- **Merging never hurts once the donors are already optimized.** Arms 5, 7, and 10 each
  merge two donors that individually reach the per-task ceiling, and each merge preserves
  that ceiling (no regression from combining). Arm 2 is the control that shows merging
  *unoptimized* donors does not manufacture a lift on its own — the floor stays at 0.0.
- **Optimizing the single collapsed file directly (Arms 8, 9) reaches the same ceiling as
  optimizing the three separate files (Arm 3/6).** Both single-file optimization runs
  (jointly on both tasks, or independently per task) accepted their very first candidate at
  val 1.0 — the collapse does not make the optimizer's job harder.
- **The merge-of-optimized-mutations trick generalizes one level up the collapse.** Arm 5
  merges three separately-optimized *files*; Arm 10 merges two independently-optimized
  *mutations of the same already-collapsed file*. Both land at 1.0/1.0 with no regression.
- Sample size is 2 tasks in one domain (DC-OPF / power-system dispatch). Treat the above as
  directional for this skill family, not a general claim about all conflicted skills in
  Table E (`xlsx`'s 6-task conflict, in particular, already shows a donor variant that
  actively *hurts* a receiving task — see `results/transfer-eval-8fold/summary.md` — so the
  "merging never hurts" reading above is specific to this DC-OPF skill family, not universal).

## Methodological notes

- Every zero-shot arm (`zs`) reports `test_delta: 0.0` and `best_id: "seed"` by
  construction — with `--max-iterations 0` there is only one artifact to evaluate, so
  cap-evolve trivially compares it against itself. The real comparison is always against a
  *different* arm's score, read from this table, not from that run's own delta.
- The `opt` arms (3, 6, 8, 9) each accepted their first optimizer candidate at val 1.0 and
  were killed immediately after (exact job ID, per the "kill a saturated baseline" rule) —
  once val hits the ceiling there is no room left for the optimizer to improve, so a further
  iteration only spends budget. None of these runs completed a second iteration.
- Every run in this pilot hit the same `gate_warning`: "combined/paired SE is 0 (likely
  n_trials=1 or identical trials) — the significance gate cannot distinguish noise from
  signal and is falling back to STRICT (accept any Δ>0)." This is an expected artifact of
  these small-n (1–2 task) runs, not a defect — the STRICT fallback still requires a real
  positive delta to accept a candidate.

## Provenance

- Full narrative (job-by-job diffs, merge methodology, yaml specs, event logs) in
  `docs/specs/a2p_experiment_plan.md` §§1–11, worktree `intake_skillbench_c7`, branch
  `intake_skillbench_c7`, 2026-09-10 → 2026-09-16.
- Native seed/optimized figures (Arms 1, 3) read from `results/results.json`
  (`tasks[].seed`, `tasks[].best`).
- Machine-readable per-arm job IDs and scores: [`a2p_skill_merge_results.json`](a2p_skill_merge_results.json).

## Operational notes (CCC / LSF)

- **Kill a job the moment its accepted candidate hits val 1.0.** Arms 6/8/9's optimizer
  runs (jobs 778692, 795839, 795739, 795840) each saturated on iteration 1; each was killed
  by exact ID rather than let run its second budgeted iteration.
- **Check the job's own log/`events.jsonl`, not just `bjobs` STAT.** Every zero-shot arm's
  job (777815/777816/778690/778691/778790/778791/787174/787175/797395) finished cleanly
  (`Exit: 0`) but then sat in LSF `RUN` state indefinitely; each was killed by exact ID only
  after the log/`events.jsonl` confirmed a complete result.
- **One dedicated host per job (`bsub -m <host>`), `-n 1`, no `-W`.** Same constraints as
  `results/transfer-eval-8fold/summary.md` — `-W` risks killing a job mid-postprocessing
  after it already wrote a valid result; `-n 1` because these are single-eval or
  single/dual-task runs with no internal parallelism to spare extra slots for.
- Two rounds of LSF host trouble this pilot: `brsvs` advance-reservation blocking (Arms 2's
  jobs, first attempt) and raw host-slot saturation from unrelated users' jobs (Arms 8/9's
  jobs, first attempt) — both resolved the same way: kill the pending job by exact ID,
  re-derive genuinely free hosts via `bhosts`, resubmit.
