# Clusters and hypotheses

Source: `$R/clusters.json` (diagnose with `--cluster v2`). Each cluster: `cluster_id`, `tasks`, `headroom`
(reward lost), `kind`, tool-error signature. Trials are pooled.

Pick by `headroom`, not by one vivid trace. `act.py propose` accepts a hypothesis only if it covers >= 2
tasks OR headroom >= 0.06 (`--small-edit-justification` overrides, recorded).

Hypothesis file (`--hypothesis-file`, JSON):
`{"id":"h3","cluster_ids":["c2","c5"],"claim":"...","predicted_tasks":["t4","t9"],
  "predicted_mechanism":"...","edit_scope":["policy","tools"]}`
`predicted_tasks` must lie inside the chosen clusters. Same clusters + scope as a pruned hypothesis is
flagged `repeat_of`: change the FORM (tool-edit-lessons.md), not the wording.

Status in the digest: open, attempted, fixed, stuck. After two `stuck` attempts read a raw TRAIN trace
(never test) before a third.

Per-task pass rate k/n: <= 0.3 real defect (aim here); 0.4-0.7 unstable (remove ambiguity); >= 0.8 noise, leave alone.
A deterministic tool bug (same error signature across tasks) needs no multi-task argument; fix it in code.
