# 3x2_toy pilot — cross-task skill merging, single-file collapse, and re-optimization

_Generated 2026-09-16, renamed 2026-09-20 · 2 tasks (`energy-market-pricing`, `grid-dispatch-operator`) ·
12 arms (10 run, 2 documented gaps) · dedicated LSF host per job (CCC) · Sonnet-5/Opus-5 agent · worktree
`intake_skillbench_c7`, full narrative in `docs/specs/3x2_toy_experiment_plan.md`._

> **Naming note:** this pilot was informally called "A2p" while in flight (a letter-code from
> `docs/specs/experiments_plan_v1.md`'s study-level lettering scheme). Renamed **3x2_toy** on
> 2026-09-20 to avoid colliding with that scheme now that arms are numbered per-section
> (`A1`-`A6`, `B1`-`B6`) — do not use "A2p" as a name going forward.

**Status: 10 of 12 arms complete; 2 gap arms identified but not yet run (see below).**

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

## Naming

Two structural sections, each with an identical 6-arm chain wherever data allows it:

- **`seed`** — native, never-optimized skill(s).
- **`tbt`** — task-by-task: an independent optimizer run per task.
- **`joint`** — a single optimizer run scoring both tasks together.
- **`merge`** — a static union of two already-produced artifacts, no optimizer call.
- **`cross`** — zero-shot hand-off of one task's donor skill to the other task, untouched.

Section **A = "three-skills"** (`dc-power-flow`, `economic-dispatch`, `power-flow-data` kept
as distinct `SKILL.md` packages). Section **B = "combo-skill"** (the three files collapsed
into one, `power-system-optimization`).

## Results

**Section A — three-skills**

| Arm | Name | Description | Mode | energy-market-pricing | grid-dispatch-operator | Average |
|---|---|---|---|---:|---:|---:|
| A1 | three-skills/seed | Native seed — before any optimization | zs | 0.0 | 0.0 | 0.0 |
| A2 | three-skills/tbt | Native optimized — each task's own skills, after its own optimization run | opt | 0.9 | 1.0 | 0.95 |
| A3 | three-skills/tbt-cross | Cross-task transfer — the *other* task's tbt-optimized donor skills, no adaptation | zs | 0.7 | 0.8 | 0.75 |
| A4 | three-skills/tbt-merge | Merged bundle — both tasks' tbt-optimized donor skills unioned into 3 files, no further optimization | zs | 1.0 | 1.0 | 1.0 |
| A5 | three-skills/tbt-merge-joint | Merged bundle (A4), then jointly optimized further on both tasks | opt | 1.0 | 1.0 | 1.0 |
| A6 | three-skills/joint | *(gap — not yet run)* Direct joint optimization of the native seed on both tasks, no tbt, no merge | opt | — | — | — |

**Section B — combo-skill**

| Arm | Name | Description | Mode | energy-market-pricing | grid-dispatch-operator | Average |
|---|---|---|---|---:|---:|---:|
| B1 | combo-skill/seed | Pure seed-stage merge — collapse the three *never-optimized* seed files into one, no optimization at all | zs | 0.0 | 0.0 | 0.0 |
| B2 | combo-skill/tbt | Start from the seed-merge (B1), optimize independently per task (two separate runs), not yet merged back | opt | 1.0 | 1.0 | 1.0 |
| B3 | combo-skill/tbt-merge _(lineage: via A2)_ | Collapse the three *already tbt-optimized* (A2) donor files into one, no further optimization | zs | 0.9 | 1.0 | 0.95 |
| B4 | combo-skill/tbt-merge _(lineage: via B2)_ | Merge the two B2 per-task mutations back into one file, score zero-shot, no further optimization | zs | 1.0 | 1.0 | 1.0 |
| B5 | combo-skill/tbt-merge-joint | *(gap — not yet run)* Take a tbt-merge result (B3/B4) and continue optimizing jointly on both tasks | opt | — | — | — |
| B6 | combo-skill/joint | Start from the seed-merge (B1) and optimize it jointly on both tasks | opt | 1.0 | 1.0 | 1.0 |

`B3` and `B4` share the name `combo-skill/tbt-merge` but come from different lineages (which
donors were merged) and score slightly differently (0.9/1.0 vs 1.0/1.0) — kept as two rows
rather than conflated into one.

## The two documented gaps

The two sections were each designed to mirror the other's 6-arm chain, but each is missing
exactly the cell the other section already has:

- **A6 (`three-skills/joint`)** has no run — Section A never optimized its native seed
  jointly on both tasks without a `tbt` pass first.
- **B5 (`combo-skill/tbt-merge-joint`)** has no run — Section B never continued optimizing a
  `tbt-merge` result jointly.

Both are documented here as named, scoped, not-yet-run arms rather than left as unlabeled
holes. Machine-readable record: [`results.json`](results.json) (`status: "not_run"`).

## Reading of the 10 run arms

- **Collapsing three files into one, on its own, neither helps nor hurts.** B1 (seed merge,
  no optimization) scores 0.0/0.0 — identical to A1's native-seed floor. The two sections
  track each other arm-for-arm: A1≈B1, A2≈B2, A4≈B3, A5≈B6.
- **Every lift above the 0.0 floor comes from optimizer-added content reaching the skill —
  environment hardening, DC-model-fidelity guardrails, task-specific solver scripts — not
  from the act of merging or collapsing files.** This shows up identically whether the
  content arrives via cross-task transfer (A3), a static merge of already-optimized donors
  (A4, B3), a fresh optimization pass on the merged/collapsed file (A5, B2, B6), or a second
  merge of two already-optimized mutations (B4).
- **Merging never hurts once the donors are already optimized.** A4, B3, and B4 each merge
  two donors that individually reach the per-task ceiling, and each merge preserves that
  ceiling (no regression from combining). B1 is the control that shows merging *unoptimized*
  donors does not manufacture a lift on its own — the floor stays at 0.0.
- **Optimizing the single collapsed file directly (B2, B6) reaches the same ceiling as
  optimizing the three separate files (A2/A5).** Both single-file optimization runs (jointly
  on both tasks, or independently per task) accepted their very first candidate at val 1.0 —
  the collapse does not make the optimizer's job harder.
- **The merge-of-optimized-mutations trick generalizes one level up the collapse.** A4 merges
  three separately-optimized *files*; B4 merges two independently-optimized *mutations of the
  same already-collapsed file*. Both land at 1.0/1.0 with no regression.
- **Joint vs. task-by-task optimizer cost/time does not follow one simple rule.** On the
  optimizer side, B6's single joint LLM call ($5.83, 20.3 min) cost *less* than either
  individual B2 run ($6.46/19.8 min and $9.46/23.5 min), not just less than their sum — this
  is directionally interesting but n=1 per arm, not statistically established. On the
  evaluation (runner) side, B6's joint eval (343s for 20 rollouts) was *slower* than the sum
  of B2's two separate evals (69s+29s=98s for the same 20 rollouts), which does match the
  intuition that scoring two tasks together costs more wall-clock than scoring them apart.
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
- The `opt` arms (A2, A5, B2, B6) each accepted their first optimizer candidate at val 1.0 and
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
  `docs/specs/3x2_toy_experiment_plan.md` §§1–11, worktree `intake_skillbench_c7`, branch
  `docs/a2p-skill-merge-results`, 2026-09-10 → 2026-09-16. That document predates the
  2026-09-20 rename and still uses the original "A2p" name and old global arm numbers
  (1–10) in its historical narrative and in literal artifact identifiers (project/yaml
  names containing `a2p_`) — see its naming-migration note for the old→new mapping.
- Native seed/optimized figures (A1, A2) read from `results/results.json`
  (`tasks[].seed`, `tasks[].best`).
- Machine-readable per-arm job IDs and scores: [`results.json`](results.json).

## Operational notes (CCC / LSF)

- **Kill a job the moment its accepted candidate hits val 1.0.** A5/B6/B2's optimizer runs
  (jobs 778692, 795839, 795739, 795840) each saturated on iteration 1; each was killed by
  exact ID rather than let run its second budgeted iteration.
- **Check the job's own log/`events.jsonl`, not just `bjobs` STAT.** Every zero-shot arm's
  job (777815/777816/778690/778691/778790/778791/787174/787175/797395) finished cleanly
  (`Exit: 0`) but then sat in LSF `RUN` state indefinitely; each was killed by exact ID only
  after the log/`events.jsonl` confirmed a complete result.
- **One dedicated host per job (`bsub -m <host>`), `-n 1`, no `-W`.** Same constraints as
  `results/transfer-eval-8fold/summary.md` — `-W` risks killing a job mid-postprocessing
  after it already wrote a valid result; `-n 1` because these are single-eval or
  single/dual-task runs with no internal parallelism to spare extra slots for.
- Two rounds of LSF host trouble this pilot: `brsvs` advance-reservation blocking (B1's
  jobs, first attempt) and raw host-slot saturation from unrelated users' jobs (B6/B2's
  jobs, first attempt) — both resolved the same way: kill the pending job by exact ID,
  re-derive genuinely free hosts via `bhosts`, resubmit.
