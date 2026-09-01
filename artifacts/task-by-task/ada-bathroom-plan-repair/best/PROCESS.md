# PROCESS — cand_0003 (parent cand_0002)

## Trajectory reality (cand_0002, 10 trials of the one val task ada-bathroom-plan-repair)
Parsed each trial's `score.reward`, failed-test names, AND which skills it launched:

| trial | reward | skills launched | outcome |
| --- | --- | --- | --- |
| t0 | 1.0 | extraction only | pass (hand-rolled correctly, got lucky) |
| t1 | 1.0 | extraction + accessibility + repair | pass |
| t2 | 1.0 | extraction + accessibility | pass |
| t3 | 1.0 | extraction + accessibility | pass |
| t4 | 1.0 | extraction + accessibility | pass (ran repair_layout.py via accessibility pointer) |
| t5 | 0.0 | **extraction only** | FAIL `test_violation_list_is_consistent_with_plan_view_rules` |
| t6 | 1.0 | extraction + accessibility | pass |
| t7 | 1.0 | extraction + accessibility | pass |
| t8 | 0.0 | **extraction only** | FAIL 5 tests incl. missing `violations_before.json` |
| t9 | 1.0 | extraction + accessibility | pass |

Mean = 8/10 = 0.800 (matches val). **Every trial that launched `ada-plan-view-accessibility`
passed (7/7). Of the 3 that launched extraction only, 2 failed (t0 got lucky).**

### The single root cause (one cluster, high leverage)
The bundled scripts already work: `repair_layout.py:132` emits the exact canonical name
`toilet_centerline_from_side_wall_range` the verifier expects, and it writes `violations_before.json`.
The failures are NOT a code bug — they are a **skill-invocation-consistency (trigger) bug**:

- **t5**: launched only `architectural-dxf-extraction`, never `ada-plan-view-accessibility` or
  `geometric-layout-repair`, so it never saw the repair-script pointer → hand-rolled the violation
  list and used the wrong rule name `toilet_centerline_from_side_wall` (verifier wants
  `..._range`). Failed `test_violation_list_is_consistent_with_plan_view_rules`.
- **t8**: same — extraction only → never produced `violations_before.json` at all → 5 tests failed.

The agent reliably launches the extraction skill but inconsistently launches the accessibility +
repair skills, and when it stops after extraction it hand-rolls the violations/repair and fails.

## Ranked cluster list
| rank | cluster | failing trials | root cause | tag | edit class |
| --- | --- | --- | --- | --- | --- |
| 1 | Agent stops after extraction; never launches accessibility/repair skills → hand-rolls violations + repair | t5, t8 (both val failures) | Trigger/routing gap: `ada-plan-view-accessibility` & `geometric-layout-repair` descriptions don't fire on the task's "identify violations / produce repaired layout" phrasing, and nothing routes the agent onward from the always-launched extraction skill. | BEHAVIORAL (trigger consistency) | DESCRIPTION + BODY (additive routing pointer) |

No other clusters exist — all 6 verifier tests pass whenever the repair pipeline runs.

## Changes made this iteration (3 additive edits, no code change — the scripts already work)
| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | DESCRIPTION | `ada-plan-view-accessibility/SKILL.md` frontmatter | Front-loads "identifying or reporting plan-view ADA violations … producing a before-repair violation list (violations_before.json)" so the task's "identify the plan-view ADA-derived accessibility violations" phrasing triggers the skill. Third-person, no all-caps. | Yes — only widens when the skill fires; the 7 trials that already launch it are unchanged. |
| 1 | DESCRIPTION | `geometric-layout-repair/SKILL.md` frontmatter | Front-loads "produce a minimally invasive repaired … layout — repaired_layout.json plus a modified CAD/DXF" so "produce a minimally invasive repaired CAD layout" triggers it. | Yes — additive trigger only. |
| 1 | BODY (additive) | `architectural-dxf-extraction/SKILL.md` | New top section "Extraction is only stage 1 — do not stop here": after extraction, use the `ada-plan-view-accessibility` skill to write `violations_before.json` (canonical name `toilet_centerline_from_side_wall_range`, not a hand-invented one) and the `geometric-layout-repair` skill to write the repair, running their bundled scripts. This is the ONE skill launched in every trial, so it is the surest place to route the agent onward. | Yes — additive; the 7 already-correct trials already do this. It only redirects the extraction-only trials (t5/t8) onto the verified-correct path. |

## Verify-the-fix (tie each edit to the failed assertion + blast radius)
- **t5** failed `test_violation_list_is_consistent_with_plan_view_rules` because it produced rule
  `toilet_centerline_from_side_wall` instead of `..._range`. The bundled `repair_layout.py`
  emits `..._range` (verified at line 132). Routing the agent to launch the accessibility/repair
  skills (edits above) makes it run that script → correct `violations_before.json` → test passes.
- **t8** failed because `violations_before.json` was never written; running the repair pipeline
  writes it. Same routing fix produces the file.
- **Blast radius / SAFE:** every trial that launched `ada-plan-view-accessibility` already passes
  (7/7). t0 passes WITHOUT it only by luck; routing it onto the pipeline makes it more robust, not
  worse. The edits are purely additive (broadened triggers + a "continue" pointer) and change NO
  guidance the passing trials already follow. No script/code changed, so no verified-correct output
  can regress. Single-task val → blast radius confined to this task class.
- **Non-overfitting:** no filename/value/marker/answer hardcoded. `violations_before.json`,
  `repaired_layout.json`, `repaired_plan.dxf` and the canonical rule name are the task-class output
  contract (already named throughout the existing skills), not a per-instance literal. The routing
  ("after extraction, detect violations then repair") is the general shape of every task in this class.
- **Valid packages:** all three frontmatters parse; descriptions 211–312 chars; bodies ≤86 lines;
  no markdown reference links added (sibling skills/scripts named in prose, as the existing bodies
  already do), so no broken links.

## Process & features used
- Serial diagnosis (single val task, 10 trials). Parsed rewards, failed-test traces, AND the
  per-trial `Launching skill:` events from `./trajectories/` — the skill-launch signal is what
  isolated the root cause (extraction-only ⇒ failure). No subagents needed for one cluster.

## Good things to PRESERVE
- The three bundled scripts from cand_0002 (repair_layout.py, extract_layout.py, write_repaired_dxf.py)
  and their execute-intent SKILL sections — verified correct; this iteration only improves how
  reliably the agent reaches them.

## Deliberately skipped
- No script/code edits: the scripts already produce the correct outputs; the miss was invocation,
  not computation. Adding another script would not address a routing gap.
- No orchestrator/mega-script: the failure was skill LAUNCH, not partial script execution, so a
  single-command orchestrator adds cross-skill path fragility without addressing the cause.
- Did NOT touch `architectural-dxf-extraction`'s trigger (it fires reliably every trial — narrowing
  it risks a regression). Only added a body pointer.
