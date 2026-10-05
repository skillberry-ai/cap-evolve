"""Agent tool surface for the SWE-bench mini-swe-agent runs.

mini-swe-agent's only native tool is a bash shell; its "tools" capability is
therefore the set of executable helpers the agent can invoke by command line.
This file is delivered into the task container (see the project adapter) and
sourced/executed by the agent's bash commands.

The seed ships ONE general-purpose verification helper — the step the traces
show agents re-deriving by hand every task (find the FAIL_TO_PASS tests for the
files a patch touches, run them, and report a PASS/FAIL verdict). The optimizer
may add, edit, or remove helpers here; anything defined in this file is directly
callable in the container.
"""

from __future__ import annotations

import subprocess
import sys


def run_cmd(cmd: str, timeout: int = 120) -> tuple[int, str]:
    """Run a shell command, returning (returncode, combined output)."""
    try:
        p = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"TIMEOUT after {timeout}s: {cmd}"


def _git_changed_py_files() -> list[str]:
    """Source files (.py) modified vs HEAD, newest-first, capped at 12."""
    rc, out = run_cmd("git diff HEAD --name-only 2>/dev/null | head -30")
    if rc != 0:
        return []
    files = [f.strip() for f in out.splitlines()
             if f.strip().endswith(".py") and not f.strip().startswith("test")]
    return files[:12]


def _project_test_cmd(changed: list[str]) -> str | None:
    """Best-effort pytest invocation for the repo's own tests."""
    probes = [
        "python -m pytest -x -q",       # generic
        "python tests/runtests.py",     # Django
        "bin/test -s",                  # SymPy
    ]
    for p in probes:
        rc, _ = run_cmd(f"{p} --version 2>/dev/null || true", timeout=30)
        # --version doesn't work for all; just check the runner exists
        base = p.split()[0]
        rc, _ = run_cmd(f"command -v {base.split('/')[-1]} python -c 'import pytest' 2>/dev/null || true")
    rc, _ = run_cmd("python -c 'import pytest' 2>/dev/null")
    if rc == 0:
        return "python -m pytest"
    rc, _ = run_cmd("test -f tests/runtests.py")
    if rc == 0:
        return "python tests/runtests.py"
    rc, _ = run_cmd("test -x bin/test")
    if rc == 0:
        return "bin/test"
    return None


def verify_fix() -> dict:
    """Locate and run the most relevant existing tests for the files you changed.

    Returns {"changed": [...], "runner": str|None, "results": [{"file": ..., "passed": bool, "output_tail": ...}]}.
    """
    changed = _git_changed_py_files()
    runner = _project_test_cmd(changed)
    results = []
    if runner and changed:
        for f in changed[:3]:
            test_guess = f.replace("/src/", "/tests/").replace(".py", "_test.py")
            rc, _ = run_cmd(f"test -f {test_guess}")
            if rc != 0:
                # common convention: tests/<module path>.py or tests/test_<name>.py
                base = f.rsplit("/", 1)[-1].replace(".py", "")
                for cand in (f"tests/{base}.py", f"tests/test_{base}.py",
                             f"test/{base}.py", f"test/test_{base}.py"):
                    rc, _ = run_cmd(f"test -f {cand}")
                    if rc == 0:
                        test_guess = cand
                        break
            rc, out = run_cmd(f"test -f {test_guess} && {runner} {test_guess} -x -q 2>&1 | tail -20", timeout=600)
            if rc == 0:
                results.append({"file": test_guess, "passed": True, "output_tail": out[-500:]})
            elif rc != 124 or "test -f" not in out:
                # 124 with no output means the guessed file didn't exist; otherwise record
                results.append({"file": test_guess, "passed": False, "output_tail": out[-500:]})
    return {"changed": changed, "runner": runner, "results": results}


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        rc, out = run_cmd("echo ok")
        assert (rc, out.strip()) == (0, "ok"), f"run_cmd broken: {rc} {out!r}"
        print("self-check ok")
    elif len(sys.argv) > 1 and sys.argv[1] == "verify-fix":
        import json as _json
        print(_json.dumps(verify_fix(), indent=2))
    else:
        print("usage: tools.py verify-fix | --self-check", file=sys.stderr)
        sys.exit(2)
