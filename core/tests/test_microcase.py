"""microcase.py — TDD-style micro-tests (#436): schema, generator, and runner.

Three levels of evidence:
  1. ``gen`` extracts a real diagnosed rollout's tool calls VERBATIM into a case's
     fixture — checked against the committed run3 rollout that seeded this feature.
  2. The runner's pass/fail/error contract, exercised against a tiny synthetic
     project with no external dependency (proves the generic infra works on ANY
     project).
  3. The checked-in worked example (``core/tests/fixtures/microcases/
     netguard_duplicate_payment``) run for real against a seed and a candidate
     tools module that differ by exactly the accepted mechanism from the real
     diagnosed run — the seed fails (duplicate write), the candidate passes (netted
     into one entry) — using a lightweight stand-in for the external ``tau2``
     package the real project's tools module imports (unavailable offline; see the
     module docstring on ``_STUB_TAU2``).
"""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts" / "microcase.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
REAL_ROLLOUT = FIXTURES / "run3_task10_seed_t8_duplicate_payment.json"
REAL_CASE = FIXTURES / "microcases" / "netguard_duplicate_payment"
_STUB_TAU2 = FIXTURES / "netguard_project" / "stub_tau2"
_SEED_PROJECT = FIXTURES / "netguard_project" / "seed"
_CANDIDATE_PROJECT = FIXTURES / "netguard_project" / "candidate"


def _run(*args, env=None):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, env=env)


# ---------------------------------------------------------------------------
# 1. gen — extraction is verbatim
# ---------------------------------------------------------------------------

def test_gen_extracts_calls_verbatim_from_a_real_diagnosed_rollout(tmp_path):
    out = tmp_path / "netguard_duplicate_payment"
    p = _run("gen", "--rollout", str(REAL_ROLLOUT),
              "--cluster-id", "netguard_duplicate_payment",
              "--source-task-ids", "10", "--expects", "guard_fires",
              "--description", "duplicate write on a re-issued update",
              "--assert-metric", "payment_history_len", "--assert-op", "<=",
              "--assert-value", "1", "--out", str(out))
    assert p.returncode == 0, p.stderr

    calls = json.loads((out / "fixture" / "calls.json").read_text())["calls"]
    update_calls = [c for c in calls if c["name"] == "update_reservation_flights"]
    assert len(update_calls) == 2, "the real rollout has exactly two duplicate calls"
    # Verbatim: the exact reservation/payment ids the real agent used, unmodified.
    for c in update_calls:
        assert c["arguments"]["reservation_id"] == "4NQLHD"
        assert c["arguments"]["payment_id"] == "credit_card_7434610"
    # The two calls differ in which flights they name — that IS the defect.
    assert update_calls[0]["arguments"]["flights"] != update_calls[1]["arguments"]["flights"]

    case_yaml = (out / "case.yaml").read_text()
    assert "expects: guard_fires" in case_yaml
    assert (out / "reproduce.py").exists()
    assert (out / "assert.py").exists()


def test_gen_refuses_a_rollout_with_no_tool_calls(tmp_path):
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"rollout": {"trace": []}, "score": {}}))
    p = _run("gen", "--rollout", str(empty), "--cluster-id", "x",
              "--source-task-ids", "1", "--expects", "call_shape",
              "--description", "d", "--assert-metric", "m", "--assert-op", "==",
              "--assert-value", "1", "--out", str(tmp_path / "x"))
    assert p.returncode != 0
    assert "no tool calls" in p.stdout


# ---------------------------------------------------------------------------
# 2. runner contract — generic, no external dependency
# ---------------------------------------------------------------------------

def _write_generic_case(case_dir: Path, expected: int) -> None:
    """Scaffold via the real ``gen`` command (a fake one-call rollout is enough to
    satisfy it), then swap in a trivial ``reproduce.py`` — proves ``run``/``run-all``
    work against ANY case, not just the tau2-shaped worked example.
    """
    rollout = case_dir.parent / f"{case_dir.name}_rollout.json"
    rollout.parent.mkdir(parents=True, exist_ok=True)
    rollout.write_text(json.dumps({
        "rollout": {"trace": [{"role": "assistant",
                               "tool_calls": [{"name": "noop", "arguments": {}}]}]},
        "score": {},
    }))
    p = _run("gen", "--rollout", str(rollout), "--cluster-id", case_dir.name,
              "--source-task-ids", "1", "--expects", "call_shape",
              "--description", "generic pass/fail contract",
              "--assert-metric", "n", "--assert-op", "==",
              "--assert-value", str(expected), "--out", str(case_dir))
    assert p.returncode == 0, p.stdout

    (case_dir / "reproduce.py").write_text(
        "import argparse, json\n"
        "from pathlib import Path\n"
        "ap = argparse.ArgumentParser()\n"
        "ap.add_argument('--candidate', required=True)\n"
        "ap.add_argument('--project', required=True)\n"
        "ap.add_argument('--fixture', required=True)\n"
        "ap.add_argument('--out', required=True)\n"
        "args = ap.parse_args()\n"
        "n = int(Path(args.candidate, 'n.txt').read_text())\n"
        "Path(args.out).write_text(json.dumps({'status': 'ok', 'n': n}))\n")
    (case_dir / "candidate_pass").mkdir()
    (case_dir / "candidate_pass" / "n.txt").write_text(str(expected))
    (case_dir / "candidate_fail").mkdir()
    (case_dir / "candidate_fail" / "n.txt").write_text(str(expected + 1))


def test_run_reports_pass_and_fail(tmp_path):
    case_dir = tmp_path / "generic"
    _write_generic_case(case_dir, expected=1)

    passed = _run("run", "--case", str(case_dir),
                  "--candidate", str(case_dir / "candidate_pass"), "--project", "x")
    assert passed.returncode == 0, passed.stdout
    assert json.loads(passed.stdout)["status"] == "pass"

    failed = _run("run", "--case", str(case_dir),
                  "--candidate", str(case_dir / "candidate_fail"), "--project", "x")
    assert failed.returncode == 1
    assert json.loads(failed.stdout)["status"] == "fail"


def test_run_reports_error_on_reproduce_crash(tmp_path):
    case_dir = tmp_path / "broken"
    (case_dir / "fixture").mkdir(parents=True)
    (case_dir / "fixture" / "calls.json").write_text(json.dumps({"calls": []}))
    (case_dir / "case.yaml").write_text(
        "id: broken\ncluster_id: broken\nsource_task_ids: [1]\nsource_rollout: x\n"
        "timeout_s: 5\nexpects: call_shape\ndescription: crashes\n"
        "assert:\n  metric: n\n  op: \"==\"\n  value: 1\n")
    (case_dir / "reproduce.py").write_text("raise RuntimeError('project dependency missing')\n")
    p = _run("run", "--case", str(case_dir), "--candidate", str(tmp_path), "--project", "x")
    assert p.returncode == 2
    out = json.loads(p.stdout)
    assert out["status"] == "error"


def test_run_all_flags_micro_test_fail_and_recommends_rejection(tmp_path):
    cases_dir = tmp_path / "microcases"
    _write_generic_case(cases_dir / "case_a", expected=1)

    p = _run("run-all", "--cases-dir", str(cases_dir),
              "--candidate", str((cases_dir / "case_a" / "candidate_fail")),
              "--project", "x")
    out = json.loads(p.stdout)
    assert p.returncode == 1
    assert out["micro_test_fail"] is True
    assert "micro_test_fail" in out["recommendation"]

    p_ok = _run("run-all", "--cases-dir", str(cases_dir),
                "--candidate", str((cases_dir / "case_a" / "candidate_pass")),
                "--project", "x")
    out_ok = json.loads(p_ok.stdout)
    assert p_ok.returncode == 0
    assert out_ok["micro_test_fail"] is False


# ---------------------------------------------------------------------------
# 3. the real worked example, end to end
# ---------------------------------------------------------------------------

def _env_with_stub_tau2():
    import os
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_STUB_TAU2)
    return env


def test_real_case_fails_against_the_unfixed_seed():
    p = _run("run", "--case", str(REAL_CASE), "--candidate", str(_SEED_PROJECT),
              "--project", "x", env=_env_with_stub_tau2())
    assert p.returncode == 1, p.stdout
    out = json.loads(p.stdout)
    assert out["status"] == "fail"
    assert out["observed"] == 2, "the seed appends a SECOND payment on the re-issued call"


def test_real_case_passes_against_the_candidate_with_the_real_accepted_guard():
    p = _run("run", "--case", str(REAL_CASE), "--candidate", str(_CANDIDATE_PROJECT),
              "--project", "x", env=_env_with_stub_tau2())
    assert p.returncode == 0, p.stdout
    out = json.loads(p.stdout)
    assert out["status"] == "pass"
    assert out["observed"] == 1, "the guard nets both calls into ONE entry"


def test_real_case_runs_in_well_under_a_second():
    p = _run("run", "--case", str(REAL_CASE), "--candidate", str(_CANDIDATE_PROJECT),
              "--project", "x", env=_env_with_stub_tau2())
    out = json.loads(p.stdout)
    assert out["wall_seconds"] < 2.0, (
        "the whole point of a micro-test is seconds, not a task rollout")


# ---------------------------------------------------------------------------
# 4. the new reject basis is wired into commit.py
# ---------------------------------------------------------------------------

def test_commit_py_accepts_micro_test_fail_as_a_reject_basis():
    commit_py = SCRIPT.parent / "commit.py"
    text = commit_py.read_text()
    assert '"micro_test_fail"' in text
    assert "microcase.py" in text or "#436" in text
