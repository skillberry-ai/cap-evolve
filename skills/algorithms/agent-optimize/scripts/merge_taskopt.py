"""Merge N per-task-optimised capability copies into one candidate, via git's 3-way merge.

The per-task phase gives K optimisers a 30x cheaper feedback loop each, but they all edit the
SAME two files from the SAME base, so their results have to be combined before anything can be
gated. Hand-merging K policy rewrites is how a good round quietly becomes a bad one.

So don't hand-merge. `git merge-file` already implements 3-way merge correctly, including
conflict detection, and it has been debugged by more people than this repo has commits. Base
becomes a commit, each optimiser's copy becomes a branch, and merging happens one branch at a
time so a conflict is attributable to a specific pair rather than to "the merge".

A conflict is a SIGNAL, not an accident: two optimisers guarding the same moment in the same tool
means their diagnoses overlap, and the round should ship one of them, not a stitched-together
hybrid neither one measured. Conflicts are reported and left for a decision; they are never
auto-resolved.

    python merge_taskopt.py --root <dir-of-optimiser-copies> \\
        --base <parent-artifact> --out <merged-candidate> --include t7 t17 u33 ...
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

FILES_DEFAULT = "policy/policy.md,tools/tools.py"


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=check,
        env={"GIT_AUTHOR_NAME": "capevolve", "GIT_AUTHOR_EMAIL": "capevolve@local",
             "GIT_COMMITTER_NAME": "capevolve", "GIT_COMMITTER_EMAIL": "capevolve@local",
             "PATH": "/usr/bin:/bin:/usr/local/bin", "HOME": "/tmp"},
    )


def stage(repo: Path, src: Path, files: list[str]) -> None:
    """Copy the merge-relevant files from src into the repo working tree."""
    for rel in files:
        s, d = src / rel, repo / rel
        if s.exists():
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, d)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, help="the parent artifact every optimiser started from")
    ap.add_argument("--out", required=True, help="destination candidate dir")
    ap.add_argument("--include", nargs="+", required=True,
                    help="subdir names under --root to merge. Use NAME:PARENT when an optimiser "
                         "was REBASED onto another one's copy (e.g. t17b:u67b) — its branch is "
                         "then cut from PARENT so only its own deltas are applied. Without this "
                         "a rebased copy's diff re-applies everything its parent already did and "
                         "conflicts with the parent's own branch.")
    ap.add_argument("--root", required=True, help="dir holding the per-task optimiser copies")
    ap.add_argument("--files", default=FILES_DEFAULT,
                    help="comma-separated capability-relative files to 3-way merge")
    ap.add_argument("--subdirs", default="policy,tools,reference",
                    help="comma-separated capability subdirs to copy into --out")
    ap.add_argument("--union-on-conflict", action="store_true",
                    help="resolve a conflict by keeping BOTH sides (a git union merge driver). "
                         "Legitimate ONLY for textual collisions of DISTINCT additions — two new "
                         "functions or two new dict keys that happen to land on adjacent lines. "
                         "Never for a semantic conflict, where two optimisers arbitrate the SAME "
                         "decision differently: union there ships contradictory guidance nobody "
                         "measured. Union-resolved files are named in the output so the claim can "
                         "be checked, and the result MUST be validated (it can break syntax) and "
                         "gated as a whole before it is believed.")
    ap.add_argument("--repo", default="/tmp/capevolve_merge", help="scratch git repo")
    args = ap.parse_args()

    base, out = Path(args.base).resolve(), Path(args.out).resolve()
    root = Path(args.root).resolve()
    files = [f.strip() for f in args.files.split(",") if f.strip()]
    subdirs = [s.strip() for s in args.subdirs.split(",") if s.strip()]
    repo = Path(args.repo)
    shutil.rmtree(repo, ignore_errors=True)
    repo.mkdir(parents=True)

    git(repo, "init", "-q", "-b", "base")
    if args.union_on_conflict:
        (repo / ".gitattributes").write_text(
            "\n".join(f"{f} merge=union" for f in files) + "\n")
        git(repo, "config", "merge.union.name", "keep both sides")
        git(repo, "config", "merge.union.driver", "git merge-file --union -L base -L ours "
                                                 "-L theirs %A %O %B")
    stage(repo, base, files)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "base")

    spec = []
    for item in args.include:
        name, _, parent = item.partition(":")
        spec.append((name, parent or "base"))
    order = {n: i for i, (n, _) in enumerate(spec)}
    for name, parent in spec:
        if parent != "base" and order.get(parent, 1 << 30) > order[name]:
            print(json.dumps({"error": f"{name} is rebased onto {parent}, so {parent} must be "
                                       f"listed BEFORE it in --include"}, indent=2))
            return 2

    for name, parent in spec:
        src = root / name
        if not any((src / f).exists() for f in files):
            print(f"skip {name}: none of {files} present", file=sys.stderr)
            continue
        git(repo, "checkout", "-q", "-b", name, parent)
        stage(repo, src, files)
        git(repo, "add", "-A")
        r = git(repo, "commit", "-qm", name, check=False)
        if "nothing to commit" in (r.stdout + r.stderr):
            print(f"note {name}: identical to base (no edit)", file=sys.stderr)

    git(repo, "checkout", "-q", "base")
    git(repo, "checkout", "-q", "-b", "merged")

    merged, conflicts, empty, unioned = [], {}, [], []
    for name, _parent in spec:
        if not any((root / name / f).exists() for f in files):
            continue
        r = git(repo, "merge", "--no-edit", name, check=False)
        if r.returncode == 0:
            if args.union_on_conflict:
                unioned.append(name)
            if "Already up to date" in r.stdout:
                empty.append(name)
            else:
                merged.append(name)
            continue
        status = git(repo, "diff", "--name-only", "--diff-filter=U").stdout.split()
        conflicts[name] = status
        git(repo, "merge", "--abort", check=False)

    out.mkdir(parents=True, exist_ok=True)
    for sub in subdirs:
        shutil.rmtree(out / sub, ignore_errors=True)
        if (base / sub).exists():
            shutil.copytree(base / sub, out / sub, ignore=shutil.ignore_patterns("__pycache__"))
    for rel in files:
        if (repo / rel).exists():
            shutil.copy2(repo / rel, out / rel)
    shutil.rmtree(out / "tools" / "__pycache__", ignore_errors=True)

    diff = git(repo, "diff", "--stat", "base", "merged").stdout.strip()
    print(json.dumps({
        "out": str(out),
        "bases": {n: p for n, p in spec},
        "merged_cleanly": merged,
        "union_resolution_enabled": bool(args.union_on_conflict),
        "union_candidates": unioned if args.union_on_conflict else [],
        "no_edit": empty,
        "conflicted": conflicts,
        "diffstat_vs_base": diff.splitlines(),
        "next": ("syntax-check, RENDER THE LIVE TOOLSET (union resolution can break syntax or "
                 "duplicate a definition), then gate the merged dir on full val"),
    }, indent=2))
    return 1 if conflicts else 0


if __name__ == "__main__":
    raise SystemExit(main())
