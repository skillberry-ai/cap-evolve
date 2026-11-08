# Optimize the capability — ship several REAL, SAFE, VERIFIED fixes this iteration

{{TARGET_READER}}

{{FOCUS_SUMMARY}}

GOAL: raise the eval score as much as you can THIS iteration, then STOP (the harness
re-scores you — don't run evaluation yourself). The edit surface is the agent's TOOLS
ONLY — the files `my_skill/scripts/<tool>.py`. The system prompt / airline policy is NOT editable;
prose a tool needs goes in that tool's docstring.

Make **AS MANY real fixes as you can this iteration — solve many issues across many
trajectories, not just the biggest one.** A timid one- or two-edit iteration is an
under-used iteration: diagnose EVERY failure cluster in `./trajectories/` and ship a fix
for each one that passes the three tests below. Breadth is the goal — the more distinct
failing clusters you fix in this ONE candidate, the larger the gain.

The ONLY brake on breadth is regression: every edit must pass all three tests, because a
single speculative edit that breaks a passing task can sink an iteration of good work (it
did in prior runs). So the discipline is "many fixes, each one real and safe" — NOT "few
fixes". Do not stop at the first cluster; work through them all.

## PREFER CODE (this is where prior iterations fell short)
A strong iteration changes the tool CODE — many edits across many tools. The recurring
failure mode to avoid: an iteration that (at most) rewords a few docstrings, leaving the
logic in `my_skill/scripts/<tool>.py` untouched. That is an under-used iteration even if it
"covers" several clusters, because:
- **A BEHAVIORAL miss is NOT fixed by a prose rule.** When the agent already "knows" the
  rule but skips it (doesn't call get_*_details before acting, acts on a guess, re-asks
  after consent, miscomputes a total) — adding ANOTHER prose rule it will skip the same
  way does nothing. Enforce it in CODE: an in-body guard / validation / computation in
  the EXISTING tool, or a composite tool that performs the whole action. Prose is reserved
  for genuine KNOWLEDGE gaps (a fact/format/criterion the agent cannot derive).
- **Do NOT defer a capability-gap cluster** ("would need a compute tool — next iteration").
  If a cluster needs a compute/validation/composite tool, BUILD it THIS iteration — that
  is the highest-leverage edit available, not something to postpone.
So for each cluster, first ask "can this be enforced in tool code?" — if yes, do
that; only fall back to a docstring rule for a true knowledge gap. Expect your
`my_skill/scripts/<tool>.py` diff to contain real CODE (guards, validations, new/changed tool bodies), not only
docstring text — across SEVERAL tools, not one.

## THIS BENCHMARK: tau2-bench airline (vanilla upstream), blackbox delivery
- **What you edit.** The capability is the airline agent's TOOL SURFACE, delivered as the
  Skillberry store skill `my_skill`. Every file `my_skill/scripts/<tool>.py` becomes ONE tool that
  the Skillberry Proxy-Agent injects into the agent's LLM calls. The 14 seed files mirror
  tau2's 14 airline tools. The system prompt / airline policy is NOT part of the capability.
- **`./guidance/tools/SKILL.md`** describes a `tools.json` artifact. Its improvement TYPES
  (guards, normalization, computation, composite tools, enriched errors, add/remove tools,
  sharper descriptions) all apply here; its `tools.json` FORMAT does not — the artifact is
  the Python files under `my_skill/scripts/`.
- **Trajectories.** `./trajectories/` holds one JSON per rollout whose `trace` is the FULL
  tau2 simulation: `messages` (the conversation, the `env_<tool>` primitive calls each
  wrapper made — recorded under the tau2 tool name — and any NEW/compound tool calls) and
  `reward_info` with the per-check breakdown (`db_check`, `action_checks`,
  `communicate_checks`, ...) and the expected (gold) actions. Use it to localize the exact
  defect; tool calls and results are paired BY POSITION (ids are empty). Keep every edit
  GENERAL — never hardcode a task's id or value (see NON-OVERFITTING).
- **Score.** `reward_info.reward` in [0,1]; airline reward_basis is DB + COMMUNICATE: the
  final DB must equal the gold DB and the required info must be stated to the user.
- **Data model.** tau2's airline `data_model.py` is at `./guidance/sources/data_model.py`.

## BLACKBOX DELIVERY RULES (break one and the tool silently breaks — no error)
1. ONE public top-level `def` per file, named EXACTLY like the file. Every top-level `def`
   becomes its own tool, so helpers must be NESTED inside it and `_`-prefixed.
2. The signature + docstring ARE the schema the model reads (Google style `Args:`). The
   SEED's 14 signatures are FROZEN (the scorer matches actions by name and argument). A NEW
   tool uses str/int/list/dict parameters by default; for a genuinely structured parameter,
   copy the class from `./guidance/sources/data_model.py` into that tool's OWN file WITH its
   dependencies — only value models + `typing`/`pydantic` imports, never `tau2.*`, never a
   DB class. The `def` line stays on ONE line; no self-referential model.
3. Reach the environment ONLY by calling an `env_<tool>` primitive BY BARE NAME (no
   import): `env_book_reservation`, `env_calculate`, `env_cancel_reservation`,
   `env_get_flight_status`, `env_get_reservation_details`, `env_get_user_details`,
   `env_list_all_airports`, `env_search_direct_flight`, `env_search_onestop_flight`,
   `env_send_certificate`, `env_transfer_to_human_agents`,
   `env_update_reservation_baggages`, `env_update_reservation_flights`,
   `env_update_reservation_passengers` — same parameter names as the seed tool. A
   primitive returns the PARSED result (dict/list/str) on success and an error STRING
   (e.g. "Error: ...") on a tool-level failure.
4. NEVER call `_make_api_call`, NEVER edit `primitive_tools/`, leave `my_skill/SKILL.md`
   EMPTY (all three are sealed; an edit voids the candidate).
5. A new/composite tool is a NEW FILE under `my_skill/scripts/` that calls primitives by
   bare name; removing a tool means deleting its file.

## The THREE TESTS every change must pass (this is the whole game)
Before you keep any edit, confirm all three. Drop any edit that fails even one.
1. **REAL** — it targets a cluster that is FAILING in THIS iteration's `./trajectories/`
   (reward 0, partial-credit, or communication/omission). Never edit for a hypothetical
   problem, never touch a path only used by already-PASSING tasks.
2. **SAFE (bounded blast radius)** — the real regression question is *behavioral*:
   **would this edit change what the agent DOES on ANY currently-passing task?** Not
   "does a passing task call this tool" — "does the agent now take a different action,
   or newly ACT where it correctly REFUSED / escalated". Two blast-radius classes:
   - **BOUNDED** — an in-body guard/computation that fires ONLY on the exact violating
     condition. Only already-failing inputs hit it; passing tasks are untouched by
     construction. This is the SAFE default — prefer it.
   - **UNBOUNDED** — any edit to a GLOBAL decision/permission/refusal rule, in a guard or
     a docstring (loosening "X may do Y", broadening who may take an action, relaxing a
     refuse-and-escalate rule). It changes behavior across the ENTIRE decision class,
     including tasks where the stricter/original behavior was the gold answer. Allowed
     ONLY if the new behavior is correct for EVERY task in that class AND you have read
     the currently-passing tasks in the class and confirmed none relied on the old
     behavior. Otherwise it is a guaranteed regression — encode the discriminating
     CONDITION instead (see the DECISION / PERMISSION lever below).
   Name the passing tasks in each edit's blast-radius class and state which class it is.
   A regression wastes the whole candidate (the gate rejects a net-zero), not one task.
3. **VERIFIED** — you have shown it actually fixes its target (see VERIFY-THE-FIX). An
   edit you cannot verify is a guess — drop it.

Quality AND breadth: ship every fix that passes the three tests — the more clusters you
cover safely, the bigger the gain. The only edits to leave out are the speculative ones
(an edit that fails a test), not real fixes you ran out of patience for. Don't re-add
anything `LEDGER.md` / `JOURNAL.md` show was already tried and rejected.

## Read these first (everything is in this working directory)
- **`./guidance/<cap>/SKILL.md` for EACH selected capability — READ IT IN FULL before you
  edit; it is the MENU of improvement TYPES available to you.** Each capability skill lists
  the concrete kinds of change you can make (for a tools capability: in-body validation
  guards, normalization, computation, composite/atomic-write tools, loop/workflow tools,
  enriched return values + actionable errors, add/remove tools, sharpened descriptions).
  Do not invent change types from memory — take them from the
  skill, and deliberately apply MULTIPLE DIFFERENT types this iteration (e.g. several
  in-body guards + a compute tool + enriched errors + a couple of docstring rules), matching
  each cluster to the strongest type the skill describes for it. (Tool code? also read
  `./guidance/sources/` for the data models/types so your code is correct.)
- `./guidance/diagnose/SKILL.md` — the failure-clustering method. Use it.
- `./trajectories/` — the FULL traces of the current best candidate (the step you build
  on). The `{{FAILURES}}` block below summarizes them with argument-level feedback — read
  the actual traces for the clusters you'll fix, don't rely on the summary alone.
- `./LEDGER.md` — FACTS (read-only): every prior iteration's outcome + the exact tasks it
  broke/fixed. Your SAFE test starts here — never re-introduce a change that broke a task.
- `./JOURNAL.md` — the accumulating handover. Each entry is the optimizer's INTENT, and
  directly below it the framework stamps a **RESULT** line (objective: ACCEPTED/REJECTED ·
  Δ · the exact tasks fixed/broke). The RESULT lines — not the intent — are the truth of
  what worked: read them all before proposing. If the most recent RESULT is **REJECTED**,
  its batch was reverted; read that entry's `./prior_iterations/<id>/diff.patch`, keep the
  edits that did NOT appear in its `broke={...}`, and DROP or REDESIGN the ones that did —
  do NOT resubmit the whole rejected batch, and do NOT abandon the cluster. APPEND your new
  entry (intent only) below the marker; never edit earlier entries or re-try a refuted idea.
- `./RUNMAP.md` + `./prior_iterations/<id>/` — EVERY prior iteration's (accepted AND
  rejected) PROCESS.md + diff.patch. Read the one(s) that touched a cluster you're about to
  work on, so you build on what worked and avoid repeating what regressed.
- `./PROCESS.md` — your REQUIRED explainability file for THIS iteration (template inside).
- `./guidance/optimizer/<name>.md` — your agent's subagent/parallelism features (optional).
{{BENCH_REPO}}

## Process (do this, then STOP)
**Parallelism:** {{PARALLEL_NOTE}}
1. Read your capability SKILL(s) + the diagnose method + the cross-iteration files
   (LEDGER facts, JOURNAL handover, RUNMAP for clusters you'll touch).
2. Diagnose THIS iteration's `./trajectories/` ONLY (not stale signatures). Cluster ALL
   failures by shared root cause — total, partial-credit, AND communication/omission.
   RANK clusters by LEVERAGE = (# failing tasks × trials × score recoverable), biggest
   first — but plan to fix ALL of them this iteration, not only the top few.
3. For EACH cluster, pick the strongest improvement TYPE from the capability SKILL(s)
   (cross-check the FAILURE TYPE section next) and draft the edit. Across the iteration
   use MULTIPLE different types from the skills, not the same one repeatedly. Run each
   edit through the THREE TESTS; keep it only if it passes all three.
4. Ship every passing edit together in this ONE candidate — cover as many clusters as you
   can SAFELY (that is the win), and never include an edit that fails a test.
5. Fill `PROCESS.md` and APPEND your entry to `JOURNAL.md`. STOP.

## Choose the lever by FAILURE TYPE
Pick the strongest lever YOUR capability's edit space offers (see `./guidance/<cap>/`).

- **RULE VIOLATION** — the agent breaks a rule/precondition/formula it could already
  follow. **Default strong lever (tools): move the rule INTO THE CODE BODY of the
  EXISTING tool that governs it** — an in-body validation / normalization / computation
  that raises an ACTIONABLE error or returns the corrected value, scoped to fire ONLY on
  the violating condition. This is the highest-yield, lowest-regression edit and is what
  drove the best prior results — reach for it first. *Example:*
  ```
  def book(record_id, amount, payment_id):
  +   methods = {m["id"] for m in get_record(record_id)["payment_methods"]}
  +   if payment_id not in methods:                      # fires only on the violation
  +       raise ValueError(f"payment_id {payment_id!r} not on file; available={sorted(methods)}")
      return _backend.book(record_id, amount, payment_id)
  ```
- **CAPABILITY GAP / ACTION STALL** — the agent has NO reliable way to do the thing (a
  hard-ZERO cluster needing a real compute / composite / discriminating-predicate tool),
  or it narrates/confirms a multi-step action then never executes it. **Prose does
  NOTHING for a hard zero** — a 0.00 task stays 0.00 after any docstring reword;
  it needs a TOOL the agent will CALL that changes the graded state. (tools) ADD a NEW
  code-bearing tool that closes the gap — a composite atomic-WRITE tool whose body
  performs the whole action via the existing primitives (then REMOVE the raw primitives
  so it can't be skipped), or a loop/validation tool. Add a new tool ONLY when it closes
  a real gap AND the agent will call it AND it changes the graded outcome — NOT a
  read/compute/summary helper that a guard or a docstring line would subsume, and never to
  hit a quota.
- **KNOWLEDGE GAP** — a format/criterion/fact the agent genuinely cannot derive →
  prose: a precise docstring rule. Don't restate a rule the agent already has;
  that's a rule-violation (use code), not a knowledge gap.
- **DECISION / PERMISSION (ACT vs REFUSE)** — the agent made the wrong call on a
  decision the policy governs: it ACTED where it should have refused/escalated, or
  refused where it should have acted. **This is the most dangerous cluster to fix
  wrong.** NEVER loosen, broaden, or alter a GLOBAL decision/permission/refusal rule in
  a docstring or guard to fix it — a global change (e.g. "restricted records MAY now be
  modified") flips behavior for the WHOLE class and regresses every currently-passing task where
  the original, stricter behavior was the gold answer (this exact mistake sank a prior
  run). Instead encode the EXACT discriminating CONDITION that separates the qualifying
  cases, **ideally in CODE** — an in-body guard on the tool that owns the action, which
  refuses/raises ONLY when the precise policy predicate is/isn't met (bounded blast
  radius: only the qualifying cases change). If it truly cannot be code, add an ADDITIVE
  docstring rule that NARROWS (states the exact predicate) — never one that LOOSENS.

Also improve **tool RETURN values / error messages** (actionable: what's wrong + valid
options + next step) when a recoverable error stranded the agent — this is high-leverage
and low-risk. Never delete a needed rule; change/consolidate instead.

## VERIFY-THE-FIX (do this for EACH kept edit — it satisfies the VERIFIED + SAFE tests)
- **In-body guard / computation:** run the tool body on the EXACT args from the failing
  trace and confirm it fires / returns the corrected value. THEN run it on the args from
  1–2 currently-PASSING tasks that use the same tool and confirm it does NOT fire (the
  blast-radius / SAFE check). A guard that never fires on the failing task is dead code;
  one that fires on a passing task is a regression — drop or rescope either.
- **Decision / permission edit (docstring OR guard):** the SAFE check is BEHAVIORAL, not
  argument-level. Enumerate the currently-passing tasks in the SAME decision class (same
  permission/refusal rule) and confirm the edit would NOT flip the agent's action on any
  of them — in particular that it does not make the agent newly ACT where a passing
  task's gold answer was to refuse/escalate. If you cannot enumerate and check that
  class, the edit is UNBOUNDED and unverified — replace it with a coded
  discriminating-condition guard scoped to the violating cases only.
- **New tool:** construct the inputs the agent SHOULD have passed (from the trace's
  observed state) and run the tool body; confirm it completes the action end-to-end.
- **Docstring:** confirm the missing fact is now stated, general, and unambiguous.

Record one line per edit in PROCESS.md, e.g.
`trace <task> arg x=<bad> → guard raises "<msg>"; passing tasks <ids> → guard does NOT fire`.
An edit with no verification line is unverified — verify it or drop it.

## NON-OVERFITTING (every edit must GENERALIZE)
Every edit encodes a GENERAL rule that holds across the whole class of inputs — NEVER a
literal that special-cases one task (its id, target, name, or expected answer). A guard
fires on the general condition ("the id is not in the user's records", "the record is in
a state that forbids this action"), NOT `if record_id == "<TASK_SPECIFIC_ID>"`. ALLOWED: constants the policy/domain
defines (the policy's stated current date, a fixed fee/threshold, a domain enum). Use
per-task specifics and any ground-truth in the traces ONLY to understand the failure
CLASS, then write the general fix.

## Handover (REQUIRED before you STOP)
- **PROCESS.md** (this iteration): the ranked cluster list (with leverage + RULE/GAP/
  KNOWLEDGE tag), every kept edit + its lever, the VERIFY-THE-FIX + blast-radius line per
  edit, what you deliberately skipped and why, and (if you used subagents) that you did.
- **DIAGNOSIS.json** (OPTIONAL but recommended): a machine-readable diagnosis file that makes
  your diagnosis available to the dashboard. If absent, the dashboard will parse PROCESS.md
  tables when present, or show only outcome data. The schema:
  ```json
  {
    "candidate": "cand_NNNN",
    "headline": "Brief summary of this iteration's strategy",
    "clusters": [
      {"id": "A", "name": "Short cluster name",
       "detail": "Root cause explanation", "tasks": ["task-id", ...],
       "scope": "BOUNDED|WIDESPREAD|SYSTEMIC", "latent": false,
       "tag": "KNOWLEDGE|BEHAVIORAL|CAPABILITY-GAP"}
    ],
    "edits": [
      {"id": "E1", "title": "What this edit does",
       "files": ["my_skill/scripts/book_reservation.py"], "lever": "CONTRACT|KNOWLEDGE|BEHAVIORAL|...",
       "clusters": ["A"], "blast_radius": "BOUNDED|MODERATE|WIDE",
       "verified": "How you tested it"}
    ],
    "skipped": [{"title": "What was skipped", "reason": "Why"}],
    "techniques": ["technique 1", "technique 2"]
  }
  ```
  Validation is advisory only and never blocks an iteration. Warnings are recorded when a
  task ID is not in the val split, an edit references a missing cluster, or an edit
  references a file that does not exist in the candidate.
- **JOURNAL.md** (append ONE entry below the marker; never edit earlier entries). Write
  INTENT only — you cannot know your gate result; the framework stamps the RESULT below
  your entry: the changes I made (1 line/edit, naming the file/tool + cluster) · the
  EXPECTED effect + why each is safe · which prior RESULTS I built on and which regressing
  edits I did NOT re-try (cite ids) · refuted hypotheses (a prior RESULT disproved — never
  re-test) · high-value clusters not yet cracked + designs already tried · plateau signal +
  which lever to switch to · focus next iteration.

{{FAILURES}}
{{PASSING}}
{{CAP_BRIEF}}
{{ALGO_BRIEF}}

## Self-check before STOP
- Every kept edit passes the THREE TESTS (REAL, SAFE, VERIFIED) and has its
  verify + blast-radius line in PROCESS.md. Drop any that doesn't.
- You read each selected capability's `./guidance/<cap>/SKILL.md` and applied MULTIPLE
  DIFFERENT improvement types it describes (not the same lever repeated).
- You addressed EVERY failing cluster you found this iteration (not just the top few),
  and did NOT defer a capability-gap cluster to "next iteration" — you built the tool now.
- Your `my_skill/scripts/<tool>.py` diff contains real CODE (in-body guards / validations / new or
  changed tool bodies / a composite tool) across SEVERAL tools — NOT just docstring text. If
  the only change is documentation, you under-used the iteration: convert the
  behavioral / rule-violation / capability-gap clusters into code and try again.
- Every BEHAVIORAL cluster (agent knows the rule but skips the action) is fixed in CODE,
  not by adding another prose rule it will skip the same way.
- You shipped many edits across many tool files — and you did NOT pad with
  speculative/cosmetic edits or re-add anything already rejected (check LEDGER/JOURNAL).
- For RULE-VIOLATION clusters on a tools capability, you used in-body guards on the
  existing tools (the default strong lever), not loose prose.
- For DECISION / PERMISSION clusters you did NOT loosen or alter a global decision/
  permission/refusal rule; you encoded the discriminating CONDITION (in code where
  possible) and confirmed it does not flip the action on any passing task in the class.
- Every docstring edit is ADDITIVE knowledge the agent lacked (a fact/format/narrowing
  predicate) — never a change to a decision the agent currently gets right.
- For any hard-ZERO cluster you shipped a real tool the agent will call (prose does
  nothing for a zero).
- Any new tool closes a real gap, will be called, and changes the graded outcome — not a
  helper a guard subsumes, not quota-filling.
- No edit hardcodes a task-specific id/value/date/answer.
- PROCESS.md + JOURNAL.md are filled. Keep narration minimal; don't restate these
  instructions or explore unrelated files.
