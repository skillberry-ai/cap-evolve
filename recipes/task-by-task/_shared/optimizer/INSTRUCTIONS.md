# Optimize the SHARED office-document skills — ship several REAL, SAFE, VERIFIED fixes this iteration

{{FOCUS_SUMMARY}}

GOAL: raise the SkillsBench pass-rate as much as you can THIS iteration, then STOP (the
harness re-scores you — don't run evaluation yourself). The editable artifact is the FOUR
shared Agent Skills under your candidate dir: `docx/`, `pptx/`, `xlsx/`, `pdf/`. The SAME
four skills are deployed verbatim to EVERY task, so a fix to one skill's body/reference/
script moves every task that uses it. This is a **skill-package** capability — your levers
are the skill text + scripts, NOT a prompt or a tool API.

**FULL EDIT SURFACE — the WHOLE skill directory is the artifact, NOT just SKILL.md.** Inside
each package (`docx/`, `pptx/`, `xlsx/`, `pdf/`) you may CREATE, MODIFY, or DELETE any file or
directory: edit SKILL.md; edit, ADD, or remove `references/*.md`; edit or ADD NEW scripts under
`scripts/` (and `assets/`); delete dead or misleading content; and RESTRUCTURE the package —
anything that raises the pass-rate, as long as each package stays a VALID skill. You edit files
DIRECTLY in this workdir (a full copy of the candidate) and the ENTIRE directory is snapshotted,
so new scripts/files persist into later iterations and the final artifact. Do NOT default to
only tweaking SKILL.md — a typical strong iteration touches MULTIPLE files across multiple
skills (bodies + references + scripts together). Reach for adding a real `scripts/` helper the
agent will RUN whenever the trace shows it hand-rolling or botching the same transform.
**Placement rule (critical): every file you create or edit MUST live INSIDE one of the four
skill package dirs** — e.g. `pdf/scripts/extract.py`, `xlsx/references/formulas.md`,
`docx/SKILL.md`. ONLY the sub-package dirs that contain a `SKILL.md` are deployed to the agent;
a file written at the candidate ROOT (e.g. `./scan.py`) is NOT deployed and a SKILL.md pointing
at it is a dead reference. Put new scripts under `<skill>/scripts/` and reference them from that
skill's SKILL.md with execute intent.

Make **AS MANY real fixes as you can this iteration — solve many failure clusters across
many trajectories, not just the biggest one.** A one- or two-edit iteration is an
under-used iteration: diagnose EVERY failure cluster in `./trajectories/` and ship a fix
for each one that passes the three tests below. Breadth is the goal — improve multiple
skills' bodies + references + scripts + descriptions together in ONE candidate.

The ONLY brake on breadth is regression: every edit must pass all three tests, because one
speculative edit that breaks a currently-passing task can sink an iteration of good work.
The discipline is "many fixes, each one real and safe" — NOT "few fixes".

## The THREE TESTS every change must pass (this is the whole game)
1. **REAL** — it targets a cluster that is FAILING in THIS iteration's `./trajectories/`
   (the failed verifier test names + assertion messages in the score feedback). Never edit
   for a hypothetical problem; never touch a skill path only exercised by passing tasks.
2. **SAFE (bounded blast radius)** — would this edit change what the agent DOES on ANY
   currently-passing task that uses the same skill? Skills are shared across all tasks, so
   the blast radius is wide. Prefer ADDITIVE, narrowing edits (a missing step, a corrected
   procedure, a bundled helper the agent will call) over REWRITES of guidance the agent
   already follows correctly. Name the passing tasks that use the skill you're editing and
   confirm the edit does not change their behavior.
3. **VERIFIED** — you have shown it actually addresses the failed test (see VERIFY-THE-FIX).
   An edit you cannot tie to a specific failing assertion is a guess — drop it.

Don't re-add anything `LEDGER.md` / `JOURNAL.md` show was already tried and rejected.

## Read these first (everything is in this working directory)
STEP 0 (reading mandate — do this BEFORE any edit, EVERY iteration):
- `./guidance/skill-package/SKILL.md` — READ IT IN FULL. It defines your edit space (all four
  edit classes), the progressive-disclosure model, and the skill-creator authoring rules
  (valid frontmatter, body budget, one-level references, no broken links), with worked
  examples. This read is mandatory; every edit must keep each skill a VALID package.
- `./guidance/diagnose/SKILL.md` — the failure-clustering method. Use it.
- `./guidance/optimizer/claude-code.md` — your subagent/parallelism features.
- `./trajectories/` — the FULL agent transcripts + which verifier tests failed for the
  current best candidate (the step you build on). The `{{FAILURES}}` block summarizes them
  with the failed test names; read the actual traces for the clusters you'll fix.
- The FOUR skills in your candidate dir (`docx/`, `pptx/`, `xlsx/`, `pdf/`) — read the
  SKILL.md + references + scripts of any skill you intend to edit.
- `./LEDGER.md` (FACTS, read-only) — every prior iteration's outcome + tasks it broke/fixed.
- `./JOURNAL.md` — the accumulating handover. Each entry is the optimizer's INTENT; the
  framework stamps a **RESULT** line right below it (objective: ACCEPTED/REJECTED · Δ · the
  EXACT tasks fixed/broke). The RESULT lines — not the intent — are the truth of what worked:
  read them ALL before proposing. If the most recent RESULT is REJECTED, its whole batch was
  reverted — read that entry's `./prior_iterations/<id>/diff.patch`, keep the edits NOT in its
  `broke={…}`, and DROP or REDESIGN the ones that were (don't resubmit the batch, don't
  abandon the cluster). APPEND your new entry (INTENT only) below the marker.
- `./RUNMAP.md` + `./prior_iterations/<id>/` — prior PROCESS.md + diffs for clusters you touch.
- `./PROCESS.md` — your REQUIRED explainability file for THIS iteration (template inside).
{{BENCH_REPO}}

## Process (do this, then STOP)
**Parallelism:** {{PARALLEL_NOTE}} A useful pattern: Phase 1 — one read-only diagnose
subagent per FAILING task produces a tight issue list (which skill, which behavior, which
failed test); Phase 2 — one edit-subagent per SKILL in its own worktree, then merge all
edits into ONE candidate.
1. Read STEP-0 files + the cross-iteration files (LEDGER facts, JOURNAL handover, RUNMAP).
2. Diagnose THIS iteration's `./trajectories/` ONLY. Cluster ALL failures by shared root
   cause (which skill failed to elicit which behavior). RANK clusters by LEVERAGE
   (# failing tasks × score recoverable), biggest first — but plan to fix ALL of them.
3. For EACH cluster, pick the right SKILL EDIT CLASS (next section), draft the edit, run it
   through the THREE TESTS; keep it only if it passes all three.
4. Ship every passing edit together in this ONE candidate — cover as many clusters SAFELY
   as you can. Re-validate every touched skill against the authoring rules.
5. Fill `PROCESS.md` and APPEND your entry to `JOURNAL.md`. STOP.

## Choose the SKILL EDIT CLASS by failure type (highest leverage first)
1. **DESCRIPTION / TRIGGER** — the wrong skill fired (or none) for the task's phrasing.
   Fix the frontmatter `description` so the RIGHT skill triggers on the task's wording
   (say plainly WHAT it does + WHEN to use it; front-load the use case; third person; no
   all-caps imperatives — they over-trigger). Lowest-risk, often high-leverage.
2. **BODY** — the agent keeps SKIPPING a step the skill should make unmissable (e.g. docx
   split-placeholder handling across runs, xlsx formula recalculation after edits, pdf form
   fields). Make the required step explicit, ordered, and imperative in the SKILL.md body —
   ADDITIVE where possible. Keep the body within budget (~500 lines / ~5k tokens); if it
   grows too long, move detail into a reference (class 3).
3. **REFERENCES** — rarely-used or bulky detail bloats the body, or a needed detail is
   missing. Factor it into `references/<f>.md` (ONE level deep) with an explicit
   "load this when …" pointer from the body. Keep links valid (no broken references).
4. **SCRIPTS** — the trace shows the agent re-implementing the same helper, or hand-rolling
   a fragile transform the skill could ship. Bundle a script under `scripts/` and state the
   execute-vs-read intent in the body ("run `scripts/<x>.py`, do not reimplement"). Add a
   script ONLY when the agent will actually call it and it changes the produced file.

PREFER CODE (a script) over prose for a BEHAVIORAL miss (this is where iterations fall short).
If the trace shows the agent already "knows" what to do but skips or botches a deterministic
step (mishandles docx split-runs, forgets to recalc xlsx formulas, mangles a pdf transform),
adding ANOTHER prose rule it will skip the same way does little — ship a `<skill>/scripts/`
helper the agent RUNS that performs the step correctly, and point the body at it with execute
intent. Reserve prose for genuine KNOWLEDGE gaps (a fact/format/criterion the agent cannot
derive). For a hard-ZERO cluster a script is usually the only thing that moves it. Do NOT
defer a needed script to "next iteration" — build it now; it is the highest-leverage edit.
VERIFY BY RUNNING: you have Bash in this workdir — after adding/editing a script, RUN it
(python / pytest / soffice) on the FAILING task's actual inputs and confirm it produces the
corrected output BEFORE shipping. An unverified script is a guess; either verify it or drop it.
Don't avoid scripts for fear you can't test them — you can, so test them.

## VERIFY-THE-FIX (do this for EACH kept edit — satisfies VERIFIED + SAFE)
- **Body / procedure edit:** tie it to the exact failed verifier test in the trace (e.g.
  "`test_relocation_section_removed`: marker `{{END_IF_RELOCATION}}` still present") and
  show the new step would produce the asserted-on result. Confirm a task that ALREADY
  passes with this skill is not pushed onto a different (worse) path by the edit.
- **Description edit:** confirm the failing task's phrasing now matches the trigger, and
  that no other task's correct skill selection is disturbed.
- **Script edit:** run the script body on inputs from the failing trace and confirm it
  produces the corrected file; confirm the body tells the agent to execute it.
- **Reference edit:** confirm the moved detail is still reachable via a body pointer and the
  link resolves (no broken-reference warning from the capability's validate).
Record one line per edit in PROCESS.md, e.g.
`docx body: add split-placeholder merge step → fixes offer-letter test_X; pptx/xlsx tasks unaffected (don't use docx)`.

## NON-OVERFITTING (every edit must GENERALIZE — this is critical for skills)
Skills are used MANY times across the task class and the held-out gate. NEVER hardcode a
task-specific filename, value, marker literal, or answer into a skill. Encode the GENERAL
behavior ("when a placeholder spans multiple runs, merge the runs before substituting",
"recalculate formulas after any cell write"), not `if filename == "offer_letter.docx"`.
Use per-task specifics in the traces ONLY to understand the failure CLASS, then write the
general fix. A fiddly task-specific rule hurts the held-out tasks.

## Handover (REQUIRED before you STOP)
- **PROCESS.md** (this iteration): the ranked cluster list (with leverage + a
  KNOWLEDGE / BEHAVIORAL / CAPABILITY-GAP tag per cluster), every kept edit + its edit
  CLASS, the VERIFY-THE-FIX + blast-radius line per edit, what you deliberately skipped and
  why, and (if you used subagents) that you did.
- **JOURNAL.md** (append ONE entry below the marker; never edit earlier entries). Write
  INTENT only — you cannot know your own gate result; the framework stamps the RESULT line
  below your entry. Include: the changes I made (1 line/edit, naming the skill + file +
  cluster) · the EXPECTED effect + why each is safe (which failing task it should fix; why
  no passing task regresses) · which prior RESULTS I built on and which regressing edits I
  did NOT re-try (cite ids) · refuted hypotheses (a prior RESULT disproved — never re-test) ·
  high-value clusters not yet cracked · focus next iteration.

{{FAILURES}}
{{PASSING}}
{{CAP_BRIEF}}
{{ALGO_BRIEF}}

## Self-check before STOP
- Every kept edit passes the THREE TESTS (REAL, SAFE, VERIFIED) and has its verify +
  blast-radius line in PROCESS.md. Drop any that doesn't.
- You shipped several such edits across the top-ranked clusters you could fix SAFELY, and
  did NOT pad with speculative/cosmetic edits or re-add anything already rejected.
- Every edit keeps its skill a VALID package (frontmatter, body budget, one-level
  references, no broken links) — re-validate each touched skill.
- No edit hardcodes a task-specific filename/value/marker/answer — every edit GENERALIZES.
- PLACEMENT: every skill file you created/edited lives INSIDE a skill dir (docx/pptx/xlsx/pdf,
  e.g. `pdf/scripts/x.py`). You did NOT create any new skill file at the candidate ROOT — only
  the required handover files (PROCESS.md / JOURNAL.md) belong there. A skill file at the root
  is NOT deployed to the agent and any SKILL.md reference to it is dead.
- For a hard-ZERO cluster you shipped an unmissable procedure or a script the agent will
  run, not a reworded paragraph.
- PROCESS.md + JOURNAL.md are filled. Keep narration minimal.
