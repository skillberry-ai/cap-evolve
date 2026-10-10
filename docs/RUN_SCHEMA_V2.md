# Run schema v2

The single contract for `graph.jsonl` node extras and new `events.jsonl` kinds. DAG-engine,
evidence-ledger, cost and dashboard PRs cite this file for field names. Code: `core/cap_evolve/schema_v2.py`.

Rules: every key below is **optional and additive**; readers must tolerate absence (a v1 run
renders unchanged). `run_config` events carry `schema_version: 2`. Nodes are written with the
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
| `status` | existing + `queued` | `queued` = proposed, not yet evaluated |
| `eval_state` | `unevaluated\|screened\|partial\|full` | monotone measurement state |
| `eval_coverage` | `{split, task_ids[], n_tasks, n_val_tasks, trials_min, trials_max, tier, stage, full: bool, reuse_from: [tag]}` | what the scores were measured on |
| `capability_hash` | str | content hash of the capability |
| `capability_files` | `[paths]` | files in the capability snapshot |
| `edit` | `{change_type, cluster_ids, target_tasks, hypothesis, files_changed}` | what the edit tried |
| `objectives` | `{name: {value, stderr, n_tasks, basis}}` | per-objective estimates |
| `vs_parent` | `{reward:{d,se,z,n}, cost_matched:{d,rel,se,z,n_matched,coverage,matched_task_ids}, ecps:{d,rel,se,z}, latency:{d,rel}}` | comparison to `base_for_eval` (shape owned by the objectives issue) |
| `gate_verdict` | `{stage: "feasibility"\|"ordering", outcome: accept\|reject\|indecisive\|tradeoff, reason}` | |
| `cost_ledger` | `{optimizer_usd, optimizer_tokens, optimizer_seconds, eval_agent_usd, eval_usersim_usd, control_usd, eval_seconds}` | who spent what |

Also reserved by the lineage design (same record, optional): `tip: bool`, `hypothesis_id`,
`pregate: {ok, tests[], replay:{task, ok}}`, `coverage: {n_tasks, n_trials, task_ids[]}`,
`post: {mean, se, p_beat_parent, p_beat_seed}`, `cost: {eval_usd, optimizer_usd}`,
`interaction: {score, parts}`.

## 2. events.jsonl kinds

| kind | fields |
|---|---|
| `candidate_proposed` | `id, parents, branch_id, round_id` |
| `eval_coverage` | `tag, split, task_ids, trials, reused_from` |
| `eval_state` | `id, from, to` (monotone: unevaluated < screened < partial < full) |
| `decision` | `id, decision: propose\|screen\|promote\|kill\|merge\|grow\|accept\|reject\|stop\|tradeoff, evidence{}, rationale, optimizer_usd` |
| `optimizer_spend` | `role, model, usd, tokens, seconds, node\|null` |
| `evaluate` (existing) | gains `usersim_usd, cost_ledger, task_ids, n_trials` |
| `run_config` (existing) | gains `schema_version: 2`, `objective_defs` |
| `schema_warning` | `of, bad_keys` |

Required keys (checked by `schema_v2.emit`): `candidate_proposed` id,parents; `eval_coverage`
tag,split,task_ids,trials; `eval_state` id,to; `decision` id,decision; `optimizer_spend` role,usd.

## 3. Backward compatibility (reader side)

`schema_v2.normalize_node(node)` / `CandidateGraph.node_v2(id)` fill, only when absent:

- `eval_state`: `status: queued` -> `unevaluated`; `val_mean` present -> `full`; screen/subset only -> `screened`; else `unevaluated`.
- `base_for_eval` = `parents[0]`; `parent_roles` = `parents[0]` primary, rest donor.
- `eval_coverage` for a screened-only node = `{split: val, task_ids: <screen subset>, n_tasks, full: false}`.

Concurrency: `eval_state` is monotone; a reducer takes the latest record per id, so out-of-order
writes from concurrent branches are safe (`schema_v2.advance_eval_state` never moves backwards).
