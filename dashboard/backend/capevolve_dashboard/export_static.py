"""Export a cap-evolve run as the static JSON the dashboard SPA's STATIC_MODE reads.

Re-uses the exact same backend reducers (runs / trajectories / memory / files /
gitlog / compare) the live FastAPI app uses, so the emitted shapes match
``src/lib/types.ts`` byte-for-byte. Every file is named by the same slug the
frontend's ``staticSlug()`` computes from the /api/* path+query, so the SPA finds
it under ``data/<slug>.json`` with no backend.

Trajectories / rollouts are intentionally skipped (emitted as empty lists), and
the ``rollouts`` subtree is pruned from the Files tree to keep the export small.

Usage:
    python -m capevolve_dashboard.export_static \
        --base /path/to/.capevolve --run-id run_full --out /path/to/ui/data
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from . import _bootstrap  # noqa: F401  (ensures cap_evolve importable)
from . import compare, files, gitlog, memory, runs
from cap_evolve import RunDir, dashboard


# One exclude list, shared with the live server (see gitlog.DIFF_EXCLUDE) — the export
# and the live view of the same run must show the same diff.
_GIT_DIFF_EXCLUDE = gitlog.DIFF_EXCLUDE


def slug(url: str) -> str:
    """Mirror of the frontend ``staticSlug()`` — keep the two in lock-step."""
    path = re.sub(r"^/api/?", "", url)
    s = re.sub(r"[^a-z0-9]+", "_", path.lower()).strip("_")
    return s or "index"


class Exporter:
    def __init__(self, base: Path, run_id: str, out: Path) -> None:
        self.base = Path(base)
        self.run_id = run_id
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=True)
        self.run_path = runs.resolve_run(self.base, run_id)
        self.written: list[str] = []

    def _emit(self, url: str, payload) -> None:
        name = f"{slug(url)}.json"
        (self.out / name).write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        self.written.append(name)

    def export(self) -> None:
        rid = self.run_id
        rp = self.run_path

        # Hub: runs list + per-run compare (single-id, harmless).
        self._emit("/api/runs", runs.list_runs(self.base))

        # Reduce the run ONCE; reuse for detail + all per-candidate diffs (the live
        # backend's diff_candidate re-reduces per call, which is far too slow here).
        rd = RunDir.open(rp)
        reduced = dashboard.reduce_run(rd)
        graph = reduced["graph"]
        nodes = graph.get("nodes", [])
        detail = {"run_id": rid, "path": str(rp), **reduced}
        self._emit(f"/api/runs/{rid}", detail)

        # Memory (history + rejected, redacted).
        self._emit(f"/api/runs/{rid}/memory", memory.read_memory(rp))

        # Per-candidate diff vs parent — build_diffs once for the whole graph, then
        # project each node into the {candidate, parent, files:[{path,added,removed,rows}]}
        # shape (identical to trajectories.diff_candidate).
        all_diffs = dashboard.build_diffs(rd, graph) or {}
        for n in nodes:
            cid = n["id"]
            files_out = []
            for entry in all_diffs.get(cid, []):
                rows = entry.get("rows", [])
                files_out.append({
                    "path": entry.get("file"),
                    "added": sum(1 for r in rows if r.get("t") == "add"),
                    "removed": sum(1 for r in rows if r.get("t") == "del"),
                    "rows": rows,
                })
            self._emit(
                f"/api/runs/{rid}/diff/{cid}",
                {"candidate": cid, "parent": n.get("parent"), "files": files_out},
            )
            # Candidate scratch files.
            self._emit(
                f"/api/runs/{rid}/candidate/{cid}/files",
                memory.list_candidate_files(rp, cid),
            )

        # Git log + every adjacent (commit vs parent) diff the Git tab requests.
        # Exclude the huge regenerated artifacts that would bloat each diff (and which
        # are out of scope for a static export): trajectory results, the embedded
        # dashboard.html snapshot, append-only event/log files, and compiled caches.
        # This keeps each diff to the meaningful capability/candidate changes.
        log = gitlog.log(rp)
        self._emit(f"/api/runs/{rid}/git/log", log)
        for i, c in enumerate(log):
            if i == 0:
                continue  # initial commit has no parent (UI shows "no previous")
            h = c["hash"]
            frm, to = f"{h}~1", h
            self._emit(
                f"/api/runs/{rid}/git/diff?from={frm}&to={to}",
                gitlog.diff(rp, frm, to, exclude=_GIT_DIFF_EXCLUDE),
            )

        # Files tree — prune the rollouts subtree (skipped) to keep the export small.
        tree = files.tree(rp)
        tree["entries"] = [e for e in tree["entries"] if e.get("name") != "rollouts"]
        tree["truncated"] = False
        self._emit(f"/api/runs/{rid}/tree?path=", tree)

        # File contents for every (non-rollout) file remaining in the tree.
        for path in _iter_file_paths(tree["entries"]):
            self._emit(
                f"/api/runs/{rid}/file?path={path}",
                files.read_file(rp, path),
            )

        # Trajectories / rollouts: omitted in static export -> empty lists.
        self._emit(f"/api/runs/{rid}/rollouts", [])
        for split in ("val", "test", "train"):
            self._emit(f"/api/runs/{rid}/rollouts?split={split}", [])

        # Compare (single id; the Hub can still navigate to /compare for this run).
        self._emit(f"/api/compare?ids={rid}", compare.compare_runs(self.base, [rid]))


def _iter_file_paths(entries: list[dict]):
    for e in entries:
        if e.get("type") == "file":
            yield e["path"]
        else:
            yield from _iter_file_paths(e.get("children", []))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Export a cap-evolve run as static JSON.")
    ap.add_argument("--base", required=True, help="dir containing run_* (the .capevolve dir)")
    ap.add_argument("--run-id", required=True, help="run dir name (e.g. run_full)")
    ap.add_argument("--out", required=True, help="output data/ dir for the static export")
    args = ap.parse_args(argv)

    exp = Exporter(Path(args.base), args.run_id, Path(args.out))
    exp.export()
    print(f"wrote {len(exp.written)} JSON files to {exp.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
