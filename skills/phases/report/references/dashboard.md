# Reference — the dashboard & terminal report

Builder: `cap_evolve.dashboard` (engine-owned, stdlib-only), imported by the report
skill via `scripts/dashboard.py`. The flow is **reduce → render**:

```
reduce_run(run_dir)  → {"graph": {...}, "summary": {...}}   (redacted)
render_html(reduced, run_dir)  → self-contained dashboard.html
render_ansi(reduced)           → colored terminal report
```

## Contents
- [Reduced run schema](#reduced-run-schema) — graph + summary the panels read from.
- [What each panel reads](#what-each-panel-reads) — the eight HTML panels.
- [Terminal report](#terminal-report) — the `--terminal` / `--ansi` mode.
- [Secret redaction](#secret-redaction) — what is scrubbed and how.
- [Graceful degradation](#graceful-degradation) — which panels hide when data is missing.

## Reduced run schema

`reduce_run` folds the run dir's append-only `events.jsonl` (the source of truth)
plus `baseline.json`, `final.json`, the persisted per-task `rollouts/`, and the git
iteration store into one structure. It never trusts `state.json` for anything it can
recompute from events.

**graph**
```jsonc
{"root": "seed", "best_id": "cand_0007",
 "nodes": [
   {"id": "cand_0001", "parent": "seed", "children": ["cand_0002"],
    "status": "accepted|rejected|seed|failed",
    "val": 0.62, "stderr": 0.04, "best_so_far": 0.62,
    "per_task": {"t1": 1.0, "t2": 0.0}, "feedback": {"t2": "…"},
    "cost_usd": 0.012, "tokens": 1840, "seconds": 4.1,
    "optimizer_seconds": 2.3, "runner_seconds": 1.8,
    "iteration": 1, "reason": "Δ=+0.12 (paired, p<0.05)",
    "parent_val": 0.50, "epoch": 0, "merge_of": ["cand_0003","cand_0005"]}
 ]}
```
`epoch` appears only for skillopt; `merge_of` only for gepa merges (multi-parent).
`status` is `failed` when a step produced neither a val score nor rollouts (e.g. the
optimizer raised); `seed` is the baseline node.

**summary**
```jsonc
{"run_id", "baseline_val", "best_val", "best_id",
 "delta_abs", "delta_pct",                    // %Δ is null off a zero baseline → use delta_abs
 "test_reward", "test_stderr", "test_pass_k", "test_sealed",
 "counts": {"accepted","rejected","failed","seed","total"},
 "frontier",                                  // gated leaves with no accepted child
 "tasks": ["t1","t2", …],
 "wall_clock_seconds", "optimizer_seconds", "runner_seconds",
 "cost": {"optimizer_usd","runner_usd","total_usd"},
 "tokens",
 "gate_warnings": [{"reason","context","mode"}],
 "diagnoses": [{"kind","candidate","text"}],   // gate reasons + diagnose/optimizer_error
 "git_log": [{"hash","subject"}]}              // one row per iteration commit
```

## What each panel reads

1. **KPI strip** — `summary` (best/baseline/Δ, counts by status, frontier, sealed
   test, wall-clock, optimizer-vs-runner cost split, tokens).
2. **Score over iterations** — `graph.nodes[*].{iteration,val,best_so_far,status,
   parent_val}`. Running-best is an SVG step polyline; champion star + value label;
   record-holder rings on each new best; per-iteration scatter colored by status;
   hover → id / status / val / Δ-from-parent.
3. **tasks×iterations heatmap** — `graph.nodes[*].per_task` + `summary.tasks`. Rows
   = tasks sorted worst-first by mean reward, cols = iterations; green=pass,
   red=fail, amber=partial, grey=not-run. Hover a cell → that task's feedback.
4. **Diff vs parent** — `build_diffs(run_dir, graph)` diffs each candidate dir
   against its parent dir (unified, split/unified toggle, add/del/hunk coloring).
5. **Lineage** — `graph` parent→child DAG; merges drawn as multi-parent edges; the
   best-lineage spine (best_id → root) highlighted gold.
6. **Cost · tokens · latency** — per-iteration stacked bars (optimizer-seconds blue,
   runner-seconds green) + a cumulative-cost dashed line; plus a separate
   cumulative-cost-vs-best-score plot (shown only when total cost > 0).
7. **Annotations & diagnoses** — `summary.gate_warnings` + `summary.diagnoses`
   rendered as an inline stream.
8. **Candidates** — full leaderboard table (id, status badge, val, Δ-parent, iter,
   reason) + the git iteration-store log.

## Terminal report

`python scripts/run.py --run-dir DIR --terminal` (alias `--ansi`) prints, instead of
the JSON summary:
- a one-line **KPI strip** (baseline / best / Δ / sealed test / counts / frontier /
  cost / tokens / wall),
- a **cumulative-best** block chart (█ running best, ○ accept, · reject, x fail),
- a **top-N** candidate table (`--top-n`, default 8), and
- up to three **gate warnings**.

It is sized to the terminal width and is **CLAUDECODE-margin-aware**: when
`CLAUDECODE=1` it subtracts ~6 columns so lines don't wrap inside the tool-output
frame. `--no-color` (or `NO_COLOR=1`) disables ANSI codes for piping/CI.

## Secret redaction

`reduce_run` returns its result through `redact()` before it reaches the HTML or the
terminal, so a shared `dashboard.html` never leaks a credential pulled in from
config/env. The redactor walks dicts/lists/strings and:
- replaces any **value under a secret-looking key** wholesale (`*api_key*`,
  `*secret*`, `*token*` — but not the `tokens` metric — `password`, `credential`,
  `watsonx`, `authorization`, `bearer`, `private_key`, `access_key`, `session`,
  `cookie`); and
- masks **value-shaped secrets inside free text**: `sk-…`, `Bearer …`, JWTs, long
  hex/base64 blobs, and inline `KEY=value` / `KEY: value` leaks (e.g. an optimizer
  error echoing `RITS_API_KEY=…`), keeping the key name and masking only the value.

Covers `RITS_API_KEY`, `BOBSHELL_API_KEY`, `WATSONX_*`, `OPENAI_API_KEY`,
`ANTHROPIC_API_KEY`, etc.

## Graceful degradation

Optional panels hide rather than crash when their data is absent:
- no per-task rollouts → heatmap is empty/hidden, scores fall back to `baseline.json`
  per_task or the step event's `val`;
- candidate dirs not snapshotted (e.g. a synthetic log) → `diffs` is `{}`, the diff
  panel hides;
- not finalized → test KPI shows "—", the test-sealed flag reads "not finalized";
- no git store → the iteration-store log is omitted;
- zero cost → the cost-vs-score plot is omitted.
