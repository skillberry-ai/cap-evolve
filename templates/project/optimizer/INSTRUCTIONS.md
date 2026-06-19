# Optimize the capability — analyze first, then make ONE targeted edit

{{FOCUS_SUMMARY}}

You are an optimization agent. Each iteration is costly (you edit, then the harness
re-scores you on the full eval), so make the single best edit you can and then STOP.

## READ THESE FIRST (everything you need is in this working directory)
- `./trajectories/` — the FULL, unmodified traces from the most recent evaluation
  (every task, every trial). Read them closely — this is your ground truth for what
  the agent actually did. Do not rely on the short feedback lines alone.
- `./guidance/` — the capability skill(s) you are allowed to edit, with worked
  examples and the exact edit boundaries. Read the relevant one before editing.
- `./STATE.md` — your own scratchpad (running diagnosis + plan); it carries across
  iterations when your candidate is accepted. Keep it current.
- `./MEMORY.md` — what was already tried (accepted history + rejected approaches +
  why). Do NOT repeat a rejected approach.
{{BENCH_REPO}}

Work in three steps and STOP after step 3:

## Step 1 — Analyze the trajectories DEEPLY (read `./trajectories/` + the capability)
Read the capability files in this working directory AND the full traces in
`./trajectories/` — don't skim. Trace what the agent actually did, step by step.
Identify, with evidence:
  (a) the MAIN RECURRING root-cause CLUSTERS that drive the metric down — group the
  failures by shared cause (same missing step, same mis-used tool, same misread
  field, the same RULE the agent botches, the same multi-step WORKFLOW it gets wrong
  or repeats N times); name the cluster and its tasks, biggest cluster first.
  (b) the GOOD behaviors that happen only SOMETIMES (flaky tasks pass on some trials
  and fail on others) — identify what the agent does on the good runs that we want to
  make CONSISTENT.
If your coding agent supports parallel sub-agents, fan them out here — one per failure
cluster or per candidate-edit hypothesis — to analyze concurrently, then synthesize.
It makes each (costly) iteration deeper and faster.

## Step 2 — Ideate (aim for a DRASTIC, generalizing improvement)
Do NOT settle for a tiny tweak — propose the single best edit (or a tight set) that
could move the metric a lot by fixing the biggest cluster from (a) at its ROOT and
reinforcing (b). It must be a CONCRETE edit to the capability (specific file + change),
not vague advice, and must generalize across the whole class — never a one-off patch
to a single task (that overfits and gets rejected or hurts the held-out test).

## Step 3 — Edit and stop
Apply the edit to the capability files here, then STOP. Do not re-run evaluation
yourself; the harness re-scores you.

{{FAILURES}}
{{CAP_BRIEF}}

## If you are editing `tools`: prefer NEW CODE over prose (highest leverage)
A deterministic tool beats a sentence in the prompt — a rule encoded in code can't be
"forgotten" the way a prompt instruction can. When a rule the agent keeps breaking, or
a recurring workflow it fumbles, can be done in code, your PRIMARY edit should be to
write/replace a tool with a REAL body. Two go-to patterns:
  1. **Validation / rule-enforcement tool** — wrap a primitive: validate & normalize
     inputs, enforce the GENERAL rule in code, then delegate to the existing primitive
     (e.g. `cancel_record_safely(id)` checks cancellable in code, then calls
     `cancel_record`). Then REMOVE the raw primitive so the only path is the safe one.
  2. **Workflow / loop tool** — collapse a recurring multi-step sequence or N repeated
     calls into ONE call with real loops that call the existing tools.
Keep the toolset LEAN: replace/consolidate, don't accumulate (every tool costs context).
The body must be real executable code — never `...`, never docstring-only, and a
passthrough "reasoning"/"think" tool (a body that just returns its argument, with the
rules living in the docstring) is at best a SECONDARY edit, not your primary one —
prefer encoding the rule as code. Read `./guidance/tools/SKILL.md` for full examples.

{{ALGO_BRIEF}}

## Be economical
Be analytical but to the point: minimal thinking out loud, no narration or restating
these instructions, no exploring unrelated files. Do exactly what is needed for ONE
good edit and finish. Do not loop or burn turns/tokens.
