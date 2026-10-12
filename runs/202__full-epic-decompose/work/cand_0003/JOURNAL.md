# JOURNAL — optimizer handover (append-only, whole run)

YOU (the optimizer) own this file. It is the running, accumulating handover across ALL iterations — accepted AND rejected — and it is NEVER reset. Each iteration you APPEND one new entry at the bottom (under the marker line); you do NOT edit or delete earlier entries. Read the whole journal before proposing, so you build on EVERY prior attempt (not just the last accepted one) and never re-test a refuted idea.

You CANNOT know your own gate result while you write — the harness scores you AFTER you stop and stamps a **RESULT** line (outcome + Δ + the tasks you measurably broke/fixed, plus the ones whose move was too small to resolve) right below your entry. So do NOT write 'what worked' as a guess. To learn what actually worked, READ the framework RESULT lines of prior entries (and LEDGER.md): an entry whose RESULT says `rejected` with `broke={...}` tells you which specific edits to drop or redesign — its diff.patch is in ./prior_iterations/<id>/.

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
    - Cost-reduction opportunity (if `cost`/`latency`/`num_messages` is a declared objective,
      run `detect_loop_patterns.py --run-dir $R --tag $BEST --split val` — free, no extra
      eval — and check its `by_tool` map for a same-tool-called-N-times-in-a-row pattern. A
      hit names the exact tool + repeat count: propose a composite/bulk tool (capability
      `tools`), a bundled script entrypoint (`skills-package`), or upfront-batched
      instructions (`prompt`/`system-prompt`) that replace the N calls with one. No hit
      (or cost/latency not a declared objective): say so plainly, do not leave this blank):
    - Focus next iteration:

## Iteration cand_0001 — deterministic enforcement of the three defect classes the 019 review passed on
- Changes I made (1 line per edit; name the file/tool + cluster it targets):
  - NEW `epic-decompose/scripts/check_decomposition.py` (584 lines, --self-check passes): mechanical checks for docs-priority derivation, gating-AC gap, spec/content boundary overlap, structural breaches — targets all three 019 sub-clusters (A/B/C).
  - `prompts/decompose-agent.md` Step 5: new "Spec-vs-content boundary" axis rule + worked example (cluster A).
  - `prompts/decompose-agent.md` Step 7: gating-coverage AC rule (cluster C).
  - `prompts/decompose-agent.md` Step 8c: must run the check to exit 0 before `decompose_complete=true` (clusters A-D).
  - `prompts/review-agent.md` new Step 2.0: reviewer runs the same script first, folds findings into the issues list with class→criterion/severity mapping (clusters A-D).
  - `prompts/review-agent.md` Criterion 3 + Criterion 6: named spec-vs-content overlap and gating-coverage patterns (clusters A, C).
  - `prompts/revise-agent.md` Step 2: enumerated must-fix classes for `minor` issues (overlap / gating-AC / docs-priority / structural), observation-minors keep judgment latitude (clusters A-D).
  - `prompts/revise-agent.md` boundary recipes + Step 4: spec-vs-content correction recipe (never merge — stub or subsume) and post-correction script re-run to exit 0 (clusters A-D).
- Per change, the EXPECTED effect + why it's safe (which failing task it should fix; why no passing task changes behavior):
  - Expected: case-019 goes 4/5 → 5/5. The scored deduction is the Epic-Boundaries "one minor overlap" (E001 authoring a reference tutorial that duplicates E003's authoring surface); the same review also flagged the E004 docs-priority derivation (Major→P1, not HLR-4's P2) and the E002 gating-AC gap. The decomposer now has the rules (prose) AND a deterministic check (code) at three enforcement points; even if the decomposer skips, the first review's mechanical pre-check lists the defects and the unconditional first revision must fix them, and the reviser cannot leave a checkable defect for the terminal re-review.
  - Safety: every edit's firing condition was verified ABSENT from all 7 passing tasks' exact artifacts (programmatic scan; script exits 0 on all of them, flags exactly the 3 target findings on 019). The revise must-fix list is enumerated to the script's defect classes so 015/016's leave-observation behavior and 017's signal-fix latitude are unchanged; review pass/fail thresholds and pipeline cycle-cap semantics untouched.
- Building on prior RESULTS: none — iteration 1 (seed baseline; RUNMAP/LEDGER empty, no rejected.jsonl).
- Refuted hypotheses (a prior RESULT proved this is NOT the fix — never re-test): none yet.
- High-value clusters still NOT cracked (and the guard/tool designs already tried):
  - gate_failure_impact/gated_by completeness (020's first-review majors): mechanically checkable, deliberately not added this iteration because it fires on a passing task's post-decompose state; needs verification that decompose-time fixing lands identically to revise-time fixing before enabling.
  - The external scorer's full rationale is truncated at ~1288 chars (framework limit), so the 4/5 attribution rests on the visible "one minor overlap" + the mirrored internal-review minors; if the gate shows 019 still <1.0, the deduction may live in the invisible tail — next lever would be tightening the remaining named dimensions (DAG justification verbosity, summary-section completeness).
- Plateau signal: none (first iteration; baseline 0.969).
- Cost-reduction opportunity: cost/latency is not a declared objective for this run. (For completeness: the pipelines run ~23 min/case and ~50 turns; no same-tool repeat-loop pattern was checked since cost is not scored.)
- Focus next iteration: re-score of 019 is the signal. If 5/5 → consider the gate-metadata check (with the 020 pre-revision verification) and watch for new minors the script doesn't cover. If still 4/5 → the scorer's invisible rationale tail; attack AC specificity/summary completeness instead. Keep the three enforcement legs (decompose 8c / review 2.0 / revise 4) in sync in any future edit.

> **RESULT (framework, measured):** REJECTED (champion unchanged) · val=0.812 Δ=-0.156 · fixed={case-019-content-vs-code-split} · broke={case-013-human-process-gates, case-014-tech-preview-foundation, case-016-component-canonicalization} · unresolved={—} (moved less than 2·SE of its own measurement — NOT evidence the edit touched those tasks; do not redesign on them). — its WHOLE batch was reverted; re-introduce only the edits that did NOT break a task above, dropping/redesigning the ones that did.
<!-- cand_0001: rejected val=0.812 Δ=-0.156 -->

## Iteration cand_0002 — same 019 cluster, bounded enforcement: narrow fail-open script at decomposer 8c + missing rules + reviewer naming + reviser recipes
- Changes I made (1 line per edit; name the file/tool + cluster it targets):
  - NEW `epic-decompose/scripts/check_decomposition.py` (341 lines, --self-check 5/5): two mechanical checks — spec-content overlap, gating-AC gap — each finding names file + epic + defect + exact fix (clusters A/B).
  - `prompts/decompose-agent.md` Step 5: new "Spec-vs-content boundary" axis rule + worked example in a different domain (cluster A).
  - `prompts/decompose-agent.md` Step 7: "Rollout-gate coverage" AC rule with human-gate/CI-gate exclusions (cluster B).
  - `prompts/decompose-agent.md` Step 8c: fail-open boundary self-check invocation (dual-path script resolution, fix-findings-then-rerun-once, never blocks completion) (clusters A/B).
  - `prompts/review-agent.md` Criterion 3: named spec-vs-content overlap pattern + do-not-flag guidance for the observed near-miss classes (cluster A).
  - `prompts/review-agent.md` Criterion 6: named rollout-gate coverage pattern + do-not-flag guidance (cluster B).
  - `prompts/revise-agent.md` Step 2: exactly two named defect classes fixed even when minor; all other minors keep latitude (clusters A/B).
  - `prompts/revise-agent.md` Epic Boundary recipe: spec-epic/content-epic overlap → stub or subsume, NEVER merge (cluster A).
  - `prompts/revise-agent.md` AC recipe: missing rollout-gate AC → given/when/then gate AC (cluster B).
  - `SKILL.md` frontmatter: description now says WHEN to use (clears the seed's validation warning).
- Per change, the EXPECTED effect + why it's safe (which failing task it should fix; why no passing task changes behavior):
  - Expected: case-019 goes 0.75 → 1.0 by eliminating the two defects the terminal re-review listed — the scored "one minor overlap" (E001 authoring a reference tutorial that duplicates E003's authoring surface) and the E002 gating-AC gap. The decomposer now has the rules (knowledge), a deterministic self-check at 8c (enforcement), the first review has the patterns named (second net; the unconditional first revision then fixes them via the recipes), and the reviser has the correct fix shapes (stub/subsume — not the merge the scope-duplication rule would suggest).
  - Safety: every firing condition was measured, not asserted — the script exits 0 with zero findings on all 7 passing tasks' final artifacts AND on every intermediate file version (per-file histories reconstructed from all Write/Edit calls in all 8 transcripts, i.e. the exact states the 8c check sees); the Step 5/Step 7 rule triggers are verified absent from all passing tasks (019 is the only val task with a format epic beside a non-docs content epic; 019-E002 the only gate-in-scope-without-AC); no passing task's first OR final review lists an overlap/gating issue, so the recipes and the must-fix sentence never fire there; 013 (human-approval gates) and 014 ("enabled by default" with gate AC) are explicitly protected by the do-not-flag exclusions. On passing tasks the only behavioral delta is one extra Bash call that prints OK.
- Building on prior RESULTS: cand_0001's RESULT (fixed={019}, broke={013,014,016}) — kept its cluster diagnosis (the gate confirmed the right defect classes) and its decomposer-side rule ideas; DROPPED/REDESIGNED the parts consistent with the break: no reviewer-side script folding (its Step 2.0), no revise-side re-run gate (its Step 4), no four-family must-fix enumeration (its Step 2), no structural/branch/epic_count/draft-ID checks, no docs-priority check, hard 8c gate → fail-open. Its diff.patch is truncated (only DIAGNOSIS.json survived), so the redesign is inferred from its JOURNAL/PROCESS descriptions.
- Refuted hypotheses (a prior RESULT proved this is NOT the fix — never re-test): "fixing 019's three listed minors via the full enforcement chain is net-positive" — cand_0001's RESULT disproved the blast-radius claim (broke 3 passing tasks > 2·SE each); do not re-add consumer-side mechanical folding or hard completion gates.
- High-value clusters still NOT cracked (and the guard/tool designs already tried): none on the val split — 7/8 solid, 019 is the only headroom. Latent: gate_failure_impact/gated_by completeness (fires on 020's post-decompose state; needs decompose-time-vs-revise-time fix-path equivalence verified first — deliberately not tried by either iteration).
- Plateau signal: baseline 0.969 with one flaky task; max realistic gain this cluster ≈ +0.031. If this batch is accepted at 019=1.0, remaining iterations should defend (no churn) and consider the latent gate-metadata cluster only with the 020 equivalence verification.
- Cost-reduction opportunity: cost/latency is not a declared objective for this run. (Pipelines run ~23 min/case; no same-tool repeat-loop pattern was checked since cost is not scored.)
- Focus next iteration: re-score of 019 is the signal. If 1.0 → hold; watch for new minors the two checks can't see (the scorer's rationale tail is truncated). If still <1.0 → the deduction lives in the invisible tail; next lever is AC-specificity/summary-completeness dimensions, and ask whether the two new checks actually ran (grep the rollout for the 8c invocation and "boundary check unavailable" notes — a silent non-run means the path resolution failed in the real layout).

> **RESULT (framework, measured):** REJECTED (champion unchanged) · val=0.938 Δ=-0.031 · fixed={—} · broke={case-013-human-process-gates} · unresolved={—} (moved less than 2·SE of its own measurement — NOT evidence the edit touched those tasks; do not redesign on them). — its WHOLE batch was reverted; re-introduce only the edits that did NOT break a task above, dropping/redesigning the ones that did.
<!-- cand_0002: rejected val=0.938 Δ=-0.031 -->

<!-- cap-evolve:journal-append-below — add your Iteration entry under this line; do not edit anything above it -->

## Iteration cand_0003 — one mechanism behind every 4/5 (unresolved defect-class minor in the terminal re-review): structural script + producer rules + reviewer narrowing + reviser must-fix
- Changes I made (1 line per edit; file/tool + cluster):
  - NEW `epic-decompose/scripts/check_decomposition.py` (structural-only: mermaid↔frontmatter edges both directions, dangling deps, cycles, main-plan→branch deps; --self-check 9/9) — cluster A1 (c2-019's first-review defect).
  - `prompts/decompose-agent.md` Step 8c: fail-open invocation of that script (dual-path, fix-findings-once) — A1.
  - `prompts/decompose-agent.md` Step 5: spec-vs-content boundary rule + different-domain example — A4 (seed-019's overlap).
  - `prompts/decompose-agent.md` Step 7: parallel-supplier AC completeness rule + different-domain example — A2 (c2-019's re-review defect).
  - `prompts/decompose-agent.md` Step 7: rollout-gate AC coverage rule with exclusions — A5 (seed-019's gate-AC minor).
  - `prompts/review-agent.md` Criterion 7: already-surfaced strategy ambiguity (health-warning mirrors, "confirm with the author") is not a Completeness issue — A3, the exact mechanism that broke 013 in cand_0002.
  - `prompts/revise-agent.md` Step 2: defect-vs-observation must-fix discriminator for minors (prescriptive → fix; hedged/conditional/signal-value → discretionary) — A6 (seed-019's reviser left all 3 minors).
  - `prompts/revise-agent.md` recipes: spec/content overlap → stub-or-subsume (+supplier-AC sweep), missing rollout-gate AC → gate-verification AC — A4/A5/A2.
  - `prompts/revise-agent.md` Step 4: propagate dep/AC changes to Mermaid+justification, re-check parallel consumers after producer-scope changes, run the script fail-open — A1/A2.
  - `SKILL.md` description: "Use when…" (clears the standing validation warning; cand_0002's E10).
- Per change, the EXPECTED effect + why it's safe:
  - Expected: case-019 0.75 → 1.0. The judge scores 4/5 iff the terminal re-review leaves a defect-class minor (verified: all four observed 4/5s cite one; all observed 5/5s had clean/observation-only final reviews). The edits remove each known producer defect class (A1 mechanically; A2/A4/A5 by rule), make the reviser fix prescriptive minors it used to leave (A6), and stop the re-review from re-listing already-surfaced ambiguity as unresolved defects (A3). Together they empty the defect-minor population the judge anchors on.
  - Safety: every firing condition was MEASURED over all 8 tasks' final AND post-decompose states (Write + frontmatter.py-set replay from every rollout's stdout): script CLEAN on all 8 finals and 7/8 post-decompose (seed-018's single firing is a true defect whose fix converges to the state that already scores 5/5; c2-013 post-decompose CLEAN — the script is not implicated in cand_0002's 013 break). Rule triggers grepped absent-or-already-satisfied on all passing tasks (014-E005's gate ACs exist; 013's gate epics are excluded classes; no spec-epic/content-epic or parallel-supplier patterns outside 019). The reviser discriminator was checked against all 12 observed minors — only seed-019's three classify as defects. The reviewer edit is narrowing-only; no passing task's final review lists a health-warning mirror.
- Building on prior RESULTS: cand_0001's RESULT (fixed={019}, broke={013,014,016}) — kept its cluster diagnosis (gate-confirmed correct) and cand_0002's RESULT (broke={013}) — kept its proven dual-path invocation shape and its E1 boundary rule (which verifiably cleaned 019's external dim-2). Dropped/redesigned: reviewer-side script folding (cand_0001 Step 2.0), hard 8c exit-0 gate (→ fail-open), four-family must-fix enumeration (→ calibrated discriminator), semantic keyword script checks (→ structural-only), reviewer pattern-naming (cand_0002 E5/E6 — the plausible 013-pedantry driver; reviewer now gets a narrowing rule only).
- Refuted hypotheses (never re-test): (1) "fixing 019's minors via a broad enforcement chain is net-positive" — cand_0001's RESULT (3 passing tasks broke). (2) "producer-side bounded enforcement of two defect classes suffices to flip 019" — cand_0002's RESULT (019 stayed 0.75: the re-review found a NEW defect class, A2, that nothing covered). (3) "the 013 break was caused by the decomposer rules" — this iteration's evidence points at the re-review draw (the 3 minors appeared only in the re-review, mirrored from health warnings the seed run also had with a clean review); the decomposer rules' triggers are absent from 013.
- High-value clusters still NOT cracked (designs tried): gate_failure_impact/gated_by completeness (fires on passing 020's post-decompose state — deliberately not tried by three iterations now; needs the decompose-time-vs-revise-time equivalence verified). Residual risk on 019: the re-review can still find a genuinely NEW defect class no rule covers (it did exactly that to cand_0002); the mitigations are the reviser's post-fix sweep and the narrowing rule, not full coverage.
- Plateau signal: baseline 0.969, two rejects. This is the third attempt on the same 0.031 of headroom; if this batch is rejected with 019 still <1.0, the mechanism (judge anchors on terminal-review defect minors) predicts the next lever is emptying the re-review's defect findings further — e.g. extending the reviser's post-fix sweep to re-derive every consumer AC against changed producers — NOT more boundary prose.
- Cost-reduction opportunity: cost/latency is not a declared objective for this run. (Pipelines still run ~23 min/case; the new script adds one Bash call per decompose and per revise — negligible.)
- Focus next iteration: if 019 = 1.0 and nothing broke → hold; the A3 narrowing also protects 013-class draws. If 019 still 4/5 → grep the new rollout's terminal review for what minor the judge cited; extend the producer rule or reviser sweep for THAT class, and check the 8c invocation actually ran (grep "consistency check unavailable" / "OK: no structural findings"). If a passing task broke → check first whether its terminal review changed listing behavior (the A3 rule should only remove listings); the reviser discriminator is the next most likely suspect (016's signal-value minor is the nearest classification boundary).

