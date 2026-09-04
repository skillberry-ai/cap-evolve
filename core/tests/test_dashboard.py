"""Wave-4 observability: the reducer folds events → a well-formed candidate graph
+ run-summary, the HTML renderer is self-contained and parseable, secrets are
redacted before they reach the artifact, and optional panels degrade silently.
"""

import html.parser
import json
import re
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
            assert n["status"] in ("seed", "accepted", "rejected", "indecisive", "failed")

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
        assert s["counts"] == {"accepted": 1, "rejected": 1, "indecisive": 0, "failed": 0,
                                   "seed": 1, "total": 3}
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
        # The panel set the self-contained artifact must always carry. "Annotations &
        # diagnoses" was folded into the Activity log, which shows the same optimizer
        # stderr / diagnosis text with a timestamp, phase and candidate attached.
        for panel in ("Summary", "Run status", "Score over iterations",
                      "Per-task pass/fail", "Lineage", "Candidates",
                      "Cost ledger", "Gate decisions", "Activity log"):
            assert panel in text, f"missing panel: {panel}"


def test_render_html_shows_per_iteration_latency():
    """``summary.per_iteration`` (optimizer vs runner seconds per step) is COMPUTED
    by the reducer regardless of rendering — this asserts the HTML artifact actually
    renders it as a visible panel, not just carries it in the embedded JSON payload."""
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), events=_BASE_EVENTS, baseline=_BASELINE,
                     final={"test": {"reward": 0.8}, "best_id": "cand_0001"})
        r = dashboard.reduce_run(rd)
        assert [n["optimizer_seconds"] for n in r["summary"]["per_iteration"]] == [1.2, 1.0]
        text = dashboard.render_html(r, rd)
        _parse_html(text)
        assert "Per-iteration timing" in text
        assert "S.per_iteration" in text


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


# ---- Process narrative: template-only detection ---------------------------

def test_narrative_flags_an_unedited_seed_template():
    """A run-level accumulator file that is STILL byte-for-byte its seed instructional
    template (no real handover was ever appended) must not be presented as populated
    narrative — it needs its own ``template_only`` flag so the renderer can flag it."""
    from cap_evolve import dashboard, harness
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), events=_BASE_EVENTS, baseline=_BASELINE)
        (rd.root / "JOURNAL.md").write_text(harness._JOURNAL_SEED, encoding="utf-8")
        r = dashboard.reduce_run(rd)
        (journal,) = [f for f in r["summary"]["narrative"]["files"]
                      if f["title"].startswith("Journal")]
        assert journal["template_only"] is True

        html = dashboard.render_html(r, rd)
        _parse_html(html)
        assert "template only" in html


def test_narrative_does_not_flag_a_real_appended_entry():
    """The moment a real entry is appended below the marker, the file is no longer
    byte-identical to its seed — must not be flagged."""
    from cap_evolve import dashboard, harness
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), events=_BASE_EVENTS, baseline=_BASELINE)
        real = harness._JOURNAL_SEED + "\n## Iteration cand_0001 — a real handover\n- did X\n"
        (rd.root / "JOURNAL.md").write_text(real, encoding="utf-8")
        r = dashboard.reduce_run(rd)
        (journal,) = [f for f in r["summary"]["narrative"]["files"]
                      if f["title"].startswith("Journal")]
        assert journal["template_only"] is False


# ---- Config tab: full run configuration ------------------------------------

def _mk_project(base: Path, *, extra_spec: str = "", write_project_md: bool = True):
    """A minimal project dir mirroring the real tau2_airline layout (capevolve.yaml,
    PROJECT.md, adapters/, seed_capability/) without depending on the live path."""
    proj = base / "project"
    proj.mkdir(parents=True, exist_ok=True)
    (proj / "capevolve.yaml").write_text(
        "capabilities:       [system-prompt, tools]\n"
        "capability_path:    seed_capability\n"
        "algorithm_skill:    agent-optimize\n"
        "optimizer_skill:    claude-code\n"
        "gate_mode:          paired\n"
        "gate_k_se:          1.0\n"
        "split_ids_file:     split_ids.json\n"
        + extra_spec, encoding="utf-8")
    if write_project_md:
        (proj / "PROJECT.md").write_text(
            "# Project\n\n- num_trials=1 — single-trial scores\n", encoding="utf-8")
    (proj / "adapters").mkdir(exist_ok=True)
    (proj / "adapters" / "adapter.py").write_text(
        "def run_target():\n    pass\n", encoding="utf-8")
    (proj / "seed_capability" / "policy").mkdir(parents=True, exist_ok=True)
    (proj / "seed_capability" / "policy" / "policy.md").write_text(
        "# Policy\nBe helpful.\n", encoding="utf-8")
    return proj


def test_config_reads_spec_groups_project_md_and_files():
    """A future, unrecognised spec key must still show up (in 'Other'), never vanish."""
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        _mk_project(base, extra_spec="future_input:      some-new-thing\n")
        rd = _mk_run(base, events=_BASE_EVENTS, baseline=_BASELINE)
        r = dashboard.reduce_run(rd)
        cfg = r["summary"]["config"]
        assert r["summary"]["capabilities"]["config"] is True

        groups = {g["group"]: {i["key"]: i["value"] for i in g["items"]}
                   for g in cfg["spec_groups"]}
        assert groups["Capability"]["capability_path"] == "seed_capability"
        assert groups["Algorithm & optimizer"]["algorithm_skill"] == "agent-optimize"
        assert groups["Budget & gate"]["gate_mode"] == "paired"
        # unrecognised key lands in "Other", not dropped
        assert groups["Other"]["future_input"] == "some-new-thing"

        assert "single-trial scores" in cfg["project_md"]

        files = {f["path"]: f for f in cfg["files"]}
        assert "adapters/adapter.py" in files
        assert "def run_target" in files["adapters/adapter.py"]["preview"]
        assert "seed_capability/policy/policy.md" in files
        # capevolve.yaml / PROJECT.md are shown separately, not duplicated in the tree
        assert "capevolve.yaml" not in files
        assert "PROJECT.md" not in files

        html = dashboard.render_html(r, rd)
        _parse_html(html)
        assert "Config — run configuration" in html
        assert "future_input" in html


def test_config_degrades_binary_and_oversized_files():
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        proj = _mk_project(base)
        (proj / "seed_capability" / "reference").mkdir(parents=True, exist_ok=True)
        (proj / "seed_capability" / "reference" / "blob.bin").write_bytes(bytes(range(256)) * 4)
        big = proj / "seed_capability" / "reference" / "huge.py"
        big.write_text("x = 1\n" * 60000, encoding="utf-8")  # > 200_000 bytes

        rd = _mk_run(base, events=_BASE_EVENTS, baseline=_BASELINE)
        r = dashboard.reduce_run(rd)
        files = {f["path"]: f for f in r["summary"]["config"]["files"]}

        blob = files["seed_capability/reference/blob.bin"]
        assert blob["binary"] is True
        assert blob["preview"] is None

        huge = files["seed_capability/reference/huge.py"]
        assert huge["binary"] is False
        assert huge["preview"] is None  # too large to preview — size + path only
        assert huge["size"] > 200_000

        html = dashboard.render_html(r, rd)
        _parse_html(html)  # renders without trying to dump the huge/binary file


def test_config_absent_without_a_project_dir():
    """No sibling project/ at all → the panel's data is absent, not faked."""
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        rd = _mk_run(Path(d), events=_BASE_EVENTS, baseline=_BASELINE)
        r = dashboard.reduce_run(rd)
        assert r["summary"]["config"] == {}
        assert r["summary"]["capabilities"]["config"] is False
        # The Config panel's JS guards on `CFG.project_dir`, not on `CFG` itself: `{}` is
        # truthy in JS, so a bare `if(!CFG)return` would render an empty panel claiming to
        # have read the config "straight off undefined". (Can't be asserted from the HTML
        # text — the section title is a JS string literal that is always present.)
        assert "project_dir" not in r["summary"]["config"]


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


# ---- SPA + shipped bundles: offline/air-gapped (no CDN) -------------------

def test_shipped_spa_bundles_have_no_external_cdn_reference():
    """The self-contained dashboard.html is guarded above; the React SPA and the
    committed prebuilt bundles served at runtime need the same guarantee, or the
    "zero runtime deps / offline" story silently breaks in air-gapped evals.
    Regression guard for issue #120 (a CDN webfont @import in index.css).

    Deliberately NOT a denylist of known CDN hosts: that only ever catches the
    CDNs someone already thought of (fonts.bunny.net, typekit.net, the next one).
    We ban the *shape* — any absolute http(s) subresource — with a tiny allowlist.
    Targets are discovered by glob, so a bundle added later is covered by
    construction, and a floor on the discovered count fails loudly if one vanishes.

    ``vendor/`` is excluded: it holds gitignored third-party CLONES an example's setup
    pulls down at onboarding time (a benchmark checkout, the Skillberry services), not
    assets cap-evolve ships. Auditing those made this guard fail on whatever a cloned
    dependency happens to have in its own ``ui/`` — a finding about someone else's
    frontend, which says nothing about our offline story.
    """
    exts = {".css", ".js", ".jsx", ".ts", ".tsx", ".html"}
    # Every shipped/served bundle dir, discovered — not enumerated.
    bundles = sorted(
        p for pat in ("**/dist", "**/ui") for p in REPO.glob(pat)
        if p.is_dir() and "node_modules" not in p.parts
        and p.relative_to(REPO).parts[0] != "site"      # site/ is issue #123
        and p.relative_to(REPO).parts[0] != "vendor"    # third-party clones, see below
    )
    # Glob alone can't notice a bundle that MOVED (it just stops finding it), so the
    # known served bundles are also named and asserted to exist. Glob = new coverage,
    # this list = no silent loss of coverage.
    required = [
        REPO / "dashboard" / "frontend" / "src",
        REPO / "dashboard" / "frontend" / "index.html",
        REPO / "dashboard" / "frontend" / "dist",
        REPO / "examples" / "tau2_airline" / "run_full" / "ui",
    ]
    targets = sorted(set(bundles) | set(required))
    # Anything absolute in a subresource position: @import, url(), href=, src=, import from.
    external = re.compile(
        r"""(?:@import\s+|url\(|href\s*=\s*|src\s*=\s*|from\s+)['"]?\s*"""
        r"""(https?://([A-Za-z0-9.\-]+)[^'"\s)]*)""")
    allowed = {"localhost", "127.0.0.1", "www.w3.org", "w3.org"}  # SVG/XML ns, dev server
    checked = 0
    for t in targets:
        assert t.exists(), f"guard target vanished (renamed/moved?): {t}"
        files = [t] if t.is_file() else sorted(
            p for p in t.rglob("*") if p.is_file() and p.suffix in exts)
        for p in files:
            text = p.read_text(encoding="utf-8", errors="ignore")
            checked += 1
            for url, host in external.findall(text):
                assert host in allowed, (
                    f"{p.relative_to(REPO)} loads an external subresource: {url[:120]}")
    # Floors: a vanished bundle dir or an emptied bundle must fail, not silently pass.
    assert len(bundles) >= 4, f"expected >=4 bundle dirs, discovered {len(bundles)}: {bundles}"
    assert checked >= 60, f"expected >=60 shipped SPA files, checked only {checked} — paths moved?"


def test_gate_fields_read_both_prefixed_and_unprefixed_conventions(tmp_path):
    """The gate-decisions table must find the numbers under EITHER naming convention.

    Both are real and both are on disk: current ``commit.py`` writes ``gate_delta`` &co on
    the accept/reject event, older revisions wrote ``delta``/``stderr``/``n``/``k_se``/
    ``threshold``/``resolvable_effect_size`` directly. Reading only the prefixed spelling
    made every already-completed run of the older kind render "—" for every gate stat and
    fall back to regexing the prose ``reason`` — with the real numbers in the same event.
    """
    from cap_evolve.dashboard import reduce_run
    numbers = {"delta": 0.05, "stderr": 0.0705, "n": 30, "k_se": 1.0,
               "threshold": 0.0295, "resolvable_effect_size": 0.0589}
    for prefixed in (False, True):
        payload = ({"gate_" + k: v for k, v in numbers.items()} if prefixed
                   else dict(numbers))
        rd = _mk_run(tmp_path / ("pre" if prefixed else "un"), events=[
            {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.5},
            {"kind": "evaluate", "split": "val", "tag": "c1", "reward": 0.55},
            # No parseable numbers in the prose: the structured fields are the only source.
            {"kind": "accept", "candidate": "c1", "val": 0.55,
             "note": "accepted on the driver's judgement", **payload},
        ])
        row = next(r for r in reduce_run(rd)["summary"]["gate_decisions"]
                   if r["candidate"] == "c1")
        for field, want in numbers.items():
            assert row[field] == want, (
                f"{'prefixed' if prefixed else 'unprefixed'} {field!r}: "
                f"got {row[field]!r}, want {want!r}")


def test_gate_prefixed_field_wins_over_unprefixed(tmp_path):
    """When an event carries both, the PREFIXED (current-convention) value is used."""
    from cap_evolve.dashboard import reduce_run
    rd = _mk_run(tmp_path, events=[
        {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.5},
        {"kind": "accept", "candidate": "c1", "val": 0.55, "note": "ok",
         "gate_delta": 0.05, "delta": 0.99},
    ])
    row = next(r for r in reduce_run(rd)["summary"]["gate_decisions"]
               if r["candidate"] == "c1")
    assert row["delta"] == 0.05


def test_gate_regex_on_prose_is_still_the_last_resort(tmp_path):
    """Even-older data has neither convention — the prose scrape must still work."""
    from cap_evolve.dashboard import reduce_run
    rd = _mk_run(tmp_path, events=[
        {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.5},
        {"kind": "step", "candidate": "c1", "val": 0.55, "accept": True,
         "reason": "accept: Δ̄ = 0.0500 > 1.0·SE=0.0295 (SE=0.0295, n=30)"},
    ])
    row = next(r for r in reduce_run(rd)["summary"]["gate_decisions"]
               if r["candidate"] == "c1")
    assert row["delta"] == 0.05 and row["n"] == 30


def test_control_replicates_are_detected_by_tag_prefix(tmp_path):
    """Null-control replicates are identifiable ONLY by their ``ctl_null`` tag today.

    Nothing in round.py/commit.py sets ``role``/``is_control``, so requiring either dropped
    the entire noise-floor section on every real run that measured one — including a run
    whose controls swung 0.06, more than the accepted candidate's own delta. Controls must
    reach the ``controls`` list AND the evaluations table, labelled as controls.
    """
    from cap_evolve.dashboard import reduce_run
    rd = _mk_run(tmp_path, events=[
        {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.50},
        {"kind": "evaluate", "split": "val", "tag": "ctl_null_i0", "reward": 0.58,
         "stderr": 0.069, "n_scored": 30},
        {"kind": "evaluate", "split": "val", "tag": "ctl_null_i0r1", "reward": 0.57},
        {"kind": "evaluate", "split": "val", "tag": "ctl_null_i3a1", "reward": 0.65},
        {"kind": "evaluate", "split": "val", "tag": "cand_1", "reward": 0.61},
    ])
    S = reduce_run(rd)["summary"]
    assert [c["tag"] for c in S["controls"]] == ["ctl_null_i0", "ctl_null_i0r1", "ctl_null_i3a1"]
    assert S["controls"][0]["reward"] == 0.58 and S["controls"][0]["n"] == 30
    assert S["capabilities"]["controls"] is True
    # ...and they are not invisible in the eval table either (the old bug put them in NEITHER).
    ctl_rows = [e for e in S["evaluations"] if e["kind"] == "control"]
    assert [e["candidate"] for e in ctl_rows] == [c["tag"] for c in S["controls"]]
    assert "cand_1" not in [e["candidate"] for e in ctl_rows]


def test_control_replicates_still_detected_by_explicit_role_field(tmp_path):
    """Forward-compatibility: an explicit ``role``/``is_control`` marker also counts."""
    from cap_evolve.dashboard import reduce_run
    rd = _mk_run(tmp_path, events=[
        {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.5},
        {"kind": "evaluate", "split": "val", "tag": "replay_a", "reward": 0.51,
         "role": "control"},
        {"kind": "evaluate", "split": "val", "tag": "replay_b", "reward": 0.49,
         "is_control": True},
    ])
    assert [c["tag"] for c in reduce_run(rd)["summary"]["controls"]] == ["replay_a", "replay_b"]


def test_a_plain_candidate_eval_is_not_mistaken_for_a_control(tmp_path):
    """The prefix must not swallow ordinary tags — no controls means an absent section."""
    from cap_evolve.dashboard import reduce_run
    rd = _mk_run(tmp_path, events=[
        {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.5},
        {"kind": "evaluate", "split": "val", "tag": "controller_fix", "reward": 0.55},
        {"kind": "evaluate", "split": "val", "tag": "cand_1", "reward": 0.55},
    ])
    S = reduce_run(rd)["summary"]
    assert S["controls"] == [] and S["capabilities"]["controls"] is False


def test_optimizer_spend_recorded_only_in_state_json_is_attributed(tmp_path):
    """Money and time must land in the SAME bucket.

    An agent-mode run whose proposer spend reaches only state.json's Spent attributed $0 of
    it, so the KPI strip showed one dollar figure as both "cost" and "unattributed" (100%
    unattributed) while the wall-clock KPI put every second in the other bucket.
    """
    from cap_evolve.dashboard import reduce_run
    rd = _mk_run(tmp_path, events=[
        {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.5, "cost_usd": 0.0},
        {"kind": "accept", "candidate": "c1", "val": 0.6, "note": "ok"},
    ])
    rd.update_spent(optimizer_usd=4.8, optimizer_tokens=69224, optimizer_seconds=12.0)
    L = reduce_run(rd)["summary"]["cost_ledger"]
    assert abs(L["unattributed_usd"]) < 0.001, L
    recon = [r for r in L["rows"] if r["kind"] == "optimizer_reconciliation"]
    assert len(recon) == 1 and abs(recon[0]["usd"] - 4.8) < 1e-6


def test_config_section_survives_a_project_dir_with_no_spec(tmp_path):
    """No capevolve.yaml is a NOTE, not a reason to omit every project artifact."""
    from cap_evolve.dashboard import reduce_run
    rd = _mk_run(tmp_path, events=[
        {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.5},
    ])
    proj = rd.root.parent / "project"
    (proj / "adapters").mkdir(parents=True)
    (proj / "adapters" / "adapter.py").write_text("# real adapter\n", encoding="utf-8")
    cfg = reduce_run(rd)["summary"]["config"]
    assert cfg["spec_missing"] is True
    assert [f["path"] for f in cfg["files"]] == ["adapters/adapter.py"]
