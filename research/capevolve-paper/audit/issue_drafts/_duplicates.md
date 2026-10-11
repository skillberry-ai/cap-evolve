# Duplicates — not drafted (checked against `gh issue list --state all`, 266 issues)

| Audit finding | Existing issue | State | Note |
|---|---|---|---|
| Optimizer can edit/replace the scorer; no sandbox (D08 general part) | #276 | open | confirmed by `r6_isolation.py`; D08 draft adds only the agent-optimize false-claim and seal-scope bug |
| Honesty invariants enforced at CLI not core | #365 | open | meta; D01/D04/D07 are instances |
| `evaluate_candidate(split="test")` callable outside finalize | #361 | open | D07 adds the campaign-level reuse angle |
| tool_surface edit policy enforced by label only | #372 | open | not re-verified here |
| Action policy fails open (`policy.json` path) | #352 | open | affects 'editable artifacts' claims |
| Benchmark sources unpinned | #513 | open | affects reproducibility claims |
| agent-optimize single linear lineage / no branch graph | #586 | open | superseded in part by the DAG engine (graph.jsonl, `--parent`) |
| agent-optimize: per-instance Pareto tracking | #638 | open | merge/frontier |
| SkillOpt mini-batch focus empty / edit budget advisory / applied_changes | #371, #382, #395 | open | D13 |
| GEPA trajectories tag stops resolving from iteration 2 | #376 | open | D12 |
| One-task gain delta == SE | #351 | CLOSED but reproduces | D14 |
| Infra-errored trials scored as 0 / tiny val guard | #306, #113 | closed | partially fixed; D04 covers the remaining joint-coverage and candidate-exception gaps |
