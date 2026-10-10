"""pregate — deterministic, ~$0 validity checks run on a candidate BEFORE any screen or val gate (#708).

A candidate once added a composite write tool that called other write tools from inside Python.
The benchmark grades the list of actions the AGENT took, so the internal writes were invisible:
a zero DB-match after 278 rollouts (~3.55 USD). Everything here is the cheap version of that lesson.

Checks (each ``{name, ok, detail, skipped?}``; a check with nothing to look at is skipped, never
failed):

* ``static``      — every ``.py`` compiles, every ``.md`` decodes, policy text grew <= the cap.
* ``hidden_writes`` — AST scan: a NEW/CHANGED write tool must not call another write tool
  itself (``self.other_write(...)`` / ``getattr(self, "other_write")``). Heuristic: a call via a
  computed name is reported as a warning only, never a failure.
* ``tool_smoke``  — changed tools re-run on ``tool_fixtures.jsonl`` rows (built by
  ``diagnose/scripts/build_tool_fixtures.py``); a NEW exception on a row that recorded no error fails.
* ``replay``      — tool-call-level gold replay (see below).

Replay spike (scripting the benchmark's user simulator): its registry lets a custom user class
be registered, so a user returning the recorded user turns is possible, but the AGENT is still
an LLM, so after its first divergent reply the scripted turns no longer answer what it asked:
it costs real LLM calls, needs the benchmark venv and gateway, and is not deterministic. So the replay here is at the TOOL-CALL level, with no LLM: the recorded agent tool
calls are re-executed in order against the candidate's tools and against the parent's, each on
a fresh toolkit, and the per-call outcome (ok/error), the set of successful write calls and the
final DB hash must match. It is valid only for deterministic tool paths, and it only runs when
an adapter-supplied ``--toolkit module:callable`` (``callable(candidate_dir) -> toolkit``,
optional ``get_db_hash()``) and ``--trace`` are given.

CLI: ``pregate.py --candidate DIR [--parent DIR] [--fixtures F] [--toolkit M:F] [--trace T ...]``;
exit 1 and a fix-it message on failure. ``enabled(spec)`` is the ``ablation.pregate`` switch.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
#: Policy text may grow at most this fraction over the parent (one real candidate: +42% — the cost guard).
MAX_POLICY_GROWTH = 0.30


def enabled(spec: dict | None = None) -> bool:
    """`ablation.pregate`: env CAPEVOLVE_PREGATE wins, then spec ablation.pregate; default on."""
    env = os.environ.get("CAPEVOLVE_PREGATE", "").strip().lower()
    if env:
        return env not in {"0", "false", "no", "off"}
    ab = (spec or {}).get("ablation")
    v = ab.get("pregate") if isinstance(ab, dict) else None
    return True if v is None else bool(v)


def _cluster():
    """cluster.py (trace_calls, _mutates) loaded by path: other skills ship same-named modules."""
    skills = Path(os.environ.get("CAPEVOLVE_SKILLS_DIR", HERE.parents[2]))
    spec = importlib.util.spec_from_file_location(
        "pregate_cluster", skills / "phases" / "diagnose" / "scripts" / "cluster.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _check(name, ok, detail="", skipped=False):
    return {"name": name, "ok": bool(ok), "detail": detail, "skipped": skipped}


def _files(root: Path, suffix: str) -> list[Path]:
    return sorted(p for p in root.rglob(f"*{suffix}")
                  if p.is_file() and "__pycache__" not in p.parts) if root.is_dir() else []


def _policy_bytes(root: Path) -> int:
    return sum(p.stat().st_size for p in _files(root / "policy", ".md"))


# ---- static ---------------------------------------------------------------------------------
def static_check(cand: Path, parent: Path | None = None, max_growth: float = MAX_POLICY_GROWTH) -> dict:
    bad = []
    for p in _files(cand, ".py"):
        try:
            compile(p.read_text(encoding="utf-8"), str(p), "exec")
        except (SyntaxError, UnicodeDecodeError, ValueError) as e:
            bad.append(f"{p.relative_to(cand)}: {type(e).__name__}: {e}")
    for p in _files(cand, ".md"):
        try:
            p.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            bad.append(f"{p.relative_to(cand)}: {e}")
    if parent is not None and (old := _policy_bytes(parent)):
        growth = _policy_bytes(cand) / old - 1
        if growth > max_growth:
            bad.append(f"policy grew {growth:+.0%} over the parent (cap {max_growth:+.0%}): "
                       "every task pays for those tokens; trim or justify")
    return _check("static", not bad, "; ".join(bad))


# ---- hidden writes (AST) --------------------------------------------------------------------
def _funcs(tree: ast.AST) -> dict[str, ast.FunctionDef]:
    return {n.name: n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _is_write(fn, mutates) -> bool:
    deco = " ".join(ast.unparse(d) for d in fn.decorator_list)
    if "WRITE" in deco:
        return True
    if "is_tool" in deco or fn.name.startswith("_"):
        return False
    return mutates(fn.name)  # undecorated public function: the name heuristic, as cluster.py


def hidden_writes(cand_src: str, parent_src: str | None = None, mutates=None) -> dict:
    """Failure iff a new/changed write tool directly calls another write tool."""
    mutates = mutates or _cluster()._mutates
    funcs, old = _funcs(ast.parse(cand_src)), _funcs(ast.parse(parent_src)) if parent_src else {}
    writes = {n for n, f in funcs.items() if _is_write(f, mutates)}
    bad, warn = [], []
    for name in sorted(writes):
        fn = funcs[name]
        if name in old and ast.dump(old[name]) == ast.dump(fn):
            continue  # unchanged: whatever it does, the parent already did
        for c in (n for n in ast.walk(fn) if isinstance(n, ast.Call)):
            f = c.func
            callee = f.attr if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) \
                and f.value.id in {"self", "cls"} else f.id if isinstance(f, ast.Name) else None
            if isinstance(f, ast.Name) and f.id == "getattr" and len(c.args) >= 2:
                a = c.args[1]
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    callee = a.value
                else:
                    warn.append(f"{name}: getattr with a computed name (cannot verify)")
            if callee in writes and callee != name:
                bad.append(f"{name} calls write tool {callee} internally (line {c.lineno})")
    msg = ("; ".join(dict.fromkeys(bad)) + ". The grader scores the agent's visible actions, so an internal "
           "write is invisible to it (DB match 0). Keep one tool per write, or "
           "have the policy tell the agent to call each write itself.") if bad else ""
    return {**_check("hidden_writes", not bad, msg or "; ".join(dict.fromkeys(warn))),
            "warnings": list(dict.fromkeys(warn))}


def hidden_writes_dirs(cand: Path, parent: Path | None) -> dict:
    """hidden_writes over every .py under cand/tools, paired with the parent's same-path file."""
    fails, warns, seen = [], [], 0
    for p in _files(cand / "tools", ".py"):
        rel = p.relative_to(cand)
        old = (parent / rel) if parent else None
        try:
            r = hidden_writes(p.read_text(encoding="utf-8"),
                              old.read_text(encoding="utf-8") if old and old.is_file() else None)
        except SyntaxError:
            continue  # reported by static
        seen += 1
        if r["detail"]:
            (warns if r["ok"] else fails).append(f"{rel}: {r['detail']}")
    if not seen:
        return _check("hidden_writes", True, "no tools/*.py", skipped=True)
    return _check("hidden_writes", not fails, "; ".join(fails or warns))


# ---- tool smoke -----------------------------------------------------------------------------
def tool_smoke(toolkit, fixtures: list[dict], tools: set[str] | None = None) -> dict:
    """Re-run recorded pre-write calls of ``tools`` (None = all). New exception => fail."""
    rows = [r for r in fixtures if tools is None or r.get("tool") in tools]
    if not rows:
        return _check("tool_smoke", True, "no fixtures for the changed tools", skipped=True)
    bad = []
    for r in rows:
        if not hasattr(toolkit, r["tool"]):
            bad.append(f"{r['tool']}: tool missing from the candidate")
            continue
        try:
            getattr(toolkit, r["tool"])(**(r.get("args") or {}))
        except Exception as e:  # the recorded result had no error (fixtures drop failed reads)
            if not str(r.get("result") or "").lstrip().lower().startswith("error"):
                bad.append(f"{r['tool']}({r.get('args')}): {type(e).__name__}: {e}")
    return _check("tool_smoke", not bad, "; ".join(bad[:5]) + (f" (+{len(bad) - 5} more)" if len(bad) > 5 else ""))


# ---- tool-call replay -----------------------------------------------------------------------
def _run_calls(toolkit, calls: list[dict]) -> tuple[list[str], str | None]:
    out = []
    for c in calls:
        try:
            getattr(toolkit, c["name"])(**(c["args"] if isinstance(c["args"], dict) else {}))
            out.append("ok")
        except Exception as e:
            out.append(f"err:{type(e).__name__}")
    h = getattr(toolkit, "get_db_hash", None)
    return out, (h() if callable(h) else None)


def replay(make_cand, make_parent, calls: list[dict], mutates=None) -> dict:
    """Same recorded calls on a fresh candidate and parent toolkit: outcomes, successful write
    calls and final DB hash must agree. (Parent-only comparison: the recorded trace's own
    results may depend on LLM-free state we cannot rebuild, the parent's replay is the oracle.)"""
    mutates = mutates or _cluster()._mutates
    if not calls:
        return _check("replay", True, "no recorded tool calls", skipped=True)
    (co, ch), (po, ph) = _run_calls(make_cand(), calls), _run_calls(make_parent(), calls)
    diffs = [f"call {i} {c['name']}: candidate {a}, parent {b}"
             for i, (c, a, b) in enumerate(zip(calls, co, po)) if a != b]
    cw = [c["name"] for c, o in zip(calls, co) if o == "ok" and mutates(c["name"])]
    pw = [c["name"] for c, o in zip(calls, po) if o == "ok" and mutates(c["name"])]
    if cw != pw:
        diffs.append(f"successful write calls differ: candidate {cw}, parent {pw}")
    if ch != ph:
        diffs.append("final DB state differs from the parent's replay")
    return _check("replay", not diffs, "; ".join(diffs[:5]))


def trace_agent_calls(path: Path) -> list[dict]:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return _cluster().trace_calls(d.get("rollout") or d)


# ---- driver ---------------------------------------------------------------------------------
def _load_factory(spec: str):
    mod, _, fn = spec.partition(":")
    return getattr(__import__(mod, fromlist=[fn]), fn or "make_toolkit")


def changed_tools(cand: Path, parent: Path | None) -> set[str]:
    """Names of functions in cand/tools that are new or differ from the parent's."""
    names = set()
    for p in _files(cand / "tools", ".py"):
        old = parent / p.relative_to(cand) if parent else None
        try:
            new_f = _funcs(ast.parse(p.read_text(encoding="utf-8")))
            old_f = _funcs(ast.parse(old.read_text(encoding="utf-8"))) if old and old.is_file() else {}
        except SyntaxError:
            continue
        names |= {n for n, f in new_f.items() if n not in old_f or ast.dump(old_f[n]) != ast.dump(f)}
    return names


def run(cand: Path, parent: Path | None = None, *, fixtures: Path | None = None,
        toolkit: str | None = None, traces: list[Path] = (), max_growth: float = MAX_POLICY_GROWTH) -> dict:
    checks = [static_check(cand, parent, max_growth)]
    if checks[0]["ok"]:  # nothing below is meaningful on code that does not compile
        checks.append(hidden_writes_dirs(cand, parent))
        factory = _load_factory(toolkit) if toolkit else None
        rows = [json.loads(ln) for ln in fixtures.read_text(encoding="utf-8").splitlines() if ln.strip()] \
            if fixtures and fixtures.is_file() else []
        if factory and rows:
            checks.append(tool_smoke(factory(cand), rows, changed_tools(cand, parent)))
        else:
            checks.append(_check("tool_smoke", True, "needs --toolkit and tool_fixtures.jsonl", skipped=True))
        if factory and parent is not None and traces:
            for t in traces:
                r = replay(lambda: factory(cand), lambda: factory(parent), trace_agent_calls(t))
                r["detail"] = f"{Path(t).name}: {r['detail']}" if r["detail"] else ""
                checks.append(r)
        else:
            checks.append(_check("replay", True, "needs --toolkit, --parent and --trace", skipped=True))
    failed = [c for c in checks if not c["ok"]]
    return {"ok": not failed, "checks": checks,
            "failure": "; ".join(f"[{c['name']}] {c['detail']}" for c in failed)}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="pregate")
    p.add_argument("--candidate", required=True)
    p.add_argument("--parent")
    p.add_argument("--fixtures", help="tool_fixtures.jsonl (default: <run>/tool_fixtures.jsonl via --run-dir)")
    p.add_argument("--run-dir")
    p.add_argument("--toolkit", help="module:callable(candidate_dir) -> toolkit with the tool methods")
    p.add_argument("--trace", action="append", default=[], help="rollout json to replay (repeatable)")
    p.add_argument("--max-policy-growth", type=float, default=MAX_POLICY_GROWTH)
    a = p.parse_args(argv)
    fx = Path(a.fixtures) if a.fixtures else (Path(a.run_dir) / "tool_fixtures.jsonl" if a.run_dir else None)
    res = run(Path(a.candidate), Path(a.parent) if a.parent else None, fixtures=fx,
              toolkit=a.toolkit, traces=[Path(t) for t in a.trace], max_growth=a.max_policy_growth)
    print(json.dumps(res, indent=2))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
