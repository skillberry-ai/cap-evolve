"""tau2's own trajectories, at ONE path format shared by every tau2 adapter in this repo.

Two problems, one fix. First, ``examples/tau2_airline`` never wrote them: both ``run_tasks``
call sites passed ``save_path=None``, so tau2 built ``SimulationResults`` in memory,
``_sim_to_rollout`` converted each sim, and the native object was dropped. A user saw only
cap-evolve's per-rollout JSON — complete traces, but in cap-evolve's schema, which
`tau2 view` cannot read, while tau2 unconditionally closed every run by recommending it.

Second, the adapters that DID write them disagreed on where: ``examples/tau2_airline`` used
``native_sims/<tag>/results.json`` (tag only, plus a ``-2``/``-3`` suffix walk), while the
skillberry_benchmarks arms used ``trajectories/<split>/results_<ts>_<pid>.json`` (split
only). Same benchmark, two layouts — so `tau2 view --dir` took a different shape depending
on which arm produced the run, and a trace could not be attributed without knowing which
adapter wrote it.

All four now build the SAME path:

    <run_dir>/native_sims/<tag>/<split>/results_<YYYYmmdd_HHMMSS>_<pid>.json

``<tag>`` comes from the dir the harness passes as ``ctx``, under either name it uses:
``candidates/<tag>`` for the baseline (``seed``) and the finalize, and ``work/<tag>`` for an
iteration eval (``cand_0001``). ``<split>`` stands in for the phase, which no adapter is
told: the baseline is the seed on val, the finalize is the seed on test.

The stamp is what removes the suffix walk. tau2 reads an existing results file (or its
``simulations/`` sibling) as a run to RESUME: it prompts on stdin and raises
FileExistsError when the answer is not "y" (tau2/runner/checkpoint.py), and ``auto_resume``
is off by default. An eval has no stdin, so a collision would hang or kill the run — and a
silent resume would be worse, returning a previous split's sims as if they were this one's.

Saving is opt-OUT via CAPEVOLVE_NATIVE_SIMS=0, which is what CI sets: its uploaded artifact
is $OUT/** and the run dir is a separate tree, so these files reach no upload, while a full
tier writes one sim per task x trial per eval over baseline, every candidate and finalize.
"""

import hashlib
import importlib.util
import re
import sys
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ADAPTER = REPO / "templates" / "adapters" / "tau2_bench" / "adapter.py"

#: Every tau2 adapter that must agree on the path format. The duplication is deliberate —
#: each ships as ONE self-contained file copied into a project's ``adapters/`` — so the
#: alignment is held by the test below rather than by a shared import.
#:
#: A path that is ABSENT is skipped rather than failed on, so this tuple can name an adapter a
#: given checkout does not have. ``_MIN_ADAPTERS`` is what stops "skip the missing ones" from
#: degenerating into "compare nothing and pass".
TAU2_ADAPTERS = (
    REPO / "templates" / "adapters" / "tau2_bench" / "adapter.py",
    REPO / "examples" / "tau2_airline" / "adapters" / "adapter.py",
    REPO / "examples" / "tau2_custom" / "direct" / "adapters" / "adapter.py",
    REPO / "examples" / "tau2_custom" / "blackbox" / "adapters" / "adapter.py",
)

#: Below this many present adapters the alignment check is not checking alignment.
_MIN_ADAPTERS = 2


def _load_adapter_module():
    """Import the tau2 adapter with `tau2` stubbed (CI has no tau2-bench install)."""
    for p in (REPO / "core", ADAPTER.parent, ADAPTER.parent.parent):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))

    llm_utils = types.ModuleType("tau2.utils.llm_utils")
    llm_utils.get_token_usage = lambda messages: {"completion_tokens": 0, "prompt_tokens": 0}
    # ASSIGN, never setdefault: these stubs must win inside this module's tests no matter
    # what ran first. The _isolated_tau2_modules fixture puts sys.modules back afterwards,
    # so winning here does not mean poisoning anyone else — see its docstring.
    for name, mod in (
        ("tau2", types.ModuleType("tau2")),
        ("tau2.utils", types.ModuleType("tau2.utils")),
        ("tau2.utils.llm_utils", llm_utils),
    ):
        sys.modules[name] = mod

    spec = importlib.util.spec_from_file_location("_tau2_adapter_sims", ADAPTER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def _clean_flag(monkeypatch):
    """Neutralize an ambient CAPEVOLVE_NATIVE_SIMS (CI exports 0) — these tests own it."""
    monkeypatch.delenv("CAPEVOLVE_NATIVE_SIMS", raising=False)


@pytest.fixture(autouse=True)
def _isolated_tau2_modules():
    """Put every ``tau2*`` entry in ``sys.modules`` back the way it was.

    ``test_tau2_eval_cost`` stubs the SAME ``tau2.utils.llm_utils`` and needs a real
    accumulating ``get_token_usage``; this module needs only a zero-returning one. Both used
    ``sys.modules.setdefault``, so whichever file ran first installed its stub PERMANENTLY
    and the other silently got the wrong one — every cost assertion then failed. Alphabetical
    collection order (eval_cost before native_sims) happens to hide it in a full run, which
    makes it a trap: selecting a subset, reordering, or running under xdist flips it.
    Restoring here means neither file can depend on, or damage, the other's ordering.
    """
    before = {k: v for k, v in sys.modules.items() if k == "tau2" or k.startswith("tau2.")}
    try:
        yield
    finally:
        for k in [k for k in sys.modules if k == "tau2" or k.startswith("tau2.")]:
            del sys.modules[k]
        sys.modules.update(before)


def _adapter():
    return _load_adapter_module().Adapter.__new__(_load_adapter_module().Adapter)


def _candidate_dir(tmp_path, tag="seed"):
    """The ctx the harness passes: <run_dir>/candidates/<tag>."""
    d = tmp_path / "run_20260101_000000" / "candidates" / tag
    d.mkdir(parents=True, exist_ok=True)
    return d


# --- the shared format -------------------------------------------------------------

def test_path_is_run_dir_native_sims_tag_split(tmp_path):
    a = _adapter()
    run = tmp_path / "run_20260101_000000"

    p = a._sim_save_path(_candidate_dir(tmp_path, "seed"), "val")
    assert p.parent == run / "native_sims" / "seed" / "val", \
        "the run dir, then native_sims, then the tag, then the split"
    assert re.fullmatch(r"results_\d{8}_\d{6}_\d+\.json", p.name), p.name


def test_tag_separates_the_baseline_from_an_iteration(tmp_path):
    """A trace you cannot tie to the candidate that produced it cannot tell you whether an
    edit helped."""
    a = _adapter()
    seed = a._sim_save_path(_candidate_dir(tmp_path, "seed"), "val")
    cand = a._sim_save_path(_candidate_dir(tmp_path, "candidate_003"), "val")
    assert seed.parent.parent.name == "seed"
    assert cand.parent.parent.name == "candidate_003"
    assert seed.parent != cand.parent


def test_split_separates_the_baseline_eval_from_the_finalize_eval(tmp_path):
    """No adapter is told the phase, so the split stands in for it: seed-on-val is the
    baseline, seed-on-test is the finalize. Different dirs, and NO -2 suffix."""
    a = _adapter()
    ctx = _candidate_dir(tmp_path, "seed")
    val, test = a._sim_save_path(ctx, "val"), a._sim_save_path(ctx, "test")
    assert val.parent.name == "val"
    assert test.parent.name == "test"
    assert val.parent != test.parent
    for p in (val, test):
        # Scope the no-suffix check to the part the ADAPTER built. Against the ABSOLUTE
        # path it also matches pytest's own tmpdir — `/tmp/pytest-of-<user>/pytest-21/`
        # contains "-2" — so the assertion passed or failed on a tmpdir counter rather
        # than on the code, and flipped with collection order.
        built = p.relative_to(tmp_path)
        assert "-2" not in str(built), "the stamp replaced the suffix walk; nothing should walk"
        assert p.parent.parent.name == "seed", "the tag dir is the bare tag, never suffixed"


def test_an_already_written_path_is_never_reused(tmp_path):
    """tau2 treats an existing results file, or a bare `simulations/` sibling, as a run to
    resume — it prompts on stdin, which an eval does not have."""
    a = _adapter()
    ctx = _candidate_dir(tmp_path, "seed")
    first = a._sim_save_path(ctx, "val")
    first.parent.mkdir(parents=True)
    first.write_text("{}", encoding="utf-8")
    (first.parent / "simulations").mkdir()

    # A later eval of the same tag+split lands on a different second and/or process, so the
    # name cannot be the one tau2 already wrote.
    assert a._sim_save_path(ctx, "test") != first
    assert first.name != "results.json", \
        "a fixed name would collide with the file tau2 already wrote"


def test_an_iteration_eval_gets_its_own_sims_from_the_work_dir(tmp_path):
    """The harness passes TWO different dir names, and both are a real eval.

    ``candidates/<tag>`` is only the baseline and the finalize (harness.py:565 and :3665);
    every candidate eval in between is handed ``<run_dir>/work/<cid>`` (harness.py:2356,
    used at :2440). A guard that accepted ``candidates`` alone therefore returned ``None``
    for exactly the evals these traces exist for — you got the seed and the winner and
    nothing for any candidate, so no trace could tell you WHY an edit scored what it did.
    The run dir is ``parent.parent`` under either name, so accepting both is the whole fix.
    """
    a = _adapter()
    run = tmp_path / "run_20260101_000000"
    work = run / "work" / "cand_0001"
    work.mkdir(parents=True)

    p = a._sim_save_path(work, "val")
    assert p is not None, "an iteration eval must write sims, not be silently skipped"
    assert p.parent == run / "native_sims" / "cand_0001" / "val", \
        "a work/<tag> ctx must resolve to the SAME run_dir/native_sims/<tag>/<split> tree"

    # And it must not collide with the baseline's, which is the whole point of the tag.
    assert p.parent != a._sim_save_path(_candidate_dir(tmp_path, "seed"), "val").parent


def test_the_stamp_carries_the_pid_so_concurrent_candidates_cannot_collide(tmp_path):
    import os
    a = _adapter()
    p = a._sim_save_path(_candidate_dir(tmp_path, "seed"), "val")
    assert p.stem.endswith(f"_{os.getpid()}"), p.name


# --- the opt-out -------------------------------------------------------------------

def test_the_flag_turns_saving_off(monkeypatch, tmp_path):
    """CI sets CAPEVOLVE_NATIVE_SIMS=0: it never reads these files and does pay the disk."""
    a = _adapter()
    ctx = _candidate_dir(tmp_path, "seed")
    for off in ("0", "false", "no", "off", "OFF", " 0 "):
        monkeypatch.setenv("CAPEVOLVE_NATIVE_SIMS", off)
        assert a._sim_save_path(ctx, "val") is None, f"{off!r} must disable saving"


def test_saving_is_on_by_default_and_for_any_other_value(monkeypatch, tmp_path):
    """Default ON: a human working a run locally is the reader these files exist for."""
    a = _adapter()
    ctx = _candidate_dir(tmp_path, "seed")
    monkeypatch.delenv("CAPEVOLVE_NATIVE_SIMS", raising=False)
    assert a._sim_save_path(ctx, "val") is not None, "absent env must not disable saving"
    for on in ("1", "true", "yes", "on", ""):
        monkeypatch.setenv("CAPEVOLVE_NATIVE_SIMS", on)
        assert a._sim_save_path(ctx, "val") is not None, f"{on!r} must leave saving on"


def test_unexpected_layout_disables_saving_instead_of_raising(tmp_path):
    """Saving native traces is a convenience; it must never be what breaks an eval."""
    a = _adapter()
    loose = tmp_path / "not_a_candidate_dir"
    loose.mkdir()
    assert a._sim_save_path(loose, "val") is None
    assert a._sim_save_path(None, "val") is None


# --- the split lookup --------------------------------------------------------------

def test_split_is_read_from_the_runs_own_splits_json(tmp_path):
    a = _adapter()
    ctx = _candidate_dir(tmp_path, "seed")
    (ctx.parent.parent / "splits.json").write_text(
        '{"train": ["1"], "val": ["9"], "test": ["7"]}', encoding="utf-8")
    assert a._split_of(ctx, ["9"]) == "val"
    assert a._split_of(ctx, ["7"]) == "test"
    assert a._split_of(ctx, ["1"]) == "train"


def test_a_no_holdout_split_resolves_to_val_and_a_missing_file_to_eval(tmp_path):
    """val is the split the optimizer reads, so it wins ties. An unreadable splits.json
    must degrade to a label, not raise."""
    a = _adapter()
    ctx = _candidate_dir(tmp_path, "seed")
    assert a._split_of(ctx, ["9"]) == "eval", "no splits.json => a neutral label"
    (ctx.parent.parent / "splits.json").write_text(
        '{"train": ["9"], "val": ["9"], "test": ["9"]}', encoding="utf-8")
    assert a._split_of(ctx, ["9"]) == "val"


# --- the call sites ----------------------------------------------------------------

def test_both_call_sites_pass_the_save_path_and_the_split(monkeypatch, tmp_path):
    """The original bug was two `save_path=None` literals; a helper alone does not fix it."""
    mod = _load_adapter_module()
    seen = []

    class _Sims:
        simulations = []

    runner = types.ModuleType("tau2.runner")
    runner.run_tasks = lambda config, tasks, **kw: (seen.append(kw.get("save_path")), _Sims())[1]
    sim_model = types.ModuleType("tau2.data_model.simulation")
    sim_model.TextRunConfig = lambda **kw: types.SimpleNamespace(**kw)
    sim_model.TerminationReason = types.SimpleNamespace()
    gateway = types.ModuleType("gateway")
    gateway.agent_model = gateway.user_model = lambda: "aws/claude-haiku-4-5"
    gateway.llm_args_for = lambda m: {}
    for name, m in (("tau2.runner", runner),
                    ("tau2.data_model", types.ModuleType("tau2.data_model")),
                    ("tau2.data_model.simulation", sim_model),
                    ("gateway", gateway)):
        monkeypatch.setitem(sys.modules, name, m)

    a = mod.Adapter.__new__(mod.Adapter)
    # Must MAP the task: both methods return early (no run_tasks call) when nothing maps.
    monkeypatch.setattr(type(a), "_tau2_tasks_by_id",
                        lambda self: {"9": types.SimpleNamespace(id="9")}, raising=False)
    task = types.SimpleNamespace(id="9")
    ctx = _candidate_dir(tmp_path, "seed")
    (ctx.parent.parent / "splits.json").write_text('{"val": ["9"]}', encoding="utf-8")

    a.run_batch([task], ctx, seed=0)
    a.run_trials([task], ctx, n_trials=2, base_seed=0)

    assert len(seen) == 2, "run_batch and run_trials must both reach run_tasks"
    for p in seen:
        assert p is not None, "save_path=None means tau2 view still has nothing to read"
        p = Path(p)
        assert p.parent.name == "val", "the split must reach the path, not just the helper"
        assert p.parent.parent.name == "seed"
        assert p.parent.parent.parent.name == "native_sims"


# --- the alignment itself ----------------------------------------------------------

def _canonical_block(text: str) -> str:
    """The shared sim-path region: the marker comment through the end of _sim_save_path."""
    start = text.index("    # ---- tau2's OWN simulation records")
    end = text.index("\n    def ", text.index("    def _sim_save_path(", start))
    return text[start:end]


def _optout_helper(text: str) -> str:
    start = text.index("def _native_sims_enabled")
    tail = '\n        "0", "false", "no", "off"}'
    return text[start:text.index(tail, start) + len(tail)]


@pytest.mark.parametrize("extract", [_canonical_block, _optout_helper],
                         ids=["sim_path_block", "optout_helper"])
def test_every_tau2_adapter_carries_the_identical_code(extract):
    """The four adapters duplicate this on purpose — each is ONE self-contained file copied
    into a project's adapters/, so a shared import would break that portability. What must
    NOT happen is DRIFT: a fix applied to one copy and not the others, which is exactly how
    two layouts appeared in the first place. This test is the thing holding them together,
    so a change here has to be made in all four.
    """
    digests = {}
    present = [p for p in TAU2_ADAPTERS if p.is_file()]
    assert len(present) >= _MIN_ADAPTERS, (
        f"only {len(present)} of the {len(TAU2_ADAPTERS)} tau2 adapters are present — "
        "an alignment check with nothing to compare passes for the wrong reason")
    for p in present:
        digests.setdefault(
            hashlib.sha256(extract(p.read_text(encoding="utf-8")).encode()).hexdigest(),
            []).append(str(p.relative_to(REPO)))
    assert len(digests) == 1, (
        "tau2 adapters have DRIFTED — apply the change to every copy:\n"
        + "\n".join(f"  {d[:12]}: {', '.join(f)}" for d, f in digests.items()))
