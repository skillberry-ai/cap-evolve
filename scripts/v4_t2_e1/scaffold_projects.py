#!/usr/bin/env python3
"""Scaffold the 21 per-task cap-evolve projects for v4_t2_e1.

Layout (see the plan's deviation 1 for why it's nested one level deeper than
the original design doc):

    .capevolve/
      v4_t2_e1_common/
        adapters  -> ../../scripts/v4_t2_e1/common/adapters   (symlink)
        optimizer -> ../../scripts/v4_t2_e1/common/optimizer  (symlink)
      v4_t2_e1_<task-id>/
        project/
          seed_capability/*.md   (8 files, real copies — a frozen snapshot)
          capevolve.yaml
          split_ids.json
          adapters  -> ../../v4_t2_e1_common/adapters   (symlink)
          optimizer -> ../../v4_t2_e1_common/optimizer  (symlink)

Each task's project/ is its own unique directory, so cap-evolve run's
run_<timestamp>/ (created under project/'s PARENT) never collides with
another task's.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CAPEVOLVE_DIR = REPO_ROOT / ".capevolve"
COMMON_ADAPTERS_SRC = Path(__file__).resolve().parent / "common" / "adapters"
COMMON_OPTIMIZER_SRC = Path(__file__).resolve().parent / "common" / "optimizer"

# common/ holds parsec_paths.py, the single source of truth for PARSEC_V4N —
# see that module's docstring for why adapter.py and this file must not each
# keep their own copy of the same default.
_COMMON_DIR = Path(__file__).resolve().parent / "common"
if str(_COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(_COMMON_DIR))
import parsec_paths  # noqa: E402

PARSEC_V4N = parsec_paths.resolve_v4n_or_none()
PROMPTS_DIR = (
    PARSEC_V4N / "_run" / "parsec-live" / "config" / "prompts" if PARSEC_V4N else None
)

PROMPT_FILES = [
    "orchestrator.md",
    "shared_context.md",
    "aap2_agent.md",
    "babylon_agent.md",
    "cost_agent.md",
    "icinga_agent.md",
    "ocpv_agent.md",
    "security_agent.md",
]

TASK_IDS = [
    "cloud-024-guid-to-account",
    "cloud-026-gpu-abuse-triage",
    "cost-029-no-cost-rows-for-guid",
    "cost-030-threshold-not-an-anomaly",
    "icinga-010-stuck-anarchysubjects",
    "icinga-011-aap2-job-status-alert",
    "icinga-013-acknowledged-not-an-issue",
    "icinga-014-check-script-path-moved",
    "platform-001-ee-entrypoint-rca",
    "platform-002-collection-not-found-rca",
    "platform-003-tojson-dict-literal-rca",
    "platform-004-events-then-config",
    "platform-005-wrong-owner-trap",
    "platform-007-directory-path-fetch",
    "platform-008-log-does-not-say",
    "platform-022-job-on-no-controller",
    "platform-023-splunk-guid-no-events",
    "platform-031-helm-url-not-a-timeout",
    "platform-032-shared-secret-not-a-registry-outage",
    "platform-033-schema-change-not-the-oom",
    "platform-034-rate-limit-not-an-outage",
]


def render_capevolve_yaml(task_id: str) -> str:
    return f"""\
# v4_t2_e1 — single-task optimization project for {task_id}.
# See docs/superpowers/plans/2026-09-17-parsec-v4-task-by-task-optimization.md
optimizer_skill: claude-code
optimizer_model: claude-opus-5
algorithm_skill: hill-climb
target_model: claude-sonnet-4-6
capabilities: [system-prompt]
split_ids_file: split_ids.json
num_trials: 5
max_iterations: 3
stall: 2
max_usd: 50.0
max_optimizer_usd: 20.0
stop_at_reward: 1.0
"""


def render_split_ids(task_id: str) -> str:
    return (
        "{\n"
        f'  "train": ["{task_id}"],\n'
        f'  "val":   ["{task_id}"],\n'
        f'  "test":  ["{task_id}"]\n'
        "}\n"
    )


def _ensure_symlink(link: Path, target: Path) -> Path:
    """Create ``link`` -> relative(``target``) if missing; verify it if present."""
    link.parent.mkdir(parents=True, exist_ok=True)
    rel_target = Path(os.path.relpath(target, start=link.parent))
    if link.is_symlink() or link.exists():
        if link.resolve() != target.resolve():
            raise RuntimeError(
                f"{link} already exists and does not point at {target} "
                f"(points at {link.resolve()})"
            )
        return link
    link.symlink_to(rel_target, target_is_directory=True)
    return link


def scaffold_all(
    capevolve_dir: Path,
    *,
    prompts_dir: Path = PROMPTS_DIR,
    task_ids: list[str] | None = None,
    common_adapters_src: Path = COMMON_ADAPTERS_SRC,
    common_optimizer_src: Path = COMMON_OPTIMIZER_SRC,
    refresh_seeds: bool = False,
) -> list[Path]:
    task_ids = list(task_ids) if task_ids is not None else list(TASK_IDS)
    created: list[Path] = []

    common_dir = capevolve_dir / "v4_t2_e1_common"
    created.append(_ensure_symlink(common_dir / "adapters", common_adapters_src))
    created.append(_ensure_symlink(common_dir / "optimizer", common_optimizer_src))

    for task_id in task_ids:
        proj = capevolve_dir / f"v4_t2_e1_{task_id}" / "project"
        seed_dir = proj / "seed_capability"
        seed_dir.mkdir(parents=True, exist_ok=True)
        # Once a task already has a full seed snapshot, its seed_capability/ is
        # live optimizer input, not scratch — a later scaffold_all() call (e.g.
        # re-running this script mid-sweep after fixing a common/ bug) must not
        # silently re-copy over it. Only --refresh-seeds may intentionally do
        # that (e.g. resyncing a snapshot known to have been corrupted).
        already_seeded = all((seed_dir / name).exists() for name in PROMPT_FILES)
        for name in PROMPT_FILES:
            src = prompts_dir / name
            dst = seed_dir / name
            if already_seeded and not refresh_seeds:
                created.append(dst)
                continue
            shutil.copyfile(src, dst)
            created.append(dst)

        yaml_path = proj / "capevolve.yaml"
        yaml_path.write_text(render_capevolve_yaml(task_id), encoding="utf-8")
        created.append(yaml_path)

        split_path = proj / "split_ids.json"
        split_path.write_text(render_split_ids(task_id), encoding="utf-8")
        created.append(split_path)

        created.append(_ensure_symlink(proj / "adapters", common_dir / "adapters"))
        created.append(_ensure_symlink(proj / "optimizer", common_dir / "optimizer"))

    return created


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                         help="print what would be created, write nothing")
    parser.add_argument("--only", action="append", default=None,
                         help="scaffold only this task id (repeatable)")
    parser.add_argument("--refresh-seeds", action="store_true",
                         help="overwrite an already-scaffolded task's seed_capability "
                              "prompt files from prompts_dir. Default: skip tasks that "
                              "already have a full seed snapshot, so a later re-scaffold "
                              "can't silently clobber an in-progress task's optimizer "
                              "input. Use this only to intentionally resync a snapshot.")
    args = parser.parse_args()

    task_ids = args.only if args.only else TASK_IDS
    unknown = [t for t in task_ids if t not in TASK_IDS]
    if unknown:
        print(f"unknown task id(s): {unknown}", file=sys.stderr)
        return 1

    if args.dry_run:
        for task_id in task_ids:
            print(f"would scaffold {CAPEVOLVE_DIR / f'v4_t2_e1_{task_id}' / 'project'}")
        return 0

    if PROMPTS_DIR is None:
        print(
            "PARSEC_V4N environment variable is required (the parsec v4 "
            "checkout root, e.g. .../rhdp-parsec/v4_2026-09-16) — set it "
            "before scaffolding.",
            file=sys.stderr,
        )
        return 1
    if not PROMPTS_DIR.exists():
        print(f"prompts dir not found: {PROMPTS_DIR}", file=sys.stderr)
        return 1

    # _ensure_symlink() uses Path.symlink_to(), which does NOT validate that its
    # target exists. Scaffolding against a missing common/ source therefore
    # produced 21 projects' worth of dangling `adapters`/`optimizer` symlinks and
    # still exited 0. Task 5's runner catches that later, one task at a time;
    # refusing here means it never gets written in the first place.
    for label, src in (("common adapters source", COMMON_ADAPTERS_SRC),
                       ("common optimizer source", COMMON_OPTIMIZER_SRC)):
        if not src.exists():
            print(
                f"{label} not found: {src} — scaffolding now would create dangling "
                f"symlinks in every project. Nothing was written.",
                file=sys.stderr,
            )
            return 1

    # Pass the sources explicitly rather than leaning on scaffold_all()'s
    # def-time defaults, so main() scaffolds from exactly the paths it just
    # validated — the two cannot drift apart.
    paths = scaffold_all(
        CAPEVOLVE_DIR, task_ids=task_ids, prompts_dir=PROMPTS_DIR,
        common_adapters_src=COMMON_ADAPTERS_SRC,
        common_optimizer_src=COMMON_OPTIMIZER_SRC,
        refresh_seeds=args.refresh_seeds,
    )
    print(f"scaffolded {len(task_ids)} task project(s), {len(paths)} paths touched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
