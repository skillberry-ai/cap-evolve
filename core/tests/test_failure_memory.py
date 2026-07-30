"""Issue #129 — rejected approaches become a CONSTRAINT in the optimizer prompt.

Before this change ``rejected.jsonl`` was audit/UI-only (see #114): the optimizer never
saw what the gate had already killed, so it could re-propose a dead end and burn another
full-val eval on it. RUN.md nonetheless claimed "rejected approaches are remembered and
never re-proposed" — false on both halves (nothing re-injected them; nothing could stop a
re-proposal). These tests pin the real behavior:

  * ``approach_signature`` normalizes WHAT an edit changed (capability diff only, never
    the injected read-context), so cosmetic re-proposals collapse to one signature;
  * ``dead_end_constraints`` renders the deduped block, bounded on a long run;
  * ``_augment_instructions`` — the one path all three algorithms share (#114) — carries
    it into the prompt for hill-climb, GEPA and SkillOpt alike;
  * the constraint text is ADVISORY: it names the failed edit and demands justification.
    The hard half is the gate, which still rejects a repeat and counts it.
"""

import os
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
EXAMPLE = REPO / "examples" / "toy_calc"
MOCK_RUN = REPO / "skills" / "optimizers" / "run-optimizer" / "scripts" / "run.py"

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
    spec = importlib.util.spec_from_file_location("toy_fail_mem", EXAMPLE / "adapter.py")
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


# ---- approach_signature ---------------------------------------------------

def test_signature_captures_the_edit_and_ignores_injected_context(tmp_path):
    """The signature is built from the CAPABILITY diff only.

    Injected read-context (trajectories/, guidance/, LEDGER.md, …) must not appear —
    otherwise every candidate would get a unique signature and dedupe would never fire.
    """
    from cap_evolve.harness import approach_signature
    parent, child = tmp_path / "p", tmp_path / "c"
    parent.mkdir(), child.mkdir()
    (parent / "prompt.txt").write_text("base\n", encoding="utf-8")
    (child / "prompt.txt").write_text("base\nBE TERSE\n", encoding="utf-8")
    # injected read-context that must be invisible to the signature
    (child / "LEDGER.md").write_text("| iter | candidate |\n", encoding="utf-8")
    (child / "trajectories").mkdir()
    (child / "trajectories" / "t.json").write_text('{"secret": 1}', encoding="utf-8")

    sig = approach_signature(parent, child)
    assert "prompt.txt: +BE TERSE" in sig, sig
    assert "LEDGER" not in sig and "secret" not in sig, f"read-context leaked: {sig}"


def test_signature_is_stable_across_cosmetic_variation(tmp_path):
    """Whitespace/indent-only differences collapse to ONE signature — that is what makes
    "a cosmetic variation of an already-failed approach" dedupe instead of piling up."""
    from cap_evolve.harness import approach_signature
    parent = tmp_path / "p"
    parent.mkdir()
    (parent / "prompt.txt").write_text("base\n", encoding="utf-8")
    sigs = set()
    for i, text in enumerate(("base\nBE TERSE\n", "base\n   BE    TERSE   \n")):
        c = tmp_path / f"c{i}"
        c.mkdir()
        (c / "prompt.txt").write_text(text, encoding="utf-8")
        sigs.add(approach_signature(parent, c))
    assert len(sigs) == 1, f"cosmetic variants produced distinct signatures: {sigs}"


def test_signature_empty_for_a_noop_edit(tmp_path):
    """An optimizer that errored leaves the workdir a verbatim parent copy. A no-op is
    not an approach, so it must not be injected as a constraint."""
    from cap_evolve.harness import approach_signature
    parent, child = tmp_path / "p", tmp_path / "c"
    parent.mkdir(), child.mkdir()
    for d in (parent, child):
        (d / "prompt.txt").write_text("same\n", encoding="utf-8")
    assert approach_signature(parent, child) == ""


# ---- dead_end_constraints ------------------------------------------------

def test_constraints_block_names_the_edit_and_the_reason(tmp_path):
    """FAILS BEFORE THE FIX (no dead_end_constraints, nothing read rejected.jsonl)."""
    from cap_evolve import Budget, RunDir
    from cap_evolve.harness import dead_end_constraints
    from cap_evolve.memory import RejectedMemory
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="de", budget=Budget())
    RejectedMemory(run_dir.rejected_path).add(
        "cand_0001", "candidate cand_0001 (val 0.400, Δ -0.200)",
        "not significant: Δ -0.200 <= 1.0*SE 0.050", 0.4,
        approach="prompt.txt: +ALWAYS answer in one word")

    block = dead_end_constraints(run_dir)
    assert "ALREADY TRIED & REJECTED" in block
    assert "prompt.txt: +ALWAYS answer in one word" in block, "edit signature missing"
    assert "not significant" in block, "rejection reason missing"
    assert "cand_0001" in block
    # the actual constraint instruction, not just a log line
    assert "do NOT propose any of the above again" in block
    assert "materially different" in block


def test_constraints_empty_without_rejections(tmp_path):
    from cap_evolve import Budget, RunDir
    from cap_evolve.harness import dead_end_constraints
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="e0", budget=Budget())
    assert dead_end_constraints(run_dir) == ""


def test_constraints_dedupe_and_count_repeats(tmp_path):
    """A re-proposed approach is ONE row with a repeat count, not N rows."""
    from cap_evolve import Budget, RunDir
    from cap_evolve.harness import dead_end_constraints
    from cap_evolve.memory import RejectedMemory
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="dd", budget=Budget())
    mem = RejectedMemory(run_dir.rejected_path)
    for cid in ("c1", "c2", "c3"):
        mem.add(cid, f"candidate {cid}", "val gate", 0.4,
                approach="prompt.txt: +SAME IDEA")
    block = dead_end_constraints(run_dir)
    assert block.count("prompt.txt: +SAME IDEA") == 1, "not deduped"
    assert "re-proposed 3x" in block, block
    assert "rejected 1 distinct approach(es)" in block


def test_pre_129_records_without_approach_are_skipped(tmp_path):
    """Runs recorded before this change have no ``approach`` field — degrade quietly."""
    from cap_evolve import Budget, RunDir
    from cap_evolve.harness import dead_end_constraints
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="old", budget=Budget())
    run_dir.rejected_path.write_text(
        '{"candidate_id": "c1", "summary": "s", "reason": "val gate", "val": 0.1}\n'
        "not json at all\n",
        encoding="utf-8")
    assert dead_end_constraints(run_dir) == ""


def test_constraints_bounded_on_a_long_run(tmp_path):
    """50 distinct rejections must NOT produce 50 verbatim constraints, and the assembled
    prompt must stay under #199's MAX_INSTRUCTIONS_CHARS."""
    from cap_evolve import Budget, RunDir
    from cap_evolve.harness import _MAX_DEAD_ENDS, dead_end_constraints
    from cap_evolve.memory import RejectedMemory
    from cap_evolve.optimizer_context import MAX_INSTRUCTIONS_CHARS
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="big", budget=Budget())
    mem = RejectedMemory(run_dir.rejected_path)
    for i in range(50):
        mem.add(f"c{i:03d}", f"candidate c{i:03d}", "x" * 5000 + f" reason {i}", 0.1,
                approach=f"prompt.txt: +approach number {i} " + "y" * 5000)

    block = dead_end_constraints(run_dir)
    assert block.count("- **c") == _MAX_DEAD_ENDS, "injection not bounded to the cap"
    assert "showing the 12 most recent" in block
    assert "c049" in block and "c000" not in block, "kept the OLDEST, not the newest"
    # per-row budgets hold: signature <= 300, reason <= 200 → block stays small
    assert len(block) < 8_000, f"block ballooned to {len(block)} chars"
    assert len(block) < MAX_INSTRUCTIONS_CHARS


def test_a_re_proposed_dead_end_is_never_the_one_evicted(tmp_path):
    """Recency is LAST-seen, not first-seen.

    With more distinct dead ends than the cap, the row the optimizer JUST re-proposed is
    the single most predictive one — evicting it in favour of a newer one-off drops exactly
    the constraint that was about to be violated again, and falsifies the block's own
    "12 most recent" wording. A 50-distinct-approach bound test cannot catch this because
    it contains no repeat."""
    from cap_evolve import Budget, RunDir
    from cap_evolve.harness import _MAX_DEAD_ENDS, dead_end_constraints
    from cap_evolve.memory import RejectedMemory
    run_dir = RunDir.create(tmp_path / ".capevolve", ts="evict", budget=Budget())
    mem = RejectedMemory(run_dir.rejected_path)
    old = "prompt.txt: +THE OLD IDEA"
    mem.add("c000", "first", "gate said no", 0.1, approach=old)
    for i in range(1, _MAX_DEAD_ENDS + 3):          # push the old row well past the cap
        mem.add(f"c{i:03d}", "x", "gate said no", 0.1, approach=f"prompt.txt: +IDEA {i}")
    mem.add("c099", "repeat", "gate said no", 0.1, approach=old)   # re-proposed NOW

    block = dead_end_constraints(run_dir)
    assert "THE OLD IDEA" in block, "the just-re-proposed dead end was evicted"
    assert "re-proposed 2x" in block, "the repeat was not counted"
    assert "(latest c099)" in block, "the repeat's latest candidate id is not shown"
    assert block.count("- **c") == _MAX_DEAD_ENDS
    assert "IDEA 1`" not in block, "displaced a newer one-off instead of the oldest"


def test_signature_is_distinct_for_edits_sharing_a_long_prefix(tmp_path):
    """The dedupe key must be a function of the WHOLE edit.

    A plain head truncation makes two genuinely different edits that share a long prefix
    (any realistic SKILL.md or system prompt) produce ONE signature — the block would then
    tell the optimizer "re-proposed 2x" about an approach it never proposed, which is
    strictly worse than injecting no constraint at all."""
    from cap_evolve.harness import _MAX_APPROACH_CHARS, approach_signature
    shared = "\n".join(f"RULE {i}: a fairly long boilerplate rule line here" for i in range(20))
    parent = tmp_path / "p"
    parent.mkdir()
    (parent / "prompt.txt").write_text("seed\n")
    sigs = []
    for tag in ("ALPHA", "OMEGA"):
        child = tmp_path / f"c_{tag}"
        child.mkdir()
        (child / "prompt.txt").write_text(f"seed\n{shared}\nFINAL: {tag}\n")
        sigs.append(approach_signature(parent, child))
    assert len(sigs[0]) == _MAX_APPROACH_CHARS, "prefix too short to exercise the overflow"
    assert sigs[0] != sigs[1], f"different edits collapsed to one signature: {sigs[0]!r}"


def test_signature_strips_control_and_bidi_characters(tmp_path):
    """``approach`` is quoted into a markdown prompt and (once #191/#220 land) into a
    terminal writer. Strip the ANSI/C0 half AND the bidi-override half once here rather
    than in every future consumer. Legitimate content (emoji, non-latin text) survives."""
    from cap_evolve.harness import approach_signature
    parent, child = tmp_path / "p", tmp_path / "c"
    parent.mkdir(), child.mkdir()
    (parent / "prompt.txt").write_text("seed\n")
    (child / "prompt.txt").write_text("seed\n\x1b[31mRED\x07 ‮RTL ⁦iso⁩ 😀 עברית\n")
    sig = approach_signature(parent, child)
    assert "RED" in sig and "😀" in sig and "עברית" in sig, repr(sig)
    banned = set(range(32)) | {127} | set(range(0x202A, 0x202F)) | set(range(0x2066, 0x206A))
    assert not any(ord(ch) in banned for ch in sig), repr(sig)


# ---- reaches the prompt, for all three algorithms -------------------------

def _seed_rejection(run_dir, approach="prompt.txt: +DEAD END APPROACH"):
    from cap_evolve.memory import RejectedMemory
    RejectedMemory(run_dir.rejected_path).add(
        "prior_0001", "candidate prior_0001 (val 0.100, Δ -0.300)",
        "not significant: Δ -0.300", 0.1, approach=approach)


def _assert_constraint_in_prompt(workdir: Path):
    instr = (workdir / "INSTRUCTIONS.md").read_text(encoding="utf-8")
    assert "ALREADY TRIED & REJECTED" in instr, "constraint block never reached the prompt"
    assert "DEAD END APPROACH" in instr, "the rejected edit is not named in the prompt"
    return instr


def test_hill_climb_prompt_carries_the_constraints(tmp_path):
    """FAILS BEFORE THE FIX: nothing injected rejected.jsonl into the prompt."""
    from cap_evolve import harness
    adapter, run_dir, base = _setup(tmp_path, "hc", max_iterations=1, stall=3)
    _seed_rejection(run_dir)
    harness.hill_climb_loop(
        adapter, run_dir=run_dir, optimizer=_optimizer(), current_val=base,
        focus="all", max_iterations=1, gate_kwargs={"mode": "significant", "k_se": 1.0},
        algorithm="hill-climb")
    _assert_constraint_in_prompt(run_dir.root / "work" / "cand_0001")


def test_gepa_prompt_carries_the_constraints(tmp_path):
    """GEPA specifically — the algorithm whose cross-iteration channel was silently
    empty before #199 (it emits ``gepa_val_gate``, not ``step``)."""
    from cap_evolve import gepa
    adapter, run_dir, base = _setup(tmp_path, "gp", max_iterations=1, stall=5)
    _seed_rejection(run_dir)
    gepa.gepa_loop(adapter, run_dir=run_dir, optimizer=_optimizer(), seed_val=base,
                   max_iterations=1, minibatch_size=3, max_merges=0,
                   gate_kwargs={"mode": "significant", "k_se": 1.0})
    _assert_constraint_in_prompt(run_dir.root / "work" / "gepa_0001")


def test_skillopt_prompt_carries_the_constraints(tmp_path):
    from cap_evolve import skillopt
    adapter, run_dir, base = _setup(tmp_path, "so", max_iterations=1, stall=5)
    _seed_rejection(run_dir)
    skillopt.skillopt_loop(adapter, run_dir=run_dir, optimizer=_optimizer(),
                           current_val=base, epochs=1, batch_size=4,
                           gate_kwargs={"mode": "significant", "k_se": 1.0},
                           slow_update=False)
    workdir = next((run_dir.root / "work").glob("so_e01s01"))
    _assert_constraint_in_prompt(workdir)


# ---- the loop actually records signatures (not just the test seeding them) ----

def test_a_real_rejection_records_its_approach_signature(tmp_path):
    """End-to-end: the mock optimizer's edit is rejected by a strict gate, and the
    signature of that exact edit lands in rejected.jsonl — so the NEXT iteration's
    prompt constrains against it. This is the whole point of the issue."""
    import json

    from cap_evolve import harness
    adapter, run_dir, base = _setup(tmp_path, "rec", max_iterations=1, stall=3)
    harness.hill_climb_loop(
        adapter, run_dir=run_dir, optimizer=_optimizer(), current_val=base,
        focus="all", max_iterations=1,
        # threshold mode with an unreachable margin → guaranteed rejection. (A huge k_se
        # would NOT work: n_trials=1 collapses SE to 0 and the gate documents a strict
        # fallback, which accepts the mock's improvement.)
        gate_kwargs={"mode": "threshold", "threshold": 1e9}, algorithm="hill-climb")

    recs = [json.loads(ln) for ln in
            run_dir.rejected_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert recs, "no rejection recorded"
    approach = recs[-1]["approach"]
    assert "prompt.txt" in approach, f"signature does not name the edited file: {approach}"
    assert "[CALC]" in approach, f"signature does not carry the mock's edit: {approach}"
    # and it is immediately usable as a constraint
    assert "[CALC]" in harness.dead_end_constraints(run_dir)


def test_signature_names_the_real_edit_under_a_native_skills_optimizer(tmp_path):
    """The regression the ``mock`` optimizer structurally cannot show.

    ``mock`` has no ``skills_dir``/``instructions_file`` registry row, so nothing is
    injected and any skip-list gap stays invisible. Every REAL agent optimizer
    (claude-code, codex, gemini-cli, opencode, ibm-bob, cursor) gets ``CLAUDE.md`` +
    ``.claude/skills/<cap>/SKILL.md`` written into its workdir — and because the PARENT
    side of the capability diff is a snapshot (already stripped by ``_SNAPSHOT_IGNORE``)
    while the CHILD side is the live workdir, each of those files used to read as a
    capability addition, sort ahead of the real edit, and truncate it away entirely."""
    import json

    from cap_evolve import harness
    adapter, run_dir, base = _setup(tmp_path, "native", max_iterations=1, stall=3)
    harness.hill_climb_loop(
        adapter, run_dir=run_dir, optimizer=_optimizer(), current_val=base,
        focus="all", max_iterations=1, capabilities=["system-prompt"],
        optimizer_name="claude-code",          # <- the only difference from the mock case
        gate_kwargs={"mode": "threshold", "threshold": 1e9}, algorithm="hill-climb")

    workdir = next((run_dir.root / "work").iterdir())
    injected = sorted(p.name for p in workdir.iterdir())
    assert ".claude" in injected or "CLAUDE.md" in injected, \
        f"native injection did not happen, so this test proves nothing: {injected}"

    recs = [json.loads(ln) for ln in
            run_dir.rejected_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert recs, "no rejection recorded"
    approach = recs[-1]["approach"]
    assert "prompt.txt" in approach and "[CALC]" in approach, \
        f"signature does not carry the real edit: {approach}"
    for leak in (".claude", "CLAUDE.md", "SKILL.md", "AGENTS.md"):
        assert leak not in approach, f"injected read-context {leak} leaked in: {approach}"


def test_no_val_or_test_ground_truth_in_the_constraint_block(tmp_path):
    """The block is built from the capability diff + gate reason only — never from task
    data. Prove no split id (val OR sealed test) appears in it."""
    from cap_evolve import harness
    adapter, run_dir, base = _setup(tmp_path, "leak", max_iterations=1, stall=3)
    harness.hill_climb_loop(
        adapter, run_dir=run_dir, optimizer=_optimizer(), current_val=base,
        focus="all", max_iterations=1,
        gate_kwargs={"mode": "threshold", "threshold": 1e9}, algorithm="hill-climb")
    block = harness.dead_end_constraints(run_dir)
    assert block, "expected a constraint block to inspect"
    splits = run_dir.read_splits()
    leaked = [t for t in (list(splits.test) + list(splits.val)) if t in block]
    assert not leaked, f"split ids leaked into the optimizer prompt: {leaked}"
