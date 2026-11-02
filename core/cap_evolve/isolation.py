"""Optimizer isolation: keep benchmark gold data out of the optimizer's reach (#875).

Optimizer CLIs run with a shell (claude-code: ``--allowedTools Bash``), so by default they can
read every file the grader needs. A spec opts in with three flat keys:

    optimizer_isolation: auto        # off (default) | auto | namespace | sandbox
    optimizer_hide: [/data/gold, ~/.claude/projects]   # dirs/files the optimizer must not see
    optimizer_expose: [/data/gold/public_docs]         # optional: re-exposed read-only inside a hidden dir

Modes:

* ``namespace`` — every optimizer call runs in a private mount namespace (``_ns_wrap.sh``): each
  hidden directory is an empty tmpfs (an ``optimizer_expose`` path or the optimizer's own working
  dir under it is bound back), each hidden file is an empty file. The call then runs in a nested
  user namespace as a normal user, so it cannot unmount any of it. Linux with unprivileged user
  namespaces; no root; works for ANY optimizer CLI (the whole process is wrapped).
* ``sandbox`` — claude-code only: Claude Code's own bubblewrap sandbox, given ``denyRead`` for the
  hidden paths, ``allowUnsandboxedCommands: false`` and ``failIfUnavailable``, plus
  ``permissions.deny`` ``Read(...)`` rules (the sandbox wraps Bash only; Read/Grep run outside it).
* ``auto`` — ``sandbox`` for claude-code when bubblewrap + socat are present and the bind probe
  passes, else ``namespace`` when user namespaces work, else refuse.

Fail-closed: a requested mode that is not available stops the optimizer call (run-optimizer exits
2 with the reason) instead of running it unisolated. ``self_check`` proves a config offline (no
model call) and runs in ``cap-evolve check``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ENV = "CAPEVOLVE_OPTIMIZER_ISOLATION"
MODES = ("off", "auto", "namespace", "sandbox")
WRAPPER = Path(__file__).with_name("_ns_wrap.sh")


class IsolationError(RuntimeError):
    """The requested isolation cannot be provided; the optimizer must not run."""


def _paths(v) -> list[str]:
    if v in (None, ""):
        return []
    if isinstance(v, str):
        v = [x.strip() for x in v.split(",")]
    return [str(Path(os.path.expanduser(str(x)))) for x in v if str(x).strip()]


def from_spec(spec: dict) -> dict | None:
    """The isolation config a spec declares, or None when it is off/absent."""
    raw = spec.get("optimizer_isolation")
    # the zero-dependency YAML reader turns a bare off/on (no/yes) into a bool
    mode = ("auto" if raw else "off") if isinstance(raw, bool) else str(raw or "off").strip().lower()
    if mode not in MODES:
        raise IsolationError(f"optimizer_isolation: {mode!r} is not one of {MODES}")
    if mode == "off":
        return None
    hide = _paths(spec.get("optimizer_hide"))
    if not hide:
        raise IsolationError("optimizer_isolation is on but optimizer_hide lists no path")
    return {"mode": mode, "hide": hide, "expose": _paths(spec.get("optimizer_expose"))}


def load(environ=None) -> dict | None:
    raw = (environ if environ is not None else os.environ).get(ENV, "").strip()
    return json.loads(raw) if raw else None


def export(cfg: dict | None, environ=None) -> None:
    env = environ if environ is not None else os.environ
    if cfg:
        env[ENV] = json.dumps(cfg)
    else:
        env.pop(ENV, None)


# ---- availability probes (offline, no model call) -----------------------------------------------

def namespace_available() -> tuple[bool, str]:
    if not shutil.which("unshare"):
        return False, "`unshare` not found"
    try:
        r = subprocess.run(["unshare", "-rm", "--propagation", "private", "sh", "-c",
                            "unshare -U --map-user=$(id -u) --map-group=$(id -g) true"],
                           capture_output=True, text=True, timeout=20)
    except Exception as e:  # noqa: BLE001
        return False, f"unshare probe failed: {e}"
    if r.returncode != 0:
        return False, f"unprivileged user namespaces unavailable: {(r.stderr or r.stdout).strip()[:200]}"
    return True, "ok"


def sandbox_available() -> tuple[bool, str]:
    """Claude Code's sandbox needs bwrap + socat and covers missing protected paths with
    /dev/null; in containers whose /dev/null is a host bind that bind cannot be remounted and
    every sandboxed command fails. Probe exactly that."""
    for exe in ("bwrap", "socat"):
        if not shutil.which(exe):
            return False, f"`{exe}` not found"
    with tempfile.NamedTemporaryFile() as f:
        try:
            r = subprocess.run(["bwrap", "--ro-bind", "/", "/", "--ro-bind", "/dev/null", f.name, "true"],
                               capture_output=True, text=True, timeout=20)
        except Exception as e:  # noqa: BLE001
            return False, f"bwrap probe failed: {e}"
    if r.returncode != 0:
        return False, f"bwrap cannot cover a path with /dev/null here: {r.stderr.strip()[:200]}"
    return True, "ok"


def choose_mode(cfg: dict, optimizer: str) -> str:
    """Resolve ``auto`` and verify the mode can run; raise IsolationError otherwise."""
    mode = cfg["mode"]
    if mode in ("sandbox", "auto") and optimizer == "claude-code":
        ok, why = sandbox_available()
        if ok:
            return "sandbox"
        if mode == "sandbox":
            raise IsolationError(f"optimizer_isolation=sandbox unavailable: {why}")
    elif mode == "sandbox":
        raise IsolationError(f"optimizer_isolation=sandbox is claude-code only (optimizer: {optimizer})")
    ok, why = namespace_available()
    if ok:
        return "namespace"
    raise IsolationError(f"optimizer_isolation={mode} unavailable: {why}")


# ---- applying it to one optimizer command ---------------------------------------------------------

def claude_settings(cfg: dict, sandbox: bool) -> dict:
    """Claude Code settings: Read/Grep deny rules always; the bubblewrap sandbox when asked."""
    deny = []
    for p in cfg["hide"]:
        rule = p.rstrip("/") + ("/**" if not Path(p).is_file() else "")
        deny.append(f"Read(/{rule})" if rule.startswith("/") else f"Read({rule})")
    s: dict = {"permissions": {"deny": deny}}
    if sandbox:
        s["sandbox"] = {"enabled": True, "failIfUnavailable": True, "allowUnsandboxedCommands": False,
                        "filesystem": {"denyRead": list(cfg["hide"])}, "network": {"allowedDomains": []}}
    return s


def wrap(cmd: list[str], cfg: dict, *, workdir: str, optimizer: str) -> tuple[list[str], dict, str]:
    """Return ``(argv, extra_env, mode)`` for one isolated optimizer call."""
    mode = choose_mode(cfg, optimizer)
    argv = list(cmd)
    if optimizer == "claude-code":
        # inline JSON: a settings FILE may itself sit in a hidden path
        argv += ["--settings", json.dumps(claude_settings(cfg, sandbox=(mode == "sandbox")))]
    if mode == "sandbox":
        return argv, {}, mode
    env = {"CE_ISO_HIDE": "\n".join(cfg["hide"]), "CE_ISO_EXPOSE": "\n".join(cfg.get("expose") or []),
           "CE_ISO_WORK": str(Path(workdir).resolve())}
    return ["bash", str(WRAPPER), *argv], env, mode


def self_check(cfg: dict, *, workdir: str, optimizer: str = "claude-code") -> list[str]:
    """Offline proof (no model call) that a hidden path is invisible to an isolated call.

    Plants a marker file in every hidden directory (removed afterwards), runs a shell through the
    same wrapper, and checks that no marker is readable, the working dir is writable, and the
    hidden mounts cannot be undone. Returns a list of problems (empty = pass)."""
    try:
        mode = choose_mode(cfg, optimizer)
    except IsolationError as e:
        return [str(e)]
    if mode == "sandbox":
        return []  # bwrap probe passed; Claude Code enforces denyRead itself
    problems, planted = [], []
    for p in cfg["hide"]:
        d = Path(p)
        if d.is_dir() and os.access(d, os.W_OK):
            m = d / ".capevolve_isolation_probe"
            m.write_text("CAPEVOLVE-ISOLATION-PROBE")
            planted.append(m)
    probe = ("set -u; for m in " + " ".join(f"'{m}'" for m in planted) + "; do "
             "[ -e \"$m\" ] && echo \"VISIBLE $m\"; done; "
             f"touch '{Path(workdir).resolve()}/.capevolve_isolation_write' || echo 'WORKDIR NOT WRITABLE'; "
             + "".join(f"umount '{p}' 2>/dev/null && echo 'UNMOUNTED {p}'; " for p in cfg["hide"] if Path(p).is_dir())
             + "true")
    try:
        argv, env, _ = wrap(["sh", "-c", probe], cfg, workdir=workdir, optimizer="generic")
        r = subprocess.run(argv, capture_output=True, text=True, timeout=60, env={**os.environ, **env})
        out = r.stdout + r.stderr
        if r.returncode != 0:
            problems.append(f"isolated call failed (exit {r.returncode}): {out.strip()[:300]}")
        problems += [line for line in out.splitlines() if line.startswith(("VISIBLE", "WORKDIR", "UNMOUNTED"))]
    finally:
        for m in planted:
            m.unlink(missing_ok=True)
        (Path(workdir) / ".capevolve_isolation_write").unlink(missing_ok=True)
    return problems
