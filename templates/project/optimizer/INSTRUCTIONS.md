# Optimize the capability — make the largest improvement you can this iteration

{{FOCUS_SUMMARY}}

GOAL: maximize the eval score. Make the biggest, most generalizing improvement you
can this iteration. The prompt AND the tools are EQUALLY fair game — pick whatever
fixes the most failure clusters. Then STOP (the harness re-scores you; don't re-run
evaluation yourself).

EFFORT: scale your analysis depth and effort to the number and difficulty of the
failing trajectories. Few, easy failures → move fast with one focused edit. Many or
hard failures → go deeper; if your agent supports parallel sub-agents / worktrees
(see `./guidance/optimizer/<name>.md`), spawn one per cluster to analyze concurrently,
then synthesize.

## Read these first (everything is in this working directory)
- `./guidance/<cap>/SKILL.md` — the capability skill(s) you may edit. WHAT YOU CAN
  CHANGE is listed there, with worked examples and edit boundaries. Read it first.
- `./guidance/sources/` — supporting source files (data models / types the tools
  import). Read them before writing tool code so your code is correct.
- `./guidance/diagnose/SKILL.md` — the failure-clustering METHOD (reflective dataset,
  group failures by shared signature). Use it.
- `./trajectories/` — the FULL, unmodified traces of the current best candidate's most
  recent evaluation (the step you build on). Your ground truth — don't rely on the
  short feedback lines alone.
- `./MEMORY.md` — accepted history + approaches that regressed (with per-task impact).
- `./STATE.md` — your scratchpad + handover; it carries across accepted iterations.
{{BENCH_REPO}}

## Process (do this, then STOP)
1. Read the current capabilities, the guidance above, and MEMORY/STATE to understand
   what has happened so far.
2. Analyze THIS step's trajectories in `./trajectories/` with the diagnose method.
   Find the MANY recurring issues — total failures (reward 0), partial-credit failures
   (graded between 0 and 1), and communication/omission failures (the agent did the
   work but failed to report or confirm it). Also note GOOD-but-INCONSISTENT behaviors
   (pass on some trials, fail on others) to make consistent. Name each cluster, its
   tasks, and its shared cause; biggest first.
3. Make ONE bold, multi-part edit across the SELECTED capabilities that addresses as
   many clusters as you can at their root. You may rewrite, consolidate, or add prompt
   rules AND add, replace, or edit tools. Ground every change in the trajectories;
   never drop a needed rule (change/consolidate/add — don't delete). Enforcing a rule
   in tool code is stronger than prose when the rule is deterministic — so do both
   where useful. Build on the current best (keep its wins).
4. Write a short handover in `STATE.md` (sections below), apply the edit, and STOP.

## Steering — protect the wins, don't freeze
Use the "Currently PASSING" block and the "Per-task impact of prior candidates" block
(appended below) as STEERING, not as a reason to avoid editing:
  - Don't re-introduce a change that BROKE a passing task (a task a prior candidate
    dropped from passing). For each currently-passing task, make sure your edit doesn't
    change the code path / rule / tool it exercises.
  - A net gain that breaks as many tasks as it fixes is rejected — protect the passing
    set, but keep editing boldly everywhere else.

## Handover
Your `STATE.md` MUST end with:

    ## Handover for next iteration
    - Approaches tried this iteration (1 concrete line each):
    - Lessons learned (general):
    - Recommendation / what to focus on next:
    - Approaches that regressed AS IMPLEMENTED (a better-designed version may still
      work — don't permanently abandon a high-value cluster):

{{FAILURES}}
{{PASSING}}
{{CAP_BRIEF}}
{{ALGO_BRIEF}}

## Be economical
Minimal narration; don't restate these instructions or explore unrelated files. Make
one strong, multi-part candidate, write the handover, and finish.
