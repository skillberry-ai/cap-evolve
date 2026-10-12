# RUNMAP — every prior iteration's working dir (read these before proposing)

For each prior iteration, its artifacts are copied into `./prior_iterations/<candidate>/`:
- `PROCESS.md` — what that iteration did (ranked issues, changes, verify-the-fix, process)
- `diff.patch` — the EXACT capability edit it made vs its parent

The live run dir (read-only) is at `.capevolve/run_epic-glm53-v5` if you need `rollouts/<split>/` traces or the git log.

| iter | candidate | parent | outcome | val | ./prior_iterations/<id>/ |
| --- | --- | --- | --- | --- | --- |
| 1 | cand_0001 | seed | reject | 0.812 | PROCESS.md + diff.patch |

Before proposing, read the PROCESS.md + diff.patch of the prior iterations that targeted the SAME cluster you are about to work on — so you BUILD ON them rather than repeat a rejected or already-tried edit. Cross-reference LEDGER.md for which of them the gate accepted vs rejected, and JOURNAL.md for the lessons.
