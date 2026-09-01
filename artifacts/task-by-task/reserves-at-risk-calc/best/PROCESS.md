# PROCESS — cand_0004 (parent: cand_0003, ACCEPTED val=0.800)

Single-task run (train==val==test==["reserves-at-risk-calc"], 10 trials). Only the
`xlsx` skill is deployed (no docx/pptx/pdf exist). Blast radius across tasks is ZERO —
no other task can regress from an xlsx edit; the only axis is trial-to-trial variance.

## The signal this iteration (from `./trajectories/`)
cand_0003 scores 0.800 = **8/10 trials pass**. I read every trial's `reward` and whether
it ran the solver:

| trial | reward | ran rar_solver | outcome |
| --- | --- | --- | --- |
| t0,t1,t2,t3,t4,t5,t7,t8 | 1.0 | yes | PASS |
| t6 | 0.0 | **no** | hand-rolled a COMPLETE workbook but with WRONG conventions (used `NORM.S.INV`→Z=1.6449, not 1.65); download itself worked. Verifier failed step1/2/3. |
| t9 | 0.0 | **no** | hand-rolled; IMF download rabbit-hole (imf.org 403s, datahub, Wayback OLE2 .xls), **wall-clock timeout at 600s** before writing anything. |

**Every trial that ran the solver passed (8/8). Both failures share ONE root cause: the
agent never invoked the xlsx skill / never ran the solver** (grep of t6, t9 shows ZERO
mentions of `rar_solver`, `SKILL.md`, `skills/`, `xlsx/`). t6 said "invoke the xlsx skill"
three times but never actually launched it; t9 never considered it. Because the skill body
is only loaded on invocation, the SKILL.md conventions/download-recipe never reach these
agents — the ONLY channel that reaches a non-invoking agent is the frontmatter `description`.
Diagnosed the two large failing traces with parallel read-only `Explore` subagents; the 8
short passing traces were classified by direct grep for `rar_solver` + `reward`.

## Ranked issue list (clusters by leverage; all one task)
| rank | cluster | trials | root cause | tag | edit class |
| --- | --- | --- | --- | --- | --- |
| 1 | Skill never invoked → agent hand-rolls (wrong conventions t6, or download-timeout t9) | t6, t9 (2/10) | The `description` didn't make the agent actually launch the skill for this task's phrasing, so the solver + conventions never load. Description is the only lever that reaches a non-invoking agent. | BEHAVIORAL (trigger) | DESCRIPTION |
| 2 | Solver leaves a stray `#VALUE!` at `Gold price!C2` | t0 (had to hand-fix); latent for every solver run | The gold loop wrote `C2 = LN(B2/B1)*100` for the FIRST priced row, but B1 is the text header → `#VALUE!`. A less careful agent that runs the solver but doesn't hand-fix C2 fails `test_no_errors`. | CAPABILITY-GAP (script defect) | SCRIPT |
| 3 | `python scripts/…` → exit 127 (`python` absent) | t0 (recovered after a wasted turn) | The RaR-section examples used bare `python`; the sandbox only has `python3`, costing a probe turn on a 600s-budget task. | KNOWLEDGE | BODY (RaR section only) |

## Changes kept this iteration (all inside `xlsx/`)
| cluster | class | file | what & why it generalizes | blast radius |
| --- | --- | --- | --- | --- |
| 1 | DESCRIPTION | `xlsx/SKILL.md` frontmatter | Front-loaded the RaR/IMF use-case: the opening sentence now names "downloading market/commodity price data into a template workbook to compute volatility and risk metrics", and the enumerated list leads with (1) "downloading IMF gold or commodity price data … gold-price volatility … Reserves-at-Risk (RaR) as a percent of total reserves (a bundled solver script does this end to end)". All generic clauses (create / read / modify-preserving-formulas / analysis / recalc) retained as (2)–(6). Puts the task's own vocabulary at the FRONT of the trigger so the model is more likely to actually launch the skill (and thus load the solver) instead of hand-rolling. Third person, no all-caps. | Additive/reorder; does not remove any generic trigger. Cannot make xlsx fire for docx/pdf/pptx tasks (clearly spreadsheet-scoped). For held-out generic xlsx tasks the skill still triggers. 786 chars (< 1024). |
| 2 | SCRIPT | `xlsx/scripts/rar_solver.py` | Log-return loop now writes col C only when the PREVIOUS row is itself priced (tracked via `prev_priced`), so the first priced row no longer emits `=LN(B{r}/B{r-1})*100` against the text header. Removed the now-redundant hard-coded `C3` write. General fix (no hardcoded row index). | **Verified byte-identical output except C2**: diffed all cells across all sheets between pre/post-fix outputs → 0 differences other than C2 (`#VALUE!`→blank). No STDEV range includes C2 (3m vol starts at C3), so no Answer value moves; it only removes the stray error `test_no_errors` checks. |
| 3 | BODY | `xlsx/SKILL.md` (RaR section) | Changed the solver invocation example from `python scripts/rar_solver.py` to `python3 …` with a note that bare `python` may be absent (exit 127). | Additive; scoped to the RaR section only. Generic body examples left untouched (used by passing paths). |

## VERIFY-THE-FIX
- **Edit 1 (description):** t6/t9 both bypassed the skill; t9's prompt opens "download global
  commodity excel database from https://www.imf.org … extract gold price … RaR". The reordered
  description front-loads exactly these tokens (download, IMF gold/commodity price, gold-price
  volatility, Reserves-at-Risk), improving the odds the agent actually launches the skill and
  loads the solver. Only xlsx is deployed → no other task's skill selection is disturbed.
- **Edit 2 (script):** ran the solver on the real cached `/tmp/test-rar.xlsx`. Pre-fix output
  had `C2 = =LN(B2/B1)*100` (B1 = "Gold, … London 3 PM fixed price, US$ per troy ounce" → the
  `Gold price!C2` `#VALUE!` t0 reported). Post-fix `C2` is blank and a full cell-by-cell diff
  vs pre-fix shows **0 differences elsewhere**; Step-1 still 4.813323 / 3.259073 / 16.67384;
  9 Step-2 / 7 Step-3 / gold rows→430 unchanged. Ties to `test_no_errors` (stray error gone
  without manual intervention) and cannot regress step1/2/3.
- **Edit 3 (body):** t0's trace shows `python … → exit 127 (python: command not found)` then a
  `python3` probe; the example now uses `python3` directly, removing that wasted turn on a
  budget-tight task. Scoped to the RaR block.
- **Package validity:** frontmatter intact; `ast.parse` on the solver OK; description 786 chars
  (< 1024); body link `scripts/rar_solver.py` resolves; no references/ dir; body within budget.

## Why this is not a resubmit of a rejected edit
Built on cand_0003 (ACCEPTED, 0.800) and cand_0002 (ACCEPTED) — kept the verified solver, the
top-of-body conventions, the download recipe, and the URL fallbacks verbatim. Did NOT re-try
cand_0001's approach (REJECTED: unverified solver, no trigger). The description edit is a
REORDER/front-load of cand_0003's already-accepted RaR clause, not a new speculative trigger;
the script fix is a newly-diagnosed defect (C2 #VALUE!) not previously touched. Nothing here
re-introduces a change any LEDGER row shows broke a task.

## Process & features used
- Parallel read-only `Explore` subagents on the two large failing traces (t6, t9); direct grep
  classification of the 8 short passing traces. Verified the script fix by running the solver
  on the real cached input and diffing outputs cell-by-cell.

## Deliberately skipped
- No docx/pptx/pdf edits — those skills don't exist here and no task uses them.
- Did NOT try to cram conventions into the description (against authoring rules / over-trigger)
  — the body already carries them for invoking agents; the only reachable lever for a
  non-invoking agent is the trigger itself.
- Did not alter the verified Z=1.65 / RaR×100 / country-selection conventions — correct; every
  solver-run passed with them.
- Did not rewrite the generic body `python` examples (blast radius onto passing paths); scoped
  the python3 fix to the RaR section only.
