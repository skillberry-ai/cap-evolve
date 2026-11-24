"""agent-harness capability — concrete handlers for an agent's harness artifact.

The harness is the code and configuration AROUND the model: the agent loop and its
stopping rules, context management, cross-run memory, tool-error handling, sampling,
and sub-agents. Other capabilities own the prompt text (``system-prompt``) and the
tool surface (``tools`` / ``mcp-tool``); this one owns how the loop runs.

Artifact layout (all paths relative to the capability dir)::

    harness.json            declarative settings the adapter wires into the agent
    memory/lessons.jsonl    cross-run lessons, one JSON object per line (optional)
    hooks/*.py              harness code hooks the adapter imports (optional)
    harness_policy.json     optional: which edit kinds and settings are allowed

``harness_policy.json`` is NOT ``policy.json``: ``tools`` reads ``policy.json`` from the
same capability dir, and ``[tools, agent-harness]`` must be able to share one dir.

Edit schema (what an optimizer may emit)::

    {"op": "set",           "path": "context.compaction", "value": "observation_masking"}
    {"op": "unset",         "path": "sampling.n_candidates"}
    {"op": "add_lesson",    "lesson": {"id", "when", "do", "evidence", "source_split"}}
    {"op": "update_lesson", "id": "...", "lesson": {...fields to change...}}
    {"op": "remove_lesson", "id": "..."}
    {"op": "code",          "file": "hooks/compact.py", "text": "..."}

Edit kinds for the policy: ``config`` (set/unset), ``lesson`` (the three lesson ops),
``code`` (hooks). The policy can also list ``wired`` setting paths (glob patterns): a
``set`` on a path the adapter does not read is refused, because a setting nothing
reads changes nothing and only costs a gate evaluation.

Two invariants are checked mechanically, not only documented:

* ``memory.write_during_eval`` must be false. A scored rollout that writes memory makes
  the score depend on task order and lets the agent learn from val/test feedback.
  Memory is written by the optimizer BETWEEN iterations, from train/val traces.
* A lesson may not come from the ``test`` split. Test is sealed and scored once.
"""

from __future__ import annotations

import ast
import fnmatch
import json
import re
from pathlib import Path

HARNESS_FILE = "harness.json"
LESSONS_FILE = "memory/lessons.jsonl"
HOOKS_DIR = "hooks"
POLICY_FILE = "harness_policy.json"

DEFAULT_POLICY = {"allow": ["config", "lesson", "code"], "wired": ["*"]}

_OP_KIND = {"set": "config", "unset": "config", "add_lesson": "lesson",
            "update_lesson": "lesson", "remove_lesson": "lesson", "code": "code"}

# Known settings: path -> (type, constraint). Constraint is (lo, hi) for numbers or a
# tuple of allowed strings. Unknown paths outside ``custom.*`` get a warning, not a
# failure: an agent may have knobs this list does not name, but an unknown key is also
# the most common way to write a setting that nothing reads.
_NUM = (int, float)
SCHEMA: dict[str, tuple] = {
    # agent loop and stopping
    "loop.max_steps": (int, (1, 10_000)),
    "loop.max_tool_calls": (int, (1, 100_000)),
    "loop.repeat_limit": (int, (0, 100)),          # same call N times in a row -> nudge/stop
    "loop.on_repeat": (str, ("nudge", "stop", "ignore")),
    "loop.plan_tool": (bool, None),                # explicit todo/plan tool
    "loop.think_tool": (bool, None),               # no-op "think" scratch tool
    "loop.final_check": (str, ("none", "self_verify", "checklist", "run_tests")),
    "loop.no_action_nudge": (bool, None),          # re-prompt when the agent ends without acting
    # context management
    "context.max_tokens": (int, (1, 10_000_000)),
    "context.compaction": (str, ("none", "observation_masking", "summarize", "hybrid")),
    "context.compact_at_fraction": (_NUM, (0.05, 1.0)),
    "context.keep_last_turns": (int, (0, 10_000)),
    "context.tool_output_max_chars": (int, (0, 10_000_000)),
    "context.keep_errors": (bool, None),
    "context.recitation": (str, ("none", "todo", "goal")),
    "context.stable_prefix": (bool, None),         # keep the prompt prefix byte-stable (cache)
    # cross-run memory
    "memory.mode": (str, ("off", "all", "retrieved")),
    "memory.path": (str, None),
    "memory.top_k": (int, (0, 1_000)),
    "memory.max_entries": (int, (0, 100_000)),
    "memory.max_entry_chars": (int, (1, 100_000)),
    "memory.inject_at": (str, ("system", "first_user")),
    "memory.write_during_eval": (bool, None),
    # tool-call error handling
    "tool_errors.max_retries": (int, (0, 10)),
    "tool_errors.backoff_seconds": (_NUM, (0, 600)),
    "tool_errors.validate_args": (bool, None),
    "tool_errors.feed_error_back": (bool, None),
    "tool_errors.retry_on": (list, None),
    # sampling / test-time compute
    "sampling.temperature": (_NUM, (0.0, 2.0)),
    "sampling.n_candidates": (int, (1, 64)),
    "sampling.selector": (str, ("first", "verifier", "majority")),
    # sub-agents
    "subagents.enabled": (bool, None),
    "subagents.max_parallel": (int, (1, 64)),
    "subagents.context": (str, ("full", "summary", "task_only")),
}

LESSON_FIELDS = ("id", "when", "do", "evidence", "source_split")
LESSON_SPLITS = ("train", "val")
DEFAULT_MAX_ENTRY_CHARS = 600

# A long run of digits or an upper-case/digit code looks like a record id, a date or a
# gold value copied from one task. Advisory: it flags a lesson to re-read, not reject.
_LITERAL = re.compile(r"\b(?=[A-Z0-9-]*\d)[A-Z0-9-]{6,}\b|\b\d{5,}\b")
_STUB_BODY = (ast.Pass, ast.Expr)


# ---------------------------------------------------------------------------- io

def _read_json(path: Path, default):
    if not path.exists():
        return default
    text = path.read_text(encoding="utf-8")
    return json.loads(text) if text.strip() else default


def load_policy(capability_dir: Path) -> dict:
    """``harness_policy.json`` in the capability dir if present, else the default."""
    pol = dict(DEFAULT_POLICY)
    pol.update(_read_json(Path(capability_dir) / POLICY_FILE, {}))
    return pol


def load_config(capability_dir: Path) -> dict:
    return _read_json(Path(capability_dir) / HARNESS_FILE, {})


def _safe_rel(rel: str) -> bool:
    p = Path(rel)
    return bool(rel) and not p.is_absolute() and ".." not in p.parts


def _lessons_path(capability_dir: Path, cfg: dict | None = None) -> Path:
    if cfg is None:
        try:
            cfg = load_config(capability_dir)
        except json.JSONDecodeError:
            cfg = {}
    mem = cfg.get("memory") if isinstance(cfg, dict) else None
    rel = (mem or {}).get("path") if isinstance(mem, dict) else None
    if not isinstance(rel, str) or not _safe_rel(rel):
        rel = LESSONS_FILE  # validate() reports an unsafe path; never read outside the dir
    return Path(capability_dir) / rel


def load_lessons(capability_dir: Path, cfg: dict | None = None) -> list[dict]:
    """Every lesson line as a dict. A line that is not JSON raises ``ValueError``."""
    p = _lessons_path(capability_dir, cfg)
    if not p.exists():
        return []
    out = []
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"{p.name} line {i}: not JSON ({e.msg})") from None
    return out


def _save_lessons(capability_dir: Path, lessons: list[dict], cfg: dict | None = None) -> None:
    p = _lessons_path(capability_dir, cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lessons),
                 encoding="utf-8")


def _hook_files(capability_dir: Path) -> list[Path]:
    d = Path(capability_dir) / HOOKS_DIR
    return sorted(d.rglob("*.py")) if d.is_dir() else []


# ------------------------------------------------------------------ dotted paths

def get_path(cfg: dict, path: str, default=None):
    cur = cfg
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def _set_path(cfg: dict, path: str, value) -> None:
    parts = path.split(".")
    cur = cfg
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = cur[part] = {}
        cur = nxt
    cur[parts[-1]] = value


def _unset_path(cfg: dict, path: str) -> bool:
    parts = path.split(".")
    cur = cfg
    for part in parts[:-1]:
        cur = cur.get(part)
        if not isinstance(cur, dict):
            return False
    return cur.pop(parts[-1], _MISSING) is not _MISSING


_MISSING = object()


def _leaves(cfg: dict, prefix: str = ""):
    for k, v in cfg.items():
        p = f"{prefix}{k}"
        if isinstance(v, dict):
            yield from _leaves(v, p + ".")  # an empty section is no setting
        else:
            yield p, v


def _check_value(path: str, value) -> str | None:
    """Type/range problem for a known setting, or None."""
    spec = SCHEMA.get(path)
    if spec is None:
        return None
    typ, cons = spec
    if typ is int and (isinstance(value, bool) or not isinstance(value, int)):
        return f"{path}: expected an integer, got {value!r}"
    if typ is _NUM and (isinstance(value, bool) or not isinstance(value, _NUM)):
        return f"{path}: expected a number, got {value!r}"
    if typ in (bool, str, list) and not isinstance(value, typ):
        return f"{path}: expected {typ.__name__}, got {value!r}"
    if isinstance(cons, tuple) and len(cons) == 2 and all(isinstance(c, _NUM) for c in cons):
        lo, hi = cons
        if not lo <= value <= hi:
            return f"{path}: {value!r} is outside [{lo}, {hi}]"
    elif isinstance(cons, tuple) and value not in cons:
        return f"{path}: {value!r} is not one of {list(cons)}"
    return None


def _wired(policy: dict, path: str) -> bool:
    return any(fnmatch.fnmatchcase(path, pat) for pat in policy.get("wired", ["*"]))


# --------------------------------------------------------------------- handlers

def materialize(capability_dir: Path) -> dict:
    """The harness artifact as named text components (a text optimizer's view)."""
    d = Path(capability_dir)
    parts = {}
    if (d / HARNESS_FILE).exists():
        parts[HARNESS_FILE] = (d / HARNESS_FILE).read_text(encoding="utf-8")
    lp = _lessons_path(d)
    if lp.exists():
        parts[lp.relative_to(d).as_posix()] = lp.read_text(encoding="utf-8")
    for f in _hook_files(d):
        parts[f.relative_to(d).as_posix()] = f.read_text(encoding="utf-8")
    return parts


def is_empty(capability_dir: Path) -> bool:
    """True when there is no setting, no lesson and no hook yet (an empty seed)."""
    return not any("".join(v.split()) not in ("", "{}")
                   for v in materialize(Path(capability_dir)).values())


def apply(capability_dir: Path, edits: list[dict] | None = None) -> dict:
    """Apply edits under the policy. Returns ``{changed, refused, warnings}``.

    A refused edit is reported, never silently dropped, so an over-tight policy shows
    up as visible refusals. Type/range errors on a known setting are refused too: an
    out-of-range value would only fail later in ``validate`` after the edit was written.
    """
    d = Path(capability_dir)
    policy = load_policy(d)
    allow = set(policy.get("allow", []))
    report: dict = {"changed": [], "refused": [], "warnings": []}
    cfg = load_config(d)
    cfg_dirty = False
    lessons = None

    def refuse(e, why):
        report["refused"].append({"edit": e, "reason": why})

    for e in edits or []:
        op = e.get("op")
        kind = _OP_KIND.get(op)
        if kind is None:
            raise ValueError(f"unknown op {op!r}")
        if kind not in allow:
            refuse(e, f"edit kind {kind!r} is not allowed by {POLICY_FILE}")
            continue
        if kind == "config":
            path = str(e.get("path", "")).strip(".")
            if not path:
                refuse(e, "missing 'path'")
                continue
            if not _wired(policy, path):
                refuse(e, f"{path} is not in the policy's 'wired' list: the adapter does "
                          "not read it, so the edit would change nothing")
                continue
            if op == "set":
                bad = _check_value(path, e.get("value"))
                if bad:
                    refuse(e, bad)
                    continue
                if path not in SCHEMA and not path.startswith("custom."):
                    report["warnings"].append(
                        f"{path}: not a known harness setting; confirm the adapter reads it")
                _set_path(cfg, path, e.get("value"))
                cfg_dirty = True
                report["changed"].append(f"set:{path}")
            elif _unset_path(cfg, path):
                cfg_dirty = True
                report["changed"].append(f"unset:{path}")
        elif kind == "lesson":
            if lessons is None:
                lessons = load_lessons(d, cfg)
            if op == "add_lesson":
                les = dict(e.get("lesson") or {})
                missing = [f for f in LESSON_FIELDS if not str(les.get(f, "")).strip()]
                if missing:
                    refuse(e, f"lesson is missing {missing}")
                    continue
                if les["source_split"] not in LESSON_SPLITS:
                    refuse(e, f"source_split {les['source_split']!r}: lessons may come only "
                              f"from {list(LESSON_SPLITS)} traces (test is sealed)")
                    continue
                if any(x.get("id") == les["id"] for x in lessons):
                    refuse(e, f"lesson id {les['id']!r} already exists; use update_lesson")
                    continue
                lessons.append(les)
                report["changed"].append(f"add_lesson:{les['id']}")
            else:
                idx = next((i for i, x in enumerate(lessons) if x.get("id") == e.get("id")), None)
                if idx is None:
                    refuse(e, f"no lesson with id {e.get('id')!r}")
                    continue
                if op == "remove_lesson":
                    lessons.pop(idx)
                else:
                    upd = dict(e.get("lesson") or {})
                    if "source_split" in upd and upd["source_split"] not in LESSON_SPLITS:
                        refuse(e, f"source_split {upd['source_split']!r} is not allowed")
                        continue
                    lessons[idx] = {**lessons[idx], **upd, "id": lessons[idx]["id"]}
                report["changed"].append(f"{op}:{e.get('id')}")
        else:  # code
            rel = Path(str(e.get("file", "")))
            if rel.is_absolute() or ".." in rel.parts or rel.parts[:1] != (HOOKS_DIR,) \
                    or rel.suffix != ".py":
                refuse(e, f"code edits must target {HOOKS_DIR}/<name>.py, got {str(rel)!r}")
                continue
            text = e.get("text", "")
            problem = _hook_problem(rel.as_posix(), text)
            if problem:
                refuse(e, problem)
                continue
            target = d / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            report["changed"].append(f"code:{rel.as_posix()}")

    if cfg_dirty:
        (d / HARNESS_FILE).write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    if lessons is not None and any(c.split(":")[0].endswith("_lesson")
                                   for c in report["changed"]):
        _save_lessons(d, lessons, cfg)
    return report


def _hook_problem(name: str, text: str) -> str | None:
    """A hook must parse and every function must have a real body."""
    try:
        tree = ast.parse(text, filename=name)
    except SyntaxError as e:
        return f"{name}: does not parse ({e.msg}, line {e.lineno})"
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if all(isinstance(s, _STUB_BODY) and (
                    isinstance(s, ast.Pass) or isinstance(getattr(s, "value", None), ast.Constant))
                   for s in body):
                return (f"{name}: function {node.name!r} has no real body (only pass, '...' "
                        "or a docstring); write the code, or remove the hook")
    return None


def cost_factor(cfg: dict) -> float:
    """Rough multiplier on model calls per task that the settings imply.

    Best-of-N samples N full trajectories; a model-based final check adds about one
    more pass. Only the ratio between two candidates is meaningful.
    """
    n = get_path(cfg, "sampling.n_candidates", 1)
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        n = 1  # validate() reports the bad value; the factor must not crash on it
    sel = get_path(cfg, "sampling.selector", "first")
    check = get_path(cfg, "loop.final_check", "none")
    f = float(n)
    if n > 1 and sel == "verifier":
        f += 1.0
    if check in ("self_verify", "checklist"):
        f *= 1.25
    return round(f, 2)


def validate(capability_dir: Path, baseline: Path | None = None) -> dict:
    """Check the harness artifact. Returns ``{ok, empty?, stats, problems, warnings}``.

    An empty directory is a valid empty seed. ``baseline`` (e.g. the parent candidate's
    dir) adds warnings when the implied cost per task grows or when memory grows past
    its own budget, so cost growth is visible at the gate and not only on the bill.
    """
    d = Path(capability_dir)
    if is_empty(d):
        return {"ok": True, "empty": True, "stats": {}, "problems": [], "warnings": []}
    problems: list[str] = []
    warnings: list[str] = []
    policy = load_policy(d)

    try:
        cfg = load_config(d)
    except json.JSONDecodeError as e:
        return {"ok": False, "stats": {}, "problems": [f"{HARNESS_FILE}: not JSON ({e.msg})"],
                "warnings": []}
    if not isinstance(cfg, dict):
        return {"ok": False, "stats": {}, "problems": [f"{HARNESS_FILE}: must be an object"],
                "warnings": []}

    for path, value in _leaves(cfg):
        bad = _check_value(path, value)
        if bad:
            problems.append(bad)
        elif path not in SCHEMA and not path.startswith("custom."):
            warnings.append(f"{path}: not a known harness setting; confirm the adapter reads "
                            "it, or move it under 'custom.'")
        if not _wired(policy, path):
            warnings.append(f"{path}: set, but not in the policy's 'wired' list")

    mpath = get_path(cfg, "memory.path")
    if isinstance(mpath, str) and not _safe_rel(mpath):
        problems.append(f"memory.path {mpath!r} must be a relative path inside the "
                        "capability dir, so the memory is part of the candidate")
    if get_path(cfg, "memory.write_during_eval", False):
        problems.append("memory.write_during_eval is true: a scored rollout must not write "
                        "memory (scores would depend on task order and the agent would learn "
                        "from val/test feedback). The optimizer writes lessons between "
                        "iterations instead.")

    # memory
    try:
        lessons = load_lessons(d, cfg)
    except ValueError as e:
        lessons = []
        problems.append(str(e))
    mode = get_path(cfg, "memory.mode", "off")
    max_entries = get_path(cfg, "memory.max_entries")
    max_chars = get_path(cfg, "memory.max_entry_chars", DEFAULT_MAX_ENTRY_CHARS)
    seen_ids, seen_do = set(), {}
    for les in lessons:
        lid = les.get("id", "?")
        missing = [f for f in LESSON_FIELDS if not str(les.get(f, "")).strip()]
        if missing:
            problems.append(f"lesson {lid!r}: missing {missing}")
        if les.get("source_split") == "test":
            problems.append(f"lesson {lid!r}: comes from the sealed test split")
        elif les.get("source_split") and les["source_split"] not in LESSON_SPLITS:
            problems.append(f"lesson {lid!r}: unknown source_split {les['source_split']!r}")
        if lid in seen_ids:
            problems.append(f"lesson id {lid!r} is duplicated")
        seen_ids.add(lid)
        body = f"{les.get('when', '')} {les.get('do', '')}"
        if len(body) > max_chars:
            warnings.append(f"lesson {lid!r}: {len(body)} chars (> {max_chars}); split it or "
                            "shorten it")
        key = " ".join(str(les.get("do", "")).lower().split())
        if key and key in seen_do:
            warnings.append(f"lesson {lid!r} repeats lesson {seen_do[key]!r}; merge them")
        seen_do.setdefault(key, lid)
        if _LITERAL.search(body):
            warnings.append(f"lesson {lid!r}: contains a literal that looks like a task id or "
                            "value; a lesson must state the general rule")
    if isinstance(max_entries, int) and len(lessons) > max_entries:
        problems.append(f"{len(lessons)} lessons exceed memory.max_entries={max_entries}; "
                        "prune or merge before adding more")
    if lessons and mode == "off":
        warnings.append("lessons exist but memory.mode is 'off' (the default): the agent "
                        "never reads them; set memory.mode to 'all' or 'retrieved'")

    # hooks
    hooks = _hook_files(d)
    for f in hooks:
        pr = _hook_problem(f.relative_to(d).as_posix(), f.read_text(encoding="utf-8"))
        if pr:
            problems.append(pr)

    mem_chars = sum(len(json.dumps(x, ensure_ascii=False)) for x in lessons)
    stats = {"settings": sum(1 for _ in _leaves(cfg)), "lessons": len(lessons),
             "memory_tokens": mem_chars // 4, "hooks": [f.relative_to(d).as_posix() for f in hooks],
             "cost_factor": cost_factor(cfg)}

    if baseline is not None:
        bd = Path(baseline)
        try:
            bcfg = load_config(bd)
        except json.JSONDecodeError:
            bcfg = {}
        bf = cost_factor(bcfg)
        if stats["cost_factor"] > bf:
            warnings.append(f"cost_factor grew {bf} -> {stats['cost_factor']}: model calls per "
                            "task go up; report the cost next to the reward gain")
        try:
            bles = load_lessons(bd)
        except ValueError:
            bles = []
        stats["lessons_delta"] = len(lessons) - len(bles)

    return {"ok": not problems, "stats": stats, "problems": problems, "warnings": warnings}
