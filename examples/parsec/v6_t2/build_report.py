#!/usr/bin/env python3
"""Build the v6_t2 report over the whole 67-task feedback split: a JSON ledger plus an HTML heatmap.

Every feedback task gets one row, in one of four classes:
  optimized         a v6_t2 project ran on it: Seed (v6_g2_e1's 10 Seed trials) -> T2 champion
  at-ceiling        the Seed already scores 1.0 on all 10 trials; nothing to optimize
  above-threshold   Seed in [0.95, 1.0): left out of v6_t2 by the 0.95 cutoff
  unfixable-routing parsec's fast-path router (classify_fast) sends the request to a specialist
                    that lacks a tool the task's verifier requires; no edit to the skill files can
                    reach that decision, so the task was not optimized

The routing class is recomputed here from parsec's own code and the task files, not hard-coded:
classify_fast's patterns are executed against each task's instruction.md, and the chosen
specialist's tool list (from tool_definitions.py) is checked against the task's expected calls.

Usage (from the worktree root):
    python3 examples/parsec/v6_t2/build_report.py --suite-id e1 --g2-run <v6_g2_e1 run dir> --out results/v6_t2_e1
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from pathlib import Path

T2_DIR = Path(__file__).resolve().parent
REPO_ROOT = T2_DIR.parents[2]
sys.path.insert(0, str(T2_DIR))
import scaffold_projects as S  # noqa: E402

DOMAINS = ["aap2", "babylon", "cost", "security", "ocpv", "icinga"]


def load_router(agents_py: Path):
    """classify_fast as parsec defines it: exec its pattern block and the function itself."""
    src = agents_py.read_text(encoding="utf-8")
    start = src.index("_AAP2_PATTERNS = re.compile(")
    end = src.index("\n\n\n", src.index("def classify_fast("))
    ns = {"re": re}
    exec(src[start:end], ns)  # noqa: S102 — parsec's own regex block, read from the pinned tree
    return ns["classify_fast"]


def load_agent_tools(tool_defs_py: Path) -> dict[str, set[str]]:
    """{agent: tool names} from the get_<agent>_tools() bodies' _tools_by_name(...) arguments."""
    tree = ast.parse(tool_defs_py.read_text(encoding="utf-8"))
    out = {}
    for fn in tree.body:
        if isinstance(fn, ast.FunctionDef) and fn.name.startswith("get_") and fn.name.endswith("_tools"):
            agent = fn.name[len("get_"):-len("_tools")]
            if agent not in DOMAINS:
                continue
            for node in ast.walk(fn):
                if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_tools_by_name":
                    out[agent] = {a.value for a in node.args if isinstance(a, ast.Constant)}
    return out


def seed_trials(g2_run: Path, task: str) -> list[float]:
    vals = []
    for f in sorted((g2_run / "rollouts" / "feedback").glob(f"{task}__seed__t*.json")):
        rec = json.loads(f.read_text(encoding="utf-8"))
        if not (rec.get("rollout") or {}).get("error"):
            vals.append(float(rec["score"]["reward"]))
    return vals


def t2_result(suite: str, task: str) -> dict | None:
    run = REPO_ROOT / ".capevolve" / f"v6_t2_{suite}_{task}" / f"run_{task}"
    if not (run / "events.jsonl").is_file():
        return None
    steps, opt, ev, ended, failed = [], 0.0, 0.0, False, set()
    for line in (run / "events.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("kind") == "optimizer_error":
            failed.add(e.get("candidate"))      # the optimizer made no edit; the "candidate" is its parent
        elif e.get("kind") == "step":
            steps.append({"candidate": e.get("candidate"), "val": e.get("val"), "accept": bool(e.get("accept")),
                          "optimizer_failed": e.get("candidate") in failed})
            opt += e.get("opt_cost_usd") or 0.0
            ev += e.get("cost_usd") or 0.0
        elif e.get("kind") == "finalize_skipped":
            ended = True
    spent = json.loads((run / "state.json").read_text(encoding="utf-8"))["spent"]
    return {"best": spent["best_val"], "best_id": json.loads((run / "state.json").read_text())["best_id"],
            "iterations": spent["iterations"], "steps": steps, "ended": ended,
            "optimizer_usd": round(opt, 2), "eval_usd": round(ev, 2)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suite-id", required=True)
    ap.add_argument("--g2-run", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--tree", type=Path, default=Path(os.environ.get(
        "PARSEC_V6N", "/dccstor/knewedge2/boazc/workarea/python/rhdp-parsec/v6_2026-10-16")))
    args = ap.parse_args()

    live = args.tree / "_run" / "parsec-live" / "src" / "agent"
    classify = load_router(live / "agents.py")
    tools = load_agent_tools(live / "tool_definitions.py")
    # v6_g2_e1 is pooled: its feedback stratum F is the "train" split of the paper (67 tasks).
    feedback = json.loads((args.g2_run / "splits.json").read_text(encoding="utf-8"))["feedback"]
    if len(feedback) != 67:
        raise SystemExit(f"expected the 67-task feedback split, found {len(feedback)}")
    optimized = set(S.TASK_IDS)

    rows = []
    for task in sorted(feedback):
        tdir = args.tree / "bench-v6-harbor-tasks" / f"bench-v6-{task}"
        route = classify((tdir / "instruction.md").read_text(encoding="utf-8"))
        need = {c["name"] for c in json.loads((tdir / "tests" / "expected.json").read_text())["tool_calls"]["expected"]}
        missing = sorted(need - tools.get(route, set())) if route else []
        trials = seed_trials(args.g2_run, task)
        seed = sum(trials) / len(trials) if trials else None
        t2 = t2_result(args.suite_id, task) if task in optimized else None
        if t2 is not None:
            cls = "optimized"
        elif missing:
            cls = "unfixable-routing"
        elif trials and min(trials) >= 0.999:
            cls = "at-ceiling"
        else:
            cls = "above-threshold"
        rows.append({"task": task, "category": task.split("-")[0], "class": cls, "seed": seed,
                     "seed_trials": len(trials), "route": route, "route_missing_tools": missing,
                     "t2": t2, "final": (t2["best"] if t2 else seed)})

    n = len(rows)
    mean = lambda xs: sum(xs) / len(xs) if xs else None  # noqa: E731
    summary = {
        "n_tasks": n,
        "by_class": {c: sum(r["class"] == c for r in rows) for c in
                     ("optimized", "at-ceiling", "above-threshold", "unfixable-routing")},
        "seed_mean": mean([r["seed"] for r in rows]),
        "final_mean": mean([r["final"] for r in rows]),
        "optimized_solved": sum(1 for r in rows if r["t2"] and r["t2"]["best"] >= 0.999),
        "optimizer_usd": round(sum(r["t2"]["optimizer_usd"] for r in rows if r["t2"]), 2),
        "eval_usd": round(sum(r["t2"]["eval_usd"] for r in rows if r["t2"]), 2),
        "note": ("final = the task's own T2 champion where one exists, else the Seed. These are fit "
                 "numbers on the task each bundle was optimized for: 34 separate bundles, not one. "
                 "Seed = v6_g2_e1's 10 Seed trials; T2 champion = its own 5-trial evaluation."),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "results.json").write_text(json.dumps({"suite": f"v6_t2_{args.suite_id}", "summary": summary,
                                                       "tasks": rows}, indent=1), encoding="utf-8")
    (args.out / "heatmap.html").write_text(render(rows, summary, args.suite_id), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0


def render(rows: list[dict], summary: dict, suite: str) -> str:
    data = json.dumps(rows)
    s = summary
    return f"""<title>v6_t2 feedback heatmap</title>
<style>
:root {{ --bg:#fbfbfa; --fg:#1d2125; --muted:#5f6670; --line:#d9dcdf; --head:#f1f2f0;
         --unfix:#8b6fc8; --ceil:#7b8590; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ color-scheme:dark;
  --bg:#16191c; --fg:#e6e8ea; --muted:#9aa2ab; --line:#2f353b; --head:#1f2328; --unfix:#a98ce0; --ceil:#8d97a2; }} }}
:root[data-theme="dark"] {{ color-scheme:dark; --bg:#16191c; --fg:#e6e8ea; --muted:#9aa2ab; --line:#2f353b;
  --head:#1f2328; --unfix:#a98ce0; --ceil:#8d97a2; }}
body {{ background:var(--bg); color:var(--fg); font:13px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
        margin:0; padding-block:24px; padding-inline:16px; }}
main {{ max-width:1100px; margin:0 auto; }}
h1 {{ font-size:19px; margin:0 0 4px; text-wrap:balance; }}
p.lede {{ color:var(--muted); max-width:68ch; margin:0 0 16px; }}
.kpis {{ display:flex; flex-wrap:wrap; gap:8px 28px; margin:0 0 16px; }}
.kpis div {{ font-variant-numeric:tabular-nums; }} .kpis b {{ font-size:17px; display:block; }}
.kpis span {{ color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.04em; }}
.legend {{ display:flex; flex-wrap:wrap; gap:6px 18px; color:var(--muted); font-size:12px; margin-bottom:12px; }}
.sw {{ display:inline-block; width:28px; height:11px; border-radius:2px; vertical-align:-1px; margin-right:5px; }}
.wrap {{ overflow-x:auto; border:1px solid var(--line); border-radius:6px; }}
table {{ border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; }}
th, td {{ padding:4px 8px; border-bottom:1px solid var(--line); text-align:right; white-space:nowrap; }}
th {{ background:var(--head); position:sticky; top:0; font-weight:600; cursor:pointer; }}
td.task, th.task {{ text-align:left; }} td.cls {{ text-align:left; color:var(--muted); }}
td.cell {{ color:#111; min-width:64px; }} td.na {{ color:var(--muted); }}
tr.unfixable-routing td.task {{ color:var(--unfix); }}
.note {{ color:var(--muted); font-size:12px; max-width:80ch; margin-top:14px; }}
</style>
<main>
<h1>v6_t2 on the 67-task feedback split</h1>
<p class="lede">Task-by-task optimization, one bundle per task. Each row is a feedback task: its Seed reward
(v6_g2_e1's 10 Seed trials) and, where v6_t2 ran on it, the reward of that task's own champion bundle.
These are fit numbers on the task each bundle was optimized for, not a merged or held-out result.</p>
<div class="kpis">
 <div><b>{s['by_class']['optimized']}</b><span>optimized</span></div>
 <div><b>{s['optimized_solved']}</b><span>reached 1.0</span></div>
 <div><b>{s['by_class']['unfixable-routing']}</b><span>unfixable (routing)</span></div>
 <div><b>{s['by_class']['at-ceiling'] + s['by_class']['above-threshold']}</b><span>not run (≥ 0.95)</span></div>
 <div><b>{s['seed_mean']:.3f} → {s['final_mean']:.3f}</b><span>feedback mean, Seed → per-task best</span></div>
 <div><b>${s['optimizer_usd'] + s['eval_usd']:.0f}</b><span>optimizer + eval</span></div>
</div>
<div class="legend">
 <span><span class="sw" style="background:rgb(220,38,38)"></span>0.0</span>
 <span><span class="sw" style="background:rgb(254,243,199)"></span>0.5</span>
 <span><span class="sw" style="background:rgb(5,150,105)"></span>1.0</span>
 <span><span class="sw" style="background:var(--unfix)"></span>unfixable with skills: routed to a specialist missing a required tool</span>
</div>
<div class="wrap"><table id="t"><thead><tr>
 <th class="task" data-k="task">task</th><th data-k="category">domain</th><th class="task" data-k="class">class</th>
 <th data-k="seed">Seed</th><th data-k="final">T2 best</th><th data-k="delta">Δ</th>
 <th data-k="iters">iters</th><th class="task" data-k="steps">steps</th><th class="task" data-k="why">why not optimized</th>
</tr></thead><tbody></tbody></table></div>
<p class="note">Classes: <b>optimized</b> — a v6_t2 project ran; <b>at-ceiling</b> — Seed 1.0 on all 10 trials;
<b>above-threshold</b> — Seed in [0.95, 1.0), left out by the 0.95 cutoff; <b>unfixable-routing</b> — parsec's
regex fast path (<code>classify_fast</code>) sends the request to a specialist that lacks a tool the verifier requires,
so no skill edit can reach it. Steps: A = accepted candidate, r = rejected, x = the optimizer failed to run
(no edit was made; the unchanged bundle was re-measured). Suite v6_t2_{suite}.</p>
</main>
<script>
const ROWS = {data};
const color = v => {{ if (v == null) return ""; v = Math.max(0, Math.min(1, v));
  const lerp = (a,b,t) => Math.round(a+(b-a)*t);
  const [r,g,b] = v < .5 ? [lerp(220,254,v*2), lerp(38,243,v*2), lerp(38,199,v*2)]
                         : [lerp(254,5,(v-.5)*2), lerp(243,150,(v-.5)*2), lerp(199,105,(v-.5)*2)];
  return `rgb(${{r}},${{g}},${{b}})`; }};
const f = v => v == null ? "—" : v.toFixed(3);
const view = ROWS.map(r => ({{...r, iters: r.t2 ? r.t2.iterations : null,
  steps: r.t2 ? r.t2.steps.map(s => s.optimizer_failed ? "x" : s.accept ? "A" : "r").join("") : "",
  delta: r.t2 ? r.final - r.seed : null,
  why: r.class === "unfixable-routing" ? `routed to ${{r.route}}, lacks ${{r.route_missing_tools.join(", ")}}`
     : r.class === "at-ceiling" ? "Seed already 1.0" : r.class === "above-threshold" ? "Seed ≥ 0.95" : "" }}));
let key = "seed", dir = 1;
function draw() {{
  const rows = [...view].sort((a,b) => {{ const x=a[key], y=b[key];
    return (x == null) - (y == null) || (x < y ? -dir : x > y ? dir : 0); }});
  document.querySelector("#t tbody").innerHTML = rows.map(r => `<tr class="${{r.class}}">
    <td class="task">${{r.task}}</td><td>${{r.category}}</td><td class="cls">${{r.class}}</td>
    <td class="cell" style="background:${{color(r.seed)}}">${{f(r.seed)}}</td>
    <td class="cell ${{r.t2 ? "" : "na"}}" style="background:${{r.t2 ? color(r.final) : "transparent"}}">${{r.t2 ? f(r.final) : "—"}}</td>
    <td>${{r.delta == null ? "" : (r.delta >= 0 ? "+" : "") + r.delta.toFixed(3)}}</td>
    <td>${{r.iters ?? ""}}</td><td class="task">${{r.steps}}</td><td class="task cls">${{r.why}}</td></tr>`).join("");
}}
document.querySelectorAll("th").forEach(th => th.onclick = () => {{
  const k = th.dataset.k; dir = key === k ? -dir : 1; key = k; draw(); }});
draw();
</script>
"""


if __name__ == "__main__":
    raise SystemExit(main())
