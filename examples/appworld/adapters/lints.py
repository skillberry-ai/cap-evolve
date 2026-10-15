"""Candidate lints (README: Lints). A violating candidate is rejected before any rollout.

    python lints.py CANDIDATE_DIR      # prints {"ok": bool, "violations": [...]}, exit 1 on violation

The lint data (train ∪ dev instructions and supervisor contacts, app and API names) is built
from ``APPWORLD_ROOT`` (root_opt at search time) on first use and cached next to the run files.
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
from functools import lru_cache
from pathlib import Path

PROMPT_MAX_TOKENS = 8000
NOTE_MAX_CHARS = 400
NOTES_MAX_TOKENS = 20000
HELPERS_MAX_LINES = 400
MEMORY_MAX_CHARS = 30000
NGRAM = 8
TEMPLATE_VARS = {"instruction", "main_user", "app_descriptions"}
REQUIRED_VARS = {"instruction", "main_user"}
HELPER_IMPORTS = {"re", "json", "math", "datetime", "itertools", "collections", "functools"}
BANNED_CALLS = {"open", "exec", "eval", "compile", "__import__", "input", "breakpoint", "globals", "locals", "vars"}


def _root() -> Path:
    return Path(os.environ.get("APPWORLD_ROOT", "/tmp/aw_eval/root_opt"))


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _ngrams(words: list[str], n: int = NGRAM) -> set[tuple[str, ...]]:
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


CACHE = Path(os.environ.get("AW_LINT_CACHE", "/tmp/aw_eval/lint_cache.json"))


@lru_cache(maxsize=1)
def lint_data() -> dict:
    # The cache lets the lint run while root_opt is locked (README: Isolation).
    if CACHE.is_file():
        d = json.loads(CACHE.read_text())
        return {"grams": {tuple(g.split(" ")) for g in d["grams"]}, "contacts": set(d["contacts"]),
                "apps": set(d["apps"]), "api_names": set(d["api_names"])}
    return _build_lint_data()


def write_cache() -> None:
    d = _build_lint_data()
    CACHE.write_text(json.dumps({"grams": sorted(" ".join(g) for g in d["grams"]), "contacts": sorted(d["contacts"]),
                                 "apps": sorted(d["apps"]), "api_names": sorted(d["api_names"])}))


def _build_lint_data() -> dict:
    root = _root() / "data"
    ids: list[str] = []
    for s in ("train", "dev"):
        ids += (root / "datasets" / f"{s}.txt").read_text().split()
    grams: set[tuple[str, ...]] = set()
    contacts: set[str] = set()
    for tid in ids:
        spec = json.loads((root / "tasks" / tid / "specs.json").read_text())
        grams |= _ngrams(_words(spec["instruction"]))
        sup = spec.get("supervisor") or {}
        for k in ("email", "phone_number"):
            if sup.get(k):
                contacts.add(str(sup[k]).lower())
        name = f"{sup.get('first_name', '')} {sup.get('last_name', '')}".strip().lower()
        if name:
            contacts.add(name)
    apps, api_names = set(), set()
    for f in (root / "api_docs" / "standard").glob("*.json"):
        apps.add(f.stem)
        api_names |= set(json.loads(f.read_text()).keys())
    return {"grams": grams, "contacts": contacts, "apps": apps, "api_names": api_names}


def _tokens(text: str) -> int:
    try:
        import tiktoken
        return len(tiktoken.get_encoding("o200k_base").encode(text))
    except Exception:  # noqa: BLE001 — fall back to a conservative estimate
        return len(text) // 3


def _leaks(text: str, what: str) -> list[str]:
    d = lint_data()
    out = []
    hit = _ngrams(_words(text)) & d["grams"]
    if hit:
        out.append(f"{what}: contains {len(hit)} 8-gram(s) from train/dev task instructions, e.g. "
                   f"{' '.join(sorted(hit)[0])!r}")
    low = text.lower()
    names = [c for c in d["contacts"] if c in low]
    if names:
        out.append(f"{what}: contains a train/dev supervisor name, email or phone number ({len(names)} hit(s))")
    return out


def lint_prompt(text: str) -> list[str]:
    out = []
    try:
        from jinja2 import Environment, meta
        used = meta.find_undeclared_variables(Environment().parse(text))
    except Exception as e:  # noqa: BLE001
        return [f"policy/instructions.txt: Jinja template does not parse: {e}"]
    if used - TEMPLATE_VARS:
        out.append(f"policy/instructions.txt: unknown template variables {sorted(used - TEMPLATE_VARS)}; "
                   f"only {sorted(TEMPLATE_VARS)} exist")
    if not REQUIRED_VARS <= used:
        out.append(f"policy/instructions.txt: must use {sorted(REQUIRED_VARS)}")
    if "Task: {{ instruction }}" not in text or "My name is:" not in text:
        out.append("policy/instructions.txt: must end with the 'My name is: … Task: {{ instruction }}' block")
    if not text.lstrip().startswith("USER:") or "ASSISTANT:" not in text:
        out.append("policy/instructions.txt: must keep the USER:/ASSISTANT: message structure")
    n = _tokens(text)
    if n > PROMPT_MAX_TOKENS:
        out.append(f"policy/instructions.txt: {n} tokens > {PROMPT_MAX_TOKENS}")
    return out + _leaks(text, "policy/instructions.txt")


def lint_helpers(src: str) -> list[str]:
    what = "tools/helpers.py"
    out = []
    if len(src.splitlines()) > HELPERS_MAX_LINES:
        out.append(f"{what}: {len(src.splitlines())} lines > {HELPERS_MAX_LINES}")
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return out + [f"{what}: syntax error: {e}"]
    d = lint_data()
    banned_strings = d["apps"] | d["api_names"]
    for i, node in enumerate(tree.body):
        is_doc = i == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
        if not (is_doc or isinstance(node, (ast.FunctionDef, ast.Import, ast.ImportFrom))
                or (isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant))):
            out.append(f"{what}: line {node.lineno}: only imports, constants and function definitions "
                       "may appear at top level (no top-level calls)")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            bad = [a.name for a in node.names if a.name.split(".")[0] not in HELPER_IMPORTS]
            if bad:
                out.append(f"{what}: line {node.lineno}: import of {bad} not allowed (only {sorted(HELPER_IMPORTS)})")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] not in HELPER_IMPORTS:
                out.append(f"{what}: line {node.lineno}: import from {node.module!r} not allowed")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in banned_strings:
                out.append(f"{what}: line {node.lineno}: string literal {node.value!r} is an AppWorld app or "
                           "API name; helpers must take app/API names as parameters")
        elif isinstance(node, ast.Attribute):
            chain = []
            cur = node
            while isinstance(cur, ast.Attribute):
                chain.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name) and cur.id == "apis" and chain and chain[-1] in d["apps"]:
                out.append(f"{what}: line {node.lineno}: hardcoded API call chain apis.{chain[-1]}.…; "
                           "take the app name as a parameter and use getattr(apis, app_name)")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in BANNED_CALLS:
            out.append(f"{what}: line {node.lineno}: call to {node.func.id}() not allowed")
        elif isinstance(node, ast.Name) and node.id in ("__builtins__", "__import__"):
            out.append(f"{what}: line {node.lineno}: use of {node.id} not allowed")
    return list(dict.fromkeys(out + _leaks(src, what)))


def lint_notes(raw: str) -> list[str]:
    what = "tools/api_notes.json"
    try:
        notes = json.loads(raw or "{}")
    except json.JSONDecodeError as e:
        return [f"{what}: invalid JSON: {e}"]
    if not isinstance(notes, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in notes.items()):
        return [f"{what}: must be an object mapping 'app' or 'app.api' to a note string"]
    out = []
    d = lint_data()
    for k, v in notes.items():
        app, _, api = k.partition(".")
        if app not in d["apps"] or (api and api not in d["api_names"]):
            out.append(f"{what}: key {k!r} is not an AppWorld app or app.api")
        if len(v) > NOTE_MAX_CHARS:
            out.append(f"{what}: note {k!r} has {len(v)} chars > {NOTE_MAX_CHARS}")
    n = _tokens(" ".join(notes.values()))
    if n > NOTES_MAX_TOKENS:
        out.append(f"{what}: {n} tokens in total > {NOTES_MAX_TOKENS}")
    return out + _leaks(" \n ".join(notes.values()), what)


def lint_memory(text: str, what: str = "memory") -> list[str]:
    if len(text) > MEMORY_MAX_CHARS:
        return [f"{what}: {len(text)} chars > {MEMORY_MAX_CHARS}"]
    return []


def lint_candidate(cdir: Path) -> list[str]:
    cdir = Path(cdir)
    out = []
    p = cdir / "policy" / "instructions.txt"
    out += lint_prompt(p.read_text(encoding="utf-8")) if p.is_file() else ["policy/instructions.txt: missing"]
    h = cdir / "tools" / "helpers.py"
    if h.is_file():
        out += lint_helpers(h.read_text(encoding="utf-8"))
    n = cdir / "tools" / "api_notes.json"
    if n.is_file():
        out += lint_notes(n.read_text(encoding="utf-8"))
    pb = cdir / "memory" / "playbook.md"
    if pb.is_file():
        out += lint_memory(pb.read_text(encoding="utf-8"), "memory/playbook.md")
    rj = cdir / "memory" / "retrieval.json"
    if rj.is_file():
        for tid, block in json.loads(rj.read_text(encoding="utf-8")).items():
            out += lint_memory(block, f"memory/retrieval.json[{tid}]")
    return out


if __name__ == "__main__":
    if sys.argv[1:] == ["--write-cache"]:
        write_cache()
        raise SystemExit(0)
    v = lint_candidate(Path(sys.argv[1] if len(sys.argv) > 1 else "."))
    print(json.dumps({"ok": not v, "violations": v}, indent=1))
    raise SystemExit(1 if v else 0)
