"""Issue #140 — on-demand reasoning skills + the "mechanism-not-knob" proposal gate.

Two halves with deliberately different epistemic standing, and these tests pin BOTH
plus the boundary between them:

  * the ``mechanism-probe`` reasoning skill reaches the optimizer's workdir for all three
    deterministic algorithms (via #199's shared ``inject`` seam), byte-identical to
    source, and the bar's text is in the rendered prompt;
  * the DECLARATION (three named fields in PROCESS.md) parses precisely, with the seed's
    placeholders counting as missing — no vacuous pass;
  * the gate is **ADVISORY**: the false-rejection probe proves a genuine mechanism-style
    proposal is accepted exactly as it would have been without #140, and an UNDECLARED
    proposal is not rejected either. Nothing but the val gate can reject a candidate.
  * the composed prompt (#219 INSIGHTS + #221 diversify + #222 dead-ends + #140's bar)
    stays under ``MAX_INSTRUCTIONS_CHARS``, and an overflow never silently drops #140's
    block — it lives in the kept tail.
  * no sealed test-split id reaches any injected workdir file.
"""

import json
import os
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
EXAMPLE = REPO / "examples" / "toy_calc"
MOCK_RUN = REPO / "skills" / "optimizers" / "run-optimizer" / "scripts" / "run.py"
PROBE_SRC = REPO / "skills" / "reasoning" / "mechanism-probe"

sys.path.insert(0, str(CORE))


@pytest.fixture(autouse=True)
def _env():
    old = dict(os.environ)
    os.environ["CAPEVOLVE_CORE"] = str(CORE)
    os.environ["CAPEVOLVE_TOY_DATA"] = str(EXAMPLE)
    os.environ["CAPEVOLVE_MOCK_SCRIPT"] = str(EXAMPLE / "mock_script.json")
    yield
    os.environ.clear()
    os.environ.update(old)


def _toy_adapter():
    import importlib.util
    spec = importlib.util.spec_from_file_location("toy_pq", EXAMPLE / "adapter.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.Adapter()


def _setup(tmp_path, ts, **budget):
    from cap_evolve import Budget, RunDir, harness
    adapter = _toy_adapter()
    seed = tmp_path / f"seed_{ts}"
    shutil.copytree(EXAMPLE / "capability", seed)
    run_dir = RunDir.create(tmp_path / ".capevolve", ts=ts, budget=Budget(**budget))
    harness.ensure_splits(adapter, run_dir, seed=0)
    base = harness.baseline(adapter, seed, run_dir=run_dir)
    return adapter, run_dir, base


def _optimizer():
    from cap_evolve import harness
    return harness.optimizer_from_command(
        ["python3", str(MOCK_RUN), "--name", "mock", "--workdir", "{workdir}",
         "--prompt", "{prompt}"])


DECLARED = (
    "# PROCESS\n\n## Proposal declaration\n"
    "- Mechanism: quote_price recomputes the total in-body and refuses a mismatch with "
    "an actionable error, so answering from memory is impossible rather than discouraged.\n"
    "- Hypothesis: the four tax-line failures share one root cause — the total is derived "
    "by the agent instead of by code, so any task with a remembered line hits it.\n"
    "- Expected observable: get_total precedes every quote_price call and the "
    "'expected N got M' feedback disappears from these tasks.\n"
)


# ---- the declaration parses precisely ------------------------------------

def test_a_filled_declaration_parses_all_three_fields(tmp_path):
    from cap_evolve import proposal_quality
    (tmp_path / "PROCESS.md").write_text(DECLARED, encoding="utf-8")
    q = proposal_quality.parse(tmp_path)
    assert q["declared"] is True and q["missing"] == []
    assert "quote_price" in q["mechanism"]
    assert "tax-line" in q["hypothesis"]
    assert "get_total" in q["observable"]


def test_the_seeded_placeholders_count_as_missing(tmp_path):
    """The seed ships ``<...>`` prompts. If those parsed as values the gate would report
    every untouched iteration as fully declared — a vacuous pass."""
    from cap_evolve import harness, proposal_quality
    (tmp_path / "PROCESS.md").write_text(harness._PROCESS_SEED, encoding="utf-8")
    q = proposal_quality.parse(tmp_path)
    assert q["declared"] is False
    assert sorted(q["missing"]) == ["hypothesis", "mechanism", "observable"], q


def test_partial_and_placeholder_values_are_reported_field_by_field(tmp_path):
    from cap_evolve import proposal_quality
    (tmp_path / "PROCESS.md").write_text(
        "- Mechanism: in-body guard on quote_price\n"
        "- Hypothesis: n/a\n"
        "- Expected observable: <what will look different>\n", encoding="utf-8")
    q = proposal_quality.parse(tmp_path)
    assert q["declared"] is False
    assert sorted(q["missing"]) == ["hypothesis", "observable"], q
    assert q["mechanism"] == "in-body guard on quote_price"


def test_markup_and_marker_variants_still_parse(tmp_path):
    """Agents write these headings several ways; the parser must not be brittle about
    bold markers or list bullets, or the record would be empty for a real declaration."""
    from cap_evolve import proposal_quality
    (tmp_path / "PROCESS.md").write_text(
        "* **Mechanism**: in-body validation in `apply_discount`\n"
        "Hypothesis: the rounding cluster\n"
        "  - Expected Observable: no more off-by-one cents in the traces\n",
        encoding="utf-8")
    q = proposal_quality.parse(tmp_path)
    assert q["declared"] is True, q
    assert "apply_discount" in q["mechanism"]


def test_a_declaration_appended_below_the_seed_placeholders_still_counts(tmp_path):
    """The most likely agent shape: leave the seed block alone, append the filled one
    below it. A first-match-only read records that as fully UNDECLARED — inverting the
    exact signal this module exists to observe. Every occurrence must be scanned."""
    from cap_evolve import proposal_quality
    (tmp_path / "PROCESS.md").write_text(
        "## Proposal declaration\n"
        "- Mechanism: <what now behaves differently, and why>\n"
        "- Hypothesis: <which cluster this fixes>\n"
        "- Expected observable: <what will look different next iteration>\n"
        "\n### My declaration\n" + DECLARED.split("## Proposal declaration\n", 1)[1],
        encoding="utf-8")
    q = proposal_quality.parse(tmp_path)
    assert q["declared"] is True, (
        "a filled declaration appended BELOW the seed placeholders read as undeclared "
        f"— the signal is inverted: {q}")
    assert "quote_price" in q["mechanism"] and "get_total" in q["observable"], q


def test_a_bare_observable_label_is_the_same_field(tmp_path):
    """``Expected observable`` is what the seed writes, but agents shorten it. Requiring
    the adjective recorded a real declaration as missing."""
    from cap_evolve import proposal_quality
    (tmp_path / "PROCESS.md").write_text(
        "- Mechanism: in-body guard in apply_discount\n"
        "- Hypothesis: the rounding cluster, one root cause\n"
        "- Observable: no off-by-one cents in the next trajectories\n", encoding="utf-8")
    q = proposal_quality.parse(tmp_path)
    assert q["declared"] is True, q
    assert "off-by-one" in q["observable"], q


def test_a_missing_process_md_never_raises(tmp_path):
    from cap_evolve import proposal_quality
    q = proposal_quality.parse(tmp_path / "nope")
    assert q["declared"] is False and len(q["missing"]) == 3


# ---- ADVISORY: the false-rejection probe ---------------------------------

def test_a_genuine_mechanism_proposal_is_not_rejected(tmp_path):
    """THE test that matters. A real mechanism-style improvement must reach the val gate
    and be accepted on its merits — #140 must not be able to discard a real gain.

    The mock optimizer's edit is a genuine improvement on toy_calc (it raises val), and
    it declares a mechanism. Assert the step ACCEPTED it: the gate outcome is decided by
    the val delta, and #140 contributed no veto.
    """
    from cap_evolve import harness
    adapter, run_dir, base = _setup(tmp_path, "fr", max_iterations=1, stall=3)

    # Wrap the optimizer so the candidate ALSO carries a real declaration, exactly as a
    # mechanism-probe-following optimizer would leave it.
    inner = _optimizer()

    def declaring(workdir, instructions):
        out = inner(workdir, instructions)
        (Path(workdir) / "PROCESS.md").write_text(DECLARED, encoding="utf-8")
        return out

    out = harness.hill_climb_loop(
        adapter, run_dir=run_dir, optimizer=declaring, current_val=base,
        focus="all", max_iterations=1, gate_kwargs={"mode": "significant", "k_se": 1.0},
        algorithm="hill-climb")
    step = out["steps"][-1]
    assert step["accepted"] is True, (
        "FALSE REJECTION: a declared, genuinely-improving mechanism edit was rejected — "
        f"decision={step['decision']}")
    # and the reason is purely the val gate's, with no #140 vocabulary in it.
    reason = step["decision"]["reason"].lower()
    for word in ("mechanism", "knob", "declar", "proposal quality"):
        assert word not in reason, f"#140 leaked into the gate reason: {reason}"


def test_an_undeclared_proposal_is_also_not_rejected(tmp_path):
    """The symmetric half: a missing declaration is a SIGNAL, not a verdict. The bare
    mock edit (no PROCESS.md declaration at all) must be accepted on its val delta —
    otherwise #140 would be silently discarding improvements."""
    from cap_evolve import harness
    adapter, run_dir, base = _setup(tmp_path, "un", max_iterations=1, stall=3)
    out = harness.hill_climb_loop(
        adapter, run_dir=run_dir, optimizer=_optimizer(), current_val=base,
        focus="all", max_iterations=1, gate_kwargs={"mode": "significant", "k_se": 1.0},
        algorithm="hill-climb")
    assert out["steps"][-1]["accepted"] is True, (
        "an UNDECLARED proposal was rejected — the gate is not advisory")
    ev = _events(run_dir, "proposal_quality")
    assert ev and ev[-1]["declared"] is False, ev
    assert ev[-1]["enforcement"] == "advisory", ev[-1]


def test_gepas_local_gate_is_not_enforcing_the_declaration(tmp_path):
    """PER-ALGORITHM probe. The hill-climb pair above only pins ``run_step``; an
    enforcement injected into GEPA's *local* gate passes them all and surfaces only as
    confusing failures in test_gepa.py. Assert here, on GEPA's own event, that an
    UNDECLARED candidate passed the local gate on rewards alone."""
    from cap_evolve import gepa
    adapter, run_dir, base = _setup(tmp_path, "gpadv", max_iterations=1, stall=5)
    gepa.gepa_loop(adapter, run_dir=run_dir, optimizer=_optimizer(), seed_val=base,
                   max_iterations=1, minibatch_size=3, max_merges=0,
                   gate_kwargs={"mode": "significant", "k_se": 1.0})
    pq = _events(run_dir, "proposal_quality")
    assert pq and pq[-1]["declared"] is False, pq
    lg = _events(run_dir, "gepa_local_gate")
    assert lg, "GEPA logged no local gate — the probe would be vacuous"
    assert lg[-1]["passed"] is True, (
        "an UNDECLARED candidate was stopped at GEPA's LOCAL gate — the advisory "
        f"guarantee is broken for gepa: {lg[-1]}")
    # and the local gate's verdict is exactly the reward comparison, nothing else.
    assert (lg[-1]["child_sum"] > lg[-1]["parent_sum"]) is lg[-1]["passed"], lg[-1]


def test_skillopts_step_does_not_enforce_the_declaration(tmp_path):
    """PER-ALGORITHM probe, SkillOpt. It delegates to ``run_step`` today, but that is an
    implementation detail the advisory guarantee should not depend on — pin the outcome
    on SkillOpt's own step record for an UNDECLARED candidate."""
    from cap_evolve import skillopt
    adapter, run_dir, base = _setup(tmp_path, "soadv", max_iterations=2, stall=5)
    out = skillopt.skillopt_loop(adapter, run_dir=run_dir, optimizer=_optimizer(),
                                 current_val=base, epochs=1, batch_size=4,
                                 gate_kwargs={"mode": "significant", "k_se": 1.0},
                                 slow_update=False)
    pq = _events(run_dir, "proposal_quality")
    assert pq and pq[-1]["declared"] is False, pq
    step = out["steps"][-1]
    assert step["accepted"] is True, (
        "an UNDECLARED candidate was rejected under skillopt — the advisory guarantee is "
        f"broken for skillopt: decision={step.get('decision')}")
    reason = str(step["decision"]["reason"]).lower()
    for word in ("mechanism", "knob", "declar", "proposal quality"):
        assert word not in reason, f"#140 leaked into skillopt's gate reason: {reason}"


def test_the_bar_states_it_is_recorded_not_enforced():
    """Honest wording (the #222 lesson: don't claim enforcement nothing enforces)."""
    from cap_evolve import proposal_quality
    block = proposal_quality.PROMPT_BLOCK
    assert "RECORDED per candidate, not enforced" in block
    assert "does NOT reject your edit" in block
    assert "val significance gate remains the only thing that" in block


# ---- the declaration is persisted per candidate --------------------------

def _events(run_dir, kind):
    return [json.loads(ln) for ln in
            run_dir.events_path.read_text(encoding="utf-8").splitlines()
            if json.loads(ln).get("kind") == kind]


def test_the_declaration_is_recorded_per_candidate(tmp_path):
    """FAILS BEFORE THE FIX: no proposal_quality event existed."""
    from cap_evolve import harness
    adapter, run_dir, base = _setup(tmp_path, "rec", max_iterations=1, stall=3)
    inner = _optimizer()

    def declaring(workdir, instructions):
        out = inner(workdir, instructions)
        (Path(workdir) / "PROCESS.md").write_text(DECLARED, encoding="utf-8")
        return out

    harness.hill_climb_loop(
        adapter, run_dir=run_dir, optimizer=declaring, current_val=base,
        focus="all", max_iterations=1, gate_kwargs={"mode": "significant", "k_se": 1.0},
        algorithm="hill-climb")
    ev = _events(run_dir, "proposal_quality")
    assert len(ev) == 1, ev
    assert ev[0]["candidate"] == "cand_0001"
    assert ev[0]["declared"] is True and ev[0]["missing"] == []
    assert "quote_price" in ev[0]["mechanism"]
    assert ev[0]["enforcement"] == "advisory"


def test_the_declaration_is_surfaced_in_the_dashboard(tmp_path):
    """The issue asks for it to be visible. It rides the EXISTING annotations stream,
    and must not read like a gate outcome (it never explains an accept/reject)."""
    from cap_evolve import dashboard, harness
    adapter, run_dir, base = _setup(tmp_path, "dash", max_iterations=1, stall=3)
    inner = _optimizer()

    def declaring(workdir, instructions):
        out = inner(workdir, instructions)
        (Path(workdir) / "PROCESS.md").write_text(DECLARED, encoding="utf-8")
        return out

    harness.hill_climb_loop(
        adapter, run_dir=run_dir, optimizer=declaring, current_val=base,
        focus="all", max_iterations=1, gate_kwargs={"mode": "significant", "k_se": 1.0},
        algorithm="hill-climb")
    state = dashboard.reduce_run(run_dir)["summary"]
    rows = [d for d in state["diagnoses"] if d["kind"] == "proposal_quality"]
    assert len(rows) == 1, state["diagnoses"]
    assert rows[0]["candidate"] == "cand_0001"
    assert "quote_price" in rows[0]["text"] and "expected observable" in rows[0]["text"]
    # and the undeclared case names itself advisory rather than implying a rejection.
    adapter2, rd2, base2 = _setup(tmp_path, "dash2", max_iterations=1, stall=3)
    harness.hill_climb_loop(
        adapter2, run_dir=rd2, optimizer=_optimizer(), current_val=base2,
        focus="all", max_iterations=1, gate_kwargs={"mode": "significant", "k_se": 1.0},
        algorithm="hill-climb")
    row = [d for d in dashboard.reduce_run(rd2)["summary"]["diagnoses"]
           if d["kind"] == "proposal_quality"][0]
    assert "advisory" in row["text"] and "the val gate still decided" in row["text"]


# ---- the skill reaches the optimizer for ALL THREE algorithms ------------

def _assert_probe_in_workdir(workdir: Path):
    """The skill is present, byte-identical to source, and the prompt names it."""
    dst = workdir / "guidance" / "reasoning" / "mechanism-probe" / "SKILL.md"
    assert dst.is_file(), f"mechanism-probe never reached {workdir}"
    assert dst.read_bytes() == (PROBE_SRC / "SKILL.md").read_bytes(), \
        "injected SKILL.md differs from source"
    instr = (workdir / "INSTRUCTIONS.md").read_text(encoding="utf-8")
    assert "guidance/reasoning/mechanism-probe/SKILL.md" in instr, \
        "the prompt never points at the reasoning skill"
    assert "Mechanism:" in instr and "Expected observable:" in instr
    # the honest wording reaches the actual prompt, not just the constant
    assert "RECORDED per candidate, not enforced" in instr
    # and the PROCESS.md the optimizer fills carries the declaration block
    assert "Proposal declaration" in (workdir / "PROCESS.md").read_text(encoding="utf-8")
    return instr


def test_hill_climb_gets_the_reasoning_skill(tmp_path):
    """FAILS BEFORE THE FIX: skills/reasoning/ did not exist and nothing injected it."""
    from cap_evolve import harness
    adapter, run_dir, base = _setup(tmp_path, "hc", max_iterations=1, stall=3)
    harness.hill_climb_loop(
        adapter, run_dir=run_dir, optimizer=_optimizer(), current_val=base,
        focus="all", max_iterations=1, gate_kwargs={"mode": "significant", "k_se": 1.0},
        algorithm="hill-climb")
    _assert_probe_in_workdir(run_dir.root / "work" / "cand_0001")


def test_gepa_gets_the_reasoning_skill(tmp_path):
    from cap_evolve import gepa
    adapter, run_dir, base = _setup(tmp_path, "gp", max_iterations=1, stall=5)
    gepa.gepa_loop(adapter, run_dir=run_dir, optimizer=_optimizer(), seed_val=base,
                   max_iterations=1, minibatch_size=3, max_merges=0,
                   gate_kwargs={"mode": "significant", "k_se": 1.0})
    _assert_probe_in_workdir(run_dir.root / "work" / "gepa_0001")
    assert _events(run_dir, "proposal_quality"), "GEPA logged no declaration"


def test_skillopt_gets_the_reasoning_skill(tmp_path):
    from cap_evolve import skillopt
    adapter, run_dir, base = _setup(tmp_path, "so", max_iterations=1, stall=5)
    skillopt.skillopt_loop(adapter, run_dir=run_dir, optimizer=_optimizer(),
                           current_val=base, epochs=1, batch_size=4,
                           gate_kwargs={"mode": "significant", "k_se": 1.0},
                           slow_update=False)
    _assert_probe_in_workdir(next((run_dir.root / "work").glob("so_e01s01")))


# ---- the injected skill is read-context, not a capability edit ------------

def test_the_reasoning_skill_is_not_mistaken_for_a_capability_edit(tmp_path):
    """``guidance/`` is already in INJECTED_DIRS, so the new subtree must be invisible to
    the snapshot, the eval-cache hash and GEPA's component list. If it were not, every
    candidate would look edited and the cache would never hit."""
    from cap_evolve.cache import hash_candidate_dir
    from cap_evolve.gepa import _components
    from cap_evolve.harness import _SNAPSHOT_IGNORE
    a, b = tmp_path / "a", tmp_path / "b"
    for d in (a, b):
        d.mkdir()
        (d / "prompt.txt").write_text("same\n", encoding="utf-8")
    shutil.copytree(PROBE_SRC, b / "guidance" / "reasoning" / "mechanism-probe")
    assert hash_candidate_dir(a) == hash_candidate_dir(b), \
        "the injected reasoning skill perturbed the eval-cache hash"
    assert _components(a) == _components(b), \
        "the injected reasoning skill became an editable GEPA component"
    assert "guidance" in _SNAPSHOT_IGNORE


# ---- the composed prompt stays under the cap -----------------------------

def test_the_composed_prompt_is_measured_and_under_the_cap(tmp_path):
    """All four appended blocks (#219 INSIGHTS pointer, #221 diversify, #222 dead-ends,
    #140's bar) plus the rendered template, in one real render."""
    from cap_evolve import harness
    from cap_evolve.optimizer_context import MAX_INSTRUCTIONS_CHARS
    adapter, run_dir, base = _setup(tmp_path, "cap", max_iterations=1, stall=3)
    harness.hill_climb_loop(
        adapter, run_dir=run_dir, optimizer=_optimizer(), current_val=base,
        focus="all", max_iterations=1, gate_kwargs={"mode": "significant", "k_se": 1.0},
        algorithm="hill-climb")
    instr = (run_dir.root / "work" / "cand_0001" / "INSTRUCTIONS.md").read_text(
        encoding="utf-8")
    assert len(instr) < MAX_INSTRUCTIONS_CHARS, (
        f"composed prompt {len(instr)} >= cap {MAX_INSTRUCTIONS_CHARS}")
    # #140's own contribution, measured.
    from cap_evolve import proposal_quality
    assert len(proposal_quality.PROMPT_BLOCK) < 2000, \
        f"the bar is {len(proposal_quality.PROMPT_BLOCK)} chars — too big for the kept tail"


def test_an_overflowing_prompt_keeps_the_bar_whole(tmp_path):
    """CROSSES THE BOUND (the #219 lesson: a pinning test whose fixture never overflows
    proves nothing). Force an overflow through the real ``_augment_instructions`` path and
    assert #140's block survives ENTIRE — header, all three fields, and the honest
    'not enforced' wording — rather than being cut mid-list.
    """
    from cap_evolve import Budget, RunDir, harness, proposal_quality
    from cap_evolve.optimizer_context import MAX_INSTRUCTIONS_CHARS
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="ov", budget=Budget())
    workdir = tmp_path / "wd"
    workdir.mkdir()

    huge = "x" * (MAX_INSTRUCTIONS_CHARS + 50_000)
    out = harness._augment_instructions(huge, workdir, run_dir)
    assert len(out) <= MAX_INSTRUCTIONS_CHARS, f"cap not applied: {len(out)}"
    assert "chars elided to keep this prompt under" in out, "no elision notice"
    # the whole block, not a fragment.
    assert proposal_quality.PROMPT_BLOCK in out, \
        "#140's bar was truncated mid-block by the overflow elision"


def test_the_bar_is_capped_by_the_shared_cap_not_a_second_one():
    """#222's lesson: ``_augment_instructions`` appends AFTER ``render_instructions``'
    cap, so it must route through the ONE shared ``cap_instructions``. A second private
    cap would let the composed prompt exceed the ceiling again."""
    import inspect

    from cap_evolve import harness
    src = inspect.getsource(harness._augment_instructions)
    assert "_oc.cap_instructions" in src, "the composed prompt bypasses the shared cap"
    assert src.count("cap_instructions") == 1, \
        f"more than one cap applied in _augment_instructions:\n{src}"


# ---- no sealed-test leak --------------------------------------------------

def test_no_test_split_id_reaches_any_injected_workdir_file(tmp_path):
    """#199's reviewer verified test ids appear in 0 workdir files. The new injected
    subtree + the new prompt block must preserve that."""
    from cap_evolve import harness
    adapter, run_dir, base = _setup(tmp_path, "leak", max_iterations=1, stall=3)
    harness.hill_climb_loop(
        adapter, run_dir=run_dir, optimizer=_optimizer(), current_val=base,
        focus="all", max_iterations=1, gate_kwargs={"mode": "significant", "k_se": 1.0},
        algorithm="hill-climb")
    test_ids = [str(t) for t in run_dir.read_splits().test]
    assert test_ids, "no sealed test ids to check against — the probe would be vacuous"
    hits = []
    for f in (run_dir.root / "work" / "cand_0001").rglob("*"):
        if not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hits += [(str(f.relative_to(run_dir.root)), tid)
                 for tid in test_ids if tid in text]
    assert hits == [], f"sealed test ids leaked into the optimizer workdir: {hits}"


# ---- zero model calls ----------------------------------------------------

def test_the_gate_makes_no_model_call():
    """#205: every auxiliary step in core is pure Python. The declaration parser must
    not reach for a model, an API client or the network."""
    import inspect

    from cap_evolve import proposal_quality
    src = inspect.getsource(proposal_quality)
    for banned in ("anthropic", "openai", "requests", "urllib.request", "http.client",
                   "aux_model", "subprocess"):
        assert banned not in src, f"proposal_quality reaches for {banned!r}"
