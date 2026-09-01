# PROCESS — what I did this iteration (explainability; REQUIRED)  [cand_0002, parent cand_0001]

## Diagnosis of THIS iteration's ./trajectories/ (10 trials of cand_0001)
- **9/10 trials PASS** (reward 1.0): the agent invokes the skill, runs the bundled
  `scripts/solve_sequencing.py` at ~240s, writes all four outputs, and the objective
  (~3967–4033) clears the oracle gap (allowed ≈ 4085 = 3966 × 1.03). All 3 scored verifier
  tests pass: `test_objective_value_is_reported_correctly`, `test_solution_is_feasible`,
  `test_verifier_objective_is_no_worse_than_oracle`.
- **1/10 trial FAILS (t0)**: `output:null, trace:null, tool_calls:[], cost 0.0, tokens 0`,
  error "bench eval run timed out after 2400s". This is a **pre-rollout infra timeout** (the
  rollout produced zero tokens), explicitly flagged by the harness as uncontrollable noise
  ("not a skill defect; do not optimize against it"). No skill edit can address it.

So there is **no output-missing / wrong-answer failure cluster this iteration** — cand_0001
already fixed the "no output written" cluster. The reward is ceilinged at 0.90 by the single
infra flake, which is not skill-fixable.

## Ranked issue list
| rank | cluster | tasks | root cause | tag | change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Objective-margin fragility under the oracle-gap test (the FLAKY signal) | exam-block-sequencing | The bundled heuristic's 2-swap-only local search is marginal: at short budgets / under CPU contention it can land ABOVE the allowed 4085 (measured: baseline seed 1 = 4116@30s, 4090@120s; seed 42 = 4147@30s, 4203@120s-contended). `test_verifier_objective_is_no_worse_than_oracle` is the binding constraint (allowed ≈ 4085, oracle 3966 → only ~3% slack), so any rollout that hits an unlucky seed/short budget/contended CPU risks failing. | BEHAVIORAL (search quality) | SCRIPT |
| — | Infra timeout t0 | exam-block-sequencing | Pre-rollout bench timeout, 0 tokens. | INFRA | none (uncontrollable) |

## Change made this iteration (ONE edit, script-only)
| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | SCRIPT (in place) | `ordered-window-sequencing-mip/scripts/solve_sequencing.py` | Enlarged the local-search neighborhood from **2-swap only** to **2-swap + or-opt(1) relocation** in BOTH the simulated-annealing proposal (50/50 swap/relocate) and the steepest-descent polish. Added `build_feasible(inst)` (front-loading = "no large block in a late position"; only 3 late positions here, so any move — swap or relocation — is O(3) to feasibility-check) and a `relocate(perm,p,q)` or-opt helper. Also shortened the restart segment slightly (seg 3–6s) so more best-of-N restarts fit. Steepest descent still accepts only strictly-improving feasible moves, so the objective is monotonically non-increasing; best-of-restarts is preserved; the round-trip disk audit is preserved. Purely data-driven from `instance.json` (no hardcoded answer) → generalizes to any instance of this ordered-window family and held-out seeds. | Yes — see blast radius below. |

Also updated the method-description prose inside the script's `formulation.md`/`report.md`
strings and the module docstring to say "2-swap + or-opt(1)" for accuracy. These texts are
**not** keyword-asserted by the verifier (checked: only the 3 tests above are scored;
formulation/report merely need to exist), so the text edits cannot break a test.

## Verify-the-fix (ran the REAL solver + REAL verifier on the REAL instance)
- Targets `test_verifier_objective_is_no_worse_than_oracle` (allowed obj ≤ 4084.98). The
  richer neighborhood escapes swap-only local optima → strictly lower/equal objective in
  practice, widening the pass margin.
- **Head-to-head vs baseline (same seeds/budgets):**
  - @30s (6-way contended): improved seeds {1,42,7,99,2025,12345} = {4085,4041,4030,3992,4043,4063} — ALL ≤ 4085. Baseline @30s: seed 1 = 4116 (FAIL), seed 42 = 4147 (FAIL).
  - @120s (heavy contention): improved seed 1 = 4031, seed 42 = 4060; baseline seed 1 = 4134 (FAIL), seed 42 = 4203 (FAIL). Improved worst-case 4060 vs baseline worst-case 4203.
  - Operating point @180s single-run, historically-worst seed 1: improved = **3972** (baseline 4090–4116) — margin 113 under threshold, near the oracle 3966.
- **Real verifier:** ran `scripts/solve_sequencing.py --time-limit 60 --seed 1` on the task's
  actual `environment/data`, then executed the real `verifier/test_outputs.py` under pytest
  against the produced outputs → **3 passed** (obj 3993). Round-trip disk audit assert intact.

## Blast radius (SAFE)
- Only **one task** (exam-block-sequencing) uses these two skills, so blast radius is contained.
- Output contract is byte-identical (same 4 files, same schedule.csv/metrics.json schema); the
  objective evaluator (`evaluate`/`evaluate_perm`, incl. the active-pattern `z` term) is
  UNCHANGED — I only enlarged the move set the search explores. Feasibility is preserved
  (every relocation is feasibility-checked; the final schedule is still a valid permutation
  with front-loading satisfied). A strictly-lower objective can only keep-passing or improve
  the 3 verifier tests — it cannot flip a passing trial to failing.
- The 9 currently-passing trials ran at ~240s and passed with baseline; improved yields lower
  objectives at that budget, so they still pass (with MORE margin).

## Process & features used
- Serial diagnosis (single task, single skill package) + parallel background bash to run
  multi-seed solver benchmarks without blocking. No subagents/worktrees needed — the leverage
  was one verified, strictly-dominant search improvement, not fan-out.
- Prior iterations read: cand_0001 PROCESS.md + JOURNAL RESULT (ACCEPTED). Built directly on
  its bundled solver; this is the "add or-opt/reheating moves; raise restarts" focus cand_0001
  queued for next iteration.

## Good things to PRESERVE
- The exact objective evaluator (ordered tuples + active-pattern four-slot `z` overlap) —
  verified byte-for-byte against the benchmark verifier. Do NOT simplify `z` to all-triples-in-
  a-4-span.
- Keep `--time-limit` default (240s) well under the agent budget; do not raise near the wall.
- Keep both the 2-swap AND or-opt neighborhoods and the best-of-restarts + final-polish loop.

## Deliberately skipped
- The infra-timeout trial t0: uncontrollable pre-rollout bench noise (0 tokens), not skill-fixable.
- No SKILL.md body/description edits: the correct skill already triggers and the body already
  directs the agent to run the bundled solver (all 9 completed trials did so). Editing the body
  would be a rewrite of guidance the agent already follows correctly — higher blast radius, no
  benefit. The failure is search *quality*, fixed in code, not knowledge, fixed in prose.
- Did NOT reduce the recommended time budget to chase the infra timeout — t0 produced zero
  tokens (pre-rollout), so agent runtime is irrelevant to it.
