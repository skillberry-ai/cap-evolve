#!/usr/bin/env bash
# Copy the CURATED audit artifacts of an agent-optimize run out of the (gitignored)
# run dir into examples/, so the numbers in docs/RESULTS.md are traceable and the
# dashboard UI is reproducible from the repo alone.
#
#   bash examples/tau2_airline/export_run_artifacts.sh <run_dir> <dest_dir>
#
# `.gitignore` globs `.capevolve*/`, so run dirs are never committable by accident —
# this is the only path by which a run's evidence reaches the repo.
#
# events.jsonl is MANDATORY, not optional: the dashboard replays a run from it, and a
# previous export omitted it, which made that run's UI unreproducible. Rollouts are the
# bulk of a run dir and are NOT copied wholesale; per-task rewards are distilled into
# {train,val}_per_task.json instead, and the candidate edits into candidate_diffs.txt.
set -euo pipefail
RUN="${1:?usage: export_run_artifacts.sh <run_dir> <dest_dir>}"
DEST="${2:?usage: export_run_artifacts.sh <run_dir> <dest_dir>}"
[ -d "$RUN" ] || { echo "no such run dir: $RUN" >&2; exit 2; }
mkdir -p "$DEST"

for f in events.jsonl state.json splits.json baseline.json final.json measure.json report.md; do
  [ -f "$RUN/$f" ] && cp "$RUN/$f" "$DEST/$f"
done
[ -d "$RUN/screens" ] && { mkdir -p "$DEST/screens"; cp "$RUN"/screens/*.json "$DEST/screens/" 2>/dev/null || true; }

# Per-task rewards per split per tag — the source the results table is re-derivable from.
python3 - "$RUN" "$DEST" <<'PY'
import json, sys
from pathlib import Path
run, dest = Path(sys.argv[1]), Path(sys.argv[2])
for split in ("train", "val", "test"):
    d = run / "rollouts" / split
    if not d.is_dir():
        continue
    # trials > 1 writes one rollout file PER TRIAL (…__t0/__t1/…). Keying only by task
    # would silently keep whichever trial sorted last and throw the rest away, so the
    # exported `reward` would not be the number the gate saw. Collect every trial, then
    # report `reward` as the mean over trials and keep the raw vector in `trials`.
    acc: dict = {}
    for f in sorted(d.glob("*__*__t*.json")):
        parts = f.name[:-len(".json")].split("__")
        task, tag, trial = parts[0], "__".join(parts[1:-1]), parts[-1]
        rec = json.loads(f.read_text(encoding="utf-8"))
        sc = rec.get("score") or {}
        acc.setdefault(tag, {}).setdefault(task, []).append(
            (trial, sc.get("reward"), bool((rec.get("rollout") or {}).get("error")),
             (sc.get("feedback") or "")[:600])
        )
    out: dict = {}
    for tag, tasks in acc.items():
        for task, rows in tasks.items():
            rows.sort(key=lambda r: r[0])
            vals = [r[1] for r in rows if isinstance(r[1], (int, float))]
            out.setdefault(tag, {})[task] = {
                "reward": (sum(vals) / len(vals)) if vals else None,
                "trials": [r[1] for r in rows],
                "errored": any(r[2] for r in rows),
                "feedback": rows[0][3],
            }
    if out:
        (dest / f"{split}_per_task.json").write_text(json.dumps(out, indent=2, sort_keys=True),
                                                     encoding="utf-8")
        print(f"wrote {split}_per_task.json ({len(out)} tags)")
PY

# Unified diff of every snapshotted candidate against the seed — what was actually edited.
{
  seed="$RUN/candidates/seed"
  for cand in "$RUN"/candidates/*; do
    name="$(basename "$cand")"
    [ "$name" = "seed" ] && continue
    for rel in policy/policy.md tools/tools.py; do
      if [ -f "$cand/$rel" ] && ! diff -q "$seed/$rel" "$cand/$rel" >/dev/null 2>&1; then
        echo "===== $name :: $rel ====="
        diff -u "$seed/$rel" "$cand/$rel" || true
        echo
      fi
    done
  done
} > "$DEST/candidate_diffs.txt"

echo "exported to $DEST:"; ls -la "$DEST"; du -sh "$DEST"
