# JOURNAL — optimizer handover (append-only, whole run)

YOU (the optimizer) own this file. It is the running, accumulating handover across ALL iterations — accepted AND rejected — and it is NEVER reset. Each iteration you APPEND one new entry at the bottom (under the marker line); you do NOT edit or delete earlier entries. Read the whole journal before proposing, so you build on EVERY prior attempt (not just the last accepted one) and never re-test a refuted idea.

You CANNOT know your own gate result while you write — the harness scores you AFTER you stop and stamps a **RESULT** line (outcome + Δ + the EXACT tasks you broke/fixed) right below your entry. So do NOT write 'what worked' as a guess. To learn what actually worked, READ the framework RESULT lines of prior entries (and LEDGER.md): an entry whose RESULT says `rejected` with `broke={...}` tells you which specific edits to drop or redesign — its diff.patch is in ./prior_iterations/<id>/.

Append your entry for THIS iteration below the marker, using this shape (INTENT only — the framework appends the RESULT):

    ## Iteration <your candidate id> — <one-line headline of what you tried>
    - Changes I made (1 line per edit; name the file/tool + cluster it targets):
    - Per change, the EXPECTED effect + why it's safe (which failing task it should fix;
      why no passing task changes behavior):
    - Building on prior RESULTS: which prior entries' broke/fixed I used, and what I
      did NOT re-try because a prior RESULT showed it regressed (cite ids):
    - Refuted hypotheses (a prior RESULT proved this is NOT the fix — never re-test):
    - High-value clusters still NOT cracked (and the guard/tool designs already tried):
    - Plateau signal (are the last few RESULTs flat/negative? if so, which LEVER to switch
      to — e.g. a NEW composite tool instead of another guard, or prompt instead of code):
    - Focus next iteration:

## Iteration cand_0001 — bundle a verified ACOPF report-builder + fix losses/precision reporting rules
- Changes I made:
  - NEW SCRIPT `ac-branch-pi-model/scripts/build_report.py` — assembles report.json from a solved point; sets `total_losses_MW = total_generation_MW − total_load_MW` and writes vm/va/pg/qg at full precision; reuses `branch_flows.py` for feasibility + top-10 loading. (clusters: losses + power-balance)
  - BODY `ac-branch-pi-model/SKILL.md` — added "Assembling the ACOPF report.json" section (run build_report.py, execute intent) + explicit losses-definition & full-precision rules for hand-built reports.
  - BODY `casadi-ipopt-nlp/SKILL.md` — added "Reporting a solved solution" subsection (losses = gen − load; full precision) + failure-mode bullet + pointer to build_report.py, for when the agent builds the report inside its solve script.
- Expected effect + why safe:
  - Fixes `test_internal_consistency_losses` (t3,t5): they reported branch-only losses 423.88 vs gen−load 425.12 (Δ1.24>1.0). Definition is now explicit + scripted. Fixes `test_power_balance_acopf` (t2): over-rounded voltages → mismatch>1MW; full precision removes it.
  - SAFE: all edits additive; passing trials t0,t1,t4,t6 ALREADY report losses=425.12 at full precision, so the script/prose produce identical-quality output — no behavior change on them. Only ac-branch-pi-model + casadi-ipopt-nlp edited (both already used by this task); power-flow-data untouched. No hardcoded values — general to any MATPOWER net.
  - VERIFIED end-to-end: solved the real 300-bus net with casadi/IPOPT, ran build_report.py, ran the ACTUAL verifier → 22 passed, 1 skipped, 1 deselected (slow benchmark, known-pass); both previously-failing tests now pass.
- Building on prior RESULTS: none (baseline only).
- Refuted hypotheses: none yet.
- High-value clusters still NOT cracked: verifier-side 240s timeouts (t7,t8,t9) — the verifier re-solves the full ACOPF in-test; not fixable via skills (score feedback labels it uncontrollable noise). If it persists it caps achievable reward at ~0.7.
- Plateau signal: n/a (first iteration).
- Focus next iteration: if losses/precision clusters are ACCEPTED, remaining loss is purely the infra timeouts; otherwise re-examine whether the agent adopts build_report.py (may need a stronger body directive or moving the report step earlier in the solve skill).

> **RESULT (framework, objective):** ACCEPTED (new champion) · val=0.500 Δ=+0.100 · fixed={—} · broke={—}.
<!-- cand_0001: ACCEPTED val=0.500 Δ=+0.100 -->

## Iteration cand_0002 — ship the intended shared office skills + a general reference-key reconciliation rule (fix invoice-fraud null-PO)
- Changes I made (all additive; the 3 ACOPF skills untouched):
  - NEW `pdf/`, `xlsx/`, `fuzzy-match/` — copied the canonical shared office skills into the
    candidate. The adapter deploys every sub-dir with a SKILL.md and strips the task's own
    skills, so office task draws (t5–t9) previously ran with NO relevant skill support.
  - `fuzzy-match/SKILL.md` — added "Reconciling records against reference tables": normalize
    entity suffixes before matching; **an unresolved/malformed foreign key not found in the
    reference table is reported as `null`, never echoed raw**; apply criteria strictly in
    priority order (checks needing the reference row run only after the key resolves).
- Per-change expected effect + why safe:
  - Fixes t9 (invoice-fraud-detection `::TestOutputs::test_content`): the agent output
    `po_number:"PO-INVALID"` for Invalid-PO rows; GT expects `null` (all 5 Invalid-PO rows are
    null). Everything else in its report already matched GT counts/fields. The new null-key
    convention produces the asserted-on result. VERIFIED: ran corrected logic on the real
    invoices.pdf/vendors.xlsx/purchase_orders.csv → actual verifier assertions PASS 50/50.
  - SAFE: fuzzy-match/pdf/xlsx descriptions are entity-matching / file-type scoped → they do
    NOT trigger on ACOPF, so t1 and the timeout draws are unchanged. The null-key rule is
    conditional on "output schema requires a reference id that must exist" → t5–t8 (field
    diffs / form fills) don't hit it, so passing office tasks don't regress. No hardcoded
    filenames/values/answers; the `PO-\d+` regex is explicitly labelled illustrative.
- Building on prior RESULTS: cand_0001 (ACCEPTED, ACOPF losses/precision) — kept its ACOPF
  skills fully intact. From the reference office-skills run (examples/skillsbench/run_full)
  rejected.jsonl: cand_0007 shipped a full deterministic invoice-fraud helper SCRIPT and was
  REJECTED (Δ=+0.000, saturated 0.714 baseline) → I did NOT re-try a task-specific end-to-end
  fraud script; encoded the fix as general reconciliation prose in the fuzzy-match skill.
- Refuted hypotheses: task-specific deterministic fraud script does not clear the gate
  (ref-run cand_0007) — avoid re-testing; and it overfits the held-out gate.
- High-value clusters still NOT cracked: ACOPF verifier-side 240s timeouts (t0,t2,t3,t4) —
  verifier re-solves the ACOPF in-test on limited CPUs; not fixable via skills (flagged
  uncontrollable). These cap achievable reward regardless of edits.
- Plateau signal: n/a (2nd iteration). If this is REJECTED because the office draws re-sample
  away, the lever to switch to is making the office skills' triggering/scope even tighter, or
  verifying whether the gate's val set is stable across iterations.
- Focus next iteration: confirm the office skills deploy and are consulted; if the null-PO
  prose doesn't reliably flip the agent, consider a SMALL general reconciliation helper (not a
  task-specific end-to-end script) under fuzzy-match/scripts with execute intent.

> **RESULT (framework, objective):** REJECTED (champion unchanged) · val=0.300 Δ=-0.200 · fixed={—} · broke={—}. — its WHOLE batch was reverted; re-introduce only the edits that did NOT break a task above, dropping/redesigning the ones that did.
<!-- cand_0002: rejected val=0.300 Δ=-0.200 -->

## Iteration cand_0003 — surgical, single tightly-scoped fuzzy-match reconciliation skill (fix invoice-fraud null-PO) WITHOUT the pdf package that sank cand_0002
- Changes I made:
  - NEW `fuzzy-match/SKILL.md` (single skill) — reconcile transactional records against
    authoritative reference tables (approved-vendor lists, PO registers, customer masters).
    Core rule: an **unresolved/malformed/absent foreign key is reported as `null`, never the
    raw string**; plus normalize-before-match, strict priority order, and difflib/rapidfuzz
    how-to. Targets the t9 invoice-fraud cluster.
  - I did NOT add `pdf/` or `xlsx/` this time (see below).
- Expected effect + why safe:
  - Fixes t9 `::TestOutputs::test_content`: agent wrote `po_number:"PO-INVALID"` for an
    Invalid-PO row; GT (and the task prompt: "if the PO is missing, set it to null") expects
    `null`. Assertion failed `'PO-INVALID' == None` on page 4. The null-key convention
    produces exactly the asserted result; everything else in t9's report already matched GT.
    VERIFIED: reproduced the validate-then-membership rule → PO-INVALID/malformed/absent → None,
    valid keys preserved.
  - SAFE: description front-loaded to invoice/reference-table reconciliation + fuzzy
    vendor-name matching + foreign-key validation → matches t9's wording, NOT the employee-diff
    tasks (t5/t8 "deleted/modified employees between two files") nor the PDF-form tasks
    (t6/t7). Null-key rule is conditional (only when a foreign key fails to resolve) so it is
    inert even if loaded elsewhere. ACOPF skills + trials (t0–t4) untouched. No hardcoded
    filenames/values/answers; the `PO-\d+` regex is explicitly labelled illustrative.
- Building on prior RESULTS: cand_0001 (ACCEPTED — ACOPF losses/precision) kept fully intact.
  cand_0002 (REJECTED, val 0.300) added `pdf/` AND `fuzzy-match/`; I attribute the regression
  to the broad `pdf/` trigger firing on the PASSING PDF-form tasks (t6/t7) — so I dropped
  `pdf/`/`xlsx/` and shipped ONLY the reconciliation skill, with a TIGHTER trigger than
  cand_0002's generic "matching entity names across datasets" (which risked the employee-diff
  tasks). This is the minimal-blast-radius version of the same cluster fix.
- Refuted hypotheses (do NOT re-test): full task-specific deterministic fraud SCRIPT (ref-run
  cand_0007, rejected — overfits gate); adding broad `pdf/`/`xlsx/` packages alongside the
  fix (cand_0002, val −0.200 — regresses passing office tasks).
- High-value clusters still NOT cracked: ACOPF verifier 240s timeouts (t0,t2,t3,t4) — verifier
  re-solves the ACOPF in-test on limited CPUs; not fixable via skills. Caps reward ~0.6.
- Plateau signal: cand_0002 was the first negative; this iteration switches LEVER from
  "add many office skills" to "one tightly-scoped skill, minimal blast radius". If this is
  also rejected, the office-skill direction is likely futile (office tasks pass without skills)
  and the plateau is the uncontrollable ACOPF-timeout noise floor.
- Focus next iteration: if this is REJECTED with broke={} again, treat the val as
  noise-dominated (4/10 uncontrollable) and stop chasing t9 via skills; if it fixed t9 but
  didn't clear the bar, the null-PO rule may not reliably trigger — consider whether the skill
  is being consulted at all before adding more surface.

> **RESULT (framework, objective):** ACCEPTED (new champion) · val=0.900 Δ=+0.400 · fixed={—} · broke={—}.
<!-- cand_0003: ACCEPTED val=0.900 Δ=+0.400 -->

## Iteration cand_0004 — reinforce the null-PO convention with a RUNNABLE finalizer + worked example (fix flaky invoice-fraud t7)
- Changes I made (1 line/edit):
  - NEW SCRIPT `fuzzy-match/scripts/nullify_unresolved_keys.py` — general report finalizer:
    nulls any reference-key field whose value isn't in a supplied valid-key set (`--set field=@file`
    or comma-list); leaves matches untouched. Targets the invoice-fraud null-PO cluster.
  - BODY `fuzzy-match/SKILL.md` — added a worked example (`reason="Invalid PO"` WITH `po_number=null`
    vs the wrong leaked-placeholder row) and a "Finalize the output" step directing the agent to RUN
    the finalizer as the LAST step (execute intent, "do not reimplement"), warning that inline
    null-checks are easy to botch.
- Expected effect + why safe:
  - Fixes t7 `::TestOutputs::test_content` → `assert 'PO-INVALID' == None` on page 4. The trace shows
    the agent classified reason correctly but wrote a botched inline null-check
    (`po if po != "PO-INVALID" or True else po` — a no-op) so the raw placeholder leaked. Running the
    deterministic finalizer as a final pass produces the GT-passing null. VERIFIED by running the
    script on a reproduced report → page 4 → null, valid PO preserved, existing null preserved.
  - SAFE: only `fuzzy-match` is touched; the 9 passing trials this draw (file-org, ACC, retrieval,
    Three.js — confirmed via their prompts) never load it. Finalizer only nulls non-valid values, so
    it is a no-op on a correct report. No task-specific filename/value/answer hardcoded.
- Building on prior RESULTS: built on cand_0003 (ACCEPTED, 0.900) — kept its null-PO prose and
  reinforced it with code (prose alone proved flaky). Did NOT re-add `pdf/`/`xlsx/` (cand_0002
  REJECTED −0.200).
- Refuted hypotheses (not re-tested): full end-to-end task-specific fraud SCRIPT (ref-run cand_0007,
  rejected/overfit) — my script is a general finalizer, not that; broad `pdf/`/`xlsx/` packages
  (cand_0002 −0.200).
- High-value clusters still NOT cracked: none addressable this draw — the val is a resampled mixed
  pool and only the invoice-fraud task fails; the flakiness is the botched inline null-check.
- Plateau signal: champion has been flat at the invoice-fraud cluster since cand_0003; this switches
  the LEVER from prose to a runnable script to make the good behavior consistent.
- Focus next iteration: if still flaky, the agent may not adopt the finalizer — consider directing
  the WHOLE reconciliation output through a bundled step earlier, or check whether fuzzy-match is
  consulted at all on the invoice draw.

> **RESULT (framework, objective):** REJECTED (champion unchanged) · val=0.800 Δ=-0.100 · fixed={—} · broke={—}. — its WHOLE batch was reverted; re-introduce only the edits that did NOT break a task above, dropping/redesigning the ones that did.
<!-- cand_0004: rejected val=0.800 Δ=-0.100 -->
