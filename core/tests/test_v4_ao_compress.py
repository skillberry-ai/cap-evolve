"""AO-2 V4: the compress operator cadence, and the near-miss confirm extension driven through the conductor."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import ao2_fakes as F  # noqa: E402

import conductor  # noqa: E402
from test_ao2_p2_mode import SPEC, _make, _run  # noqa: E402


def _record(be):
    seen = []
    orig = be.start

    def start(job):
        if job["kind"] == "propose":
            seen.append(dict(job))
        return orig(job)
    be.start = start
    return seen


def test_compress_off_by_default():
    assert conductor.Cfg.from_spec({**SPEC}).compress_every == 0
    assert conductor.Cfg.from_spec({**SPEC, "ao_compress_every": 5}).compress_every == 5


def test_a_compress_job_runs_on_the_champion_at_most_once_per_champion(tmp_path):
    be, cfg = _make(tmp_path, [0.45, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0], cap=9000, k=2, spec={"ao_compress_every": 2})
    seen = _record(be)
    c, be = _run(be, cfg)
    comp = [j for j in seen if j.get("compress")]
    assert c.champion != "seed" and comp, "a champion exists, so a compress job must have been launched"
    assert all(j["parent"] in c.st["compressed"] for j in comp)
    assert len(c.st["compressed"]) == len(set(c.st["compressed"]))          # once per champion
    assert "seed" not in c.st["compressed"]                                 # never compress the untouched seed
    assert all(j["slot"] == 0 for j in comp)


def test_no_compress_job_without_the_flag(tmp_path):
    be, cfg = _make(tmp_path, [0.45, 0.0, 0.0, 0.0], cap=7000, k=2)
    seen = _record(be)
    _run(be, cfg)
    assert not any(j.get("compress") for j in seen)


def test_a_near_miss_is_extended_through_the_conductor_and_decided(tmp_path):
    be, cfg = _make(tmp_path, [0.22, 0.0, 0.0], cap=9000, k=1, slots=3,
                    spec={"p2_z_conf": 3.0, "p2_extend_z": 0.5, "p2_conf_n": 48})
    # k=1 uses the group-sequential test; use k=2 so the round has a confirmation stage
    be, cfg = _make(tmp_path / "x" if (tmp_path / "x").mkdir() is None else tmp_path, [0.22, 0.0, 0.0, 0.0], cap=9000,
                    k=2, slots=3, spec={"p2_z_conf": 3.0, "p2_extend_z": 0.5, "p2_conf_n": 48})
    c, be = _run(be, cfg)
    assert be.run_dir.spent.metric_calls <= 9000
    statuses = {n["status"] for n in c.st["nodes"].values()}
    assert "racing" not in statuses and "confirming" not in statuses        # nothing left half-decided
