#!/usr/bin/env python3
"""decompose.py: E25 artifact decomposition (deterministic, no model).  For each champion that differs from the seed on BOTH surfaces:
    P-only = champion policy/ + seed tools/        T-only = seed policy/ + champion tools/
A sub-artifact whose content hash equals the seed or the champion is skipped.  Sub-artifacts are frozen read-only copies with hashes;
the manifest feeds `order.py --extra decomp --decomp-manifest ...` (cells: sub-artifact x final tasks x n=3 on Suite D, n=1 on B/C).

    decompose.py --suite D --manifest manifests/artifacts_D.json [--arms pt,rulep,1s,ctl] [--out-root DIR]
Suite B/C: pass --arms oneshot[,hcstock] (one-shot and stock-gate champions only; scheduled last, dropped first if the window is tight)."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fe_common as C  # noqa: E402
from reconstruct import freeze_copy  # noqa: E402


def rm_force(p):
    p = Path(p)
    if p.exists():
        for q in [p] + list(p.rglob("*")):
            try:
                q.chmod(0o755 if q.is_dir() else 0o644)
            except Exception:
                pass
        shutil.rmtree(p)


def surface_hashes(root):
    out = {}
    for sub in ("policy", "tools"):
        h = {f: C.sha256_file(Path(root) / f) for f in C.tree_files(root, "tau_cap") if f.startswith(sub + "/")}
        out[sub] = h
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", required=True, choices=["B", "C", "D"])
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--arms", default=None)
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--mode", default="B")
    a = ap.parse_args(argv)
    suite = a.suite
    man = C.jload(a.manifest)
    out_root = Path(a.out_root) if a.out_root else C.final_dir(suite)
    seed = man["seed_artifact"]
    seed_dir = Path(seed["frozen_dir"])
    seed_h = surface_hashes(seed_dir)
    want = a.arms.split(",") if a.arms else (C.SUITES[suite]["main"] if suite == "D" else ["oneshot"])
    entries, skipped = [], []
    for e in man["entries"]:
        if e["mode"] != a.mode or e["arm"] not in want or e["status"] == "impossible" or not e.get("frozen_dir"):
            continue
        champ = Path(e["frozen_dir"])
        ch = surface_hashes(champ)
        edits_p, edits_t = ch["policy"] != seed_h["policy"], ch["tools"] != seed_h["tools"]
        if not (edits_p and edits_t):
            skipped.append({"arm": e["arm"], "seed": e["seed"], "reason": "champion differs from the seed on %s only" % ("policy" if edits_p else ("tools" if edits_t else "no surface"))})
            continue
        for tag, keep_from_champ, keep_from_seed in (("P", "policy", "tools"), ("T", "tools", "policy")):
            tmp = out_root / "artifacts" / "decomp_tmp" / ("%s-%s-s%d" % (e["arm"], tag, e["seed"]))
            rm_force(tmp)
            for sub, src in ((keep_from_champ, champ), (keep_from_seed, seed_dir)):
                if (src / sub).is_dir():
                    shutil.copytree(src / sub, tmp / sub)
            rm_force(tmp / "__none__")
            for q in [tmp] + list(tmp.rglob("*")):
                q.chmod(0o755 if q.is_dir() else 0o644)
            h, files = C.tree_hash(tmp, "tau_cap")
            if h in (seed["tree_sha256"], e["tree_sha256"]):
                skipped.append({"arm": e["arm"], "seed": e["seed"], "reason": "%s-only equals the %s" % (tag, "seed" if h == seed["tree_sha256"] else "champion")})
                rm_force(tmp)
                continue
            dst = out_root / "artifacts" / "decomp" / e["arm"] / ("%s-s%d" % (tag, e["seed"]))
            freeze_copy(tmp, dst, "tau_cap")
            rm_force(tmp)
            entries.append({"arm": e["arm"], "arm_label": "%s-%sonly" % (e["arm"], tag), "seed": e["seed"], "part": tag, "parent_tree_sha256": e["tree_sha256"],
                            "seed_tree_sha256": seed["tree_sha256"], "tree_sha256": h, "files": files, "frozen_dir": str(dst), "candidate_id": e.get("candidate_id")})
    doc = {"suite": suite, "generated_utc": C.now_utc(), "source_manifest": a.manifest, "source_manifest_sha256": C.file_sha(a.manifest),
           "decompose_py_sha256": C.file_sha(__file__), "arms": want, "entries": entries, "skipped": skipped}
    path = Path(a.out) if a.out else C.MANIFESTS / ("decomp_%s.json" % suite)
    C.write_json_atomic(path, doc)
    print("decomposed %d sub-artifacts from %d champions' entries (skipped %d) -> %s" % (len(entries), len(want), len(skipped), path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
