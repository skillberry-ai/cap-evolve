"""Edit-surface enforcement for the abl_capability arms (P / TD / TC)."""
from __future__ import annotations

import ast
from pathlib import Path

POLICY = "policy/policy.md"
TOOLS = "tools/tools.py"
_EXTRA_IGNORE = ("PROCESS.md", "__pycache__", ".git", ".pytest_cache")


def _ignored(rel: Path) -> bool:
    from .harness import _SNAPSHOT_IGNORE
    # Root-level files (INSTRUCTIONS.md, DIAGNOSIS.json, PROCESS.md, ...) are harness/proposer scratch: the
    # adapter reads only policy/, tools/ and reference/, so they cannot change the agent under test.
    return len(rel.parts) == 1 or rel.parts[0] in _SNAPSHOT_IGNORE or any(
        p in _EXTRA_IGNORE or p.endswith(".pyc") for p in rel.parts)


def _files(root: Path) -> dict:
    out = {}
    if not root.is_dir():
        return out
    for p in sorted(root.rglob("*")):
        if p.is_file() or p.is_symlink():
            rel = p.relative_to(root)
            if not _ignored(rel):
                out[rel.as_posix()] = p
    return out


def _bytes(p):
    return p.read_bytes() if p is not None else None


def _parse(path):
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, ValueError, UnicodeDecodeError):
        return None


_DOC_NODES = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _has_doc(n):
    b = getattr(n, "body", None)
    return bool(b) and isinstance(b[0], ast.Expr) and isinstance(
        b[0].value, ast.Constant) and isinstance(b[0].value.value, str)


def _strip_docs(tree):
    for n in ast.walk(tree):
        if isinstance(n, _DOC_NODES) and _has_doc(n):
            n.body = n.body[1:] or [ast.Pass()]
    return tree


def _docstrings(tree) -> dict:
    out = {}

    def walk(node, prefix):
        for c in ast.iter_child_nodes(node):
            if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                q = prefix + c.name
                out[q] = ast.get_docstring(c, clean=False)
                walk(c, q + ".")
            else:
                walk(c, prefix)
    walk(tree, "")
    return out


def surface_violation(arm: str, parent_dir, cand_dir) -> str | None:
    if arm not in ("P", "TD", "TC"):
        raise ValueError(f"unknown abl_capability arm {arm!r}")
    pf, cf = _files(Path(parent_dir)), _files(Path(cand_dir))
    bad = []
    for rel in sorted(set(pf) | set(cf)):
        if rel in (POLICY, TOOLS) or _bytes(pf.get(rel)) == _bytes(cf.get(rel)):
            continue
        if arm == "TC" and rel.startswith("tools/") and rel != TOOLS:
            continue  # TC may add/modify files under tools/
        what = "added" if rel not in pf else "removed" if rel not in cf else "changed"
        bad.append(f"{rel} {what}")
    if arm == "P":
        if _bytes(pf.get(TOOLS)) != _bytes(cf.get(TOOLS)):
            bad.append(f"{TOOLS} changed (policy-only arm)")
    else:
        if _bytes(pf.get(POLICY)) != _bytes(cf.get(POLICY)):
            bad.append(f"{POLICY} changed (tools-only arm)")
        pt = _parse(pf[TOOLS]) if TOOLS in pf else None
        ct = _parse(cf[TOOLS]) if TOOLS in cf else None
        if TOOLS in pf and TOOLS not in cf:
            bad.append(f"{TOOLS} removed")
        elif pt is not None and ct is not None:  # syntax errors: stock validation handles
            if arm == "TD":
                a = ast.dump(_strip_docs(pt))
                b = ast.dump(_strip_docs(ct))
                if a != b:
                    bad.append(f"{TOOLS} code changed (docstring-only arm)")
            else:
                pd, cd = _docstrings(pt), _docstrings(ct)
                for q, d in pd.items():
                    if q in cd and cd[q] != d:
                        bad.append(f"{TOOLS} docstring of pre-existing {q} changed")
    return "; ".join(bad) if bad else None
