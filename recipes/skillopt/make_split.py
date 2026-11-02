#!/usr/bin/env python3
"""Build the SkillOpt split_dir for one exp895 search (issue #895 §3, §7.3), with the test-id guard.

train = official train 80, val = official val 40 (SkillOpt's own selection gate), test = a 1-item STUB that is a
TRAIN id (eval_test=false, so it is never rolled out; the loader only needs the directory to exist). No test id
is ever written. With --ids FILE (smoke only) train = val = those ids.

Items come from SkillOpt's own data/spreadsheetbench_id_split/{train,val}/items.json (its test/ file is never
opened). The official split_ids.json is loaded only to assert that nothing we wrote is a test id; on a failure
it prints a COUNT, never an id.

Usage: make_split.py <out_dir> <official split_ids.json> <skillopt repo> [--ids FILE]
"""
import json
import sys
from pathlib import Path

out, official, repo = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
ids_file = sys.argv[sys.argv.index("--ids") + 1] if "--ids" in sys.argv else None
src = repo / "data" / "spreadsheetbench_id_split"
items = {n: json.loads((src / n / "items.json").read_text()) for n in ("train", "val")}
by_id = {str(i["id"]): i for n in items for i in items[n]}
off = json.loads(official.read_text())
for n in ("train", "val"):
    assert sorted(str(i["id"]) for i in items[n]) == sorted(map(str, off[n])), f"SkillOpt {n} != official {n}"
if ids_file:
    ids = [ln.strip() for ln in open(ids_file) if ln.strip()]
    split = {"train": [by_id[i] for i in ids], "val": [by_id[i] for i in ids]}
else:
    split = {"train": items["train"], "val": items["val"]}
split["test"] = [split["train"][0]]
written = {str(i["id"]) for n in split for i in split[n]}
leak = len(written & set(map(str, off["test"])))
assert leak == 0, f"{leak} TEST id(s) would be written into the SkillOpt split; refusing"
for n, v in split.items():
    (out / n).mkdir(parents=True, exist_ok=True)
    (out / n / "items.json").write_text(json.dumps(v, indent=1))
(out / "split_manifest.json").write_text(json.dumps({
    "source": str(src), "smoke_ids_file": ids_file, "counts": {n: len(v) for n, v in split.items()},
    "test_is_stub": True, "test_stub_is_train_id": True, "test_ids_written": 0}, indent=1))
print("split ok:", {n: len(v) for n, v in split.items()}, "test ids written: 0")
