#!/usr/bin/env python3
"""Write `full_verified/split_ids.json` from SkillOpt's RELEASED SpreadsheetBench split.

WikiSkill (arXiv 2608.27454v1, Appendix B) states its splits "are strictly matched with prior work
(Yang et al., 2026 [SkillOpt])", and SkillOpt publishes that split as id manifests in
microsoft/SkillOpt (MIT) under data/spreadsheetbench_id_split/{train,val,test}/items.json, built
from HF KAKA22/SpreadsheetBench `spreadsheetbench_verified_400.tar.gz`. Using it puts our
`full_verified` numbers on the same 80/40/280 partition as both papers, instead of our own
seed-42 2:1:7 reconstruction (kept as split_ids.capevolve_seed42.json for the runs that used it).

Pinned to one SkillOpt commit so the file cannot drift; `split_source.json` records the pin and a
digest of each split so tests can check the committed ids without network access.

    python3 ci/benchmarks/spreadsheetbench/utils/make_skillopt_split.py           # print
    python3 ci/benchmarks/spreadsheetbench/utils/make_skillopt_split.py --write   # write
"""
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

REPO = "microsoft/SkillOpt"
COMMIT = "79124b37e9a6371e13b753f8bcd7adb1e493ade1"
BASE = "data/spreadsheetbench_id_split"
TIER = Path(__file__).resolve().parent.parent / "full_verified"


def digest(ids: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()


def _fetch(path: str):
    url = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/{path}"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def build() -> tuple[dict, dict]:
    manifest = _fetch(f"{BASE}/split_manifest.json")
    split = {s: sorted(str(it["id"]) for it in _fetch(f"{BASE}/{s}/items.json"))
             for s in ("train", "val", "test")}
    source = {
        "source": f"https://github.com/{REPO}/tree/{COMMIT}/{BASE}",
        "repo": REPO, "commit": COMMIT, "license": "MIT",
        "dataset_source": manifest.get("source_url"),
        "dataset_file": manifest.get("source_file"),
        "dataset_revision": manifest.get("source_revision"),
        "counts": {s: len(v) for s, v in split.items()},
        "sha256_sorted_ids": {s: digest(v) for s, v in split.items()},
    }
    return split, source


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    split, source = build()
    payload = json.dumps(split, indent=2, sort_keys=True) + "\n"
    if args.write:
        (TIER / "split_ids.json").write_text(payload, encoding="utf-8")
        (TIER / "split_source.json").write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")
    else:
        print(payload, end="")


if __name__ == "__main__":
    main()
