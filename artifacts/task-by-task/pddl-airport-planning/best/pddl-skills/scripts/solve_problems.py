#!/usr/bin/env python3
"""Solve every PDDL task listed in a problem.json, write each plan, and self-check it.

Canonical, verified pipeline for PDDL planning tasks (never hand-write a plan):
  load-problem  -> PDDLReader.parse_problem(domain, problem)
  generate-plan -> OneshotPlanner(name="pyperplan").solve(problem) -> result.plan
  save-plan     -> PDDLWriter(problem).write_plan(plan, filename=plan_output)
  self-check    -> PDDLReader.parse_plan(problem, plan_output) + PlanValidator

CRITICAL — plan output FORMAT (this is what the grader parses back).
  The grader reads each plan with PDDLReader.parse_plan(problem, plan_file), which
  ONLY accepts one IPC / parenthesized action per line:

      (action_name arg1 arg2)

  It RAISES on function-call notation `action_name(arg1, arg2)`. The example in the
  task prompt is shown in function-call style, but that style is NOT accepted — you
  must emit the parenthesized form. PDDLWriter.write_plan (used below) emits exactly
  the accepted form, so ALWAYS let this script format the plan; never reformat or
  hand-write it.

Usage:
  python3 solve_problems.py [problem_json]

  problem_json defaults to ./problem.json (e.g. /app/problem.json). The domain,
  problem and plan_output paths inside problem.json are resolved relative to the
  directory that contains problem.json, so no path is hardcoded.
"""

import json
import os
import sys


def _import_up():
    from unified_planning.io import PDDLReader, PDDLWriter
    from unified_planning.shortcuts import OneshotPlanner, PlanValidator
    return PDDLReader, PDDLWriter, OneshotPlanner, PlanValidator


def main(problem_json):
    PDDLReader, PDDLWriter, OneshotPlanner, PlanValidator = _import_up()

    problem_json = os.path.abspath(problem_json)
    base = os.path.dirname(problem_json)
    with open(problem_json) as f:
        tasks = json.load(f)

    failures = []
    for t in tasks:
        pid = t.get("id", "?")
        domain = os.path.join(base, t["domain"])
        problem_file = os.path.join(base, t["problem"])
        out = os.path.join(base, t["plan_output"])
        print(f"[{pid}] solving {t['domain']} / {t['problem']} ...")

        reader = PDDLReader()
        problem = reader.parse_problem(domain, problem_file)

        with OneshotPlanner(name="pyperplan") as planner:
            result = planner.solve(problem)
        plan = getattr(result, "plan", None)
        if plan is None:
            print(f"[{pid}] NO PLAN FOUND")
            failures.append(pid)
            continue

        out_dir = os.path.dirname(out)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        # write_plan emits the parenthesized "(action arg1 arg2)" form the grader
        # requires. Do not post-process this file.
        PDDLWriter(problem).write_plan(plan, filename=out)

        # Self-check with the SAME logic the grader uses, so a bad plan is caught here.
        pred = reader.parse_plan(problem, out)
        with PlanValidator(problem_kind=problem.kind, plan_kind=pred.kind) as v:
            val = v.validate(problem, pred)
        ok = bool(val)
        print(f"[{pid}] wrote {t['plan_output']} ({len(plan.actions)} actions) "
              f"-> parse_plan OK, VALID={ok}")
        if not ok:
            failures.append(pid)

    if failures:
        print("FAILED to produce a valid plan for:", failures)
        return 1
    print("All plans written and self-validated.")
    return 0


if __name__ == "__main__":
    pj = sys.argv[1] if len(sys.argv) > 1 else "problem.json"
    sys.exit(main(pj))
