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


def test_transcript_turn_skips_system_line_with_string_message():
    """A "system" line can carry a plain string ``message`` (e.g. a permission-denial
    notice) instead of the usual ``{"content": [...]}`` dict. ``.get()`` on a string
    used to raise AttributeError before the type ever got checked."""
    from cap_evolve import dashboard
    ev = {"type": "system", "subtype": "permission_denied",
          "message": "Permission to use Write has been denied."}
    assert dashboard._transcript_turn(ev) is None


def test_transcript_with_string_message_system_line_does_not_crash_reduce_run():
    """Regression for a real run (host/transcript.jsonl line 239): a system line whose
    "message" is a plain string used to crash _transcript_turn, which cascaded through
    reduce_run and 500'd GET /api/runs/{run_id} for the whole run, not just this panel."""
    rd, dashboard = _make_run()
    hdir = rd.root / "host"
    hdir.mkdir()
    real_permission_denied_line = (
        '{"type":"system","subtype":"permission_denied","tool_name":"Write",'
        '"tool_use_id":"toolu_bdrk_01GGCHTW4SctBqUjDWoxYp9t","agent_id":"ad621f6b49843494a",'
        '"decision_reason_type":"asyncAgent",'
        '"decision_reason":"Permission prompts are not available in this context",'
        '"message":"Permission to use Write has been denied. IMPORTANT: You *may* attempt '
        'to accomplish this action using other tools that might naturally be used to '
        'accomplish this goal, e.g. using head instead of cat. But you *should not* attempt '
        'to work around this denial in malicious ways, e.g. do not use your ability to run '
        'tests to execute non-test actions. You should only try to work around this '
        'restriction in reasonable ways that do not attempt to bypass the intent behind '
        'this denial. If you believe this capability is essential to complete the user\'s '
        'request, STOP and explain to the user what you were trying to do and why you need '
        'this permission. Let the user decide how to proceed.",'
        '"uuid":"e141aa19-5db5-4d49-a823-cc29fa0c3d5c","session_id":"a7e94a62-23c9-4200-94ed-'
        'a8f5b192f7a4"}'
    )
    transcript = [
        {"type": "assistant", "timestamp": "2026-09-03T12:00:00Z",
         "message": {"content": [{"type": "text", "text": "Before the bad line."}]}},
        real_permission_denied_line,  # raw text: the fixture line as it appears on disk
        {"type": "assistant", "timestamp": "2026-09-03T12:00:02Z",
         "message": {"content": [{"type": "text", "text": "After the bad line."}]}},
    ]
    lines = [t if isinstance(t, str) else json.dumps(t) for t in transcript]
    (hdir / "transcript.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    reduced = dashboard.reduce_run(rd)  # must not raise
    hs = reduced["summary"]["host_session"]
    assert hs["transcript_total_lines"] == 3
    assert len(hs["transcript_turns"]) == 2
    assert "Before the bad line" in hs["transcript_turns"][0]["text"]
    assert "After the bad line" in hs["transcript_turns"][1]["text"]


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
