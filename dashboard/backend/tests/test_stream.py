import json


def test_sse_format():
    from capevolve_dashboard import stream
    out = stream.sse_format("event", {"kind": "step"})
    assert out == 'event: event\ndata: {"kind": "step"}\n\n'


def test_read_new_events_incremental(tmp_path):
    from capevolve_dashboard import stream
    p = tmp_path / "events.jsonl"
    p.write_text(json.dumps({"kind": "baseline", "val": 0.25}) + "\n", encoding="utf-8")
    events, off = stream.read_new_events(p, 0)
    assert events == [{"kind": "baseline", "val": 0.25}]
    assert off == p.stat().st_size

    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"kind": "step", "candidate": "cand_0001"}) + "\n")
    events2, off2 = stream.read_new_events(p, off)
    assert events2 == [{"kind": "step", "candidate": "cand_0001"}]
    assert off2 == p.stat().st_size


def test_read_new_events_ignores_partial_trailing_line(tmp_path):
    from capevolve_dashboard import stream
    p = tmp_path / "events.jsonl"
    p.write_text('{"kind": "baseline"}\n{"kind": "ste', encoding="utf-8")  # partial
    events, off = stream.read_new_events(p, 0)
    assert events == [{"kind": "baseline"}]
    assert off == len('{"kind": "baseline"}\n')  # partial line not consumed
