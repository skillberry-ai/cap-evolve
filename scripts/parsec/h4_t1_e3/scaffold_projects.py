#!/usr/bin/env python3
"""Scaffold the 30 per-task cap-evolve projects for an h4 arm.

Each project gets a seed_capability/ copied from ONE prompt bundle -- whichever
$PARSEC_H4_BUNDLE points at -- so the arm's independent variable is that bundle
and nothing else. Mirrors scripts/parsec/v4_t2_e1's scaffold, with two
deliberate differences:

  * No optimizer/ symlink. These arms run exactly one baseline-only eval per
    task (see run_one_task.py), and cap_evolve.check.load_adapter() only looks
    under project/adapters/, so an optimizer symlink would be dead structure.
  * adapters/ symlinks straight to v4_t2_e1's common adapters dir rather than
    through an intermediate per-arm hop. The adapter is generic, so this is
    reuse rather than a new dependency -- the same file, not a copy.

Layout:

    .capevolve/
      h4_t1_e3_<task-id>/
        project/
          seed_capability/*.md   (8 files, copied from $PARSEC_H4_BUNDLE)
          capevolve.yaml
          split_ids.json
          adapters -> ../../../scripts/parsec/v4_t2_e1/common/adapters
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
CAPEVOLVE_DIR = REPO_ROOT / ".capevolve"
COMMON_ADAPTERS_SRC = REPO_ROOT / "scripts" / "parsec" / "v4_t2_e1" / "common" / "adapters"

#: The prompt bundle each task is seeded from, located by $PARSEC_H4_BUNDLE.
#: It lives on the parsec-history branch (artifacts/h4/<arm>/, beside v1/v2/v4)
#: so main carries no parsec artifacts — so a run needs that branch checked out
#: too, with this variable pointed at the arm's directory.
#:
#: No fallback default, for the reason parsec_paths.py gives about PARSEC_V4N:
#: there is no single "the" bundle to guess at, and guessing wrong would seed a
#: run from one arm's prompts while reporting it as another's.
BUNDLE_REQUIRED_MSG = (
    "PARSEC_H4_BUNDLE environment variable is required — it must point at an "
    "h4 prompt bundle directory holding the 8 prompt files (e.g. "
    ".../parsec-history/artifacts/h4/t1 for the T1 arm, or .../h4/g2 for G2)."
)


def resolve_bundle_dir() -> Path:
    """The prompt bundle root, from $PARSEC_H4_BUNDLE.

    Raises rather than defaulting: which arm's prompts get installed is the
    independent variable of the whole experiment, so an unset value has to stop
    the run rather than pick one.
    """
    raw = os.environ.get("PARSEC_H4_BUNDLE", "").strip()
    if not raw:
        raise RuntimeError(f"{BUNDLE_REQUIRED_MSG} Set it before running this script.")
    return Path(raw)

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
    '061-capacity-manager-unused-cost-owner-lookup',
    '062-provisioning-job-trace',
    '063-babylon-namespace-missing-for-account',
    '064-reservation-release-active-job-check',
    'cloud-055-azure-subscription-not-found',
    'cloud-056-gcp-delete-in-progress-not-requested',
    'cloud-057-cloudtrail-select-only-refusal',
    'cloud-058-malformed-account-id',
    'cloud-059-blank-owner-email-fallback',
    'cloud-060-marketplace-usd-not-enriched',
    'cost-050-org-wide-aggregate-doubling',
    'cost-051-gcp-net-of-credits',
    'cost-052-azure-empty-cache-no-filter',
    'cost-053-capacity-dropped-reservations',
    'cost-054-monitor-no-dashboard-link',
    'icinga-045-hosts-search-filter',
    'icinga-046-services-search-cross-host',
    'icinga-047-downtime-similar-host-names',
    'icinga-048-comment-service-vs-host-scope',
    'icinga-049-downtime-already-expired',
    'platform-035-aap2-cross-controller-job-search',
    'platform-036-secret-redacted-not-absent',
    'platform-037-ocpv-healthy-vm-degraded-machineset',
    'platform-038-anarchy-subject-guid-cross-cluster',
    'platform-039-catalog-miss-pr-fallback',
    'platform-040-workshop-cross-cluster-name-search',
    'platform-041-resource-pool-unfiltered-list',
    'platform-042-deployment-via-resource-claim',
    'platform-043-multiworkshop-asset-failure',
    'platform-044-search-catalog-env-type',
]
assert len(TASK_IDS) == 30, f"expected 30 task ids, got {len(TASK_IDS)}"
assert len(set(TASK_IDS)) == 30, "duplicate task id in TASK_IDS"


def render_capevolve_yaml(task_id: str) -> str:
    return f"""\
# h4_t1_e3 -- baseline-only eval for {task_id}.
# This project is never handed to `cap-evolve run` -- run_one_task.py invokes
# skills/phases/baseline/scripts/run.py directly, exactly once, n_trials=5.
# The algorithm/optimizer fields below are unused (kept only so this file
# reads like a normal cap-evolve project spec) -- there is no algorithm loop.
optimizer_skill: claude-code
optimizer_model: claude-opus-5
algorithm_skill: hill-climb
target_model: claude-sonnet-4-6
capabilities: [system-prompt]
split_ids_file: split_ids.json
num_trials: 5
max_iterations: 0
stall: 0
max_usd: 0.0
max_optimizer_usd: 0.0
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
    bundle_dir: Path | None = None,
    task_ids: list[str] | None = None,
    common_adapters_src: Path = COMMON_ADAPTERS_SRC,
    refresh_seeds: bool = False,
) -> list[Path]:
    task_ids = list(task_ids) if task_ids is not None else list(TASK_IDS)
    if bundle_dir is None:
        bundle_dir = resolve_bundle_dir()
    created: list[Path] = []

    for task_id in task_ids:
        proj = capevolve_dir / f"h4_t1_e3_{task_id}" / "project"
        seed_dir = proj / "seed_capability"
        seed_dir.mkdir(parents=True, exist_ok=True)
        # Same guard as v4_t2_e1: once a task has a full seed snapshot, it's live
        # eval input, not scratch -- a later re-scaffold (e.g. after fixing a bug
        # in this script) must not silently re-copy over it. Only --refresh-seeds
        # may intentionally do that.
        already_seeded = all((seed_dir / name).exists() for name in PROMPT_FILES)
        for name in PROMPT_FILES:
            src = bundle_dir / name
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

        created.append(_ensure_symlink(proj / "adapters", common_adapters_src))

    return created


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                         help="print what would be created, write nothing")
    parser.add_argument("--only", action="append", default=None,
                         help="scaffold only this task id (repeatable)")
    parser.add_argument("--refresh-seeds", action="store_true",
                         help="overwrite an already-scaffolded task's seed_capability "
                              "from bundle_dir. Default: skip tasks that already have a "
                              "full seed snapshot. Use this only to intentionally resync.")
    args = parser.parse_args()

    task_ids = args.only if args.only else TASK_IDS
    unknown = [t for t in task_ids if t not in TASK_IDS]
    if unknown:
        print(f"unknown task id(s): {unknown}", file=sys.stderr)
        return 1

    if args.dry_run:
        for task_id in task_ids:
            print(f"would scaffold {CAPEVOLVE_DIR / f'h4_t1_e3_{task_id}' / 'project'}")
        return 0

    bundle_dir = resolve_bundle_dir()
    if not bundle_dir.exists():
        print(f"prompt bundle dir not found: {bundle_dir}", file=sys.stderr)
        return 1
    missing_files = [name for name in PROMPT_FILES if not (bundle_dir / name).exists()]
    if missing_files:
        print(f"merge bundle missing file(s): {missing_files}", file=sys.stderr)
        return 1

    # Same defensive check as v4_t2_e1: Path.symlink_to() does not validate that
    # its target exists, so scaffolding against a missing adapters source would
    # silently write 34 dangling symlinks and still exit 0.
    if not COMMON_ADAPTERS_SRC.exists():
        print(
            f"common adapters source not found: {COMMON_ADAPTERS_SRC} -- scaffolding "
            f"now would create dangling symlinks in every project. Nothing was written.",
            file=sys.stderr,
        )
        return 1

    paths = scaffold_all(
        CAPEVOLVE_DIR, task_ids=task_ids, bundle_dir=bundle_dir,
        common_adapters_src=COMMON_ADAPTERS_SRC,
        refresh_seeds=args.refresh_seeds,
    )
    print(f"scaffolded {len(task_ids)} task project(s), {len(paths)} paths touched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
