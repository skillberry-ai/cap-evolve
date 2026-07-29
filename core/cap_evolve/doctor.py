"""``cap-evolve doctor`` — install/health self-diagnostic.

Every check here targets a failure that ``docs/TROUBLESHOOTING.md`` already
documents as a real support case, so the diagnostic preempts the actual stumbles
rather than invented ones:

  ``python``       Python too old (TROUBLESHOOTING "Python too old" — needs 3.10+)
  ``core``         ``cap-evolve: command not found`` / ``pip install ./core`` skipped
  ``cli-path``     same, plus a *shadowing* second install (issue #121)
  ``git``          the default version store is git; a missing git breaks candidates
  ``skills``       ``no manifest — run install.sh``, and install.sh's own
                   "best-guess" host dirs (install.sh:38-40)
  ``optimizer``    optimizer CLI missing / not logged in (TROUBLESHOOTING
                   "Missing credentials at runtime")
  ``credentials``  runner + optimizer provider creds, PRESENCE ONLY
  ``run-dir``      the run dir must be writable before any budget is spent
  ``project``      ``cap-evolve check`` is not green — reuses ``check.run_check``

SECURITY: the credential check reports only PRESENCE/ABSENCE. No secret value —
not even a prefix or a length — is ever emitted, and the whole report is passed
through ``dashboard.redact`` on the way out as defense in depth.

Exit code: 0 when nothing FAILs (warnings are advisory), 1 on any hard failure,
so CI can gate on ``cap-evolve doctor``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import __version__
from .dashboard import redact

PASS, WARN, FAIL = "pass", "warn", "fail"

_MARK = {PASS: "PASS", WARN: "WARN", FAIL: "FAIL"}

# Runner-model credential surface documented in INSTALL.md#credentials-only-for-real-runs
# and TROUBLESHOOTING "Missing credentials at runtime" / "RITS calls fail" /
# "SkillsBench: Docker / benchflow errors". Names only — values are never read.
_RUNNER_ENV_GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("anthropic", ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL")),
    ("openai", ("OPENAI_API_KEY",)),
    ("rits", ("RITS_API_KEY", "RITS_API_URL")),
    ("watsonx", ("WATSONX_APIKEY", "WATSONX_URL", "WATSONX_PROJECT_ID")),
    ("gemini", ("GEMINI_API_KEY",)),
]

# install.sh:38-40 admits these host dirs are guesses; the verified ones are documented
# in the same comment. Surfacing which kind you're on is the whole point of check #5.
_VERIFIED_HOST_DIRS = ("/.claude/skills", "/.agents/skills", "/.config/opencode/skills",
                       "/.capevolve/skills", "/.gemini/extensions/cap-evolve/skills")


@dataclass
class Check:
    name: str
    status: str
    detail: str = ""
    fix: str = ""
    # Credential PRESENCE only: env var NAMES, never values. Kept structured (rather than
    # baked into ``detail``) so the "NAME: set (hidden)" rendering happens AFTER redact()
    # — otherwise the inline KEY=value redactor would scrub the word "set" itself.
    present: list = field(default_factory=list)
    absent: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"name": self.name, "status": self.status, "detail": self.detail, "fix": self.fix,
                "present": list(self.present), "absent": list(self.absent)}


@dataclass
class DoctorReport:
    checks: list[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(c.status == FAIL for c in self.checks)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "cap_evolve": __version__,
                "checks": [c.to_dict() for c in self.checks]}


# ---------------------------------------------------------------------------
# individual checks — each takes (cwd) and returns a Check
# ---------------------------------------------------------------------------

def _check_python(cwd: Path) -> Check:
    v = sys.version_info
    ver = f"{v.major}.{v.minor}.{v.micro}"
    if v < (3, 10):
        return Check("python", FAIL, f"{ver} at {sys.executable}",
                     "cap-evolve needs Python 3.10+ — create a newer venv: "
                     "python3 -m venv .venv && source .venv/bin/activate")
    return Check("python", PASS, f"{ver} at {sys.executable}")


def _check_core(cwd: Path) -> Check:
    try:
        import cap_evolve
    except Exception as e:  # noqa: BLE001 — pragma: no cover (we ARE cap_evolve)
        return Check("core", FAIL, f"import cap_evolve failed: {e}",
                     "pip install ./core (or export CAPEVOLVE_CORE=<repo>/core)")
    where = Path(cap_evolve.__file__).parent
    venv = os.environ.get("VIRTUAL_ENV") or sys.prefix
    detail = f"cap_evolve {__version__} from {where} (env {venv})"
    # "Trapped in the wrong venv": the interpreter importing core is not the one the
    # activated venv points at, so `pip install` lands somewhere the run won't see.
    active = os.environ.get("VIRTUAL_ENV")
    if active and not str(Path(sys.executable).resolve()).startswith(str(Path(active).resolve())):
        return Check("core", WARN, detail + f" — but VIRTUAL_ENV={active} does not own {sys.executable}",
                     "you are in one venv but running another interpreter; "
                     f"use {Path(active) / 'bin' / 'python'} -m cap_evolve.cli, or re-activate")
    return Check("core", PASS, detail)


def _check_cli_path(cwd: Path) -> Check:
    found = shutil.which("cap-evolve")
    if not found:
        return Check("cli-path", WARN, "cap-evolve is not on PATH",
                     "install.sh deliberately does NOT install the Python package: run "
                     "`pip install ./core` in the active venv. Until then use "
                     "`python -m cap_evolve.cli ...`.")
    # Shadowing: the first cap-evolve on PATH belongs to a different install than the
    # cap_evolve package this process imported.
    expected = Path(sys.executable).parent / "cap-evolve"
    if expected.exists() and Path(found).resolve() != expected.resolve():
        return Check("cli-path", WARN, f"PATH resolves to {found}, but this interpreter's is {expected}",
                     "a second (shadowing) install is earlier on PATH — remove it, or call "
                     f"{expected} / `python -m cap_evolve.cli` explicitly.")
    return Check("cli-path", PASS, found)


def _check_git(cwd: Path) -> Check:
    exe = shutil.which("git")
    if not exe:
        return Check("git", FAIL, "git not found on PATH",
                     "the default version store is git (every candidate is a commit) — "
                     "install git, or set `store: none` in capevolve.yaml")
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10)
        return Check("git", PASS, out.stdout.strip() or exe)
    except Exception as e:  # noqa: BLE001
        return Check("git", FAIL, f"{exe} present but not runnable: {e}",
                     "reinstall git or fix its permissions")


def _skills_dir() -> Path | None:
    from .cli import _find_skills_dir
    return _find_skills_dir()


def _check_skills(cwd: Path) -> Check:
    d = _skills_dir()
    if d is None:
        return Check("skills", FAIL, "no skills dir found",
                     "run ./install.sh (or set CAPEVOLVE_SKILLS_DIR to the repo's skills/)")
    manifest = d / "_registry" / "manifest.json"
    if not manifest.exists():
        return Check("skills", FAIL, f"skills at {d} but no _registry/manifest.json",
                     "rebuild it: python skills/_registry/build_manifest.py "
                     f"{d}   (install.sh does this for you)")
    try:
        skills = json.loads(manifest.read_text(encoding="utf-8")).get("skills") or {}
    except Exception as e:  # noqa: BLE001
        return Check("skills", FAIL, f"{manifest} is not valid JSON: {e}",
                     f"rebuild it: python skills/_registry/build_manifest.py {d}")
    # Manifest/disk consistency: a stale manifest naming a skill whose dir was removed
    # fails opaquely deep inside `cap-evolve run` (KeyError / missing entry script).
    missing = [n for n, s in skills.items() if not (d / s.get("path", "") / s.get("entry", "")).exists()]
    # The repo's own skills/ (component layout: skills/phases/..., an _registry sibling of
    # optimizers/) is a first-class source, not a "best-guess host dir".
    from_source = (d / "optimizers" / "registry.yaml").exists()
    guessy = not from_source and not any(str(d).endswith(v) for v in _VERIFIED_HOST_DIRS)
    if missing:
        return Check("skills", FAIL,
                     f"{len(skills)} skill(s) in manifest at {d}; "
                     f"{len(missing)} entry script(s) missing: {', '.join(sorted(missing)[:5])}",
                     f"stale manifest — rebuild: python skills/_registry/build_manifest.py {d}")
    if guessy:
        return Check("skills", WARN, f"{len(skills)} skill(s) at {d}",
                     "this is a best-guess host dir, not one of the ones verified in "
                     "install.sh:38-40 — if your agent doesn't see the skills, re-install "
                     "with ./install.sh --dest DIR or set $CAPEVOLVE_SKILLS_DIR")
    return Check("skills", PASS, f"{len(skills)} skill(s) at {d}"
                 + (" (repo source layout)" if from_source else ""))


def _optimizer_registry() -> dict:
    """Resolve ``optimizers/registry.yaml`` the same way ``run-optimizer/scripts/run.py``
    does, so doctor reports what the run will actually find (repo layout or flat install).
    """
    d = _skills_dir()
    cands = []
    env = os.environ.get("CAPEVOLVE_OPTIMIZER_REGISTRY")
    if env:
        cands.append(Path(env))
    if d:
        # repo layout, flat install root, and beside the copied run-optimizer skill dir
        cands += [d / "optimizers" / "registry.yaml", d / "registry.yaml",
                  d / "run-optimizer" / "registry.yaml"]
    for cand in cands:
        if cand.exists():
            from .specfile import read_yaml
            return read_yaml(cand.read_text(encoding="utf-8")) or {}
    return {}


def _check_optimizer(cwd: Path) -> Check:
    reg = _optimizer_registry()
    if not reg:
        return Check("optimizer", WARN, "optimizers/registry.yaml not found",
                     "run ./install.sh, or set CAPEVOLVE_OPTIMIZER_REGISTRY")
    available, absent = [], []
    for name, row in reg.items():
        if not isinstance(row, dict):
            continue
        tmpl = str(row.get("command_template") or "")
        exe = tmpl.split()[0] if tmpl.split() else ""
        if not exe or exe.startswith("$") or exe in ("python3", "python"):
            available.append(name)   # mock/generic/env-driven — nothing to look up
        elif shutil.which(exe):
            available.append(name)
        else:
            absent.append(name)
    if not available:
        return Check("optimizer", FAIL, f"no optimizer CLI on PATH (checked {len(reg)})",
                     "install one (e.g. Claude Code, codex, gemini) or use "
                     "`optimizer_skill: mock` for a zero-API run")
    return Check("optimizer", PASS, f"available: {', '.join(sorted(available))}"
                 + (f" | not on PATH: {', '.join(sorted(absent))}" if absent else ""))


def _check_credentials(cwd: Path) -> Check:
    """PRESENCE ONLY. Never reads or reports a credential VALUE — see module docstring."""
    groups = list(_RUNNER_ENV_GROUPS)
    # Fold in each optimizer row's declared env_keys so the surface stays in sync with
    # the registry instead of being a second hardcoded list.
    opt_keys: list[str] = []
    for row in _optimizer_registry().values():
        if isinstance(row, dict):
            opt_keys += [k.strip() for k in str(row.get("env_keys") or "").split(",") if k.strip()]
    if opt_keys:
        groups.append(("optimizer-cli", tuple(dict.fromkeys(opt_keys))))

    seen: set[str] = set()
    set_names, unset_names = [], []
    for _, keys in groups:
        for k in keys:
            if k in seen:
                continue
            seen.add(k)
            # bool() of presence only — the VALUE is never read into any reported field.
            (set_names if os.environ.get(k) else unset_names).append(k)
    if not set_names:
        return Check("credentials", WARN, "no provider credentials in the environment",
                     "the toy example needs none; a real run needs the optimizer CLI's creds "
                     "plus runner creds in a repo-root .env — see "
                     "docs/INSTALL.md#credentials-only-for-real-runs",
                     absent=unset_names)
    return Check("credentials", PASS, f"{len(set_names)} set, {len(unset_names)} absent",
                 present=set_names, absent=unset_names)


def _check_run_dir(cwd: Path) -> Check:
    base = cwd / ".capevolve"
    target = base if base.is_dir() else cwd
    try:
        with tempfile.NamedTemporaryFile(dir=target, prefix=".doctor-", delete=True):
            pass
    except Exception as e:  # noqa: BLE001
        return Check("run-dir", FAIL, f"{target} is not writable: {e}",
                     "runs write splits/rollouts/candidates under .capevolve/ — "
                     "cd to a writable dir or fix permissions")
    return Check("run-dir", PASS, f"{target} writable")


def _check_project(cwd: Path) -> Check:
    project = cwd / ".capevolve" / "project"
    if not (project / "adapters" / "adapter.py").exists():
        return Check("project", PASS, "not inside a cap-evolve project (nothing to validate)")
    from .check import run_check
    rep = run_check(project)
    if rep.ok:
        return Check("project", PASS, f"{project} — cap-evolve check green; " + "; ".join(rep.notes))
    return Check("project", FAIL, f"{project} — cap-evolve check failed: " + "; ".join(rep.problems),
                 "this is the hard gate doing its job — fix the adapter, then "
                 f"`cap-evolve check {project}` must print {{\"ok\": true}}. "
                 "See docs/ADAPTER_CONTRACT.md")


# ponytail: a plain list, not a plugin registry — adding a check is one function + one line.
CHECKS = (_check_python, _check_core, _check_cli_path, _check_git, _check_skills,
          _check_optimizer, _check_credentials, _check_run_dir, _check_project)


def run_doctor(cwd: Path | str = ".") -> DoctorReport:
    cwd = Path(cwd)
    rep = DoctorReport()
    for fn in CHECKS:
        try:
            rep.checks.append(fn(cwd))
        except Exception as e:  # noqa: BLE001 — one broken check must not hide the others
            rep.checks.append(Check(fn.__name__.removeprefix("_check_"), FAIL,
                                    f"check raised: {e}", "please report this with the output above"))
    return rep


def format_report(rep: DoctorReport) -> str:
    """Human-readable pass/warn/fail lines. Redacted (defense in depth)."""
    d = redact(rep.to_dict())
    out = [f"cap-evolve doctor  (core {d['cap_evolve']})", ""]
    for c in d["checks"]:
        out.append(f"  [{_MARK[c['status']]}] {c['name']:<12} {c['detail']}")
        # Names only, rendered post-redaction: "set (hidden)" / "absent", never a value.
        for k in c.get("present") or []:
            out.append(f"         {k}: set (hidden)")
        if c.get("absent"):
            out.append(f"         absent: {', '.join(c['absent'])}")
        if c["fix"] and c["status"] != PASS:
            out.append(f"         → fix: {c['fix']}")
    n_fail = sum(1 for c in d["checks"] if c["status"] == FAIL)
    n_warn = sum(1 for c in d["checks"] if c["status"] == WARN)
    out += ["", f"{'FAIL' if n_fail else 'OK'}: {n_fail} failure(s), {n_warn} warning(s)"]
    return "\n".join(out)


def _main(argv: list[str]) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="cap-evolve doctor",
                                description="install/health diagnostic; exits non-zero on hard failure")
    p.add_argument("cwd", nargs="?", default=".", help="directory to diagnose (default: .)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    args = p.parse_args(argv)
    rep = run_doctor(Path(args.cwd))
    print(json.dumps(redact(rep.to_dict()), indent=2) if args.json else format_report(rep))
    return 0 if rep.ok else 1
