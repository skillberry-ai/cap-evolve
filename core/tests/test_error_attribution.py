"""D1 candidate faults: an exception raised from code under the candidate directory is attributed to
the candidate (error_kind=candidate) and scores 0.0 under errored_trial_policy=fail; adapter/infra
errors stay missing."""

import importlib.util
import json
from pathlib import Path

import pytest

from p2_fakes import make_run

from cap_evolve import harness, trials  # noqa: E402
from cap_evolve import Rollout, Score  # noqa: E402

CRASH_ON = {f"t{i:03d}" for i in range(0, 20, 2)}        # 10 of 100 tasks


class _ModAdapter:
    """run_target calls candidate code (loaded from the candidate dir) for every task."""

    def __init__(self, ids):
        self.ids = ids

    def tasks(self, split):
        from cap_evolve import Task
        return [Task(id=t) for t in self.ids]

    def run_target(self, task, ctx, *, seed=0):
        if task.id == "t_infra":
            raise ConnectionError("proxy reset")
        spec = importlib.util.spec_from_file_location("cand_impl", Path(ctx) / "impl.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return Rollout(task_id=task.id, output=mod.answer(task.id), trace="x")

    def score(self, task, rollout):
        r = 1.0 if rollout.output == "ok" else 0.0
        return Score(task_id=task.id, reward=r, trial_rewards=[r])

    def apply(self, d, edits=None):
        return None


@pytest.fixture(autouse=True)
def _flag(monkeypatch):
    monkeypatch.setenv("CAPEVOLVE_FAULT_ATTRIBUTION", "1")


def _run(tmp_path, ids, crash, policy):
    adapter, run_dir = make_run(tmp_path, n_train=0, n_val=1)
    run_dir.write_splits(type(run_dir.read_splits())(train=[], val=list(ids), test=[], seed=1))
    cand = tmp_path / "cand"
    cand.mkdir()
    (cand / "impl.py").write_text(
        f"CRASH = {sorted(crash)!r}\n"
        "def answer(t):\n"
        "    if t in CRASH:\n        raise KeyError('missing placeholder ' + t)\n"
        "    return 'ok'\n")
    ad = _ModAdapter(ids)
    return harness.evaluate_candidate(ad, cand, run_dir=run_dir, split="val", tag="c", workers=4,
                                      errored_policy=policy), run_dir


def test_exception_inside_candidate_code_is_attributed_and_scores_zero(tmp_path):
    ids = [f"t{i:03d}" for i in range(100)]
    res, _ = _run(tmp_path, ids, CRASH_ON, "fail")
    crashed = [pt for pt in res.per_task if pt["task_id"] in CRASH_ON]
    assert all(pt["reward"] == 0.0 and pt["raw"]["valid_trials"] == 1 for pt in crashed)
    assert res.n_scored == 100


def test_under_drop_the_same_crashes_are_missing_and_hide_the_regression(tmp_path):
    ids = [f"t{i:03d}" for i in range(100)]
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    drop, _ = _run(tmp_path / "a", ids, CRASH_ON, "drop")
    fail, _ = _run(tmp_path / "b", ids, CRASH_ON, "fail")
    assert drop.n_scored == 90 and fail.n_scored == 100
    # the incumbent passes everything: the candidate crashing on 10% loses >= 0.05 under fail ...
    assert 1.0 - fail.reward >= 0.05
    # ... and is flat (reward 1.0 on the tasks it did run) under drop
    assert drop.reward == 1.0


def test_infra_errors_stay_missing(tmp_path):
    ids = [f"t{i:03d}" for i in range(10)] + ["t_infra"]
    res, _ = _run(tmp_path, ids, set(), "fail")
    infra = next(pt for pt in res.per_task if pt["task_id"] == "t_infra")
    assert infra["raw"]["valid_trials"] == 0 and infra["raw"]["errored"]


def test_candidate_scope_is_reentrant_and_cleans_up(tmp_path):
    d = tmp_path / "c"
    d.mkdir()
    (d / "m.py").write_text("def f():\n    raise ValueError('x')\n")
    spec = importlib.util.spec_from_file_location("mm", d / "m.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        mod.f()
    except ValueError as e:
        exc = e
    assert trials.raised_in_candidate_code(exc) is False
    with trials.candidate_scope(d), trials.candidate_scope(d):
        assert trials.raised_in_candidate_code(exc) is True
    assert trials.raised_in_candidate_code(exc) is False


def test_tau2_adapter_hook_classifies_errors():
    import importlib.util as iu
    root = Path(__file__).resolve().parents[2] / "benchmarks" / "tau2" / "template"
    shared = root.parents[1] / "_shared"
    import sys
    sys.path.insert(0, str(shared))             # model_config.py
    sys.path.insert(0, str(root))
    try:
        spec = iu.spec_from_file_location("tau2_adapter_for_test", root / "adapter.py")
        mod = iu.module_from_spec(spec)
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(root))
        sys.path.remove(str(shared))
    assert mod.Adapter.supports_error_kind is True
    assert mod.classify_error_kind("TerminationReason.UNEXPECTED_ERROR", "KeyError in tools.py line 4") == "candidate"
    assert mod.classify_error_kind("TerminationReason.UNEXPECTED_ERROR", "connection reset") == "infra"
    assert mod.classify_error_kind("TerminationReason.TIMEOUT", "tools.py") == "infra"


def test_flag_off_by_default_leaves_rollouts_untagged(tmp_path, monkeypatch):
    monkeypatch.delenv("CAPEVOLVE_FAULT_ATTRIBUTION")
    ids = [f"t{i:03d}" for i in range(20)]
    res, run_dir = _run(tmp_path, ids, CRASH_ON, "fail")
    assert res.n_scored == 20 - len([t for t in ids if t in CRASH_ON])      # crashes stay missing
    rollout = next((run_dir.rollouts / "val").glob("t000__c__t0.json"))
    assert "error_kind" not in json.loads(rollout.read_text())["rollout"]["metadata"]


def test_third_party_transient_and_cause_chains_are_not_blamed(tmp_path):
    d = tmp_path / "c"
    d.mkdir()
    (d / "m.py").write_text("\n".join([
        "import json",
        "def parse(s):",
        "    return json.loads(s)",
        "def rate():",
        "    raise RuntimeError('HTTP 429 too many requests')",
        "def own():",
        "    raise KeyError('x')",
        "def swallow():",
        "    try:",
        "        own()",
        "    except KeyError:",
        "        raise ValueError('later')",
        ""]))
    spec = importlib.util.spec_from_file_location("mm2", d / "m.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    def catch(fn, *a):
        try:
            fn(*a)
        except Exception as e:      # noqa: BLE001
            return e
    with trials.candidate_scope(d):
        assert trials.raised_in_candidate_code(catch(mod.own)) is True
        assert trials.raised_in_candidate_code(catch(mod.rate)) is False          # 429 text
        assert trials.raised_in_candidate_code(catch(mod.parse, "{")) is True    # stdlib frames are skipped: the candidate called it
        assert trials.raised_in_candidate_code(catch(mod.swallow)) is True         # raised in candidate code, __context__ not walked


def test_a_project_root_or_adapter_dir_is_never_attributed(tmp_path):
    d = tmp_path / "proj"
    d.mkdir()
    (d / "adapter.py").write_text("def boom():\n    raise KeyError('adapter bug')\n")
    spec = importlib.util.spec_from_file_location("adp", d / "adapter.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        mod.boom()
    except KeyError as e:
        exc = e
    with trials.candidate_scope(d):
        assert trials.raised_in_candidate_code(exc) is False


def _raise_in_candidate(tmp_path, body_lines):
    d = tmp_path / "cx"
    d.mkdir(exist_ok=True)
    (d / "m.py").write_text("\n".join(["import socket"] + body_lines + [""]))
    spec = importlib.util.spec_from_file_location("mmx", d / "m.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        mod.f()
    except Exception as e:      # noqa: BLE001
        return d, e


@pytest.mark.parametrize("name,body", [
    ("connection", ["def f():", "    raise ConnectionError('proxy reset')"]),
    ("timeout", ["def f():", "    raise TimeoutError('read')"]),
    ("socket_timeout", ["def f():", "    raise socket.timeout('timed out')"]),
    ("oserror", ["def f():", "    raise OSError('Network is unreachable')"]),
    ("http_503", ["class HTTPError(Exception):", "    status_code = 503",
                  "def f():", "    raise HTTPError('503 Service Unavailable')"]),
    ("wrapped", ["def f():", "    try:", "        raise ConnectionError('reset')",
                 "    except ConnectionError as e:", "        raise RuntimeError('tool failed') from e"]),
])
def test_infrastructure_errors_are_never_blamed_on_the_candidate(tmp_path, name, body):
    d, exc = _raise_in_candidate(tmp_path, body)
    with trials.candidate_scope(d):
        assert trials.raised_in_candidate_code(exc) is False, name


def test_a_plain_candidate_bug_is_still_attributed(tmp_path):
    d, exc = _raise_in_candidate(tmp_path, ["def f():", "    return {}['missing']"])
    with trials.candidate_scope(d):
        assert trials.raised_in_candidate_code(exc) is True
