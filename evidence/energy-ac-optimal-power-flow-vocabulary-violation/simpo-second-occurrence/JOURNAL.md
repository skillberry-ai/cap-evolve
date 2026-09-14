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

## Iteration cand_0001 — make the two flaky-failure behaviors consistent (env placement + loss ratio semantics)
- Changes I made (both in `nlp-research-repo-package-installment/SKILL.md` — the only skill on any failing path; `pdf/` untouched):
  1. Part A (env, cluster t1): build the venv at the canonical `/opt/py310`, symlink it as the default `python`/`pip`, install ALL declared deps (don't drop `wandb`/`sentencepiece`-type transitive imports), and verify the target module imports + entry script runs under that same interpreter before finishing.
  2. Part B (loss math, cluster t6): reconcile paper symbols with config attribute names; do NOT re-transform an already-scaled ratio — a `*_ratio` hyperparameter (e.g. `gamma_beta_ratio`) is the full ratio, subtract it directly instead of dividing again by its components; use config defaults as-is.
- Expected effect + safety:
  - t1 failed only because it built the env at `/opt/simpo_env`; the verifier's `test.sh` `[ -x /opt/py310/bin/python ]` branch then fell back to a minimal uvx env lacking `wandb`, so its mandatory re-run of `unit_test_1.py` (imports `trl.CPOTrainer` → `import wandb`) failed — even though t1's own `loss.npz` matched gold EXACTLY. Steering the env to `/opt/py310` + full deps makes the verifier reuse the rich env. Safe: the 8 passing runs already do exactly this, so no passing behavior changes.
  - t6 failed only because it coded `logits = pi_logratios - gamma_beta_ratio/beta`; correct is `- gamma_beta_ratio`. Verified in torch: correct == gold to rtol=1e-5; t6's variant reproduces t6's wrong output. Safe: passing runs already implement it correctly; the note only removes the specific mis-scaling.
- Building on prior RESULTS: none — this is the seed's first iteration (LEDGER/RUNMAP empty).
- Refuted hypotheses: none yet. Note (NOT a fix to try): the agent's own torch version is NOT the flaky factor — t1 used torch 2.2.2 and still matched gold within tolerance; the verifier re-run even uses torch 2.1.2+cpu and reproduces gold. So don't chase torch-build pinning for reproducibility.
- High-value clusters still not cracked: none remaining — t1 and t6 are the only two failing trajectories and both are addressed. If this is rejected, next lever = convert the two body rules into a deterministic `scripts/` setup helper the agent runs (canonical-path venv + install-declared-deps + import/run verification), which is harder to skip than prose.
- Focus next iteration: read the RESULT line below; if t1/t6 not both fixed, escalate the weaker cluster from prose to a bundled script.

> **RESULT (framework, objective):** ACCEPTED (new champion) · val=0.900 Δ=+0.100 · fixed={—} · broke={—}.
<!-- cand_0001: ACCEPTED val=0.900 Δ=+0.100 -->

## Iteration cand_0002 — harden CPU-grader env install (the sole failure is an infra/mislabeled trace, not skill-fixable)
- Changes I made (1 edit; `nlp-research-repo-package-installment/SKILL.md` Part A step 3, additive sub-bullet):
  - On a CPU-only grader (this sandbox is `gpus:0`), install `torch`/`torchvision`/`torchaudio` from the CPU wheel index keeping the repo's pinned version, and DROP CUDA-build-only packages (`flash-attn`, `nvidia-*-cu12`) that no direct loss/metric unit test imports — record the deviation, don't force-build a CUDA package under the run cap. `pdf/` untouched.
- Expected effect + safety:
  - This is NOT a patch for the failing trial. t9 (the only reward-0.0 trial) is a MISLABELED / infra trajectory: its `task_id`/`input` say `simpo-code-reproduction` but its entire 46-step trace is an INVOICE-FRAUD task (invoices.pdf/vendors.xlsx/fraud_report.json) — zero SimPO/loss.npz/opt-py310 content. The agent was fed the wrong prompt, so no `loss.npz` was produced and `test_content` failed. No skill edit can solve a task the agent was never given.
  - The edit instead encodes the behavior ALL 9 passing SimPO runs already improvised (t0/t2: `torch==2.2.2+cpu` from download.pytorch.org/whl/cpu; explicitly skip flash-attn as CUDA-build-only). So it changes NO passing run's behavior; it only steers a future agent away from taking "install ALL declared deps" literally and stalling on a CUDA-only build. Generalizes (no SimPO filename/dep hardcoded) for the held-out gate.
- Building on prior RESULTS: cand_0001 ACCEPTED (fixed t1 env-path + t6 loss double-scaling). I did NOT re-touch either — all 9 real runs already pass them; re-editing would be speculative and could regress. broke={} for cand_0001, so nothing to drop.
- Refuted hypotheses: none newly refuted. Note: torch-build pinning is NOT the repro flakiness lever (proven in cand_0001).
- High-value clusters still NOT cracked: NONE that a skill can reach — the lone remaining failure is an infra mislabel, not a behavior. If future iterations still see a real (SimPO-content) env failure, escalate to a bundled `scripts/setup_repro_env.sh` (canonical /opt/py310 venv + CPU-wheel torch + filter flash-attn/nvidia + import/run verify) — but only ship it VERIFIED end-to-end (heavy install), else it's a guess.
- Plateau signal: at ceiling for skill-reachable gains on this single task (9/10 genuine passes; 10th is infra). If this is REJECTED as ~no-op, that CONFIRMS the failure is infra noise outside the edit surface — do not chase it with more SimPO edits.
- Focus next iteration: read the RESULT below; if still 0.900, treat t9 as infra and stop editing SimPO for it. Only act on a NEW cluster whose trace actually contains SimPO behavior.

> **RESULT (framework, objective):** REJECTED (champion unchanged) · val=0.300 Δ=-0.600 · fixed={—} · broke={—}. — its WHOLE batch was reverted; re-introduce only the edits that did NOT break a task above, dropping/redesigning the ones that did.
<!-- cand_0002: rejected val=0.300 Δ=-0.600 -->

## Iteration cand_0003 — the val gate is a DIVERSE suite; fix the one real failure (invoice-fraud) by adding the ACCEPTED fuzzy-match skill
- KEY REFRAME (both prior iterations were wrong about this): the champion cand_0001's val
  rollouts are NOT 10× SimPO — they are a diverse shared-skill sample (SimPO t0–t4, HR-diff
  t5/t8, PDF t6, court-form t7, invoice-fraud t9). 9/10 pass = 0.900. The lone failure t9 is a
  GENUINE invoice-fraud task (not "mislabeled infra" as cand_0002 claimed). cand_0002's −0.600
  was a different, harder random task sample (3D/drone/anonymize/PDDL) + its refuted nlp edit.
- Changes I made (1 edit):
  1. ADD `fuzzy-match/SKILL.md` (new skill in my candidate) = verbatim port of the invoice-fraud
     run's **ACCEPTED** cand_0002 fuzzy-match skill: fuzzy-match helpers + the "Reporting
     reconciled keys" section with the `report_key(source_key, reference_keys)` idiom (unmatched
     lookup key → `null`, never echo the raw source token). Cluster: invoice t9 Invalid-PO→null.
- Expected effect + why safe:
  - t9 flagged the CORRECT 50/53 pages; its ONLY error was `po_number:"PO-INVALID"` instead of
    `null` on Invalid-PO pages (verifier: `page 4 Expected 'None' Got 'PO-INVALID'`). The
    `report_key` idiom flips exactly that field. VERIFIED locally (idiom → None for PO-INVALID,
    keeps valid POs; the agent's truthiness idiom reproduces the bug) AND cross-run (this content
    was the only ACCEPTED invoice iteration, +0.100, verified 50/50 exact GT match).
  - Safe: additive new skill with the SEED (narrow) description — will not trigger for
    SimPO/PDF/court-form (non-reconciliation), so those passing trials are unchanged. HR-diff may
    load it but the guidance is generically correct (can only add a correct rule). The accepted
    SimPO fixes in `nlp-research-repo-package-installment/` are left UNTOUCHED.
- Building on prior RESULTS: kept cand_0001 (ACCEPTED, SimPO env+loss fixes) verbatim. Did NOT
  re-add cand_0002's CPU-wheel/drop-flash-attn nlp edit (REJECTED −0.600). From the invoice run:
  ported only its ACCEPTED cand_0002; did NOT port its REJECTED cand_0003 (broadened description,
  −0.2) or cand_0004 (prose→script, −0.2).
- Refuted hypotheses (never re-test): (a) t9 is "mislabeled infra" — FALSE, it's a real invoice
  task. (b) invoice-fraud fix via broadened trigger description or a bundled reconcile script —
  both REJECTED in the invoice run. (c) CPU-wheel torch / drop flash-attn nlp edit — REJECTED here.
- High-value clusters still NOT cracked: invoice-fraud is intrinsically flaky (its dedicated run
  plateaued at test=0.3; ±0.2 is noise at n=10) and may not be sampled every val — this fix is the
  best-evidenced lever but its measured effect is noise-sized. No other failing cluster exists in
  the current trajectories.
- Plateau signal: gate Δ is dominated by which diverse tasks get sampled per candidate (cand_0002's
  −0.6 was mostly sampling). If this is rejected as noise, next lever = broaden the OWNED shared
  skills (pdf) with generalizing, zero-regression reconciliation/report-schema guidance, since pdf
  is used by the widest set of sampled tasks — but only additively.
- Focus next iteration: read the RESULT below. If invoice sampled and still failing, check whether
  the agent LOADS fuzzy-match (loading correlated 100% with passing); if not, the lever is trigger
  reliability, not content.

> **RESULT (framework, objective):** REJECTED (champion unchanged) · val=0.900 Δ=+0.000 · fixed={—} · broke={—}. — its WHOLE batch was reverted; re-introduce only the edits that did NOT break a task above, dropping/redesigning the ones that did.
<!-- cand_0003: rejected val=0.900 Δ=+0.000 -->

## Iteration cand_0004 — move the ACCEPTED PO→null idiom into the pdf skill (reliably loaded), not a separate skill
- Changes I made (1 edit):
  1. `pdf/SKILL.md`: add a scoped "Building a validation / reconciliation report" subsection
     under Common Tasks carrying the `report_key(lookup_key, valid_keys)` code idiom — an
     existence-validated lookup key that is absent from the authoritative source is reported
     as `null`, never echoed as the raw string; resolved keys are reported verbatim. Cluster:
     invoice-fraud t9 (`test_content`: page-4 Expected 'None', Got 'PO-INVALID').
- Expected effect + why safe:
  - t9's ONLY failure (confirmed 14/14 identical across the dedicated invoice run) is echoing
    `"PO-INVALID"` instead of `null` on Invalid-PO pages. The idiom flips exactly that field
    (verified: PO-INVALID→None, valid POs kept). t9's own script does `import pypdf` (pdf
    skill's primary lib), so the agent reliably reads pdf/SKILL.md — this is the placement fix
    over cand_0003.
  - Safe for the 4 passing pdf-using seeds: scoped to existence-validated lookup fields in a
    report. t5/t8 HR-diff report value diffs (not key-existence-null), t6 emits a PDF, t7 fills
    a form → idiom inert. Note explicitly disclaims extract/transform/diff. Additive; frontmatter
    + refs + body budget unchanged. nlp skill untouched (all SimPO seeds pass).
- Building on prior RESULTS: kept cand_0001 (ACCEPTED, SimPO env+loss) verbatim. Used the
  dedicated invoice run's ACCEPTED lever = the CODE IDIOM (its cand_0002, +0.100). Did NOT
  re-add cand_0002's REJECTED nlp CPU-wheel/drop-flash-attn edit (−0.600). Did NOT re-add
  cand_0003's separate `fuzzy-match/SKILL.md` (+0.000) — moved its idiom into pdf instead.
- Refuted hypotheses (never re-test): (a) separate fuzzy-match skill for the invoice fix
  (cand_0003 here, +0.000; also dedicated-run cand_0003 broadened-trigger REJECTED). (b) prose-only
  rule for PO→null (dedicated cand_0001 −0.100). (c) bundled reconcile script (dedicated cand_0004
  −0.200). (d) nlp CPU-wheel/drop-flash-attn (cand_0002 −0.600).
- High-value clusters still NOT cracked: none other exists — t0–t8 all pass. Invoice-fraud is
  intrinsically flaky (dedicated run capped at val 0.400 WITH this idiom); with one invoice seed
  in this diverse val, the expected lift is ~+0.1 only ~40% of the time — may not clear the bar.
- Plateau signal: 2 straight flat/negative RESULTs on the invoice cluster (cand_0002 −0.6,
  cand_0003 +0.0). Lever switched to PLACEMENT (reliably-loaded pdf skill) + the one proven
  content lever (code idiom). If this is still +0.000, the cluster is structurally noise-bound
  at n=1 seed and is NOT skill-reachable in this val — stop editing for it.
- Focus next iteration: read the RESULT below. If rejected as noise, treat t9 as an un-movable
  single flaky seed; there is no other failing cluster, so hold the champion rather than ship
  speculative edits that risk the 9 passing seeds.

> **RESULT (framework, objective):** REJECTED (champion unchanged) · val=0.800 Δ=-0.100 · fixed={—} · broke={—}. — its WHOLE batch was reverted; re-introduce only the edits that did NOT break a task above, dropping/redesigning the ones that did.
<!-- cand_0004: rejected val=0.800 Δ=-0.100 -->
