"""Wave-4 observability: the reducer folds events → a well-formed candidate graph
+ run-summary, the HTML renderer is self-contained and parseable, secrets are
redacted before they reach the artifact, and optional panels degrade silently.
"""

import html.parser
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))


def _mk_run(tmp: Path, *, events, baseline=None, final=None):
    """Build a minimal run dir with a state.json + events.jsonl (+ optional
    baseline/final) without running an optimizer."""
    from cap_evolve import Budget, RunDir
    rd = RunDir.create(tmp, ts="t", budget=Budget())
    rd.events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
    if baseline is not None:
        (rd.root / "baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
    if final is not None:
        (rd.root / "final.json").write_text(json.dumps(final), encoding="utf-8")
    return rd


def _parse_html(text: str):
    class _P(html.parser.HTMLParser):
        def error(self, message):  # py<3.10 compat: surface malformed markup
            raise AssertionError(message)
    _P().feed(text)


_BASE_EVENTS = [
    {"kind": "splits", "train": 4, "val": 2, "test": 2, "seed": 0},
    {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.25,
     "stderr": 0.0, "cost_usd": 0.0, "tokens": 0, "seconds": 0.0},
    {"kind": "baseline", "val": 0.25, "stderr": 0.0},
    {"kind": "step", "candidate": "cand_0001", "accept": True, "reason": "up",
     "val": 0.75, "parent": "seed", "parent_val": 0.25,
     "optimizer_seconds": 1.2, "runner_seconds": 0.5, "cost_usd": 0.01, "tokens": 500},
    {"kind": "gate_warning", "mode": "paired", "reason": "SE collapsed to 0", "context": "se=0"},
    {"kind": "step", "candidate": "cand_0002", "accept": False, "reason": "down",
     "val": 0.6, "parent": "cand_0001", "parent_val": 0.75,
     "optimizer_seconds": 1.0, "runner_seconds": 0.4, "cost_usd": 0.008, "tokens": 400},
]

_BASELINE = {"val": {"reward": 0.25, "per_task": [
    {"task_id": "t1", "reward": 0.0, "feedback": "wrong"},
    {"task_id": "t2", "reward": 0.5, "feedback": ""}]}, "best_id": "seed"}


# ---- reducer: well-formed graph ------------------------------------------

def test_reduce_run_builds_well_formed_graph():
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), events=_BASE_EVENTS, baseline=_BASELINE,
                     final={"test": {"reward": 0.8, "stderr": 0.05, "pass_k": {"1": 0.8}},
                            "best_id": "cand_0001"})
        r = dashboard.reduce_run(rd)
        g, s = r["graph"], r["summary"]

        # graph shape
        assert set(g.keys()) == {"nodes", "root", "best_id"}
        nodes = {n["id"]: n for n in g["nodes"]}
        assert set(nodes) == {"seed", "cand_0001", "cand_0002"}
        # every node carries the required fields
        for n in g["nodes"]:
            for k in ("id", "parent", "children", "status", "val", "per_task",
                      "cost_usd", "tokens", "seconds", "optimizer_seconds",
                      "runner_seconds", "iteration", "reason", "best_so_far"):
                assert k in n, f"node {n['id']} missing {k}"
            assert n["status"] in ("seed", "accepted", "rejected", "failed")

        # parent → child edges are wired both ways
        assert nodes["seed"]["children"] == ["cand_0001"]
        assert nodes["cand_0001"]["parent"] == "seed"
        assert nodes["cand_0002"]["parent"] == "cand_0001"
        assert nodes["seed"]["status"] == "seed"
        assert nodes["cand_0001"]["status"] == "accepted"
        assert nodes["cand_0002"]["status"] == "rejected"

        # running-best is monotonic non-decreasing
        bests = [n["best_so_far"] for n in sorted(g["nodes"], key=lambda x: x["iteration"])]
        assert bests == sorted(bests)

        # summary KPIs
        assert s["baseline_val"] == 0.25
        assert s["best_val"] == 0.75
        assert s["best_id"] == "cand_0001"
        assert s["counts"] == {"accepted": 1, "rejected": 1, "failed": 0, "seed": 1, "total": 3}
        assert s["test_reward"] == 0.8
        assert s["delta_pct"] == 200.0  # (0.75-0.25)/0.25*100
        assert s["frontier"] >= 1
        assert len(s["gate_warnings"]) == 1
        # optimizer vs runner split is preserved
        assert s["optimizer_seconds"] == 2.2
        assert s["runner_seconds"] == 0.9
        assert s["tokens"] == 900


def test_failed_candidate_status():
    """A step with no val and no rollouts is classified 'failed', not 'rejected'."""
    from cap_evolve import dashboard
    evs = _BASE_EVENTS[:3] + [
        {"kind": "optimizer_error", "candidate": "cand_0001", "error": "boom"},
        {"kind": "step", "candidate": "cand_0001", "accept": False, "reason": "opt error",
         "val": None, "parent": "seed"},
    ]
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), events=evs, baseline=_BASELINE)
        r = dashboard.reduce_run(rd)
        node = {n["id"]: n for n in r["graph"]["nodes"]}["cand_0001"]
        assert node["status"] == "failed"
        # the optimizer_error became a diagnosis annotation
        assert any(diag["kind"] == "optimizer_error" for diag in r["summary"]["diagnoses"])


# ---- redaction ------------------------------------------------------------

def test_redact_scrubs_secrets():
    from cap_evolve.dashboard import redact
    obj = {
        "RITS_API_KEY": "rits-abcdef1234567890",
        "nested": {"BOBSHELL_API_KEY": "sk-verysecretkey0123456789", "ok": "fine"},
        "WATSONX_APIKEY": "zzzzzzzz",
        "note": "authorization: Bearer abcdef1234567890token",
        "hexblob": "deadbeef" * 8,
        "list": [{"openai_api_key": "sk-aaaaaaaaaaaaaaaaaa"}],
        "plain": "hello world",
        "reward": 0.5,
    }
    r = redact(obj)
    assert r["RITS_API_KEY"] == "«redacted»"
    assert r["nested"]["BOBSHELL_API_KEY"] == "«redacted»"
    assert r["nested"]["ok"] == "fine"
    assert r["WATSONX_APIKEY"] == "«redacted»"
    assert "«redacted»" in r["note"]          # bearer token masked in-string
    assert r["hexblob"] == "«redacted»"        # long hex blob masked
    assert r["list"][0]["openai_api_key"] == "«redacted»"
    assert r["plain"] == "hello world"                   # innocent values untouched
    assert r["reward"] == 0.5


def test_reducer_output_is_redacted():
    """A secret leaking into an event field must not survive into the reduced run."""
    from cap_evolve import dashboard
    evs = _BASE_EVENTS + [
        {"kind": "optimizer_error", "candidate": "cand_0002",
         "error": "auth failed RITS_API_KEY=rits-supersecret0123456789 retrying"},
    ]
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), events=evs, baseline=_BASELINE)
        blob = json.dumps(dashboard.reduce_run(rd))
        assert "supersecret" not in blob


# ---- HTML rendering: self-contained + parseable ---------------------------

def test_render_html_self_contained_and_parseable():
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), events=_BASE_EVENTS, baseline=_BASELINE,
                     final={"test": {"reward": 0.8}, "best_id": "cand_0001"})
        out = dashboard.write_dashboard(rd)
        text = out.read_text(encoding="utf-8")
        # parses as HTML
        _parse_html(text)
        # no external network resource (the only allowed http is the SVG XML namespace)
        for marker in ('src="http', 'href="http', "<link", "cdn.", "fetch("):
            assert marker not in text, f"dashboard pulls an external resource: {marker}"
        # core panels present
        for panel in ("Summary", "Score over iterations", "Per-task pass/fail",
                      "Lineage", "Candidates", "Annotations"):
            assert panel in text, f"missing panel: {panel}"


def test_dashboard_degrades_without_rollouts_or_finalize():
    """No rollouts, no finalize, no candidate dirs → still reduces + renders."""
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), events=_BASE_EVENTS, baseline=_BASELINE)  # no final.json
        r = dashboard.reduce_run(rd)
        assert r["summary"]["test_reward"] is None
        assert r["summary"]["test_sealed"] in (False, True)
        text = dashboard.render_html(r, rd)
        _parse_html(text)
        # diffs empty (no candidate dirs) — panel hides client-side, doesn't crash
        assert '"diffs": {}' in text or '"diffs":{}' in text


# ---- ANSI terminal --------------------------------------------------------

def test_render_ansi_kpis_and_no_color():
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), events=_BASE_EVENTS, baseline=_BASELINE,
                     final={"test": {"reward": 0.8}, "best_id": "cand_0001"})
        r = dashboard.reduce_run(rd)
        plain = dashboard.render_ansi(r, color=False)
        assert "\033[" not in plain                  # color=False → no ANSI codes
        assert "cap-evolve report" in plain
        assert "best val" in plain and "0.750" in plain
        assert "top" in plain                        # candidate table header


def test_render_ansi_claudecode_margin(monkeypatch):
    """Under CLAUDECODE=1 the report stays within the framed width."""
    from cap_evolve import dashboard
    monkeypatch.setenv("CLAUDECODE", "1")
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), events=_BASE_EVENTS, baseline=_BASELINE)
        r = dashboard.reduce_run(rd)
        # width is clamped; just assert it renders and respects a narrow margin
        w = dashboard._term_width()
        assert 40 <= w <= 200
        out = dashboard.render_ansi(r, color=False)
        assert out  # non-empty


def test_target_profile_event_surfaces_in_summary_and_ansi():
    from cap_evolve import dashboard
    events = _BASE_EVENTS + [
        {"kind": "target_profile", "model": "gpt-oss-120b", "tier": "mid",
         "suggested_num_trials": 5, "resolution_note": ""}]
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), events=events, baseline=_BASELINE)
        r = dashboard.reduce_run(rd)
        assert r["summary"]["target_profile"] == {
            "model": "gpt-oss-120b", "tier": "mid", "resolution_note": ""}
        plain = dashboard.render_ansi(r, color=False)
        assert "consuming model gpt-oss-120b (tier mid)" in plain


def test_no_target_profile_event_leaves_summary_none():
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), events=_BASE_EVENTS, baseline=_BASELINE)
        r = dashboard.reduce_run(rd)
        assert r["summary"]["target_profile"] is None
        assert "consuming model" not in dashboard.render_ansi(r, color=False)
