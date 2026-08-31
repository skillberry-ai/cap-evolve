"""The ``intervention:`` spec field — HOW a candidate reaches the model under test.

``capabilities:`` says WHAT gets edited. ``intervention:`` says how the edited artifact is
delivered:

* ``direct`` (default, and every pre-existing spec) — the runner reads the artifact from
  disk or its own config. Nothing extra happens; this module is a no-op.
* ``spa`` — the artifact lives in the Skillberry Store and the Skillberry Proxy-Agent
  injects it into the agent's LLM calls. The stack that makes that possible is a
  ``component: intervention`` skill (``skills/interventions/llm-proxies/spa/``), and a run must not begin
  unless it is actually up.

Two things this module exists to prevent:

1. **A silent typo.** The spec is read as a plain dict via ``spec.get(...)`` with no
   unknown-key or unknown-value rejection anywhere, so ``intervention: sap`` would otherwise
   be ignored and the run would proceed in ``direct`` mode against a stack nobody wired
   — producing numbers that look like an answer. Every value is validated by name.
2. **A run that cannot possibly work.** Without the stack, every candidate's deployment
   fails, and because a failed deployment is *correctly* treated as per-candidate infra
   noise, the run does not crash: it quietly errors every rollout and finishes having
   measured nothing. One preflight up front, naming what is wrong, is worth more than
   that whole run.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

DIRECT = "direct"
SPA = "spa"
KNOWN = (DIRECT, SPA)


class InterventionError(RuntimeError):
    """An intervention that is misdeclared, missing, or not ready."""


def declared(spec: dict) -> str:
    """The validated ``intervention`` value for this spec (``direct`` when absent).

    Raises on an unknown value rather than falling back: a fallback here is exactly the
    failure mode described in this module's docstring.
    """
    raw = spec.get("intervention")
    if raw is None or str(raw).strip() == "":
        return DIRECT
    val = str(raw).strip().lower()
    if val not in KNOWN:
        raise InterventionError(
            f"unknown intervention {raw!r} in the spec. Valid values: {', '.join(KNOWN)}. "
            f"(A run with an unrecognised intervention would silently deliver candidates the "
            f"{DIRECT} way, so this is refused rather than defaulted.)")
    return val


def skill_dir(intervention: str, skills: dict, skills_dir: Path) -> Path:
    """Where the intervention skill lives, from the manifest.

    Looked up by name AND asserted to be ``component: intervention`` — a name collision with
    a capability or phase would otherwise hand us the wrong skill.
    """
    row = skills.get(intervention)
    if not row:
        raise InterventionError(
            f"intervention {intervention!r} is declared but no such skill is registered. Run "
            "`python skills/_registry/build_manifest.py skills` and check "
            f"skills/interventions/**/{intervention}/meta.yaml exists.")
    if row.get("component") != "intervention":
        raise InterventionError(
            f"skill {intervention!r} is component {row.get('component')!r}, not 'intervention'")
    return skills_dir / row["path"]


def _load_spa_env(intervention_dir: Path):
    """Import the SPA intervention's library from its skill dir, without polluting sys.path.

    Loaded by file location rather than by name so this works from any cwd and does not
    depend on the skills dir being importable.
    """
    mod_path = intervention_dir / "scripts" / "spa_env.py"
    if not mod_path.exists():
        raise InterventionError(f"intervention library not found at {mod_path}")
    scripts = str(intervention_dir / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec_ = importlib.util.spec_from_file_location("spa_env", mod_path)
    module = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(module)
    return module


def preflight(spec: dict, skills: dict, skills_dir: Path) -> dict:
    """Verify the declared intervention is ready, and return a record for the run metadata.

    ``direct`` is always ready. For ``spa``: the services must be provisioned and
    healthy; an already-provisioned but stopped stack is STARTED here, because that is
    recoverable and a human would only run the same two calls by hand. Provisioning is
    NOT done here — cloning and installing two services is minutes of network and
    gigabytes of disk, which is an onboarding step (the example's setup.sh), not
    something a run should do behind your back.

    Raises ``InterventionError`` with an actionable message when the intervention cannot be made
    ready. Never returns a "sort of ready" state.
    """
    rt = declared(spec)
    if rt == DIRECT:
        return {"intervention": DIRECT}

    d = skill_dir(rt, skills, skills_dir)
    env = _load_spa_env(d)

    st = env.status()
    missing = [n for n in ("store", "spa") if not st[n]["provisioned"]]
    if missing:
        raise InterventionError(
            f"intervention 'spa' is declared but {', '.join(missing)} is not provisioned "
            f"(expected under {env.vendor_dir()}). Run the example's setup.sh first — "
            "provisioning clones and installs two services, which a run deliberately "
            "does not do on your behalf.")

    # A port held by something that is NOT our service is a different problem from a
    # stopped service, and the fix differs, so say which one it is.
    for name in ("store", "spa"):
        r = st[name]
        if not r["healthy"] and r["pids"] and not r["ours"]:
            raise InterventionError(
                f"port {r['port']} is held by PID(s) {r['pids']}, which are not the "
                f"{name} service. Free the port and retry.")

    skill_name = str(spec.get("skill_name") or "").strip()
    if not st["spa"]["healthy"] and not skill_name:
        raise InterventionError(
            "intervention 'spa' needs `skill_name:` in the spec to start the proxy-agent: SPA "
            "serves exactly one skill, and with no name it falls back to searching the "
            "store — which succeeds silently even when the store is empty.")

    if not st["store"]["healthy"]:
        env.start_store()
    if not st["spa"]["healthy"]:
        env.start_spa(skill_name)

    st = env.status()
    for name in ("store", "spa"):
        if not st[name]["healthy"]:
            raise InterventionError(f"intervention 'spa': {name} is not healthy on port "
                                f"{st[name]['port']} after a start attempt")

    rec = {
        "intervention": rt,
        "skill_dir": str(d),
        "skill_name": skill_name or None,
        "store_port": st["store"]["port"],
        "spa_port": st["spa"]["port"],
        "remote_env": st["remote_env"]["url"] or None,
        "remote_env_healthy": st["remote_env"]["healthy"],
    }
    # The benchmark owns its environment service, so a missing one is a warning, not a
    # failure: not every benchmark has one, and only its own tools would notice.
    if st["remote_env"]["url"] and not st["remote_env"]["healthy"]:
        rec["warning"] = (f"remote environment {st['remote_env']['url']} is not reachable; "
                          "store-hosted tools that call it will fail")
    return rec


def describe(rec: dict) -> str:
    """One human line for the run's stderr preamble."""
    if rec.get("intervention", DIRECT) == DIRECT:
        return "intervention: direct (candidate delivered as files)"
    bits = [f"intervention: {rec['intervention']}",
            f"store :{rec.get('store_port')}", f"proxy :{rec.get('spa_port')}"]
    if rec.get("skill_name"):
        bits.append(f"skill={rec['skill_name']}")
    if rec.get("remote_env"):
        bits.append(f"env={rec['remote_env']}"
                    f"{'' if rec.get('remote_env_healthy') else ' (UNREACHABLE)'}")
    return " | ".join(bits)
