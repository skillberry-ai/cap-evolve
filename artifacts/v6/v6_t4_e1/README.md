# v6_t4_e1 artifacts (T-mrg)

| Directory | Bundle | Built by |
|---|---|---|
| `m1_order/` | merge by order: the 34 diffs applied in ascending T-opt gain, later wins (`git merge -X theirs`) | `examples/parsec/v6_t4/build_merges.py`, no LLM |
| `m3_smart/` | smart merge: an LLM merger with no access to any score merged by meaning | a fresh Claude Code agent (Opus 5.5) + 3 sub-agents; decisions in `m3_smart/MERGE_LOG.md` |
| `m2_nonconflict/` | non-conflicting hunks: the 91 of 188 hunks no other task touches | `build_merges.py`, no LLM |
| `merge_inputs/` | what the merges were allowed to read: the Seed, each task's `edit.diff` and request, and its `PROCESS.md` with every score removed | |

Each bundle is the 8 skill files plus a `MERGE_LOG.md`. All three were frozen before any evaluation.
