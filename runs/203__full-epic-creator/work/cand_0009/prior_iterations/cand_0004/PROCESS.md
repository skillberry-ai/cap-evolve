# PROCESS — what I did this iteration (explainability; REQUIRED)

## Ranked issue list (clusters by # failing tasks × trials, biggest first)

Diagnosed cand_0001's own trials from `./trajectories/` (33 trials, 11 val tasks). **Exactly 3 imperfect trials exist** (per-trial reward decomposition: reward = (dq−1)/4 − 0.1·softgates):

| task | trial rewards | failing trial | lost points |
| --- | --- | --- | --- |
| case-013-human-process-gates (0.97) | 0.9 / 1.0 / 1.0 | t0 | −0.1 `implementation_type_rules` (dq was 5) |
| case-014-tech-preview-foundation (0.92) | 1.0 / 0.75 / 1.0 | t1 | dq 4/5 ("one minor gap": architecture_claims) |
| case-020-hardware-dependent-investigation (0.92) | 1.0 / 1.0 / 0.75 | t0 | dq 4/5 ("one minor gap": misfiled soft AC) |

All 30 other trials score 1.0. No ENVIRONMENT faults — every pipeline completed; every failure is a capability failure. Max recoverable this iteration ≈ +0.02 val (0.982 → ~1.0); all three clusters are "make the good behavior consistent" (flaky) fixes.

| rank | cluster | tasks (trials) | shared root cause | tag | change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Rule 10 parallel-edge violation (`konflux-onboarding` → general, soft gate −0.1) | case-013 (t0) | Decompose agent wired E003 (konflux-onboarding) → E007 (general evidence-package epic) justifying it as a Rule-13 "artifact dependency (signed attestations are package contents)"; the internal review **enumerated Rule 10, then rationalized the edge away** with two invented exemptions ("E007 is not THE component's general implementation"; "package contents ≠ image digest"). The external judge is mechanical and admits no exemption: ANY direct edge between a konflux-onboarding and a general implementation epic fails, whatever the component or rationale. Sibling trials t1/t2 (passing) built no konflux epic at all; case-020's passing trials have konflux epics with NO edge and the dq grader praised that shape ("Rule 10 is honored... the coupling is the Rule 25 AC, as mandated") | BEHAVIORAL (rule known, rationalized past) | STRUCTURAL: new validator check 5 (Rules 7/8/10, judge parity) + close the two prose loopholes in decompose Rule 10/13 and review Criterion 2 |
| 2 | `architecture_claims` calibration miss (dq 4) | case-014 (t1) | Every implementation epic scored `architecture_claims: 0` with rationale "the strategy makes no specific architecture claims" — reading the +1 condition ("Strategy cites specific architecture context files/APIs") as requiring explicit citations. The strategy's premise ("Llama Stack shipped as Tech Preview... TP status currently excuses quality gaps") IS an architecture claim corroborated by the .context file; the annotation explicitly expects the signal to reference it. Passing siblings t0/t2 scored +1 on every epic with context-file-citing rationales | KNOWLEDGE (what counts as an architecture claim) | CONTRACT: rewrite signal 9's ±1 conditions + scoring note in decompose Step 6; calibration check in review Criterion 5; re-scoring guidance in revise |
| 3 | Availability precondition misfiled as an AC (dq 4) | case-020 (t0) | E001's AC "Dedicated AMD Instinct nodes are available to the campaign" is an externally-controlled availability precondition (procurement/partner-lab timing), already duplicated in Risks and Health Warning 3. Step 7's soft-AC rule named only SCHEDULE constraints. First review accepted it ("availability state the epic influences"); re-review flagged it minor but PASSED (13/14) → per the phase machine, a passing re-review never triggers another revise → the AC survived. The revise playbook also had no "move to Risks" correction for soft ACs | KNOWLEDGE (boundary too narrow) + STRUCTURAL gap (review-pass → minor never fixed) | WORKED EXAMPLE: broaden Step 7 to all externally-controlled preconditions; broaden review Criterion 6 scan + close the "epic influences it" rebuttal; add the move-to-Risks correction to the revise playbook |

## Changes made this iteration (one row per edit)

| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | STRUCTURAL (bundled script) | `epic-decompose/scripts/validate_decomposition.py` — new check 5 | Implementation-type parallelism (Rules 7/8/10) with exact judge parity (kind(): non-Implementation → exempt; implementation_type outside the 4-label enum → "general"; direct edges only; docs-authoring dependent exempt; deps filtered to existing epics). Runs as precondition of `decompose_complete` (existing Step 8c wiring), in review Step 1.7, and revise Step 4 | Yes — corpus-verified: flags exactly case-013 t0 and NOTHING else across all 33 trials; `--self-check` passes (5 checks fire on bad fixture, clean on good) |
| 1 | KNOWLEDGE (close loophole 1) | `prompts/decompose-agent.md` Rule 10 | The parallel rule covers EVERY konflux-onboarding × general pair whatever the general epic's component or deliverable (assembly/packaging/evidence epics included); no "different component" or "genuine artifact dependency" exemption; real coupling → AC on the consuming epic | Yes — passing trials with konflux epics (case-020 t0/t2) already have no edge; the dq grader praised that shape |
| 1 | KNOWLEDGE (close loophole 2) | `prompts/decompose-agent.md` Rule 13 | Configuration-reference carve-out extended: build-pipeline outputs consumed as CONTENT (signed attestations, SBOMs, provenance, scan results) are AC gates, not edges — code builds against API/CRD/library, not against attestations or digests | Yes — same narrow condition; the image-digest form was already there and passing trials comply |
| 1 | CONTRACT (sync description) | `prompts/decompose-agent.md` Step 8c | Validator's described coverage now includes the parallel-edge check + the fix recipe (remove the edge, express coupling as an AC gate) | Yes — additive description of what the script checks |
| 1 | STRUCTURAL (review mapping) | `prompts/review-agent.md` Step 1.7 | New violation→criterion row: parallel edge → severity critical, criterion "DAG Coherence" — the reviewer can no longer rationalize past a validator flag | Yes — issues added only on violations |
| 1 | KNOWLEDGE (review loopholes) | `prompts/review-agent.md` Criterion 2 | (a) "its component's general implementation" → ANY general implementation epic whatever its component; (b) image-digest carve-out extended to attestations/SBOMs/provenance consumed as content; (c) symmetric rule: do NOT report the edge's absence as a missing data dependency (prevents review demanding back the edge the validator removed) | Yes — narrows reviewer discretion only on the exact pattern the judge mechanically forbids |
| 1 | STRUCTURAL (revise playbook) | `prompts/revise-agent.md` contract-violations section | Parallel-edge correction: remove the flagged dep + summary DAG edge + justification row; real coupling → AC on the dependent epic | Yes — revise only acts on review issues |
| 2 | CONTRACT (signal definition) | `prompts/decompose-agent.md` Step 6, ai_signals row 9 | +1 = epic's scope or the strategy's premise about the component (surfaces, repos, deployment model, maturity state such as Tech Preview/GA) corroborated by an architecture-context file, named in the rationale; −1 = strategy asserts architecture the context contradicts | Yes — passing trials already score this way (case-014 t0/t2, case-020, case-024, case-029, case-030 all +1 with file-citing rationales) |
| 2 | KNOWLEDGE (scoring note) | `prompts/decompose-agent.md` Step 6, note under the 9-signal table | A strategy makes architecture claims whenever it states what a component IS (maturity state, CRD/API/repo surfaces, deployment model), even without the word "claim"; 0 only when no context file covers any touched component; "no specific architecture claims" is not a valid 0 rationale when context files exist | Yes — bounded by the discriminating condition: the all-0 PASSING trials (case-015/017/019) have strategies with NO maturity/state premises (verified — grep found none), so nothing changes for them |
| 2 | KNOWLEDGE (review calibration) | `prompts/review-agent.md` Criterion 5 | architecture_claims calibration check against .context (internal consistency is not enough): strategy-premise-asserts-component-state + context file covers it + epic scored 0 with "no claims" rationale = calibration miss → minor issue → the unconditional first revise re-scores it | Yes — same discriminating condition; severity minor (does not zero a criterion or fail the review on passing tasks) |
| 2 | KNOWLEDGE (revise guidance) | `prompts/revise-agent.md` AI-scoring section | architecture_claims re-evaluation recipe against `.context/architecture-context/` (+1 corroborated / −1 contradicted / 0 only when no file covers the components; cite the file) | Yes — revise only acts on review issues |
| 3 | KNOWLEDGE + worked example (boundary broadened) | `prompts/decompose-agent.md` Step 7 | "External schedule constraints are not ACs" → "Externally-controlled preconditions are not ACs" covering schedule (lab queues, review-board cadence, vendor timing) AND availability (procurement, hardware/node allocation, partner-lab access); tell-tale: an AC asserting a resource "is available" TO the epic rather than a condition on the epic's deliverable; securing access is work, the access being granted is not a deliverable | Yes — the only externally-granted availability AC in the corpus is case-020 t0's (the failure); passing trials' "available" ACs are conditions on their own deliverables (verified by scanning every AC in all 33 trials) |
| 3 | KNOWLEDGE (review scan broadened + rebuttal closed) | `prompts/review-agent.md` Criterion 6 | Soft-AC scan extended to availability preconditions granted by parties outside the strategy; "the epic's work includes securing the access" is explicitly NOT a defense (the exact rationalization the case-020 t0 first review used); a condition on what the epic itself builds (e.g. "the runtime this epic produces supports the cleared model set") is valid even if it says "available" | Yes — same discriminator; corpus scan shows no passing trial carries an externally-granted availability AC |
| 3 | STRUCTURAL (revise correction added) | `prompts/revise-agent.md` AC-issues section | New correction "Misfiled soft AC (externally-controlled precondition)": remove from ACs, record in Risks/Notes (or Health Warnings if strategy-level), replace with a testable AC on the epic's own deliverable — the review's "move to Risks/Notes" correction previously had NO playbook entry, so a flagged soft AC could be rewritten instead of moved | Yes — revise only acts on review issues; the correction is the grader-endorsed remedy |

SKILL.md (dispatcher) deliberately unchanged: no dispatcher-driven failure exists (dispatcher_turn_discipline passes on all 11 val tasks). fetch-agent.md unchanged (no failures in its phase).

## Verify-the-fix (one line per change: the trace it targets → what the guard/computation/new-tool now does on those exact inputs)

- **Validator check 5** — run end-to-end against all 33 trials' extracted artifacts: flags EXACTLY `case-013 t0` ("Rule 10: RHAISTRAT-9013-E003 (konflux-onboarding) blocks RHAISTRAT-9013-E007 (general) — these must run in parallel; remove the dependencies edge...") and nothing else. Trials that have konflux-onboarding epics with the compliant no-edge shape (case-020 t0 E006, t2 E002) pass cleanly — the check has no false positives on the corpus. `--self-check` passes (fires on a konflux→general bad fixture, clean on a parallel good fixture).
- **trace case-013 t0**: decompose agent's summary DAG carries edge E003→E007 justified as "signed attestations are package contents" (the dq grader's dimension-3 note confirms the rationale); review Criterion 2 text let the reviewer accept it via "E007 is not the Platform Operator's general implementation". With the edits: the validator (precondition of `decompose_complete`) exits 1 naming the edge — the agent removes E003 from E007's `dependencies` and (per Rule 13's new sentence) records the attestation coupling as an AC on E007, which already carries E004/E005 deps so it remains blocked; Rule 11, priority inheritance, and the mandated-AC judge are all unaffected by the removal (E007's chain after removal contains no konflux epic — exactly the rule-compliant shape judge note B8 describes). Even if the decompose agent missed it, review Step 1.7 turns the VIOLATION into a critical DAG-Coherence issue → review fails → revise removes the edge (playbook). Blast radius: BOUNDED — corpus-verified no flags on the other 32 trials; judge parity means the check can only fire on decompositions the implementation_type_rules judge would already fail.
- **trace case-014 t1**: every ai-signals file reads `architecture_claims | 0 | The strategy makes no specific architecture claims...` while the strategy's opening premise is "Llama Stack shipped as Tech Preview... TP status currently excuses quality gaps" and the Llama Stack context file states the TP maturity. With the edits: signal 9's +1 condition now names "the strategy's premise about the component (maturity state such as Tech Preview/GA)" and the scoring note states that a premise about what a component IS is an architecture claim — the agent scores +1 citing the context file (the exact shape of the passing t0/t2 rationales: "Consistent with architecture context (Llama Stack TP maturity...)"). If missed at decompose time, review Criterion 5's calibration check flags it (minor) → the unconditional first revise re-scores per the new revise guidance. Blast radius: BOUNDED — the rule changes behavior only when a strategy premise asserts a component state/maturity; the all-0 passing trials' strategies (case-015/017/019, verified by grep) contain no such premises, so their 0s stay correct and untouched.
- **trace case-020 t0**: E001's AC list contains "Dedicated AMD Instinct nodes are available to the campaign (procured or accessed via partner lab)" — duplicated in Risks and Health Warning 3. With the edits: Step 7's broadened rule + worked example names availability preconditions as non-ACs, so the agent places it in Risks/Notes only (it already did) and writes the AC on the campaign's deliverable; if it slips through, review Criterion 6's scan flags it (the "securing the access" rebuttal is explicitly closed — the exact rationalization the t0 first review used to accept it) and the FIRST revise — which is unconditional and fixes every issues-list entry — moves it via the new playbook correction. Blast radius: BOUNDED — the scan keys on "granted by parties outside the strategy"; corpus scan of every AC in all 33 trials shows the only such AC is the failing trial's own; passing trials' "available"-worded ACs (case-014 t1/t2, case-020 t1) are conditions on the epics' own deliverables and are explicitly protected by the "condition on what the epic itself builds is valid" sentence.

## Why the review→revise wiring lands the fixes (phase-machine analysis)

`pipeline_state.py`: REVIEW_DECOMP → REVISE_DECOMP is **unconditional** (the revise agent fixes every entry in the review's `issues` list, minor or major); RE_REVIEW runs only if something changed; a further revise runs only if the re-review FAILS. This is why case-020 t0's re-review-passing 13/14 left its minor soft-AC issue unfixed — and why all three review-side checks above are calibrated to fire at the FIRST review (validator flags at decompose time; Criterion 5/6 checks at first review), where the unconditional revise is guaranteed to apply them.

## Process & features used

- Serial this iteration (no subagents/worktrees): only 3 imperfect trials exist and each maps to one cluster; the diagnosis was a single coherent chain (per-trial reward decomposition → judge-source cross-read → trace mechanism), and the 13 edits land in 4 files whose contents must stay mutually consistent (validator ↔ decompose Step 8c ↔ review Step 1.7 ↔ revise playbook) — parallel edit-subagents would have conflicted.
- Read in full: `guidance/skill-package/SKILL.md` (levers used: skipped-step→bundled-script, output-contract clarification, worked example, body knowledge note), `guidance/diagnose/SKILL.md` (per-trial mean vs last-trial feedback; flaky-vs-failing separation; blast-radius naming).
- Prior iterations read: `prior_iterations/cand_0001/` (PROCESS.md + diff.patch) — built directly on its validator/Step-8c/review-1.7/revise wiring; no regressing edits to redesign (cand_0001 broke nothing; LEDGER `broke={}`).
- Improvement types applied (multiple, per the capability skill): bundled-script enforcement (validator check 5), output-contract clarification (signal 9 row, Step 8c description), worked example (Step 7 availability AC), decision-rule narrowing via discriminating condition (architecture_claims "component-state premise"; soft-AC "granted by parties outside the strategy"), review-to-revise issue mapping (Step 1.7 row; Criterion 5/6 checks), revise-playbook correction entries (3 new).

## Good things to PRESERVE (do not let a future iteration undo these)

- The validator's judge-parity logic — now including check 5's kind() semantics (non-Implementation → exempt; unknown implementation_type → "general"; direct edges only; docs-dependent exemption). Corpus-verified flag-for-flag: only case-013 t0 across all 33 trials.
- The "validator as precondition of decompose_complete" ordering and the Step 1.7 violation→issue→zeroed-criterion mapping.
- The narrow discriminating conditions: architecture_claims fires only on strategy-premise-asserts-component-state; soft-AC fires only on granted-by-parties-outside-the-strategy. Broadening either (e.g. "whenever context files exist", or "any AC mentioning availability") would flip behavior on passing tasks (case-015/017/019 all-0 trials; case-014/020 deliverable-condition ACs).
- Review Criterion 2's symmetric rule (don't demand back the edge the validator removed) — without it the review/validator oscillate.

## Deliberately skipped (cluster + why)

- case-013 t0's dq "minor notes" (E006 no-dep justification prose; open_questions asymmetry; E007 triaged-tail) — grader explicitly "below the one minor gap threshold", dq was 5: fails the REAL test.
- case-020 t0's external_dependency 0-vs-+1 review nits and the AMD discovery-stack completeness flag — grader: "real but conservative, routing-neutral, and outside the five graded dimensions": fails the REAL test.
- case-014 t1's "summary cites strategy frontmatter priority: Critical, not visible in strategy_markdown" — grader: "not scored": fails the REAL test.
- mandated-AC (Rules 24/25) validator checks — that judge is staged thresholdless (B9) and does not affect reward yet: not REAL.
- SKILL.md frontmatter/description edits — the runner invokes the skill directly; triggering is not a failure mode.
- Escalating the Criterion 5/6 checks to MAJOR severity — minor suffices (the unconditional first revise fixes all issues-list entries) and major would zero criteria / fail reviews on borderline cases: bigger blast radius for no additional fix.

## Environment faults

None. All 33 trials ran to completion; every failure is a capability failure.

---

# DIAGNOSIS.json — machine-readable diagnosis (REQUIRED under agent-optimize)

```json
{
  "candidate": "cand_0002",
  "headline": "Rule 7/8/10 parallel-edge validator check (judge parity) + loophole-closing knowledge for the konflux/general edge, architecture_claims calibration against .context, and the soft-AC boundary broadened to availability preconditions",
  "clusters": [
    {"id": "A", "name": "Rule 10 parallel-edge violation (konflux-onboarding -> general)",
     "detail": "E003 (konflux-onboarding) blocks E007 (general evidence-package epic), justified as a Rule-13 artifact dependency; the internal review enumerated Rule 10 and rationalized two invented exemptions (component scope, package-contents). The implementation_type_rules judge is mechanical and admits no exemption.",
     "tasks": ["case-013-human-process-gates"], "scope": "BOUNDED", "latent": false,
     "tag": "BEHAVIORAL"},
    {"id": "B", "name": "architecture_claims calibration miss",
     "detail": "All implementation epics scored architecture_claims 0 with 'the strategy makes no specific architecture claims' while the strategy's premise (component shipped as Tech Preview) is an architecture claim corroborated by .context — the annotation's declared expectation. Passing siblings score +1 citing the context file.",
     "tasks": ["case-014-tech-preview-foundation"], "scope": "BOUNDED", "latent": false,
     "tag": "KNOWLEDGE"},
    {"id": "C", "name": "availability precondition misfiled as an AC",
     "detail": "E001's AC 'Dedicated AMD Instinct nodes are available to the campaign' is an externally-controlled availability precondition already duplicated in Risks/Health Warning 3; Step 7 named only schedule constraints; the first review accepted it via 'availability state the epic influences'; the re-review flagged it minor but passed, and a passing re-review never triggers another revise.",
     "tasks": ["case-020-hardware-dependent-investigation"], "scope": "BOUNDED", "latent": false,
     "tag": "KNOWLEDGE"}
  ],
  "edits": [
    {"id": "E1", "title": "Validator check 5: implementation-type parallelism (Rules 7/8/10) with judge parity + self-check",
     "files": ["epic-decompose/scripts/validate_decomposition.py"], "lever": "STRUCTURAL",
     "clusters": ["A"], "blast_radius": "BOUNDED",
     "verified": "End-to-end over all 33 trials' extracted artifacts: flags exactly case-013 t0, nothing else; --self-check passes (fires on konflux->general fixture, clean on parallel fixture)"},
    {"id": "E2", "title": "Rule 10: no component-scope or artifact-dependency exemption; coupling -> AC on the consuming epic",
     "files": ["epic-decompose/prompts/decompose-agent.md"], "lever": "KNOWLEDGE",
     "clusters": ["A"], "blast_radius": "BOUNDED",
     "verified": "trace case-013 t0 review text invents both exemptions verbatim; passing konflux trials (case-020 t0/t2) already edge-free and grader-praised"},
    {"id": "E3", "title": "Rule 13: build-pipeline outputs consumed as content (attestations, SBOMs, provenance) are AC gates, not edges",
     "files": ["epic-decompose/prompts/decompose-agent.md"], "lever": "KNOWLEDGE",
     "clusters": ["A"], "blast_radius": "BOUNDED",
     "verified": "the t0 edge's justification is exactly 'signed attestations are package contents'; judge note B8 confirms no general epic may have konflux in its chain"},
    {"id": "E4", "title": "Step 8c validator description includes the parallel check + fix recipe",
     "files": ["epic-decompose/prompts/decompose-agent.md"], "lever": "CONTRACT",
     "clusters": ["A"], "blast_radius": "BOUNDED",
     "verified": "description matches what the extended script checks"},
    {"id": "E5", "title": "Review Step 1.7 mapping: parallel edge -> critical, DAG Coherence",
     "files": ["epic-decompose/prompts/review-agent.md"], "lever": "STRUCTURAL",
     "clusters": ["A"], "blast_radius": "BOUNDED",
     "verified": "issues added only on validator violations; targets the t0 reviewer's rationalization"},
    {"id": "E6", "title": "Review Criterion 2: any-component scope + attestations-as-content carve-out + no missing-edge report for config references",
     "files": ["epic-decompose/prompts/review-agent.md"], "lever": "KNOWLEDGE",
     "clusters": ["A"], "blast_radius": "BOUNDED",
     "verified": "closes both loopholes the t0 reviewer used; symmetric rule prevents validator/review oscillation"},
    {"id": "E7", "title": "Revise playbook: parallel-edge correction (remove edge + summary row; coupling -> AC)",
     "files": ["epic-decompose/prompts/revise-agent.md"], "lever": "STRUCTURAL",
     "clusters": ["A"], "blast_radius": "BOUNDED",
     "verified": "revise only acts on review issues; correction is the judge-compliant remedy"},
    {"id": "E8", "title": "ai_signals row 9 rewritten: premise-corroborated-by-context -> +1 naming the file",
     "files": ["epic-decompose/prompts/decompose-agent.md"], "lever": "CONTRACT",
     "clusters": ["B"], "blast_radius": "BOUNDED",
     "verified": "passing trials' rationales already match this shape (case-014 t0/t2 cite context files incl. TP maturity)"},
    {"id": "E9", "title": "Scoring note: a strategy premise about what a component IS is an architecture claim; 0 only when no context covers the components",
     "files": ["epic-decompose/prompts/decompose-agent.md"], "lever": "KNOWLEDGE",
     "clusters": ["B"], "blast_radius": "BOUNDED",
     "verified": "all-0 passing trials (case-015/017/019) have no maturity/state premises (grep-verified) so their 0s stay correct"},
    {"id": "E10", "title": "Review Criterion 5: architecture_claims calibration check against .context (minor issue)",
     "files": ["epic-decompose/prompts/review-agent.md"], "lever": "KNOWLEDGE",
     "clusters": ["B"], "blast_radius": "BOUNDED",
     "verified": "fires only on strategy-premise-asserts-component-state + 0-with-no-claims-rationale; the unconditional first revise applies it"},
    {"id": "E11", "title": "Revise guidance: architecture_claims re-evaluation recipe against .context",
     "files": ["epic-decompose/prompts/revise-agent.md"], "lever": "KNOWLEDGE",
     "clusters": ["B"], "blast_radius": "BOUNDED",
     "verified": "revise only acts on review issues"},
    {"id": "E12", "title": "Step 7: externally-controlled preconditions (schedule AND availability) are not ACs, with worked example",
     "files": ["epic-decompose/prompts/decompose-agent.md"], "lever": "KNOWLEDGE",
     "clusters": ["C"], "blast_radius": "BOUNDED",
     "verified": "corpus scan of every AC in all 33 trials: the only externally-granted availability AC is case-020 t0's (the failure)"},
    {"id": "E13", "title": "Review Criterion 6: soft-AC scan broadened to availability preconditions; 'securing the access' rebuttal closed; deliverable-condition ACs protected",
     "files": ["epic-decompose/prompts/review-agent.md"], "lever": "KNOWLEDGE",
     "clusters": ["C"], "blast_radius": "BOUNDED",
     "verified": "the t0 first review's exact acceptance rationale ('availability state the epic influences') is named and closed; passing 'available'-ACs are deliverable conditions, explicitly valid"},
    {"id": "E14", "title": "Revise playbook: misfiled soft AC -> move to Risks/Notes + replace with deliverable AC",
     "files": ["epic-decompose/prompts/revise-agent.md"], "lever": "STRUCTURAL",
     "clusters": ["C"], "blast_radius": "BOUNDED",
     "verified": "the review's 'move to Risks/Notes' correction previously had no playbook entry — the gap that let the flagged AC survive"}
  ],
  "skipped": [
    {"title": "case-013 t0 dq minor notes (E006 prose, open_questions asymmetry)", "reason": "grader: below the one-minor-gap threshold, dq was 5 — fails REAL"},
    {"title": "case-020 t0 external_dependency 0-vs-+1 nits, AMD discovery-stack flag", "reason": "grader: routing-neutral, outside the five graded dimensions — fails REAL"},
    {"title": "case-014 t1 strategy-frontmatter-priority citation", "reason": "grader: not scored — fails REAL"},
    {"title": "mandated-AC (Rules 24/25) validator checks", "reason": "that judge is staged thresholdless and does not affect reward yet"},
    {"title": "SKILL.md description edits", "reason": "skill invoked directly by the runner; triggering not a failure mode"},
    {"title": "Major severity for Criterion 5/6 checks", "reason": "minor suffices (unconditional first revise fixes all issues-list entries); major would zero criteria on borderline cases for no extra fix"}
  ],
  "techniques": ["bundled-script enforcement (judge parity)", "per-trial reward decomposition", "loophole-closing knowledge edits", "worked example", "review-to-revise issue mapping via the phase machine", "corpus blast-radius verification"]
}
```
