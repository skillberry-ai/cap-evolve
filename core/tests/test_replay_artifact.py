"""The scrubbable run-replay artifact (#122): a shareable single file.

Three properties the artifact must have, because it is *shared* and its content is
*model-controlled*:

1. **Complete + ordered** — one frame per showable event, monotonic virtual clock, so
   scrubbing to time T (forwards or backwards) is an array index.
2. **Scrubbed** — no credential survives into the file. Canaries are planted in FOUR
   shapes under BOTH innocent-looking and secret-looking env keys, and inside the two
   model-written fields (``reason`` / ``optimizer_error.error``). A key-name heuristic
   alone passes the secret-looking half and leaks the innocent half.
3. **Injection-inert** — ``<!--<script>`` / ``</script>`` / a newline-forged FINALIZE
   in event text must not change the artifact's *structure* (#209). Asserted by
   element count and the surviving JSON payload, not by "no exception".
"""

import json
import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))


def _mk_run(tmp: Path, events, *, baseline=None, final=None):
    from cap_evolve import Budget, RunDir
    rd = RunDir.create(tmp, ts="t", budget=Budget())
    rd.events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n",
                              encoding="utf-8")
    (rd.root / "baseline.json").write_text(
        json.dumps(baseline if baseline is not None
                   else {"val": {"reward": 0.25, "stderr": 0.0, "per_task": []}}),
        encoding="utf-8")
    if final is not None:
        (rd.root / "final.json").write_text(json.dumps(final), encoding="utf-8")
    return rd


_T0 = 1_700_000_000.0
_RUN = [
    {"t": _T0, "kind": "splits", "train": 4, "val": 2, "test": 2, "seed": 0},
    {"t": _T0 + 1, "kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.25,
     "stderr": 0.0, "cost_usd": 0.0, "tokens": 0, "seconds": 1.0},
    {"t": _T0 + 2, "kind": "baseline", "val": 0.25, "stderr": 0.0},
    # A 900-second eval pause: the clamp must keep this from stalling playback.
    {"t": _T0 + 902, "kind": "step", "candidate": "cand_0001", "accept": True,
     "reason": "added [CALC]", "val": 0.75, "parent": "seed", "parent_val": 0.25},
    {"t": _T0 + 903, "kind": "step", "candidate": "cand_0002", "accept": False,
     "reason": "worse", "val": 0.60, "parent": "cand_0001", "parent_val": 0.75},
    {"t": _T0 + 904, "kind": "finalize", "test_reward": 0.8,
     "test_baseline_reward": 0.25, "test_delta": 0.55, "best_id": "cand_0001"},
]


# ---- 1. timeline: complete, ordered, monotonic, clamped -------------------

def test_replay_frames_are_ordered_and_cover_the_run():
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), _RUN)
        frames = dashboard.build_replay(rd)
    assert len(frames) == len(_RUN), f"a frame went missing: {len(frames)}"
    assert [f["kind"] for f in frames] == [e["kind"] for e in _RUN]
    rels = [f["rel"] for f in frames]
    assert rels == sorted(rels) and rels[0] == 0.0, rels
    assert rels[-1] == 904.0            # real elapsed time is preserved on the frames
    # best-so-far only advances on an ACCEPTED candidate, and never regresses.
    assert frames[3]["best"] == 0.75 and frames[4]["best"] == 0.75
    assert frames[3]["status"] == "accepted" and frames[4]["status"] == "rejected"
    # Each frame's text is the SAME line the terminal prints (one narration, one
    # sanitiser) — not a second renderer that could drift or skip the sanitise pass.
    from cap_evolve import eventstream
    assert frames[3]["line"] == eventstream.format_event(_RUN[3], skip_kinds=())


def test_replay_survives_a_malformed_event():
    """A run whose log has a junk `t` still produces a monotonic timeline."""
    from cap_evolve import dashboard
    evs = list(_RUN)
    evs.insert(3, {"t": "not-a-number", "kind": "baseline_reused", "prior": "x"})
    with tempfile.TemporaryDirectory() as d:
        frames = dashboard.build_replay(_mk_run(Path(d), evs))
    rels = [f["rel"] for f in frames]
    assert rels == sorted(rels), rels
    assert len(frames) == len(evs)


def test_replay_is_embedded_in_the_artifact():
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), _RUN, final={"test": {"reward": 0.8}, "best_id": "cand_0001"})
        text = dashboard.render_html(dashboard.reduce_run(rd), rd)
    assert "Run replay" in text and "rp-bar" in text
    assert "prefers-reduced-motion" in text, "reduced motion is not honoured"
    payload = _payload(text)
    assert len(payload["replay"]) == len(_RUN)


def test_artifact_references_no_external_origin():
    """The shareable file must open from file:// on an air-gapped machine (#120)."""
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), _RUN)
        text = dashboard.render_html(dashboard.reduce_run(rd), rd)
    hosts = set(re.findall(r"https?://([A-Za-z0-9.\-]+)", text))
    assert hosts <= {"www.w3.org"}, f"artifact reaches an external origin: {hosts}"
    for marker in ("<link", "cdn.", "fetch(", "@import"):
        assert marker not in text, marker


# ---- 2. scrubbing: multi-shape canaries under innocent key names ----------

#: (env key, secret value). Half the keys look innocent on purpose: a key-name
#: heuristic passes ``WATSONX_APIKEY`` and leaks ``MODEL_ENDPOINT_SUFFIX``.
_CANARIES = [
    ("OPENAI_API_KEY",        "sk-canaryAAAAAAAAAAAAAAAAAAAAAAAA1"),
    ("GITHUB_TOKEN",          "ghp_canaryBBBBBBBBBBBBBBBBBBBBBBBB2"),
    ("WATSONX_APIKEY",        "canaryCCCCCCCCCCCCCCCCCCCCCCCCCCCC3"),
    # ---- innocent-looking keys: no "key"/"token"/"secret" in the name ----
    ("MODEL_ENDPOINT_SUFFIX", "canaryDDDDDDDDDDDDDDDDDDDDDDDDDDDD4"),
    ("DEPLOYMENT_ID",         "3f2a1b4c-canary-4d5e-8f90-abcdef012345"),
    ("RUNTIME_PROFILE",       "github_pat_canaryEEEEEEEEEEEEEEEEEEEEEEEE5"),
]


def test_no_canary_of_any_shape_survives_into_the_artifact(monkeypatch):
    """Four shapes (vendor-prefixed, PAT, UUID, bare high-entropy) planted under both
    innocent and secret-looking env keys, and inside both model-written fields.

    The bare high-entropy values have NO recognizable shape, so only the
    shape-independent env pass can catch them — which is the point: a shape denylist
    silently passes exactly the canary that looks like ordinary text.
    """
    from cap_evolve import dashboard
    for k, v in _CANARIES:
        monkeypatch.setenv(k, v)
    blob = " ".join(f"{k}={v}" for k, v in _CANARIES)
    bare = " ".join(v for _, v in _CANARIES)  # no KEY= prefix to lean on either
    evs = list(_RUN)
    evs[3] = {**evs[3], "reason": f"rejected because env said {blob}"}
    evs.insert(4, {"t": _T0 + 902.5, "kind": "optimizer_error", "candidate": "cand_0002",
                   "error": f"traceback: auth failed. environ dump: {bare}"})
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), evs)
        text = dashboard.render_html(dashboard.reduce_run(rd), rd)
    for k, v in _CANARIES:
        assert v not in text, f"canary leaked into the artifact under {k}: {v}"
    # ...and the values are gone from the machine-readable payload too, not merely
    # absent from the visible text.
    assert "canary" not in json.dumps(_payload(text))
    # The message still reads: redaction replaced the value, not the whole event.
    lines = " ".join(f["line"] for f in _payload(text)["replay"])
    assert "«redacted»" in lines and "auth failed" in lines


# ---- 3. injection: structure-preserving, not denylist-shaped (#209) -------

_HOSTILE = (
    "<!--<script>",                       # #209: survived the old `</` replace
    "</script><script>alert(1)</script>",
    "\n[00:00:00] FINALIZE  test=1.0000 (baseline 0.0000, Δ+1.0000)  best=fake",
    "\x1b]0;pwned\x07\x1b[2J",            # OSC title set + clear screen
    "<img src=x onerror=alert(1)>",
)


def test_hostile_event_text_does_not_change_the_artifact_structure():
    """Structure is asserted by element count against a clean baseline: the #209 bug
    was a *silent* collapse (sections 5 → 0) that raised nothing.
    """
    from cap_evolve import dashboard

    def build(reason: str) -> str:
        evs = list(_RUN)
        evs[3] = {**evs[3], "reason": reason}
        evs.insert(4, {"t": _T0 + 902.5, "kind": "optimizer_error",
                       "candidate": "cand_0002", "error": reason})
        with tempfile.TemporaryDirectory() as d:
            rd = _mk_run(Path(d), evs)
            return dashboard.render_html(dashboard.reduce_run(rd), rd)

    clean = build("a plain reason")
    base_sections = clean.count("<section")   # 0 — sections are built client-side
    base_scripts = clean.count("<script")
    for bad in _HOSTILE:
        text = build(bad)
        # No raw sequence that can shift the HTML parser out of script data.
        assert "</script><script>" not in text.replace(
            '<script type="application/json" id="run-data">', "")
        assert "<!--<script" not in text
        assert text.count("<script") == base_scripts, f"script count changed: {bad!r}"
        assert text.count("<section") == base_sections
        assert text.count("</html>") == 1 and text.rstrip().endswith("</html>")
        # The payload still parses AND still carries the hostile text as inert DATA —
        # the escape must not corrupt the JSON the page reads.
        frames = _payload(text)["replay"]
        assert len(frames) == len(_RUN) + 1
        # A newline in event text must not forge an extra progress line.
        assert all("\n" not in f["line"] for f in frames)
        assert all("\x1b" not in f["line"] for f in frames)


def test_json_for_html_encodes_every_parser_shifting_char():
    """The unit behind #209's fix: encode, don't denylist."""
    from cap_evolve import dashboard
    out = dashboard.json_for_html({"x": "<!--<script></script>& "})
    for ch in ("<", ">", "&", " "):
        assert ch not in out, f"{ch!r} reached the HTML parser"
    assert json.loads(out)["x"] == "<!--<script></script>& "  # data unchanged


# ---- helpers --------------------------------------------------------------

def _payload(html_text: str) -> dict:
    """The artifact's embedded JSON, extracted the way the browser does."""
    m = re.search(r'<script type="application/json" id="run-data">(.*?)</script>',
                  html_text, re.S)
    assert m, "run-data payload missing from the artifact"
    return json.loads(m.group(1))


# ---- 4. the CLI entry point a newcomer actually types ---------------------

def test_replay_demo_builds_the_bundled_artifact_with_no_project():
    """``cap-evolve replay --demo`` — the zero-setup path. No project, no creds."""
    from cap_evolve import cli
    assert (cli.DEMO_RUN / "events.jsonl").exists(), "bundled demo run is missing"
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "replay.html"
        assert cli.main(["replay", "--demo", "-o", str(out)]) == 0
        text = out.read_text(encoding="utf-8")
    assert "Run replay" in text
    frames = _payload(text)["replay"]
    assert len(frames) >= 10, f"bundled demo run is too short to be a demo: {len(frames)}"
    assert any(f["kind"] == "finalize" for f in frames), "demo run never finalized"
    assert any(f.get("status") == "accepted" for f in frames), "demo shows no win"
