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
    kind = "sb_files_v2" if suite == "A" else C.SUITES[suite]["artifact_kind"]     # A: + skills/** (helpers carrier)
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


V2_CODE_ROOT = "/home/dev/projects2/wt-v2run"        # main at a3f5eeb6d (amendment 11 erratum 1): adapter, core, helpers carrier, gold isolation, iopub idle-wait fix
V2_TAU_ADAPTERS = {"D": "/home/dev/projects2/campaign-scratch/scripts/V2/adapters/retail/adapter.py", "E": "/home/dev/projects2/campaign-scratch/scripts/V2/adapters/airline/adapter.py"}
V2_CODE_SHA = "a3f5eeb6d54d9782c9fb3985ca1d63560f6cc4bb"


def build_harness_dir(code_root, dst):
    """v2 Suite A sandbox harness = main's vendored third_party/spreadsheetbench with api.py replaced by the campaign-patched api.py (idle-kernel timeout 10800 s, sha256 from
    manifests/expected_api_sha256.txt, the one the v1 window used); jupyter.py stays main's vendored file (the adapter patches its staged copy)."""
    import shutil
    dst = Path(dst)
    if not dst.exists():
        shutil.copytree(Path(code_root) / "third_party/spreadsheetbench", dst)
        shutil.copy2(C.REPO / "third_party/spreadsheetbench/code_exec_docker/api.py", dst / "code_exec_docker/api.py")
    want = (C.HERE / "manifests/expected_api_sha256.txt").read_text().split()[0]
    if C.file_sha(dst / "code_exec_docker/api.py") != want:
        sys.exit("harness api.py sha256 != %s" % want)
    return str(dst)


def apply_a_overrides(jobs, meta, code_root, harness_dir):
    """Every Suite A cell of the v2 window (v2 champions AND the in-window anchors) is scored by the v2 code path: main's adapter at a registered SHA with the helpers carrier."""
    code_root = str(code_root)
    sha = C.git_head(Path(code_root))
    jup = C.file_sha(Path(harness_dir) / "code_exec_docker/jupyter.py")
    for j in jobs:
        j.update(code_root=code_root, code_root_sha=sha, harness_dir=str(harness_dir), harness_jupyter_sha256=jup, artifact_kind="sb_files_v2",
                 adapter_path=str(Path(code_root) / "templates/adapters/spreadsheetbench/adapter.py"))
        j["env"] = dict(j.get("env") or {}, CAPEVOLVE_HELPERS="1")
    meta["scorer"] = {"window": "v2", "code_root": code_root, "code_root_sha": sha, "harness_dir": str(harness_dir), "harness_jupyter_sha256": jup,
                      "adapter_sha256": C.file_sha(Path(code_root) / "templates/adapters/spreadsheetbench/adapter.py"), "env": {"CAPEVOLVE_HELPERS": "1"},
                      "note": "v2 and the in-window anchors share this scorer (11F); the v1 window used bench/patches/new/adapter.py without a helpers carrier"}


def make_order(suite, mpath, out=None, tag_exp=None, code_root=None, harness_dir=None):
    out = Path(out or (Path(mpath).parent / ("order_V2_%s.jsonl" % suite)))
    code_root = code_root or V2_CODE_ROOT
    argv = ["--suite", suite, "--manifest", str(mpath), "--tasks", "final", "--arms", ",".join(V2_ARMS + (V1_COMPARATOR,)), "--no-end",
            "--tag-exp", tag_exp or ("FINAL-%s-V2" % suite), "--out", str(out)]
    if suite == "A":
        argv += ["--adapter-path", str(Path(code_root) / "templates/adapters/spreadsheetbench/adapter.py")]
    if O.main(argv):
        sys.exit("order.py failed")
    # held-out set only: drop the sel cells (D H65 / E H30 contain the selection split; 11C names test-40 / test-20 as the v2 held-out sets)
    rows = [json.loads(l) for l in open(out)]
    meta, jobs = rows[0], [r for r in rows[1:] if r.get("type") == "job"]
    man = json.load(open(mpath))
    # erratum 11 (3): an inert v2 champion (tree hash equal to the seed's) is flagged and mapped to the seed-check cell, primary delta 0; no separate rescoring cell
    inert = sorted((e["arm"], e["seed"]) for e in man["entries"] if e["arm"] in V2_ARMS and e.get("identical_to_seed"))
    if inert:
        jobs = [j for j in jobs if (j["arm"], j["seed"]) not in inert]
    meta["inert_mapped_to_seed_check"] = [{"arm": a_, "seed": s_} for a_, s_ in inert]
    if suite == "A":
        apply_a_overrides(jobs + meta.get("canary_jobs", []), meta, code_root, harness_dir)
    else:       # D / E: the V2 adapter copy (v1 file + read-only reference/ guard) for every cell, anchors included
        adp = V2_TAU_ADAPTERS[suite]
        for j in jobs + meta.get("canary_jobs", []):
            j["adapter_py"] = adp
        meta["scorer"] = {"window": "v2", "adapter_py": adp, "adapter_sha256": C.file_sha(adp),
                          "note": "v2 and the in-window anchors share the V2 adapter copy (11F); the v1 window used the frozen v1 adapter (no reference/ guard)"}
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
    meta = json.loads(open(manifests / ("order_V2_%s.jsonl" % suite)).readline())
    sc = meta.get("scorer") or {}
    if sc:
        items.append(("v2window_scorer_%s" % suite, hashlib.sha256(json.dumps(sc, sort_keys=True).encode()).hexdigest(), manifests / ("order_V2_%s.jsonl" % suite),
                      "scorer of the v2 window (v1 window used a different adapter): " + json.dumps(sc, sort_keys=True)[:600]))
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
    hd = build_harness_dir(V2_CODE_ROOT, Path(root) / "harness") if a.suite == "A" else None
    out, sha, meta = make_order(a.suite, mpath, a.out, harness_dir=hd)
    print("v2 window %s: manifest %s; order %s: %d jobs, %d tasks, sha256 %s" % (a.suite, mpath, out, meta["n_jobs"], len(meta["tasks"]), sha))
    print("counts by arm:", {k: v for k, v in sorted(meta["counts_by_arm"].items())})
