"""The ``acapo`` CLI — a thin sequencer over the skill ``run.py`` scripts.

``acapo`` does NOT contain pipeline logic; it locates skills (via the registry
manifest) and runs their ``scripts/run.py`` in the order a ``acapo.yaml`` spec
declares, threading the run dir between them. The honesty guarantees live in
``agent_capo`` (splits/gate/seal); ``acapo`` just orchestrates.

Subcommands:
    acapo version
    acapo splits  --ids ... [--seed N] [--ratios a,b,c]
    acapo check   [project_dir]
    acapo run     --spec .agentcapo/project/acapo.yaml   (sequences phase skills)

``run`` is intentionally minimal in Phase 0 and grows as phase skills land; it
already resolves the manifest and validates the spec so the wiring is testable.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from . import __version__
from .check import run_check


def _find_skills_dir() -> Path | None:
    for cand in [
        os.environ.get("ACAPO_SKILLS_DIR"),
        "./.claude/skills",
        os.path.expanduser("~/.claude/skills"),
        os.path.expanduser("~/.agentcapo/skills"),
    ]:
        if cand and Path(cand).is_dir():
            return Path(cand)
    # fall back to the repo's own skills/ if running from source
    here = Path(__file__).resolve()
    for parent in here.parents:
        s = parent / "skills"
        if s.is_dir():
            return s
    return None


def _cmd_version(argv):
    print(json.dumps({"acapo": __version__}))
    return 0


def _cmd_splits(argv):
    from .__main__ import _cmd_splits as f
    return f(argv)


def _cmd_check(argv):
    project = Path(argv[0]) if argv else Path(".agentcapo/project")
    rep = run_check(project)
    print(json.dumps(rep.to_dict(), indent=2))
    return 0 if rep.ok else 1


def _resolve_skills(skills_dir: Path) -> dict:
    manifest = skills_dir / "_registry" / "manifest.json"
    if not manifest.exists():
        raise FileNotFoundError(
            "no manifest — run install.sh or skills/_registry/build_manifest.py first")
    return json.loads(manifest.read_text()).get("skills", {})


def _cmd_run(argv):
    import argparse
    import subprocess
    from .specfile import read_yaml

    p = argparse.ArgumentParser(prog="acapo run")
    p.add_argument("--spec", default=".agentcapo/project/acapo.yaml")
    p.add_argument("--project", default=".agentcapo/project")
    p.add_argument("--skills-dir", default=None)
    p.add_argument("--plan-only", action="store_true", help="print the command plan, don't execute")
    p.add_argument("--run-ts", default=None)
    args = p.parse_args(argv)

    skills_dir = Path(args.skills_dir) if args.skills_dir else _find_skills_dir()
    if not skills_dir:
        print(json.dumps({"error": "skills dir not found; set ACAPO_SKILLS_DIR or --skills-dir"}))
        return 1
    skills = _resolve_skills(skills_dir)
    spec = read_yaml(Path(args.spec).read_text())

    def skill_run(name: str) -> str:
        s = skills.get(name)
        if not s:
            raise KeyError(f"skill {name!r} not in manifest")
        return str(skills_dir / s["path"] / s["entry"])

    # All steps run in ONE consistent working directory: the dir that contains
    # .agentcapo/ (i.e. project's grandparent). Paths are kept relative to it so the
    # run_dir baseline prints ("..agentcapo/run_X") resolves identically in every
    # subprocess regardless of where `acapo run` was invoked from.
    proj_abs = Path(args.project).resolve()
    workdir = proj_abs.parent.parent
    project = str(proj_abs.relative_to(workdir))      # ".agentcapo/project"
    base = str(proj_abs.parent.relative_to(workdir))  # ".agentcapo"
    cap_path = spec.get("capability_path", "seed_capability")
    ratios = f"{spec.get('split_train',0.5)},{spec.get('split_val',0.25)},{spec.get('split_test',0.25)}"
    opt_cmd = (f"{sys.executable} {skill_run(spec['optimizer_skill'])} "
               f"--workdir {{workdir}} --prompt {{prompt}}")
    if spec.get("optimizer_model"):
        opt_cmd += f" --model {spec['optimizer_model']}"
    py = sys.executable

    def run(cmd):
        return subprocess.run(cmd, capture_output=True, text=True, cwd=str(workdir))

    if args.plan_only:
        print(json.dumps({"skills_dir": str(skills_dir), "workdir": str(workdir), "spec": spec,
                          "optimizer_cmd": opt_cmd,
                          "sequence": ["baseline", spec["algorithm_skill"], "finalize", "report"]},
                         indent=2))
        return 0

    # 1) baseline (creates the run dir; capture its relative path)
    base_cmd = [py, skill_run("baseline"), "--base", base, "--project", project,
                "--capability", cap_path, "--seed", str(spec.get("split_seed", 0)),
                "--ratios", ratios, "--max-iterations", str(spec.get("max_iterations", 10)),
                "--stall", str(spec.get("stall", 0)), "--n-trials", str(spec.get("num_trials", 1))]
    if spec.get("split_ids_file"):
        base_cmd += ["--split-ids", str(spec["split_ids_file"])]
    if args.run_ts:
        base_cmd += ["--run-ts", args.run_ts]
    proc = run(base_cmd)
    if proc.returncode != 0:
        print(json.dumps({"step": "baseline", "error": proc.stderr[-1500:]}))
        return 1
    run_dir = json.loads(proc.stdout)["run_dir"]

    # 2) algorithm
    alg_cmd = [py, skill_run(spec["algorithm_skill"]), "--run-dir", run_dir, "--project", project,
               "--optimizer", opt_cmd, "--max-iterations", str(spec.get("max_iterations", 10)),
               "--n-trials", str(spec.get("num_trials", 1)),
               "--gate-mode", str(spec.get("gate_mode", "significant")),
               "--k-se", str(spec.get("gate_k_se", 1.0)),
               "--store", str(spec.get("store", "git"))]
    if spec.get("store_commit_cmd"):
        alg_cmd += ["--store-commit-cmd", str(spec["store_commit_cmd"])]
    proc = run(alg_cmd)
    if proc.returncode != 0:
        print(json.dumps({"step": "algorithm", "error": proc.stderr[-1500:]}))
        return 1

    # 3) finalize  4) report
    last = proc.stdout
    for step, extra in (("finalize", ["--n-trials", str(spec.get("num_trials", 1))]), ("report", [])):
        cmd = [py, skill_run(step), "--run-dir", run_dir]
        if step == "finalize":
            cmd += ["--project", project]
        cmd += extra
        proc = run(cmd)
        if proc.returncode != 0:
            print(json.dumps({"step": step, "error": proc.stderr[-1500:]}))
            return 1
        last = proc.stdout

    print(last)
    return 0


COMMANDS = {
    "version": _cmd_version,
    "splits": _cmd_splits,
    "check": _cmd_check,
    "run": _cmd_run,
}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: acapo {version|splits|check|run} [args]", file=sys.stderr)
        return 0 if argv else 2
    fn = COMMANDS.get(argv[0])
    if fn is None:
        print(f"unknown command: {argv[0]}", file=sys.stderr)
        return 2
    return fn(argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
