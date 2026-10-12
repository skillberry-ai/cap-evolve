#!/usr/bin/env python3
"""Pinned downloads, decontamination check and frozen splits for the SWE-bench Verified design.

  python3 -I swebench_splits.py --cache /data/swebench_cache --out ./splits

Needs only `pyarrow` (pip install pyarrow). Every parquet file is downloaded from a pinned
Hugging Face revision and verified against the sha256 recorded below; a mismatch aborts.
Outputs (all deterministic, safe to re-run, hashes printed at the end):
  decontam_report.json   repo-level, instance-level and time-window overlap tables
  gym_splits.json        SWE-Gym pools OPT-100 / SEL-60 / REH-100 / PIL-40 + per-repo reserve queues
  dev_splits.json        SWE-bench dev: DEV-225 (all) and DEV-PIL-60 (pilot subset)
  id_hashes.json         sha256 of "\n".join(sorted(instance_ids)) for every source split
The Verified instance ids are read only to run the decontamination check and to be excluded;
no Verified text, patch or test field is ever read.
"""
import argparse, collections, hashlib, json, os, random, sys, urllib.request

SOURCES = {
    # name: (hf repo, revision, path, sha256 of the file)
    "verified": ("princeton-nlp/SWE-bench_Verified", "c104f840cc67f8b6eec6f759ebc8b2693d585d4a",
                 "data/test-00000-of-00001.parquet",
                 "a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd"),
    "dev": ("princeton-nlp/SWE-bench", "e48e2bd1e9fecd5bbd641e9414ac59da9f2e69f6",
            "data/dev-00000-of-00001.parquet",
            "d758d54540aa4140d0274ed0cc93b8288aa6f323c3c603e2557e7666a47fc41b"),
    "train": ("princeton-nlp/SWE-bench", "e48e2bd1e9fecd5bbd641e9414ac59da9f2e69f6",
              "data/train-00000-of-00001.parquet",
              "0ba403a7060af657e1f0476937a703726c07da15b759836694b16e553705a10f"),
    "swegym": ("SWE-Gym/SWE-Gym", "bb94ed9e39bbeb96a7fcbfb533b80f25a7fd59cb",
               "data/train-00000-of-00001.parquet",
               "60569cea74bb281f7a5579467436a2bc1932c6e0c5f2f7fa0d084392abd9ad97"),
}
SEED = 20261012
POOL_ORDER = [("OPT-100", 100), ("SEL-60", 60), ("REH-100", 100), ("PIL-40", 40)]
DEV_PILOT = 60


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def fetch(cache, name):
    repo, rev, path, want = SOURCES[name]
    dest = os.path.join(cache, f"{name}.parquet")
    if not os.path.exists(dest):
        os.makedirs(cache, exist_ok=True)
        url = f"https://huggingface.co/datasets/{repo}/resolve/{rev}/{path}"
        urllib.request.urlretrieve(url, dest)
    got = sha256_file(dest)
    if got != want:
        sys.exit(f"sha256 mismatch for {name}: {got} != {want}")
    return dest


def load(cache, name):
    import pyarrow.parquet as pq
    t = pq.read_table(fetch(cache, name), columns=["instance_id", "repo", "created_at"]).to_pydict()
    return [dict(instance_id=i, repo=r, created_at=c)
            for i, r, c in zip(t["instance_id"], t["repo"], t["created_at"])]


def idhash(rows):
    return hashlib.sha256("\n".join(sorted(r["instance_id"] for r in rows)).encode()).hexdigest()


def largest_remainder(counts, target, floor=1):
    alloc = {r: min(floor, c) for r, c in counts.items()}
    left = target - sum(alloc.values())
    pool = sum(c - alloc[r] for r, c in counts.items())
    share = {r: (counts[r] - alloc[r]) / pool * left if pool else 0 for r in counts}
    for r in counts:
        alloc[r] += int(share[r])
    rem = target - sum(alloc.values())
    for r in sorted(counts, key=lambda r: (-(share[r] - int(share[r])), r)):
        if rem <= 0:
            break
        if alloc[r] < counts[r]:
            alloc[r] += 1
            rem -= 1
    return alloc


def decontam(src):
    ver, out = src["verified"], {}
    vrepos = collections.Counter(r["repo"] for r in ver)
    vids = {r["instance_id"] for r in ver}
    vmax = max(r["created_at"] for r in ver)
    for name in ("train", "dev", "swegym"):
        rows = src[name]
        repos = collections.Counter(r["repo"] for r in rows)
        out[name] = {
            "n": len(rows), "n_repos": len(repos),
            "repo_overlap_with_verified": sorted(set(repos) & set(vrepos)),
            "instance_overlap_with_verified": len(vids & {r["instance_id"] for r in rows}),
            "created_min": min(r["created_at"] for r in rows), "created_max": max(r["created_at"] for r in rows),
            "n_created_after_verified_max": sum(1 for r in rows if r["created_at"] > vmax),
            "repos": dict(repos.most_common()),
        }
    out["verified"] = {"n": len(ver), "n_repos": len(vrepos), "repos": dict(vrepos.most_common()),
                       "created_min": min(r["created_at"] for r in ver), "created_max": vmax}
    return out


def gym_splits(rows):
    rng = random.Random(SEED)
    by_repo = collections.defaultdict(list)
    for r in sorted(rows, key=lambda r: r["instance_id"]):
        by_repo[r["repo"]].append(r["instance_id"])
    queues = {}
    for repo in sorted(by_repo):          # sorted: the RNG stream is order-stable
        q = list(by_repo[repo])
        rng.shuffle(q)
        queues[repo] = q
    remaining = {r: len(q) for r, q in queues.items()}
    pos = {r: 0 for r in queues}
    pools = {}
    for name, size in POOL_ORDER:
        alloc = largest_remainder(remaining, size)
        ids = []
        for repo in sorted(queues):
            k = alloc[repo]
            ids += queues[repo][pos[repo]:pos[repo] + k]
            pos[repo] += k
            remaining[repo] -= k
        pools[name] = sorted(ids)
    reserve = {r: queues[r][pos[r]:] for r in sorted(queues)}
    return pools, reserve


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    src = {n: load(a.cache, n) for n in SOURCES}
    dump = lambda name, obj: json.dump(obj, open(os.path.join(a.out, name), "w"), indent=1, sort_keys=True)
    dump("id_hashes.json", {n: {"n": len(rows), "sha256_sorted_ids": idhash(rows),
                                "parquet_sha256": SOURCES[n][3], "hf_repo": SOURCES[n][0], "revision": SOURCES[n][1]}
                            for n, rows in src.items()})
    dump("decontam_report.json", decontam(src))
    pools, reserve = gym_splits(src["swegym"])
    dump("gym_splits.json", {"seed": SEED, "pool_order": POOL_ORDER, "pools": pools, "reserve_queue_per_repo": reserve})
    dev = sorted(r["instance_id"] for r in src["dev"])
    drng = random.Random(SEED + 1)
    by_repo = collections.defaultdict(list)
    for r in src["dev"]:
        by_repo[r["repo"]].append(r["instance_id"])
    alloc = largest_remainder({k: len(v) for k, v in by_repo.items()}, DEV_PILOT)
    pil = []
    for repo in sorted(by_repo):
        ids = sorted(by_repo[repo]); drng.shuffle(ids); pil += ids[:alloc[repo]]
    dump("dev_splits.json", {"seed": SEED + 1, "DEV-225": dev, "DEV-PIL-60": sorted(pil)})
    # hard checks: pools disjoint, disjoint from Verified, no Verified repo
    vrepos = {r["repo"] for r in src["verified"]}
    allp = [i for p in pools.values() for i in p]
    assert len(allp) == len(set(allp)) == sum(s for _, s in POOL_ORDER)
    assert not {r["repo"] for r in src["swegym"]} & vrepos
    assert not {r["repo"] for r in src["dev"]} & vrepos
    print("ok")
    for f in sorted(os.listdir(a.out)):
        print(f, sha256_file(os.path.join(a.out, f)))


if __name__ == "__main__":
    main()
