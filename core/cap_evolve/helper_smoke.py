"""``helper_smoke``: run a candidate's NEW or CHANGED helper files before any rollout is charged.

For each such file (``helpers.executable_files``) a subprocess, with no network, no process
spawning, gold/evaluator paths unreadable and every write refused (see ``_helper_smoke_runner``):

1. imports it. A skill script (``skills/<skill>/scripts/*.py``) is imported the way the target gets it
   (``helpers.skills_loader: kernel``, the default): the candidate's whole skills tree goes through
   ``helpers.kernel_bootstrap``, so ``skills.<skill>.<script>`` is defined from text, in file-name order,
   with no file on disk. A helper whose sibling import only works from a real file is refused here,
   instead of failing every rollout. Any other helper file (and ``skills_loader: file``) is imported from
   its file;
2. for each fixture row that targets it, runs it TWICE (different ``PYTHONHASHSEED``, fresh
   identical workspaces) and requires: no exception, identical stdout/return value/output bytes,
   and writes only to the row's declared ``outputs``.

Fixtures are rows built from RECORDED traces (inputs the target actually passed), never from gold::

    {"helper": "skills/fmt/scripts/norm.py",       # path under the candidate
     "kind": "cli" | "call",                        # default cli (run as __main__)
     "argv": ["{ws}/in.json"], "stdin": null,       # cli; "{ws}" is the fixture workspace
     "call": "normalise", "args": [], "kwargs": {}, # call (dotted attribute of the module)
     "files": {"in.json": "text" | {"src": "/abs/copy/of/a/trace/input"} | {"b64": "..."}},
     "outputs": ["out.json", "results/"]}           # a trailing "/" declares a directory

``fixtures_from_traces`` reads rows from the ``helper_fixtures`` list of rollout JSON files. A file
with no row still gets the import check. A failure leaves the node ``proposed`` with the text below
and costs 0 rollouts.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import helpers

RESULT_TAG = "@@HELPER_SMOKE_RESULT@@"
_RUNNER = Path(__file__).with_name("_helper_smoke_runner.py")
_SEEDS = ("1", "2")


def load_fixtures(path: Path | None = None, traces=()) -> list[dict]:
    rows: list[dict] = []
    if path and Path(path).is_file():
        rows += [json.loads(ln) for ln in Path(path).read_text(encoding="utf-8").splitlines() if ln.strip()]
    rows += fixtures_from_traces(traces)
    return rows


#: At most this many distinct recorded calls become fixtures for one helper function.
MAX_ROWS_PER_CALL = 3


def fixture_traces(rollouts_dir: Path, tag: str, splits=("feedback", "train")) -> list[Path]:
    """Rollout JSON files of candidate ``tag`` in the feedback splits ONLY. The hidden confirm stratum, test,
    val and pool are refused here as well as in ``helpers.resolve``: a fixture is the proposer's own evidence."""
    bad = set(splits) & helpers.FIXTURE_SPLITS_FORBIDDEN
    if bad:
        raise ValueError(f"fixtures never come from {sorted(bad)}")
    out: set[Path] = set()
    for sp in splits:
        d = Path(rollouts_dir) / sp
        # ``<task>__<tag>__t<n>.json`` (the hill-climb and baseline evaluations), and the P2 evaluator's
        # ``<task>__<round>__<tag>__<stage>_<i>__t<n>.json`` (HC-2 rungs, incumbent draws, champion top-ups).
        # ``__`` delimits the tag on both sides, so ``cand_0001`` never matches ``cand_00012``.
        out.update(d.glob(f"*__{tag}__t*.json"))
        out.update(d.glob(f"*__{tag}__*__t*.json"))
    return sorted(out)


def fixtures_from_traces(traces) -> list[dict]:
    """Rows from rollout JSON: explicit ``helper_fixtures`` (top level or under ``metadata``), and the
    ``metadata.helper_calls`` the SpreadsheetBench kernel records (inputs of top-level helper calls that
    returned; converted to ``call`` rows, deduplicated, ``MAX_ROWS_PER_CALL`` per function)."""
    rows: list[dict] = []
    seen: dict[tuple, int] = {}
    for t in traces or []:
        try:
            d = json.loads(Path(t).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        d = d if isinstance(d, dict) else {}
        md = d.get("metadata") or {}
        for r in (d.get("helper_fixtures") or md.get("helper_fixtures") or []):
            if isinstance(r, dict) and r.get("helper"):
                rows.append(r)
        for c in md.get("helper_calls") or []:
            if not (isinstance(c, dict) and c.get("helper") and c.get("call")):
                continue
            fn = str(c["call"]).split(".<locals>.")[-1]
            key = (c["helper"], fn)
            body = json.dumps([c.get("args"), c.get("kwargs")], sort_keys=True)
            if seen.get((*key, body)) or sum(1 for k in seen if k[:2] == key) >= MAX_ROWS_PER_CALL:
                continue
            seen[(*key, body)] = 1
            rows.append({"helper": c["helper"], "kind": "call", "call": fn, "args": c.get("args") or [],
                         "kwargs": c.get("kwargs") or {}, "outputs": [],
                         "id": f"{d.get('task_id', 'rollout')}:{fn}"})
    return rows


def _materialize(ws: Path, row: dict, cfg: dict) -> None:
    import re
    prot = [re.compile(p) for p in (cfg.get("protected_patterns") or helpers.DEFAULT_PROTECTED)]
    for rel, spec in (row.get("files") or {}).items():
        dest = ws / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(spec, str):
            dest.write_text(spec, encoding="utf-8")
        elif isinstance(spec, dict) and "b64" in spec:
            dest.write_bytes(base64.b64decode(spec["b64"]))
        elif isinstance(spec, dict) and "src" in spec:
            src = str(Path(spec["src"]).resolve())
            if any(p.search(src) for p in prot) or any(src.startswith(str(Path(r).resolve())) for r in cfg["deny_roots"]):
                raise ValueError(f"fixture file {rel!r} is sourced from a protected (gold/evaluator) path")
            shutil.copyfile(src, dest)
        else:
            raise ValueError(f"fixture file {rel!r}: expected text, {{'src': path}} or {{'b64': data}}")


def _run_once(root: Path, script: Path, row: dict | None, cfg: dict, seed: str, mode: str, *,
              bootstrap: str | None = None, module: str | None = None) -> dict:
    """One runner subprocess. With ``bootstrap`` (kernel loader) the runner execs that source instead of
    importing ``script`` from its file, and a ``call`` row calls ``module`` (``skills.<skill>.<script>``)."""
    tmp = Path(tempfile.mkdtemp(prefix="capevolve_helper_smoke_"))
    try:
        ws, rt = tmp / "ws", tmp / "rt"
        (ws / ".scratch").mkdir(parents=True)
        rt.mkdir()
        shutil.copyfile(_RUNNER, rt / "runner.py")
        if row:
            _materialize(ws, row, cfg)
        spec = {
            "mode": mode, "script": str(script), "script_dir": str(root),
            "workspace": str(ws), "outputs": (row or {}).get("outputs") or [],
            "deny_patterns": cfg.get("protected_patterns") or helpers.DEFAULT_PROTECTED,
            "deny_roots": cfg["deny_roots"],
            "argv": [str(a).replace("{ws}", str(ws)) for a in (row or {}).get("argv") or []],
            "stdin": (row or {}).get("stdin"), "call": (row or {}).get("call"),
            "args": (row or {}).get("args") or [], "kwargs": (row or {}).get("kwargs") or {},
            "loader": "kernel" if bootstrap is not None else "file", "bootstrap": bootstrap, "module": module,
        }
        (rt / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONHASHSEED": seed,
               "PYTHONDONTWRITEBYTECODE": "1", "HOME": str(ws), "TMPDIR": str(ws / ".scratch"),
               "LANG": "C.UTF-8", "TZ": "UTC"}
        try:
            p = subprocess.run([sys.executable, "-s", str(rt / "runner.py"), str(rt / "spec.json")],
                               cwd=str(ws), env=env, capture_output=True, text=True,
                               timeout=float(cfg["smoke_timeout"]))
        except subprocess.TimeoutExpired:
            return {"ok": False, "exception": f"timed out after {cfg['smoke_timeout']}s", "violations": []}
        line = next((ln for ln in reversed(p.stdout.splitlines()) if ln.startswith(RESULT_TAG)), None)
        if line is None:
            return {"ok": False, "exception": f"smoke subprocess died (rc={p.returncode}): "
                                              f"{(p.stderr or p.stdout)[-300:]}", "violations": []}
        res = json.loads(line[len(RESULT_TAG):])
        res["stdout"] = res.get("stdout", "").replace(str(ws), "<ws>")
        undeclared = sorted(set(res.get("outputs") or {}) - _declared(ws, spec["outputs"], res))
        if undeclared:
            res["ok"] = False
            res.setdefault("violations", []).append(f"wrote undeclared file(s): {undeclared[:3]}")
        res["outputs"] = {k: v for k, v in (res.get("outputs") or {}).items()}
        return res
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _declared(ws: Path, outputs, res) -> set:
    ok = set()
    for k in res.get("outputs") or {}:
        for o in outputs:
            if k == o.rstrip("/") or (o.endswith("/") and k.startswith(o)):
                ok.add(k)
    return ok


KERNEL_IMPORT_LABEL = "skills import (as the target loads them: skills.<skill>.<script>, from text, in file-name order)"


def _skill_module(cand: Path, f: Path) -> str | None:
    """``skills.<skill>.<script>`` when ``f`` is one of the files ``kernel_bootstrap`` loads, else None."""
    rel = f.relative_to(cand).parts
    if len(rel) == 4 and rel[0] == "skills" and rel[2] == "scripts" and f.suffix == ".py":
        return f"skills.{helpers._ident(rel[1])}.{helpers._ident(f.stem)}"
    return None


def _removed_skill_scripts(cand: Path, parent: Path | None) -> list[str]:
    """Skill scripts the parent has and the candidate does not: the tree the target loads changed even
    when no remaining file did."""
    if parent is None or not Path(parent).is_dir():
        return []
    return sorted(f.relative_to(parent).as_posix() for f in Path(parent).glob("skills/*/scripts/*.py")
                  if not (cand / f.relative_to(parent)).exists())


def _why(label: str, r: dict) -> str:
    bits = list(r.get("violations") or [])
    if r.get("exception"):
        bits.append(r["exception"])
    return f"{label}: " + "; ".join(bits)[:300]


def run_smoke(cand: Path, cfg: dict, *, parent: Path | None = None, fixtures: list[dict] | None = None) -> dict:
    """``{name, ok, detail, skipped, files, runs}`` for the pregate. Not enabled / nothing to run => skipped."""
    cand = Path(cand).resolve()
    files = helpers.changed_files(cand, parent, helpers.executable_files(cand, cfg))
    kernel = cfg.get("skills_loader", "kernel") == "kernel"
    removed = _removed_skill_scripts(cand, parent) if kernel else []
    if not files and not removed:
        return {"name": "helper_smoke", "ok": True, "detail": "no new or changed helper files",
                "skipped": True, "files": [], "runs": 0}
    rows = fixtures or []
    problems: list[str] = []
    runs = 0
    boot: dict = {}            # the one whole-tree import: {"src", "ok"} once it ran

    def kernel_import(f: Path) -> bool:
        nonlocal runs
        if not boot:
            try:
                boot["src"] = helpers.kernel_bootstrap(cand / "skills")   # the target's own call: same limit
            except ValueError as e:      # oversize tree, or two files that import as one module
                boot.update(src=None, ok=False)
                problems.append(f"{KERNEL_IMPORT_LABEL}: {e}"[:300])
                return False
            r = _run_once(cand, f, None, cfg, _SEEDS[0], "import", bootstrap=boot["src"])
            runs += 1
            boot["ok"] = bool(r.get("ok"))
            if not boot["ok"]:
                problems.append(_why(KERNEL_IMPORT_LABEL, r))
        return boot["ok"]

    for f in files:
        rel = f.relative_to(cand).as_posix()
        module = _skill_module(cand, f) if kernel else None
        if module is not None:
            if not kernel_import(f):
                continue
        else:
            r = _run_once(cand, f, None, cfg, _SEEDS[0], "import")
            runs += 1
            if not r.get("ok"):
                problems.append(_why(f"{rel} import", r))
                continue
        for i, row in enumerate(x for x in rows if x.get("helper") == rel):
            label = f"{rel} fixture {row.get('id', i)}"
            mode = "call" if row.get("kind") == "call" else "cli"
            kw = ({"bootstrap": boot["src"], "module": module}
                  if module is not None and mode == "call" else {})   # a cli row runs the file, as before
            try:
                a = _run_once(cand, f, row, cfg, _SEEDS[0], mode, **kw)
                b = _run_once(cand, f, row, cfg, _SEEDS[1], mode, **kw)
            except ValueError as e:
                problems.append(f"{label}: {e}")
                continue
            runs += 2
            if not a.get("ok") or not b.get("ok"):
                problems.append(_why(label, a if not a.get("ok") else b))
            elif (a["stdout"], a["value"], a["outputs"]) != (b["stdout"], b["value"], b["outputs"]):
                problems.append(f"{label}: not deterministic (two runs differ in "
                                f"{'stdout' if a['stdout'] != b['stdout'] else 'return value' if a['value'] != b['value'] else 'output bytes'})")
    if removed and not boot:      # only deletions: an unchanged sibling may import a removed script
        kernel_import(cand / "skills")
    return {"name": "helper_smoke", "ok": not problems, "detail": "; ".join(problems), "skipped": False,
            "files": [f.relative_to(cand).as_posix() for f in files], "runs": runs}
