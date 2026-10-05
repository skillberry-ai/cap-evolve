"""Agent tool surface for the SWE-bench mini-swe-agent runs.

mini-swe-agent's only native tool is a bash shell; its "tools" capability is
therefore the set of executable helpers the agent can invoke by command line.
This file is delivered into the task container (see the project adapter) and
sourced/executed by the agent's bash commands.

Helpers:
  find-python            print the interpreter that has the project's deps
  run-tests TGT [TGT..]  run test files / node ids with that interpreter
  verify-fix             locate and run the most relevant tests for your edits

Why they exist (from trajectory diagnosis): the agent's default `python` is a
bare interpreter WITHOUT the repository's dependencies, while the image also
ships a second conda env that has them. Agents that ran tests with the default
python hit ModuleNotFoundError for the project itself and concluded testing
was impossible, then shipped unverified fixes. These helpers discover the
right interpreter and give a real test feedback loop.
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys

TIMEOUT = 900


def run_cmd(cmd: str, timeout: int = 120) -> tuple[int, str]:
    """Run a shell command, returning (returncode, combined output)."""
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s: {cmd}"


def _candidate_interpreters() -> list[str]:
    """All plausible python executables on this image, best guesses first.

    Conda env pythons tend to carry the project deps (SWE-bench-style images
    build one env per repo), so they beat the system pythons. Within conda,
    prefer envs with the most site-packages as a cheap proxy for "has deps".
    """
    pats = ["/opt/*/envs/*/bin/python", "/opt/*/bin/python",
            "/usr/local/bin/python3", "/usr/bin/python3"]
    pats += [p for p in os.environ.get("SWE_TOOLS_PY_GLOBS", "")
             .split(os.pathsep) if p]
    found: list[str] = []
    for pat in pats:
        for p in sorted(glob.glob(pat)):
            if os.path.isfile(p) and p not in found:
                found.append(p)
    for p in ("python3", "python"):
        w = shutil_which(p)
        if w and w not in found:
            found.append(w)
    if sys.executable and sys.executable not in found:
        found.append(sys.executable)
    # /opt/*/bin/python (bare conda base) sorts before env pythons via the glob
    # order above only by accident; explicitly deprioritize non-env conda roots.
    envs = [p for p in found if "/envs/" in p]
    rest = [p for p in found if "/envs/" not in p]
    return envs + rest


def shutil_which(name: str) -> str | None:
    """PATH lookup without importing shutil.which (keeps import surface tiny)."""
    for d in os.environ.get("PATH", "").split(os.pathsep):
        cand = os.path.join(d or ".", name)
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


def _repo_packages() -> list[str]:
    """Importable top-level package names for the repo at cwd.

    Covers src/ and lib/ layouts plus plain top-level packages. Excludes
    non-importable and vendored dirs so interpreter probing tests the real
    project.
    """
    excludes = {"test", "tests", "doc", "docs", "examples", "example",
                "tools", "scripts", "benchmarks", "setup", "bin", "build",
                "dist", "__pycache__"}
    pkgs: list[str] = []
    for root in (".", "src", "lib"):
        if not os.path.isdir(root):
            continue
        try:
            entries = sorted(os.listdir(root))
        except OSError:
            continue
        for e in entries:
            if e in excludes or e.startswith((".", "_")):
                continue
            # a package dir, or a known single-module project
            if os.path.isdir(os.path.join(root, e)) and \
                    os.path.isfile(os.path.join(root, e, "__init__.py")):
                pkgs.append(e)
            elif root == "." and e in ("setup.py", "setup.cfg", "pyproject.toml",
                                       "tox.ini"):
                continue
    return pkgs


def _test_import(py: str, names: list[str]) -> bool:
    """True if `py` can import every name in `names` (empty list -> pytest).

    The snippet is fed on stdin (base64) so no quoting ever reaches the
    shell; a failed import or a missing python both exit nonzero.
    """
    if not names:
        names = ["pytest"]
    snippet = "import importlib, sys\n" + "".join(
        f"importlib.import_module({n!r})\n" for n in names) + "sys.exit(0)\n"
    import base64
    b64 = base64.b64encode(snippet.encode()).decode()
    rc, _ = run_cmd(f"{py} -c 'import base64;exec(base64.b64decode(\"{b64}\"))'",
                    timeout=60)
    return rc == 0


def find_test_python() -> dict:
    """Pick the interpreter that can import the repo's packages and pytest.

    Returns {"python": path or None, "can_import": [...], "note": str}.
    Probing is capability-based (can this python import the project?), not
    name-based, so it generalizes across images.
    """
    pkgs = _repo_packages()
    per_python = []
    for py in _candidate_interpreters():
        ok = _test_import(py, pkgs[:2] if pkgs else [])
        per_python.append({"python": py, "imports_project": ok})
        if ok:
            return {"python": py, "can_import": pkgs, "note": "project import ok"}
    note = ("no interpreter can import the project packages; "
            f"candidates probed: {len(per_python)}" if per_python
            else "no python interpreters found")
    return {"python": None, "can_import": pkgs, "note": note, "probed": per_python}


def _git_root() -> str | None:
    rc, out = run_cmd("git rev-parse --show-toplevel 2>/dev/null")
    if rc != 0 or not out.strip():
        return None
    return out.strip()


def _session_base_commit() -> str | None:
    """The last commit that existed when this agent session started.

    The agent often `git commit`s its work mid-session, which makes
    `git diff HEAD` empty and made the old helper go blind. We time-walk the
    log instead: the session base is the newest commit that is at least
    SESSION_COMMIT_AGE_MIN minutes older than HEAD. Env override for tests.
    """
    rc, out = run_cmd('git log -40 --format="%H %ct"')
    if rc != 0:
        return None
    rows = [ln.split() for ln in out.splitlines() if ln.strip()]
    if not rows:
        return None
    try:
        head_ts = int(rows[0][1])
    except (ValueError, IndexError):
        return None
    # allow override for offline verification
    age_s = int(os.environ.get("SWE_TOOLS_COMMIT_AGE_MIN", "180")) * 60
    for sha, ts_s in rows:
        try:
            if head_ts - int(ts_s) >= age_s:
                return sha
        except ValueError:
            continue
    # every commit is fresh (repo fully rebuilt this session): diff against
    # the oldest one we saw
    return rows[-1][0]


def _git_changed_py_files() -> list[str]:
    """Source files (.py) changed since the session base, newest-first, <=12.

    Merges committed-since-session and uncommitted changes so a mid-session
    `git commit` doesn't hide work from verify-fix.
    """
    rc, out = run_cmd(
        "git status --porcelain 2>/dev/null | awk '{print $2}' | head -40")
    committed: list[str] = []
    if rc == 0:
        base = _session_base_commit()
        if base:
            rc2, out2 = run_cmd(f"git diff --name-only {base}..HEAD")
            if rc2 == 0:
                committed = [ln.strip() for ln in out2.splitlines() if ln.strip()]
    uncommitted = [ln.strip() for ln in out.splitlines() if ln.strip()]
    seen, files = set(), []
    for f in committed + uncommitted:
        if f in seen or not f.endswith(".py"):
            continue
        seen.add(f)
        if f.startswith(("test", "tests/", "testing/")) or "/tests/" in f:
            continue
        files.append(f)
    return files[:12]


def _project_test_cmd(changed: list[str], py: str | None = None) -> str | None:
    """Test-runner invocation for this repo, prefixed with a working python."""
    py = py or find_test_python()["python"] or "python"
    if os.path.isfile("tests/runtests.py"):
        return f"{py} tests/runtests.py"          # Django-style
    if os.path.isfile("bin/test"):
        return f"{py} bin/test"                   # SymPy-style
    if _test_import(py, ["pytest"]):
        return f"{py} -m pytest"
    return None


def _to_dotted(path: str) -> str:
    """tests/x/y.py -> tests.x.y (Django runtests.py wants dotted labels)."""
    p = path[:-3] if path.endswith(".py") else path
    return p.replace("\\", "/").replace("/", ".")


def _guess_test_files(src: str, runner: str) -> list[str]:
    """Existing test files most likely to cover `src`, conventions + grep."""
    stem = os.path.basename(src)[:-3] if src.endswith(".py") else os.path.basename(src)
    cands: list[str] = []
    src_noext = src[:-3] if src.endswith(".py") else src
    for mapping in ("/src/", "/lib/"):
        if mapping in src_noext:
            src_noext = src_noext.replace(mapping, "/tests/")
    cands.append(src_noext + "_test.py")
    base = os.path.basename(src_noext)
    for cand in (f"tests/{base}.py", f"tests/test_{stem}.py",
                 f"tests/{stem}_test.py", f"test/{base}.py",
                 f"test/test_{stem}.py", src_noext.replace("/src/", "/test/"),
                 f"testing/{stem if 'testing' not in src else base}.py",
                 f"{src_noext}_test.py"):
        cands.append(cand)
    out: list[str] = []
    for c in cands:
        if c and os.path.isfile(c) and c not in out:
            out.append(c)
    if not out and stem:
        # bounded content search: which test files mention this module's stem
        rc, g = run_cmd(
            f"grep -rl -w {json.dumps(stem)} --include='*.py' tests test testing 2>/dev/null | head -3")
        if rc == 0:
            for ln in g.splitlines():
                ln = ln.strip()
                if ln and os.path.isfile(ln) and ln not in out:
                    out.append(ln)
    return out[:3]


def run_tests(targets: list[str], timeout: int = TIMEOUT) -> dict:
    """Run the given test files / node ids with the deps-having interpreter.

    Handles the three runner shapes seen across repos: plain pytest,
    Django's tests/runtests.py (converts paths to dotted labels), and SymPy's
    bin/test. Returns a structured verdict with the output tail so the agent
    can iterate on real failures instead of guessing.
    """
    if not targets:
        return {"error": "no test targets given; pass files or node ids"}
    py_info = find_test_python()
    py = py_info["python"] or "python"
    runner = _project_test_cmd([], py=py)
    if runner is None:
        return {"error": f"no usable test runner with interpreter {py}",
                "python": py, "note": py_info.get("note", "")}
    results = []
    for t in targets:
        if "runtests.py" in runner:
            label = _to_dotted(t) if t.endswith(".py") else t
            cmd = f"{runner} {label} -v 2"
        elif "bin/test" in runner:
            cmd = f"{runner} {t}"
        else:
            cmd = f"{runner} {json.dumps(t)} -x -q"
        rc, out = run_cmd(f"cd {json.dumps(os.getcwd())} && {cmd} 2>&1 | tail -40",
                          timeout=timeout)
        passed = rc == 0
        results.append({"target": t, "cmd": cmd, "passed": passed,
                        "output_tail": out[-1500:]})
    all_passed = all(r["passed"] for r in results)
    return {"python": py, "runner": runner, "results": results,
            "all_passed": all_passed}


def verify_fix() -> dict:
    """Locate and run the most relevant existing tests for the files you changed.

    Combines: session-aware changed-file detection (works even after you
    `git commit`), interpreter discovery, runner detection, and per-file
    verdicts. Only reports test files that actually exist.
    """
    changed = _git_changed_py_files()
    if not changed:
        return {"changed": [], "runner": None, "results": [],
                "note": "no changed .py source files detected; if you committed "
                        "your work, pass files explicitly: run-tests <file> ..."}
    py_info = find_test_python()
    py = py_info["python"] or "python"
    runner = _project_test_cmd(changed, py=py)
    if runner is None:
        return {"changed": changed, "runner": None, "python": py,
                "note": "no test runner available for interpreter " + py}
    results = []
    for f in changed[:3]:
        for test_file in _guess_test_files(f, runner):
            if "runtests.py" in runner:
                label = _to_dotted(test_file)
                cmd = f"{runner} {label} -v 2"
            elif "bin/test" in runner:
                cmd = f"{runner} {test_file}"
            else:
                cmd = f"{runner} {test_file} -x -q"
            rc, out = run_cmd(f"{cmd} 2>&1 | tail -40", timeout=TIMEOUT)
            results.append({"file": test_file, "passed": rc == 0,
                            "cmd": cmd, "output_tail": out[-1200:]})
    hint = ""
    if results:
        hint = ("rerun a single failing target: python /harbor/skills/candidate/"
                "tools/tools.py run-tests <test file or node id>")
    return {"changed": changed, "runner": runner, "python": py,
            "results": results, "hint": hint}


def _self_check() -> None:
    rc, out = run_cmd("echo ok")
    assert (rc, out.strip()) == (0, "ok"), f"run_cmd broken: {rc} {out!r}"
    # discovery machinery must run without raising anywhere it's dropped in
    _candidate_interpreters()
    _repo_packages()
    info = find_test_python()
    assert isinstance(info, dict) and "python" in info
    changed = _git_changed_py_files()
    assert isinstance(changed, list)
    assert _guess_test_files("no/such/file.py", "x") == []
    assert _to_dotted("tests/x/y.py") == "tests.x.y"
    assert run_tests([])["error"].startswith("no test targets")
    print("self-check ok")


def main(argv: list[str]) -> int:
    if "--self-check" in argv:
        _self_check()
        return 0
    if len(argv) < 2:
        print("usage: tools.py find-python | run-tests TGT [TGT..] | "
              "verify-fix | --self-check", file=sys.stderr)
        return 2
    cmd = argv[1]
    if cmd == "verify-fix":
        print(json.dumps(verify_fix(), indent=2))
        return 0
    if cmd == "find-python":
        print(json.dumps(find_test_python(), indent=2))
        return 0
    if cmd == "run-tests":
        if len(argv) < 3:
            print("run-tests needs at least one test file or node id",
                  file=sys.stderr)
            return 2
        print(json.dumps(run_tests(argv[2:]), indent=2))
        return 0
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
