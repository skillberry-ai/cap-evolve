"""#712: the decision digest (<= 1.5k tokens, numbers cited) and the six act.py verbs."""

from __future__ import annotations

import json
import math
import random
import re
import sys
import time
import types
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts"
sys.path.insert(0, str(REPO / "core"))
sys.path.insert(0, str(SCRIPTS))

import act  # noqa: E402
import digest  # noqa: E402
from cap_evolve import RunDir, eval_index, graph, hypotheses  # noqa: E402
from test_round_requires_screen_ladder import _staged_run_dir  # noqa: E402

SWITCHES = ("DAG_PARALLEL", "ACTIVE_EVAL", "SMART_MERGE", "COST_GATING", "FAILURE_CLUSTERING",
            "PREGATE", "CONTEXT_DIGEST", "OPTIMIZER_COST")


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in SWITCHES:
        monkeypatch.delenv(f"CAPEVOLVE_{k}", raising=False)
    monkeypatch.setenv("CAPEVOLVE_OPTIMIZER_COST", "off")  # tests opt in to metering explicitly
    monkeypatch.delenv("CAPEVOLVE_HOST_METER", raising=False)


def _row(h, task, i, reward, ts=None, tag="x"):
    return {"cap_hash": h, "split": "val", "task": task, "trial_idx": i, "tag": tag, "k": i, "env_fp": "",
            "window_id": 0, "reward": float(reward), "subset": False, "cost": 0.01, "tokens": 1,
            "ts": time.time() if ts is None else ts}


def _ledger(rd, h, data, ts=None):
    with (rd.root / eval_index.LEDGER).open("a") as f:
        for task, rs in data.items():
            for i, r in enumerate(rs):
                f.write(json.dumps(_row(h, task, i, r, ts)) + "\n")


def _h(rd, tag):
    return eval_index.cap_hash(digest.cand_dir(rd, tag))


def _run(tmp_path, **kw):
    rd, project, work = _staged_run_dir(tmp_path, **kw)
    return rd, project, work, [str(t) for t in rd.read_splits().ids("val")]


def _args(rd, project=None, *extra):
    return ["--run-dir", str(rd.root), *(["--project", str(project)] if project else []), *extra]


class Sh:
    """Replacement for act.sh: answers by script name, records every command."""

    def __init__(self, **answers):
        self.answers, self.calls = answers, []

    def __call__(self, cmd, env=None):
        cmd = [str(c) for c in cmd]
        self.calls.append(cmd)
        for name, ans in self.answers.items():
            if any(c.endswith(name) for c in cmd):
                return ans(cmd) if callable(ans) else ans
        return 0, "{}", ""

    def cmd(self, name):
        return next(c for c in self.calls if any(x.endswith(name) for x in c))


def _act(monkeypatch, capsys, argv, sh=None):
    if sh is not None:
        monkeypatch.setattr(act, "sh", sh)
    rc = act.main(argv)
    out = json.loads(capsys.readouterr().out)
    return rc, out


# ---- noise: sd_est from repeat cells ---------------------------------------------------------

def test_sd_est_from_repeat_cells_is_exact_on_a_known_case(tmp_path):
    rd, _, _, val = _run(tmp_path)
    _ledger(rd, "h1", {t: [1, 0, 1, 0] for t in val})            # unbiased var 1/3 per task
    n = digest.noise(rd, val)
    assert n["sd_est"] == pytest.approx(math.sqrt(len(val) / 3) / len(val), abs=1e-4)
    assert n["min_detectable"] == pytest.approx(2 * n["sd_est"], abs=1e-3)
    assert n["repeat_cells"] == len(val)


def test_sd_est_tracks_the_true_sd_of_a_one_trial_full_val_mean(tmp_path):
    """Statistical claim: pooled repeat-cell variance recovers sqrt(sum p(1-p))/T (here p=.5)."""
    rd, _, _, val = _run(tmp_path)
    rng = random.Random(7)
    for k in range(40):   # 40 byte-distinct candidates, 2 trials per cell
        _ledger(rd, f"h{k}", {t: [int(rng.random() < .5) for _ in range(2)] for t in val})
    true = math.sqrt(len(val) * .25) / len(val)
    assert digest.noise(rd, val)["sd_est"] == pytest.approx(true, rel=0.12)


def test_sd_est_is_called_stale_when_thin_or_old(tmp_path):
    rd, _, _, val = _run(tmp_path)
    assert digest.noise(rd, val) == {"sd_est": None, "min_detectable": None, "repeat_cells": 0,
                                     "stale": True, "why": "no repeat cells yet"}
    _ledger(rd, "h1", {t: [1, 0] for t in val[:2]})
    n = digest.noise(rd, val)
    assert n["stale"] and "only 2 repeat cells" in n["why"]
    _ledger(rd, "h2", {t: [1, 0] for t in val})
    assert not digest.noise(rd, val)["stale"]
    assert "min old" in digest.noise(rd, val, now=time.time() + 4 * 3600)["why"]


# ---- the digest ------------------------------------------------------------------------------

def _two_tips(rd, work, val, c1, c2):
    """cand_1 / cand_2 are siblings off 'cur'; cur alternates 0/1, c1/c2 map task -> rewards."""
    import shutil
    shutil.copytree(work / "cand_1", work / "cand_2")
    (work / "cand_2" / "extra.md").write_text("different bytes")
    for t in ("cand_1", "cand_2"):
        graph.append_node(rd, node_id=t, parents=["cur"], status="proposed")
    _ledger(rd, _h(rd, "cur"), {t: [i % 2] * 3 for i, t in enumerate(val)})
    _ledger(rd, _h(rd, "cand_1"), c1)
    _ledger(rd, _h(rd, "cand_2"), c2)


def test_digest_reports_tips_with_posteriors_noise_and_suggestions_that_cite_numbers(tmp_path):
    rd, _, work, val = _run(tmp_path)
    _two_tips(rd, work, val, {t: [1, 1, 1] for t in val}, {t: [0] for t in val[:2]})
    (rd.root / "clusters.json").write_text(json.dumps({"clusters": [
        {"cluster_id": "C1", "signature": "arith", "tasks": val[:3], "headroom": 0.13}]}))
    d = digest.build(rd)
    tips = {t["id"]: t for t in d["tips"]}
    assert tips["cand_1"]["p_beat_parent"] > 0.95 and tips["cand_1"]["cov"] == f"{len(val)}/{len(val)}"
    assert tips["cand_1"]["mean"] > tips["cand_2"]["mean"], "tips are ranked by posterior mean"
    assert tips["cand_2"]["cov"] == f"2/{len(val)}"
    assert d["clusters"][0]["id"] == "C1" and d["clusters"][0]["status"] == "open"
    sug = {(s["verb"], s["target"]): s["why"] for s in d["suggested"]}
    promote = sug[("promote", "cand_1")]
    assert re.search(r"P\(beat parent\) [0-9.]+", promote) and "cov" in promote
    assert any(v == "propose" and "headroom 0.13" in w for (v, _), w in sug.items())
    text = digest.render(d)
    assert "cand_1" in text and "p_beat_parent" in text and digest.tokens(text) <= digest.MAX_TOKENS


def test_a_tip_with_futile_evidence_is_suggested_for_pruning(tmp_path):
    rd, _, work, val = _run(tmp_path)
    _two_tips(rd, work, val, {t: [0, 0, 0, 0] for t in val}, {t: [1] for t in val})
    d = digest.build(rd)
    assert ("prune", "cand_1") in {(s["verb"], s["target"]) for s in d["suggested"]}


def test_untried_tip_is_suggested_for_probing_and_unmeasured_noise_is_flagged(tmp_path):
    rd, _, work, val = _run(tmp_path)
    graph.append_node(rd, node_id="cand_1", parents=["cur"], status="proposed")
    d = digest.build(rd)
    assert d["tips"][0]["p_beat_parent"] is None and d["tips"][0]["cov"] == f"0/{len(val)}"
    assert d["noise"]["stale"]
    assert ("probe", "cand_1") in {(s["verb"], s["target"]) for s in d["suggested"]}


def test_stop_when_the_best_open_cluster_is_below_what_noise_can_resolve(tmp_path):
    rd, _, work, val = _run(tmp_path)
    for i in range(8):
        _ledger(rd, f"h{i}", {t: [1, 0] for t in val})            # big noise: min detectable ~0.5
    (rd.root / "clusters.json").write_text(json.dumps([{"cluster_id": "C9", "tasks": val[:1], "headroom": 0.03}]))
    d = digest.build(rd)
    fin = [s for s in d["suggested"] if s["verb"] == "finalize"]
    assert fin and "0.03" in fin[0]["why"] and "min detectable" in fin[0]["why"]


def test_hypothesis_history_drives_cluster_status(tmp_path):
    rd, _, _, val = _run(tmp_path)
    cl = [{"cluster_id": "C1", "tasks": val[:2], "headroom": .1}, {"cluster_id": "C2", "tasks": val[2:4], "headroom": .1},
          {"cluster_id": "C3", "tasks": val[4:6], "headroom": .1}]
    hs = [{"id": f"p{i}", "cluster_ids": ["C1"], "edit_scope": ["policy"], "status": "pruned"} for i in range(3)]
    hs += [{"id": "a", "cluster_ids": ["C2"], "edit_scope": ["policy"]}]
    rows = {r["id"]: r["status"] for r in digest.cluster_rows(cl, hs, per_task=False)}
    assert rows == {"C1": "stuck", "C2": "attempted", "C3": "open"}
    hs.append({"id": "a", "status": "fixed"})   # a later record for the same id wins (merged on id)
    merged = {h["id"]: h for h in hs}
    assert digest.hyp_latest.__doc__  # last-record-wins is the documented contract
    assert merged["a"]["status"] == "fixed"


def test_failure_clustering_off_lists_tasks_not_clusters(tmp_path, monkeypatch):
    rd, _, _, val = _run(tmp_path)
    (rd.root / "clusters.json").write_text(json.dumps([{"cluster_id": "C1", "tasks": val[:3], "headroom": .2}]))
    monkeypatch.setenv("CAPEVOLVE_FAILURE_CLUSTERING", "0")
    ids = [c["id"] for c in digest.build(rd)["clusters"]]
    assert sorted(ids) == sorted(f"task {t}" for t in val[:3])


def test_context_digest_off_gives_raw_numbers_and_no_suggestions(tmp_path, monkeypatch):
    rd, _, _, _ = _run(tmp_path)
    monkeypatch.setenv("CAPEVOLVE_CONTEXT_DIGEST", "0")
    d = digest.build(rd)
    assert d["context_digest"] is False and "suggested" not in d and "tips" not in d
    assert "context_digest off" in digest.render(d)


def test_digest_fits_the_token_budget_on_a_large_run():
    d = {"budget": {"remaining_usd": 12.5, "eval_usd": 40, "opt_usd": 9, "usersim_usd": 3, "rollouts": 2000, "wall_min": 300},
         "noise": {"sd_est": .048, "min_detectable": .1, "repeat_cells": 40, "stale": False, "why": ""},
         "champion": {"id": "cand_4", "mean": .6, "cov": 30, "T": 30},
         "clusters": [{"id": f"C{i:05d}", "label": "x" * 28, "tasks": [str(j) for j in range(8)], "headroom": .1,
                       "status": "open", "attempts": 2} for i in range(40)],
         "tips": [{"id": f"cand_{i}", "mean": .5, "se": .05, "cov": "30/30", "p_beat_parent": .4, "p_beat_champ": .3, "n": 90}
                  for i in range(30)],
         "merge_opps": [{"a": "cand_1", "b": "cand_2", "I": .1, "complementarity": .6}] * 3,
         "pregate": ["cand_3: " + "w" * 100] * 4,
         "suggested": [{"verb": "probe", "target": f"cand_{i}", "why": "y" * 150} for i in range(6)],
         "warnings": ["a" * 200] * 5}
    d2, text = digest.fit(d)
    assert digest.tokens(text) <= digest.MAX_TOKENS
    assert "cand_0" in text and "probe cand_0" in text, "the head of every list survives trimming"


def test_merge_opportunities_need_complementary_wins_and_no_existing_merge(tmp_path, monkeypatch):
    rd, _, work, val = _run(tmp_path)
    _two_tips(rd, work, val, {t: [1, 1, 1] for t in val}, {t: [1, 1, 1] for t in val})
    wins = {"cand_1": set(val[:3]), "cand_2": set(val[3:6])}
    fake = types.SimpleNamespace(
        wins_from_run=lambda rd_, tags, base: wins,
        features=lambda b, x, t, w: {"wins": w}, interaction=lambda f1, f2: {"I": 0.12, "unknown": False})
    monkeypatch.setitem(sys.modules, "merge_n", fake)
    opps = digest.build(rd)["merge_opps"]
    assert [(o["a"], o["b"], o["complementarity"], o["I"]) for o in opps] == [("cand_1", "cand_2", 1.0, 0.12)]
    wins["cand_2"] = set(val[:3])     # same wins => redundant, not complementary
    assert digest.build(rd)["merge_opps"] == []
    assert digest.complementarity({"a", "b"}, {"b", "c"}) == pytest.approx(2 / 3, abs=1e-3)


def test_digest_is_valid_under_repeated_looks_at_equal_candidates(tmp_path):
    """Acting on the digest at EVERY look must not promote a candidate whose true rate equals
    the champion's: sequential looks at 5 growing evidence levels, 20 simulated runs."""
    false_promotes = 0
    for sim in range(20):
        sub = tmp_path / f"s{sim}"
        sub.mkdir()
        rd, _, work, val = _run(sub, n=12)
        import shutil
        shutil.copytree(work / "cand_1", work / "cand_2")
        (work / "cand_2" / "z.md").write_text("z")
        graph.append_node(rd, node_id="cand_2", parents=["cur"], status="proposed")
        rng = random.Random(sim)
        p = {t: rng.choice([.2, .5, .8]) for t in val}         # shared true per-task rates
        for look in range(5):
            for tag in ("cur", "cand_2"):
                _ledger(rd, _h(rd, tag), {t: [int(rng.random() < p[t]) for _ in range(2)] for t in val},
                        ts=time.time() + look * 1000 + (tag == "cur"))   # distinct (tag, look) rows
            d = digest.build(rd)
            if any(s["verb"] == "promote" for s in d["suggested"]):
                false_promotes += 1
                break
    assert false_promotes <= 2, f"{false_promotes}/20 equal-rate runs were suggested for promotion"


# ---- metering --------------------------------------------------------------------------------

def _session_log(rd, tmp_path, monkeypatch, usage_out=1_000_000):
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(Path(rd.root).parent.parent.resolve()))
    log = tmp_path / "claude" / "projects" / slug / "sess.jsonl"
    log.parent.mkdir(parents=True)
    log.write_text(json.dumps({"type": "assistant", "timestamp": "2030-01-01T00:00:00Z", "message": {
        "id": "m1", "model": "claude-opus-4-8", "usage": {"output_tokens": usage_out}}}) + "\n")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "claude"))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "sess")
    monkeypatch.setenv("CAPEVOLVE_OPTIMIZER_COST", "session")


def test_budget_includes_real_optimizer_spend_exactly_once(tmp_path, monkeypatch):
    rd, _, _, _ = _run(tmp_path)
    _session_log(rd, tmp_path, monkeypatch)
    d = digest.build(rd)
    assert d["budget"]["opt_usd"] == pytest.approx(25.0, abs=0.01)
    again = digest.build(RunDir.open(rd.root))
    assert again["budget"]["opt_usd"] == pytest.approx(25.0, abs=0.01), "metering is idempotent"
    kinds = [json.loads(ln)["kind"] for ln in rd.events_path.read_text().splitlines()]
    assert kinds.count("optimizer_spend") == 1


def test_metering_failure_fails_open_loudly_and_strict_raises(tmp_path, monkeypatch, capsys):
    rd, _, _, _ = _run(tmp_path)
    monkeypatch.setenv("CAPEVOLVE_OPTIMIZER_COST", "session")
    monkeypatch.setattr(digest.optimizer_cost, "harvest", lambda *a, **k: (_ for _ in ()).throw(OSError("disk")))
    assert digest.meter(rd) is None
    assert "metering failed" in capsys.readouterr().err
    with pytest.raises(OSError):
        digest.meter(rd, strict=True)


# ---- act: propose ----------------------------------------------------------------------------

def _hyp(path, tasks, cid="C1", hid="h1"):
    path.write_text(json.dumps({"id": hid, "cluster_ids": [cid], "claim": "c", "predicted_tasks": tasks,
                                "predicted_mechanism": "m", "edit_scope": ["policy"]}))
    return str(path)


def test_propose_first_call_prepares_a_child_of_the_named_parent(tmp_path, capsys, monkeypatch):
    rd, _, work, _ = _run(tmp_path)
    rc, out = _act(monkeypatch, capsys, ["propose", "cand_new", "--parent", "cur", *_args(rd)])
    assert rc == 0 and out["result"]["stage"] == "proposed" and (work / "cand_new").is_dir()
    assert graph.latest_node(rd, "cand_new")["parents"] == ["cur"]
    assert "edit" in out["result"]["next"] and "digest" in out


def test_propose_enforces_the_multi_task_rule_and_failure_clustering_off_waives_it(tmp_path, capsys, monkeypatch):
    rd, _, _, val = _run(tmp_path)
    (rd.root / "clusters.json").write_text(json.dumps([{"cluster_id": "C1", "tasks": val[:2], "headroom": 0.02}]))
    sh = Sh(**{"pregate.py": (0, json.dumps({"ok": True, "checks": [], "warnings": []}), "")})
    f = _hyp(tmp_path / "h.json", val[:1])
    rc, out = _act(monkeypatch, capsys, ["propose", "cand_1", "--parent", "cur", "--hypothesis-file", f, *_args(rd)], sh)
    assert rc == 2 and "hypothesis rejected" in out["error"] and not sh.calls, "refused before any check runs"
    f2 = _hyp(tmp_path / "h2.json", val[:2], hid="h2")
    rc, out = _act(monkeypatch, capsys, ["propose", "cand_1", "--parent", "cur", "--hypothesis-file", f2, *_args(rd)], sh)
    assert rc == 0 and out["result"]["stage"] == "checked"
    assert graph.latest_node(rd, "cand_1")["stage"] == "checked"
    assert [h["id"] for h in hypotheses.load(rd)] == ["h2"]
    monkeypatch.setenv("CAPEVOLVE_FAILURE_CLUSTERING", "0")
    rc, out = _act(monkeypatch, capsys, ["propose", "cand_1", "--parent", "cur", *_args(rd)], sh)
    assert rc == 0, "off: no hypothesis needed"


def test_propose_returns_the_pregate_failure_and_stays_proposed(tmp_path, capsys, monkeypatch):
    rd, _, _, _ = _run(tmp_path)
    monkeypatch.setenv("CAPEVOLVE_FAILURE_CLUSTERING", "0")
    sh = Sh(**{"pregate.py": (1, json.dumps({"ok": False, "failure": "[hidden_writes] composite writes", "warnings": []}), "")})
    rc, out = _act(monkeypatch, capsys, ["propose", "cand_1", "--parent", "cur", *_args(rd)], sh)
    assert rc == 2 and "hidden_writes" in out["error"]
    assert graph.latest_node(rd, "cand_1")["stage"] == "proposed"


def test_pregate_infra_error_fails_open_with_a_warning_and_strict_refuses(tmp_path, capsys, monkeypatch):
    rd, _, _, _ = _run(tmp_path)
    monkeypatch.setenv("CAPEVOLVE_FAILURE_CLUSTERING", "0")
    sh = Sh(**{"pregate.py": (3, "Traceback...", "boom")})
    rc, out = _act(monkeypatch, capsys, ["propose", "cand_1", "--parent", "cur", *_args(rd)], sh)
    assert rc == 0 and any("pregate infra error" in w for w in out["warnings"])
    rc, out = _act(monkeypatch, capsys, ["propose", "cand_1", "--parent", "cur", *_args(rd, None, "--strict")], sh)
    assert rc == 2 and "--strict" in out["error"]


def test_pregate_off_never_runs_it_and_dag_parallel_off_parents_on_best(tmp_path, capsys, monkeypatch):
    rd, _, work, _ = _run(tmp_path)
    monkeypatch.setenv("CAPEVOLVE_FAILURE_CLUSTERING", "0")
    monkeypatch.setenv("CAPEVOLVE_PREGATE", "0")
    sh = Sh()
    rc, out = _act(monkeypatch, capsys, ["propose", "cand_1", "--parent", "elsewhere", *_args(rd)], sh)
    assert rc == 0 and out["result"]["pregate"] is None
    assert not any(c[1].endswith("pregate.py") for c in sh.calls)
    monkeypatch.setenv("CAPEVOLVE_DAG_PARALLEL", "0")
    rc, out = _act(monkeypatch, capsys, ["propose", "cand_9", "--parent", "elsewhere", *_args(rd)], sh)
    assert out["result"]["parent"] == "cur" and any("dag_parallel is off" in w for w in out["warnings"])


def test_unknown_ablation_key_in_the_spec_refuses_the_verb(tmp_path, capsys, monkeypatch):
    rd, project, _, _ = _run(tmp_path)
    (project / "capevolve.yaml").write_text((project / "capevolve.yaml").read_text() + "optimizer:\n  ablation:\n    pregte: false\n")
    rc, out = _act(monkeypatch, capsys, ["probe", "cand_1", "--plan", *_args(rd, project)])
    assert rc == 2 and "unknown ablation key" in out["error"]


def test_decision_event_records_whether_the_digest_was_followed(tmp_path, capsys, monkeypatch):
    rd, _, _, val = _run(tmp_path)
    monkeypatch.setenv("CAPEVOLVE_FAILURE_CLUSTERING", "0")
    sh = Sh(**{"pregate.py": (0, json.dumps({"ok": True}), "")})
    (rd.root / "digest_last.json").write_text(json.dumps({"suggested": [{"verb": "propose", "target": "cand_1", "why": ""}]}))
    _act(monkeypatch, capsys, ["propose", "cand_1", "--parent", "cur", *_args(rd)], sh)
    ev = [json.loads(ln) for ln in rd.events_path.read_text().splitlines()]
    assert [e["followed_digest"] for e in ev if e["kind"] == "decision"] == [True]
    (rd.root / "digest_last.json").write_text(json.dumps({"suggested": []}))
    import shutil
    shutil.copytree(rd.root / "work" / "cand_1", rd.root / "work" / "cand_2")
    _act(monkeypatch, capsys, ["propose", "cand_2", "--parent", "cur", *_args(rd)], sh)
    ev = [json.loads(ln) for ln in rd.events_path.read_text().splitlines()]
    assert [e["followed_digest"] for e in ev if e["kind"] == "decision"] == [True, False]


# ---- act: probe (real evaluation through the synthetic adapter) ------------------------------

def test_probe_runs_only_missing_cells_and_a_second_probe_is_free(tmp_path, capsys, monkeypatch):
    rd, project, _, val = _run(tmp_path)
    rc, out = _act(monkeypatch, capsys, ["probe", "cand_1", "--tasks", ",".join(val[:3]), "--n", "1", *_args(rd, project)])
    assert rc == 0, out
    assert out["result"]["missing_cells"] == 3 and out["result"]["ran_cells"] == 3
    h = _h(rd, "cand_1")
    assert sorted(eval_index.counts(rd, h)) == sorted(val[:3])
    node = graph.latest_node(rd, "cand_1")
    assert node["stage"] == "probed" and node["coverage"]["n_tasks"] == 3 and node["post"]["p_beat_parent"] is not None
    rc, out = _act(monkeypatch, capsys, ["probe", "cand_1", "--tasks", ",".join(val[:4]), "--n", "1", *_args(rd, project)])
    assert out["result"]["missing_cells"] == 1, "only the one new cell is paid for"
    rc, out = _act(monkeypatch, capsys, ["probe", "cand_1", "--tasks", ",".join(val[:4]), "--n", "1", *_args(rd, project)])
    assert out["result"]["missing_cells"] == 0 and "free" in out["result"]["next"]


def test_probe_plan_spends_nothing_and_refuses_non_val_tasks(tmp_path, capsys, monkeypatch):
    rd, project, _, val = _run(tmp_path)
    sh = Sh()
    rc, out = _act(monkeypatch, capsys, ["probe", "cand_1", "--plan", "--n", "2", *_args(rd, project)], sh)
    assert rc == 0 and out["result"]["missing_cells"] == 2 * len(val) and not sh.calls
    rc, out = _act(monkeypatch, capsys, ["probe", "cand_1", "--tasks", "not_a_val_task", *_args(rd, project)], sh)
    assert rc == 2 and "frozen val split" in out["error"]


def test_probe_auto_is_full_val_unless_active_eval_then_a_bounded_allocation(tmp_path, capsys, monkeypatch):
    rd, project, _, val = _run(tmp_path)
    graph.append_node(rd, node_id="cand_1", parents=["cur"], status="proposed")
    _ledger(rd, _h(rd, "cur"), {t: [i % 2] * 3 for i, t in enumerate(val)})
    rc, out = _act(monkeypatch, capsys, ["probe", "cand_1", "--auto", "--plan", *_args(rd, project)])
    assert out["result"]["tasks"] == val and "active_eval off" in out["result"]["selected_by"]
    monkeypatch.setenv("CAPEVOLVE_ACTIVE_EVAL", "1")
    rc, out = _act(monkeypatch, capsys, ["probe", "cand_1", "--auto", "--plan", "--budget", "4", *_args(rd, project)])
    r = out["result"]
    assert "allocator" in r["selected_by"] and 0 < len(r["tasks"]) <= 4 and set(r["tasks"]) <= set(val)


def test_probe_passes_the_gateway_cap_to_the_evaluator(tmp_path, capsys, monkeypatch):
    rd, project, _, val = _run(tmp_path, extra="gateway_max_concurrency: 3\n")
    seen = {}
    monkeypatch.setattr(act, "sh", lambda cmd, env=None: (seen.update(env=env, cmd=[str(c) for c in cmd]) or (0, "{}", "")))
    _act(monkeypatch, capsys, ["probe", "cand_1", "--tasks", val[0], *_args(rd, project)])
    assert seen["env"] == {"CAPEVOLVE_WORKERS": "3"} and "--topup-to" in seen["cmd"]
    assert seen["cmd"][seen["cmd"].index("--candidate") + 1] == str(rd.root / "work" / "cand_1")


# ---- act: promote / prune --------------------------------------------------------------------

def _gate(verdict, reward=0.75):
    return (0, json.dumps({"verdict": verdict, "gate": {"accept": verdict == "accept"}, "candidate": {"reward": reward}}), "")


def _covered(rd, val, tags=("cur", "cand_1")):
    graph.append_node(rd, node_id="cand_1", parents=["cur"], status="proposed")
    for t in tags:
        _ledger(rd, _h(rd, t), {v: [1, 1] for v in val})


def test_promote_refuses_without_full_val_coverage(tmp_path, capsys, monkeypatch):
    rd, project, _, val = _run(tmp_path)
    _ledger(rd, _h(rd, "cand_1"), {v: [1] for v in val[:2]})
    sh = Sh()
    rc, out = _act(monkeypatch, capsys, ["promote", "cand_1", *_args(rd, project)], sh)
    assert rc == 2 and "lacks full-val ledger coverage" in out["error"] and "act.py probe" in out["next"] and not sh.calls


def test_promote_accepts_through_the_reward_gated_gate_and_commit(tmp_path, capsys, monkeypatch):
    rd, project, _, val = _run(tmp_path)
    _covered(rd, val)
    sh = Sh(**{"gate_check.py": _gate("accept"), "commit.py": (0, "{}", "")})
    rc, out = _act(monkeypatch, capsys, ["promote", "cand_1", *_args(rd, project)], sh)
    assert rc == 0 and out["result"]["champion_changed"] and out["result"]["gate_mode"] == "reward_gated"
    g, c = sh.cmd("gate_check.py"), sh.cmd("commit.py")
    assert g[g.index("--mode") + 1] == "reward_gated" and g[g.index("--current") + 1] == "cur"
    assert c[c.index("--decision") + 1] == "accept" and c[c.index("--val") + 1] == "0.75"
    node = graph.latest_node(rd, "cand_1")
    assert node["stage"] == "alive" and node["status"] == "accepted"


def test_promote_without_an_accept_leaves_the_champion_alone(tmp_path, capsys, monkeypatch):
    rd, project, _, val = _run(tmp_path)
    _covered(rd, val)
    sh = Sh(**{"gate_check.py": _gate("indecisive")})
    rc, out = _act(monkeypatch, capsys, ["promote", "cand_1", *_args(rd, project)], sh)
    assert rc == 1 and not out["result"]["champion_changed"]
    assert not any(c[1].endswith("commit.py") for c in sh.calls)
    assert graph.latest_node(rd, "cand_1")["stage"] == "alive" and rd.best_id == "cur"


def test_cost_gating_off_uses_the_paired_gate(tmp_path, capsys, monkeypatch):
    rd, project, _, val = _run(tmp_path)
    _covered(rd, val)
    monkeypatch.setenv("CAPEVOLVE_COST_GATING", "0")
    sh = Sh(**{"gate_check.py": _gate("reject")})
    _act(monkeypatch, capsys, ["promote", "cand_1", *_args(rd, project)], sh)
    g = sh.cmd("gate_check.py")
    assert g[g.index("--mode") + 1] == "paired"


def test_gate_that_cannot_judge_refuses(tmp_path, capsys, monkeypatch):
    rd, project, _, val = _run(tmp_path)
    _covered(rd, val)
    sh = Sh(**{"gate_check.py": (2, json.dumps({"error": "no val rollouts for tag"}), "")})
    rc, out = _act(monkeypatch, capsys, ["promote", "cand_1", *_args(rd, project)], sh)
    assert rc == 2 and "could not judge" in out["error"]


def test_prune_commits_a_reject_marks_the_hypothesis_and_the_new_engine_keeps_stall_at_zero(tmp_path, capsys, monkeypatch):
    rd, project, _, val = _run(tmp_path)
    graph.append_node(rd, node_id="cand_1", parents=["cur"], status="proposed", opt_usd_at_propose=1.0)
    hypotheses.append(rd, {"id": "h1", "cluster_ids": ["C1"], "edit_scope": ["policy"], "candidate": "cand_1"})
    rd.update_spent(accepted=False)
    rd.update_spent(accepted=False)
    sh = Sh(**{"commit.py": (0, "{}", "")})
    rc, out = _act(monkeypatch, capsys, ["prune", "cand_1", "--reason", "p=0.04 after 60 trials", *_args(rd, project)], sh)
    assert rc == 0
    c = sh.cmd("commit.py")
    assert c[c.index("--decision") + 1] == "reject" and c[c.index("--reject-basis") + 1] == "driver_judgement"
    assert "p=0.04" in c[c.index("--bypassed-gate-justification") + 1]
    assert graph.latest_node(rd, "cand_1")["stage"] == "pruned"
    assert hyp_status(rd) == "pruned"
    assert RunDir.open(rd.root).spent.stall == 2, "legacy engine: the stall counter is the commit's business"
    monkeypatch.setenv("CAPEVOLVE_ACTIVE_EVAL", "1")
    graph.append_node(rd, node_id="cand_2", parents=["cur"], status="proposed")
    _act(monkeypatch, capsys, ["prune", "cand_2", "--reason", "r", *_args(rd, project)], sh)
    assert RunDir.open(rd.root).spent.stall == 0, "new engine has no stall rule"


def hyp_status(rd):
    return digest.hyp_latest(rd)[0]["status"]


def test_prune_needs_a_reason_and_surfaces_a_commit_refusal(tmp_path, capsys, monkeypatch):
    rd, project, _, _ = _run(tmp_path)
    sh = Sh(**{"commit.py": (2, json.dumps({"error": "already has a decision"}), "")})
    rc, out = _act(monkeypatch, capsys, ["prune", "cand_1", "--reason", "x", *_args(rd, project)], sh)
    assert rc == 2 and "already has a decision" in json.dumps(out["commit"])
    rc, out = _act(monkeypatch, capsys, ["prune", "cand_1", "--reason", "  ", *_args(rd, project)], sh)
    assert rc == 2 and "reason" in out["error"]


# ---- act: merge ------------------------------------------------------------------------------

def _fake_merge_n(probe=True):
    def plan(tags, dir_of, g, **kw):
        return {"merged": list(tags), "unmerged": [], "conflicts": [], "max_I": 0.31, "unknown_pairs": [],
                "built": True, "probe": probe, "steps": [{"added": tags[1], "base": "cur", "three_way_merged": [], "built": True}],
                "eval_request": {"task_ids": ["a", "b"], "n_trials": 3, "reason": "I=0.31 >= 0.2", "missing": {"a": 3}} if probe else None,
                "order": list(tags)}

    def node_record(res, tag, round_id=None):
        return {"id": tag, "parents": res["merged"], "edit_kind": "merge", "merge_base": "cur", "stage": "built",
                "status": "proposed", "eval_state": "unevaluated"}
    return types.SimpleNamespace(plan=plan, node_record=node_record, wins_from_run=lambda *a: {})


def test_merge_records_a_two_parent_node_and_prices_the_probe(tmp_path, capsys, monkeypatch):
    rd, project, work, val = _run(tmp_path)
    import shutil
    shutil.copytree(work / "cand_1", work / "cand_2")
    for t in ("cand_1", "cand_2"):
        graph.append_node(rd, node_id=t, parents=["cur"], status="proposed")
    (work / "merge_cand_1_cand_2").mkdir()
    (work / "merge_cand_1_cand_2" / "x.md").write_text("m")
    monkeypatch.setitem(sys.modules, "merge_n", _fake_merge_n())
    rc, out = _act(monkeypatch, capsys, ["merge", "cand_1", "cand_2", *_args(rd, project)])
    assert rc == 0 and out["result"]["probe"] is True
    assert "act.py probe merge_cand_1_cand_2 --tasks a,b --n 3" in out["result"]["next"] and "3 cells not in the ledger" in out["result"]["next"]
    node = graph.latest_node(rd, "merge_cand_1_cand_2")
    assert node["parents"] == ["cand_1", "cand_2"] and node["edit_kind"] == "merge" and node["stage"] == "built"
    monkeypatch.setitem(sys.modules, "merge_n", _fake_merge_n(probe=False))
    rc, out = _act(monkeypatch, capsys, ["merge", "cand_1", "cand_2", "--tag", "m2", *_args(rd, project)])
    assert "auto-merged without a probe" in out["result"]["next"]


def test_merge_refuses_when_smart_merge_is_off_or_merge_n_is_missing(tmp_path, capsys, monkeypatch):
    rd, project, _, _ = _run(tmp_path)
    monkeypatch.setitem(sys.modules, "merge_n", _fake_merge_n())
    monkeypatch.setenv("CAPEVOLVE_SMART_MERGE", "0")
    rc, out = _act(monkeypatch, capsys, ["merge", "a", "b", *_args(rd, project)])
    assert rc == 2 and "smart_merge is off" in out["error"]
    monkeypatch.delenv("CAPEVOLVE_SMART_MERGE")
    monkeypatch.setitem(sys.modules, "merge_n", _fake_merge_n())
    rc, out = _act(monkeypatch, capsys, ["merge", "a", *_args(rd, project)])
    assert rc == 2 and "at least two" in out["error"]


# ---- act: finalize ---------------------------------------------------------------------------

def test_finalize_confirms_with_fresh_seeds_gates_against_seed_then_seals_once(tmp_path, capsys, monkeypatch):
    rd, project, _, val = _run(tmp_path)
    rd.snapshot("seed", rd.candidate_dir("cur"))
    _ledger(rd, _h(rd, "cur"), {v: [1, 0] for v in val})
    sh = Sh(**{"gate_check.py": _gate("accept"), "run.py": (0, json.dumps({"test_reward": 0.7}), "")})
    rc, out = _act(monkeypatch, capsys, ["finalize", *_args(rd, project)], sh)
    assert rc == 0, out
    ev = next(c for c in sh.calls if "--topup-to" in c)
    assert ev[ev.index("--topup-to") + 1] == "5", "2 existing trials + 3 confirm trials: seeds never reused"
    g = sh.cmd("gate_check.py")
    assert g[g.index("--candidate") + 1] == "cur" and g[g.index("--current") + 1] == "seed"
    fin = [c for c in sh.calls if "finalize" in c[1]]
    assert fin and out["result"]["final"] == {"test_reward": 0.7}
    assert json.loads((rd.root / "final.json").read_text())["champion"] == "cur"


def test_finalize_refuses_a_second_seal(tmp_path, capsys, monkeypatch):
    rd, project, _, _ = _run(tmp_path)
    sp = rd.read_splits()
    sp.test_used = True
    rd.write_splits(sp)
    sh = Sh()
    rc, out = _act(monkeypatch, capsys, ["finalize", *_args(rd, project)], sh)
    assert rc == 2 and "already sealed" in out["error"] and not sh.calls


def test_verbs_that_spend_need_a_project(tmp_path, capsys, monkeypatch):
    rd, _, _, val = _run(tmp_path)
    rc, out = _act(monkeypatch, capsys, ["probe", "cand_1", "--tasks", val[0], *_args(rd)], Sh())
    assert rc == 2 and "--project is required" in out["error"]


def test_every_verb_meters_optimizer_spend_first(tmp_path, capsys, monkeypatch):
    rd, project, _, val = _run(tmp_path)
    _session_log(rd, tmp_path, monkeypatch)
    _act(monkeypatch, capsys, ["probe", "cand_1", "--plan", *_args(rd, project)], Sh())
    assert RunDir.open(rd.root).spent.optimizer_usd == pytest.approx(25.0, abs=0.01)


def test_diagnose_v2_persists_clusters_json_for_the_digest(tmp_path):
    import subprocess
    rd, project, _, _ = _run(tmp_path)
    p = subprocess.run([sys.executable, str(REPO / "skills/phases/diagnose/scripts/run.py"), "--run-dir", str(rd.root),
                        "--tag", "cur", "--cluster", "v2"], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    saved = json.loads((rd.root / "clusters.json").read_text())
    assert saved["clusters"] == json.loads(p.stdout)["clusters"]
    assert digest.load_clusters(rd) == saved["clusters"]
