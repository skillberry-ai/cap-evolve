"""Write cap-evolve's split_ids.json from the official AppWorld splits (rule S2: train = val = train ∪ dev).

Refuses to run unless the four official split files have the expected counts (rule S1), and records
their sha256 in runs/manifest.json.

Usage: python make_splits.py OUT_JSON
"""

from __future__ import annotations

import json
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from awpaths import EXPECTED_COUNTS, ROOT_FULL, SPLITS, read_split, sha256_file, update_manifest  # noqa: E402


def main(argv: list[str]) -> int:
    out = argv[1] if len(argv) > 1 else "split_ids.json"
    ids = {s: read_split(s) for s in SPLITS}
    counts = {s: len(v) for s, v in ids.items()}
    if counts != EXPECTED_COUNTS:
        print(f"split counts {counts} != {EXPECTED_COUNTS}", file=sys.stderr)
        return 1
    sets = {s: set(v) for s, v in ids.items()}
    for i, a in enumerate(SPLITS):
        for b in SPLITS[i + 1:]:
            if sets[a] & sets[b]:
                print(f"official splits {a} and {b} overlap", file=sys.stderr)
                return 1
    union = ids["train"] + ids["dev"]
    with open(out, "w") as f:
        json.dump({"train": union, "val": union, "test": []}, f, indent=1)
    update_manifest(split_files={s: {"count": counts[s],
                                     "sha256": sha256_file(ROOT_FULL / "data" / "datasets" / f"{s}.txt")}
                                 for s in SPLITS})
    print(f"wrote {out}: train = val = {len(union)} (train ∪ dev), test = 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
