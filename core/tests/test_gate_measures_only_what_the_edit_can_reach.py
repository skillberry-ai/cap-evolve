"""The gate's four statistical-honesty defects, each with the run data that exposed it.

Audited on run_finalrun6 (7 candidates, 30 val tasks, agent-optimize):

1. **No statistical power.** SE(paired Δ) ran 0.022-0.035 while real per-edit effects were
   0.011-0.05, because the delta was measured across ALL 30 val tasks even though each edit
   touched a handful. The 7-way null-control replicate spread (0.567-0.603) was
   statistically indistinguishable from the 7-way across-candidate spread (0.570-0.607).
2. **False broke/fixed.** ``eps = 1e-9`` stamped a single flipped rollout (1.0 → 0.9 at 10
   trials) as a behavioural break. Byte-identical code measured twice (cand_2, and its
   fresh-tag re-measurement cand_4) got different broke/fixed labels, and the optimizer
   reasoned from them across three rounds.
3. **Stale gate_stderr.** ``gate_stderr`` was published as 0.0738 on rounds i0, i3 and i6 —
   identical — while the ``gate_threshold`` it is supposed to generate moved 0.0222 →
   0.0244 → 0.0346 at ``k_se = 1.0``.
4. **Promised memory files that never existed.** The staged instructions pointer told the
   optimizer to read ``LEDGER.md`` / ``PROCESS.md`` / ``RUNMAP.md`` / ``prior_iterations/``;
   on disk the working dir held only ``INSTRUCTIONS.md``, ``CLAUDE.md``, ``guidance/``,
   ``project/`` and ``trajectories/``. ``rejected.jsonl`` DID exist and was never mentioned.
"""

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))


def _rollout(run_dir, tag, task_id, k, reward, *, split="val", text=""):
    """One synthetic per-trial rollout file in the harness's on-disk format.

    ``text`` lands in the trace, which is where footprint detection looks for the names the
    edit touched — the same flat search it runs over a real adapter's rollout.
    """
    vdir = run_dir.rollouts / split
    vdir.mkdir(parents=True, exist_ok=True)
    rec = {"input": {}, "rollout": {"task_id": task_id, "error": None, "trace": text},
           "score": {"task_id": task_id, "reward": reward, "feedback": "", "raw": {}}}
    (vdir / f"{task_id}__{tag}__t{k}.json").write_text(json.dumps(rec), encoding="utf-8")


def _fresh(name):
    from cap_evolve import RunDir
    return RunDir.create(Path(tempfile.mkdtemp()) / ".capevolve", ts=name)


# --- 1. footprint-restricted measurement ------------------------------------------------

def test_a_real_effect_on_three_tasks_survives_the_noise_of_twenty_seven_others():
    """The defect, at the scale it was measured at: a genuine +0.1 on the three tasks the
    edit can reach is INVISIBLE when the other 27 tasks contribute their measurement wobble
    to the SE, and RESOLVED when they contribute the 0.0 they have by construction.

    Same rewards, same gate, same k_se — the only difference is which tasks the delta vector
    treats as capable of having moved.
    """
    from cap_evolve import harness
    from cap_evolve.gate import decide
    from cap_evolve.loop import Score, aggregate_scores

    reached = [f"t{i}" for i in range(3)]
    # Parent and candidate agree everywhere except the three in-footprint tasks (+0.1 each).
    # The 27 others carry ±0.1 re-measurement wobble in alternating directions: identical
    # code, different draw — exactly what the null-control replicates showed.
    par, cand = {}, {}
    for i in range(30):
        t = f"t{i}"
        par[t] = 0.5
        cand[t] = 0.6 if t in reached else (0.6 if i % 2 else 0.4)

    def _sr(d):
        return aggregate_scores("val", [Score(task_id=t, reward=r, n=10) for t, r in d.items()])

    cur_sr, cand_sr = _sr(par), _sr(cand)

    full = harness._paired_deltas(cur_sr, cand_sr)
    restricted = harness._paired_deltas(cur_sr, cand_sr, footprint=set(reached))

    # Both vectors describe the same 30 tasks and the same mean movement over them...
    assert len(full) == len(restricted) == 30
    mean_full = sum(full) / 30
    mean_restricted = sum(restricted) / 30
    assert round(mean_restricted, 10) == 0.01              # 3 tasks x +0.1 over 30
    # ...but the unrestricted mean is dominated by the wobble, not by the edit.
    assert mean_full > mean_restricted

    unres = decide(0.5, mean_full + 0.5, split="val", mode="paired", paired_deltas=full)
    res = decide(0.5, 0.51, split="val", mode="paired", paired_deltas=restricted)

    # THE defect: the noisy vector cannot resolve the effect it is measuring — its
    # significance bar is wider than the whole effect, which is the run_finalrun6 shape
    # (SE 0.022-0.035 against effects of 0.011-0.05).
    assert not unres.accept, unres.reason
    assert unres.threshold > mean_restricted, unres.reason
    # Restricted, the same +0.01 clears its own bar: the 27 tasks the edit cannot reach
    # stopped contributing variance, and the bar fell ~4x with them.
    assert res.accept, res.reason
    assert res.threshold < unres.threshold / 3, (res.threshold, unres.threshold)


def test_footprint_is_the_tasks_whose_rollouts_exercise_the_edited_surface():
    """Which tasks the edit can reach is read from the diff + the persisted rollouts —
    generically, with no knowledge of the capability, the benchmark or the adapter."""
    from cap_evolve import footprint

    rd = _fresh("fp")
    parent = rd.candidate_dir("seed")
    cand = rd.candidate_dir("cand_1")
    parent.mkdir(parents=True, exist_ok=True)
    cand.mkdir(parents=True, exist_ok=True)
    (parent / "tools.py").write_text("def cancel_reservation(rid):\n    return rid\n")
    (cand / "tools.py").write_text(
        "def cancel_reservation(rid):\n    return rid\n\n"
        "def cancel_reservations(rids):\n    return rids\n")

    # t0/t1 route through the new surface; t2 never mentions it.
    for tag in ("seed", "cand_1"):
        _rollout(rd, tag, "t0", 0, 1.0, text="called cancel_reservations([1,2])")
        _rollout(rd, tag, "t1", 0, 1.0, text="cancel_reservations again")
        _rollout(rd, tag, "t2", 0, 1.0, text="searched for a flight")

    fp = footprint.footprint(rd, parent_dir=parent, cand_dir=cand,
                             tags=("seed", "cand_1"), all_task_ids=["t0", "t1", "t2"])
    assert fp == {"t0", "t1"}


def test_no_footprint_data_measures_the_full_split_rather_than_guessing():
    """Every unknowable case degrades to today's full-vector behaviour, never to a crash and
    never to a restriction invented from nothing."""
    from cap_evolve import footprint

    rd = _fresh("fpnone")
    d = rd.candidate_dir("seed")
    d.mkdir(parents=True, exist_ok=True)
    (d / "tools.py").write_text("x = 1\n")

    # Identical snapshots -> no diff -> no symbols -> no footprint.
    assert footprint.footprint(rd, parent_dir=d, cand_dir=d, tags=("seed",)) is None
    # A snapshot that does not exist at all must not raise.
    assert footprint.footprint(rd, parent_dir=d, cand_dir=rd.candidate_dir("ghost"),
                              tags=("seed",)) is None
    # A footprint covering every measured task is not a restriction, so it is not reported.
    cand = rd.candidate_dir("cand_1")
    cand.mkdir(parents=True, exist_ok=True)
    (cand / "tools.py").write_text("x = 1\n\ndef widget_helper():\n    pass\n")
    for t in ("t0", "t1"):
        _rollout(rd, "cand_1", t, 0, 1.0, text="widget_helper ran")
    assert footprint.footprint(rd, parent_dir=d, cand_dir=cand, tags=("cand_1",),
                              all_task_ids=["t0", "t1"]) is None
    # A rewrite-sized diff names too many surfaces to localize anything.
    assert footprint.touched_symbols(
        "@@ -1 +1 @@\n" + "\n".join(f"+def surface_{i}(x):" for i in range(200))) == set()
    # And docstring PROSE is not a surface: an English word before a parenthesis is not a
    # call, which is the distinction that kept "cancelled"/"flights"/"user" out of the set.
    assert footprint.touched_symbols(
        '@@ -1 +1 @@\n+        """Cancel MULTIPLE reservations (e.g. ABC and XYZ) at once."""'
    ) == set()
    assert footprint.touched_symbols(
        "@@ -1 +1 @@\n+        self.cancel_reservation(rid)") == {"cancel_reservation"}


def test_an_edit_inside_a_body_takes_its_enclosing_definition_as_its_surface():
    """run_finalrun6's cand_7 rewrote one tool's docstring and nothing else. Its changed lines
    name no surface at all, so on the changed lines alone it has no footprint and gets measured
    against the whole split — where its SE was 0.0346, against a real effect of 0.0067.

    The enclosing definition IS the surface for an edit inside a body, and it is taken ONLY
    when the hunk named nothing of its own: a hunk that does name its surfaces must not drag in
    every neighbouring definition that happens to sit inside the diff's context window.
    """
    from cap_evolve import footprint

    docstring_only = (
        "@@ -1,6 +1,6 @@\n"
        "     def update_reservation_passengers(self, rid, passengers):\n"
        '-        """Update the passengers."""\n'
        '+        """Update the passengers on an existing reservation."""\n'
        "         return rid\n")
    assert footprint.touched_symbols(docstring_only) == {"update_reservation_passengers"}

    # A hunk that names its own surface does NOT also claim the neighbour in its context.
    names_itself = (
        "@@ -1,6 +1,6 @@\n"
        "     def some_unrelated_neighbour(self):\n"
        "         pass\n"
        "+    def cancel_reservations(self, ids):\n"
        "+        return ids\n")
    assert footprint.touched_symbols(names_itself) == {"cancel_reservations"}


def test_control_replicates_pool_into_one_lower_variance_parent_reference():
    """The parent-side power gain that costs no rollouts: two byte-identical control
    replicates already on disk are draws from one distribution, so pooling their TRIALS per
    task (not averaging their means) is a better estimate of the same parent."""
    from cap_evolve import harness

    rd = _fresh("pool")
    # Two replicates of the same parent, each 1 trial per task, disagreeing on t0.
    _rollout(rd, "ctl_a", "t0", 0, 1.0)
    _rollout(rd, "ctl_b", "t0", 0, 0.0)

    one = harness.split_result_from_rollouts(rd, "ctl_a", "val")
    pooled = harness.split_result_from_rollouts(rd, ["ctl_a", "ctl_b"], "val")
    assert [pt["n"] for pt in one.per_task] == [1]
    assert [pt["n"] for pt in pooled.per_task] == [2]      # trials merged, not means averaged
    assert pooled.per_task[0]["reward"] == 0.5


# --- 2. broke/fixed thresholded at the measurement's own resolution ----------------------

def test_one_flipped_rollout_in_ten_is_not_a_behavioural_break():
    """The exact shape that poisoned the optimizer's reasoning: 1.0 -> 0.9 at 10 trials.

    That is one rollout out of ten, well inside the task's own measurement error, and it was
    being asserted as a task the candidate BROKE. It must land in ``unresolved`` — a real,
    supra-threshold regression on the same run must still land in ``broke``.
    """
    from cap_evolve import harness

    rd = _fresh("bf")
    # t_noise: parent 10/10, candidate 9/10 -> Δ = -0.1, inside 2·SE (SE_cand = 0.095).
    # t_real:  parent 10/10, candidate 0/10 -> Δ = -1.0, far outside any SE.
    for k in range(10):
        _rollout(rd, "seed", "t_noise", k, 1.0)
        _rollout(rd, "seed", "t_real", k, 1.0)
        _rollout(rd, "cand_1", "t_noise", k, 0.0 if k == 0 else 1.0)
        _rollout(rd, "cand_1", "t_real", k, 0.0)

    imp = harness._candidate_task_impact(rd, "cand_1", "val", parent_of={"cand_1": "seed"})
    assert imp["broke"] == ["t_real"], imp
    assert imp["unresolved"] == ["t_noise"], imp


def test_a_single_trial_run_classifies_exactly_as_it_always_did():
    """At one trial per task there is no variance estimate, the bar collapses to eps, and the
    one draw is all the evidence there is — so the old behaviour is preserved exactly."""
    from cap_evolve import harness

    rd = _fresh("bf1")
    for tid, r in (("1", 1.0), ("2", 1.0), ("3", 0.0)):
        _rollout(rd, "seed", tid, 0, r)
    for tid, r in (("1", 1.0), ("2", 0.0), ("3", 1.0)):
        _rollout(rd, "cand_1", tid, 0, r)

    imp = harness._candidate_task_impact(rd, "cand_1", "val", parent_of={"cand_1": "seed"})
    assert imp["broke"] == ["2"]
    assert imp["fixed"] == ["3"]
    assert imp["unresolved"] == []


def test_an_unresolved_move_is_named_as_such_where_the_optimizer_reads_it():
    """Both places the classification reaches the optimizer must carry the distinction, and
    neither may keep calling the classification 'objective' — a 1-in-10 rollout flip stamped
    as a break was the opposite of objective."""
    from cap_evolve import harness

    rd = _fresh("bfdoc")
    for k in range(10):
        _rollout(rd, "seed", "t_noise", k, 1.0)
        _rollout(rd, "cand_1", "t_noise", k, 0.0 if k == 0 else 1.0)
    rd.log_event("step", candidate="cand_1", parent="seed", accept=False, val=0.99)

    work = Path(tempfile.mkdtemp())
    harness._build_ledger(work, rd)
    ledger = (work / "LEDGER.md").read_text(encoding="utf-8")
    row = [ln for ln in ledger.splitlines() if "cand_1" in ln][0]
    assert "unresolved" in ledger
    assert "2·SE" in ledger
    assert "objective" not in ledger
    # The noisy task is in the row's unresolved cell, and NOT claimed as broken.
    assert "t_noise" in row
    assert row.index("t_noise") > row.index("|", row.index("reject"))

    harness._reconcile_journal(work, rd, "cand_1", accepted=False, val=0.99, delta=-0.01,
                              reason="docstring-only edit")
    journal = (rd.root / "JOURNAL.md").read_text(encoding="utf-8")
    assert "unresolved={t_noise}" in journal
    assert "broke={—}" in journal
    assert "RESULT (framework, objective)" not in journal


# --- 3. the published SE is this round's own, not a constant -----------------------------

def test_the_published_gate_stderr_is_the_se_the_threshold_was_built_from():
    """Three rounds of run_finalrun6 published gate_stderr 0.0738, 0.0738, 0.0738 against
    thresholds 0.0222, 0.0244, 0.0346 at k_se 1.0 — a constant beside three different bars
    derived from it. The published SE must satisfy ``threshold == k_se · SE`` for its own
    round, which is what makes the two numbers readable in one row.
    """
    sys.path.insert(0, str(REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"))
    import commit as commit_mod

    rd = _fresh("se")
    work = rd.root / "work"
    work.mkdir(parents=True, exist_ok=True)
    for it, (thr, res) in enumerate([(0.022173, 0.044347), (0.024361, 0.048721),
                                     (0.034646, 0.069292)]):
        (work / f"round_i{it}.json").write_text(json.dumps({
            # The mean-over-tasks SE the old code published: identical every round, and
            # several times the bar it was printed beside.
            "parent": {"tag": "seed", "reward": 0.5933, "stderr": 0.0737942671874435,
                       "n_tasks": 30},
            "gated_against": {"mode": "parent"},
            "candidates": [{"tag": f"cand_{it}", "stderr": 0.0737942671874435,
                            "gate_delta": 0.001, "gate_threshold": thr, "k_se": 1.0,
                            "n": 30, "resolvable_effect_size": res}],
        }), encoding="utf-8")

    seen = []
    for it in range(3):
        rd.update_spent(iterations=1) if it else None
        # spent.iterations names the round table _round_gate_numbers reads.
        while int(rd.spent.iterations) < it:
            rd.update_spent(iterations=1)
        g = commit_mod._round_gate_numbers(rd, f"cand_{it}")
        assert g["gate_stderr"] * g["gate_k_se"] == round(g["gate_threshold"], 6), g
        seen.append(g["gate_stderr"])
    # The whole point: it MOVES with the round instead of being one frozen number.
    assert len(set(seen)) == 3, seen


# --- 4. every promised memory file exists, and the ones that exist are promised ----------

def test_the_instructions_pointer_promises_exactly_the_files_it_creates():
    """The pointer told the optimizer to read four files and a directory that nothing on the
    agent-mode path created. Now the code that writes the promise also creates the files, and
    names only what exists — so the promise cannot drift away from the filesystem again."""
    from cap_evolve import harness

    rd = _fresh("mem")
    rd.candidate_dir("seed").mkdir(parents=True, exist_ok=True)
    rd.log_event("step", candidate="cand_1", parent="seed", accept=False, val=0.5)

    work = Path(tempfile.mkdtemp())
    harness._write_instructions_pointer(work / "CLAUDE.md", ".claude/skills",
                                        run_dir=rd, workdir=work)
    pointer = (work / "CLAUDE.md").read_text(encoding="utf-8")

    for name in ("LEDGER.md", "JOURNAL.md", "PROCESS.md", "RUNMAP.md",
                 "INSIGHTS.md", "META_INSIGHTS.md", "FRAMEWORK_IMPROVEMENTS.md"):
        assert name in pointer, f"{name} not promised"
        assert (work / name).is_file(), f"{name} promised but not created"
    # JOURNAL.md's own seed text points every prior candidate's exact edit at this path.
    assert (work / "prior_iterations").is_dir()
    assert "prior_iterations" in pointer
    # rejected.jsonl always existed on disk and was never mentioned to the optimizer.
    assert "rejected.jsonl" in pointer
    assert str(rd.rejected_path) in pointer


def test_the_pointer_names_no_file_it_could_not_create():
    """Called without a run dir there is nothing to build from, so the pointer must promise
    no cross-iteration file at all rather than name files that are not there."""
    from cap_evolve import harness

    work = Path(tempfile.mkdtemp())
    harness._write_instructions_pointer(work / "CLAUDE.md", ".claude/skills")
    pointer = (work / "CLAUDE.md").read_text(encoding="utf-8")
    for name in ("LEDGER.md", "RUNMAP.md", "prior_iterations", "PROCESS.md"):
        assert name not in pointer, f"{name} promised with nothing to create it from"
    assert "INSTRUCTIONS.md" in pointer      # the one file staging always writes


def test_agent_mode_carries_the_memory_forward_every_round():
    """Not just at staging: ``seed_framework_memory`` writes into the candidate snapshot the
    next round copies from, the same mechanism JOURNAL.md already relied on. A round-1-only
    seed leaves a LEDGER that never mentions any round."""
    from cap_evolve import harness

    rd = _fresh("mem2")
    rd.candidate_dir("seed").mkdir(parents=True, exist_ok=True)
    rd.set_best("seed")
    rd.log_event("step", candidate="cand_1", parent="seed", accept=True, val=0.7)

    written = harness.seed_framework_memory(rd.candidate_dir("seed"), rd)
    assert {"LEDGER.md", "JOURNAL.md", "PROCESS.md", "RUNMAP.md"} <= set(written)
    ledger = (rd.candidate_dir("seed") / "LEDGER.md").read_text(encoding="utf-8")
    assert "cand_1" in ledger and "ACCEPT" in ledger
