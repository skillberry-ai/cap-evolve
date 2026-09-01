---
name: pddl-skills
description: Solve PDDL (Planning Domain Definition Language) planning tasks end to end — load a domain and problem, generate a valid sequential plan with a classical planner, write it in the correct plan format, and self-validate it. Use for IPC-style planning problems (e.g. airport ground traffic, logistics/TPP) where a problem.json lists domain/problem files and a plan_output path per task.
license: Proprietary. LICENSE.txt has complete terms
---

# PDDL planning tasks

Do the work with the bundled scripts — do NOT hand-write, hand-trace, or reformat
plans. Hand-tracing IPC domains is unreliable, and hand-written plans use the wrong
syntax (see the format rule below). Run the planner and the writer instead.

## Required procedure (run these, in order)

The task gives a `problem.json` (usually at `/app/problem.json`); each entry has
`id`, `domain`, `problem`, and `plan_output`. For every entry you must load the
domain+problem, generate a plan, and write it to `plan_output`.

1. **Prepare the environment (once).** Run:

   ```bash
   bash /skills/pddl-skills/scripts/prepare_env.sh
   ```

   This ensures the planner (`unified_planning` + `up-pyperplan`) and the
   plan-validation toolchain used to grade your output are installed and reachable.
   It is idempotent and safe to run once up front.

2. **Generate + write + self-validate every plan.** Run (pass the problem.json path
   if it is not `./problem.json`):

   ```bash
   python3 /skills/pddl-skills/scripts/solve_problems.py /app/problem.json
   ```

   For each task this does: `PDDLReader.parse_problem(domain, problem)` →
   `OneshotPlanner(name="pyperplan").solve(problem)` →
   `PDDLWriter.write_plan(plan, filename=plan_output)`, then re-parses the written
   file with `PDDLReader.parse_plan` and checks it with `PlanValidator`. It prints
   `VALID=True` per task and `All plans written and self-validated.` on success.
   Do not reimplement this pipeline; run the script.

3. **Confirm** every `plan_output` file now exists and the script reported
   `VALID=True` for each task. If any task printed `NO PLAN FOUND` or `VALID=False`,
   re-read that domain/problem and re-run — do not fall back to hand-writing a plan.

## Plan output FORMAT (critical — this is what the grader parses)

The grader reads each plan back with `PDDLReader.parse_plan`, which accepts ONE
parenthesized action per line and nothing else:

```
(action_name arg1 arg2)
(action_name arg1)
```

- It **rejects** function-call notation `action_name(arg1, arg2)` — even though the
  example shown in some task prompts is written that way. Never emit that form.
- One action per line; action and object names must match the domain/problem exactly.
- `PDDLWriter.write_plan` (used by `solve_problems.py`) emits exactly the accepted
  form, so always let the script write the file and never post-process it.

## Reference: the underlying primitives

`solve_problems.py` is the canonical pipeline; the individual `.skill` files
(`load_problem`, `generate_plan`, `save_plan`, `validate`) document the same steps if
you need to call them programmatically. Prefer running `solve_problems.py`.
