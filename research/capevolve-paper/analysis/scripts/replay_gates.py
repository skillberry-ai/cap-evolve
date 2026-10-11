"""Zero-cost gate replay on the downloaded historical run artifacts (E07 / E11 / E12 counterpart to sim_*).

    python -I replay_gates.py [--history DIR] [--out DIR]

For every recorded candidate with a recorded parent and per-task val rewards (the dashboard export
``ui/data/runs_*.json``: ``graph.nodes[*].per_task``), replay the accept decision under

  (a) the decision RECORDED by the run (the live rule at that commit: footprint-masked paired k_se
      for hill-climb, the control-based gate for agent-optimize),
  (b) the unmasked paired one-SE gate (``gate.decide`` mode=paired, k_se=1, full delta vector),
  (c) the same gate at k_se 0.2 and 0.3 (the historical hill-climb settings),
  (d) rule P: the screen stage is (b); the fresh-trial confirmation is NOT replayable (no run in the
      artifacts re-measured a candidate and its incumbent on fresh seeds) and is reported as such,
  (e) reward_gated: only its REWARD stage is replayable (``objectives.paired_reward`` with the 0.031
      noise floor, z_accept); its cost conditions need per-trial cost, which the artifacts do not carry.

Provenance of every number: ``source`` = artifact (read from a file), ``computed`` (a deterministic
function of artifact numbers, via the repo's own gate/objectives code), or ``inferred`` (needs an
assumption stated beside it). Nothing is simulated.

What the artifacts cannot give, and the script says so rather than guessing: rollout TRACES (so the
E07 footprint set itself cannot be recomputed; ``rollouts*.json`` exports are empty) and per-candidate
TEST scores (test is sealed once, for the run's final champion only).

Writes replay_gates.json and replay_gates.md under --out.
"""
import argparse
import glob
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve()
CORE = HERE.parents[4] / "core"
sys.path.insert(0, str(CORE))

from cap_evolve import gate as gate_mod  # noqa: E402
from cap_evolve import objectives  # noqa: E402

DEFAULT_HISTORY = Path("/home/dev/projects2/campaign-scratch/artifacts/history")
OUT = HERE.parents[1] / "out"
EPS = 5e-4                       # recorded numbers are rounded to 4 decimals
RULES = ["recorded", "unmasked_k1", "k0.2", "k0.3", "reward_gated_reward_stage"]
_SKIP = ("_file_path_", "_candidate_", "_diff_", "rollouts", "git_log", "memory", "tree", "process_html")


# ---- loading ------------------------------------------------------------------------------------

def _main_json(art: Path):
    for f in sorted(glob.glob(str(art / "ui" / "data" / "runs_*.json"))):
        if any(s in f for s in _SKIP) or f.endswith("/runs.json"):
            continue
        try:
            d = json.load(open(f))
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("summary") and (d.get("graph") or {}).get("nodes"):
            return d
    return None


def load_runs(history: Path):
    runs = []
    for rd in sorted(p for p in history.iterdir() if p.is_dir() and p.name.isdigit()):
        for art in sorted(p for p in rd.iterdir() if p.is_dir()):
            try:
                meta = json.load(open(art / "runmeta.json"))
            except (OSError, ValueError):
                continue
            main = _main_json(art)
            if main is None:
                continue
            metrics = []
            try:
                metrics = [json.loads(l) for l in open(art / "metrics.jsonl") if l.strip()]
            except (OSError, ValueError):
                pass
            runs.append({"run_id": rd.name, "artifact": art.name, "meta": meta, "main": main, "metrics": metrics})
    return runs


# ---- statistics (the repo's own code) -----------------------------------------------------------

def paired_vector(parent_pt: dict, cand_pt: dict):
    """cand - parent over tasks BOTH sides scored (a missing/None task is dropped, as harness._paired_deltas)."""
    ids = sorted(t for t in cand_pt if t in parent_pt and cand_pt[t] is not None and parent_pt[t] is not None)
    return ids, [float(cand_pt[t]) - float(parent_pt[t]) for t in ids]


def paired_gate(deltas, k_se: float) -> dict:
    d = gate_mod.decide(0.0, 0.0, mode="paired", k_se=k_se, paired_deltas=deltas)
    mean, se = gate_mod._paired_mean_se(deltas)
    return {"accept": bool(d.accept), "mean": mean, "se": se, "bar": d.threshold, "n": len(deltas)}


def reward_stage(parent_pt, cand_pt) -> dict:
    """The replayable half of reward_gated: dR, floored SE, z_superior vs z_accept (cost conditions excluded)."""
    mk = lambda pt: [objectives.TrialRec(task=t, k=0, reward=float(r), cost_usd=None)  # noqa: E731
                     for t, r in pt.items() if r is not None]
    cfg = objectives.GateCfg()
    r = objectives.paired_reward(mk(parent_pt), mk(cand_pt), cfg.noise_floor)
    za = objectives.z_accept(cfg)
    z = r["d"] / r["se"] if r["se"] else 0.0
    return {"accept": bool(z > za), "d": r["d"], "se": r["se"], "se_raw": r["se_raw"], "z": z, "z_accept": za,
            "noise_floor": cfg.noise_floor, "n": r["n"], "cost_conditions": "not replayable (no per-trial cost in artifacts)"}


# ---- per-run replay -----------------------------------------------------------------------------

def recorded_gate_rows(summary):
    return {g["candidate"]: g for g in (summary.get("gate_decisions") or []) if g.get("candidate")}


def replay_run(run) -> dict:
    s, g = run["main"]["summary"], run["main"]["graph"]
    nodes = {n["id"]: n for n in g["nodes"]}
    rec = recorded_gate_rows(s)
    algo = s.get("algorithm") or run["meta"].get("algorithm") or "unknown (pre-metadata export)"
    if str(algo).startswith("hill-climb"):
        algo = "hill-climb"
    cands = []
    for cid, n in nodes.items():
        par = n.get("parent")
        if not par or par not in nodes or not n.get("per_task") or not nodes[par].get("per_task"):
            continue
        ids, d = paired_vector(nodes[par]["per_task"], n["per_task"])
        if len(d) < 2:
            continue
        status = n.get("status")
        r = rec.get(cid) or {}
        row = {"candidate": cid, "parent": par, "iteration": n.get("iteration"),
               "recorded_accept": status == "accepted", "recorded_status": status,
               "recorded_gate": {k: r.get(k) for k in ("verdict", "delta", "stderr", "n", "k_se", "gate_mode", "threshold") if k in r},
               "source": {"recorded_*": "artifact", "unmasked/k/reward_*": "computed"}}
        row["unmasked_n"] = len(d)
        row["rules"] = {
            "recorded": {"accept": row["recorded_accept"], "provenance": "artifact"},
            "unmasked_k1": {**paired_gate(d, 1.0), "provenance": "computed"},
            "k0.2": {**paired_gate(d, 0.2), "provenance": "computed"},
            "k0.3": {**paired_gate(d, 0.3), "provenance": "computed"},
            "reward_gated_reward_stage": {**reward_stage(nodes[par]["per_task"], n["per_task"]), "provenance": "computed"},
            "rule_P": {"screen_stage": "= unmasked_k1", "confirmation": "not replayable (no fresh-trial confirmation of candidate and incumbent in the artifacts)"},
        }
        row["delta_vector"] = {"mean": paired_gate(d, 1.0)["mean"], "n_nonzero": sum(1 for x in d if abs(x) > 1e-12),
                               "n_pos": sum(1 for x in d if x > 1e-12), "n_neg": sum(1 for x in d if x < -1e-12),
                               "sum_neg": sum(x for x in d if x < 0), "sum_pos": sum(x for x in d if x > 0)}
        row["masking"] = masking_audit(row, r, algo)
        cands.append(row)
    cands.sort(key=lambda c: (c["iteration"] is None, c["iteration"] or 0))
    for c in cands:
        outs = {k: c["rules"][k]["accept"] for k in RULES}
        c["flips"] = sorted(k for k in RULES if outs[k] != outs["recorded"])
        c["outcomes"] = outs
    return {"run_id": run["run_id"], "artifact": run["artifact"], "bench": run["meta"].get("bench"),
            "tier": run["meta"].get("tier"), "algorithm": algo, "gate_k_se_meta": run["meta"].get("gate_k_se"),
            "n_val": (s.get("splits") or {}).get("val"), "best_id": g.get("best_id"),
            "candidates": cands, "champion_path": champion_path(nodes, g.get("best_id")),
            "test": test_summary(s, run["metrics"])}


def masking_audit(row, r, algo) -> dict:
    """Did the live gate see a footprint-masked vector? Inferred by comparing the RECORDED delta/SE/n with the
    unmasked ones. Only hill-climb records the paired mean the gate used; agent-optimize's recorded gate is
    control-based and not comparable."""
    out = {"applicable": False}
    if algo != "hill-climb" or r.get("delta") is None or r.get("stderr") is None:
        out["why"] = "recorded gate is not the paired mean" if algo != "hill-climb" else "no recorded delta/stderr"
        return out
    um = row["delta_vector"]["mean"]
    se_un = paired_gate_se(row)
    n = r.get("n") or row["unmasked_n"]
    diff = um - r["delta"]
    masked = abs(diff) > EPS or abs(se_un - r["stderr"]) > EPS
    mass = n * diff
    out.update(applicable=True, masked_or_floored_inferred=bool(masked), recorded_delta=r["delta"], recorded_se=r["stderr"],
               unmasked_delta=um, unmasked_se=se_un, n_recorded=n,
               excluded_net_delta_mass=mass if masked else 0.0,
               excluded_tasks_lower_bound=int(math.ceil(abs(mass) - 1e-9)) if masked and abs(mass) > EPS * n else 0,
               inference="Σ over tasks outside the footprint of (cand-parent) = n*(unmasked mean - recorded mean); "
                         "task count is a lower bound assuming |per-task delta| <= 1 (INFERRED; footprint set not recorded)")
    return out


def paired_gate_se(row) -> float:
    return row["rules"]["unmasked_k1"]["se"]


def champion_path(nodes, best_id):
    path, cur = [], best_id
    while cur and cur in nodes and nodes[cur].get("parent"):
        path.append(cur)
        cur = nodes[cur]["parent"]
    return list(reversed(path))


def test_summary(s, metrics):
    out = {"test_reward": s.get("test_reward"), "test_baseline_reward": s.get("test_baseline_reward"),
           "test_delta": s.get("test_delta"), "test_sealed": s.get("test_sealed"), "source": "artifact (summary)"}
    pairs = [(m["reward_baseline"], m["reward_opt"]) for m in metrics
             if m.get("reward_baseline") is not None and m.get("reward_opt") is not None]
    if pairs:
        d = [o - b for b, o in pairs]
        mean, se = gate_mod._paired_mean_se(d) if len(d) >= 2 else (d[0], 0.0)
        out["paired_test"] = {"n_tasks": len(d), "mean_delta": mean, "se": se, "source": "computed from metrics.jsonl"}
        if out["test_delta"] is None:
            # summary lacks the baseline (older exports): fall back to the paired per-task metrics
            out["test_delta"] = mean
            out["test_delta_source"] = "computed from metrics.jsonl (summary has no test_baseline_reward)"
    return out


# ---- aggregation --------------------------------------------------------------------------------

def aggregate(replays):
    agg = {"runs": len(replays), "candidates": 0, "accepts": Counter(), "decided_by_algorithm": defaultdict(Counter),
           "flips": Counter(), "flip_pairs": Counter(), "path": {}, "masking": {}}
    path_tbl = {k: {"survives": [], "fails": []} for k in RULES if k != "recorded"}
    mask = {"hill_climb_decisions": 0, "masked_or_floored": 0, "accepted_masked": 0,
            "accepted_masked_unmasked_would_reject": 0, "net_mass_sum": 0.0, "net_neg_mass_decisions": 0, "net_pos_mass_decisions": 0,
            "tasks_lower_bound_sum": 0, "records": []}
    for r in replays:
        for c in r["candidates"]:
            agg["candidates"] += 1
            for k in RULES:
                agg["accepts"][k] += int(c["outcomes"][k])
            for k in c["flips"]:
                agg["flips"][k] += 1
            agg["decided_by_algorithm"][r["algorithm"]]["candidates"] += 1
            m = c["masking"]
            if m["applicable"]:
                mask["hill_climb_decisions"] += 1
                if m["masked_or_floored_inferred"]:
                    mask["masked_or_floored"] += 1
                    mask["net_mass_sum"] += m["excluded_net_delta_mass"]
                    mask["net_neg_mass_decisions"] += int(m["excluded_net_delta_mass"] < -EPS)
                    mask["net_pos_mass_decisions"] += int(m["excluded_net_delta_mass"] > EPS)
                    mask["tasks_lower_bound_sum"] += m["excluded_tasks_lower_bound"]
                    if c["recorded_accept"]:
                        mask["accepted_masked"] += 1
                        if not c["outcomes"]["unmasked_k1"]:
                            mask["accepted_masked_unmasked_would_reject"] += 1
                    mask["records"].append({"run_id": r["run_id"], "candidate": c["candidate"], "recorded_accept": c["recorded_accept"],
                                            "unmasked_k1_accept": c["outcomes"]["unmasked_k1"], **{k: m[k] for k in (
                                                "recorded_delta", "unmasked_delta", "recorded_se", "unmasked_se",
                                                "excluded_net_delta_mass", "excluded_tasks_lower_bound")},
                                            "n_broke_full_val_recorded": None})
        td = r["test"].get("test_delta")
        by_id = {c["candidate"]: c for c in r["candidates"]}
        for rule in path_tbl:
            steps = [by_id.get(x) for x in r["champion_path"]]
            if not steps or any(s is None for s in steps) or td is None:
                continue
            ok = all(s["outcomes"][rule] for s in steps)
            path_tbl[rule]["survives" if ok else "fails"].append({"run_id": r["run_id"], "algorithm": r["algorithm"],
                                                                  "test_delta": td, "path": r["champion_path"]})
    for rule, v in path_tbl.items():
        def summ(xs):
            ds = [x["test_delta"] for x in xs]
            return {"runs": len(xs), "mean_test_delta": (sum(ds) / len(ds)) if ds else None,
                    "run_ids": [x["run_id"] for x in xs], "test_deltas": [round(x, 4) for x in ds]}
        agg["path"][rule] = {"champion_path_survives": summ(v["survives"]), "champion_path_blocked": summ(v["fails"])}
    agg["masking"] = mask
    agg["accepts"] = dict(agg["accepts"])
    agg["flips"] = dict(agg["flips"])
    agg["decided_by_algorithm"] = {k: dict(v) for k, v in agg["decided_by_algorithm"].items()}
    return agg


# ---- output -------------------------------------------------------------------------------------

def md_table(head, rows):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(map(str, r)) + " |" for r in rows])


def fnum(x, nd=4):
    return "n/a" if x is None else (f"{x:+.{nd}f}" if isinstance(x, float) else str(x))


def render(replays, agg, history) -> str:
    L = ["# replay_gates: historical candidate decisions under alternative acceptance rules", "",
         f"Source: `{history}` (manifest `research/capevolve-paper/audit/artifact_manifest.json`). Script: "
         "`analysis/scripts/replay_gates.py`; every number is read from an artifact or computed from artifact numbers with the "
         "repo's own `gate.decide` / `objectives.paired_reward`. **Inferred** items are marked [INFERRED]. Nothing is simulated.", "",
         "## What is and is not replayable", "",
         "| rule | status |", "|---|---|",
         "| (a) recorded decision | read from the run (node status). hill-climb: footprint-masked paired k_se at the run's setting; agent-optimize: the control-based gate |",
         "| (b) unmasked k_se=1 | replayed from per-task val rewards of candidate and parent |",
         "| (c) k_se 0.2 / 0.3 | replayed |",
         "| (d) rule P | screen stage = (b); **confirmation not replayable**: no artifact re-measures candidate and incumbent on fresh trials |",
         "| (e) reward_gated | **reward stage only** (z vs z_accept=2.734 with the 0.031 SE floor); cost conditions need per-trial cost, absent |",
         "| E07 footprint set | **not recomputable**: rollout traces are not in the artifacts (`rollouts*.json` exports are empty). Masking is inferred from recorded vs unmasked delta/SE |",
         "| per-candidate test | **not available**: test is sealed once, for the run's final champion only |", ""]
    L += ["## Totals", "", f"{agg['runs']} runs, {agg['candidates']} replayable candidate decisions "
          f"(by algorithm: {agg['decided_by_algorithm']}).", "",
          md_table(["rule", "accepts", "decisions that differ from the recorded one"],
                   [[k, agg["accepts"][k], agg["flips"].get(k, 0) if k != "recorded" else "-"] for k in RULES]), ""]
    L += ["Runs are replicates on the same benchmark/seed split with the same optimizer family, and several share identical "
          "baselines and candidate trajectories; they are NOT independent samples. Pre-metadata exports have no algorithm field "
          "and no recorded k_se.", ""]
    L += ["## Recorded accepts that another rule would reject", ""]
    rows = []
    for r in replays:
        for c in r["candidates"]:
            if c["recorded_accept"]:
                lost = [k for k in RULES if k != "recorded" and not c["outcomes"][k]]
                if lost:
                    rows.append([r["run_id"], r["algorithm"], c["candidate"], c["candidate"] in r["champion_path"],
                                 fnum(c["delta_vector"]["mean"]), ",".join(lost), fnum(r["test"].get("test_delta")) if c["candidate"] in r["champion_path"] else "not measured (never sealed)"])
    L += [md_table(["run", "algorithm", "candidate", "on champion path", "unmasked delta", "rules that reject it", "run test delta (champion path only)"], rows), ""]
    L += ["## Does a flip predict test gain or loss?", "",
          "Only each run's FINAL champion is measured on test (vs the seed on the same test tasks). For a rule, the champion's ancestry "
          "(seed -> ... -> champion) either passes every step under that rule (the run would have reached the same champion; "
          "[INFERRED] assuming the optimizer proposes the same candidates) or is blocked at some step. Runs pooled; runs are not independent "
          "(shared seed/benchmark/optimizer), so this is descriptive.", ""]
    rows = []
    for rule, v in agg["path"].items():
        s, b = v["champion_path_survives"], v["champion_path_blocked"]
        rows.append([rule, s["runs"], fnum(s["mean_test_delta"]), b["runs"], fnum(b["mean_test_delta"]), b["test_deltas"]])
    L += [md_table(["rule", "path survives: runs", "mean test delta", "path blocked: runs", "mean test delta", "test deltas of blocked runs"], rows), ""]
    L += ["A blocked run whose champion nevertheless gained on test is a gain the stricter rule would have forfeited; a blocked run with "
          "test delta <= 0 is a loss it would have avoided.", ""]
    m = agg["masking"]
    L += ["## E07 footprint false-exclusion audit (hill-climb)", "",
          f"Decisions with a recorded paired delta/SE: {m['hill_climb_decisions']}. In {m['masked_or_floored']} the recorded delta or SE differs from "
          "the unmasked one by more than rounding: the live gate saw a footprint-masked and/or SE-floored vector [INFERRED from the mismatch].", "",
          f"- accepted while masked: {m['accepted_masked']}; of these the unmasked k_se=1 gate would reject: **{m['accepted_masked_unmasked_would_reject']}**",
          f"- masked decisions whose excluded tasks carried net NEGATIVE delta (masking hid regressions): {m['net_neg_mass_decisions']}; net positive: {m['net_pos_mass_decisions']}",
          f"- sum of excluded net delta mass (task-delta units, + = gain hidden): {m['net_mass_sum']:+.3f} [INFERRED = n*(unmasked mean - recorded mean)]",
          f"- lower bound on excluded tasks with nonzero delta, summed over decisions: {m['tasks_lower_bound_sum']} [INFERRED, assumes |delta| <= 1 per task]", ""]
    if m["records"]:
        L += [md_table(["run", "candidate", "recorded accept", "unmasked k1 accept", "recorded delta", "unmasked delta", "recorded SE", "unmasked SE", "excluded net mass", ">= tasks"],
                       [[x["run_id"], x["candidate"], x["recorded_accept"], x["unmasked_k1_accept"], fnum(x["recorded_delta"]), fnum(x["unmasked_delta"]),
                         f"{x['recorded_se']:.4f}", f"{x['unmasked_se']:.4f}", fnum(x["excluded_net_delta_mass"], 3), x["excluded_tasks_lower_bound"]]
                        for x in m["records"]]), ""]
    else:
        L += ["No decision shows evidence of masking in these artifacts.", ""]
    L += ["## Per run", ""]
    for r in replays:
        t = r["test"]
        L += [f"### {r['run_id']} {r['bench']}/{r['tier']} {r['algorithm']} (meta k_se {r['gate_k_se_meta']}, val n {r['n_val']})", "",
              f"Champion `{r['best_id']}` path {r['champion_path']}; test {fnum(t.get('test_reward'))} vs baseline {fnum(t.get('test_baseline_reward'))} "
              f"(delta {fnum(t.get('test_delta'))}" + (f", paired over {t['paired_test']['n_tasks']} tasks SE {t['paired_test']['se']:.4f})" if t.get("paired_test") else ")"), ""]
        rows = []
        for c in r["candidates"]:
            o = c["outcomes"]
            yn = lambda b: "acc" if b else "rej"  # noqa: E731
            rows.append([c["candidate"], c["parent"], fnum(c["delta_vector"]["mean"]), f"{c['rules']['unmasked_k1']['se']:.4f}",
                         yn(o["recorded"]), yn(o["unmasked_k1"]), yn(o["k0.2"]), yn(o["k0.3"]), yn(o["reward_gated_reward_stage"]),
                         ",".join(c["flips"]) or "-"])
        L += [md_table(["candidate", "parent", "unmasked delta", "unmasked SE", "recorded", "k=1 unmasked", "k=0.2", "k=0.3", "reward_gated (reward stage)", "flips vs recorded"], rows), ""]
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--history", default=str(DEFAULT_HISTORY))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    runs = load_runs(Path(a.history))
    replays = [replay_run(r) for r in runs]
    replays = [r for r in replays if r["candidates"]]
    agg = aggregate(replays)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    payload = {"history": a.history, "rules": RULES, "aggregate": agg, "runs": replays,
               "not_replayable": ["rule_P confirmation", "reward_gated cost conditions", "E07 footprint set (no traces)", "per-candidate test"]}
    (out / "replay_gates.json").write_text(json.dumps(payload, indent=1, default=str), encoding="utf-8")
    (out / "replay_gates.md").write_text(render(replays, agg, a.history), encoding="utf-8")
    print(f"{agg['runs']} runs, {agg['candidates']} decisions -> {out}/replay_gates.{{json,md}}")


if __name__ == "__main__":
    main()
