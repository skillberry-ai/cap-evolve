# PROCESS — what I did this iteration (explainability; REQUIRED)

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
Re-clustered all of the seed's failures from `./trajectories/` (33 trials, 11 val tasks). No ENVIRONMENT faults — every failure is a capability failure (all pipelines completed, no infra errors).

| rank | cluster | tasks (trials) | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Epic body missing required section (hard gate → reward 0) | case-020 (t1: 0.0) | Decompose agent wrote `## Content Outline` instead of `## Scope` on a docs-authoring epic; neither internal review nor revise caught a mechanically-checkable contract item | BEHAVIORAL (skipped check) | STRUCTURAL: bundled validator script, run as precondition of the `decompose_complete` sentinel |
| 2 | Redundant/overlapping HLRs split into two epics (dq 3/5) | case-015 (t1, t2: 0.5) | Agent *detected* the HLR-1/HLR-3 wording overlap (Health Warning "resolved by splitting") and split by priority label anyway; review endorsed at 14/14. Passing trial t0 of the same task consolidated ("bundled per Step 4") — behavior exists but is inconsistent | KNOWLEDGE (discriminating condition missing) | WORKED EXAMPLE + explicit consolidate rule in decompose Step 4; presentation-mode duplication check in review Criterion 3 |
| 3 | Priority inheritance violation (dq 4/5) | case-018 (t2: 0.75; t0 latent — same defect, grader missed it) | Quota-data epic left P1 while directly blocking a P0 epic; reviewer asserted "blocks no P0 work" without enumerating `dependencies` | BEHAVIORAL (mechanical check skipped) | STRUCTURAL: validator checks priority inheritance; review maps violation → Criterion 1 issue; revise gets the correction |
| 4 | Non-canonical component name (soft gate −0.1) | case-013 (t2: 0.9) | Prompt's own fallback example ("closest parent-level component … e.g. 'Model Serving Runtimes'") invited inventing a name; agent wrote `Model Serving Stack` | KNOWLEDGE (contract mis-stated) | CONTRACT: rewrite Step 2 fallback — verbatim-from-list only; validator checks membership |
| 5 | Rule 11 docs-last gap (soft gate −0.1) | case-024 (t1: 0.9) | Branch-C docs epic's dependency closure missed main-plan E002; rule stated but one edge omitted | BEHAVIORAL (mechanical check skipped) | STRUCTURAL: validator checks closure; review maps violation → Criterion 2 issue |
| 6 | Schedule-risk note written as an AC (dq 4/5) | case-013 (t0: 0.75) | E005's final AC ("Lab scheduling and review-board cadence are externally controlled…") is the rubric's canonical soft-AC exemplar; internal review observed it but didn't make it an issue | KNOWLEDGE (boundary unstated) | WORKED EXAMPLE in decompose Step 7; soft-AC scan in review Criterion 6 |

## Changes made this iteration (one row per edit)
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1,3,4,5 | NEW bundled script (STRUCTURAL) | `epic-decompose/scripts/validate_decomposition.py` (new) | Deterministically checks the 4 mechanically-decidable contract rules (body sections, component vocabulary, Rule 11 closure, priority inheritance) with judge-parity logic; `--self-check` verifies each check fires on a bad fixture and passes a good one | Yes — exits 0 on all 28 trials that currently pass those gates (verified on the full 33-trial corpus) |
| 1,3,4,5 | STRUCTURAL (ordered procedure) | `prompts/decompose-agent.md` Step 8c (+ Step 0 triage path) | Validator run is now a precondition of the `decompose_complete` sentinel ("proceed only once it prints OK") — the step can no longer be forgotten | Yes — additive gate; no-op when contract already satisfied |
| 1,3,4,5 | STRUCTURAL (review feeds revise) | `prompts/review-agent.md` new Step 1.7 | Reviewer runs the validator, converts every VIOLATION into an issues-list entry + zeroed criterion (severity/criterion mapping given) — the unconditional revise pass then fixes what the LLM reviewer missed (case-018 t2's false "blocks no P0 work" assertion) | Yes — issues added only on violations; review_discipline consistency preserved by the explicit zeroing instruction |
| 1,3,4,5 | STRUCTURAL (closed loop) | `prompts/revise-agent.md` Step 2 + Step 4 | Mechanical correction playbook per violation type (rename heading → `## Scope`; canonical component; add Rule 11 edge; raise priority to P0) + re-run validator until OK before finishing | Yes — revise only acts on review issues |
| 4 | CONTRACT | `prompts/decompose-agent.md` Step 2 | Fallback rewritten: component values copied verbatim from the canonical list, never invented/paraphrased/combined; cross-component epic gets the single most-relevant canonical name + logged note. The old example ("Model Serving Runtimes" — itself non-canonical) was the trap | Yes — all passing tasks already use canonical names verbatim |
| 2 | KNOWLEDGE + worked example | `prompts/decompose-agent.md` Step 4 | Redundant-HLR rule: two HLRs on the same surface (one a restatement/presentation mode of the other) = ONE epic listing both at the higher priority; a P0/P1 pair on a shared surface is redundant wording, not a deferral signal | Yes — verified no passing decomposition contains a same-surface presentation-mode split; case-015 t0 (passing) already consolidates |
| 2 | KNOWLEDGE | `prompts/review-agent.md` Criterion 3 | Presentation-mode split = scope duplication (major) even when the second epic only extends the first's surface; priority label is not a boundary | Yes — same narrow condition |
| 6 | KNOWLEDGE + worked example | `prompts/decompose-agent.md` Step 7 | External schedule constraints (lab queues, review-board cadence) are not ACs — Risks/Health Warnings; AC sits at the engineering completion point you control | Yes — grep-verified no passing trial carries a schedule-note AC |
| 6 | KNOWLEDGE | `prompts/review-agent.md` Criterion 6 | Soft-AC scan: flag schedule-constraint ACs as minor issues with the "move to Risks/Notes" correction (feeds the revise pass) | Yes — same condition |
| 1 | CONTRACT | `prompts/decompose-agent.md` Step 8b | The four body-section headings are literal for EVERY epic incl. docs-authoring; a content outline goes INSIDE `## Scope`, never as a renamed `## Content Outline` heading | Yes — all other trials already use literal headings (surveyed every docs epic in all 33 trials) |

SKILL.md (dispatcher) deliberately unchanged: dispatcher_turn_discipline passed on all 11 val tasks; no dispatcher-driven failure exists.

## Verify-the-fix (one line per change: the trace it targets → what the guard/computation/new-tool now does on those exact inputs)
- **Validator script** — run against all 33 trial artifacts extracted from `./trajectories/`: flags EXACTLY case-013 t2 (component 'Model Serving Stack'), case-018 t2 (E004 P1 blocks P0 E003), case-020 t1 (E006 missing 'Scope'), case-024 t1 (Rule 11: BRANCH-C-E004 missing E002) — the 4 mechanically-failing trials — and nothing else except case-018 t0's identical latent priority violation (same defect the t2 grader dinged; t0's grader missed it; fix direction = grader-endorsed "E004 must inherit P0"). `--self-check` passes (each check fires on a bad fixture, clean on a good one).
- **trace case-020 t1**: decompose agent's Write of E006 (event 346) had `## Content Outline`, no `## Scope` → artifact_contract hard-gate failure, reward 0. With the edit: Step 8b forbids the renamed heading, and the validator (precondition of `decompose_complete`) exits 1 with "body missing 'Scope' section" — the agent renames the heading before the sentinel; even if missed there, review Step 1.7 records it critical → unconditional revise renames it (revise playbook names the rename correction explicitly).
- **trace case-015 t1/t2**: Health Warning 4 records "HLR-1/HLR-3 overlap … resolved by splitting into separate epics"; review endorsed 14/14. With the edit: Step 4's redundant-HLR rule names this exact pattern (side-by-side + diff view of the same run data = one capability, one epic listing both HLRs) — the t0 passing trial already produced this shape citing Step 4, so the rule makes the consistent behavior the only permitted one; review Criterion 3 flags a presentation-mode split as major → revise merges. Blast radius: no passing task splits two presentation modes of one surface (checked all passing epic lists: case-014/016/017/019/029/030 split by component, binary, work-type, or repo — never by presentation mode of one surface).
- **trace case-018 t2**: E003 (P0) frontmatter lists E004 (P1) as direct dependency; grader: "the rule requires E004 to inherit P0". With the edit: validator prints "priority inheritance: …E004 (P1) blocks P0 epic E003…"; decompose fixes before sentinel, or review Step 1.7 maps it to a Criterion 1 major issue → revise raises priority (playbook). On t0 (currently 1.0 with the same latent defect): the fix direction is the stated rule and the grader-endorsed remedy — no other behavior changes.
- **trace case-013 t2**: E005 `component: Model Serving Stack` (canonical list has Serving Runtimes/KServe/Platform Operator). With the edit: Step 2 forbids invented/combined names and says a cross-component epic carries the single most-relevant canonical name + logged note; validator exits 1 on any non-canonical value → agent picks e.g. KServe and logs the span. Blast radius: every passing trial's components are already verbatim-canonical.
- **trace case-024 t1**: BRANCH-C-E004 (docs) closure missed main-plan E002. With the edit: validator's Rule 11 check (judge-parity: universe = non-branch Implementation non-docs; closure over dependencies incl. through branch nodes) prints the missing epic; review maps to Criterion 2 critical → revise adds the edge (playbook: "add the missing epic to the docs epic's dependencies").
- **trace case-013 t0**: E005's last AC is verbatim a schedule-risk note ("Lab scheduling and review-board cadence are externally controlled and cannot be compressed…"). With the edit: Step 7's worked example names this exact boundary (submission-triage = valid AC; externally-controlled cadence = Risks); review Criterion 6 flags it minor with the move-to-Risks correction → unconditional revise relocates it → the dq grader's "one minor gap" disappears. Blast radius: no passing trial has a schedule-note AC (grep over all 18 passing-trial AC sections).

## Process & features used
- Serial this iteration (no subagents/worktrees): the diagnosis phase needed the benchmark's judge source cross-read against every failing trial, which is one coherent reasoning chain; the corpus extraction + validator verification was a single scripted loop. Parallel edit-subagents would have conflicted on the same three prompt files.
- Prior iterations I read from ./prior_iterations/ + ./RUNMAP.md: none exist (this is iteration 1 on the seed).
- Read `guidance/skill-package/SKILL.md` (levers: skipped-step→bundled-script, body contract, worked examples) and `guidance/diagnose/SKILL.md` (failure-site/expectation clustering, flaky-vs-failing separation).

## Good things to PRESERVE (do not let a future iteration undo these)
- The validator's judge-parity logic (substring heading match, branch exemptions, docs-authoring priority exemption, closure semantics) — it was verified flag-for-flag against all 33 trials; loosening/tightening it without re-running that corpus check risks false positives on passing tasks.
- The "validator as precondition of decompose_complete" ordering — the sentinel is the only structural hook that makes the check unavoidable.
- The redundant-HLR rule's narrow condition (same surface + same team + presentation-mode/restatement) — broadening it to "similar HLRs" would wrongly consolidate legitimate component/work-type splits (case-019, case-016 pass on those).

## Deliberately skipped (cluster + why)
- case-013 t0's ai-signal rationale lean (E001's investigation_signals citing E003's ACs): named in feedback but did NOT drive the dq-4 verdict (the soft AC did — grader's "one minor gap"); fails the REAL test.
- Draft-ID-in-body and signals-table-in-body checks in the validator: no val trial fails on them (not REAL this iteration); cheap to add later if a future iteration shows them failing.
- SKILL.md frontmatter/description: the runner invokes the skill directly; triggering is not a failure mode here.
- run_report_consistent / dispatcher behaviors: all val trials pass those gates.

## Environment faults
None. All 33 trials ran to completion; every failure is a capability failure.

---

# DIAGNOSIS.json — machine-readable diagnosis (REQUIRED under agent-optimize)

```json
{
  "candidate": "cand_0001",
  "headline": "Bundled contract validator (judge-parity) as a structural gate in decompose/review/revise, plus targeted knowledge fixes for redundant-HLR consolidation, canonical component fallback, and soft-AC boundary",
  "clusters": [
    {"id": "A", "name": "epic body missing required section",
     "detail": "Decompose agent renamed '## Scope' to '## Content Outline' on a docs-authoring epic; artifact_contract hard gate fails and reward drops to 0. Mechanically checkable, skipped by internal review and revise.",
     "tasks": ["case-020-hardware-dependent-investigation"], "scope": "BOUNDED", "latent": false,
     "tag": "BEHAVIORAL"},
    {"id": "B", "name": "redundant HLRs split by priority label",
     "detail": "Two HLRs describing one comparison surface (side-by-side + diff view) split into two epics; agent saw the overlap and split anyway; review endorsed 14/14. Expected handling: one epic listing both HLRs.",
     "tasks": ["case-015-redundant-hlrs"], "scope": "BOUNDED", "latent": false,
     "tag": "KNOWLEDGE"},
    {"id": "C", "name": "priority inheritance violation",
     "detail": "P1 epic directly blocks a P0 epic (E003 lists E004); rule exists but agent and reviewer both skip the mechanical enumeration of dependencies. Same latent defect present in a currently-passing trial (case-018 t0) — grader-inconsistent.",
     "tasks": ["case-018-cross-strategy-dependency"], "scope": "BOUNDED", "latent": true,
     "tag": "BEHAVIORAL"},
    {"id": "D", "name": "non-canonical component name",
     "detail": "component 'Model Serving Stack' invented for a cross-component epic; prompt's fallback example itself modeled inventing a non-canonical name.",
     "tasks": ["case-013-human-process-gates"], "scope": "BOUNDED", "latent": false,
     "tag": "KNOWLEDGE"},
    {"id": "E", "name": "Rule 11 docs-last closure gap",
     "detail": "Branch-C docs-authoring epic's transitive dependencies missed one main-plan Implementation epic (E002); rule stated, one edge omitted.",
     "tasks": ["case-024-real-default-vector-store"], "scope": "BOUNDED", "latent": false,
     "tag": "BEHAVIORAL"},
    {"id": "F", "name": "schedule-risk note as acceptance criterion",
     "detail": "E005's final AC restates an external schedule constraint (lab/review-board cadence) instead of a testable condition on the epic's deliverable — the rubric's canonical soft-AC exemplar.",
     "tasks": ["case-013-human-process-gates"], "scope": "BOUNDED", "latent": false,
     "tag": "KNOWLEDGE"}
  ],
  "edits": [
    {"id": "E1", "title": "New bundled validator script (body sections, component vocabulary, Rule 11, priority inheritance) with judge-parity logic and --self-check",
     "files": ["epic-decompose/scripts/validate_decomposition.py"], "lever": "STRUCTURAL",
     "clusters": ["A", "C", "D", "E"], "blast_radius": "BOUNDED",
     "verified": "Run over artifacts of all 33 trials extracted from ./trajectories/: flags exactly the 4 mechanically-failing trials (+ case-018 t0's identical latent priority defect); exits 0 on all 28 others; --self-check passes"},
    {"id": "E2", "title": "Validator as precondition of decompose_complete in decompose Step 8c (+ triage path in Step 0)",
     "files": ["epic-decompose/prompts/decompose-agent.md"], "lever": "STRUCTURAL",
     "clusters": ["A", "C", "D", "E"], "blast_radius": "BOUNDED",
     "verified": "Sentinel ordering makes the run unavoidable; no-op on contract-clean decompositions (all passing trials)"},
    {"id": "E3", "title": "Review Step 1.7: run validator, map every VIOLATION to an issues-list entry + zeroed criterion",
     "files": ["epic-decompose/prompts/review-agent.md"], "lever": "STRUCTURAL",
     "clusters": ["A", "C", "D", "E"], "blast_radius": "BOUNDED",
     "verified": "Targets the exact reviewer misses observed in traces (case-018 t2 'blocks no P0 work' assertion, case-024 t1 Rule 11 gap, case-020 t1 unseen section); issues added only on violations"},
    {"id": "E4", "title": "Revise playbook for validator violations + re-run until OK in Step 4",
     "files": ["epic-decompose/prompts/revise-agent.md"], "lever": "STRUCTURAL",
     "clusters": ["A", "C", "D", "E"], "blast_radius": "BOUNDED",
     "verified": "Revise only acts on review issues; corrections are the grader-endorsed remedies"},
    {"id": "E5", "title": "Step 2 component constraint rewritten: verbatim-from-list only, never invent/combine; span noted not invented",
     "files": ["epic-decompose/prompts/decompose-agent.md"], "lever": "CONTRACT",
     "clusters": ["D"], "blast_radius": "BOUNDED",
     "verified": "trace case-013 t2 E005 'Model Serving Stack'; all passing trials already verbatim-canonical"},
    {"id": "E6", "title": "Step 4 redundant-HLR consolidation rule with worked example",
     "files": ["epic-decompose/prompts/decompose-agent.md"], "lever": "KNOWLEDGE",
     "clusters": ["B"], "blast_radius": "BOUNDED",
     "verified": "trace case-015 t1/t2 Health Warning 'overlap resolved by splitting'; passing trial t0 already consolidates; no passing task splits presentation modes of one surface"},
    {"id": "E7", "title": "Review Criterion 3: presentation-mode split is scope duplication (major)",
     "files": ["epic-decompose/prompts/review-agent.md"], "lever": "KNOWLEDGE",
     "clusters": ["B"], "blast_radius": "BOUNDED",
     "verified": "case-015 t2 review endorsed the split 14/14 — the added check names the exact pattern"},
    {"id": "E8", "title": "Step 7 AC boundary: external schedule constraints are not ACs (worked example)",
     "files": ["epic-decompose/prompts/decompose-agent.md"], "lever": "KNOWLEDGE",
     "clusters": ["F"], "blast_radius": "BOUNDED",
     "verified": "trace case-013 t0 E005 final AC is verbatim the example; no passing trial has a schedule-note AC"},
    {"id": "E9", "title": "Review Criterion 6: soft-AC scan flags schedule-constraint ACs (minor, move to Risks)",
     "files": ["epic-decompose/prompts/review-agent.md"], "lever": "KNOWLEDGE",
     "clusters": ["F"], "blast_radius": "BOUNDED",
     "verified": "case-013 t0's internal review observed the soft AC but scored around it; the issue entry now feeds the unconditional revise pass"},
    {"id": "E10", "title": "Step 8b: four body-section headings are literal for every epic incl. docs-authoring",
     "files": ["epic-decompose/prompts/decompose-agent.md"], "lever": "CONTRACT",
     "clusters": ["A"], "blast_radius": "BOUNDED",
     "verified": "surveyed all 33 trials' docs epics: only case-020 t1 deviated (Content Outline); every other docs epic uses the literal headings"}
  ],
  "skipped": [
    {"title": "ai-signal rationale scoping (score against own epic's scope)", "reason": "named in case-013 t0 feedback but did not drive the dq-4 verdict (the soft AC did) — fails the REAL test"},
    {"title": "draft-ID-in-body and signals-table-in-body validator checks", "reason": "no val trial fails on them this iteration"},
    {"title": "SKILL.md description/frontmatter edits", "reason": "skill is invoked directly by the runner; triggering is not a failure mode"}
  ],
  "techniques": ["bundled-script enforcement (skipped step → code)", "judge-parity corpus verification", "worked example", "output contract clarification", "review-to-revise issue mapping"]
}
```
