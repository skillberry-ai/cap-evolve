"""Observability reducer + renderers for a CapEvolve run. 

This module is the deterministic, stdlib-only builder the ``report`` skill calls.
It does three things:

1. ``reduce_run(run_dir)`` — fold the run dir's append-only ``events.jsonl`` (plus
   ``baseline.json``, ``final.json``, the persisted per-task ``rollouts/``, and the
   git iteration store) into a single ``{graph, summary}`` structure. The event log
   is the source of truth (``rundir`` keeps state.json only as a derived cache), so
   the reducer never trusts state.json for anything it can recompute from events.

2. ``render_html(reduced, run_dir)`` — emit a **self-contained** ``dashboard.html``:
   inline CSS + vanilla JS + inline SVG, no external CDNs, so the file opens offline
   from ``file://`` and is a single shareable artifact.

3. ``render_ansi(reduced, ...)`` — a colored terminal report (KPI strip + cumulative
   best chart + top-N table), sized to the terminal and CLAUDECODE-margin-aware.

Everything that reaches the HTML or the terminal first passes through ``redact`` so a
shared dashboard never leaks a credential pulled in from config/env.

The candidate **graph** schema (``reduced["graph"]``)::

    {"nodes": [
        {"id", "parent", "children": [...], "status": seed|accepted|rejected|failed,
         "val", "stderr", "per_task": {task_id: reward}, "feedback": {task_id: str},
         "cost_usd", "tokens", "seconds", "optimizer_seconds", "runner_seconds",
         "iteration", "reason", "epoch"?, "merge_of"?, "best_so_far"}
     ],
     "root": "seed", "best_id": "..."}

The **summary** schema (``reduced["summary"]``)::

    {"run_id", "baseline_val", "best_val", "delta_pct", "test_reward", "test_sealed",
     "test_pass_k", "counts": {accepted, rejected, failed, seed, total},
     "frontier": int, "tasks": [task_id, ...],
     "wall_clock_seconds", "optimizer_seconds", "runner_seconds",
     "cost": {optimizer_usd, runner_usd, total_usd}, "tokens": int,
     "gate_warnings": [...], "diagnoses": [...], "git_log": [...]}

Optional panels degrade silently: when per-task data / diffs / finalize are missing
the renderer hides the panel rather than crashing.
"""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------

# Case-insensitive regexes over a KEY whose VALUE must be scrubbed before it can
# reach a shared artifact. Covers the providers CapEvolve talks to plus the generic
# shapes (``*_API_KEY``, ``*_TOKEN``, ``*_SECRET`` ...). Note ``token`` is matched as
# a word (``api_token``, ``access-token``) but NOT ``tokens`` — the cost metric — so
# the redactor doesn't eat a legitimate count.
_SECRET_KEY_RES = [
    re.compile(p, re.I) for p in (
        r"api[_\-]?key", r"secret", r"\btokens?\b" if False else r"token(?!s)",
        r"password", r"passwd", r"credential", r"watsonx", r"wx_api",
        r"authorization", r"bearer", r"private[_\-]?key", r"access[_\-]?key",
        r"\bsession\b", r"\bcookie\b",
    )
]

# Value-shaped secrets to mask even when the key looks innocent, and inline
# ``KEY=value`` leaks inside free-text (an optimizer error echoing the environment):
# long hex/base64 blobs, bearer headers, JWTs, the common vendor key prefixes, and
# any ``<SECRET_KEY>=<value>`` pair where the key name itself looks like a secret.
_SECRET_VALUE_RES = [
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{12,}\b", re.I),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]{6,}\b"),  # JWT
    re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b"),  # long base64
    re.compile(r"\b[0-9a-fA-F]{40,}\b"),          # long hex
]

# KEY=secret / KEY: secret inside prose — mask the value, keep the key name so the
# message still reads ("RITS_API_KEY=«redacted»"). Two groups: (prefix)(value).
_INLINE_KV_RE = re.compile(
    r"((?:[A-Za-z0-9_\-]*(?:api[_\-]?key|secret|token|password|credential|key)"
    r"[A-Za-z0-9_\-]*)\s*[:=]\s*)(\S+)", re.I)

_REDACTED = "«redacted»"


def _key_is_secret(key: str) -> bool:
    k = str(key)
    return any(rx.search(k) for rx in _SECRET_KEY_RES)


def _scrub_value(val: str) -> str:
    out = _INLINE_KV_RE.sub(lambda m: m.group(1) + _REDACTED, val)
    for rx in _SECRET_VALUE_RES:
        out = rx.sub(_REDACTED, out)
    return out


def redact(obj):
    """Recursively redact secrets from ``obj`` before it reaches an artifact.

    - Dict values under a secret-looking key are replaced wholesale.
    - String values are scanned for secret-shaped tokens and masked in place.
    - Lists/tuples/dicts are walked recursively. Scalars pass through.

    Pure, returns a new structure; the caller's object is untouched.
    """
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if _key_is_secret(k) and v not in (None, "", 0):
                out[k] = _REDACTED
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [redact(v) for v in obj]
    if isinstance(obj, str):
        return _scrub_value(obj)
    return obj


# ---------------------------------------------------------------------------
# Reducer
# ---------------------------------------------------------------------------

def _read_jsonl(path: Path) -> list[dict]:
    out = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def _read_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _per_task_from_rollouts(run_dir, tag: str, split: str = "val"):
    """(per_task_reward, feedback) for ``tag`` rebuilt from persisted rollouts.

    Uses the canonical core helper so scores match the loop exactly. Returns two
    dicts keyed by task id; empty if no rollouts were persisted for this tag.
    """
    try:
        from . import harness
        sr = harness.split_result_from_rollouts(run_dir, tag, split)
    except Exception:  # noqa: BLE001 — degrade: a missing/odd rollout shouldn't crash the report
        return {}, {}
    per = {pt["task_id"]: pt["reward"] for pt in sr.to_dict().get("per_task", [])}
    fb = {pt["task_id"]: pt.get("feedback", "") for pt in sr.to_dict().get("per_task", [])}
    return per, fb


def _git_log(root: Path) -> list[dict]:
    """One row per iteration commit from the run dir's git store (empty if none)."""
    if not (root / ".git").exists() or not shutil.which("git"):
        return []
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "log", "--format=%h%x09%s", "-n", "200"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    rows = []
    for line in r.stdout.splitlines():
        if "\t" in line:
            h, s = line.split("\t", 1)
            rows.append({"hash": h, "subject": s})
    rows.reverse()  # oldest first → reads top-to-bottom as the run progressed
    return rows


# Step-like events carry a candidate, an accept flag, and per-iteration cost/time.
# Different algorithms name the candidate field differently; normalise here.
def _step_candidate(ev: dict):
    return ev.get("candidate") or ev.get("candidate_id")


def reduce_run(run_dir) -> dict:
    """Fold the run dir into ``{"graph": ..., "summary": ...}`` (redacted)."""
    root = Path(run_dir.root)
    events = _read_jsonl(root / "events.jsonl")
    baseline = _read_json(root / "baseline.json")
    final = _read_json(root / "final.json")

    base_val_obj = baseline.get("val") or {}
    baseline_val = base_val_obj.get("reward")
    tasks = [pt["task_id"] for pt in base_val_obj.get("per_task", [])]

    # --- nodes: start with the seed -------------------------------------
    nodes: dict[str, dict] = {}
    seed_per, seed_fb = _per_task_from_rollouts(run_dir, "seed", "val")
    if not seed_per:  # no rollouts persisted (synthetic logs) → fall back to baseline.json
        seed_per = {pt["task_id"]: pt["reward"] for pt in base_val_obj.get("per_task", [])}
        seed_fb = {pt["task_id"]: pt.get("feedback", "") for pt in base_val_obj.get("per_task", [])}
    nodes["seed"] = {
        "id": "seed", "parent": None, "children": [], "status": "seed",
        "val": baseline_val, "stderr": base_val_obj.get("stderr"),
        "per_task": seed_per, "feedback": seed_fb,
        "cost_usd": (base_val_obj.get("cost_usd") or 0.0),
        "tokens": (base_val_obj.get("tokens") or 0),
        "seconds": (base_val_obj.get("seconds") or 0.0),
        "optimizer_seconds": 0.0, "runner_seconds": (base_val_obj.get("seconds") or 0.0),
        "iteration": 0, "reason": "baseline (seed)", "best_so_far": baseline_val,
    }

    gate_warnings: list[dict] = []
    diagnoses: list[dict] = []
    minibatch_evals: set[str] = set()  # tags only seen on a minibatch (gepa) — not full val

    # First pass: which tags were evaluated on val (vs only minibatch).
    for ev in events:
        if ev.get("kind") == "evaluate" and ev.get("split") == "val":
            minibatch_evals.discard(ev.get("tag"))
        if ev.get("kind") == "minibatch":
            minibatch_evals.add(ev.get("tag"))

    best = baseline_val if baseline_val is not None else 0.0
    it = 0
    for ev in events:
        kind = ev.get("kind")
        if kind == "gate_warning":
            gate_warnings.append({"reason": ev.get("reason"), "context": ev.get("context"),
                                  "mode": ev.get("mode")})
            continue
        if kind in ("diagnose", "optimizer_error"):
            diagnoses.append({
                "kind": kind,
                "candidate": _step_candidate(ev),
                "text": ev.get("error") or ev.get("summary") or ev.get("note") or "",
            })
            continue
        if kind not in ("step", "skillopt_step", "gepa_val_gate"):
            continue

        cid = _step_candidate(ev)
        if not cid:
            continue
        it += 1
        accepted = bool(ev.get("accept"))
        parent = ev.get("parent_id") or ev.get("parent")
        # gepa val-gate / step events don't always carry the parent edge; fall back
        # to "seed" if we have nothing better so the lineage tree stays connected.
        val = ev.get("val")
        parent_val = ev.get("parent_val")

        per, fb = _per_task_from_rollouts(run_dir, cid, "val")
        # A candidate that errored out / produced no rollouts and no val score is "failed".
        if val is None and not per:
            status = "failed"
        else:
            status = "accepted" if accepted else "rejected"

        if val is not None:
            best = max(best, val)

        merge_of = ev.get("merge_of")
        node = {
            "id": cid,
            "parent": parent if parent in (None,) or True else parent,
            "children": [],
            "status": status,
            "val": val,
            "stderr": None,
            "per_task": per,
            "feedback": fb,
            "cost_usd": ev.get("cost_usd") or 0.0,
            "tokens": ev.get("tokens") or 0,
            "seconds": (ev.get("runner_seconds") or 0.0) + (ev.get("optimizer_seconds") or 0.0),
            "optimizer_seconds": ev.get("optimizer_seconds") or 0.0,
            "runner_seconds": ev.get("runner_seconds") or 0.0,
            "iteration": it,
            "reason": ev.get("reason") or "",
            "parent_val": parent_val,
            "best_so_far": best,
        }
        if "epoch" in ev:
            node["epoch"] = ev.get("epoch")
        if merge_of:
            node["merge_of"] = merge_of
        # Last write wins if the same cid appears twice (e.g. gepa local-gate then
        # val-gate); keep the richer (val-bearing) record.
        if cid in nodes and nodes[cid].get("val") is not None and val is None:
            pass
        else:
            node["parent"] = parent
            nodes[cid] = node

    # --- wire parent → children edges -----------------------------------
    for nid, n in nodes.items():
        p = n.get("parent")
        if p and p in nodes and p != nid:
            nodes[p]["children"].append(nid)
        # multi-parent (merge): also link the merge sources
        for mp in (n.get("merge_of") or []):
            if mp in nodes and nid not in nodes[mp]["children"]:
                nodes[mp]["children"].append(nid)

    # --- best id (prefer event log over state.json) ---------------------
    best_id = "seed"
    best_val = baseline_val if baseline_val is not None else None
    for nid, n in nodes.items():
        if n["status"] == "accepted" and n.get("val") is not None:
            if best_val is None or n["val"] >= best_val:
                best_val, best_id = n["val"], nid
    if final.get("best_id"):
        best_id = final["best_id"]

    # --- frontier: gated (accepted) leaves with no accepted child -------
    accepted_ids = {nid for nid, n in nodes.items() if n["status"] in ("accepted", "seed")}
    frontier = 0
    for nid in accepted_ids:
        kids = [c for c in nodes[nid]["children"] if nodes.get(c, {}).get("status") == "accepted"]
        if not kids:
            frontier += 1

    # --- counts ----------------------------------------------------------
    counts = {"accepted": 0, "rejected": 0, "failed": 0, "seed": 0}
    for n in nodes.values():
        counts[n["status"]] = counts.get(n["status"], 0) + 1
    counts["total"] = len(nodes)

    # --- cost / time / tokens split (optimizer vs runner) ---------------
    opt_secs = sum(n.get("optimizer_seconds") or 0.0 for n in nodes.values())
    run_secs = sum(n.get("runner_seconds") or 0.0 for n in nodes.values())
    # cost_usd on a step is the RUNNER eval cost; optimizer cost is captured
    # separately by headless backends as opt_cost_usd when present.
    runner_usd = sum(float(n.get("cost_usd") or 0.0) for n in nodes.values())
    opt_usd = 0.0
    for ev in events:
        if ev.get("kind") in ("step", "skillopt_step", "gepa_val_gate"):
            opt_usd += float(ev.get("opt_cost_usd") or ev.get("optimizer_cost_usd") or 0.0)
    tokens = sum(int(n.get("tokens") or 0) for n in nodes.values())

    test = final.get("test") or {}
    test_reward = test.get("reward")
    try:
        sealed = run_dir.read_splits().test_used
    except Exception:  # noqa: BLE001
        sealed = bool(final)

    delta_pct = None
    if baseline_val not in (None, 0) and best_val is not None:
        delta_pct = round((best_val - baseline_val) / abs(baseline_val) * 100.0, 1)
    elif baseline_val == 0 and best_val:
        delta_pct = None  # undefined %Δ off a zero baseline; show absolute Δ instead

    summary = {
        "run_id": root.name,
        "baseline_val": baseline_val,
        "best_val": best_val,
        "best_id": best_id,
        "delta_abs": (round(best_val - baseline_val, 4)
                      if (best_val is not None and baseline_val is not None) else None),
        "delta_pct": delta_pct,
        "test_reward": test_reward,
        "test_stderr": test.get("stderr"),
        "test_pass_k": test.get("pass_k"),
        "test_sealed": sealed,
        "counts": counts,
        "frontier": frontier,
        "tasks": tasks,
        "wall_clock_seconds": round(opt_secs + run_secs, 1),
        "optimizer_seconds": round(opt_secs, 1),
        "runner_seconds": round(run_secs, 1),
        "cost": {"optimizer_usd": round(opt_usd, 4), "runner_usd": round(runner_usd, 4),
                 "total_usd": round(opt_usd + runner_usd, 4)},
        "tokens": tokens,
        "gate_warnings": gate_warnings,
        "diagnoses": diagnoses,
        "git_log": _git_log(root),
    }

    graph = {"nodes": list(nodes.values()), "root": "seed", "best_id": best_id}
    return redact({"graph": graph, "summary": summary})


# ---------------------------------------------------------------------------
# Diff view (candidate vs parent) — computed from candidate dirs
# ---------------------------------------------------------------------------

def _read_dir_files(d: Path) -> dict[str, str]:
    out = {}
    if not d.exists():
        return out
    for f in sorted(d.rglob("*")):
        if f.is_file():
            try:
                out[str(f.relative_to(d))] = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
    return out


def build_diffs(run_dir, graph: dict) -> dict:
    """For every node with a parent, compute a unified-ish diff vs its parent dir.

    Returns ``{node_id: [{"file", "hunks": [{"old","new","tag"}...]}]}``. Empty when
    candidate dirs were not snapshotted (synthetic logs) — the panel hides itself.
    """
    import difflib
    cand_root = Path(run_dir.candidates)
    diffs: dict[str, list] = {}
    for n in graph["nodes"]:
        nid, parent = n["id"], n.get("parent")
        if not parent:
            continue
        cdir, pdir = cand_root / nid, cand_root / parent
        if not cdir.exists() or not pdir.exists():
            continue
        cf, pf = _read_dir_files(cdir), _read_dir_files(pdir)
        file_diffs = []
        for path in sorted(set(cf) | set(pf)):
            a = pf.get(path, "").splitlines()
            b = cf.get(path, "").splitlines()
            if a == b:
                continue
            rows = []
            for line in difflib.unified_diff(a, b, lineterm="", n=2):
                if line.startswith("+++") or line.startswith("---"):
                    continue
                tag = ("add" if line.startswith("+") else "del" if line.startswith("-")
                       else "hunk" if line.startswith("@@") else "ctx")
                rows.append({"t": tag, "l": line})
            if rows:
                file_diffs.append({"file": path, "rows": rows})
        if file_diffs:
            diffs[nid] = file_diffs
    return redact(diffs)


# ---------------------------------------------------------------------------
# HTML rendering — self-contained (inline CSS + JS + SVG, no CDN)
# ---------------------------------------------------------------------------

def render_html(reduced: dict, run_dir=None) -> str:
    """Render the self-contained dashboard HTML from a reduced run."""
    diffs = {}
    if run_dir is not None:
        try:
            diffs = build_diffs(run_dir, reduced["graph"])
        except Exception:  # noqa: BLE001 — diff panel is optional
            diffs = {}
    payload = {"graph": reduced["graph"], "summary": reduced["summary"], "diffs": diffs}
    data = json.dumps(payload, default=str).replace("</", "<\\/")
    return _HTML_TEMPLATE.replace("/*__RUN_DATA__*/null", data)


def write_dashboard(run_dir) -> Path:
    """Reduce + render + write ``dashboard.html`` next to the run state."""
    reduced = reduce_run(run_dir)
    html_text = render_html(reduced, run_dir)
    out = Path(run_dir.root) / "dashboard.html"
    out.write_text(html_text, encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# ANSI terminal report — CLAUDECODE margin-aware
# ---------------------------------------------------------------------------

class _C:
    RESET = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
    RED = "\033[31m"; GREEN = "\033[32m"; YELLOW = "\033[33m"
    BLUE = "\033[34m"; CYAN = "\033[36m"; GREY = "\033[90m"
    BG_GREEN = "\033[42m"; BG_RED = "\033[41m"


def _term_width(default: int = 100) -> int:
    """Usable terminal width, minus the CLAUDECODE tool-output frame margin.

    Inside Claude Code (``CLAUDECODE=1``) the tool-output frame eats ~6 columns; if
    we print to the real width the lines wrap inside the frame. Subtract the margin
    so the report stays inside the box.
    """
    try:
        cols = shutil.get_terminal_size((default, 24)).columns
    except OSError:
        cols = default
    if os.environ.get("CLAUDECODE") == "1":
        cols -= 6
    return max(40, min(cols, 200))


def render_ansi(reduced: dict, *, color: bool = True, top_n: int = 8) -> str:
    s = reduced["summary"]
    g = reduced["graph"]
    width = _term_width()
    use = color and os.environ.get("NO_COLOR") is None

    def c(code: str, text: str) -> str:
        return f"{code}{text}{_C.RESET}" if use else text

    lines: list[str] = []
    title = f" cap-evolve report · {s['run_id']} "
    lines.append(c(_C.BOLD, title) + c(_C.GREY, "─" * max(0, width - len(title))))

    # --- KPI strip ------------------------------------------------------
    base = s["baseline_val"]
    best = s["best_val"]
    test = s["test_reward"]
    delta = (f"{s['delta_pct']:+.1f}%" if s.get("delta_pct") is not None
             else (f"{s['delta_abs']:+.3f}" if s.get("delta_abs") is not None else "—"))
    fmt = lambda v: "—" if v is None else f"{v:.3f}"  # noqa: E731
    cnt = s["counts"]
    kpi = [
        ("baseline", fmt(base), _C.GREY),
        ("best val", fmt(best), _C.CYAN),
        ("Δ vs base", delta, _C.GREEN if (s.get("delta_abs") or 0) > 0 else _C.GREY),
        ("test" + (" (sealed)" if s["test_sealed"] else ""), fmt(test), _C.BOLD),
        ("cands", str(cnt["total"]), _C.BLUE),
        ("accept", str(cnt["accepted"]), _C.GREEN),
        ("reject", str(cnt["rejected"]), _C.YELLOW),
        ("failed", str(cnt["failed"]), _C.RED),
        ("frontier", str(s["frontier"]), _C.CYAN),
        ("$", f"{s['cost']['total_usd']:.4f}", _C.GREY),
        ("tok", str(s["tokens"]), _C.GREY),
        ("wall", f"{s['wall_clock_seconds']:.0f}s", _C.GREY),
    ]
    row = "  ".join(c(_C.DIM, k + " ") + c(col, v) for k, v, col in kpi)
    lines.append(row)
    lines.append("")

    # --- cumulative-best chart (per iteration) --------------------------
    nodes = sorted([n for n in g["nodes"] if n.get("iteration") is not None],
                   key=lambda n: n["iteration"])
    series = [(n["iteration"], n.get("best_so_far"), n.get("val"), n["status"]) for n in nodes]
    series = [(i, b, v, st) for (i, b, v, st) in series if b is not None]
    if series:
        lines.append(c(_C.BOLD, "cumulative best"))
        chart_h = 6
        vals = [b for _, b, _, _ in series] + [v for _, _, v, _ in series if v is not None]
        lo, hi = min(vals), max(vals)
        span = (hi - lo) or 1.0
        chart_w = min(len(series), width - 10)
        # downsample columns to chart_w
        step = max(1, len(series) // chart_w)
        cols = series[::step]
        grid = [[" "] * len(cols) for _ in range(chart_h)]
        for x, (_, b, v, st) in enumerate(cols):
            yb = chart_h - 1 - int(round((b - lo) / span * (chart_h - 1)))
            grid[yb][x] = "█"
            if v is not None:
                yv = chart_h - 1 - int(round((v - lo) / span * (chart_h - 1)))
                if grid[yv][x] == " ":
                    grid[yv][x] = "·" if st == "rejected" else ("x" if st == "failed" else "○")
        for r, gr in enumerate(grid):
            axis = f"{hi:.2f}" if r == 0 else (f"{lo:.2f}" if r == chart_h - 1 else "    ")
            painted = "".join(c(_C.GREEN, ch) if ch == "█" else
                              (c(_C.RED, ch) if ch == "x" else
                               (c(_C.YELLOW, ch) if ch == "·" else c(_C.CYAN, ch)))
                              for ch in gr)
            lines.append(f"{c(_C.GREY, axis.rjust(5))} {painted}")
        lines.append(c(_C.GREY, "      " + "█ best  ○ accept  · reject  x fail"))
        lines.append("")

    # --- top-N candidate table ------------------------------------------
    ranked = sorted([n for n in g["nodes"] if n.get("val") is not None],
                    key=lambda n: n["val"], reverse=True)[:top_n]
    if ranked:
        lines.append(c(_C.BOLD, f"top {len(ranked)} candidates"))
        hdr = f"{'id':<14}{'status':<10}{'val':>7}{'Δparent':>9}{'iter':>6}"
        lines.append(c(_C.DIM, hdr))
        for n in ranked:
            star = "★" if n["id"] == s["best_id"] else " "
            dlt = (n["val"] - n["parent_val"]) if n.get("parent_val") is not None else None
            stcol = {"accepted": _C.GREEN, "rejected": _C.YELLOW,
                     "failed": _C.RED, "seed": _C.GREY}.get(n["status"], _C.RESET)
            line = (f"{star}{n['id']:<13}" + c(stcol, f"{n['status']:<10}") +
                    f"{n['val']:>7.3f}" +
                    (f"{dlt:>+9.3f}" if dlt is not None else f"{'—':>9}") +
                    f"{n.get('iteration', 0):>6}")
            lines.append(line)
        lines.append("")

    if s["gate_warnings"]:
        lines.append(c(_C.YELLOW, f"⚠ {len(s['gate_warnings'])} gate warning(s):"))
        for w in s["gate_warnings"][:3]:
            txt = (w.get("reason") or "")[: width - 4]
            lines.append(c(_C.GREY, "  " + txt))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML template (inline CSS + JS + SVG). Run data is injected as a JSON island.
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>cap-evolve · run dashboard</title>
<style>
:root{--bg:#07090d;--card:#0d1117;--card2:#141b24;--line:#1e2733;--text:#e6edf3;
--muted:#8b98a9;--accent:#3b82f6;--champion:#f59e0b;--ok:#22c55e;--bad:#ef4444;--warn:#d29922;--radius:12px}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.num{font-variant-numeric:tabular-nums}
header{position:sticky;top:0;z-index:5;background:rgba(14,17,22,.88);backdrop-filter:blur(8px);
border-bottom:1px solid var(--line);padding:14px 28px;display:flex;align-items:baseline;gap:16px}
header h1{font-size:17px;margin:0;font-weight:700;letter-spacing:-.02em}
header .meta{color:var(--muted);font-size:12px}
main{max-width:1180px;margin:0 auto;padding:26px;display:flex;flex-direction:column;gap:26px}
section{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:18px 20px}
section h2{font-size:13px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin:0 0 14px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));gap:12px}
.kpi{background:var(--card2);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.kpi .l{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em}
.kpi .v{font-size:23px;font-weight:700;margin-top:4px}
.kpi .v.ok{color:var(--ok)} .kpi .v.bad{color:var(--bad)} .kpi .v.acc{color:var(--accent)} .kpi .v.champ{color:var(--champion)}
header .logo{flex:none}
header .tag{color:var(--muted);font-size:12px;margin-left:auto}
.phases{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.phase{background:var(--card2);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.phase .nm{font-weight:600} .phase .st{font-size:11px;text-transform:uppercase;letter-spacing:.05em}
.phase.done{border-color:#1f3a23} .phase.done .st{color:var(--ok)}
.phase.active{border-color:var(--accent)} .phase.active .st{color:var(--accent)}
.phase.pending .st{color:var(--muted)}
.phase .d{color:var(--muted);font-size:11px;margin-top:4px}
.dead{background:var(--card2);border:1px solid var(--line);border-left:3px solid var(--bad);border-radius:0 8px 8px 0;padding:6px 12px;margin:6px 0}
.dead .x{color:var(--bad);font-size:11px;float:right}
.kpi .s{color:var(--muted);font-size:11px;margin-top:2px}
svg{display:block;max-width:100%}
.legend{color:var(--muted);font-size:12px;margin-top:8px;display:flex;gap:16px;flex-wrap:wrap}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}
.tip{position:fixed;pointer-events:none;background:#000d;border:1px solid var(--line);
border-radius:8px;padding:7px 10px;font-size:12px;z-index:50;display:none;max-width:320px;white-space:pre-line}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.04em}
td.r,th.r{text-align:right}
.badge{display:inline-block;padding:1px 8px;border-radius:20px;font-size:11px;font-weight:600}
.b-accepted{background:#1f3a23;color:var(--ok)} .b-rejected{background:#3a2f12;color:var(--warn)}
.b-failed{background:#3a1c1c;color:var(--bad)} .b-seed{background:#22303a;color:var(--accent)}
.hide{display:none!important}
.row{display:flex;gap:18px;flex-wrap:wrap}
.col{flex:1;min-width:280px}
select,button{background:var(--card2);color:var(--text);border:1px solid var(--line);
border-radius:8px;padding:5px 9px;font:inherit;cursor:pointer}
.diff{font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;background:#0b0e13;border:1px solid var(--line);
border-radius:8px;padding:10px;overflow:auto;max-height:420px;white-space:pre}
.diff .add{color:var(--ok)} .diff .del{color:var(--bad)} .diff .hunk{color:var(--accent)} .diff .ctx{color:var(--muted)}
.diff .file{color:var(--text);font-weight:700;margin:8px 0 2px}
.ann{border-left:3px solid var(--warn);padding:6px 12px;margin:8px 0;background:var(--card2);border-radius:0 8px 8px 0}
.ann.diag{border-left-color:var(--accent)}
.ann .who{color:var(--muted);font-size:11px}
.heat rect{cursor:pointer} .heat text{fill:var(--muted);font-size:10px}
code{background:var(--card2);padding:1px 5px;border-radius:5px;font-size:12px}
.muted{color:var(--muted)}
</style></head><body>
<header><svg class="logo" width="26" height="26" viewBox="0 0 48 48" aria-label="cap-evolve">
<path d="M4 40 L16 34 L26 24 L36 14 L44 8" fill="none" stroke="#f59e0b" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="44" cy="8" r="2.6" fill="#f59e0b"/>
<g fill="#e6edf3"><ellipse cx="22" cy="33" rx="13" ry="8.5"/><ellipse cx="34" cy="28" rx="7.5" ry="6.5"/>
<ellipse cx="40.5" cy="29.5" rx="3.2" ry="2.6"/><circle cx="31" cy="22" r="1.8"/><circle cx="36" cy="22" r="1.8"/>
<rect x="14" y="38" width="2.8" height="6" rx="1.4"/><rect x="26" y="38" width="2.8" height="6" rx="1.4"/></g>
<circle cx="34" cy="26.5" r="1" fill="#07090d"/></svg>
<h1>cap<span style="color:#f59e0b">·</span>evolve</h1><span class="meta" id="hdr"></span>
<span class="tag">watch capability evolve</span></header>
<main id="main"></main>
<div class="tip" id="tip"></div>
<script type="application/json" id="run-data">/*__RUN_DATA__*/null</script>
<script>
const DATA = JSON.parse(document.getElementById('run-data').textContent);
const G = DATA.graph, S = DATA.summary, DIFFS = DATA.diffs||{};
const $ = (t,a={},...k)=>{const e=document.createElement(t);for(const[p,v]of Object.entries(a)){
  if(p==='html')e.innerHTML=v;else if(p==='text')e.textContent=v;else e.setAttribute(p,v);}
  for(const c of k)if(c!=null)e.append(c);return e;};
const NS='http://www.w3.org/2000/svg';
const svg=(t,a={})=>{const e=document.createElementNS(NS,t);for(const[p,v]of Object.entries(a))e.setAttribute(p,v);return e;};
const fmt=v=>v==null?'—':(+v).toFixed(3);
const main=document.getElementById('main'), tip=document.getElementById('tip');
document.getElementById('hdr').textContent =
  `${S.run_id} · ${S.counts.total} candidates · ${S.test_sealed?'test sealed':'no holdout yet'}`;
function showTip(e,txt){tip.textContent=txt;tip.style.display='block';
  tip.style.left=Math.min(e.clientX+14,innerWidth-330)+'px';tip.style.top=(e.clientY+14)+'px';}
function hideTip(){tip.style.display='none';}
function sec(title){const s=$('section');s.append($('h2',{text:title}));main.append(s);return s;}

/* ---------- 1. KPI strip ---------- */
(function(){
  const s=sec('Summary'); const g=$('div',{class:'kpis'});
  const dpct=S.delta_pct!=null?`${S.delta_pct>0?'+':''}${S.delta_pct}%`:
            (S.delta_abs!=null?`${S.delta_abs>0?'+':''}${S.delta_abs.toFixed(3)}`:'—');
  const kp=(l,v,cls='',s2='')=>{const k=$('div',{class:'kpi'});k.append($('div',{class:'l',text:l}),
    $('div',{class:'v '+cls,text:v}));if(s2)k.append($('div',{class:'s',text:s2}));return k;};
  const c=S.counts, cost=S.cost;
  g.append(
    kp('best val',fmt(S.best_val),'champ',S.best_id),
    kp('baseline',fmt(S.baseline_val)),
    kp('Δ vs baseline',dpct,(S.delta_abs>0?'ok':'')),
    kp('held-out test',fmt(S.test_reward),'',S.test_sealed?'sealed once':'not finalized'),
    kp('candidates',c.total,'',`${c.accepted}✓ ${c.rejected}✗ ${c.failed}⚠`),
    kp('frontier',S.frontier),
    kp('wall clock',`${S.wall_clock_seconds}s`,'',`opt ${S.optimizer_seconds}s · run ${S.runner_seconds}s`),
    kp('cost',`$${cost.total_usd.toFixed(4)}`,'',`opt $${cost.optimizer_usd.toFixed(4)} · run $${cost.runner_usd.toFixed(4)}`),
    kp('tokens',S.tokens.toLocaleString())
  );
  s.append(g);
})();

/* ---------- 1b. Narrative summary ---------- */
(function(){
  const c=S.counts, parts=[];
  if(S.baseline_val!=null&&S.best_val!=null){
    const d=((S.best_val-S.baseline_val)*100).toFixed(1);
    parts.push(`Starting from a ${(S.baseline_val*100).toFixed(1)}% baseline, the search reached `+
      `${(S.best_val*100).toFixed(1)}% (+${d} points)`);
  }
  parts.push(`after ${c.accepted+c.rejected} iterations (${c.accepted} accepted, ${c.rejected} rejected)`);
  if(S.test_reward!=null)parts.push(`The best candidate scored ${(S.test_reward*100).toFixed(1)}% on the sealed test set`);
  if(!parts.length)return;
  const s=sec('Narrative'); s.append($('p',{class:'muted',text:parts.join('. ')+'.'}));
})();

/* ---------- 1c. Phases timeline ---------- */
(function(){
  const c=S.counts, total=c.total, evaluated=c.accepted+c.rejected;
  const hasBase=S.baseline_val!=null, finalized=(S.test_reward!=null)||S.test_sealed;
  const D=b=>b?'done':'pending';
  const phases=[
    {nm:'Intake',st:D(total>0||hasBase),d:'Interview + scaffold project, adapter, seed.'},
    {nm:'Implement & check',st:D(total>0||hasBase),d:'Hard gate before any budget is spent.'},
    {nm:'Baseline',st:D(hasBase),d:`Freeze splits; seed val ${fmt(S.baseline_val)}.`},
    {nm:'Optimize'+(S.algorithm?' · '+S.algorithm:''),st:finalized?'done':(hasBase?'active':'pending'),
     d:`${evaluated} iters · ${c.accepted} accepted · best ${fmt(S.best_val)}.`},
    {nm:'Finalize',st:D(finalized),d:`Sealed test ${fmt(S.test_reward)}.`},
    {nm:'Report',st:D(finalized),d:'This dashboard.'},
  ];
  const s=sec('Pipeline phases'); const g=$('div',{class:'phases'});
  for(const p of phases){const e=$('div',{class:'phase '+p.st});
    e.append($('div',{class:'nm',text:p.nm}),$('div',{class:'st',text:p.st}),$('div',{class:'d',text:p.d}));
    g.append(e);}
  s.append(g);
})();

/* ---------- 1d. What not to try (deduped dead-ends) ---------- */
(function(){
  const norm=r=>(r||'rejected').replace(/-?\d+\.\d+/g,'N').replace(/-?\d+/g,'N').trim();
  const map=new Map();
  for(const n of G.nodes){ if(n.status!=='rejected')continue;
    const k=norm(n.reason); const cur=map.get(k)||{reason:k,count:0,ex:[]};
    cur.count++; if(cur.ex.length<3)cur.ex.push(n.id); map.set(k,cur);}
  const ends=[...map.values()].sort((a,b)=>b.count-a.count);
  if(!ends.length)return;
  const s=sec('What not to try — dead ends');
  for(const d of ends){const e=$('div',{class:'dead'});
    if(d.count>1)e.append($('span',{class:'x',text:'×'+d.count}));
    e.append($('div',{class:'muted',text:d.ex.join(', ')}),$('div',{text:d.reason}));
    s.append(e);}
})();

/* ---------- 2. Cumulative-best stair over per-iteration scatter ---------- */
(function(){
  const pts=G.nodes.filter(n=>n.iteration!=null&&n.best_so_far!=null)
    .sort((a,b)=>a.iteration-b.iteration);
  if(pts.length<2)return;
  const s=sec('Score over iterations — cumulative best');
  const W=1080,H=300,m={l:46,r:16,t:16,b:30};
  const xs=pts.map(p=>p.iteration), allv=pts.flatMap(p=>[p.best_so_far,p.val].filter(v=>v!=null));
  const xmin=Math.min(...xs),xmax=Math.max(...xs)||1,vmin=Math.min(...allv,0),vmax=Math.max(...allv,1);
  const X=i=>m.l+(i-xmin)/((xmax-xmin)||1)*(W-m.l-m.r);
  const Y=v=>H-m.b-(v-vmin)/((vmax-vmin)||1)*(H-m.t-m.b);
  const el=svg('svg',{viewBox:`0 0 ${W} ${H}`,width:W,height:H});
  for(let g2=0;g2<=4;g2++){const v=vmin+(vmax-vmin)*g2/4;
    el.append(svg('line',{x1:m.l,x2:W-m.r,y1:Y(v),y2:Y(v),stroke:'#2b333d','stroke-width':1}));
    el.append(svg('text',{x:6,y:Y(v)+4,fill:'#8b949e','font-size':10,'text-content':''})).textContent=v.toFixed(2);}
  // stair polyline of running best
  let d='';let prevY=null;
  pts.forEach((p,i)=>{const x=X(p.iteration),y=Y(p.best_so_far);
    if(i===0)d=`M${x},${y}`;else d+=` L${x},${prevY} L${x},${y}`;prevY=y;});
  el.append(svg('path',{d,fill:'none',stroke:'#3fb950','stroke-width':2}));
  // record-holder rings + per-iter scatter
  let rec=-1;
  pts.forEach(p=>{
    if(p.val!=null){const col=p.status==='accepted'?'#3fb950':p.status==='failed'?'#f85149':'#d29922';
      const c=svg('circle',{cx:X(p.iteration),cy:Y(p.val),r:4,fill:col,'fill-opacity':.85,stroke:'#0e1116'});
      const dpar=p.parent_val!=null?(p.val-p.parent_val).toFixed(3):'—';
      c.addEventListener('mousemove',e=>showTip(e,`${p.id}\n${p.status}  val=${fmt(p.val)}\nΔ parent=${dpar}\niter ${p.iteration}`));
      c.addEventListener('mouseleave',hideTip);el.append(c);}
    if(p.best_so_far>rec){rec=p.best_so_far;
      el.append(svg('circle',{cx:X(p.iteration),cy:Y(p.best_so_far),r:7,fill:'none',stroke:'#4493f8','stroke-width':1.5}));}
  });
  // champion star + label
  const champ=pts.reduce((a,b)=>(b.best_so_far>=a.best_so_far?b:a),pts[0]);
  const cx=X(champ.iteration),cy=Y(champ.best_so_far);
  el.append(svg('path',{d:starPath(cx,cy-12,7,3),fill:'#f0d040',stroke:'#0e1116'}));
  el.append(svg('text',{x:cx+10,y:cy-8,fill:'#e6edf3','font-size':12})).textContent=fmt(champ.best_so_far);
  s.append(el);
  s.append($('div',{class:'legend',html:
    '<span><i style="background:#3fb950"></i>running best / accept</span>'+
    '<span><i style="background:#d29922"></i>rejected</span>'+
    '<span><i style="background:#f85149"></i>failed</span>'+
    '<span><i style="background:#4493f8;border-radius:50%"></i>record-holder ring</span>'}));
  function starPath(cx,cy,R,r){let p='';for(let i=0;i<10;i++){const ang=Math.PI/5*i-Math.PI/2;
    const rad=i%2?r:R;p+=(i?'L':'M')+(cx+rad*Math.cos(ang))+','+(cy+rad*Math.sin(ang));}return p+'Z';}
})();

/* ---------- 3. tasks × iterations pass/fail heatmap ---------- */
(function(){
  const tasks=S.tasks||[];
  const iters=G.nodes.filter(n=>Object.keys(n.per_task||{}).length).sort((a,b)=>a.iteration-b.iteration);
  if(!tasks.length||iters.length<1)return;
  const s=sec('Per-task pass/fail across iterations');
  // sort rows worst-first by mean reward
  const meanFor=t=>{let sum=0,n=0;iters.forEach(it=>{if(it.per_task[t]!=null){sum+=it.per_task[t];n++;}});return n?sum/n:0;};
  const rows=[...tasks].sort((a,b)=>meanFor(a)-meanFor(b));
  const cw=Math.max(10,Math.min(26,Math.floor(1000/iters.length))),ch=16,labW=120;
  const W=labW+iters.length*cw+10,H=rows.length*ch+24;
  const el=svg('svg',{viewBox:`0 0 ${W} ${H}`,width:W,height:H,class:'heat'});
  iters.forEach((it,j)=>{el.append(svg('text',{x:labW+j*cw+cw/2,y:12,'text-anchor':'middle'})).textContent=it.iteration;});
  rows.forEach((t,i)=>{
    el.append(svg('text',{x:labW-6,y:24+i*ch+11,'text-anchor':'end'})).textContent=t.length>16?t.slice(0,15)+'…':t;
    iters.forEach((it,j)=>{
      const v=it.per_task[t];
      const col=v==null?'#21262d':v>=0.999?'#2ea043':v<=0.001?'#7d2622':'#9e6a1a';
      const rect=svg('rect',{x:labW+j*cw,y:24+i*ch,width:cw-1.5,height:ch-1.5,rx:2,fill:col});
      const fb=(it.feedback&&it.feedback[t])||'';
      rect.addEventListener('mousemove',e=>showTip(e,`${t} @ iter ${it.iteration} (${it.id})\nreward=${v==null?'—':v.toFixed(3)}\n${fb.slice(0,180)}`));
      rect.addEventListener('mouseleave',hideTip);
      el.append(rect);
    });
  });
  s.append(el);
  s.append($('div',{class:'legend',html:
    '<span><i style="background:#2ea043"></i>pass</span><span><i style="background:#7d2622"></i>fail</span>'+
    '<span><i style="background:#9e6a1a"></i>partial</span><span><i style="background:#21262d"></i>not run</span>'+
    '<span class="muted">rows sorted worst-first · hover a cell for feedback</span>'}));
})();

/* ---------- 4. Per-iteration diff view ---------- */
(function(){
  const ids=Object.keys(DIFFS); if(!ids.length)return;
  const s=sec('Diff vs parent');
  const bar=$('div',{class:'row'});
  const sel=$('select'); ids.forEach(id=>sel.append($('option',{value:id,text:id})));
  const mode=$('select'); mode.append($('option',{value:'unified',text:'unified'}),$('option',{value:'split',text:'split'}));
  bar.append($('span',{class:'muted',text:'candidate '}),sel,$('span',{class:'muted',text:' view '}),mode);
  s.append(bar);
  const out=$('div',{class:'diff'}); s.append(out);
  function esc(t){return t.replace(/&/g,'&amp;').replace(/</g,'&lt;');}
  function render(){
    const id=sel.value, files=DIFFS[id]||[], split=mode.value==='split';
    out.innerHTML='';
    files.forEach(f=>{
      out.append($('div',{class:'file',text:'━ '+f.file}));
      if(!split){
        f.rows.forEach(r=>out.append($('div',{class:r.t,text:r.l})));
      }else{
        const tbl=$('div'); f.rows.forEach(r=>{
          if(r.t==='hunk'){tbl.append($('div',{class:'hunk',text:r.l}));return;}
          const cls=r.t; const line=$('div',{class:cls});
          line.textContent=(r.t==='del'?'◀ ':r.t==='add'?'▶ ':'  ')+r.l.slice(1);
          tbl.append(line);
        }); out.append(tbl);
      }
    });
  }
  sel.addEventListener('change',render); mode.addEventListener('change',render); render();
})();

/* ---------- 5. Lineage tree (DAG, best-spine highlighted) ---------- */
(function(){
  const nodes=G.nodes, byId=Object.fromEntries(nodes.map(n=>[n.id,n]));
  if(nodes.length<2)return;
  const s=sec('Lineage');
  // depth = distance from root; assign columns by BFS order within depth
  const depth={}; const order=[];
  (function walk(id,d){const n=byId[id];if(!n||depth[id]!=null)return;depth[id]=d;order.push(id);
    (n.children||[]).forEach(c=>walk(c,d+1));})('seed',0);
  nodes.forEach(n=>{if(depth[n.id]==null){depth[n.id]=0;order.push(n.id);}});
  const cols={}; const maxd=Math.max(...Object.values(depth));
  const byDepth={}; order.forEach(id=>{const d=depth[id];(byDepth[d]=byDepth[d]||[]).push(id);});
  const pos={};
  for(let d=0;d<=maxd;d++){(byDepth[d]||[]).forEach((id,i)=>pos[id]={x:60+d*150,y:40+i*46});}
  // best-lineage spine
  const spine=new Set(); let cur=S.best_id;
  while(cur){spine.add(cur);cur=byId[cur]?byId[cur].parent:null;}
  const W=80+( maxd+1)*150, H=40+Math.max(...Object.values(byDepth).map(a=>a.length))*46+20;
  const el=svg('svg',{viewBox:`0 0 ${W} ${H}`,width:W,height:H});
  nodes.forEach(n=>{const p=pos[n.id];if(!p)return;
    const parents=[n.parent,...(n.merge_of||[])].filter(x=>x&&pos[x]);
    parents.forEach(pp=>{const a=pos[pp];const onSpine=spine.has(n.id)&&spine.has(pp);
      el.append(svg('path',{d:`M${a.x+14},${a.y} C${(a.x+p.x)/2},${a.y} ${(a.x+p.x)/2},${p.y} ${p.x-14},${p.y}`,
        fill:'none',stroke:onSpine?'#f0d040':'#3a434d','stroke-width':onSpine?2.5:1.2}));});
  });
  nodes.forEach(n=>{const p=pos[n.id];if(!p)return;
    const col=n.status==='accepted'?'#3fb950':n.status==='rejected'?'#d29922':n.status==='failed'?'#f85149':'#4493f8';
    const c=svg('circle',{cx:p.x,cy:p.y,r:n.id===S.best_id?9:6,fill:col,
      stroke:spine.has(n.id)?'#f0d040':'#0e1116','stroke-width':spine.has(n.id)?2:1});
    c.addEventListener('mousemove',e=>showTip(e,`${n.id}\n${n.status}  val=${fmt(n.val)}\n${n.reason||''}`));
    c.addEventListener('mouseleave',hideTip); el.append(c);
    el.append(svg('text',{x:p.x+12,y:p.y+4,fill:'#8b949e','font-size':10})).textContent=n.id;
  });
  s.append(el);
  s.append($('div',{class:'legend',html:'<span><i style="background:#f0d040"></i>best lineage spine</span>'+
    '<span class="muted">merges shown as multi-parent edges</span>'}));
})();

/* ---------- 6. Cost / tokens / latency ---------- */
(function(){
  const pts=G.nodes.filter(n=>n.iteration).sort((a,b)=>a.iteration-b.iteration);
  if(!pts.length)return;
  const s=sec('Cost · tokens · latency (optimizer vs runner)');
  const W=1080,H=240,m={l:46,r:16,t:14,b:28},n=pts.length;
  const bw=Math.max(6,Math.min(40,(W-m.l-m.r)/n-6));
  const maxSec=Math.max(...pts.map(p=>(p.optimizer_seconds||0)+(p.runner_seconds||0)),0.001);
  const el=svg('svg',{viewBox:`0 0 ${W} ${H}`,width:W,height:H});
  // stacked bars: optimizer (blue) + runner (green) seconds; cumulative cost line
  let cum=0; const costMax=Math.max(S.cost.total_usd,0.0001);
  pts.forEach((p,i)=>{const x=m.l+i*((W-m.l-m.r)/n)+3;
    const os=(p.optimizer_seconds||0)/maxSec*(H-m.t-m.b);
    const rs=(p.runner_seconds||0)/maxSec*(H-m.t-m.b);
    el.append(svg('rect',{x,y:H-m.b-rs,width:bw,height:rs,fill:'#3fb950'})).addEventListener('mousemove',()=>{});
    el.append(svg('rect',{x,y:H-m.b-rs-os,width:bw,height:os,fill:'#4493f8'}));
    const bar=svg('rect',{x,y:m.t,width:bw,height:H-m.t-m.b,fill:'transparent'});
    bar.addEventListener('mousemove',e=>showTip(e,`${p.id} · iter ${p.iteration}\nopt ${(p.optimizer_seconds||0).toFixed(2)}s · run ${(p.runner_seconds||0).toFixed(2)}s\n$${(p.cost_usd||0).toFixed(4)} · ${p.tokens||0} tok`));
    bar.addEventListener('mouseleave',hideTip); el.append(bar);
  });
  // cumulative cost line (right axis, normalized)
  let d='';pts.forEach((p,i)=>{cum+=(p.cost_usd||0);const x=m.l+i*((W-m.l-m.r)/n)+3+bw/2;
    const y=H-m.b-(cum/costMax)*(H-m.t-m.b);d+=(i?' L':'M')+x+','+y;});
  if(S.cost.total_usd>0)el.append(svg('path',{d,fill:'none',stroke:'#f0d040','stroke-width':1.8,'stroke-dasharray':'4 3'}));
  s.append(el);
  s.append($('div',{class:'legend',html:'<span><i style="background:#4493f8"></i>optimizer s</span>'+
    '<span><i style="background:#3fb950"></i>runner s</span>'+
    (S.cost.total_usd>0?'<span><i style="background:#f0d040"></i>cumulative $</span>':'')}));
})();

/* ---------- 6b. cumulative cost vs best score ---------- */
(function(){
  if(S.cost.total_usd<=0)return;
  const pts=G.nodes.filter(n=>n.iteration&&n.best_so_far!=null).sort((a,b)=>a.iteration-b.iteration);
  if(pts.length<2)return;
  const s=sec('Cost vs best score'); const W=1080,H=220,m={l:46,r:16,t:14,b:28};
  let cum=0;const xy=pts.map(p=>{cum+=(p.cost_usd||0);return [cum,p.best_so_far];});
  const xmax=Math.max(...xy.map(p=>p[0]))||1,ymin=Math.min(...xy.map(p=>p[1]),0),ymax=Math.max(...xy.map(p=>p[1]),1);
  const X=v=>m.l+v/xmax*(W-m.l-m.r),Y=v=>H-m.b-(v-ymin)/((ymax-ymin)||1)*(H-m.t-m.b);
  const el=svg('svg',{viewBox:`0 0 ${W} ${H}`,width:W,height:H});
  let d='';xy.forEach((p,i)=>d+=(i?' L':'M')+X(p[0])+','+Y(p[1]));
  el.append(svg('path',{d,fill:'none',stroke:'#4493f8','stroke-width':2}));
  el.append(svg('text',{x:W-m.r,y:H-8,fill:'#8b949e','font-size':10,'text-anchor':'end'})).textContent=`$${xmax.toFixed(4)} total`;
  s.append(el);
})();

/* ---------- 7. Annotations / diagnoses stream ---------- */
(function(){
  const W=S.gate_warnings||[], D=S.diagnoses||[];
  if(!W.length&&!D.length)return;
  const s=sec('Annotations & diagnoses');
  W.forEach(w=>{const a=$('div',{class:'ann'});a.append($('div',{class:'who',text:'gate · '+(w.mode||'')}),
    $('div',{text:w.reason||''}));s.append(a);});
  D.forEach(d=>{const a=$('div',{class:'ann diag'});a.append($('div',{class:'who',text:(d.kind||'diagnose')+(d.candidate?' · '+d.candidate:'')}),
    $('div',{text:(d.text||'').slice(0,400)}));s.append(a);});
})();

/* ---------- 8. Candidate leaderboard + git log ---------- */
(function(){
  const s=sec('Candidates'); const t=$('table');
  t.append($('tr',{},$('th',{text:'id'}),$('th',{text:'status'}),$('th',{class:'r',text:'val'}),
    $('th',{class:'r',text:'Δ parent'}),$('th',{class:'r',text:'iter'}),$('th',{text:'reason'})));
  G.nodes.slice().sort((a,b)=>(b.val||-1)-(a.val||-1)).forEach(n=>{
    const dlt=n.parent_val!=null&&n.val!=null?(n.val-n.parent_val):null;
    t.append($('tr',{},
      $('td',{},n.id===S.best_id?'★ '+n.id:n.id),
      $('td',{},$('span',{class:'badge b-'+n.status,text:n.status})),
      $('td',{class:'r num',text:fmt(n.val)}),
      $('td',{class:'r num',text:dlt==null?'—':(dlt>0?'+':'')+dlt.toFixed(3)}),
      $('td',{class:'r num',text:n.iteration}),
      $('td',{class:'muted',text:(n.reason||'').slice(0,80)})));
  });
  s.append(t);
  if(S.git_log&&S.git_log.length){
    s.append($('h2',{text:'Iteration store (git)',style:'margin-top:18px'}));
    const g=$('div',{class:'diff'});
    S.git_log.forEach(r=>g.append($('div',{class:'ctx',text:r.hash+'  '+r.subject})));
    s.append(g);
  }
})();
</script></body></html>
"""
