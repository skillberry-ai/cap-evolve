# Evidence: an optimizer win doesn't persist across runs — and a weaker optimizer model can't rediscover it in-budget

**Claim:** cap-evolve's per-run optimizer state (`JOURNAL.md`, accepted candidates) is
**not carried forward** between independent runs against the same shared skill. When a
run starts from the pre-improvement seed, the optimizer has to re-derive a fix from
scratch within its iteration budget — and if that fix took several iterations last time,
a fresh run can plateau at Δ=0 without ever reaching it, especially with a weaker
optimizer model. This looks like "the task regressed" or "the run is broken," but it is
neither: it's lost progress plus insufficient budget/capability to re-find it.

**Task:** SkillsBench `shock-analysis-demand` (category: finance-economics /
macroeconomic-analysis), shared `xlsx` skill-package capability.

## The headline numbers

| Run | Worktree | Optimizer model | Iterations | Seed val | Best val | Best candidate | Held-out test Δ |
|---|---|---|---|---|---|---|---|
| Prior | `intake_skillbench_c2`, `run_task_shock-analysis-demand_v2` | `claude-opus-4-8` | 4 | 0.0 | 0.9 | `cand_0004` | **+0.9** |
| Current | `intake_skillbench_c4`, `run_task_shock-analysis-demand_c4v1` | `claude-opus-4-6` | 6 | 0.0 | 0.0 | seed (no accepted candidate) | **+0.0** |

Source for the optimizer model per run — `capevolve.shock-analysis-demand.yaml`,
`optimizer_model:` line, captured verbatim in each run's folder here
(`c2-v2-prior-run/optimizer_model.txt`, `c4-current-run/optimizer_model.txt`).

Both runs start from val=0.0 — **that part is not a regression**, it's the same
un-improved seed both times (verified below). The regression is entirely in what each
run's optimizer accomplished with its iteration budget.

## What the prior run (c2-v2, Opus 4.8) actually discovered

Its own append-only `JOURNAL.md` (full copy: `c2-v2-prior-run/JOURNAL.md`) shows a clean
lever-switching sequence:

- **cand_0001** (prose: "fill templates in place, honor layout") — `REJECTED, Δ=+0.000`.
- **cand_0002** (read-only `audit.py` + a general formula-projection reference doc) —
  `REJECTED, Δ=+0.000`.
- **cand_0003** — switched levers from prose to code: shipped a brand-new script,
  `xlsx/scripts/build_shock_model.py` (261 lines — full copy in
  `c2-v2-prior-run/build_shock_model.py`), that **scaffolds the exact required workbook
  structure**: the 5 required sheets (`WEO_Data`, `SUT Calc`, `SUPPLY (38-38)-2024`,
  `USE (38-38)-2024`, `NA`) with the correct column layout, and every calculated cell
  written as a real Excel **formula** (not a hardcoded value). The journal entry records
  that the optimizer fetched the real verifier + template + oracle from GitHub and
  confirmed the scaffolder scores **7/7** against the actual grading logic before
  proposing it. — `ACCEPTED, val=0.400, Δ=+0.400`.
- **cand_0004** — diagnosed that reward was still flaky because the agent often didn't
  *run* the (already-verified-correct) scaffolder: "the 4 passing trials ran it; all 6
  failing trials did not." Fix was purely behavioral — a "START HERE" block making the
  scaffolder the mandatory first action for this task type, before any web-data
  collection — no change to the script itself. — `ACCEPTED, val=0.900, Δ=+0.500`.

`diffs/cand_0002-to-cand_0003.diff` and `diffs/cand_0003-to-cand_0004.diff` in this
bundle are the actual `xlsx/SKILL.md` + `scripts/build_shock_model.py` diffs between
those accepted commits, taken from the run's own git store
(`git log --oneline --stat`, full log in `c2-v2-prior-run/git-log.txt`).

**In short: the winning fix was a two-step discovery — (1) write a script that
scaffolds the exact graded structure, verified against the real grader, then (2) fix the
trigger so the agent reliably runs it — and it took 4 iterations to land.**

## What the current run (c4, Opus 4.6) tried instead

Its `JOURNAL.md` (full copy: `c4-current-run/JOURNAL.md`) ran all 6 of its iterations —
more than the prior run's 4 — and never wrote that scaffolder:

| Candidate | Lever tried | Result |
|---|---|---|
| cand_0001 | body prose: structure-first workflow, time-boxing, formula guidance, inspect script | `Δ=+0.000` |
| cand_0002 | executable helper scripts (`fetch_macro_data.py`, `inspect_xlsx.py`) + body prose | `Δ=+0.000` |
| cand_0003 | dedicated reference file with column conventions + scripts + body prominence | `Δ=+0.000` |
| cand_0004 | description-trigger timing + formula code patterns + `validate_formulas.py` | `Δ=+0.000` |
| cand_0005 | full body restructure (front-loaded workflow steps) + `validate_workbook.py` | `Δ=+0.000` |
| cand_0006 | combined description+body+reference+script | `Δ=+0.000` |

Every one of these is in the same category the prior run had already refuted at
cand_0001/cand_0002 (prose, reference docs, small helper/validator scripts) — none of
them is a structural scaffolder that *writes* the required sheets/formulas the way
`build_shock_model.py` does. Tellingly, the current run's own "focus next iteration"
notes flag exactly this gap and keep deferring it:

- after cand_0002: *"the lever to try next is a more complete workbook-scaffolding
  script that generates the full sheet structure from a JSON spec."*
- after cand_0003: *"the next lever is a full workbook scaffolding script that creates
  the complete sheet structure programmatically."*
- after cand_0004: *"if description doesn't trigger earlier, a scaffolding script that
  creates the full workbook structure might be needed."*
- after cand_0005: *"...a script-heavy approach (e.g., full workbook scaffolding) might
  be needed despite overfitting risk."*

It correctly identified the same lever the prior run used to win — four separate
times — but spent its whole 6-iteration budget on validators/helpers/prose instead of
committing to writing the scaffolder itself, and ran out before ever trying it.

## Confirming this isn't a harness bug: the seed never had the fix

If the prior run's accepted win had been merged back into the shared `xlsx` skill used
as every subsequent run's seed, the current run's seed val should already reflect it.
It doesn't (seed val=0.0 in both runs), and a direct check confirms why:
`diffs/c4-seed-vs-c2-winning-skill.diff` diffs the current run's actual seed
`xlsx/SKILL.md` (`c4-current-run/SKILL.md.seed`) against the prior run's winning
`cand_0004` `xlsx/SKILL.md` (`c2-v2-prior-run/SKILL.md.cand_0004`) — the "START HERE"
block and the macro-shock description clause are entirely absent from the seed, and
`find`-ing the seed's skill directory shows no `build_shock_model.py` at all
(`c4-current-run/` has no such script, because there is none in the seed to copy).

**Conclusion: the current run executed correctly and is not malfunctioning.** It is a
reproducible, legitimate negative result given (a) a from-scratch seed that doesn't
carry forward prior runs' accepted improvements, and (b) a run that — this time, with a
weaker optimizer model (`claude-opus-4-6` vs. the prior run's `claude-opus-4-8`) —
recognized the right lever repeatedly but never spent an iteration actually pulling it
before its 6-iteration budget ran out.

## Implications for the optimizer (why this belongs in evidence, not just a bug report)

1. **Cross-run knowledge is currently lost.** Every independent run against the same
   shared skill-package capability starts the optimizer from zero, even when a previous
   run already discovered and validated (against the real grader) a fix for the exact
   same failure cluster. A mechanism to seed a new run's `JOURNAL.md` — or the skill body
   itself — from a prior run's accepted state for the same capability would prevent this
   exact class of "regression."
2. **The optimizer can identify the right lever without pulling it.** Four consecutive
   "focus next iteration" notes named the fix, and the run still didn't attempt it before
   running out of budget. This suggests either the per-iteration lever-selection heuristic
   is too conservative about "script-heavy... despite overfitting risk," or budget
   allocation should weight later iterations toward the lever an entry has explicitly
   deferred more than once.
3. **Optimizer model strength is a real, comparable variable.** This is the first
   evidence bundle on this branch that isolates optimizer model as the varying factor
   (`claude-opus-4-8` → `claude-opus-4-6`, all else roughly comparable: same task, same
   shared skill lineage, same failure cluster, more iterations available to the weaker
   model). Worth deliberately re-running this exact task with `opus-4-6` given the prior
   run's `JOURNAL.md` as a documented target, to see whether it can execute the known fix
   when told the lever, versus discover it cold.

## Bundle contents

- `c2-v2-prior-run/` — `JOURNAL.md`, `report.md`, `state.json`, `git-log.txt`,
  `optimizer_model.txt`, the winning `build_shock_model.py` script, and the winning
  `cand_0004` `xlsx/SKILL.md`.
- `c4-current-run/` — `JOURNAL.md`, `report.md`, `state.json`, `optimizer_model.txt`,
  and the actual seed `xlsx/SKILL.md` this run started from.
- `diffs/cand_0002-to-cand_0003.diff` — the prior run's SKILL.md + new-script diff where
  the scaffolder was introduced (val 0.0 → 0.4).
- `diffs/cand_0003-to-cand_0004.diff` — the prior run's trigger-fix diff (val 0.4 → 0.9).
- `diffs/c4-seed-vs-c2-winning-skill.diff` — proof the current run's seed never received
  the prior run's accepted improvement.
