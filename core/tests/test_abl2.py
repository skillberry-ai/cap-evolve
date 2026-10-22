"""ablation v2: abl2_scope tools|policy lint, best-val, truncation audit."""
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))
sys.path.insert(0, str(REPO / "core" / "tests"))

from cap_evolve import abl, abl2_audit, abl2_lint, abl2_overfit  # noqa: E402

RUNS = Path("/home/dev/projects2/campaign-scratch/runs/ABL")
SEED = RUNS / "CAP-TC/s0/.capevolve/project/seed_capability/tools/tools.py"
TC = RUNS / "CAP-TC/s0/final/tools/tools.py"
TD = RUNS / "CAP-TD/s0/final/tools/tools.py"
K2 = [RUNS / f"GATE-K2/s{i}/final/tools/tools.py" for i in range(4)]
RUN_MAIN = RUNS / "CAP-TC/s0/.capevolve/run_main"

TOOLS = '''"""module doc"""
from tau2.environment.toolkit import ToolKitBase, is_tool


class AirlineTools(ToolKitBase):
    """All tools."""

    def _helper(self, x):
        """private."""
        return x

    @is_tool(None)
    def alpha(self, x: int) -> int:
        """Alpha tool.

        Args:
            x: a number.
        """
        return x + 1

    @is_tool(None)
    def beta(self, x: int) -> int:
        """Beta tool."""
        return x * 2
'''


def mk(root: Path, tools=TOOLS, policy="be nice\n") -> Path:
    (root / "policy").mkdir(parents=True)
    (root / "tools").mkdir()
    (root / "reference").mkdir()
    (root / "policy/policy.md").write_text(policy)
    (root / "tools/tools.py").write_text(tools)
    (root / "reference/benchmark_policy.md").write_text("Reservation ids are 6 chars.\n")
    return root


@pytest.fixture
def pc(tmp_path):
    p = mk(tmp_path / "parent")
    c = tmp_path / "cand"
    shutil.copytree(p, c)
    return p, c


def set_tools(c, fn):
    f = c / "tools/tools.py"
    f.write_text(fn(f.read_text()))


def tv(pc):
    return abl2_lint.check("tools", *pc)


# ---- calibration on real files ----------------------------------------------
def _src(p):
    if not p.is_file():
        pytest.skip(f"{p} absent")
    return p.read_bytes()


def test_seed_zero_findings():
    assert abl2_lint.all_findings(_src(SEED)) == []
    assert abl2_lint.policy_in_tool_findings(_src(SEED), _src(SEED)) == []


def test_cap_tc_get_procedure_flagged():
    f = abl2_lint.policy_in_tool_findings(_src(SEED), _src(TC))
    assert any("get_procedure" in x for x in f)


def test_cap_td_long_docstrings_flagged():
    f = abl2_lint.policy_in_tool_findings(_src(SEED), _src(TD))
    assert any("docstring_long" in x and "cancel_reservation" in x for x in f)


def test_k2_champion_s2_clean_and_short_helpers_pass():
    assert abl2_lint.policy_in_tool_findings(_src(SEED), _src(K2[2])) == []


# ---- tools scope: accepted edits ---------------------------------------------
def test_accepts_docstring_edit(pc):
    set_tools(pc[1], lambda s: s.replace("Alpha tool.", "Alpha tool: adds one to x."))
    assert tv(pc) is None


def test_accepts_code_edit(pc):
    set_tools(pc[1], lambda s: s.replace("x + 1", "x + 2"))
    assert tv(pc) is None


def test_accepts_add_remove_composite_tool(pc):
    set_tools(pc[1], lambda s: s + '''
    @is_tool(None)
    def quote(self, x: int, y: int) -> dict:
        """Total of alpha(x) and beta(y). Both are per-passenger amounts."""
        return {"total": self.alpha(x) + self.beta(y), "note": "alpha plus beta"}
''')
    assert tv(pc) is None
    set_tools(pc[1], lambda s: s.replace('''
    @is_tool(None)
    def beta(self, x: int) -> int:
        """Beta tool."""
        return x * 2
''', ""))
    assert tv(pc) is None
    (pc[1] / "tools/helper.py").write_text("X = 1\n")      # extra file under tools/ is fine
    assert tv(pc) is None


def test_accepts_schema_change(pc):
    set_tools(pc[1], lambda s: s.replace("def alpha(self, x: int) -> int:", "def alpha(self, x: int, y: int = 0) -> int:"))
    assert tv(pc) is None


# ---- tools scope: rejected ---------------------------------------------------
PROC = '''
    @is_tool(None)
    def get_procedure(self, topic: str) -> str:
        """Return the checklist."""
        long = "Get the user id, then check eligibility, then ask for a yes before any write. " * 3
        guides = {"cancel": long, "book": long + "x", "bags": long + "y"}
        return guides[topic]
'''


def test_rejects_get_procedure(pc):
    set_tools(pc[1], lambda s: s + PROC)
    lint, d = tv(pc)
    assert lint == "surface" and "POLICY-IN-TOOL LINT" in d and "get_procedure" in d


def test_rejects_multiline_steps_in_return(pc):
    set_tools(pc[1], lambda s: s + '''
    @is_tool(None)
    def how(self) -> str:
        return """1. look up the user
2. you must check the reservation
3. never skip the confirmation"""
''')
    assert "return_prose" in tv(pc)[1]


def test_short_hint_strings_and_long_data_strings_pass(pc):
    set_tools(pc[1], lambda s: s + '''
    @is_tool(None)
    def fee(self, n: int) -> dict:
        """Bag fee."""
        note = "Tell the user the fee, and that it is charged per bag. " * 8
        return {"fee": 50 * n, "hint": "tell the user the fee", "long": note}
''')
    assert tv(pc) is None


def test_rejects_long_checklist_docstring(pc):
    doc = "\\n".join(f"        {i}. You must never skip step {i} before calling." for i in range(1, 9))
    set_tools(pc[1], lambda s: s.replace('"""Beta tool."""', '"""Beta.\\n' + doc + '\n        """'))
    assert "docstring_rules" in tv(pc)[1]
    set_tools(pc[1], lambda s: s.replace('"""Alpha tool.', '"""Alpha tool.' + "\\n x" * 30))
    assert "docstring_long" in tv(pc)[1]


def test_preexisting_findings_do_not_count(tmp_path):
    parent = TOOLS + PROC
    p = mk(tmp_path / "p", tools=parent)
    c = tmp_path / "c"
    shutil.copytree(p, c)
    set_tools(c, lambda s: s.replace("x + 1", "x + 3"))
    assert abl2_lint.check("tools", p, c) is None


def test_policy_edit_rejected_by_tools_scope(pc):
    (pc[1] / "policy/policy.md").write_text("be very nice\n")
    lint, d = tv(pc)
    assert lint == "surface" and "policy/policy.md" in d


def test_other_files_rejected_scratch_ignored(pc):
    (pc[1] / "PROCESS.md").write_text("notes")
    assert tv(pc) is None
    (pc[1] / "reference/x.md").write_text("x")
    assert "reference/x.md" in tv(pc)[1]


# ---- policy scope ------------------------------------------------------------
def _rollout(tid, texts):
    trace = [{"role": "user", "content": t, "tool_calls": None} for t in texts]
    return {"input": "", "rollout": {"task_id": str(tid), "trace": trace}, "score": {"task_id": str(tid)}}


@pytest.fixture
def run_with_traces(tmp_path):
    rd = tmp_path / "run"
    (rd / "rollouts/val").mkdir(parents=True)
    d = _rollout(12, [
        "I'm Emma Kim, user id emma_kim_9957, email emma.kim@example.com, cancel reservation K1NW8N "
        "on 2024-05-17 PHX to JFK on flight HAT156",
        '{"reservation_id": "ZZ9Y8X", "passengers": [{"first_name": "Evelyn", "last_name": "Taylor"}], '
        '"payment_history": [{"payment_id": "credit_card_5832574", "amount": 1}]}'])
    (rd / "rollouts/val/0__seed__t0.json").write_text(json.dumps(d))
    return rd


def pv(pc, rd):
    return abl2_lint.check("policy", pc[0], pc[1], type("R", (), {"root": rd})())


def test_forbidden_built(run_with_traces):
    f = abl2_overfit.build_forbidden(run_with_traces / "rollouts/val", "")
    assert "K1NW8N" in f["reservation_ids"] and "ZZ9Y8X" in f["reservation_ids"]
    assert "emma_kim_9957" in f["user_ids"] and "emma.kim@example.com" in f["emails"]
    assert "Emma Kim" in f["names"] and "Evelyn Taylor" in f["names"]
    assert "HAT156" in f["flight_numbers"] and "credit_card_5832574" in f["payment_ids"]
    assert ["PHX", "2024-05-17"] in f["city_dates"] and f["task_ids"] == ["12"]


@pytest.mark.parametrize("bad", [
    "Check K1NW8N first.", "For emma_kim_9957 refuse.", "Contact emma.kim@example.com",
    "Customers like Emma Kim often ask", "In task 12 you must transfer.", "task_id 12 is special",
    "HAT156 is always full", "PHX on 2024-05-17 is cancelled"])
def test_overfit_rejected(pc, run_with_traces, bad):
    (pc[1] / "policy/policy.md").write_text("be nice\n" + bad + "\n")
    lint, d = pv(pc, run_with_traces)
    assert lint == "overfit"


def test_generic_rule_accepted_and_cached(pc, run_with_traces):
    (pc[1] / "policy/policy.md").write_text("be nice\nAlways confirm with the user before a write. Reservation ids are 6 chars.\n")
    assert pv(pc, run_with_traces) is None
    assert (run_with_traces / abl2_overfit.CACHE).is_file()


def test_tools_edit_rejected_by_policy_scope(pc, run_with_traces):
    set_tools(pc[1], lambda s: s.replace("x + 1", "x + 2"))
    lint, d = pv(pc, run_with_traces)
    assert lint == "surface" and "tools/tools.py" in d


def test_benchmark_policy_content_is_generic(tmp_path, run_with_traces):
    f = abl2_overfit.build_forbidden(run_with_traces / "rollouts/val", "contact HAT156 and Emma Kim")
    assert "HAT156" not in f["flight_numbers"] and "Emma Kim" not in f["names"]


@pytest.mark.skipif(not RUN_MAIN.is_dir(), reason="real run absent")
def test_forbidden_on_real_run_has_sane_content():
    f = abl2_overfit.build_forbidden(RUN_MAIN / "rollouts/val", "")
    assert len(f["user_ids"]) > 10 and len(f["reservation_ids"]) > 50 and not any(x.startswith("HAT") for x in f["reservation_ids"])


# ---- abl.py validation -------------------------------------------------------
def test_abl2_scope_validation():
    assert abl.load({"abl2_scope": "Tools"}).scope == "tools"
    assert abl.load({"abl2_scope": "policy"}).active
    assert not abl.load({}).active and abl.load({}).scope is None
    for bad in ({"abl2_scope": "both"}, {"abl2_scope": "tools", "abl_capability": "P"},
                {"abl2_scope": "policy", "abl_info": "eval"}):
        with pytest.raises(ValueError):
            abl.load(bad)


# ---- audit -------------------------------------------------------------------
def test_best_val_candidate_ties_earliest(tmp_path):
    ev = [{"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.9},
          {"kind": "evaluate", "split": "val", "tag": "cand_0001", "reward": 0.5},
          {"kind": "evaluate", "split": "val", "tag": "cand_0002", "reward": 0.7},
          {"kind": "evaluate", "split": "val", "tag": "cand_0003", "reward": 0.7},
          {"kind": "other", "tag": "cand_0004", "reward": 1.0}]
    (tmp_path / "events.jsonl").write_text("\n".join(json.dumps(e) for e in ev))
    assert abl2_audit.best_val_candidate(tmp_path) == {"candidate": "cand_0002", "val": 0.7}
    assert abl2_audit.best_val_candidate(tmp_path / "nope")["candidate"] is None


def test_truncation_report(tmp_path):
    for name, stop in (("a", "end_turn"), ("b", "tool_use")):
        d = tmp_path / "claude_cfg/projects/p" / name
        d.mkdir(parents=True)
        (d.parent / f"{name}.jsonl").write_text(
            json.dumps({"type": "assistant", "message": {"stop_reason": "tool_use"}}) + "\n"
            + json.dumps({"type": "assistant", "message": {"stop_reason": stop}}) + "\n"
            + json.dumps({"type": "user"}) + "\n")
    r = abl2_audit.truncation_report(tmp_path)
    assert r["session_count"] == 2 and r["cut_count"] == 1


@pytest.mark.skipif(not (RUNS / "GATE-K2/s2/claude_cfg").is_dir(), reason="real run absent")
def test_truncation_real_k2():
    assert abl2_audit.truncation_report(RUNS / "GATE-K2/s2")["cut_count"] == 17
    assert abl2_audit.truncation_report(RUNS / "GATE-K2/s0")["cut_count"] == 0


# ---- run_step: no rollouts paid ----------------------------------------------
def _run(tmp_path, scope, edit, traces=False):
    from test_capability_validation_wiring import CountingAdapter, _adapter, _fresh_run
    from cap_evolve import harness
    adapter = CountingAdapter(_adapter())

    def seed_extra(seed):
        (seed / "policy").mkdir(exist_ok=True)
        (seed / "policy/policy.md").write_text("be nice\n")
        (seed / "tools").mkdir(exist_ok=True)
        (seed / "tools/tools.py").write_text(TOOLS)
    rd, base = _fresh_run(tmp_path, adapter, "abl2", seed_extra=seed_extra)
    spec = tmp_path / "abl2.yaml"
    spec.write_text(f"abl2_scope: {scope}\n")
    rd.log_event("spec_resolved", spec=str(spec))
    if traces:
        (rd.root / "rollouts/val").mkdir(parents=True, exist_ok=True)
        (rd.root / "rollouts/val/0__seed__t0.json").write_text(json.dumps(
            _rollout(3, ["reservation K1NW8N for mia_li_3668"])))
    before = adapter.rollouts
    rejected, history, store = harness._init_memory_store(rd, None)
    step = harness.run_step(adapter, run_dir=rd, parent_dir=rd.candidate_dir("seed"), optimizer=edit,
                            instructions="go", current_val=base, ctx=harness.OptimizerContext(),
                            rejected=rejected, gate_kwargs={"mode": "significant", "k_se": 1.0})
    evs = [json.loads(l) for l in (rd.root / "events.jsonl").read_text().splitlines() if l.strip()]
    return step, adapter.rollouts - before, rd, evs


def test_run_step_tools_scope_policy_edit_costs_nothing(tmp_path):
    def opt(w, i):
        (w / "policy/policy.md").write_text("be nice\nmore\n")
    step, paid, rd, evs = _run(tmp_path, "tools", opt)
    assert paid == 0 and step["accepted"] is False and step["candidate_val"] is None
    assert "SURFACE VIOLATION" in step["decision"]["reason"]
    assert any(e.get("kind") == "surface_violation" for e in evs)
    assert "SURFACE VIOLATION" in (rd.root / "rejected.jsonl").read_text()


def test_run_step_tools_scope_get_procedure_costs_nothing(tmp_path):
    def opt(w, i):
        (w / "tools/tools.py").write_text(TOOLS + PROC)
    step, paid, rd, evs = _run(tmp_path, "tools", opt)
    assert paid == 0 and "POLICY-IN-TOOL LINT" in step["decision"]["reason"]


def test_run_step_policy_scope_overfit_costs_nothing(tmp_path):
    def opt(w, i):
        (w / "policy/policy.md").write_text("be nice\nreservation K1NW8N is special\n")
    step, paid, rd, evs = _run(tmp_path, "policy", opt, traces=True)
    assert paid == 0 and step["accepted"] is False and step["candidate_val"] is None
    assert step["decision"]["reason"].startswith("OVERFIT LINT:")
    assert "OVERFIT LINT" in (rd.root / "rejected.jsonl").read_text()
    ev = [e for e in evs if e.get("kind") == "surface_violation"]
    assert ev and ev[0]["lint"] == "overfit"
