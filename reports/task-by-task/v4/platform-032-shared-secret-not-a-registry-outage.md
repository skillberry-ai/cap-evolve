# platform-032-shared-secret-not-a-registry-outage

<!-- BEGIN:auto -->

**task:** `platform-032-shared-secret-not-a-registry-outage`  
**category:** platform  
**tranche:** challenge  
**services:** platform, github  
**status:** optimized  
**run:** `.capevolve/v4_t2_e1_platform-032-shared-secret-not-a-registry-outage/run_20260921_013947` (n_runs: 1)  

_Read no cell without the `n` and split beside it._

| measurement | split | n | reward |
|---|---|--:|--:|
| JB baseline | test | 1 | 0.475 |
| our baseline (v4_t1_e1) | test | 3 | 0.650 |
| seed (val, v4_t2_e1) | val | 5 | 0.487 |
| cand_0001 (val, v4_t2_e1)  <- best (val) | val | 5 | 0.590 |
| final (test, v4_t2_e1) | test | 5 | 0.575 |

delta vs JB: 0.100 · delta vs our baseline: -0.075

**T2 cost/time:** $36.11, 2,819,580 tokens, 2.52h (eval $7.99/2,562,040tok · optimizer $28.12/257,540tok) — see [`../../../results/v4/cost_time/`](../../../results/v4/cost_time/)

Optimizer run material (not committed here -- `parsec-intake_v4` worktree, gitignored): `.capevolve/v4_t2_e1_platform-032-shared-secret-not-a-registry-outage/run_20260921_013947/report.md`, `.capevolve/v4_t2_e1_platform-032-shared-secret-not-a-registry-outage/run_20260921_013947/JOURNAL.md`

<!-- END:auto -->

## What this task is about

Provisioning is failing on a controller with authentication errors, starting from one job. The task requires checking whether other catalog items failed the same way in the same window -- pointing to a shared credential problem -- rather than concluding the registry itself is down, which the log's own wording (a refused token) actually rules out.

## What the optimizer tried

A single iteration (`cand_0001`, the only candidate in this 1-iteration run). Its most consequential move happened before any scoring: an earlier draft targeted `aap2_agent.md` + `orchestrator.md` on the assumption that `services: ["platform", "github"]` determined which prompt file is loaded, but the implementer checked the runtime routing code (`classify_fast()` in `agents.py`) and found this task's instruction phrase ("catalog item**s**") matches `_BABYLON_PATTERNS` before the orchestrator ever runs, while no `_AAP2_PATTERNS` alternative matches — so the whole draft was reverted (`aap2_agent.md` −180 lines, `orchestrator.md` −14) and re-targeted into `babylon_agent.md` (+165/−7) and `shared_context.md` (+29/−0), the two files this task's live 8-round `babylon` agent actually reads. The shipped edits: a new "Your Round Budget — Report As You Go" section (state each fact in the round you establish it; never end a turn with a plan or offer to continue) mirrored generically in `shared_context.md`; an expanded "Catalog Item Lookup Rules" plus a new "Deriving an AgnosticV Path Without the Index" section that derives the `<account>/<item>/<stage>.yaml` config path from data already visible in the job list when `lookup_catalog_item` degrades, rather than sweeping with `search_github_repo`; a rewritten "Job and Provision Failures" section requiring `find_jobs status=failed` with no date filter ("never guess a date window — today's date is not evidence") and stating the count of affected items in the same turn it's established; a new "Authentication and Credential Failures" section requiring both the credential name and the file path it's pulled from, plus a table distinguishing "the service never answered" from "the service answered and refused the credential"; and an affirmative-only guard explicitly built on a sibling task's lesson (`platform-031-helm-url-not-a-timeout`) that a rule naming a forbidden label, even to require evidence for it, teaches the label.

## Why the winning candidate won

JOURNAL.md's per-seed reward breakdown attributes the gain to four traceable mechanisms: accepting the round-1 job log's verbatim phrase "invalid username/password" as satisfying the `registry-answered` fact with no extra tool call; stating the count of affected catalog items in round 2, recovering the `affected-items` fact missed in 4/5 seed trials; deriving the GitHub config path from the unfiltered `find_jobs` result already on screen rather than depending on the degraded `lookup_catalog_item` tool, worth both a matched-tool-call point and the facts behind one `fetch_github_file` call; and a swept-clean check for forbidden substrings (0 of 8 files, versus 5 of 10 natural ways of phrasing the same denial that would have tripped one). This moved val from the seed's 0.4875 to 0.590 (Δ+0.102), the run's only candidate and its accepted champion. On the held-out test split, `report.md` records the baseline `seed` skills at 0.435 ± 0.021 versus the optimized skills at 0.575 ± 0.0 — a test-side improvement of +0.14. This task's val-seed score (0.4875) is not the same number as its test-seed score (0.435); the two splits disagree, and neither equals the auto block's separately-measured "our baseline" (v4_t1_e1) test score of 0.650, discussed below.

## Caveats

n=5 val trials is a small sample, this was single-task tuning, and — unusually for this batch of six — the run stopped after one accepted iteration rather than continuing toward a plateau, so several clusters JOURNAL.md calls "only *probably* cracked" (the config-path derivation depends on the agent choosing derivation over a sweep at run time) were never re-measured with a follow-up candidate. This is also the one task in this batch where the auto block's "delta vs our baseline" is *negative* (−0.075): the final optimized test score (0.575) sits below the separately-measured `v4_t1_e1` "our baseline" test score (0.650), even though it beats both the single JB baseline run (0.475) and this run's own internal seed baseline (0.435 test / 0.4875 val). `report.md`'s own "+0.14" test-improvement figure is computed against the latter (0.435), not the former — the two baselines come from different runs and are not directly comparable, and this report does not attempt to explain the gap between them. Separately, JOURNAL.md records that the implementer's first draft for this run targeted the wrong prompt file entirely (`aap2_agent.md`/`orchestrator.md`) before catching the routing mismatch pre-scoring — a reminder that the `services` field on a task describes which *tools* are available, not which prompt file is loaded.
