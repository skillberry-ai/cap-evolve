# The prompt — onboard SkillsBench as a new benchmark and optimize its skills

Paste this to your coding agent (Claude Code) at the cap-evolve repo root and say
**"follow RUN.md."** Intake treats this as a brand-new benchmark: the integration
step **clones SkillsBench + installs the BenchFlow CLI**, wires the runner (a
`claude-sonnet-4-6` agent in a Docker sandbox), writes the adapter, runs the
`cap-evolve check` gate, then the full optimize → gate → sealed-test → report loop
with a live dashboard. Everything below is the input intake needs.

```text
Follow RUN.md to run a cap-evolve optimization. Onboard this as a brand-new
benchmark — the intake/integration step should CLONE + INSTALL it (not assume it
exists). Here is everything intake needs:

# 1. CAPABILITY TO OPTIMIZE  (a copy is edited each iteration; the original is never touched)
- type:         [skill-package]      # the Agent Skill packages themselves
- what:         the SHARED office-document skills SkillsBench hands its agent —
                docx, pptx, xlsx, pdf. The same four skill packages are used across
                many tasks, so improving them moves multiple tasks at once. This is
                exactly the skill-package capability: edit SKILL.md (frontmatter +
                body), references/*.md, and bundled scripts/, while staying a VALID
                skill (skill-creator authoring rules: progressive disclosure, valid
                frontmatter, body budget, one-level references, no broken links).
- seed:         one canonical copy of each of the four skills, placed under
                seed_capability/{docx,pptx,xlsx,pdf}/ . SkillsBench ships per-task
                VARIANTS of these skills; seed with the MOST COMPLETE variant of each
                found in the cloned tasks (docx → offer-letter-generator's;
                pptx → exceltable-in-ppt's full ooxml+scripts variant;
                xlsx → exceltable-in-ppt's recalc.py variant; pdf → pdf-excel-diff's
                forms.md+reference.md+scripts variant). This single shared set is what
                the optimizer edits and what gets deployed to EVERY task.
- capability_path:   seed_capability   (a dir holding the four skill sub-packages)
- actions:      [edit]
- capability_sources:  []   (the skills are self-contained; no shared types module)
- NOTE for the integration step — the skill-package capability's handlers
  (scripts/abstract.py: materialize/apply/validate) operate on ONE skill dir. The
  seed holds FOUR. If `cap-evolve check` shows the capability only sees one skill,
  treat it as a FRAMEWORK GAP and extend the skill-package handlers to walk every
  immediate sub-package under capability_path (namespacing components by
  "<skill>/SKILL.md", "<skill>/references/<f>.md") and validate each. Do not hand-wave
  it in the adapter.

# 2. BENCHMARK / DATASET  (the eval) — INSTALL IT DURING INTAKE
- benchmark:    SkillsBench  (the first benchmark for how well agents USE skills)
- repo:         https://github.com/benchflow-ai/skillsbench   (latest main; record the resolved commit)
- install:      git clone (structure only is fine: GIT_LFS_SKIP_SMUDGE=1 is OK for
                reading/seed extraction); install the runner CLI with
                `uv tool install benchflow` (this is the `bench` CLI, v0.6.4+).
                BenchFlow fetches each task's pinned content itself at run time via
                --source-repo/--source-path, so the runner does not depend on a local
                checkout — the local clone is only for reading task structure and
                extracting the seed skills.
- sandbox:      docker  (REQUIRED; each task runs in its own container)
- tasks:        "adapter" — adapter.tasks() returns the 10 task ids below as Tasks
                (id = the SkillsBench task name; no network in tasks()).

# 2b. THE 10 TASKS + SPLIT  (all use the shared office skills; difficulty in parens)
- train == val  (7 tasks; train and val are the SAME ids — fit the metric, the engine
                logs a splits_warning):
    offer-letter-generator   (easy,   docx)
    exceltable-in-ppt        (medium, pptx+xlsx)
    xlsx-recover-data        (medium, xlsx)
    sales-pivot-analysis     (medium, pdf+xlsx)
    invoice-fraud-detection  (hard,   pdf+xlsx)
    weighted-gdp-calc        (medium, xlsx)
    financial-modeling-qa    (hard,   pdf+xlsx)
- test  (3 held-out tasks, SEALED — scored once by finalize):
    pdf-excel-diff           (medium, pdf+xlsx)
    pptx-reference-formatting(medium, pptx)
    reserves-at-risk-calc    (medium, xlsx)
- pin the split in split_ids.json: {"train":[...7...],"val":[...same 7...],"test":[...3...]}.
- VERIFY at clone time that each task still ships one of docx/pptx/xlsx/pdf under
  tasks/<id>/environment/skills/; if a task drifted, swap it for another task that does.

# 3. RUNNER  (the agent under test) + MODELS + CREDENTIALS
- agent under test:   claude-sonnet-4-6, run as BenchFlow's Claude agent
                (`--agent claude`, i.e. claude-agent-acp = Claude Code via ACP).
- how to run ONE task (the call adapter.run_target builds):
    bench eval run \
      --source-repo benchflow-ai/skillsbench --source-path tasks --source-ref main \
      --include <task_id> \
      --agent claude --model claude-sonnet-4-6 \
      --sandbox docker \
      --skill-mode with-skill --skills-dir <CANDIDATE_SKILLS_DIR> \
      --jobs-dir <PER_EVAL_OUTPUT_DIR> \
      --agent-env ANTHROPIC_BASE_URL=$ANTHROPIC_BASE_URL \
      --agent-env ANTHROPIC_AUTH_TOKEN=$ANTHROPIC_AUTH_TOKEN
- SKILL INJECTION (the key mechanism — verified in benchflow/skill_policy.py):
    passing --skill-mode with-skill --skills-dir <DIR> where <DIR> != the task's own
    environment/skills makes BenchFlow STRIP the task's bundled skills (and the
    Dockerfile COPY of them) and mount <DIR> at /skills instead. So <DIR> = the
    candidate's optimized seed_capability is deployed to EVERY task verbatim. ctx (the
    live candidate dir) IS that <DIR>; materialize writes the edited skills there.
- ABSOLUTE PATHS (critical, or every rollout fails): bench is invoked from a FIXED
    working dir (so it reuses its dataset clone cache), which is NOT cap-evolve's cwd.
    cap-evolve hands run_target a candidate dir (ctx) as a RELATIVE path
    (e.g. `.capevolve/<run>/candidates/<id>`). You MUST resolve EVERY path you pass to
    bench to ABSOLUTE before the call — `--skills-dir` (= `Path(ctx).resolve()`) AND
    `--jobs-dir` — otherwise bench, running in its own cwd, raises
    `FileNotFoundError: skills_dir not found: <relative path>` (benchflow/skill_policy.py)
    and the rollout produces no graded result. A standalone `bench eval run` you type by
    hand with an absolute --skills-dir will PASS and HIDE this — so do not trust a
    hand-typed smoke; verify on the real cap-evolve path (next bullet).
- UNIQUE JOBS DIR PER CANDIDATE (or every candidate scores the baseline): BenchFlow treats a
    `--jobs-dir` that already holds a completed result as DONE and SKIPS re-running (resume
    behavior). If run_target derives the jobs dir from only task+seed, the baseline and every
    candidate share the same dir, so candidate evals are skipped and read the BASELINE's stale
    result — every candidate ties the baseline (Δ=0, all rejected, ~10s evals). The jobs dir
    MUST be UNIQUE PER CANDIDATE: include the candidate id (the candidate dir's name, e.g.
    `seed`, `cand_0001`) in the path, e.g. `<run>/bench_jobs/<candidate>/<task>__seed<k>/`.
    Symptom of this bug: a candidate eval that finishes in seconds with reward identical to the
    baseline. (See the per-candidate verification below — a one-candidate smoke can't catch it.)
- CLEAN SKILLS DIR (or the agent install breaks from iteration 1 on): the candidate dir
    (ctx) is ALSO the optimizer's workdir, so from iteration 1 it accumulates optimizer
    scratch files at the top level — INSTRUCTIONS.md, PROCESS.md, JOURNAL.md, LEDGER.md,
    guidance/, trajectories/, etc. If you pass the whole candidate dir to `--skills-dir`,
    BenchFlow treats EVERY top-level entry as a skill and injects them all into the
    Dockerfile ("Skills injected: N items"), which corrupts the build and the agent
    install fails with `claude-agent-acp install failed (rc=127)` — every edited-skill
    task errors (the seed/baseline dir is clean so it hides this until iteration 1). So
    run_target MUST deploy a CLEAN skills dir: materialize a temp dir containing ONLY the
    immediate sub-packages that actually contain a SKILL.md (docx/pptx/xlsx/pdf), copied
    (or symlinked) from ctx, and pass THAT (absolute) as `--skills-dir`. Never hand bench
    the raw candidate dir. VERIFY this with a candidate that has a stray top-level file
    (e.g. drop an INSTRUCTIONS.md next to the four skills) — the task must still run.
- VERIFY ON THE REAL CAP-EVOLVE PATH (not a hand-typed bench call): the only honest
    check that the adapter works is a real `cap-evolve run`/baseline where ctx comes
    from the harness as a relative path. Run a 1–2-task baseline via a smoke spec and
    confirm a task actually executes in Docker (the `evaluate` event's `seconds` is in
    MINUTES, ~4 min/task, not ~14s) and returns a real 0/1 reward with rollout.error
    null — an instant all-zero baseline means the rollouts errored (the absolute-path
    bug above). Only then is `cap-evolve check` + integration truly green end to end.
    CRITICAL — also verify a SECOND, EDITED candidate, because a baseline-only smoke cannot
    catch the candidate-specific bugs (scratch pollution, jobs-dir reuse): take the seed
    skills, make a real edit to ONE skill, and run that as a separate candidate through the
    SAME run_target/eval path. Confirm it (a) deploys exactly the four skill packages, (b)
    actually re-runs in Docker (minutes, its OWN jobs subdir — NOT an instant ~10s eval that
    reuses the baseline's result), and (c) its reward can DIFFER from the baseline. If the
    second candidate finishes in seconds with the baseline's exact score, the jobs dir is not
    unique per candidate (above) — fix it before trusting any iteration.
- models + credentials:   the agent reaches the IBM-internal Anthropic-compatible
    LiteLLM gateway. Read ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN from the repo-root
    .env (copy them there from ~/.claude/settings.json's env block — base URL
    https://ete-litellm.ai-models.vpc-int.res.ibm.com, model id claude-sonnet-4-6) and
    PROPAGATE them into the sandboxed agent with --agent-env (above). Use the same .env
    loader pattern as examples/tau2_airline/adapters/rits.py (_load_env walks parents,
    setdefault, no python-dotenv dep); read ANTHROPIC_* instead of RITS_*. Never hardcode
    the token.
- INTEGRATION RISK to validate during implement-and-check (resolve empirically, fix as a
    framework gap if needed): (a) the in-sandbox claude agent must honor ANTHROPIC_BASE_URL
    /ANTHROPIC_AUTH_TOKEN and reach the VPC gateway from inside Docker — if BenchFlow's own
    LiteLLM proxy or default base URL shadows it, route around it (e.g. --agent-env, or a
    config-override); (b) if `--agent claude` (Claude Code via ACP) is too heavy/unauthenticated
    in Docker, fall back to a simpler routable LLM agent on claude-sonnet-4-6. Decide by RUNNING
    one task, not by guessing.

# 4. SCORER  (what to optimize against) — and WHERE the metric comes from
- metric:       per-task BINARY pass in {0,1}. SkillsBench verifiers (verifier/test.sh)
                run pytest and write /logs/verifier/reward.txt = 1 (all tests pass) or 0,
                plus a CTRF JSON at /logs/verifier/ctrf.json with per-test results.
- metric source: BenchFlow collects the verifier reward into the per-task result under
                --jobs-dir (the run's result.json / scored-trajectory). Implement
                adapter.score() to read that reward (cross-check with `bench eval metrics`
                which reports pass-rate over a jobs dir). score() must be DETERMINISTIC on a
                fixed rollout (the cap-evolve check gate enforces this) — read the recorded
                reward, do not re-run.
- pass rate:    the objective = mean reward across tasks on the VAL split (cap-evolve
                computes mean + SE; BenchFlow's summary/metrics cross-checks).
- feedback (the learning signal) — gold-SAFE and SPECIFIC: for each FAILING task, parse the
                CTRF ctrf.json for the failed TEST NAMES and their assertion messages
                (e.g. "test_relocation_section_removed: marker '{{END_IF_RELOCATION}}' still
                present in output") and surface those as the feedback, so the optimizer knows
                WHICH behavior the skill failed to elicit. Gold-SAFE: surface only the agent's
                OWN output defect named by the test (the assertion message about what is wrong
                in the produced file) and the task instruction; NEVER read or echo the task's
                oracle/solve.sh, the gold output, or any expected value. If the message is not
                safely usable, fall back to the failing test name alone. Deterministic.

# 4b. TRAJECTORIES  (the FULL traces the optimizer reads) — PATH IS AN INPUT
- where:        BenchFlow writes each rollout's native artifacts under --jobs-dir
                (the agent's llm_trajectory.jsonl, the result/scored-trajectory, verifier
                logs). Point run_target's --jobs-dir at a per-eval dir UNDER THE RUN, e.g.
                <run_dir>/trajectories/val/.
- expose:       implement adapter.trajectories(split) to return that directory. cap-evolve
                copies it VERBATIM into the optimizer's working dir as ./trajectories/ each
                iteration, so the optimizer reads the complete agent transcript + which tests
                failed (return None to fall back to cap-evolve's per-rollout JSON).

# 5. OPTIMIZER  (proposes the edits) + MODEL + CREDENTIALS + CONTEXT
- optimizer:    claude-code
- model:        claude-opus-4-8
- credentials:  the logged-in Claude Code session / the same ANTHROPIC_* gateway env
- runner_repo_path:  the cloned skillsbench checkout (read-only context so the optimizer can
                consult task.md instructions, verifier tests, and the skills it is editing)
- optimizer instructions: author .capevolve/project/optimizer/INSTRUCTIONS.md from the
                scaffolded template (keep its {{...}} placeholders intact — the harness fills
                them per iteration). SCOPE IT TO skill-package ONLY (no prompt/tools/mcp
                guidance; the editable artifact is the four skill packages). Encode:
    * STEP-0 reading mandate (REQUIRED, before any edit): read ./guidance/skill-package/SKILL.md
      IN FULL — it defines the edit surface, the four edit classes, and the skill-creator
      validity rules; the optimizer MUST consult it every iteration. Then read
      ./guidance/diagnose/SKILL.md + ./guidance/optimizer/claude-code.md, then ./trajectories/
      (the agent transcript + failed tests) and the four skills BEFORE editing.
    * FULL EDIT SURFACE — the WHOLE skill directory is the artifact, NOT just SKILL.md. The
      optimizer may CREATE, MODIFY, or DELETE any file or directory inside each skill package
      (docx/pptx/xlsx/pdf): edit SKILL.md, edit/add/remove references/*.md, edit/add NEW
      scripts under scripts/ (and assets/), delete dead or misleading content, and RESTRUCTURE
      the package — anything that raises the objective score, as long as each package stays a
      VALID skill. Do NOT default to only tweaking SKILL.md: a typical iteration touches
      MULTIPLE files across multiple skills (bodies + references + scripts together). The
      optimizer edits files DIRECTLY in its workdir (a full copy of the candidate) and
      cap-evolve snapshots the ENTIRE directory, so new scripts/files persist into later
      iterations and the final artifact — use that freedom. PLACEMENT RULE: every file the
      optimizer creates/edits MUST live INSIDE one of the four skill package dirs (e.g.
      pdf/scripts/extract.py, xlsx/references/formulas.md) — only sub-packages containing a
      SKILL.md are deployed; a file at the candidate ROOT is ignored and any SKILL.md pointing
      at it is a dead reference. (The authored INSTRUCTIONS must state this.)
    * the four edit classes (use as MANY as apply each iteration, not a single pick): (1) the
      description/trigger — make the right skill fire for the task's phrasing; (2) the body —
      fix the step the agent keeps skipping (e.g. docx split-placeholder handling, xlsx formula
      recalc, pdf form fields), keep it within budget and imperative; (3) references — factor
      rarely-used detail out of the body (or ADD a new reference), one level deep with explicit
      "load when" pointers; (4) scripts — bundle a NEW deterministic helper under scripts/ (and
      tell the agent to execute it) whenever the trace shows the agent re-implementing or
      botching the same transform; prefer a script the agent RUNS over prose it may skip. Each
      edit must keep the package a VALID skill (validate via the capability's run.py/check).
      The optimizer can run Bash in its workdir, so it must VERIFY a new/edited script by
      RUNNING it on the failing task's inputs before shipping — an unverified script is a guess.
      (Requires the optimizer command to allow Bash — set in optimizers/registry.yaml.)
    * BREADTH per iteration: diagnose EVERY failure cluster across the trajectories and ship a
      fix for as many as pass REAL/SAFE/VERIFIED in ONE candidate (improve multiple skills'
      bodies + references + scripts + descriptions together), each scoped to not regress a
      currently-passing task. A single one-line edit is an under-used iteration.
    * NON-OVERFITTING guardrail: every edit must GENERALIZE across the task class — never hardcode
      a task-specific filename/value/answer into a skill. Skills are used many times; fiddly
      task-specific rules hurt the held-out gate.
    * CROSS-ITERATION files: read ./LEDGER.md + the whole ./JOURNAL.md + ./RUNMAP.md +
      ./prior_iterations/ FIRST. NOTE the JOURNAL model (framework-owned): each optimizer entry
      is INTENT only, and the framework stamps a RESULT line below it (ACCEPTED/REJECTED · Δ ·
      exact tasks fixed/broke) — the RESULT lines are the truth of what worked; if the latest
      RESULT is REJECTED its batch was reverted, so keep the edits NOT in its broke={…} and
      drop/redesign those that were (don't resubmit, don't abandon the cluster). Each iteration
      fill ./PROCESS.md (ranked clusters with KNOWLEDGE/BEHAVIORAL/CAPABILITY-GAP tags, every
      edit + class, verify-the-fix, what to preserve, what was skipped) and APPEND your INTENT
      entry to ./JOURNAL.md. PREFER CODE: a BEHAVIORAL miss (agent knows the step but skips it)
      is fixed by a script the agent RUNS, not another prose rule it will skip; build the
      script THIS iteration, don't defer it.
    * use the two-phase subagent pattern where helpful (Phase 1: one read-only diagnose subagent
      per failing task → tight issue list; Phase 2: one edit-subagent per skill in its own
      worktree → merge into ONE candidate).

# 6. BUDGET / GATE
- algorithm:        hill-climb  (--focus all)
- max_iterations:   10          num_trials: 1
- per-iteration optimizer $ cap:  optimizer_usd_per_iter 40   (claude --max-budget-usd, CLI-enforced; OPTIMIZER ONLY)
- optimizer_max_turns: 200      (generous; the $ cap is the real per-iteration ceiling)
- max_optimizer_usd: 400        max_usd: 600   (total ceiling incl. the sonnet docker rollouts)
- gate:             paired (per-task paired SE — banks real 1-task gains), k_se 0.2
- store:            git          (every iteration committed for an inspectable process)
- note:             Docker rollouts are slow; run the full optimization in the background.
```

> The bundled `examples/skillsbench/` is the **result** of following this prompt: the
> adapter (`adapters/adapter.py`), the Anthropic-gateway env shim, the seed skills
> (`seed_capability/{docx,pptx,xlsx,pdf}/`), and the optimizer instructions
> (`.capevolve/project/optimizer/INSTRUCTIONS.md`) are what the intake /
> implement-and-check flow produced. `setup.sh` is the executable transcript of that
> onboarding (clone skillsbench, install benchflow, scaffold via intake, wire the
> adapter + skills injection + scoring, `cap-evolve check`); `run.sh` runs the full
> optimization with the live dashboard. See `DEMO.md`.
