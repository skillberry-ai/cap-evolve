#!/usr/bin/env python3
"""Freeze tau2 retail splits at pin 8ebb749. Official TEST ids are recorded but are the sealed final set."""
import json, hashlib, random, sys
SRC = "/home/dev/projects2/campaign-scratch/bench/src/tau2-8ebb749/data/tau2/domains/retail/"
OUT = "/home/dev/projects2/wt-tau/protocol/tau_retail_splits.json"
def h(ids): return hashlib.sha256(json.dumps(sorted(ids, key=int)).encode()).hexdigest()
def fsha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()
s = json.load(open(SRC + "split_tasks.json"))
train, test, base = sorted(s["train"], key=int), sorted(s["test"], key=int), sorted(s["base"], key=int)
assert not set(train) & set(test)
rng = random.Random(42)
sh = list(train); rng.shuffle(sh)
n_opt = round(len(train) * 2 / 3)
opt, sel = sorted(sh[:n_opt], key=int), sorted(sh[n_opt:], key=int)
assert not set(opt) & set(sel) and set(opt) | set(sel) == set(train) and not (set(opt) | set(sel)) & set(test)
tasks = json.load(open(SRC + "tasks.json"))
nl = {t["id"] for t in tasks if t["evaluation_criteria"].get("nl_assertions")}
out = {"pin": "sierra-research/tau2-bench@8ebb7499622fc2be9b9d510d6f7a7653461f4f29", "domain": "retail",
       "files_sha256": {"split_tasks.json": fsha(SRC + "split_tasks.json"), "tasks.json": fsha(SRC + "tasks.json"), "policy.md": fsha(SRC + "policy.md")},
       "official_counts": {k: len(v) for k, v in s.items()},
       "official_id_list_sha256": {"train": h(train), "test": h(test), "base": h(base)},
       "method": "random.Random(42).shuffle(sorted-int official train); first round(2/3*74)=49 -> opt, rest 25 -> sel",
       "opt": opt, "sel": sel, "sealed_test": test,
       "split_sha256": {"opt": h(opt), "sel": h(sel), "test": h(test)},
       "n": {"opt": len(opt), "sel": len(sel), "test": len(test)},
       "nl_assertion_tasks": {"opt": sorted(nl & set(opt), key=int), "sel": sorted(nl & set(sel), key=int), "test": sorted(nl & set(test), key=int)}}
json.dump(out, open(OUT, "w"), indent=1)
print(json.dumps({k: out[k] for k in ("official_counts", "official_id_list_sha256", "split_sha256", "n")}, indent=1))
print({k: len(v) for k, v in out["nl_assertion_tasks"].items()})
