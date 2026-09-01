# PROCESS — what I did this iteration (explainability; REQUIRED)

## Ranked issue list (clusters by # failing trials, biggest first)
| rank | cluster | trials | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Hand-rolled export omits `toNonIndexed()` | t1, t3, t8, t9 (4/10) | Agent writes its own export script and drops `if (geom.index) geom = geom.toNonIndexed();`. Indexed geometry's vertex cloud differs from the de-indexed ground truth → Chamfer >> 2e-4 → both `test_part_meshes_*` and `test_link_meshes_*` fail. | BEHAVIORAL | SCRIPT (ship complete correct exporter) + BODY (steer to run it) |
| 2 | Shipped `export_link_objs.mjs` is buggy | t0 (1/10; part passed, link failed) | The skill's own per-link exporter (which SKILL.md tells the agent to run) omits `toNonIndexed()` in `addGeometry`. Running it yields indexed merged links → `test_link_meshes_match_ground_truth` fails. Reproduced: 848 verts vs GT 1608, worst Chamfer 1.09. | CAPABILITY-GAP (bug in shipped code) | SCRIPT (bugfix) |

Passing trials (t2,t4,t5,t6,t7) all hand-rolled a script that DID include `toNonIndexed()` → the good behavior to make consistent.

## Changes made this iteration
| cluster | edit class | file / tool | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 | SCRIPT (new) | `threejs/scripts/export_structure.mjs` | New complete exporter: bakes world transforms, **de-indexes**, nearest-named-ancestor part assignment, writes both `part_meshes/<part>/<mesh>.obj` and merged `links/<part>.obj`. Paths are flags (defaults `/root/...`). Mirrors the general algorithm, no task-specific literals. | Yes — new file; only runs if invoked. |
| 1 | BODY | `threejs/SKILL.md` | Added top section directing the agent to RUN `export_structure.mjs` for the part-structure task instead of reimplementing; added "`toNonIndexed()` is mandatory" note to the bake section; listed the script first under Scripts with execute intent. Additive; removes no existing guidance. | Yes — additive, steers toward the behavior passing trials already used. |
| 2 | SCRIPT (bugfix) | `threejs/scripts/export_link_objs.mjs` | Added `if (geom.index) geom = geom.toNonIndexed();` to `addGeometry`. General correctness fix for any vertex-cloud comparison. | Yes — indexed output is essentially never the intended result; fix can only correct. |

## Verify-the-fix (ran against the REAL task inputs with the REAL verifier logic)
- Generated ground truth from the task's `gen_ground_truth.mjs` on the actual `object.js` (three@0.170.0, matching Dockerfile).
- `export_structure.mjs`: dir-name set, per-part mesh-name set, and link-name set all EQUAL ground truth; worst Chamfer = 0.0 for both part_meshes and links → both failing tests pass exactly.
- `export_link_objs.mjs` BEFORE fix: 2 link failures, worst Chamfer 1.09 (848 vs 1608 verts) — reproduces t0. AFTER fix: 0 failures, worst Chamfer 0.0.
- Blast radius: only task in val/test is threejs-structure-parser; edits are additive/corrective and cannot push the already-passing hand-rolled path onto a worse one.

## Process & features used
- Serial (single task, tight cluster); no subagents needed. Diagnosed all 10 trajectories by extracting each run's written script and correlating `toNonIndexed` presence with pass/fail (perfect correlation except t0, explained by the shipped-script bug).
- Prior iterations: none (seed only; LEDGER/RUNMAP empty).

## Good things to PRESERVE
- `export_structure.mjs` as the canonical full-task exporter; the "`toNonIndexed()` mandatory" guidance; the fixed `export_link_objs.mjs`.

## Deliberately skipped
- No DESCRIPTION edit: the `threejs` skill already triggers (Skill selected in every trace).
- Did not touch `obj-exporter` skill: its snippets already de-index (exportMesh + mergeMeshes) and no failure traced to it.
