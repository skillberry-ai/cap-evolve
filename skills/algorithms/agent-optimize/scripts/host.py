"""host.py — drive this skill's loop from a NON-INTERACTIVE caller (CI, cron, a script).

agent-optimize's loop is prose in ``SKILL.md``, executed by the conversational agent that
ran intake. ``cap-evolve run`` (agent mode) does check + baseline, prints a handoff, and
returns: no algorithm subprocess, no auto-finalize. That is exactly right with a human in
the loop and leaves the algorithm *unavailable* anywhere without one — a CI job gets the
handoff and then nothing happens.

This script is the missing host, and deliberately owns as little as possible:

  * the **loop** stays in ``SKILL.md`` + this dir's helpers. The briefing points at them; it
    does not restate the algorithm, because a second copy of the loop would drift from the
    first and there would be no way to tell which one ran.
  * the **CLI invocation** is delegated to ``optimizers/run-optimizer``, which already
    resolves a registry row, substitutes ``{model}``, maps ``--budget``/``--usd-budget`` to
    that CLI's own flags, captures cost from its JSON output, and hard-fails when the CLI
    is absent. Re-implementing any of that here would be a second, worse copy.

What is genuinely this script's own:

**A raised Bash-tool ceiling.** Every loop command is a shell call, and a full-val eval on
a real benchmark runs for hours. Claude Code caps one Bash call at ``BASH_MAX_TIMEOUT_MS``
(default 600000 = 10 min) and the effective ceiling is ``max(default, max)``, so both are
raised. Left alone, every eval is killed mid-flight and an entirely healthy run reads as a
broken runner.

**A guaranteed seal.** An agent that exhausts its turns or dies mid-loop leaves no
``final.json``. CI then cannot distinguish "stopped early" from "a step crashed", and there
is no honest number at all. So if the agent did not seal, the host does — through the same
``measure.py`` the skill documents, labelled ``seal: host`` so nobody mistakes it for the
agent's own judgement that it was finished.

The seal is idempotent: an already-sealed run reports ``seal: agent`` rather than raising
``TestSealError`` out of the host and failing a run that is actually complete.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import _bootstrap  # noqa: F401

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
SKILLS = SKILL_DIR.parents[1]
RUN_OPTIMIZER = SKILLS / "optimizers" / "run-optimizer" / "scripts" / "run.py"
REGISTRY = SKILLS / "optimizers" / "registry.yaml"

# 4h. Long enough for a full-val eval on the slowest benchmark in this repo
# (spreadsheetbench full: one Docker container per task x trials), while still bounding a
# genuinely hung command instead of waiting forever.
BASH_TIMEOUT_MS = 4 * 60 * 60 * 1000


def _spec(project: Path, spec_path: Path | None) -> dict:
    from cap_evolve.specfile import read_yaml

    path = spec_path or (project / "capevolve.yaml")
    if not path.exists():
        return {}
    return read_yaml(path.read_text(encoding="utf-8")) or {}


def _known_agents() -> list[str]:
    from cap_evolve.specfile import read_yaml

    try:
        return sorted((read_yaml(REGISTRY.read_text(encoding="utf-8")) or {}).keys())
    except Exception:  # noqa: BLE001 — a missing registry is reported by the caller below
        return []


def _editable_files(run_dir: Path, project: Path, spec: dict) -> list[str]:
    """The capability's real files, relative — the surface the agent may actually edit.

    ``capabilities`` names which capability skills' ``validate()`` runs; it does NOT restrict
    what may be written. Handing the agent only those names is what leaves most of the
    surface untouched: in one measured run a spec declaring both a prompt capability and a
    tool-code capability produced 2 of 2 candidates that edited only the prompt file, while
    the tool code sat writable and unopened in the same candidate dir.

    Read from the materialized seed candidate (what the agent copies and edits) rather than
    from the project's capability_path, so this is the same file set it will really see.
    """
    root = run_dir / "candidates" / "seed"
    if not root.is_dir():
        cap = str(spec.get("capability_path") or "seed_capability")
        root = (project / cap).resolve()
    if not root.is_dir():
        return []
    skip_dirs = {"__pycache__", ".git"}
    files = [
        p.relative_to(root).as_posix()
        for p in sorted(root.rglob("*"))
        if p.is_file()
        and not any(part in skip_dirs for part in p.parts)
        and p.suffix not in {".pyc", ".pyo"}
    ]
    return files


def _surface_section(files: list[str]) -> str:
    """Render the editable-file list, and say what a prompt-only edit leaves undone.

    Scaled to what is actually there: naming tool code for a capability that has none sends
    the agent hunting outside its capability for code to change.
    """
    if not files:
        return ""
    listing = "\n".join(f"- `{f}`" for f in files)
    if len(files) == 1:
        return (f"## Your editable surface — one file\n\n{listing}\n\n"
                "That file is the whole capability. There is no tool code and no second "
                "surface, so do not go looking for one outside it.\n")
    return (
        f"## Your editable surface — ALL {len(files)} of these files\n\n{listing}\n\n"
        "Every one of them is in your candidate copy and every one is fair game — prose, "
        "code, data, nested files alike. A round that changes **only the obvious prompt "
        "file** leaves the rest of the agent's instruction and behaviour surface exactly as "
        "it was, and that is the most common way a run produces nothing: the fix that was "
        "needed lived in a file nobody opened.\n\n"
        "So before you write an edit, decide *which file* is the right place for it — a rule "
        "the agent already has and violates usually belongs in code as a guard, while a "
        "missing decision criterion belongs in prose. Say which file you chose, and why that "
        "one, when you commit the round.\n")


def _briefing(*, run_dir: Path, project: Path, spec: dict, skills: Path,
              rounds: int) -> str:
    """The driver briefing: the handoff facts, then a pointer to the loop itself.

    Deliberately NOT a restatement of the algorithm. SKILL.md is the implementation and the
    agent reads it; what it cannot know are the paths, the spec values and the fact that
    nobody is available to answer a question.
    """
    stop = str(spec.get("stop_condition") or "").strip()
    n_trials = spec.get("num_trials", 1)
    k_se = spec.get("gate_k_se", 1.0)
    gate_mode = spec.get("gate_mode", "paired")
    caps = spec.get("capabilities") or []
    cap_path = spec.get("capability_path") or "seed_capability"
    surface = _surface_section(_editable_files(run_dir, project, spec))
    skill_md = SKILL_DIR / "SKILL.md"
    helpers = HERE

    if not stop:
        stop = (f"Spend at most {rounds} rounds, gate every candidate on FULL val, and "
                "finish by sealing test exactly once with measure.py.")

    return f"""# Drive the agent-optimize loop on an existing run — unattended

You are the optimizer for a cap-evolve run that is ALREADY set up and baselined.
`cap-evolve run` finished check + baseline and handed the loop over. Your job is to run the
`agent-optimize` loop against it and finish with one honest sealed measurement.

## Read this first

`{skill_md}`

That file IS the algorithm — its "Agent-mode loop" section is what you execute, step by
step, including Phase 0. Its helper scripts are in `{helpers}`. Do not re-derive the loop
from this briefing; this briefing only gives you the facts SKILL.md cannot know.

## The handoff

```bash
R="{run_dir}"      # the run dir: splits, baseline, candidates, rollouts, events
P="{project}"      # the project: capevolve.yaml, adapters/, {cap_path}
S="{skills}"       # the skills dir (CAPEVOLVE_SKILLS_DIR is already set to it)
A="$S/algorithms/agent-optimize/scripts"
mkdir -p "$R/work"
```

Paths are absolute; use them as given rather than relative paths, because your working
directory is not necessarily either of theirs.

## The spec values your gate needs

| key | value |
| --- | --- |
| `num_trials` | {n_trials} |
| `gate_k_se` | {k_se} |
| `gate_mode` | {gate_mode} |
| `capabilities` (which capability rules validate your edits) | {caps} |
| `capability_path` | {cap_path} |

Pass these explicitly — `--n-trials {n_trials}` on every evaluate, `--k-se {k_se}` on every
gate — rather than relying on a default that may not match this spec.

{surface}

## The primitives every round must go through

SKILL.md says why; this is the checklist, because nobody is watching and a round that
skipped one leaves artifacts that cannot be audited afterwards:

| helper | per round | what it is for |
| --- | --- | --- |
| `$A/spend.py` | before | affordability + your stop condition as checkable predicates |
| `$A/gate_check.py` | after the full-val eval | the paired significance gate — the accept decision |
| `$A/commit.py` | always, accept or reject | books the decision: snapshot, best_id, iteration, event |
| `$A/measure.py` | once, at the end | seals test exactly once and prints the honest table |

`commit.py` is the one most easily skipped on a reject, and skipping it is what makes a run
report zero iterations having done real work. `screen.py` and `round.py` are optional
accelerators; the four above are not.

## Your stop condition

{stop}

`spend.py` parses that text into checkable predicates; run it before each round and act on
its single `recommendation` (`stop` | `narrow_scope` | `continue`), as SKILL.md describes.

## Unattended — this is the one real difference from an interactive run

**Nobody is available to answer a question. Do not ask any; do not wait for input.** Where
SKILL.md's Phase 0 says to ask the user about a blocking ambiguity (including
`constraints.ambiguous` from `spend.py`), instead: pick the most conservative reading, state
the assumption in one line in your final summary, and proceed. A round spent on a
conservative assumption is worth far more than a run that stalls waiting for a reply.

Two consequences worth being explicit about:

1. **Never leave the run unsealed.** Finish with `measure.py` (which seals test exactly
   once) and the report phase, as SKILL.md's "Stop & seal" section shows. A run with no
   finalize has no result. If you are running out of budget, stop optimizing and seal —
   sealing what you have beats one more candidate.
2. **A null result is a valid outcome, honestly reported.** If nothing beat the baseline
   through the gate, say so and seal anyway. Do not lower the gate, gate on a screen
   subset, or present a screen `promote` as an accept to manufacture a gain.

## When you are done

Finish your final message with the run's honest table: seed vs best on val, on train if it
adds information, and on the sealed test split — plus the accepted candidate id, the number
of rounds, and any assumption you had to make on your own.
"""


def _seal(run_dir: Path, project: Path, spec: dict, *, timeout: float | None) -> dict:
    """Ensure the run has a sealed test number. Idempotent.

    Returns ``{"sealed": bool, "seal": "agent"|"host"|"failed", ...}``. ``agent`` means
    final.json was already there when the host looked — the normal, desired outcome.
    """
    final = run_dir / "final.json"
    if final.exists():
        return {"sealed": True, "seal": "agent"}

    n_trials = int(spec.get("num_trials", 1) or 1)
    cmd = [sys.executable, str(HERE / "measure.py"), "--run-dir", str(run_dir),
           "--project", str(project), "--n-trials", str(n_trials), "--train", "auto"]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                       env=_child_env())
    if final.exists():
        return {"sealed": True, "seal": "host", "measure_rc": p.returncode}
    return {"sealed": False, "seal": "failed", "measure_rc": p.returncode,
            "measure_error": (p.stderr or p.stdout)[-1200:]}


def _child_env() -> dict:
    env = dict(os.environ)
    env.setdefault("CAPEVOLVE_SKILLS_DIR", str(SKILLS))
    return env


def _agent_env(model: str | None) -> dict:
    """The environment the hosted agent runs in — reported so a test can assert it."""
    env = {
        "CAPEVOLVE_SKILLS_DIR": str(SKILLS),
        # Both, because the effective ceiling is max(default, max): raising only one leaves
        # the other as the real limit.
        "BASH_DEFAULT_TIMEOUT_MS": str(BASH_TIMEOUT_MS),
        "BASH_MAX_TIMEOUT_MS": str(BASH_TIMEOUT_MS),
    }
    if model:
        env["CAPEVOLVE_OPTIMIZER_MODEL"] = model
    return env


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="host.py",
        description="Drive the agent-optimize loop headlessly against a baselined run dir.")
    p.add_argument("--run-dir", required=True, help="run dir from the agent-mode handoff")
    p.add_argument("--project", required=True, help="project dir (capevolve.yaml, adapters/)")
    p.add_argument("--spec", default=None,
                   help="spec file; defaults to <project>/capevolve.yaml")
    p.add_argument("--agent", default="claude-code",
                   help="host agent: a row in optimizers/registry.yaml (default claude-code)")
    p.add_argument("--model", default=None, help="model for the host agent")
    p.add_argument("--budget", type=int, default=None,
                   help="whole-loop turn cap, mapped to the CLI's own budget flag")
    p.add_argument("--usd-budget", type=float, default=None,
                   help="whole-loop $ cap, mapped to the CLI's native flag where it has one")
    p.add_argument("--timeout", type=float, default=None,
                   help="wall-clock seconds for the hosted agent (default: none)")
    p.add_argument("--prompt-only", action="store_true",
                   help="render the briefing and exit without invoking the agent")
    p.add_argument("--seal-only", action="store_true",
                   help="skip the agent; only ensure the run has a sealed test number")
    args = p.parse_args(argv)

    run_dir = Path(args.run_dir).resolve()
    project = Path(args.project).resolve()
    if not run_dir.is_dir():
        print(json.dumps({"error": f"run dir not found: {run_dir}",
                          "fix": "pass the run_dir from the agent-mode handoff printed by "
                                 "`cap-evolve run`"}, indent=2))
        return 2
    if not project.is_dir():
        print(json.dumps({"error": f"project dir not found: {project}"}, indent=2))
        return 2

    spec = _spec(project, Path(args.spec).resolve() if args.spec else None)
    rounds = int(spec.get("max_iterations", 0) or 0) or 10

    if args.seal_only:
        out = _seal(run_dir, project, spec, timeout=args.timeout)
        print(json.dumps({"run_dir": str(run_dir), "seal_only": True, **out}, indent=2))
        return 0 if out["sealed"] else 1

    # Refuse an unknown host agent BEFORE anything is spent. The registry is where a host
    # agent is actually added, so name it in the fix.
    known = _known_agents()
    if known and args.agent not in known:
        print(json.dumps({
            "error": f"unknown host agent: {args.agent!r}",
            "known": known,
            "fix": f"pass --agent with one of the rows in {REGISTRY}, or add a row there "
                   "(one row per shell-invokable agent CLI — no new code needed)",
        }, indent=2))
        return 2

    prompt_dir = run_dir / "host"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = prompt_dir / "driver_prompt.md"
    prompt_path.write_text(
        _briefing(run_dir=run_dir, project=project, spec=spec, skills=SKILLS, rounds=rounds),
        encoding="utf-8")

    agent_env = _agent_env(args.model)
    if args.prompt_only:
        print(json.dumps({"run_dir": str(run_dir), "agent": args.agent,
                          "model": args.model, "prompt_only": True,
                          "prompt_path": str(prompt_path), "returncode": None,
                          "agent_env": agent_env, "budget": args.budget,
                          "usd_budget": args.usd_budget}, indent=2))
        return 0

    # Delegate the invocation. --json switches on run-optimizer's cost capture, which is how
    # the host's own spend reaches the run dir at all: the evaluate phase records the
    # runner's cost, and nothing records the proposer's.
    cmd = [sys.executable, str(RUN_OPTIMIZER), "--name", args.agent, "--json",
           # The agent needs write access to BOTH the run dir and the project; their common
           # parent is the natural workdir. Every path in the briefing is absolute anyway.
           "--workdir", str(_common_parent(run_dir, project)),
           "--prompt", str(prompt_path)]
    if args.model:
        cmd += ["--model", args.model]
    if args.budget:
        cmd += ["--budget", str(int(args.budget))]
    if args.usd_budget:
        cmd += ["--usd-budget", str(float(args.usd_budget))]

    started = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout,
                              env={**_child_env(), **agent_env})
        timed_out = False
    except subprocess.TimeoutExpired:
        proc = None
        timed_out = True
    seconds = time.time() - started

    payload: dict = {}
    if proc is not None:
        try:
            payload = json.loads(proc.stdout)
        except Exception:  # noqa: BLE001 — a non-JSON tail is reported, not fatal
            payload = {"stdout_tail": (proc.stdout or "")[-1200:]}

    usd = float(payload.get("cost_usd") or payload.get("usd") or 0.0)
    tokens = int(payload.get("tokens") or 0)

    # Book the host's own spend. The agent books per-round costs it knows about through
    # commit.py --optimizer-usd; it cannot know its own process cost, and the host can.
    try:
        from cap_evolve import RunDir

        rd = RunDir.open(run_dir)
        rd.log_event("host", agent=args.agent, model=args.model or "",
                     usd=usd, tokens=tokens, seconds=round(seconds, 3),
                     returncode=(None if proc is None else proc.returncode),
                     timed_out=timed_out)
        if usd or tokens:
            rd.update_spent(optimizer_usd=usd, optimizer_tokens=tokens)
    except Exception as exc:  # noqa: BLE001 — spend accounting must not lose the run
        payload.setdefault("warnings", []).append(f"could not book host spend: {exc}")

    seal = _seal(run_dir, project, spec, timeout=args.timeout)

    out = {
        "run_dir": str(run_dir),
        "agent": args.agent,
        "model": args.model,
        "prompt_path": str(prompt_path),
        "returncode": None if proc is None else proc.returncode,
        "timed_out": timed_out,
        "seconds": round(seconds, 3),
        "usd": usd,
        "agent_env": agent_env,
        "optimizer": payload,
        **seal,
    }
    if proc is not None and proc.returncode != 0:
        out["agent_error"] = (proc.stderr or "")[-1200:]
    print(json.dumps(out, indent=2))
    # The run's worth is its sealed number, so that — not the agent's exit code — decides
    # ours. An agent that ran out of turns after three honest rounds produced a result; one
    # that exited 0 without sealing did not.
    return 0 if seal["sealed"] else 1


def _common_parent(a: Path, b: Path) -> Path:
    try:
        return Path(os.path.commonpath([str(a), str(b)]))
    except ValueError:
        return a.parent


if __name__ == "__main__":
    sys.exit(main())
