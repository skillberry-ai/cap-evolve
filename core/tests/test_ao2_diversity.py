"""AO-2: near-duplicate proposals are refused (HC-2's diversity gate), and proposals stay within one round."""
import sys
import unittest.mock as m
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))
import ao2_fakes as F  # noqa: E402,F401  (puts core/ and the agent-optimize scripts on sys.path)

import conductor  # noqa: E402
import conductor_backend  # noqa: E402


def _tree(root, body):
    (root / "SKILL.md").parent.mkdir(parents=True, exist_ok=True)
    (root / "SKILL.md").write_text(body)
    return root


def _gate(tmp_path, spec=None):
    from cap_evolve import RunDir, Budget
    rd = RunDir.create(tmp_path / "rd", ts="t", budget=Budget(max_iterations=5))
    fake = SimpleNamespace(cfg=SimpleNamespace(k_prop=2), spec=spec or {}, run_dir=rd)
    parent = _tree(tmp_path / "parent", "rule one\nrule two\n")
    return fake, parent


def test_a_reworded_copy_of_a_registered_edit_is_refused_and_a_different_edit_passes(tmp_path):
    fake, parent = _gate(tmp_path)
    fmt = "Always wrap the answer in a fenced python block and never emit tool call syntax in any reply\n"
    a = _tree(tmp_path / "a", "rule one\nrule two\n" + fmt)
    b = _tree(tmp_path / "b", "rule one\nrule two\n" + fmt.replace("Always", "ALWAYS"))
    c = _tree(tmp_path / "c", "rule one\nrule two\nCheck the cancellation window before cancelling any booking\n")
    with m.patch.object(conductor_backend.digest, "cand_dir", lambda rd, t: parent):
        gate = lambda tag, w: conductor_backend.RealBackend._near_duplicate(fake, {"kind": "propose", "tag": tag}, w, "seed")  # noqa: E731
        assert gate("cand_1", a) == ""
        refusal = gate("cand_2", b)
        assert "near-duplicate" in refusal and "different root cause" in refusal
        assert gate("cand_3", c) == ""
        assert gate("cand_4", a).startswith("near-duplicate")       # the first edit is still remembered
        assert conductor_backend.RealBackend._near_duplicate(fake, {"kind": "merge", "tag": "m"}, a, "seed") == ""


def test_the_gate_can_be_turned_off_and_remembers_across_instances(tmp_path):
    fake, parent = _gate(tmp_path, {"ao_diversity_threshold": 0})
    a = _tree(tmp_path / "a", "rule one\nrule two\nsame same same edit text here\n")
    with m.patch.object(conductor_backend.digest, "cand_dir", lambda rd, t: parent):
        for tag in ("c1", "c2"):
            assert conductor_backend.RealBackend._near_duplicate(fake, {"kind": "propose", "tag": tag}, a, "seed") == ""
        fake.spec = {}
        fresh = SimpleNamespace(cfg=fake.cfg, spec={}, run_dir=fake.run_dir)
        assert conductor_backend.RealBackend._near_duplicate(fresh, {"kind": "propose", "tag": "c3"}, a, "seed") == ""
        assert conductor_backend.RealBackend._near_duplicate(fresh, {"kind": "propose", "tag": "c4"}, a, "seed")


def test_p2_proposals_are_bounded_to_one_round_by_default():
    cfg = conductor.Cfg.from_spec({"promotion_rule": "P2", "split_mode": "pooled", "ao_k_prop": 4})
    assert cfg.pipeline == 1 and cfg.alive_cap == 4
    cfg2 = conductor.Cfg.from_spec({"promotion_rule": "P2", "split_mode": "pooled", "ao_k_prop": 4, "ao_pipeline": 2})
    assert cfg2.alive_cap == 8


# ---- schema refusals do not feed the idle stop -------------------------------------------------------

def _conductor_with_refusals(tmp_path, reason):
    w, be, cfg = F.make(tmp_path, spec={"max_metric_calls": 900, "ao_plateau_n": 99, "ao_max_idle_proposals": 2})
    c = conductor.Conductor(w.root, be, cfg, sleep=lambda s: None)
    be.register = lambda job, res: {"ok": False, "refused": reason, "detail": "x"}
    return c


def _refuse(c, n):
    for i in range(n):
        c._reaped_propose({"tag": f"cand_{i + 1}", "parent": "seed", "id": f"j{i}", "kind": "propose"}, {"ok": True})
    return int(c.st.get("idle_proposals", 0))


def test_paperwork_refusals_do_not_end_the_search_but_a_runaway_of_them_still_does(tmp_path):
    c = _conductor_with_refusals(tmp_path, "hypothesis")
    cap = c.cfg.caps.max_idle
    assert cap == 2 and _refuse(c, 4 * cap * conductor.SCHEMA_REFUSAL_FACTOR // 5 + 2) == 0     # well past max_idle
    assert _refuse(c, 6 * cap * conductor.SCHEMA_REFUSAL_FACTOR) > 0                           # the runaway guard


def test_genuine_no_edit_and_failed_outcomes_still_count_as_idle(tmp_path):
    for reason in ("no_candidate", "pregate", "job_failed"):
        c = _conductor_with_refusals(tmp_path / reason, reason)
        assert _refuse(c, 3) >= 2, reason


def test_the_valid_cluster_ids_are_in_every_proposer_prompt(tmp_path):
    import json
    import proposer
    from cap_evolve import RunDir, Budget
    rd = RunDir.create(tmp_path / "rd", ts="t", budget=Budget(max_iterations=5))
    (rd.root / "clusters.json").write_text(json.dumps([{"cluster_id": "C1", "tasks": ["1"], "signature": "tool errors"},
                                                       {"cluster_id": "C2", "tasks": ["2"], "label": "format"}]))
    fake = SimpleNamespace(run_dir=rd)
    ids = conductor_backend.RealBackend._valid_clusters(fake)
    assert ids == [("C1", "tool errors"), ("C2", "format")]
    body = proposer.build_prompt(workdir=tmp_path / "w", parent="seed", cluster=None, valid_clusters=ids)
    assert "Valid cluster_ids" in body and "- C1: tool errors" in body and "- C2: format" in body
    assert "Valid cluster_ids" not in proposer.build_prompt(workdir=tmp_path / "w", parent="seed", cluster=None)
    merge = proposer.build_prompt(workdir=tmp_path / "w", parent="seed", cluster=None, kind="merge",
                                  conflicts=["a"], valid_clusters=ids)
    assert "Valid cluster_ids" not in merge
    assert len(body.encode()) <= proposer.MAX_PROMPT_BYTES
