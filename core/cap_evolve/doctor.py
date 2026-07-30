"""``cap-evolve doctor`` — install/health self-diagnostic.

Every check here targets a failure that ``docs/TROUBLESHOOTING.md`` already
documents as a real support case, so the diagnostic preempts the actual stumbles
rather than invented ones:

  ``python``       Python too old (TROUBLESHOOTING "Python too old" — needs 3.10+)
  ``core``         ``cap-evolve: command not found`` / ``pip install ./core`` skipped
  ``cli-path``     same, plus a *shadowing* second install (issue #121)
  ``git``          the default version store is git; a missing git breaks candidates
  ``skills``       ``no manifest — run install.sh``, and install.sh's own
                   "best-guess" host dirs (skills/_registry/hosts.yaml)
  ``optimizer``    optimizer CLI missing / not logged in (TROUBLESHOOTING
                   "Missing credentials at runtime")
  ``credentials``  runner + optimizer provider creds, PRESENCE ONLY
  ``run-dir``      the run dir must be writable before any budget is spent
  ``project``      ``cap-evolve check`` is not green — reuses ``check.run_check``

SECURITY (three independent layers, because shape matching alone is not enough):

1. The credential check reports only PRESENCE/ABSENCE — no value, prefix or length.
2. Third-party text (a user adapter's exception message, reached via
   ``check.run_check``) is NEVER echoed verbatim: ``_summarize_untrusted`` bounds it
   to a short excerpt and the full text goes to a local file instead of stdout.
   This is the primary defense for the ``project`` check, since an adapter can raise
   with a credential of any shape in its message.
3. The whole report passes through ``dashboard.redact``, which masks secret *shapes*
   AND (shape-independently) the literal values of this process's secret-looking env
   vars — the only rule that catches an opaque watsonx key or a UUID token.

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

# Vars the docs say must be set TOGETHER — half a pair is not usable, so PASSing on it
# is a false green. Not every group above is like this (ANTHROPIC_API_KEY alone is fine),
# hence an explicit list rather than "every group needs all its members".
#   TROUBLESHOOTING.md "RITS calls fail" — set BOTH RITS_API_KEY and RITS_API_URL
#   watsonx needs apikey + url + project id
#   the SkillsBench gateway pair: a custom base URL needs its own token
_REQUIRED_TOGETHER: list[tuple[str, ...]] = [
    ("RITS_API_KEY", "RITS_API_URL"),
    ("WATSONX_APIKEY", "WATSONX_URL", "WATSONX_PROJECT_ID"),
    ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN"),
]

def _known_host_dirs() -> tuple[str, ...]:
    """Skills-dir suffixes install.sh's ``--host`` mapping can produce.

    Derived from ``skills/_registry/hosts.yaml`` — the single source (issue #143).
    This used to be a hand-maintained tuple that had already drifted from
    install.sh's ``case``: it had six entries but only 5 of the 12 real destinations —
    its ``/.capevolve/skills`` entry is the no-host default, not a host dest — so
    **seven** correct host dirs were being reported as "best-guess".
    ``~/.capevolve/skills`` is still appended here because it is install.sh's no-host
    default, which is a legitimate placement with no hosts.yaml row (13 dirs total).
    """
    from .hosts import load_hosts
    # Strip the leading $HOME / $PWD token rather than an expanded path, so the
    # suffixes are independent of both the real $HOME (a temp-$HOME install still
    # matches) and the cwd (which a $PWD row would otherwise bake in).
    tails = [str(r.get("dest", "")).replace("$HOME", "", 1).replace("$PWD", "", 1).rstrip("/")
             for r in load_hosts().values()]
    return tuple(t for t in tails if t) + ("/.capevolve/skills",)


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
    active = os.environ.get("VIRTUAL_ENV")
    detail = f"cap_evolve {__version__} from {where} (env {active or sys.prefix})"
    # "Trapped in the wrong venv": the interpreter importing core is not the one the
    # activated venv points at, so `pip install` lands somewhere the run won't see.
    # Compare against sys.prefix — "the venv THIS interpreter belongs to". Resolving
    # sys.executable instead would follow bin/python's symlink out to the base
    # interpreter, which never lives under $VIRTUAL_ENV: a false WARN on every
    # correctly activated venv (macOS/Homebrew, and pyvenv in general).
    if active and Path(active).resolve() != Path(sys.prefix).resolve():
        return Check("core", WARN, detail + f" — but VIRTUAL_ENV={active} is not this interpreter's prefix ({sys.prefix})",
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
                     "install git, or set `store: copy` in capevolve.yaml "
                     "(store.py accepts git | copy | command — there is no `none`)")
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=10)
        return Check("git", PASS, out.stdout.strip() or exe)
    except Exception as e:  # noqa: BLE001
        return Check("git", FAIL, f"{exe} present but not runnable: {e}",
                     "reinstall git or fix its permissions")


def _skills_dir() -> Path | None:
    from .cli import _find_skills_dir
    return _find_skills_dir()


def _build_manifest_hint() -> str:
    """Path to ``build_manifest.py`` that is actually valid from where the user stands.

    A flat install has no ``skills/_registry/`` at all, so the bare repo-relative form
    printed a command that could not run. Prefer the real absolute path when we can see
    the repo checkout, otherwise say where it comes from.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "skills" / "_registry" / "build_manifest.py"
        if cand.exists():
            return str(cand)
    return "<repo>/skills/_registry/build_manifest.py"


def _check_skills(cwd: Path) -> Check:
    d = _skills_dir()
    if d is None:
        return Check("skills", FAIL, "no skills dir found",
                     "run ./install.sh (or set CAPEVOLVE_SKILLS_DIR to the repo's skills/)")
    manifest = d / "_registry" / "manifest.json"
    if not manifest.exists():
        return Check("skills", FAIL, f"skills at {d} but no _registry/manifest.json",
                     f"rebuild it: python {_build_manifest_hint()} {d}"
                     "   (re-running ./install.sh does this for you)")
    try:
        skills = json.loads(manifest.read_text(encoding="utf-8")).get("skills") or {}
    except Exception as e:  # noqa: BLE001
        return Check("skills", FAIL, f"{manifest} is not valid JSON: {e}",
                     f"rebuild it: python {_build_manifest_hint()} {d}")
    # Manifest/disk consistency: a stale manifest naming a skill whose dir was removed
    # fails opaquely deep inside `cap-evolve run` (KeyError / missing entry script).
    # `or ""` not `.get(k, "")`: a manifest with an explicit null field yields None, and
    # Path / None is a TypeError — a diagnostic must diagnose malformed input, not crash
    # on it. A null entry IS a missing entry, which is what the empty string makes it.
    missing = [n for n, s in skills.items()
               if not isinstance(s, dict)
               or not (s.get("entry") or "")
               or not (d / (s.get("path") or "") / (s.get("entry") or "")).exists()]
    # The repo's own skills/ (component layout: skills/phases/..., an _registry sibling
    # of optimizers/) is a first-class source. A flat ./install.sh tree is equally
    # legitimate — recognise it by the flattened skill dirs the manifest names, NOT by
    # the registry file (which lives elsewhere and made every flat install "guessy").
    # install.sh now copies the registry into every install, so its presence means
    # "a cap-evolve install lives here", repo or flat — either way not a stray guess.
    known = (d / "optimizers" / "registry.yaml").exists()
    from_source = known and (d / "phases").is_dir()
    # resolve() first: a relative dir like ./.claude/skills never ends with
    # "/.claude/skills" as a raw string, so every relative dir was flagged.
    resolved = str(d.resolve())
    guessy = not known and not any(resolved.endswith(v) for v in _known_host_dirs())
    if missing:
        return Check("skills", FAIL,
                     f"{len(skills)} skill(s) in manifest at {d}; "
                     f"{len(missing)} entry script(s) missing: {', '.join(sorted(missing)[:5])}",
                     f"stale manifest — rebuild: python {_build_manifest_hint()} {d}")
    if guessy:
        return Check("skills", WARN, f"{len(skills)} skill(s) at {d}",
                     "best-guess dir: not one of the hosts in skills/_registry/hosts.yaml "
                     "(see docs/HOST_SUPPORT.md for each one's grade) — if your agent "
                     "doesn't see the skills, re-install with ./install.sh --dest DIR "
                     "or set $CAPEVOLVE_SKILLS_DIR")
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
        # repo layout / flat install (install.sh copies it to $DEST/optimizers/), the
        # install root, beside the copied run-optimizer skill dir, and one level up.
        cands += [d / "optimizers" / "registry.yaml", d / "registry.yaml",
                  d / "run-optimizer" / "registry.yaml",
                  d / "run-optimizer" / "optimizers" / "registry.yaml",
                  d.parent / "optimizers" / "registry.yaml"]
    for cand in cands:
        if cand.exists():
            from .specfile import read_yaml
            return read_yaml(cand.read_text(encoding="utf-8")) or {}
    return {}


def _check_optimizer(cwd: Path) -> Check:
    reg = _optimizer_registry()
    if not reg:
        # FAIL, not WARN: run-optimizer/scripts/run.py raises FileNotFoundError on this
        # exact state, so a run dies immediately. Exiting 0 here would greenlight a
        # machine that cannot optimize — the worst thing a diagnostic can do.
        d = _skills_dir()
        where = f"{d}/optimizers/registry.yaml" if d else "<skills-dir>/optimizers/registry.yaml"
        return Check("optimizer", FAIL,
                     f"optimizers/registry.yaml not found — run-optimizer cannot start "
                     f"(looked for {where})",
                     "copy it from the repo: "
                     f"mkdir -p {d or '<skills-dir>'}/optimizers && cp <repo>/skills/optimizers/"
                     f"registry.yaml {d or '<skills-dir>'}/optimizers/   — or point at the "
                     "checkout with CAPEVOLVE_OPTIMIZER_REGISTRY=<repo>/skills/optimizers/"
                     "registry.yaml (older install.sh runs did not copy it; re-running the "
                     "current ./install.sh also fixes this)")
    # "Available" splits into CLIs actually on PATH vs. the local/zero-API rows
    # (mock/generic/$ENV-driven) that need nothing installed. Conflating them made the
    # FAIL branch unreachable with the shipped registry — mock alone always "passed".
    on_path, local, absent = [], [], []
    for name, row in reg.items():
        if not isinstance(row, dict):
            continue
        tmpl = str(row.get("command_template") or "")
        exe = tmpl.split()[0] if tmpl.split() else ""
        if not exe or exe.startswith("$") or exe in ("python3", "python"):
            local.append(name)
        elif shutil.which(exe):
            on_path.append(name)
        else:
            absent.append(name)
    tail = (f" | local/zero-API: {', '.join(sorted(local))}" if local else "") \
           + (f" | not on PATH: {', '.join(sorted(absent))}" if absent else "")
    if not on_path and not local:
        return Check("optimizer", FAIL, f"no optimizer available at all (checked {len(reg)})",
                     "install one (e.g. Claude Code, codex, gemini)")
    if not on_path:
        return Check("optimizer", WARN,
                     f"no optimizer CLI on PATH{tail}",
                     "a real run needs an agent CLI (Claude Code, codex, gemini-cli, ...); "
                     "for a zero-API run set `optimizer_skill: mock` in capevolve.yaml")
    return Check("optimizer", PASS, f"on PATH: {', '.join(sorted(on_path))}" + tail)


def _dotenv_names(cwd: Path) -> set[str]:
    """Variable NAMES declared in the nearest repo-root ``.env`` (INSTALL.md tells users
    to put credentials there, and ``run-optimizer/scripts/run.py`` reads it).

    Only the left-hand side is ever returned — the value after ``=`` is not even sliced
    out, so there is nothing here for a leak to carry.
    """
    for parent in [cwd.resolve(), *cwd.resolve().parents]:
        f = parent / ".env"
        if f.is_file():
            names = set()
            try:
                for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        names.add(line.split("=", 1)[0].strip().removeprefix("export "))
            except OSError:  # pragma: no cover — unreadable .env is not a doctor failure
                pass
            return names
    return set()


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

    dotenv = _dotenv_names(cwd)
    seen: set[str] = set()
    set_names, unset_names, partial = [], [], []
    def _here(k: str) -> bool:
        # bool() of presence only — the VALUE is never read into any reported field.
        return bool(os.environ.get(k)) or k in dotenv

    for _, keys in groups:
        for k in keys:
            if k in seen:
                continue
            seen.add(k)
            if _here(k):
                set_names.append(k if os.environ.get(k) else f"{k} (.env)")
            else:
                unset_names.append(k)
    for group in _REQUIRED_TOGETHER:
        missing = [k for k in group if not _here(k)]
        if missing and len(missing) < len(group):
            partial.append(f"{', '.join(k for k in group if _here(k))} set but "
                           f"{', '.join(missing)} absent")
    if not set_names:
        return Check("credentials", WARN, "no provider credentials in the environment or .env",
                     "the toy example needs none; a real run needs the optimizer CLI's creds "
                     "plus runner creds in a repo-root .env — see "
                     "docs/INSTALL.md#credentials-only-for-real-runs",
                     absent=unset_names)
    if partial:
        return Check("credentials", WARN,
                     f"{len(set_names)} set, {len(unset_names)} absent — "
                     f"incomplete group(s): {'; '.join(partial)}",
                     "these providers need every var in the group; set the missing ones — "
                     "see docs/INSTALL.md#credentials-only-for-real-runs",
                     present=set_names, absent=unset_names)
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


def _summarize_untrusted(texts: list[str], limit: int = 160) -> str:
    """Bound and de-identify third-party text before it can reach stdout.

    ``check.run_check``'s problems embed ``str(e)`` from arbitrary user adapter code, so
    their content is attacker/accident-controlled — an adapter that raises
    ``RuntimeError(f"auth failed for {os.environ['OPENAI_API_KEY']}")`` would otherwise
    print the key verbatim, and shape-based redaction cannot catch every credential
    format. So: never echo untrusted text in full. Keep a short, redacted excerpt for
    orientation and point at the file with the whole thing.

    Redaction runs BEFORE truncation: cutting first can slice a secret mid-value, and a
    partial prefix no longer matches any rule — so a truncated fragment would survive the
    ``format_report`` pass. Redact, then bound.
    """
    out = []
    for t in texts:
        t = " ".join(str(redact(str(t))).split())
        out.append(t if len(t) <= limit else t[:limit] + f"… (+{len(t) - limit} chars)")
    return "; ".join(out)


def _check_project(cwd: Path) -> Check:
    project = cwd / ".capevolve" / "project"
    adapter = project / "adapters" / "adapter.py"
    if not adapter.exists():
        if project.is_dir():
            # A scaffolded-but-adapterless project is a BROKEN project, not "no project".
            return Check("project", FAIL, f"{project} exists but adapters/adapter.py is missing",
                         "scaffold incomplete — implement adapters/adapter.py "
                         "(see docs/ADAPTER_CONTRACT.md), then `cap-evolve check "
                         f"{project}` must print {{\"ok\": true}}")
        return Check("project", PASS, "not inside a cap-evolve project (nothing to validate)")
    from .check import run_check
    rep = run_check(project)
    if rep.ok:
        return Check("project", PASS, f"{project} — cap-evolve check green; "
                     + _summarize_untrusted(list(rep.notes), limit=400))
    # Write the FULL untrusted detail to a local file the user can inspect themselves,
    # and print only a bounded excerpt. The report is what gets pasted into issues.
    full = "\n".join(str(p) for p in rep.problems)
    where = ""
    try:
        log = project / "doctor-check.log"
        log.write_text(full + "\n", encoding="utf-8")
        where = f" — full adapter output in {log} (inspect locally; may contain secrets)"
    except OSError:  # pragma: no cover — unwritable project dir is reported by run-dir
        pass
    return Check("project", FAIL,
                 f"{project} — cap-evolve check failed: "
                 + _summarize_untrusted(list(rep.problems)) + where,
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
