"""pregate — deterministic, ~$0 validity checks run on a candidate BEFORE any screen or val gate (#708).

A candidate once added a composite write tool that called other write tools from inside Python.
The benchmark grades the list of actions the AGENT took, so the internal writes were invisible:
a zero DB-match after 278 rollouts (~3.55 USD). Everything here is the cheap version of that lesson.

Checks (each ``{name, ok, detail, skipped, warnings?, error?}``):

* ``static``        — tools/*.py compile, policy/*.md decode; policy growth over the parent is a
  WARNING unless ``pregate.max_policy_growth`` is set explicitly (big coherent edits are wanted).
* ``hidden_writes`` — call-graph scan. Nodes are ``file:Class.method`` / ``file:function``. Edges are
  any reference (call OR value: aliases, dispatch dicts) to a known function name through
  ``self``/``cls``/``type(self)``/``self.helper.x``/an imported module, or a bare name. From each
  write tool we follow private helpers transitively and stop at the first write tool reached. A
  write tool that reaches another write tool, or uses a name it cannot resolve statically
  (``getattr(self, name)``, ``exec``, ``eval``, ``__import__``, ``globals()``), FAILS — but only
  for edges NEW relative to the parent, so an old composite with a docstring edit is not blamed.
  Without a parent dir the delta checks are skipped with a warning.
  Write tools = decorated ``WRITE``, plus ``pregate.write_tools`` (explicit list, authoritative
  for undecorated names), else the parent's decorated-WRITE names and the public-name prefixes
  in ``WRITE_PREFIXES``. Plain helpers (``format_reservation``) are never writes.
* ``tool_smoke``    — changed tools re-run on ``tool_fixtures.jsonl`` rows; a NEW exception fails.
* ``replay``        — tool-call-level replay (below). Candidate must equal the parent on tools
  UNCHANGED between them; diffs on changed tools are info only (a legitimate fix changes them).

Infra errors (missing module, bad toolkit, malformed fixture) never crash a round: the check
returns ``skipped`` with ``error`` and a warning (fail-OPEN), unless ``pregate.strict: true``,
which turns the error into a failure. static/hidden_writes are computed first and never lost.

Replay spike (scripting the benchmark's user simulator): its registry lets a custom user class
be registered, so a user returning the recorded user turns is possible, but the AGENT is still
an LLM, so after its first divergent reply the scripted turns no longer answer what it asked:
it costs real LLM calls, needs the benchmark venv and gateway, and is not deterministic. So the
replay is at the TOOL-CALL level, with no LLM: recorded agent calls are re-executed in order on a
fresh candidate and parent toolkit (adapter-supplied ``--toolkit module_or_file.py:callable``,
``callable(candidate_dir) -> toolkit``, optional ``get_db_hash()``) and compared. Valid only for
deterministic tool paths.

CLI: ``pregate.py --candidate DIR [--parent DIR] [--fixtures F] [--toolkit M:F] [--trace T ...]``;
exit 1 on failure. ``enabled(spec)`` is the ``optimizer.ablation.pregate`` switch.
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
#: Policy growth above this fraction over the parent is a warning (a failure only if set explicitly).
MAX_POLICY_GROWTH = 0.30
#: Public undecorated names starting with these count as write tools (the documented fallback).
WRITE_PREFIXES = ("update_", "cancel_", "book_", "send_", "create_", "delete_", "modify_",
                  "remove_", "add_", "set_", "issue_", "refund_", "exchange_", "pay_")
_DYNAMIC_CALLS = {"exec", "eval", "__import__", "globals", "vars"}


def enabled(spec: dict | None = None) -> bool:
    """Ablation: env CAPEVOLVE_PREGATE wins, then ``optimizer.ablation.pregate``, then the legacy
    top-level ``ablation.pregate``; default on."""
    from cap_evolve.optimizer_config import enabled as _enabled
    return _enabled("pregate", spec)


def _cluster():
    """cluster.py (trace_calls, _mutates) loaded by path: other skills ship same-named modules."""
    skills = Path(os.environ.get("CAPEVOLVE_SKILLS_DIR", HERE.parents[2]))
    spec = importlib.util.spec_from_file_location(
        "pregate_cluster", skills / "phases" / "diagnose" / "scripts" / "cluster.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _check(name, ok, detail="", skipped=False, **extra):
    return {"name": name, "ok": bool(ok), "detail": detail, "skipped": skipped, **extra}


def _guard(name, fn, strict=False):
    """Run a check; an infra exception becomes a structured error result (fail-open unless strict)."""
    try:
        return fn()
    except Exception as e:  # noqa: BLE001 — a broken check must never abort the round
        msg = f"{type(e).__name__}: {e}"
        return _check(name, not strict, f"infra error ({'strict: failing' if strict else 'fail-open'}): {msg}",
                      skipped=True, error=msg, warnings=[f"pregate check {name!r} errored: {msg}"])


def _py_files(root: Path, dirs) -> list[Path]:
    out = []
    for d in dirs:
        base = root / d
        out += [p for p in base.rglob("*.py") if "__pycache__" not in p.parts] if base.is_dir() else []
    return sorted(out)


def _md_files(root: Path) -> list[Path]:
    base = root / "policy"
    return sorted(base.rglob("*.md")) if base.is_dir() else []


def _policy_bytes(root: Path) -> int:
    return sum(p.stat().st_size for p in _md_files(root))


# ---- static ---------------------------------------------------------------------------------
def static_check(cand: Path, parent: Path | None = None, max_growth: float | None = None,
                 tool_dirs=("tools",)) -> dict:
    """Compiles only tool files and policy files (vendored/template files elsewhere are not the
    edit's business). Policy growth warns unless ``max_growth`` is explicit."""
    bad, warn = [], []
    for p in _py_files(cand, tool_dirs):
        try:
            compile(p.read_text(encoding="utf-8"), str(p), "exec")
        except (SyntaxError, UnicodeDecodeError, ValueError) as e:
            bad.append(f"{p.relative_to(cand)}: {type(e).__name__}: {e}")
    for p in _md_files(cand):
        try:
            p.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            bad.append(f"{p.relative_to(cand)}: {e}")
    if parent is not None and parent.is_dir() and (old := _policy_bytes(parent)):
        growth = _policy_bytes(cand) / old - 1
        cap = MAX_POLICY_GROWTH if max_growth is None else max_growth
        if growth > cap:
            (warn if max_growth is None else bad).append(
                f"policy grew {growth:+.0%} over the parent (cap {cap:+.0%}): "
                "every task pays for those tokens; trim or justify")
    return {**_check("static", not bad, "; ".join(bad)), "warnings": warn}


# ---- hidden writes: call graph ----------------------------------------------------------------
def _fold(node):
    """Constant-fold string expressions ('update_' + 'a', f-strings of constants); None if dynamic."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = _fold(node.left), _fold(node.right)
        return a + b if a is not None and b is not None else None
    if isinstance(node, ast.JoinedStr):
        parts = [_fold(v) for v in node.values]
        return None if None in parts else "".join(parts)
    return None


def _self_rooted(node, mods) -> bool:
    while isinstance(node, ast.Attribute):
        node = node.value
    if isinstance(node, ast.Call):  # type(self).m
        return isinstance(node.func, ast.Name) and node.func.id == "type"
    return isinstance(node, ast.Name) and (node.id in {"self", "cls"} or node.id in mods)


class _Node:
    def __init__(self, key, short, cls, fn, mods):
        self.key, self.short, self.cls = key, short, cls
        deco = " ".join(ast.unparse(d) for d in fn.decorator_list)
        self.decorated_write = "WRITE" in deco
        self.is_tool = "is_tool" in deco
        self.attr_edges, self.name_edges, self.dynamic = set(), set(), False
        for n in ast.walk(fn):
            if isinstance(n, ast.Attribute) and _self_rooted(n, mods):
                self.attr_edges.add(n.attr)
            elif isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
                self.name_edges.add(n.id)
            if isinstance(n, ast.Call):
                f = n.func
                fname = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None
                if fname in _DYNAMIC_CALLS:
                    self.dynamic = True
                elif fname in {"getattr", "methodcaller"}:
                    arg = n.args[1] if fname == "getattr" and len(n.args) >= 2 else \
                        n.args[0] if fname == "methodcaller" and n.args else None
                    name = _fold(arg) if arg is not None else None
                    if name is None:
                        self.dynamic = True
                    else:
                        self.attr_edges.add(name)


class CallGraph:
    def __init__(self, sources: dict[str, str], explicit: set | None = None, known: set = frozenset()):
        self.nodes: dict[str, _Node] = {}
        for rel, src in sources.items():
            tree = ast.parse(src)
            mods = {(a.asname or a.name).split(".")[0] for n in ast.walk(tree)
                    if isinstance(n, ast.Import) for a in n.names}
            for top in tree.body:
                defs = [(None, top)] if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)) else \
                    [(top.name, f) for f in top.body if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))] \
                    if isinstance(top, ast.ClassDef) else []
                for cls, fn in defs:
                    key = f"{rel}:{cls + '.' if cls else ''}{fn.name}"
                    self.nodes[key] = _Node(key, fn.name, cls, fn, mods)
        self.by_short: dict[str, list[str]] = {}
        for k, n in self.nodes.items():
            self.by_short.setdefault(n.short, []).append(k)
        self.explicit, self.known = explicit, set(known)
        self.imported = {a.asname or a.name for src in sources.values() for n in ast.walk(ast.parse(src))
                         if isinstance(n, ast.ImportFrom) for a in n.names}

    def is_write(self, key) -> bool:
        n = self.nodes[key]
        if n.decorated_write:
            return True
        if n.is_tool or n.short.startswith("_"):
            return False
        if self.explicit is not None:
            return n.short in self.explicit
        return n.short in self.known or n.short.startswith(WRITE_PREFIXES)

    def write_names(self) -> set:
        return {self.nodes[k].short for k in self.nodes if self.is_write(k)}

    def _targets(self, node: _Node) -> list[str]:
        out = []
        for name in node.attr_edges:
            ks = self.by_short.get(name, [])
            same = [k for k in ks if self.nodes[k].cls == node.cls and node.cls]
            out += same or ks
        for name in node.name_edges:
            out += [k for k in self.by_short.get(name, []) if self.nodes[k].cls is None]
        return [k for k in dict.fromkeys(out) if k != node.key]

    def reach(self, key: str) -> dict[str, str]:
        """{token: path text}: write tools (and dynamic-name uses) reachable from ``key`` through
        non-write helpers. A write tool reached ends that path."""
        found, seen, stack = {}, {key}, [(key, [self.nodes[key].short])]
        while stack:
            k, path = stack.pop()
            n = self.nodes[k]
            if n.dynamic:
                found.setdefault(f"dynamic@{k.split(':', 1)[-1]}", " -> ".join(path) + " (unresolvable name)")
            for t in self._targets(n):
                if t in seen:
                    continue
                seen.add(t)
                p = path + [self.nodes[t].short]
                if self.is_write(t):
                    found.setdefault(f"write@{t.split(':', 1)[-1]}", " -> ".join(p))
                else:
                    stack.append((t, p))
        return found

    def external_writes(self, key: str, names: set) -> dict[str, str]:
        """Imported bare names used in ``key`` that look like write tools (known/explicit/prefix)."""
        n = self.nodes[key]
        def looks_write(x):
            return x in names or (x in self.explicit if self.explicit is not None
                                  else x.startswith(WRITE_PREFIXES))
        return {f"write@ext:{x}": f"{n.short} -> {x} (imported)"
                for x in sorted(n.name_edges & self.imported) if looks_write(x)}


def hidden_writes(cand_src, parent_src=None, explicit: set | None = None) -> dict:
    """``*_src``: source text or {path: text}. ``parent_src=None`` skips the delta (warning)."""
    as_map = lambda s: s if isinstance(s, dict) else {"tools.py": s}  # noqa: E731
    if parent_src is None:
        return _check("hidden_writes", True, "no parent to diff against", skipped=True,
                      warnings=["hidden_writes skipped: no parent directory"])
    pg = CallGraph(as_map(parent_src), explicit)
    known = pg.write_names()
    pg.known = known
    cg = CallGraph(as_map(cand_src), explicit, known)
    names = cg.write_names() | known
    bad = []
    for k in sorted(cg.nodes):
        if not cg.is_write(k):
            continue
        now = {**cg.reach(k), **cg.external_writes(k, names)}
        old = {**pg.reach(k), **pg.external_writes(k, names)} if k in pg.nodes else {}
        bad += [f"{path}" for tok, path in sorted(now.items()) if tok not in old]
    msg = ""
    if bad:
        msg = ("write tool(s) delegate to other writes or use unresolvable names: "
               + "; ".join(dict.fromkeys(bad)) + ". The grader scores only the agent's visible "
               "calls, so an internal write is invisible to it (DB match 0). Keep one tool per "
               "write, or have the policy tell the agent to call each write itself.")
    return _check("hidden_writes", not bad, msg, warnings=[])


def _sources(root: Path, dirs) -> dict[str, str]:
    return {str(p.relative_to(root)): p.read_text(encoding="utf-8") for p in _py_files(root, dirs)}


def hidden_writes_dirs(cand: Path, parent: Path | None, tool_dirs=("tools",),
                       explicit: set | None = None) -> dict:
    cs = _sources(cand, tool_dirs)
    if not cs:
        return _check("hidden_writes", True, "no tool files", skipped=True)
    if parent is None or not parent.is_dir():
        return hidden_writes(cs, None)
    return hidden_writes(cs, _sources(parent, tool_dirs), explicit)


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
        except Exception as e:  # noqa: BLE001
            out.append(f"err:{type(e).__name__}")
    h = getattr(toolkit, "get_db_hash", None)
    return out, (h() if callable(h) else None)


def replay(make_cand, make_parent, calls: list[dict], mutates=None, changed: set = frozenset()) -> dict:
    """Same recorded calls on a fresh candidate and parent toolkit. Enforced only for tools
    UNCHANGED between them: per-call outcomes, successful write calls and the final DB hash must
    match. Calls to ``changed`` tools are reported as ``info`` (a legitimate fix changes them), and
    when the trace exercises one the state/write-list comparison is info too."""
    mutates = mutates or _cluster()._mutates
    if not calls:
        return _check("replay", True, "no recorded tool calls", skipped=True)
    (co, ch), (po, ph) = _run_calls(make_cand(), calls), _run_calls(make_parent(), calls)
    diffs, info = [], []
    for i, (c, a, b) in enumerate(zip(calls, co, po)):
        if a != b:
            (info if c["name"] in changed else diffs).append(
                f"call {i} {c['name']}: candidate {a}, parent {b}")
    touched = any(c["name"] in changed for c in calls)
    cw = [c["name"] for c, o in zip(calls, co) if o == "ok" and mutates(c["name"])]
    pw = [c["name"] for c, o in zip(calls, po) if o == "ok" and mutates(c["name"])]
    state = []
    if cw != pw:
        state.append(f"successful write calls differ: candidate {cw}, parent {pw}")
    if ch != ph:
        state.append("final DB state differs from the parent's replay")
    (info if touched else diffs).extend(state)
    return _check("replay", not diffs, "; ".join(diffs[:5]), info=info)


def trace_agent_calls(path: Path) -> list[dict]:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    return _cluster().trace_calls(d.get("rollout") or d)


# ---- driver ---------------------------------------------------------------------------------
def _load_factory(spec: str):
    mod, _, fn = spec.rpartition(":") if ":" in spec else (spec, "", "")
    if mod.endswith(".py"):  # a file path, e.g. the adapter: adapters/adapter.py:pregate_toolkit
        s = importlib.util.spec_from_file_location("pregate_toolkit_mod", mod)
        m = importlib.util.module_from_spec(s)
        s.loader.exec_module(m)
    else:
        m = __import__(mod, fromlist=[fn])
    return getattr(m, fn or "make_toolkit")


def changed_tools(cand: Path, parent: Path | None, tool_dirs=("tools",)) -> set[str]:
    """Short names of functions in the tool files that are new or differ from the parent's."""
    def funcs(srcs):
        return {n.name: ast.dump(n) for s in srcs.values() for n in ast.walk(ast.parse(s))
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    new = funcs(_sources(cand, tool_dirs))
    old = funcs(_sources(parent, tool_dirs)) if parent is not None and parent.is_dir() else {}
    return {n for n, d in new.items() if old.get(n) != d}


def _smoke_and_replay(cand, parent, factory_spec, fixtures, traces, tool_dirs, strict):
    if not factory_spec:
        return [_check("tool_smoke", True, "needs pregate.toolkit and tool_fixtures.jsonl", skipped=True),
                _check("replay", True, "needs pregate.toolkit, a parent and traces", skipped=True)]
    changed = changed_tools(cand, parent, tool_dirs)

    def fx_rows():
        if not (fixtures and fixtures.is_file()):
            return []
        return [json.loads(ln) for ln in fixtures.read_text(encoding="utf-8").splitlines() if ln.strip()]

    out = []
    holder = {}

    def factory():
        if "f" not in holder:
            holder["f"] = _load_factory(factory_spec)
        return holder["f"]

    out.append(_guard("tool_smoke", lambda: tool_smoke(factory()(cand), fx_rows(), changed)
                      if fx_rows() else _check("tool_smoke", True, "no tool_fixtures.jsonl rows", skipped=True),
                      strict))
    if parent is not None and traces:
        for t in traces:
            r = _guard("replay", lambda t=t: replay(lambda: factory()(cand), lambda: factory()(parent),
                                                    trace_agent_calls(t), changed=changed), strict)
            if r["detail"]:
                r["detail"] = f"{Path(t).name}: {r['detail']}"
            out.append(r)
    else:
        out.append(_check("replay", True, "needs a parent and traces", skipped=True))
    return out


def run(cand: Path, parent: Path | None = None, *, fixtures: Path | None = None,
        toolkit: str | None = None, traces: list[Path] = (), max_growth: float | None = None,
        strict: bool = False, write_tools=None, tool_dirs=("tools",)) -> dict:
    explicit = set(write_tools) if write_tools else None
    checks = [_guard("static", lambda: static_check(cand, parent, max_growth, tool_dirs), strict)]
    if checks[0]["ok"] or checks[0].get("error"):  # nothing below is meaningful on code that does not compile
        checks.append(_guard("hidden_writes",
                             lambda: hidden_writes_dirs(cand, parent, tool_dirs, explicit), strict))
        checks += _smoke_and_replay(cand, parent, toolkit, fixtures, traces, tool_dirs, strict)
    failed = [c for c in checks if not c["ok"]]
    return {"ok": not failed, "checks": checks,
            "warnings": [w for c in checks for w in c.get("warnings") or []],
            "failure": "; ".join(f"[{c['name']}] {c['detail']}" for c in failed)}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="pregate")
    p.add_argument("--candidate", required=True)
    p.add_argument("--parent")
    p.add_argument("--fixtures", help="tool_fixtures.jsonl (default: <run>/tool_fixtures.jsonl via --run-dir)")
    p.add_argument("--run-dir")
    p.add_argument("--toolkit", help="module_or_file.py:callable(candidate_dir) -> toolkit")
    p.add_argument("--trace", action="append", default=[], help="rollout json to replay (repeatable)")
    p.add_argument("--max-policy-growth", type=float, default=None,
                   help=f"FAIL above this policy growth fraction (default: only warn above "
                        f"{MAX_POLICY_GROWTH:.2f})")
    p.add_argument("--strict", action="store_true", help="infra errors in checks fail instead of warn")
    p.add_argument("--write-tool", action="append", default=[], help="explicit write tool name (repeatable)")
    a = p.parse_args(argv)
    fx = Path(a.fixtures) if a.fixtures else (Path(a.run_dir) / "tool_fixtures.jsonl" if a.run_dir else None)
    res = run(Path(a.candidate), Path(a.parent) if a.parent else None, fixtures=fx,
              toolkit=a.toolkit, traces=[Path(t) for t in a.trace], max_growth=a.max_policy_growth,
              strict=a.strict, write_tools=a.write_tool)
    print(json.dumps(res, indent=2))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
