# Run schema v2

The single contract for `graph.jsonl` node extras and new `events.jsonl` kinds. DAG-engine,
evidence-ledger, cost and dashboard PRs cite this file for field names. Code: `core/cap_evolve/schema_v2.py`.

Rules: every key below is **optional and additive**; readers must tolerate absence (a v1 run
renders unchanged). Emitters land incrementally in the DAG-engine/ledger PRs, so a v2 run only carries the fields its emitters wrote; `run_config` gains `schema_version: 2` when the first emitter is wired (it is NOT stamped by this PR, so absence means nothing). Nodes are written with the
existing `graph.append_node(..., **extra)` (no signature change; last record per `id` wins).
Emitters never raise: a malformed payload is dropped and a `schema_warning {of, bad_keys}`
event is logged instead.

## 1. graph.jsonl node extras

Existing keys (`id`, `parents[]`, `status`, `val_mean`, `screen`, `gate`, `subset`, `note`, ...) are unchanged.

| Key | Type | Meaning |
|---|---|---|
| `merge_base` | tag \| null | LCA used for a merge node |
| `parent_roles` | `{tag: "primary"\|"donor"}` | role of each parent |
| `branch_id` | str | concurrent-branch id |
| `base_for_eval` | tag | gating reference; may differ from `parents[0]` |
| `round_id` | str/int | proposing round |
| `stage` | `proposed\|built\|checked\|probed\|evaluating\|alive\|pruned\|merged` | fine-grained lifecycle; legacy mapping: proposed/built/checked/probed/evaluating -> `proposed`, alive -> `gated`/`accepted`, pruned -> `rejected`, merged -> `superseded` |
| `status` | existing vocabulary | a not-yet-evaluated node is `proposed` with `eval_state: unevaluated`; legacy `queued` reads as `proposed` |
| `eval_state` | `unevaluated\|screened\|partial\|full` | monotone measurement state |
| `coverage` | `{split, task_ids[], n_tasks, n_val_tasks, trials_min, trials_max, tier, stage, full: bool, reuse_from: [tag]}` | what the scores were measured on |
| `capability_hash` | str | content hash of the capability; equals the evidence-ledger row key `cap_hash` (#718). Optimizer bookkeeping (`INSIGHTS.md`, `META_INSIGHTS.md`, `FRAMEWORK_IMPROVEMENTS.md`, `DIAGNOSIS.json`, `JOURNAL.md`, `LEDGER.md`, ...; `types.NON_CAPABILITY_FILES`) is excluded from the hash. Ledgers written before this exclusion carry hashes that include those files: rebuild with `eval_index.backfill(run_dir)` (the digest does it automatically when the ledger is empty) |
| `capability_files` | `[paths]` | files in the capability snapshot |
| `edit` | `{change_type, cluster_ids, target_tasks, hypothesis, files_changed}` | what the edit tried |
| `objectives` | `{name: {value, stderr, n_tasks, basis}}` | per-objective estimates |
| `vs_parent` | `{reward:{d,se,z,n}, cost_matched:{d,rel,se,z,n_matched,coverage,matched_task_ids}, ecps:{d,rel,se,z}, latency:{d,rel}}` | comparison to `base_for_eval` (shape owned by the objectives issue) |
| `gate_verdict` | `{stage: "feasibility"\|"ordering", outcome: accept\|reject\|indecisive\|tradeoff, reason}` | |
| `cost_ledger` | `{optimizer_usd, optimizer_tokens, optimizer_seconds, eval_agent_usd, eval_usersim_usd, control_usd, eval_seconds}` | who spent what |

Also reserved by the lineage design (same record, optional): `tip: bool`, `hypothesis_id`,
`pregate: {ok, tests[], replay:{task, ok}}`, `post: {mean, se, p_beat_parent, p_beat_seed}`,
`interaction: {score, parts}`. Per-node coverage is only `coverage`; per-node cost is only `cost_ledger`.
The event `eval_coverage` has `trials` (trials per task of that eval); the node's `coverage` aggregates
them as `trials_min`/`trials_max`.

## 2. events.jsonl kinds

| kind | fields |
|---|---|
| `candidate_proposed` | `id, parents, branch_id, round_id` |
| `eval_coverage` | `tag, split, task_ids, trials, reused_from` (event; folds into node `coverage`) |
| `eval_state` | `id, from, to` (monotone: unevaluated < screened < partial < full) |
| `decision` | `id, decision: propose\|screen\|promote\|kill\|merge\|grow\|accept\|reject\|stop\|tradeoff, evidence{}, rationale, optimizer_usd` |
| `optimizer_spend` | `role, model, usd, tokens, seconds, node\|null` |
| `evaluate` (existing) | gains `usersim_usd, cost_ledger, task_ids, n_trials` |
| `run_config` (existing) | gains `schema_version: 2`, `objective_defs` |
| `schema_warning` | `of, bad_keys` |

Required keys (checked by `schema_v2.emit`): `candidate_proposed` id,parents; `eval_coverage`
tag,split,task_ids,trials; `eval_state` id,to; `decision` id,decision; `optimizer_spend` role,usd.

## 3. Backward compatibility (reader side)

`schema_v2.normalize_node(node, val_ids=, evals=, parents=)` / `CandidateGraph.node_v2(id)` fill, only when absent
(explicit `eval_state`/`coverage` always win):

- `coverage` + `eval_state` from real evaluated task ids: `schema_v2.legacy_coverage(events, val_ids)` folds v1
  `eval_start`/`evaluate` val events (`subset_ids`, `n_trials`; `<tag>__screenN` folds into `<tag>`). All val tasks -> `full`;
  only screen evals -> `screened`; otherwise `partial`.
- Without events: `val_mean` alone is not proof of a full eval. A node with `screen` and no `gate` row was screen-killed
  -> `screened` (cand_9 in run_20261008_150326: 8 of 30 tasks x 1 trial, `val_mean` was cand_7's number). `val_mean` plus a
  `gate` row (or no screen) -> `full`; screen/subset only -> `screened`; else `unevaluated`.
- `status: queued` -> `proposed`.
- `base_for_eval` = first parent; `parent_roles` = first primary, rest donor. Self-parents are dropped (`node_v2` uses
  `CandidateGraph.parents_of`, which gets #719's filter once it lands; TODO: use history to recover the original parent).

Ordering: `eval_state` is monotone by convention (`advance_eval_state` never moves backwards), but there is no lock or reducer
here; writers racing on one tag serialise via `graph.append_node_locked` (#714).
