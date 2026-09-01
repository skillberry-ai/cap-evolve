# PROCESS — what I did this iteration (explainability; REQUIRED)

## Honest state of the trajectories
The ONLY editable skills here are `lean4-theorem-proving/` and `lean4-memories/` (the docx/pptx/xlsx/pdf
names in the generic template do not exist in this candidate). The single val task is `lean4-proof`
(prove `S n ≤ 2` for `S 0 = 1, S (n+1) = S n + 1/2^(n+1)`), run over 10 trials.

Per-trial result: **9/10 trials PASS with reward 1.0** (all 4 verifier tests green). The one failing
trial (`t0`) has reward 0.0 with error **"bench eval run timed out after 2400s"** and feedback that
explicitly says: *"Uncontrollable noise, not a skill defect; do not optimize against it."* Mean = 0.90.

So there is **no failing verifier assertion / no wrong-proof cluster** to fix. The proof-writing path
already works every content trial. The only realistic, generalizing lever on the flaky-timeout is to
**reduce the agent's wall-clock / wasted work** so a run is less likely to brush the 2400s wall — done
WITHOUT changing the proof the agent produces.

## Ranked issue list
| rank | cluster | tasks | shared root cause | tag | change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Wasted environment exploration inflates run time | lean4-proof (flaky t0) | SKILL never tells the agent to orient to the project (read imports/lakefile) or to use the fast single-file typecheck loop; traces wander (t4=17, t5=12 exec calls, comparing testbed/baseline trees, scratch `/tmp` compiles) | BEHAVIORAL (efficiency) | BODY (additive) |
| 2 | Phantom/broken infrastructure references | all trials (hazard) | SKILL advertises 10/7 slash commands, 19/16 "automation scripts", a `lean4-proof-repair` Haiku/Sonnet agent, and links `../../COMMANDS.md` + `../../scripts/README.md` — **none exist** in this deployment; `../../` also violates the one-level-references rule | CAPABILITY-GAP / validity | REFERENCES (delete dead) |

## Changes made this iteration (all in `lean4-theorem-proving/SKILL.md`)
| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | BODY (additive) | SKILL.md "Orient First, Then Use a Fast Inner Loop" | New section: (a) read the file's imports + lakefile/toolchain before proving — don't assume full Mathlib (many projects vendor a limited custom library); (b) use `lake env lean <file>.lean` for the edit→check loop, reserve full `lake build` for a final check; (c) respect fixed-prefix / single-file edit-scope. General Lean practice, not task-specific. | Yes — passing trials already used `lake env lean` (t3,t8) and never `lake build`; this only makes slow/wandering trials converge faster. |
| 1 | BODY | SKILL.md Build-First Principle | Reworded "ALWAYS run `lake build`" → "use `lake env lean` while iterating, then confirm with `lake build`". Removes the push toward the slowest possible inner loop. | Yes — matches observed passing behavior. |
| 2 | REFERENCES (delete) | SKILL.md Quick Reference + Tools & Workflows | Removed the two broken `../../COMMANDS.md` / `../../scripts/README.md` links and the phantom "slash commands / automation scripts / subagents" table; replaced with an accurate index of the skill's REAL `references/*.md` files. | Yes — no passing trial referenced any of these (grep-confirmed). |
| 2 | REFERENCES (delete) | SKILL.md Compiler-Guided Repair + mathlib-search + axioms | Dropped nonexistent `/repair-file`, `/repair-goal`, `/repair-interactive`, `/search-mathlib`, `/check-axioms` slash commands and the `lean4-proof-repair` agent; KEPT the genuinely useful manual workflow (solver cascade `rfl→simp→ring→linarith→nlinarith→omega→exact?→apply?→aesop`, first-error-driven minimal patch, early-stop after ~3 repeats) as prose the agent can actually execute, plus the still-valid `references/compiler-guided-repair.md` pointer. | Yes — commands never invoked in any trace; the retained cascade is standard tactics. |

## Verify-the-fix
- Fast-loop command is verified **by the passing traces themselves**: t3 and t8 ran `lake env lean solution.lean`, it type-checked in ~12s, and those trials scored 1.0. The edit codifies the already-winning command.
- Broken-link/phantom-command removal verified by shell: `../../`, `/repair*`, `/search-mathlib`, `/check-axioms`, `COMMANDS.md`, `scripts/README` no longer appear in SKILL.md; every remaining `references/…` link resolves to an existing file (32/32 OK). Body = 142 lines, frontmatter unchanged → still a valid package.
- Blast radius: zero on the 9 passing trials — grep confirms none used slash commands / scripts / memory / full `lake build`; the added guidance reinforces the path they already take.

## Process & features used
- Serial (single task, single failing cluster that is infra-noise) — parallel subagents/worktrees were unnecessary and would only add risk for a one-skill, additive-edit change. Diagnosed all 10 trajectories directly.
- Prior iterations: none (seed). RUNMAP/LEDGER/JOURNAL empty.

## Good things to PRESERVE
- The 4-phase workflow, tactics/mathlib/repair reference set, and the solver cascade order — all kept.
- Do NOT re-introduce the `../../COMMANDS.md` / `scripts/` links or slash-command invocations — they are dead in this deployment.

## Deliberately skipped
- No proof-content edit: every content trial already passes; there is no failing assertion to target (would be a guess → violates REAL/VERIFIED).
- `lean4-memories/`: never fired in any trace and depends on an MCP memory server not present in the eval; editing it is unverifiable and adds blast radius for no signal.
- The t0 timeout is not "optimized against" directly (it is flagged infra noise); the edits only trim genuine, trace-visible wasted work as a safe side-benefit.
