"""Pipeline wiring self-test — run AFTER ``cap-evolve check`` is green.

``cap-evolve check`` proves the adapter contract holds. This self-test proves the
*pipeline plumbing around it* is wired: the optimizer would actually receive the
trajectories, the capability guidance, and a fully-rendered (no leftover
placeholder) instructions prompt.

A full one-iteration optimization (even with the ``mock`` optimizer) needs a
baseline, a frozen split, and a run dir — none of which exist yet at
implement-and-check time, and building them is benchmark-specific. So this test
does the focused, benchmark-AGNOSTIC equivalent: it exercises the same code paths
that build the optimizer's working dir, using the real harness renderer, and
reports precisely which artifact is missing so the intake agent can iterate.

It asserts:
  1. the optimizer-prompt template is scaffolded at ``optimizer/INSTRUCTIONS.md``
     and still carries its ``{{...}}`` placeholders (intake must NOT delete them);
  2. ``capevolve.yaml::optimizer_instructions_file`` points at a file that EXISTS;
  3. rendering that template through the REAL harness renderer leaves NO ``{{``
     placeholder behind (the harness fills them per iteration);
  4. the adapter EITHER defines ``trajectories()`` (returns the native traj dir) OR
     intentionally inherits the base default (cap-evolve falls back to its own
     per-rollout JSON) — both are valid; we just report which.

Exit 0 = wiring green; non-zero = a named artifact is missing/broken.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve import specfile
from cap_evolve.adapter import CapabilityAdapter
from cap_evolve.check import load_adapter
from cap_evolve.harness import _focus_instructions
from cap_evolve.loop import SplitResult


def _synthetic_val() -> SplitResult:
    """A SplitResult with a failing + a flaky + a solid task so EVERY dynamic block
    of the template (focus summary, failures index) is exercised when rendering."""
    return SplitResult(
        split="val",
        reward=0.5,
        stderr=0.1,
        per_task=[
            {"task_id": "t_fail", "reward": 0.0, "trial_rewards": [0.0],
             "feedback": "synthetic always-failing task"},
            {"task_id": "t_flaky", "reward": 0.5, "trial_rewards": [1.0, 0.0],
             "feedback": "synthetic flaky task"},
            {"task_id": "t_solid", "reward": 1.0, "trial_rewards": [1.0],
             "feedback": "synthetic solid task"},
        ],
    )


def selftest(project: Path) -> dict:
    project = Path(project)
    problems: list[str] = []
    notes: list[str] = []

    # 1) template scaffolded + placeholders intact
    spec_path = project / "capevolve.yaml"
    spec = specfile.read_yaml(spec_path.read_text(encoding="utf-8")) if spec_path.exists() else {}
    if not spec_path.exists():
        problems.append(f"missing spec: {spec_path} (intake must scaffold capevolve.yaml)")

    instr_rel = str(spec.get("optimizer_instructions_file") or "optimizer/INSTRUCTIONS.md")
    instr_path = project / instr_rel
    if not instr_path.exists():
        problems.append(
            f"optimizer_instructions_file points at a missing file: {instr_rel} "
            f"(expected an existing template under {project}/)")
        template = ""
    else:
        template = instr_path.read_text(encoding="utf-8")
        if "{{" not in template:
            problems.append(
                f"template {instr_rel} has NO {{{{...}}}} placeholders — intake must "
                "KEEP them (the harness fills FOCUS_SUMMARY/FAILURES/CAP_BRIEF/"
                "ALGO_BRIEF/BENCH_REPO per iteration); did you over-customize it?")
        else:
            notes.append(f"optimizer template OK with intact placeholders: {instr_rel}")

    # 3) render through the REAL harness renderer; no {{ may survive
    if template and "{{" in template:
        caps = [c for c in (spec.get("capabilities") or []) if c]
        rendered = _focus_instructions(
            _synthetic_val(), None, "pipeline self-test",
            capabilities=caps, algorithm=str(spec.get("algorithm_skill") or "hill-climb"),
            instructions_file=instr_path,
            bench_repo=(str(spec.get("runner_repo_path")) or None),
        )
        if "{{" in rendered:
            leftovers = sorted({tok.split("}}")[0] for tok in rendered.split("{{")[1:]})
            problems.append(
                "rendered INSTRUCTIONS.md still has leftover placeholder(s): "
                + ", ".join("{{" + x + "}}" for x in leftovers)
                + " — the harness did not substitute them (a placeholder typo?)")
        else:
            notes.append("rendered INSTRUCTIONS.md has no leftover {{ placeholders")

    # 4) trajectories(): defined OR intentionally inherited (both valid)
    try:
        adapter = load_adapter(project)
        defines_traj = type(adapter).trajectories is not CapabilityAdapter.trajectories
        notes.append(
            "adapter defines trajectories() (native traj dir → ./trajectories/)"
            if defines_traj else
            "adapter inherits trajectories() default → falls back to cap-evolve's "
            "per-rollout JSON (valid; note it in PROJECT.md)")
    except Exception as e:  # noqa: BLE001
        problems.append(f"could not load adapter to inspect trajectories(): {e}")

    return {"ok": not problems, "project": str(project),
            "problems": problems, "notes": notes}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="pipeline-selftest")
    p.add_argument("--project", default=".capevolve/project")
    args = p.parse_args(argv)
    report = selftest(Path(args.project))
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
