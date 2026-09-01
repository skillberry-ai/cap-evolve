# PROCESS — what I did this iteration (explainability; REQUIRED)

Parent: seed (val 0.626). cand_0001 (script + reference "copy-verbatim") was REJECTED
(val 0.517, Δ-0.109, broke={}, fixed={}) and reverted — I build on that result, I do not
re-try it.

## Ranked issue list (clusters by # failing tasks × trials, biggest first)
| rank | cluster | tasks | shared root cause | tag | planned change class |
| --- | --- | --- | --- | --- | --- |
| 1 | Wrong Wyckoff multiplicity method (0.45 runs: t0,t4,t6,t8 — 4/9 completed trials) | crystallographic-wyckoff-position-analysis | Agent hand-writes `get_symmetrized_structure().wyckoff_symbols`/`.equivalent_sites`, reads multiplicity off the `"4a"` prefix or keeps one orbit per letter → structures with several orbits on the same letter (e.g. Al₂O₃ five `i` orbits ⇒ should be 20) are reported as 4. Agent validates ONLY against the single provided example (FeS2_mp-226), where wrong≡right (one orbit per letter), so its own check never catches the bug. | KNOWLEDGE (wrong rule + non-discriminating self-check) | BODY (inline correctness block + self-check) |
| 2 | Coordinate `% 1` wrapping (0.82 runs: t1,t3,t7) | same task | Wrapping coords modulo 1 / collapsing `1/1`→`0` drops representative coords that legitimately round to `"1"`, capping correct-API runs at 0.82. | KNOWLEDGE | BODY (same block, pitfall bullet) |
| — | t9 timeout (0.0) | same task | bench eval run timed out (2400s) | infra noise | SKIPPED (uncontrollable, per framework label) |

Only ONE task exists in this run and it exercises only the `pymatgen` skill (sympy is used
but never mis-used). There is no second skill/cluster to fix — breadth here means covering
BOTH sub-clusters of the one task, which the single block below does.

## Changes made this iteration (one row per edit)
| cluster | edit class | file | what & why it generalizes | protects passing? |
| --- | --- | --- | --- | --- |
| 1 & 2 | BODY (additive) | `pymatgen/SKILL.md` | Added a compact, self-contained "Wyckoff multiplicities + first-atom coordinates" block in the always-loaded body (right after "When to Use", before Quick Start). States the GENERAL rule — multiplicity[letter] = total atoms carrying that letter summed over ALL orbits (`Counter(get_symmetry_dataset().wyckoffs)`), first atom in structure order via `Rational(c).limit_denominator(12)` — the two pitfalls (no symmetrized `wyckoff_symbols`; no `% 1` wrap), and a discriminating self-check ("the single worked example usually has one orbit per letter and cannot reveal a wrong multiplicity — validate on a multi-orbit-same-letter structure"). No hardcoded filenames/values/answers. | Yes — additive; only this one task uses pymatgen; sympy untouched; no other skill path changed. |

## Why this is DIFFERENT from cand_0001 (not a re-test of a refuted approach)
cand_0001 put the fix in a NEW bundled script ("copy verbatim") + reference edits + a §3
callout that all pointed INTO those files. Trace evidence: **all 10 trials have
`read_ref=False` — no trial ever opened the reference, and none ran a bundled script.**
So cand_0001's carriers were provably dead → its edits were inert and its Δ-0.109 was trial
noise (broke={}, fixed={}). I did NOT re-add the script (also: unverifiable locally — no
working pymatgen import / no CIFs, so a script edit would fail the VERIFIED test). I did NOT
beef up the never-read reference. The ONLY untried channel is the always-loaded SKILL.md
body itself, carrying the complete inline rule + the self-check that attacks the actual
blind spot (non-discriminating validation). That is the sole edit.

## Verify-the-fix (one line per change)
- Cluster 1 (t0/t4/t6/t8 → 0.45): traced t0 — agent used `get_symmetrized_structure()`,
  kept only the first orbit per letter, output Al₂O₃ `{"i":4}` where the atoms-per-letter
  truth is `i:20`. The block states multiplicity = `Counter(dataset.wyckoffs)` (total atoms
  per letter) and forbids the symbol-prefix/one-orbit reading, and the self-check forces
  validation on a multi-orbit-same-letter case (the one case the provided example can't
  cover). Verifier semantics confirmed against the task's own example (FeS2 `a:4,c:8` = 4 Fe
  + 8 S) and the correct-approach reference. Code snippet AST-parses as valid Python.
- Cluster 2 (t1/t3/t7 → 0.82): the "do not wrap modulo 1 / do not collapse `1`→`0`" pitfall
  matches the exact deviation (`% 1`) present in those traces (mod1=True) and absent in the
  1.0 runs (t2,t5).
- Blast radius: single task; pymatgen-only; strictly additive body text — cannot push the
  already-1.0 runs (t2,t5, which already use `get_symmetry_dataset().wyckoffs` + Rational,
  no mod1) onto a worse path since the block describes exactly what they already do.

## Process & features used
- Serial (single task, single skill, one failing cluster set) — no subagents/worktrees
  needed; the whole signal is one task's 10 trajectories. Diagnosed by extracting each
  trial's final `solution.py` method + score, and grepping all traces for
  reference-reads/API-choice/`% 1` (found reference NEVER read → the decisive fact behind
  cand_0001's inert result).
- Read from ./prior_iterations/cand_0001 (PROCESS.md + diff.patch) + RUNMAP + LEDGER +
  JOURNAL: learned that the script/reference channel is dead here and that its regression was
  noise, which redirected me to the body-inline channel and away from re-adding the script.

## Good things to PRESERVE (do not let a future iteration undo these)
- The inline body block is the ONLY surfaced channel that reaches this agent (it never opens
  references/scripts). Keep the correct rule IN THE BODY; do not move it back behind a
  reference or re-add a bundled "copy-verbatim" script (proven inert + unverifiable).

## Deliberately skipped (cluster + why)
- t9 timeout: genuine infra noise (bench eval timed out), uncontrollable — per framework label.
- NEW bundled script / reference rewrite: dropped. References are never read; a script fails
  VERIFIED (pymatgen won't import locally, no CIFs to run against) and cand_0001 showed both
  channels inert. Adding them would be a guess and a re-test of a rejected approach.
- sympy skill: not implicated in any failure; untouched to avoid regression.
