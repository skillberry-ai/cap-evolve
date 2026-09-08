# artifacts/ — skill packages

What the recipes in [`../recipes/`](../recipes/) actually produced. Each package is three
files — `SKILL.md` (the instructions an agent reads), `INSTRUCTIONS.md` and `PROCESS.md`
(cap-evolve's own optimizer-facing bookkeeping, carried through unedited) — under one
directory per candidate.

| directory | what it is |
|---|---|
| `v{1,2}/seed/` | the starting skill, before any optimization |
| `v{1,2}/best/` | the champion candidate — what the headline run in [`../results/`](../results/) actually scored and (for v2) what a consumer of this branch should read as "the result" |
| `v1/rejected/cand_000{1,2}/` | v1's two candidates, both proposed and both rejected by the gate |
| `v2/rejected/run_20260816_202942-cand_0001/` | v2's iteration-1 candidate, proposed and rejected — the one run whose optimizer *did* write a journal entry (see [`../reports/README.md`](../reports/README.md)'s "v2 journal caveat") |
| `v2/discarded/run_run_20260818_161550-cand_000{1,2}/` | not gate-rejected — **discarded by an operator bug**. A `--resume --run-ts` invocation silently started a fresh run instead of resuming, so these two candidates were produced against a restarted state and never evaluated against the real headline lineage. See [`../results/v2/summary.md`](../results/v2/summary.md)'s "The discarded iteration 3" section |

`v1/seed/SKILL.md` and `v1/best/SKILL.md` are **byte-identical** (`diff` reports no
difference). v1's headline run never accepted a candidate — `best_id == "seed"` in
`final.json` — so `v1/best/` exists only to make "what actually shipped" queryable the same
way for both experiments, not because anything changed.

## The v2 diff: seed → champion

v2's champion (`run_20260818_161550`, `cand_0001`) is the one artifact in this branch where
`seed/` and `best/` genuinely differ: 48 insertions, 14 deletions, all in `SKILL.md`, none in
`INSTRUCTIONS.md` or `PROCESS.md`. Run `diff -u artifacts/v2/seed/SKILL.md
artifacts/v2/best/SKILL.md` to see it verbatim. Five changes, all in the tool-selection
guidance:

1. **The core fix.** Seed's rule was *"Always use `get_job_log` instead of `get_job`"* —
   flatly wrong in this simulator, where `get_job_log` returns only `{log,
   log_original_size, log_trimmed_size}` and `get_job` returns the metadata
   (`status`, `template_name`, timings, `revision`, ...). The champion replaces the
   blanket rule with a decision: call `get_job` for metadata questions, `get_job_log` for
   log/failure analysis, and both when a question needs both — explicitly noting that
   calling both is *not* a redundant re-fetch, since they return disjoint fields.
2. A matching fix to the "Don't re-fetch" rule (point 4): the seed's version could be read
   as forbidding a second `query_aap2` call on the same job at all; the champion narrows it
   to forbidding re-fetching the *same field twice*.
3. A shortcut for simple metadata questions: the final-report rule no longer demands the
   full config-trace table when the question only asks for outcome/template/status/timing.
4. A new retry rule for transient session/timeout errors (retry once before reporting infra
   failure, and report known identifiers even on a persisted failure).
5. The tool-response-format reference table at the bottom is rewritten to match the actual
   field names above (`job_name`/`template_name`/`duration_seconds` etc., split by which
   action returns which fields).

All five are the same edit repeated at different call sites: **the seed skill's `get_job` vs.
`get_job_log` guidance was factually wrong for this simulator, and every fix is downstream of
correcting it.** None of the five touch reasoning, tool-call ordering logic, or the
config-hierarchy workflow — see
[`../results/v2/summary.md`](../results/v2/summary.md)'s tool-call-vs-answer decomposition
for why this run's win is best read as a documentation correction rather than a reasoning
improvement, and for the open, unresolved question of whether "`get_job_log` has no metadata
in this simulator" also holds against the real AAP2 API.

## v1's rejected candidates

`v1/rejected/cand_0001/` and `cand_0002/` are the two proposals from the headline pilot, both
rejected on the mean but for different reasons — `cand_0002` is, per
[`../results/v1/summary.md`](../results/v1/summary.md)'s "candidate the gate was right to
reject and wrong to discard" section, the only artifact in v1 that ever matched trajectory on
either optimized task. Diff it against `v1/seed/SKILL.md` if you want to see what a correct
gate call still threw away.
