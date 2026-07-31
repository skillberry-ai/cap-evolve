"""run_suite.sh's split selection, exercised as real bash rather than by reading it.

The hook has to satisfy two things at once:
  1. tiers that ship `split_ids.json` get that exact held-out split, and a stale or
     overlapping file is a LOUD failure (a split silently describing a different task set
     invalidates an entire comparison run), and
  2. every tier that does not ship one keeps the previous no-holdout FIT split, byte for byte.

(2) is why the extracted snippets below are compared against the same expectations the old
code produced: this change must be a no-op for tau2/swebench/skillsbench.
"""

import json
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
RUN_SUITE = REPO / "ci" / "benchmarks" / "lib" / "run_suite.sh"


def _split_block() -> str:
    """Lift the split-selection block verbatim out of run_suite.sh."""
    src = RUN_SUITE.read_text(encoding="utf-8")
    start = src.index("# SPLIT. A tier that ships its own split_ids.json")
    end = src.index('cat > "$PROJ/capevolve.yaml"', start)
    block = src[start:end]
    assert 'if [ -f "$BASE/split_ids.json" ]' in block, "split hook not found in run_suite.sh"
    return block


_case = [0]


def _run(tmp_path: Path, ids: list[str], committed: dict | None):
    """Run the real block with BASE/PROJ/IDS_CSV/PY wired to a temp tree.

    Each invocation gets its own subdirectory so a test may call this more than once.
    """
    _case[0] += 1
    root = tmp_path / f"case{_case[0]}"
    base = root / "base"
    proj = root / "proj"
    (proj / "inputs").mkdir(parents=True)
    base.mkdir(parents=True)
    if committed is not None:
        (base / "split_ids.json").write_text(json.dumps(committed), encoding="utf-8")

    script = textwrap.dedent(f"""
        set -euo pipefail
        PY=python3
        BASE={base}
        PROJ={proj}
        IDS_CSV="{','.join(ids)}"
    """) + _split_block()
    proc = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
    out = proj / "inputs" / "split_ids.json"
    written = json.loads(out.read_text(encoding="utf-8")) if out.exists() and out.stat().st_size else None
    return proc, written


IDS = [f"t{i}" for i in range(10)]


def test_without_a_committed_split_the_no_holdout_fit_split_is_unchanged(tmp_path):
    """Regression guard for tau2/swebench/skillsbench: train == val == test == all ids."""
    proc, written = _run(tmp_path, IDS, committed=None)
    assert proc.returncode == 0, proc.stderr
    assert written == {"train": IDS, "val": IDS, "test": IDS}


def test_a_committed_split_is_used_verbatim(tmp_path):
    committed = {"train": IDS[:2], "val": IDS[2:4], "test": IDS[4:]}
    proc, written = _run(tmp_path, IDS, committed=committed)
    assert proc.returncode == 0, proc.stderr
    assert {k: sorted(v) for k, v in written.items()} == \
           {k: sorted(v) for k, v in committed.items()}
    assert "held-out split" in proc.stdout


def test_overlapping_committed_split_fails_loudly(tmp_path):
    """A file that is not actually held out must not be accepted silently."""
    bad = {"train": IDS[:5], "val": IDS[4:7], "test": IDS[7:]}   # train/val share t4
    proc, _ = _run(tmp_path, IDS, committed=bad)
    assert proc.returncode != 0
    assert "not held out" in (proc.stdout + proc.stderr)


def test_split_missing_tier_tasks_fails_loudly(tmp_path):
    """A stale split would otherwise evaluate a different task set than the tier declares."""
    stale = {"train": IDS[:2], "val": IDS[2:4], "test": IDS[4:8]}   # t8, t9 unaccounted for
    proc, _ = _run(tmp_path, IDS, committed=stale)
    assert proc.returncode != 0
    assert "does not match" in (proc.stdout + proc.stderr)


def test_split_with_unknown_ids_fails_loudly(tmp_path):
    extra = {"train": IDS[:2], "val": IDS[2:4], "test": IDS[4:] + ["not-a-task"]}
    proc, _ = _run(tmp_path, IDS, committed=extra)
    assert proc.returncode != 0
    assert "does not match" in (proc.stdout + proc.stderr)


@pytest.mark.parametrize("empty_key", ["val", "test"])
def test_empty_val_or_test_fails_loudly(tmp_path, empty_key):
    """An empty selection split makes the gate meaningless; an empty test split, the seal."""
    bad = {"train": IDS[:4], "val": IDS[4:7], "test": IDS[7:]}
    # move the emptied split's ids into train so coverage still holds and `empty` is the
    # only thing wrong — otherwise the coverage check would fire first and mask it.
    bad["train"] = bad["train"] + bad[empty_key]
    bad[empty_key] = []
    proc, _ = _run(tmp_path, IDS, committed=bad)
    assert proc.returncode != 0, f"empty {empty_key} split was accepted"
    assert "empty" in (proc.stdout + proc.stderr), (proc.stdout, proc.stderr)


def test_the_real_committed_spreadsheetbench_split_passes_the_hook(tmp_path):
    """End-to-end: the actual 912-task file must satisfy the actual bash guard."""
    tasks = REPO / "ci" / "benchmarks" / "spreadsheetbench" / "full" / "tasks.json"
    split = REPO / "ci" / "benchmarks" / "spreadsheetbench" / "full" / "split_ids.json"
    ids = [str(e["id"]) for e in json.loads(tasks.read_text(encoding="utf-8"))]
    committed = json.loads(split.read_text(encoding="utf-8"))
    proc, written = _run(tmp_path, ids, committed=committed)
    assert proc.returncode == 0, proc.stderr
    assert len(written["train"]) == 182 and len(written["val"]) == 91 and len(written["test"]) == 639


def test_generated_spec_threads_split_seed():
    """split_seed must reach capevolve.yaml, defaulting to 0 (previous behaviour)."""
    src = RUN_SUITE.read_text(encoding="utf-8")
    assert "split_seed:         ${SPLIT_SEED:-0}" in src


def test_full_tier_matches_skillopts_30_turns():
    """SkillOpt runs SpreadsheetBench with up to 30 turns; the adapter default is 5."""
    src = RUN_SUITE.read_text(encoding="utf-8")
    assert "SB_MAX_TURNS_DEFAULT=5" in src, "smoke must stay cheap at 5 turns"
    assert 'if [ "$TIER" = "full" ]; then SB_MAX_TURNS_DEFAULT=30; fi' in src
    assert "SPREADSHEETBENCH_MAX_TURNS=${SPREADSHEETBENCH_MAX_TURNS:-$SB_MAX_TURNS_DEFAULT}" in src
