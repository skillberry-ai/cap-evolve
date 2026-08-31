#!/usr/bin/env python3
"""Offline self-check for the SPA runtime.

Everything here runs with NO services and NO network: this must stay green in CI and
inside ``cap-evolve check``. What it asserts, in order of how much a regression would
cost:

  1. ``safe_rm`` refuses every path that holds work rather than dependencies.
  2. ``start_spa`` refuses to run nameless (SPA's nameless fallback silently searches
     the store and would "succeed" against an empty one).
  3. ``Protection`` spares a tool on any of its three markers and nothing else.
  4. Importing the module touches no network and resolves its paths.
  5. The pins are present and shaped as the loader expects.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import spa_env  # noqa: E402


def _expect_refusal(fn, label: str, problems: list[str]) -> None:
    """A guard that does not raise is a guard that does not exist."""
    try:
        fn()
    except RuntimeError:
        return
    except Exception as e:  # noqa: BLE001 — any other error is also a failure to guard
        problems.append(f"{label}: raised {type(e).__name__} instead of RuntimeError")
        return
    problems.append(f"{label}: was NOT refused")


def main() -> int:
    report = {"skill": "spa", "component": "intervention", "ok": False, "problems": [], "notes": []}
    problems: list[str] = report["problems"]
    repo = spa_env.repo_root()

    # 1. Deletion guards -----------------------------------------------------
    for target, label in [
        (Path("/"), "root"),
        (Path.home(), "home"),
        (repo, "repo root"),
        (repo / ".capevolve", ".capevolve"),
        (repo / ".capevolve" / "run_full", "under .capevolve"),
        (repo / ".venv", ".venv"),
        (repo / ".venv" / "lib", "under .venv"),
        (Path("/tmp"), "outside the repo"),
    ]:
        _expect_refusal(lambda t=target, l=label: spa_env.safe_rm(t, l),
                        f"safe_rm({label})", problems)
    # A legitimate target that simply is not there must report, not raise. The library
    # prints as it goes; a skill's stdout is a JSON contract, so swallow that here.
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            removed = spa_env.safe_rm(repo / "vendor" / "does-not-exist-xyz", "absent vendor dir")
        if removed:
            problems.append("safe_rm claimed to remove a path that does not exist")
    except RuntimeError as e:
        problems.append(f"safe_rm refused a legitimate absent target: {e}")

    # 2. SPA must never start nameless --------------------------------------
    _expect_refusal(lambda: spa_env.start_spa(""), "start_spa('')", problems)

    # 3. Protection ---------------------------------------------------------
    p = spa_env.Protection(tags=("frozen",), names=("keep_me",), modules=("substrate.py",))
    cases = [
        ({"name": "x", "tags": ["frozen"]}, True, "tag match"),
        ({"name": "keep_me", "tags": []}, True, "name match"),
        ({"name": "y", "module_name": "substrate.py"}, True, "module match"),
        ({"name": "wrapper", "tags": ["other"], "module_name": "w.py"}, False, "no match"),
        ({}, False, "empty row"),
    ]
    for row, expected, label in cases:
        if p.covers(row) is not expected:
            problems.append(f"Protection.covers({label}) -> {not expected}, expected {expected}")
    if spa_env.Protection():
        problems.append("an empty Protection must be falsy (it protects nothing)")
    if not p:
        problems.append("a populated Protection must be truthy")

    # 4. Import hygiene + path resolution ----------------------------------
    if not (repo / "core" / "cap_evolve").is_dir():
        problems.append(f"repo_root() resolved to {repo}, which is not a cap-evolve checkout")
    for fn in ("provision", "start_store", "start_spa", "restart_spa", "reset_store_to_skill",
               "upload_skill", "delete_skill", "purge_orphans", "import_standalone_tools",
               "status", "clean", "spa_base_url", "docker_bridge_ip", "upstream_llm_args"):
        if not callable(getattr(spa_env, fn, None)):
            problems.append(f"missing public entry point: {fn}")

    # 5. Pins ---------------------------------------------------------------
    if not spa_env.STORE_REF:
        problems.append("STORE_REF pin is empty")
    if len(spa_env.AGENT_REF) != 40 or not all(c in "0123456789abcdef" for c in spa_env.AGENT_REF):
        problems.append(f"AGENT_REF should be a full 40-char commit sha, got {spa_env.AGENT_REF!r}")
    if spa_env.SPA_PORT != "7000":
        problems.append("SPA_PORT must stay 7000 — SPA and its consumers hardcode it")

    # public_functions is pure AST: assert the underscore filter, on this very file.
    names = spa_env.public_functions(Path(__file__))
    if "main" not in names or any(n.startswith("_") for n in names):
        problems.append(f"public_functions() filter is wrong: {names}")

    report["notes"].append(f"pins: store={spa_env.STORE_REF} agent={spa_env.AGENT_REF[:7]}")
    report["notes"].append(f"vendor: {spa_env.vendor_dir()}")
    report["ok"] = not problems
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
