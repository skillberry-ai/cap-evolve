#!/usr/bin/env python3
"""manifest.py write <tree> <out.json>   |   manifest.py verify <tree> <manifest.json> [--expect-root SHA]

verify fails (exit 1) on: any added/removed/changed file, any symlink, any file/dir that is writable by
group/other, or (if --expect-root) a tree hash different from the externally pinned value.
Run it before EVERY evaluation; the pinned root hash should live outside the optimizer's reach
(protocol docs / launcher), not only inside MANIFEST.json."""
import hashlib, json, os, stat, sys

def walk(root):
    ent, bad = {}, []
    for dp, dn, fn in os.walk(root):
        dn.sort()
        for n in dn + fn:
            p = os.path.join(dp, n); st = os.lstat(p)
            if stat.S_ISLNK(st.st_mode): bad.append(("symlink", os.path.relpath(p, root))); continue
            if st.st_mode & (stat.S_IWGRP | stat.S_IWOTH): bad.append(("group/other-writable", os.path.relpath(p, root)))
            if stat.S_ISREG(st.st_mode):
                h = hashlib.sha256()
                with open(p, "rb") as f:
                    for c in iter(lambda: f.read(1 << 20), b""): h.update(c)
                ent[os.path.relpath(p, root)] = h.hexdigest()
    return ent, bad

def tree_hash(ent): return hashlib.sha256("\n".join(f"{k}\0{v}" for k, v in sorted(ent.items())).encode()).hexdigest()

def main():
    mode, tree, mf = sys.argv[1], sys.argv[2], sys.argv[3]
    ent, bad = walk(tree)
    if mode == "write":
        if bad: sys.exit(f"refusing to write manifest: {bad[:5]}")
        json.dump({"n_files": len(ent), "tree_sha256": tree_hash(ent), "files": ent}, open(mf, "w"), indent=0, sort_keys=True)
        print(tree_hash(ent), len(ent)); return
    want = json.load(open(mf)); problems = []
    exp = sys.argv[sys.argv.index("--expect-root") + 1] if "--expect-root" in sys.argv else None
    for k in sorted(set(want["files"]) | set(ent)):
        if k not in ent: problems.append(f"MISSING {k}")
        elif k not in want["files"]: problems.append(f"ADDED {k}")
        elif ent[k] != want["files"][k]: problems.append(f"CHANGED {k}")
    problems += [f"UNSAFE {a} {b}" for a, b in bad]
    if exp and exp != tree_hash(ent): problems.append(f"ROOT HASH != pinned {exp[:12]}")
    if problems:
        print("MANIFEST VERIFY FAILED:\n  " + "\n  ".join(problems[:20])); sys.exit(1)
    print(f"manifest OK {tree_hash(ent)[:16]} ({len(ent)} files)")

main()
