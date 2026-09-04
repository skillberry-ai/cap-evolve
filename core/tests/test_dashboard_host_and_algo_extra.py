"""Coverage for #432 (host/driver_prompt.md + host/transcript.jsonl reach the
dashboard payload) and #433 (algo_extra's compliance capability flag is actually set,
so the frontend has something to gate the panel on).

Both gaps were the same shape: the data existed on disk / in ``events.jsonl`` and was
silently dropped before it reached the JSON the browser renders.
"""

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))


def _make_run(events=None):
    from cap_evolve import Budget, RunDir, dashboard
    tmp = Path(tempfile.mkdtemp())
    rd = RunDir.create(tmp, ts="t", budget=Budget())
    events = events if events is not None else [{"t": 1.0, "kind": "splits",
                                                  "train": 1, "val": 1, "test": 1, "seed": 0}]
    rd.events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    return rd, dashboard


def test_no_host_dir_means_no_host_session():
    """A deterministic-loop run has no ``host/`` dir — the panel must hide, not error."""
    rd, dashboard = _make_run()
    reduced = dashboard.reduce_run(rd)
    assert reduced["summary"]["host_session"] == {}
    assert reduced["summary"]["capabilities"]["host_transcript"] is False


def test_driver_prompt_and_transcript_are_read_and_summarized():
    rd, dashboard = _make_run()
    hdir = rd.root / "host"
    hdir.mkdir()
    (hdir / "driver_prompt.md").write_text("# Brief\n\nDo the thing.", encoding="utf-8")
    transcript = [
        {"type": "system", "subtype": "hook_started"},  # plumbing — must be dropped
        {"type": "assistant", "timestamp": "2026-09-03T12:00:00Z",
         "message": {"content": [{"type": "text", "text": "Looking at the run dir first."}]}},
        {"type": "assistant", "timestamp": "2026-09-03T12:00:01Z",
         "message": {"content": [{"type": "tool_use", "name": "Bash",
                                   "input": {"command": "ls -la"}}]}},
        {"type": "user", "timestamp": "2026-09-03T12:00:02Z",
         "message": {"content": [{"type": "tool_result", "content": "total 0"}]}},
    ]
    (hdir / "transcript.jsonl").write_text(
        "\n".join(json.dumps(e) for e in transcript) + "\n", encoding="utf-8")

    reduced = dashboard.reduce_run(rd)
    hs = reduced["summary"]["host_session"]
    assert reduced["summary"]["capabilities"]["host_transcript"] is True
    assert "Do the thing" in hs["driver_prompt"]
    assert hs["transcript_total_lines"] == 4
    # the plumbing "system" line contributed nothing; the other three did.
    assert len(hs["transcript_turns"]) == 3
    assert hs["transcript_turns"][0]["role"] == "assistant"
    assert "Looking at the run dir" in hs["transcript_turns"][0]["text"]
    assert "[tool] Bash" in hs["transcript_turns"][1]["text"]
    assert "[result] total 0" in hs["transcript_turns"][2]["text"]
    assert hs["transcript_truncated"] is False


def test_oversized_transcript_is_not_parsed_just_pointed_at():
    """A multi-megabyte transcript must never be read into memory whole and rendered —
    the section links out to the real path instead."""
    rd, dashboard = _make_run()
    hdir = rd.root / "host"
    hdir.mkdir()
    big_line = json.dumps({"type": "assistant",
                            "message": {"content": [{"type": "text", "text": "x" * 1000}]}})
    with (hdir / "transcript.jsonl").open("w", encoding="utf-8") as f:
        # cheap way to exceed _HOST_TRANSCRIPT_MAX_BYTES without writing real MBs of test data
        f.write((big_line + "\n") * 1)
    import cap_evolve.dashboard as dmod
    orig = dmod._HOST_TRANSCRIPT_MAX_BYTES
    dmod._HOST_TRANSCRIPT_MAX_BYTES = 10  # force the "too large" branch deterministically
    try:
        reduced = dashboard.reduce_run(rd)
    finally:
        dmod._HOST_TRANSCRIPT_MAX_BYTES = orig
    hs = reduced["summary"]["host_session"]
    assert hs["transcript_too_large"] is True
    assert "transcript_turns" not in hs
    assert hs["transcript_path"].endswith("transcript.jsonl")


def test_compliance_capability_flag_is_set_when_events_present():
    """Issue #433: ``algo_extra['compliance']`` was already computed but no
    ``capabilities.compliance`` flag existed for the frontend to gate a panel on."""
    events = [
        {"t": 1.0, "kind": "splits", "train": 1, "val": 1, "test": 1, "seed": 0},
        {"t": 2.0, "kind": "agent_optimize_compliance", "tag": "cand_a", "iteration": 1,
         "screened_before_fullval": False},
    ]
    rd, dashboard = _make_run(events)
    reduced = dashboard.reduce_run(rd)
    assert reduced["summary"]["capabilities"]["compliance"] is True
    (row,) = reduced["summary"]["algo_extra"]["compliance"]
    assert row["candidate"] == "cand_a" and row["screened_before_fullval"] is False


def test_compliance_capability_flag_absent_by_default():
    rd, dashboard = _make_run()
    reduced = dashboard.reduce_run(rd)
    assert reduced["summary"]["capabilities"]["compliance"] is False
    assert "compliance" not in reduced["summary"]["algo_extra"]


if __name__ == "__main__":  # self-check without pytest
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok", name)
