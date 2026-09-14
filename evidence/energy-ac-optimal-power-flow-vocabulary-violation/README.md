# Evidence: the optimizer invented a skill outside the seed vocabulary, and the gate accepted it

**Claim:** cap-evolve's skill-package optimizer is **not constrained to a fixed skill
vocabulary**. Nothing in `skill-package/scripts/abstract.py` refuses an edit that creates
a brand-new top-level sub-package, so the optimizer can widen a capability from N skills
to N+1 skills between iterations. On SkillsBench `energy-ac-optimal-power-flow` it did
exactly that — added a `fuzzy-match/` skill that has nothing to do with AC optimal power
flow — the significance gate accepted the candidate on its val number, and the run's final
scored number came out **0.0 against the seed's 0.4** (Δ = **−0.4**).

**Run:** `intake_skillbench_c2`, run dir
`.capevolve/run_task_energy-ac-optimal-power-flow_v1_CORRUPTED_batch3/`
(campaign: SkillsBench task-by-task, c2/c3/c4 worktrees). 4 iterations, optimizer spend
$13.44 / 178,662 tokens (`c2-run/state.json`).

## The vocabulary violation, in the run's own files

The task's seed capability has exactly **three** sub-packages
(`c2-run/seed-vs-candidates.txt`, verbatim listings of both
`.capevolve/project_energy-ac-optimal-power-flow/seed_capability/` and the run's own
`candidates/seed/`):

    ac-branch-pi-model  casadi-ipopt-nlp  power-flow-data

What each candidate actually shipped:

| candidate | top-level sub-packages | gate | val | Δ |
|---|---|---|---|---|
| `seed` | ac-branch-pi-model, casadi-ipopt-nlp, power-flow-data | — | 0.400 | — |
| `cand_0001` | *(same three)* | ACCEPT | 0.500 | +0.100 |
| `cand_0002` | + **fuzzy-match**, **pdf**, **xlsx** | reject | 0.300 | −0.200 |
| `cand_0003` | + **fuzzy-match** | **ACCEPT** | 0.900 | **+0.400** |
| `cand_0004` | + **fuzzy-match** (+ `scripts/nullify_unresolved_keys.py`) | reject | 0.800 | −0.100 |

(`c2-run/git-log.txt` — the run's own commit log — records the same five states.)

`cand_0003/fuzzy-match/` is **not** an edit to an existing skill. It is a whole new skill
package with its own frontmatter and 75-line body (`c2-run/cand_0003/fuzzy-match/SKILL.md`,
sha256 `110abc8b…`), whose description is:

> "Reconcile transactional records (invoices, transactions, line items) against
> authoritative reference tables — approved-vendor lists, purchase-order/order registers,
> customer masters … Use when detecting invoice or payment fraud …"

`cand_0004` then grew it further, adding executable code inside the invented skill
(`c2-run/cand_0004/fuzzy-match/scripts/nullify_unresolved_keys.py`) — so the new
sub-package was not a one-off text file but a lineage the optimizer kept building on.

The optimizer states plainly that it is adding new skills. From `c2-run/JOURNAL.md`:

- cand_0002: *"NEW `pdf/`, `xlsx/`, `fuzzy-match/` — copied the canonical shared office
  skills into the candidate."* and *"`fuzzy-match/SKILL.md` — added 'Reconciling records
  against reference tables'…"*
- cand_0003 (the accepted one): *"surgical, single tightly-scoped fuzzy-match
  reconciliation skill … WITHOUT the pdf package that sank cand_0002"*, *"NEW
  `fuzzy-match/SKILL.md` (single skill)"*.
- cand_0004: *"NEW SCRIPT `fuzzy-match/scripts/nullify_unresolved_keys.py`"*.

Its `PROCESS.md` for the accepted iteration (`c2-run/cand_0003/PROCESS.md`) even labels the
change class **"NEW SKILL (description + body)"** in its own change table. No refusal was
recorded anywhere — the edit simply landed.

## Why nothing stopped it (`abstract.py`)

Two mechanisms combine:

1. `_subpackages(capability_dir)` (line ~150) derives the skill vocabulary **from whatever
   is on disk right now**: *"Immediate sub-directories that are themselves skill packages
   (contain SKILL.md)"*. It is a discovery function, not a check against a declared set.
   So the moment `fuzzy-match/SKILL.md` exists, `fuzzy-match` **is** a member of the
   capability, and `validate()` happily validates it as one more sub-package.
2. `apply()` (line ~234) checks only three things per edit: path containment (no `../`),
   the edit *kind* against `policy.json`'s `allow` list, and — for a file that doesn't yet
   exist — that `"add"` is allowed:

       if not exists and "add" not in allow:
           refuse(e, f"creating '{rel}' needs the 'add' action")

   There is no check on *where* the new path sits. `DEFAULT_POLICY` allows `add`, and this
   run had **no `policy.json` anywhere** (verified: `find … -name policy.json` returns
   nothing), so it ran on the default. `add`-ing `fuzzy-match/SKILL.md` was indistinguishable
   to `apply()` from `add`-ing `ac-branch-pi-model/reference/notes.md`.

Note that the existing knob is too coarse to fix this: dropping `"add"` from the policy
would also forbid adding a new reference doc or script *inside* an existing skill — which
is legitimate, in-vocabulary work (cand_0001's accepted win was exactly that: a new
`ac-branch-pi-model/scripts/build_report.py`). A fixed-vocabulary invariant therefore has
to be **path-shaped**, not action-shaped: refuse an `add` whose relative path introduces a
new first path segment (equivalently, whose write would change the set returned by
`_subpackages()`), while leaving adds under an existing sub-package alone.

## What the gate actually did — weaker than "accepted on val"

`c2-run/events.jsonl` shows the paired significance gate never ran a significance test at
all. On **every** iteration it emitted:

> `gate_warning` … *"combined/paired SE is 0 (likely n_trials=1 or identical trials) — the
> significance gate cannot distinguish noise from signal and is falling back to STRICT
> (accept any Δ>0)."* (`context: n=1`)

and accepted cand_0003 with reason *"paired Δ̄=+0.4000 > 0 (SE=0 → STRICT fallback,
warned; n=1)"*. So the out-of-vocabulary skill was admitted by an **any-positive-delta**
rule, on a task whose seed val of 0.4 came from `[1,1,0,0,1,0,1,0,0,0]` across 10 trials
with 3 of them errored on infrastructure (`c2-run/baseline.json`) — i.e. noise of the same
magnitude as the Δ that let it in.

## Honest scoping of the "test collapsed" number

`c2-run/report.md` reports the headline:

    - Best candidate: `cand_0003`
    - Baseline val: 0.4
    - **Held-out test (optimized skills): 0.0**
    - Held-out test (baseline `seed` skills): 0.4
    - **Test improvement (optimized − baseline): -0.4**

**But `report.md`'s claim that this is a "sealed split … held-out tasks the optimizer never
saw" is wrong for this run, and the harness knew it.** `c2-run/splits.json` puts the same
single task in all three splits, and the very first line of `c2-run/events.jsonl` is:

> `splits_warning`: *"test overlaps train/val (no-holdout fit) — the test number is NOT held
> out; report it as a fit metric"*

So the correct reading is **not** "textbook generalization failure on unseen tasks." It is:
the champion the gate selected on val=0.9 re-scored **0.0** on a fresh 10-trial draw of the
*same* task, while the untouched seed re-scored **0.4** on its own fresh draw. That is
still a damning result for the accepted candidate — a 0.9 → 0.0 swing on identical task
content means the val 0.9 was not a property of the skills — but it is best described as
**gate overfitting to a noisy val draw**, not held-out-set overfitting. The vocabulary
violation is the *mechanism* that made such a large spurious swing available: the optimizer
was optimizing a skill (`fuzzy-match`) that is irrelevant to the task under test, so its
apparent +0.4 could only ever have been draw noise.

## Open question 1: what does `CORRUPTED_batch3` refer to?

The directory is named `…_v1_CORRUPTED_batch3`, so some earlier session flagged this batch
before this investigation. Whether the flag was raised *for* the new-skill injection is
unverified — but there is a separate, independently verifiable defect in the same run that
is a much better fit for the label, and it also explains *why* the optimizer reached for
`fuzzy-match` in the first place:

**The trial trajectories are mislabelled.** Every trial file is named and tagged
`energy-ac-optimal-power-flow`, but the prompts inside belong to several different
SkillsBench tasks. From `trial-mislabelling/trial-prompts.txt` (generated by reading
`work/cand_0003/trajectories/energy-ac-optimal-power-flow__cand_0001__t*.json` and printing
each trial's `input`, `rollout.task_id`, and first user message):

| trial | `task_id` says | prompt actually is |
|---|---|---|
| t0–t4 | energy-ac-optimal-power-flow | ACOPF ("As an operator-planner in an Independent System Operator…") |
| t5, t8 | energy-ac-optimal-power-flow | **HR employee-record diff** ("identify differences between its old employee records and the current database … `/root/employ…`") |
| t6 | energy-ac-optimal-power-flow | **PDF edit/form-fill** ("You are given a `PDF` file at `/root/input/input.pdf`…") |
| t7 | energy-ac-optimal-power-flow | **court-form fill** ("Fill the California Small Claims Court form at `/root/sc100-blank.pdf`…") |
| t9 | energy-ac-optimal-power-flow | **invoice-fraud detection** ("analyze the following files to find any potential invoice fraud … `/root/vendors.xlsx`, `/root/purchase_orders.csv`") |

Only 5 of the 10 "trials" of this task were this task. The other 5 were four unrelated
office tasks.

The optimizer diagnosed this itself, correctly, in `c2-run/cand_0003/PROCESS.md`:

> *"## Key finding: the val 'task' is a MIXED pool, not one task — The 10 trials named
> `energy-ac-optimal-power-flow` are actually different SkillsBench tasks: t0,t1,t2,t3,t4 =
> the real ACOPF task; t5,t8 = employee-record diff; t6,t7 = PDF form-fill; t9 =
> invoice-fraud-detection."*

Given that pool, adding `fuzzy-match` was a *rational* response to the (corrupted) evidence
in front of it: t9 was the one genuine content failure it could address. This makes the
finding sharper rather than weaker — **a data-integrity bug upstream propagated into a
permanent, out-of-scope widening of the capability's skill set, precisely because no
vocabulary invariant existed to stop it.** A fixed-vocabulary constraint would have
contained the blast radius of the mislabelling bug to "no accepted candidate," instead of
"champion selected on an unrelated skill."

All six `*_CORRUPTED_batch3` run dirs in `intake_skillbench_c2` show the same cross-task
contamination in their journals (each run's `rollouts/` contain only its own task id, yet
each journal reasons about other tasks' content), so the corruption is a property of the
batch, not of this task. But **only this run had a new-skill candidate become champion**:

| run (`*_CORRUPTED_batch3`) | seed vocabulary | out-of-vocabulary sub-package in any candidate | became champion? |
|---|---|---|---|
| energy-ac-optimal-power-flow | ac-branch-pi-model, casadi-ipopt-nlp, power-flow-data | `fuzzy-match` (cand_0002/3/4), `pdf`+`xlsx` (cand_0002) | **YES — cand_0003** |
| simpo-code-reproduction | nlp-research-repo-package-installment, pdf | `fuzzy-match` (cand_0003) | no (see below) |
| shock-analysis-supply | xlsx | `pdf` (cand_0004) | no (rejected, Δ −0.100) |
| energy-market-pricing | dc-power-flow, economic-dispatch, locational-marginal-prices, power-flow-data | none | — |
| reserves-at-risk-calc | xlsx | none | — |
| shock-analysis-demand | xlsx | none | — |

## Open question 2: `simpo-code-reproduction` is a second occurrence — and it was a near miss

Confirmed. `run_task_simpo-code-reproduction_v1_CORRUPTED_batch3` has a seed vocabulary of
`{nlp-research-repo-package-installment, pdf}` and its `cand_0003` ships a third
sub-package, `fuzzy-match/SKILL.md` (153 lines, sha256 `9996d842…`, copied here under
`simpo-second-occurrence/`). Its journal is explicit that this is a cross-task port:

> *"ADD `fuzzy-match/SKILL.md` (new skill in my candidate) = verbatim port of the
> invoice-fraud run's **ACCEPTED** cand_0002 fuzzy-match skill"*

and, on the same mislabelling defect:

> *"t9 … its `task_id`/`input` say `simpo-code-reproduction` but its entire 46-step trace is
> an INVOICE-FRAUD task (invoices.pdf/vendors.xlsx/fraud_report.json) … The agent was fed
> the wrong prompt."*

The important detail: `cand_0003` was rejected with **Δ = +0.000** (`git log`:
`8d5ec7a iter 3: reject candidate cand_0003 (val 0.900, Δ +0.000)`) — i.e. it was turned
away by the STRICT fallback's *strict* inequality, **not** by any vocabulary rule. Had that
noisy draw landed one trial higher, the same violation would have been accepted here too.
Two runs out of six proposed an out-of-vocabulary skill; one was accepted; the other missed
by a rounding-level margin.

## Why this belongs in evidence

There is an ongoing effort to constrain the optimizer to a **fixed vocabulary** — edit
prose/tools/references inside existing skills; never create or delete a skill. This bundle
is the empirical justification, not a hypothetical:

1. **The gap is real and reachable.** `apply()` + `_subpackages()` place no vocabulary
   constraint; the default policy allows `add`; the optimizer took the opening on its own
   initiative, twice, without any prompt asking it to.
2. **The gate cannot catch it.** Skill-set widening is invisible to a scalar-reward gate.
   Here the gate had degenerated to "accept any Δ>0", and the accepted Δ (+0.4) was
   indistinguishable from the noise floor of a task with 3/10 infra-errored trials.
3. **The consequence was a champion built on an irrelevant skill.** val 0.9 → re-scored
   0.0 versus the untouched seed's 0.4. Whatever the split semantics, the selected artifact
   was worse than doing nothing.
4. **It converts upstream data bugs into permanent capability drift.** The mislabelled-trial
   defect could only produce an out-of-scope skill *because* out-of-scope skills were
   creatable. The invariant is a containment boundary for classes of bug we haven't found yet.

Suggested shape of the fix (not implemented here — this bundle is documentation only):
refuse in `apply()` any `add` whose relative path's first segment is not already a member of
`_subpackages()` (and any `remove` that would empty one), snapshotting the vocabulary at run
start; surface it as a `refused` entry so the optimizer sees the boundary and re-plans.

## Bundle contents

- `c2-run/` — the full run's `JOURNAL.md`, `report.md`, `state.json`, `splits.json`,
  `events.jsonl` (the `splits_warning` + all four `gate_warning`s + the `finalize` event),
  `baseline.json` (per-trial rewards and the infra-noise feedback), and `git-log.txt`.
- `c2-run/seed-vs-candidates.txt` — verbatim `ls` of the seed capability, the run's
  `candidates/seed/`, and every candidate's top-level sub-packages. The primary proof.
- `c2-run/cand_0003/fuzzy-match/SKILL.md` — the invented skill, exactly as accepted.
- `c2-run/cand_0003/PROCESS.md` — the accepted iteration's own change table (labels itself
  "NEW SKILL") and its "the val 'task' is a MIXED pool" finding.
- `c2-run/cand_0004/fuzzy-match/` — the next iteration's expansion of the invented skill,
  including the bundled `scripts/nullify_unresolved_keys.py`.
- `trial-mislabelling/trial-prompts.txt` — per-trial `task_id` vs. actual prompt for all 10
  trials, the evidence for open question 1.
- `simpo-second-occurrence/` — the second run's `JOURNAL.md`, `report.md`, `state.json`,
  `git-log.txt`, `seed-vs-candidates.txt`, and its own out-of-vocabulary
  `fuzzy-match/SKILL.md`.
