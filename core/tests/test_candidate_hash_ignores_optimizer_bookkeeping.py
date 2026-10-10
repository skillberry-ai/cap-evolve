"""Smoke-run B1: optimizer bookkeeping files must not perturb the capability hash, otherwise a
byte-identical copy of the seed is not pooled and a commit changes the champion's hash."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cap_evolve import Budget, RunDir, eval_index, hash_candidate_dir  # noqa: E402

BOOKKEEPING = ("INSIGHTS.md", "META_INSIGHTS.md", "FRAMEWORK_IMPROVEMENTS.md", "DIAGNOSIS.json",
               "JOURNAL.md", "LEDGER.md", "PROCESS.md", "RUNMAP.md")


def _seed(d: Path) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "policy.md").write_text("be nice")
    return d


def test_seed_copy_plus_bookkeeping_hashes_equal(tmp_path):
    seed = _seed(tmp_path / "seed")
    cp = _seed(tmp_path / "copy")
    for n in BOOKKEEPING:
        (cp / n).write_text("optimizer notes")
    assert hash_candidate_dir(cp) == hash_candidate_dir(seed)
    (cp / "policy.md").write_text("be nicer")
    assert hash_candidate_dir(cp) != hash_candidate_dir(seed)


def test_eval_index_pools_seed_and_bookkeeping_copy(tmp_path):
    rd = RunDir.create(tmp_path / ".capevolve", ts="b1", budget=Budget(max_iterations=1))
    seed = _seed(rd.candidate_dir("seed"))
    cp = _seed(rd.candidate_dir("cand_null"))
    (cp / "INSIGHTS.md").write_text("notes")
    (Path(rd.rollouts) / "val").mkdir(parents=True, exist_ok=True)
    for tag in ("seed", "cand_null"):
        (Path(rd.rollouts) / "val" / f"t1__{tag}__t0.json").write_text(
            json.dumps({"rollout": {}, "score": {"reward": 1.0}}))
        eval_index.record(rd, rd.candidate_dir(tag), "val", tag, ["t1"], [0])
    h = eval_index.cap_hash(seed)
    assert eval_index.cap_hash(cp) == h
    assert eval_index.counts(rd, h, "val")["t1"][1] == 2  # pooled across both tags
    # backfill rebuilds the ledger (rebuild-safe for ledgers written with the old hash)
    eval_index.backfill(rd)
    assert eval_index.missing(rd, h, ["t1"], 2) == {}
