#!/usr/bin/env python3
"""Build the unified parsec v6 benchmark tree from JB's two 2026-10-16 bundles.

    v6_2026-10-16/
      bench-v6-harbor-tasks/bench-v6-<id>/   all 200 tasks, renamed (see below)
      task_sets.json                         per task: drop, source bundle, original name
      install_seeds.py  parsec_harbor_agent.py  parsec-simulation-redirect.patch
      parsec-<service>-skill-bundle.zip (+ unpacked dir), x5
      docs/jb-2026-10-16/{v4,v5-heldout}/    JB's own READMEs, catalogs, baselines, verbatim
      _run/tasks/      one symlink per task into bench-v6-harbor-tasks/
      _run/skills/     the five unpacked simulator bundles
      _run/parsec-live a copy of the reference parsec-live source, prompts reset to the
                       original skill, with its own freshly locked venv (built separately:
                       `uv sync --frozen` in that directory)

Renaming. A task's content is copied byte for byte except two files, and only their names:
  task.toml     name "bench/bench-vN-<id>" -> "bench/bench-v6-<id>"; suite "bench/vN" -> "bench/v6"
  provenance.md every "bench-v4-<cat>-<nnn>" / "bench-v5-<cat>-<nnn>" -> "bench-v6-..."
                (all 756 such references resolve to a task among the 200; checked here)
tests/verify.py and tests/expected.json are left byte-identical to JB's: all 200 verifiers are
one file, and its "bench/v4" schema tag is a contract-format version, not a task name.

Support files are JB's own, which are byte-identical to what he first shipped for v5, with the
two local changes v5's tree carried re-applied, so v6 runs exactly as v5 was measured:
  - docstring/comment renames to v6 (install_seeds.py, the patch);
  - the harbor agent's cost/token metering from the parsec `usage` event (taken from the v5
    tree's agent, after checking that it differs from JB's only by that addition).

Usage:
    python3 build_v6_tree.py --root /path/to/rhdp-parsec \\
        --v4-bundle _incoming_2026-10-16/v4/parsec-bench-v4-2026-10-16 \\
        --v5h-bundle _incoming_2026-10-16/v5h/parsec-bench-v5-heldout-2026-10-16 \\
        --v5-tree v5_2026-10-10 --seed-prompts <dir of the 8 original prompt files> \\
        --set-1012 <task_set_10-12.txt>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

NAME = "v6_2026-10-16"
SERVICES = ("platform", "github", "icinga", "cost", "cloud")
PROMPTS = ("orchestrator.md", "shared_context.md", "aap2_agent.md", "babylon_agent.md",
           "cost_agent.md", "icinga_agent.md", "ocpv_agent.md", "security_agent.md")
REF = re.compile(r"bench-v[45]-([a-z]+-\d{3})")
LIVE_SKIP = {".venv", ".git", "__pycache__", "parsec.egg-info"}
JB_AGENT_MD5 = "cd03bb52c3fb7fcbe2b24686dce4d5b0"
METERED_AGENT_MD5 = "09f9f53e1edef9e7e6876ada89818825"


def fail(msg: str) -> None:
    print(f"FATAL: {msg}", file=sys.stderr)
    raise SystemExit(2)


def tasks_of(bundle: Path, prefix: str, work: Path) -> dict[str, Path]:
    zips = [z for z in bundle.glob("*harbor-tasks.zip")]
    if len(zips) != 1:
        fail(f"{bundle}: expected one *harbor-tasks.zip, found {len(zips)}")
    out = work / bundle.name
    shutil.rmtree(out, ignore_errors=True)
    with zipfile.ZipFile(zips[0]) as z:
        z.extractall(out)
    found = {}
    for d in out.rglob(f"{prefix}*"):
        if d.is_dir() and (d / "task.toml").is_file():
            found[d.name[len(prefix):]] = d
    return found


def rename_toml(text: str, task_id: str) -> str:
    new, n = re.subn(r'^name = "bench/bench-v[45]-' + re.escape(task_id) + '"$',
                     f'name = "bench/bench-v6-{task_id}"', text, flags=re.M)
    if n != 1:
        fail(f"{task_id}: task.toml name line not found exactly once")
    new, n = re.subn(r'^suite = "bench/v[45]"$', 'suite = "bench/v6"', new, flags=re.M)
    if n != 1:
        fail(f"{task_id}: task.toml suite line not found exactly once")
    return new


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, type=Path)
    ap.add_argument("--v4-bundle", required=True, type=Path)
    ap.add_argument("--v5h-bundle", required=True, type=Path)
    ap.add_argument("--v5-tree", required=True, type=Path)
    ap.add_argument("--seed-prompts", required=True, type=Path)
    ap.add_argument("--set-1012", required=True, type=Path)
    args = ap.parse_args()
    root = args.root.resolve()
    v4b, v5b, v5t = (root / p if not p.is_absolute() else p for p in (args.v4_bundle, args.v5h_bundle, args.v5_tree))
    dst = root / NAME
    if dst.exists():
        fail(f"{dst} exists; refusing to overwrite (move it aside first)")
    work = root / f".{NAME}.work"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir()

    # ---- tasks -------------------------------------------------------------------------
    a = tasks_of(v4b, "bench-v4-", work)
    b = tasks_of(v5b, "bench-v5-", work)
    if set(a) & set(b):
        fail(f"task ids in both bundles: {sorted(set(a) & set(b))[:5]}")
    keys = {}
    for tid in list(a) + list(b):
        k = "-".join(tid.split("-")[:2])
        if k in keys:
            fail(f"category-number {k} used by two tasks: {keys[k]}, {tid}")
        keys[k] = tid
    s1012 = set(args.set_1012.read_text().split())
    if not s1012 <= set(b):
        fail(f"10-12 tasks missing from the heldout bundle: {sorted(s1012 - set(b))[:5]}")

    tasks_root = dst / "bench-v6-harbor-tasks"
    tasks_root.mkdir(parents=True)
    sets = {}
    for src_map, bundle in ((a, v4b), (b, v5b)):
        for tid, src in sorted(src_map.items()):
            out = tasks_root / f"bench-v6-{tid}"
            shutil.copytree(src, out, symlinks=False)
            (out / "task.toml").write_text(rename_toml((src / "task.toml").read_text(), tid))
            prov = (src / "provenance.md").read_text()
            for m in REF.finditer(prov):
                if m.group(1) not in keys:
                    fail(f"{tid}: provenance references {m.group(0)}, not among the 200")
            (out / "provenance.md").write_text(REF.sub(r"bench-v6-\1", prov))
            drop = "10-10" if src_map is a else ("10-12" if tid in s1012 else "10-16")
            sets[tid] = {"drop": drop, "source_bundle": bundle.name,
                         "original_name": src.name}
    if len(sets) != 200:
        fail(f"expected 200 tasks, got {len(sets)}")
    (dst / "task_sets.json").write_text(json.dumps(sets, indent=2, sort_keys=True) + "\n")

    # ---- support files -----------------------------------------------------------------
    for f in ("install_seeds.py", "parsec-simulation-redirect.patch", "parsec_harbor_agent.py"):
        if (v4b / f).read_bytes() != (v5b / f).read_bytes():
            fail(f"{f} differs between the two bundles")
    text = (v5b / "install_seeds.py").read_text()
    (dst / "install_seeds.py").write_text(re.sub(r"bench-v[45]", "bench-v6", text))
    text = (v5b / "parsec-simulation-redirect.patch").read_text()
    (dst / "parsec-simulation-redirect.patch").write_text(re.sub(r"bench-v[45]-", "bench-v6-", text))
    # The agent: v5's metered copy. Both files are pinned by hash to the pair whose diff was
    # reviewed (the only change is reading parsec's `usage` SSE event into AgentContext's
    # cost/token fields); any other pair is refused rather than silently carried over.
    jb_b, ours_b = (v5b / "parsec_harbor_agent.py").read_bytes(), (v5t / "parsec_harbor_agent.py").read_bytes()
    if hashlib.md5(jb_b).hexdigest() != JB_AGENT_MD5 or hashlib.md5(ours_b).hexdigest() != METERED_AGENT_MD5:
        fail("harbor agent hashes are not the reviewed pair; re-review the diff before building")
    ours = ours_b.decode()
    (dst / "parsec_harbor_agent.py").write_text(ours)
    for s in SERVICES:
        z = v5b / f"parsec-{s}-skill-bundle.zip"
        if z.read_bytes() != (v4b / z.name).read_bytes():
            fail(f"{z.name} differs between the two bundles")
        shutil.copyfile(z, dst / z.name)
        with zipfile.ZipFile(z) as zz:
            zz.extractall(dst)

    # ---- JB's documentation, verbatim --------------------------------------------------
    for bundle, sub in ((v4b, "v4"), (v5b, "v5-heldout")):
        d = dst / "docs" / "jb-2026-10-16" / sub
        d.mkdir(parents=True)
        for f in bundle.iterdir():
            if f.is_file() and not f.name.endswith(".zip") and f.suffix != ".py" and f.suffix != ".patch":
                shutil.copyfile(f, d / f.name)
            elif f.name == "baseline_trajectories.zip":
                shutil.copyfile(f, d / f.name)

    # ---- _run --------------------------------------------------------------------------
    run = dst / "_run"
    (run / "tasks").mkdir(parents=True)
    for tid in sorted(sets):
        (run / "tasks" / f"bench-v6-{tid}").symlink_to(Path("../../bench-v6-harbor-tasks") / f"bench-v6-{tid}")
    (run / "skills").mkdir()
    for s in SERVICES:
        shutil.copytree(dst / f"parsec-{s}", run / "skills" / f"parsec-{s}")
    live_src = v5t / "_run" / "parsec-live"
    shutil.copytree(live_src, run / "parsec-live", symlinks=True,
                    ignore=lambda d, names: [n for n in names if n in LIVE_SKIP])
    for n in PROMPTS:
        src = args.seed_prompts / n
        if not src.is_file():
            fail(f"seed prompt {src} missing")
        shutil.copyfile(src, run / "parsec-live" / "config" / "prompts" / n)
    for sub in ("jobs", "logs"):
        (run / sub).mkdir()

    shutil.rmtree(work)
    print(f"built {dst}: {len(sets)} tasks "
          f"({sum(v['drop'] == '10-10' for v in sets.values())} 10-10, "
          f"{sum(v['drop'] == '10-12' for v in sets.values())} 10-12, "
          f"{sum(v['drop'] == '10-16' for v in sets.values())} 10-16)")
    print(f"next: cd {run / 'parsec-live'} && uv sync --frozen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
