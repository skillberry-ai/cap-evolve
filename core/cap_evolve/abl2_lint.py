"""A2a (abl2_scope=tools) enforcement: tools-only surface + "policy-in-tool" lint.

A tool may be changed freely (code, docstrings, new/removed/composite tools, schema), but the policy must stay
byte-identical, and the change must not smuggle the policy/procedure into a tool: a tool docstring that is a
rule list, or a function that RETURNS procedure/checklist prose. Findings are compared with the parent: only
NEW findings (kind + qualified name not present in the parent) count.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

DOC_MAX_LINES = 25
RETURN_STR_MAX = 300
_STEP = re.compile(r"^\s*(?:\d+[a-z]?[.)]|[-*•])\s+\S")
_MODAL = re.compile(r"\b(must|never|always|do not|don't|only if|before calling|refuse|should not|cannot)\b", re.I)
_PHRASE = re.compile(r"\byou must\b|\bdo not\b|\bREFUSE\b")
_PHRASE_MIN = 3          # distinct phrase hits (any of the three phrases, counted by occurrence) to flag
_STEPS_MIN = 3


def _step_lines(text: str, require_modal: bool) -> int:
    return sum(1 for ln in text.splitlines()
               if _STEP.match(ln) and (not require_modal or _MODAL.search(ln)))


def _is_tool_decorated(fn) -> bool:
    for d in fn.decorator_list:
        n = d.func if isinstance(d, ast.Call) else d
        if (isinstance(n, ast.Name) and n.id == "is_tool") or (
                isinstance(n, ast.Attribute) and n.attr == "is_tool"):
            return True
    return False


def _functions(tree):
    """Yield (qualname, node, is_tool_method) for every function; tool = is_tool-decorated or a public
    method of a class."""
    def walk(node, prefix, in_class):
        for c in ast.iter_child_nodes(node):
            if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef)):
                q = prefix + c.name
                yield q, c, _is_tool_decorated(c) or (in_class and not c.name.startswith("_"))
                yield from walk(c, q + ".", False)
            elif isinstance(c, ast.ClassDef):
                yield from walk(c, prefix + c.name + ".", True)
            else:
                yield from walk(c, prefix, in_class)
    yield from walk(tree, "", False)


def _fold(x):
    """Constant-fold str literals joined by + / * (so ``"step. " * 50`` cannot dodge the length bound)."""
    if isinstance(x, ast.Constant) and isinstance(x.value, (str, int)) and not isinstance(x.value, bool):
        return x.value
    if isinstance(x, ast.BinOp) and isinstance(x.op, (ast.Add, ast.Mult)):
        a, b = _fold(x.left), _fold(x.right)
        try:
            if isinstance(x.op, ast.Add) and isinstance(a, str) and isinstance(b, str):
                return a + b
            if isinstance(x.op, ast.Mult) and {type(a), type(b)} == {str, int} and 0 <= (a if isinstance(a, int) else b) <= 10000:
                return a * b
        except Exception:  # noqa: BLE001
            return None
    return None


def _strings(node):
    for x in ast.walk(node):
        if isinstance(x, ast.Constant) and isinstance(x.value, str):
            yield x.value
        elif isinstance(x, ast.BinOp):
            v = _fold(x)
            if isinstance(v, str):
                yield v


def _assigns(scope_nodes):
    """name -> list of value nodes assigned to it in the given statement trees."""
    out: dict = {}
    for root in scope_nodes:
        for x in ast.walk(root):
            tg, val = [], None
            if isinstance(x, ast.Assign):
                tg, val = x.targets, x.value
            elif isinstance(x, (ast.AnnAssign, ast.AugAssign)) and x.value is not None:
                tg, val = [x.target], x.value
            for t in tg:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name):
                        out.setdefault(n.id, []).append(val)
    return out


def _prose(s: str) -> str | None:
    if len(s) > RETURN_STR_MAX:
        return f"string of {len(s)} chars"
    if "\n" in s and _step_lines(s, False) >= _STEPS_MIN:
        return "multi-line numbered/bulleted steps"
    return None


def _return_findings(tree) -> list:
    mod_assigns = _assigns([n for n in tree.body if not isinstance(
        n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))])
    out = []
    for q, fn, _ in _functions(tree):
        outs = [x.value for x in ast.walk(fn)
                if isinstance(x, (ast.Return, ast.Yield, ast.YieldFrom)) and x.value is not None]
        if not outs:
            continue
        loc = _assigns(fn.body)
        why = None
        cands = list(outs)
        names = {n.id for o in outs for n in ast.walk(o) if isinstance(n, ast.Name)}
        for nm in names:
            cands += loc.get(nm, []) + (mod_assigns.get(nm, []) if nm not in loc else [])
        for c in cands:
            for s in _strings(c):
                why = _prose(s)
                if why:
                    break
            if why:
                break
        if why:
            out.append(("return_prose", q, why))
    return out


def _doc_findings(tree) -> list:
    out = []
    for q, fn, is_tool in _functions(tree):
        if not is_tool:
            continue
        d = ast.get_docstring(fn, clean=True)
        if not d:
            continue
        n = len(d.strip().splitlines())
        if n > DOC_MAX_LINES:
            out.append(("docstring_long", q, f"docstring has {n} lines (> {DOC_MAX_LINES})"))
        steps = _step_lines(d, True)
        phr = len(_PHRASE.findall(d))
        if steps >= _STEPS_MIN:
            out.append(("docstring_rules", q, f"{steps} numbered/bulleted imperative rule lines"))
        elif phr >= _PHRASE_MIN:
            out.append(("docstring_rules", q, f"{phr} imperative rule phrases (you must / do not / REFUSE)"))
    return out


def _findings(src: str | bytes | None) -> dict:
    """{(kind, qualname): message} for one tools.py source; {} when it does not parse."""
    if src is None:
        return {}
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return {}
    return {(k, q): f"{q}: {m}" for k, q, m in _doc_findings(tree) + _return_findings(tree)}


def policy_in_tool_findings(parent_tools_src, cand_tools_src) -> list[str]:
    """NEW policy-in-tool findings introduced by the candidate (pre-existing parent findings are ignored)."""
    old, new = _findings(parent_tools_src), _findings(cand_tools_src)
    return [f"{k[0]} {msg}" for k, msg in sorted(new.items()) if k not in old]


def all_findings(src) -> list[str]:
    return [f"{k[0]} {m}" for k, m in sorted(_findings(src).items())]


def tools_scope_violation(parent_dir, cand_dir) -> str | None:
    from .abl_surface import POLICY, TOOLS, _bytes, _files
    pf, cf = _files(Path(parent_dir)), _files(Path(cand_dir))
    bad = []
    for rel in sorted(set(pf) | set(cf)):
        if _bytes(pf.get(rel)) == _bytes(cf.get(rel)):
            continue
        if rel.startswith("tools/"):
            continue
        what = "added" if rel not in pf else "removed" if rel not in cf else "changed"
        bad.append(f"{rel} {what}" + (" (tools-only arm)" if rel == POLICY else ""))
    if TOOLS in pf and TOOLS not in cf:
        bad.append(f"{TOOLS} removed")
    elif TOOLS in cf:
        ps = pf[TOOLS].read_bytes() if TOOLS in pf else None
        for f in policy_in_tool_findings(ps, cf[TOOLS].read_bytes()):
            bad.append(f"POLICY-IN-TOOL LINT: {f}")
    return "; ".join(bad) if bad else None


def check(scope: str, parent_dir, cand_dir, run_dir=None):
    """(lint, detail) for an abl2_scope arm, or None. lint is 'surface' or 'overfit'."""
    if scope == "tools":
        v = tools_scope_violation(parent_dir, cand_dir)
        return ("surface", v) if v else None
    if scope == "policy":
        from .abl2_overfit import policy_scope_violation
        return policy_scope_violation(parent_dir, cand_dir, run_dir)
    raise ValueError(f"unknown abl2_scope {scope!r}")
