"""The helper gate: one shared check of a candidate's helper scripts, run before any rollout is paid for.

When helpers are on (``helpers.enabled``, or ``CAPEVOLVE_HELPERS``), a candidate may carry executable helper code
(``skills/*/scripts`` and the other ``surface.executable_dirs``). Code that hard-codes task ids, reads gold paths or
does not even import must be refused before it is measured, on every path that proposes candidates, with the same
rules. This module is that single rule set; every caller (the agent-optimize pregate and conductor today) calls it
instead of keeping its own copy.

The gate runs three checks, always all three in this order, so every path reports the same findings:

* ``helper_surface``: ``helpers.surface_problems`` against the SEED (executable files outside the declared dirs,
  symlinks, size caps; a file byte-identical to the seed's is not the candidate's doing).
* ``helper_lint``: ``helpers.lint_candidate`` against the PARENT (task ids, answer literals, task-identity branches,
  network use, protected paths; only files new or changed since the parent).
* ``helper_smoke``: ``helper_smoke.run_smoke`` against the PARENT (each changed helper imports, and replays its
  recorded fixtures deterministically, in a subprocess that cannot read ``deny_roots``).

On by default: the gate is active whenever helpers are on. It is off only when switched off explicitly, by
``helpers.gate: false`` in the spec or ``CAPEVOLVE_HELPER_GATE=0`` (env wins). ``off_reason`` says which, so a caller
can warn and record it: a run with helpers but no gate must be visible in its results.

A gate that is on but cannot run (an unreadable ``ids_file``, a declared ``fixtures`` file that is missing, a missing
seed dir) raises ``GateConfigError``. That is the run's fault, never a candidate's: callers must stop rather than
fail open, because failing open would run the experiment with the check silently off.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from . import helper_smoke, helpers

ENV = "CAPEVOLVE_HELPER_GATE"
CHECKS = ("helper_surface", "helper_lint", "helper_smoke")


class GateConfigError(RuntimeError):
    """The helper gate is on but cannot run its checks. The run's fault: stop the run, do not fail open."""


def _env_gate():
    raw = os.environ.get(ENV, "").strip().lower()
    if not raw:
        return None
    if raw in helpers._TRUE | helpers._FALSE:
        return raw in helpers._TRUE
    raise GateConfigError(f"{ENV}={raw!r}: expected one of {sorted(helpers._TRUE | helpers._FALSE)}")


def active(cfg: dict | None) -> bool:
    """True when helpers are on (``cfg`` from ``helpers.resolve``) and the gate was not switched off."""
    if not cfg or not cfg.get("enabled"):
        return False
    env = _env_gate()
    return bool(cfg.get("gate", True)) if env is None else env


def off_reason(cfg: dict | None) -> str | None:
    """Why the gate is off although helpers are on, or None (helpers off, or the gate on). For the warning."""
    if not cfg or not cfg.get("enabled") or active(cfg):
        return None
    return f"{ENV}=0" if _env_gate() is False else "helpers.gate: false"


def check_config(cfg: dict | None, *, seed: Path | None = None) -> None:
    """Raise ``GateConfigError`` when an active gate cannot run its checks. Call it once, before the first
    candidate; ``gate`` calls it too, so a file that disappears mid-run is reported, not skipped."""
    if not active(cfg):
        return
    ids_file = cfg.get("ids_file")
    if ids_file:
        try:
            Path(ids_file).read_text(encoding="utf-8")
        except OSError as e:
            raise GateConfigError(f"helpers.ids_file={ids_file!r} cannot be read: {e}") from e
    fixtures = cfg.get("fixtures")
    if fixtures and not Path(fixtures).is_file():
        raise GateConfigError(f"helpers.fixtures={fixtures!r} does not exist")
    if seed is not None and not Path(seed).is_dir():
        raise GateConfigError(f"seed capability dir {str(seed)!r} does not exist")


def _check(name, ok, detail="", skipped=False, **extra) -> dict:
    return {"name": name, "ok": bool(ok), "detail": detail, "skipped": skipped, **extra}


def enabled_checks(cfg: dict) -> list[str]:
    """The checks an active gate runs for this config, in order (``lint``/``smoke`` can be turned off)."""
    return [c for c in CHECKS
            if c == "helper_surface" or cfg.get(c.removeprefix("helper_"), True)]


def run_check(name: str, cand: Path, cfg: dict, *, parent: Path | None = None, seed: Path | None = None,
              traces=()) -> dict:
    """One gate check as a ``{name, ok, detail, skipped, ...}`` dict. Exceptions propagate (see ``gate``)."""
    cand = Path(cand)
    if name == "helper_surface":
        p = helpers.surface_problems(cand, cfg, seed)
        return _check(name, not p, "; ".join(p))
    if name == "helper_lint":
        r = helpers.lint_candidate(cand, cfg, parent)
        return _check(name, r["ok"], "; ".join(r["findings"][:8]), files=r["files"])
    if name == "helper_smoke":
        rows = helper_smoke.load_fixtures(Path(cfg["fixtures"]) if cfg.get("fixtures") else None, traces)
        r = helper_smoke.run_smoke(cand, cfg, parent=parent, fixtures=rows)
        return _check(name, r["ok"], r["detail"], skipped=r["skipped"], runs=r["runs"])
    raise ValueError(f"unknown helper gate check {name!r}; known: {list(CHECKS)}")


def gate(cand: Path, cfg: dict | None, *, parent: Path | None = None, seed: Path | None = None,
         traces=()) -> dict:
    """Run the gate on ``cand``: ``{ok, checks, failure}``. ``ok`` with no checks when the gate is not active.

    ``parent`` is the candidate's own parent (the bytes it was edited from); ``seed`` is the run's seed snapshot;
    ``traces`` are rollout files whose recorded helper calls become smoke fixtures (the proposer's own feedback
    rollouts only). Raises ``GateConfigError`` on a config problem; any other exception from a check propagates,
    and the caller decides how a broken check is reported.
    """
    if not active(cfg):
        return {"ok": True, "checks": [], "failure": ""}
    check_config(cfg, seed=seed)
    checks = [run_check(n, cand, cfg, parent=parent, seed=seed, traces=traces) for n in enabled_checks(cfg)]
    failed = [c for c in checks if not c["ok"]]
    return {"ok": not failed, "checks": checks,
            "failure": "; ".join(f"[{c['name']}] {c['detail']}" for c in failed)}


# ---- the gate inside a run ---------------------------------------------------------------------------

_WARNED: set[str] = set()


def requested(spec: dict | None) -> bool:
    """True when this run asks for helpers: ``CAPEVOLVE_HELPERS`` if set, else ``helpers.enabled`` in the spec.

    Checked before anything else, so a run without helpers (the default, and every run before the gate existed)
    is untouched: no ``helpers.resolve``, no event, nothing that can raise, even when its spec carries a disabled
    ``helpers:`` table that ``resolve`` would refuse. ``helpers.resolve`` makes the same decision for ``enabled``;
    an unparseable ``CAPEVOLVE_HELPERS`` is left to it, which raises (someone meant to set it)."""
    raw = os.environ.get("CAPEVOLVE_HELPERS", "").strip().lower()
    if raw in helpers._FALSE:
        return False
    if raw:
        return True
    tbl = spec.get("helpers") if isinstance(spec, dict) else None
    return bool(tbl.get("enabled")) if isinstance(tbl, dict) else False


def _warn_if_spec_unreadable(run_dir, project) -> None:
    """``spec_for_run`` returns ``{}`` for a spec it cannot parse, which reads as "helpers off". When the run's spec
    file exists and has content, say so once: a gate that the spec turned on must not go off without a trace."""
    from .specfile import resolve_spec_path
    key = f"{run_dir.root}:spec"
    if key in _WARNED:
        return
    path = resolve_spec_path(run_dir, project)
    try:
        # content = any line that is not blank and not a YAML comment: a spec of comments only parses to {} too
        has_text = path is not None and any(ln.strip() and not ln.lstrip().startswith("#")
                                            for ln in path.read_text(encoding="utf-8").splitlines())
    except OSError:
        has_text = True
    if has_text:
        _WARNED.add(key)
        run_dir.log_event("helper_gate_spec_unreadable", spec=str(path))
        print(f"cap-evolve: WARNING: the run's spec {str(path)!r} cannot be read or parsed; the helper gate treats "
              "this run as having no helpers (set CAPEVOLVE_HELPERS to decide it explicitly)", file=sys.stderr)


def for_run(run_dir, project: Path | None = None) -> dict | None:
    """The run's resolved helper config when the gate is active, else None.

    The config comes from the spec THIS run was started with (``specfile.spec_for_run``), so every algorithm
    reads the same one. When helpers are on but the gate is off, a ``helper_gate_off`` event is logged and a
    warning printed, once per run, so the results show the run had no gate. Raises ``GateConfigError`` when the
    gate cannot run, and ``ValueError`` on an invalid ``helpers:`` table (``helpers.resolve``)."""
    from .specfile import spec_for_run
    spec = spec_for_run(run_dir, project)
    if not isinstance(spec, dict) or not spec:
        _warn_if_spec_unreadable(run_dir, project)
    if not requested(spec):
        return None
    cfg = helpers.resolve(spec)
    why = off_reason(cfg)
    if why and str(run_dir.root) not in _WARNED:
        _WARNED.add(str(run_dir.root))
        run_dir.log_event("helper_gate_off", reason=why)
        print(f"cap-evolve: WARNING: helpers are on but the helper gate is off ({why}); "
              "candidates' helper scripts are not checked in this run", file=sys.stderr)
    if not active(cfg):
        return None
    check_config(cfg)
    return cfg


class Refusal:
    """A candidate the gate refused, in the report shape the loop's indecisive-step path records."""

    def __init__(self, result: dict):
        self.result = result

    @property
    def reason(self) -> str:
        return "the helper gate refused the candidate's helper scripts: " + self.result["failure"]

    def to_dict(self) -> dict:
        return dict(self.result)


def check_candidate(run_dir, cand: Path, *, parent_dir: Path | None = None, parent_id: str | None = None,
                    project: Path | None = None) -> Refusal | None:
    """Run the gate on one proposed candidate before any rollout of it is paid for; a ``Refusal``, or None.

    ``parent_dir``/``parent_id``: the bytes the candidate was edited from. The seed is the run's own seed
    snapshot. Smoke fixtures come from the parent's rollouts in the feedback splits only
    (``helpers.fixture_splits``). Each verdict is logged as a ``helper_gate`` event. Raises
    ``GateConfigError`` when the gate cannot run."""
    cfg = for_run(run_dir, project)
    if cfg is None:
        return None
    traces = (helper_smoke.fixture_traces(run_dir.rollouts, parent_id or "seed", cfg["fixture_splits"])
              if cfg.get("smoke", True) else [])
    res = gate(cand, cfg, parent=parent_dir, seed=run_dir.candidate_dir("seed"), traces=traces)
    run_dir.log_event("helper_gate", candidate=Path(cand).name, parent=parent_id, ok=res["ok"],
                      checks={c["name"]: c["ok"] for c in res["checks"]}, failure=res["failure"][:500])
    return None if res["ok"] else Refusal(res)
