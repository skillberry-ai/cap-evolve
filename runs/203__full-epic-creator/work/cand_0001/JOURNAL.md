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

<!-- cap-evolve:journal-append-below — add your Iteration entry under this line; do not edit anything above it -->

## Iteration cand_0001 — judge-parity contract validator as a structural gate + knowledge fixes for the 6 failure clusters
- Changes I made (1 line/edit; file + cluster):
  1. NEW `epic-decompose/scripts/validate_decomposition.py` — bundled validator checking body sections, component vocabulary, Rule 11 docs-last closure, priority inheritance (clusters A/C/D/E).
  2. `prompts/decompose-agent.md` Step 8c (+Step 0): validator run is a precondition of the `decompose_complete` sentinel (clusters A/C/D/E).
  3. `prompts/review-agent.md` new Step 1.7: reviewer runs the validator, every VIOLATION becomes an issues entry + zeroed criterion (clusters A/C/D/E).
  4. `prompts/revise-agent.md` Step 2 + Step 4: mechanical correction playbook per violation type + re-run until OK (clusters A/C/D/E).
  5. `prompts/decompose-agent.md` Step 2: component values verbatim from the canonical list, never invented/combined; span noted, not invented (cluster D).
  6. `prompts/decompose-agent.md` Step 4: redundant-HLR consolidation rule with worked example (cluster B).
  7. `prompts/review-agent.md` Criterion 3: presentation-mode split = scope duplication, major (cluster B).
  8. `prompts/decompose-agent.md` Step 7: external schedule constraints are not ACs — Risks/Health Warnings; worked example (cluster F).
  9. `prompts/review-agent.md` Criterion 6: soft-AC scan → minor issue "move to Risks/Notes" (cluster F).
  10. `prompts/decompose-agent.md` Step 8b: the four body-section headings are literal for every epic incl. docs-authoring; "Content Outline" is not "Scope" (cluster A).
- Per change, the EXPECTED effect + why it's safe:
  - (1)-(4) fix the 4 mechanically-decidable failing trials: case-020 t1 (artifact_contract hard gate, reward 0 → ~1.0), case-018 t2 (dq 4→5), case-013 t2 (component gate −0.1), case-024 t1 (Rule 11 gate −0.1). Safe because the script was verified against ALL 33 trial artifacts: it flags exactly those 4 trials (+ case-018 t0's identical latent priority defect, whose remedy is the t2 grader's own stated fix) and exits 0 on every other trial — so on passing tasks the gate is a no-op. The review→revise mapping only adds issues when a violation exists, and the zeroing instruction keeps review_discipline arithmetic consistent.
  - (5) fixes case-013 t2's invented 'Model Serving Stack': the OLD prompt's fallback example itself modeled inventing a non-canonical name — the rewrite makes verbatim-from-list the only path. Safe: all passing trials already comply.
  - (6)+(7) fix case-015 t1/t2 (dq 3/5, both trials): the traces show the agent SAW the HLR overlap and split anyway, and the review endorsed it 14/14; the passing trial t0 of the same task already consolidates citing Step 4 — the rule makes the consistent behavior the only permitted one. Safe: verified no passing decomposition splits two presentation modes of one surface (they split by component/binary/work-type/repo).
  - (8)+(9) fix case-013 t0's dq-4 "one minor gap" (schedule-risk note as AC). Safe: grep-verified no passing trial carries a schedule-note AC.
  - (10) fixes the exact case-020 t1 heading rename; safe: surveyed every docs epic in all 33 trials — only the failing trial deviated.
- Building on prior RESULTS: none exist (iteration 1 on the seed). Refuted hypotheses: none yet (rejected.jsonl is empty).
- High-value clusters still NOT cracked: none identified beyond the six fixed; the two dq-level residual risks are (a) grader inconsistency on priority inheritance (t0 passed with the defect t2 was dinged for — my check enforces the rule uniformly, which should help both), and (b) the redundancy judgment itself remains LLM-graded — if the grader ever rewards the split shape, edit 6/7 would need rescoping (watch case-015's per-trial grades).
- Refuted hypotheses: n/a (first iteration).
- Plateau signal: n/a (first iteration; val 0.918 baseline, 5 flaky tasks all diagnosed).
- Cost-reduction opportunity: cost/latency is not a declared objective this run; detect_loop_patterns not applicable. The validator adds ~2 cheap local Bash calls per case (no model tokens).
- Focus next iteration: read the gate RESULT per-task. If case-015 stays split (edit 6/7 insufficient for the reader tier), consider pushing the consolidation check into the validator as a heuristic (two same-team Implementation epics whose HLR Traceability sets overlap AND whose titles share a surface keyword) — only if the LLM rule under-triggers. If any passing task regressed, check first whether the validator fired on it (it shouldn't — corpus-verified) and whether the review-zeroing interacted badly with review_discipline.

