#!/usr/bin/env python3
"""v2 scoring window (amendment 11F): ONE interleaved randomized window per suite with the v2 champions (hc2, ao2), the v1 GEPA champions
(the 11G comparator) and the seed artifact re-scored INSIDE the window.  Same adapters / scorer / worker / run_final.py as the v1 windows.

  python3 -I v2_window.py build --suite D --champions champions_V2_D.json

champions_V2_<S>.json (written by the search owner at freeze):  {"hc2": {"0": "<artifact dir>", "1": ..., "2": ...}, "ao2": {...}}
  each artifact dir is the champion (final state of the search) in the suite's artifact layout (A: prompt/skill capability; D, E: policy/ + tools/).
Steps: freeze (read-only copy + tree hash) of every v2 champion under final_eval/V2/<S>/artifacts/B/<arm>/s<k>; manifest manifests/artifacts_V2_<S>.json (v2 entries +
the v1 GEPA entries and the seed artifact copied from manifests/artifacts_<S>.json); order via order.py (arms hc2, ao2, gepa, + seed and seed-check cells, tags
FINAL-<S>-V2-..., held-out set only: A T = 70, D test-40, E test-20, no sel cells) hashed to manifests/order_V2_<S>.jsonl(.sha256).
Run it with:  run_final.py run --suite <S> --order manifests/order_V2_<S>.jsonl --root <FINAL_EVAL_ROOT>/V2/<S> --workers N
Trials follow order.DEFAULT_TRIALS (11H: A n = 1 per arm / 2 seed; D and E n = 5 per arm / 10 seed).
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fe_common as C  # noqa: E402
import order as O  # noqa: E402
import reconstruct as R  # noqa: E402

V2_ARMS = ("hc2", "ao2")
V1_COMPARATOR = "gepa"          # 11G: the one competitor run on every suite (A E10 gepa, D E20-GEPA, E E30-GEPA)


def build(suite, champions_path, out_root, manifests=None, dry=False):
    manifests = Path(manifests or C.MANIFESTS)
    champ = json.load(open(champions_path))
    v1 = json.load(open(manifests / ("artifacts_%s.json" % suite)))
    kind = C.SUITES[suite]["artifact_kind"]
    seed_art = v1["seed_artifact"]
    entries = []
    for arm in V2_ARMS:
        for seed in range(3):
            src = (champ.get(arm) or {}).get(str(seed))
            if not src:
                sys.exit("champions file has no %s seed %d" % (arm, seed))
            dst = Path(out_root) / "artifacts" / "B" / arm / ("s%d" % seed)
            if not dst.exists():
                R.freeze_copy(Path(src), dst, kind)
            (th, files), nh = C.tree_hash(dst, kind), C.tree_hash_normalized(dst, kind)
            nh = nh[0] if isinstance(nh, (tuple, list)) else nh
            entries.append({"suite": suite, "mode": "B", "arm": arm, "seed": seed, "status": "ok", "source_dir": str(src), "frozen_dir": str(dst),
                            "tree_sha256": th, "files": files, "normalized_tree_sha256": nh, "identical_to_seed": th == seed_art["tree_sha256"],
                            "identical_to_seed_normalized": nh == seed_art.get("normalized_tree_sha256"), "inert": nh == seed_art.get("normalized_tree_sha256"),
                            "dagger": False, "caveats": ["v2 champion = final state of the search (amendment 11)"]})
    gep = [e for e in v1["entries"] if e["mode"] == "B" and e["arm"] == V1_COMPARATOR]
    if len(gep) != 3:
        sys.exit("v1 manifest has %d %s entries (need 3)" % (len(gep), V1_COMPARATOR))
    man = {"suite": suite, "window": "v2", "bstar": "v2-final-state", "entries": entries + gep, "seed_artifact": seed_art,
           "v1_manifest": str(manifests / ("artifacts_%s.json" % suite)), "v1_manifest_sha256": C.file_sha(manifests / ("artifacts_%s.json" % suite)),
           "champions_file": str(champions_path), "champions_file_sha256": C.file_sha(champions_path), "generated_utc": C.now_utc()}
    mpath = manifests / ("artifacts_V2_%s.json" % suite)
    if not dry:
        C.write_json_atomic(mpath, man)
    return man, mpath


def make_order(suite, mpath, out=None, tag_exp=None):
    out = Path(out or (Path(mpath).parent / ("order_V2_%s.jsonl" % suite)))
    argv = ["--suite", suite, "--manifest", str(mpath), "--tasks", "final", "--arms", ",".join(V2_ARMS + (V1_COMPARATOR,)), "--no-end",
            "--tag-exp", tag_exp or ("FINAL-%s-V2" % suite), "--out", str(out)]
    if O.main(argv):
        sys.exit("order.py failed")
    # held-out set only: drop the sel cells (D H65 / E H30 contain the selection split; 11C names test-40 / test-20 as the v2 held-out sets)
    rows = [json.loads(l) for l in open(out)]
    meta, jobs = rows[0], [r for r in rows[1:] if r.get("type") == "job"]
    if suite in ("D", "E"):
        jobs = [j for j in jobs if j.get("split") != "sel"]
        meta["tasks"] = [t for t in meta["tasks"] if any(j["task"] == t for j in jobs)]
    for i, j in enumerate(jobs):
        j["idx"] = i
    meta.update(n_jobs=len(jobs), window="v2", counts_by_arm={})
    for j in jobs:
        k = "%s/s%d" % (j["arm_label"], j["seed"])
        meta["counts_by_arm"][k] = meta["counts_by_arm"].get(k, 0) + 1
    with open(out, "w") as f:
        f.write(json.dumps(meta, sort_keys=True) + "\n")
        for j in jobs:
            f.write(json.dumps(j, sort_keys=True) + "\n")
    sha = C.sha256_file(out)
    out.with_suffix(".sha256").write_text("%s  %s\n" % (sha, out.name))
    return out, sha, meta


def comparison_family_v2(suite):
    """11G: Holm m = 4 within suite, paired, task = cluster: HC-2 vs seed, AO-2 vs seed, HC-2 vs v1 GEPA, AO-2 vs v1 GEPA (all against in-window anchors)."""
    return {"suite": suite, "window": "v2", "holm_denominator_primary": 4,
            "primary_11G": [{"arm": "hc2", "vs": "seed"}, {"arm": "ao2", "vs": "seed"}, {"arm": "hc2", "vs": "gepa"}, {"arm": "ao2", "vs": "gepa"}],
            "descriptive_only": [{"arm": "hc2", "vs": "ao2"}, {"arm": "hc2|ao2", "vs": "best v1 competitor (data-dependent)"}, {"arm": "hc2|ao2", "vs": "v1 stock-gate hc / rule-P hc"}],
            "anchors": "seed (A n=2, D/E n=10) and v1 GEPA champions re-scored inside this window; v1-window numbers are shown beside, never pooled (11F)"}


def register(suite, manifests=None, registry=None, note=""):
    """Append the v2 window's hashes to experiments/registry.jsonl BEFORE the first rollout (run git fetch + merge first: the registry is shared)."""
    import hashlib
    import freeze as F
    manifests = Path(manifests or C.MANIFESTS)
    reg = F.Registry(registry or F.REGISTRY)
    fam = manifests / ("comparison_family_V2_%s.json" % suite)
    C.write_json_atomic(fam, comparison_family_v2(suite))
    man = json.load(open(manifests / ("artifacts_V2_%s.json" % suite)))
    h = hashlib.sha256()
    for e in sorted(man["entries"], key=lambda e: (e["mode"], e["arm"], e["seed"])):
        h.update(("%s|%s|%d|%s\n" % (e["mode"], e["arm"], e["seed"], e.get("tree_sha256"))).encode())
    items = [("v2window_champions_file_%s" % suite, C.file_sha(man["champions_file"]), man["champions_file"], "v2 champions (final state of the searches)"),
             ("v2window_artifact_manifest_%s" % suite, C.file_sha(manifests / ("artifacts_V2_%s.json" % suite)), manifests / ("artifacts_V2_%s.json" % suite), "v2 champions + v1 GEPA + seed"),
             ("v2window_artifact_tree_hashes_%s" % suite, h.hexdigest(), manifests / ("artifacts_V2_%s.json" % suite), "sha over (mode|arm|seed|tree hash); seed %s" % man["seed_artifact"]["tree_sha256"]),
             ("v2window_order_%s" % suite, C.file_sha(manifests / ("order_V2_%s.jsonl" % suite)), manifests / ("order_V2_%s.jsonl" % suite), "interleaved randomized v2 window, held-out set only"),
             ("v2window_comparison_family_%s" % suite, C.file_sha(fam), fam, "11G Holm m=4"),
             ("v2window_script_v2_window_py", C.file_sha(__file__), __file__, ""), ("v2window_script_order_py", C.file_sha(C.HERE / "order.py"), C.HERE / "order.py", ""),
             ("v2window_script_run_final_py", C.file_sha(C.HERE / "run_final.py"), C.HERE / "run_final.py", ""), ("v2window_script_fe_common_py", C.file_sha(C.HERE / "fe_common.py"), C.HERE / "fe_common.py", ""),
             ("v2window_script_commit", hashlib.sha256((C.git_head() or "").encode()).hexdigest(), C.REPO, C.git_head())]
    n = sum(1 for name, sha, p, nt in items if reg.add(name, sha, p, ((note + " | ") if note else "") + nt, suites=[suite]))
    reg.write()
    print("registered %d new v2 window items (%d lines)" % (n, len(reg.lines)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "register"])
    ap.add_argument("--suite", required=True, choices=["A", "D", "E"])
    ap.add_argument("--champions", default=None)
    ap.add_argument("--note", default="")
    ap.add_argument("--root", default=None, help="default FINAL_EVAL_ROOT/V2/<suite>")
    ap.add_argument("--manifests", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    if a.cmd == "register":
        register(a.suite, a.manifests, None, a.note)
        sys.exit(0)
    if not a.champions:
        sys.exit("--champions required for build")
    root = a.root or str(C.final_dir(a.suite).parent / "V2" / a.suite)
    man, mpath = build(a.suite, a.champions, root, a.manifests)
    out, sha, meta = make_order(a.suite, mpath, a.out)
    print("v2 window %s: manifest %s; order %s: %d jobs, %d tasks, sha256 %s" % (a.suite, mpath, out, meta["n_jobs"], len(meta["tasks"]), sha))
    print("counts by arm:", {k: v for k, v in sorted(meta["counts_by_arm"].items())})
