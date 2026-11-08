"""A file-based work queue shared by the dispatching adapter and the lane workers.

Everything lives under one root on GPFS, which every CCC node mounts:

    bundles/<sha>/*.md        immutable copy of a candidate's prompts, named by content
    pending/<item>.json       a trial waiting for a worker
    claimed/<item>__<worker>.claim   a trial a worker is running; the owner is in the name
    done/<item>.json          the finished trial: ``{"item": ..., "rollout": Rollout.to_dict()}``
    workers/<worker>.json     heartbeat: host, LSF job, state, current item, time
    stop                      present = workers exit at their next idle check

A claim is ``os.rename(pending/<item>.json, claimed/<item>__<worker>.claim)``: atomic on
one filesystem, so two workers can never take the same trial, and the owner is recorded
by the same rename rather than by a later write that a crash could separate from it.
A worker heartbeats from before its first claim; one whose heartbeat goes stale had its
node or job die, and ``requeue_stale`` moves its claimed trials back to pending.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from pathlib import Path

PROMPT_GLOB = "*.md"


def _atomic_write(path: Path, data: dict) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)


def _read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


class LaneQueue:
    def __init__(self, root: Path):
        self.root = Path(root)
        for sub in ("bundles", "pending", "claimed", "done", "workers"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    # ---- bundles -------------------------------------------------------------------------------------

    def snapshot_bundle(self, src: Path) -> Path:
        """Copy ``src``'s prompt files to ``bundles/<sha>``; identical content reuses one copy."""
        files = sorted(Path(src).glob(PROMPT_GLOB))
        if not files:
            raise ValueError(f"no {PROMPT_GLOB} files in candidate dir {src}")
        h = hashlib.sha256()
        for f in files:
            h.update(f.name.encode())
            h.update(b"\0")
            h.update(f.read_bytes())
            h.update(b"\0")
        dst = self.root / "bundles" / h.hexdigest()[:16]
        if not dst.is_dir():
            tmp = dst.with_name(f".{dst.name}.{os.getpid()}.tmp")
            shutil.rmtree(tmp, ignore_errors=True)
            tmp.mkdir()
            for f in files:
                shutil.copyfile(f, tmp / f.name)
            try:
                os.rename(tmp, dst)
            except OSError:                 # another process published the same bundle first
                shutil.rmtree(tmp, ignore_errors=True)
        return dst

    # ---- dispatcher side -----------------------------------------------------------------------------

    def enqueue(self, item: dict) -> None:
        item = {**item, "enqueued_at": time.time()}
        _atomic_write(self.root / "pending" / f"{item['item']}.json", item)

    def result(self, item_id: str) -> dict | None:
        return _read(self.root / "done" / f"{item_id}.json")

    def forget(self, item_id: str) -> None:
        """Drop a finished trial's record so it can be re-enqueued under the same id."""
        (self.root / "done" / f"{item_id}.json").unlink(missing_ok=True)

    def cancel(self, item_id: str) -> bool:
        """Withdraw a trial nobody has claimed yet; False if a worker already holds it."""
        try:
            (self.root / "pending" / f"{item_id}.json").unlink()
            return True
        except FileNotFoundError:
            return False

    def counts(self) -> dict:
        return {"pending": sum(1 for _ in (self.root / "pending").glob("*.json")),
                "claimed": sum(1 for _ in (self.root / "claimed").glob("*.claim")),
                "done": sum(1 for _ in (self.root / "done").glob("*.json"))}

    def live_workers(self, stale_sec: float) -> list[dict]:
        now = time.time()
        out = []
        for p in (self.root / "workers").glob("*.json"):
            hb = _read(p)
            if hb and hb.get("state") != "exited" and now - float(hb.get("ts") or 0) <= stale_sec:
                out.append(hb)
        return out

    def requeue_stale(self, stale_sec: float) -> list[str]:
        """Move trials claimed by a worker whose heartbeat is stale (or gone) back to pending."""
        live = {w["worker"] for w in self.live_workers(stale_sec)}
        moved = []
        for p in (self.root / "claimed").glob("*.claim"):
            item_id, _, worker = p.stem.rpartition("__")
            if worker in live:
                continue
            try:
                os.rename(p, self.root / "pending" / f"{item_id}.json")
            except OSError:
                continue                    # completed or requeued by someone else meanwhile
            moved.append(item_id)
        return moved

    def request_stop(self) -> None:
        (self.root / "stop").touch()

    def clear_stop(self) -> None:
        (self.root / "stop").unlink(missing_ok=True)

    # ---- worker side ---------------------------------------------------------------------------------

    def stop_requested(self) -> bool:
        return (self.root / "stop").exists()

    def claim(self, worker: str) -> dict | None:
        """Take the oldest pending trial, or None. Losing a rename race just means trying the next one."""
        if "__" in worker:
            raise ValueError(f"worker id may not contain '__': {worker!r}")
        aged = []
        for p in (self.root / "pending").glob("*.json"):
            try:
                aged.append((p.stat().st_mtime, p))
            except FileNotFoundError:       # claimed by another worker between listing and stat
                continue
        for _, p in sorted(aged):
            dst = self.root / "claimed" / f"{p.stem}__{worker}.claim"
            try:
                os.rename(p, dst)
            except OSError:
                continue
            item = _read(dst)
            if item is None:
                dst.unlink(missing_ok=True)
                continue
            return {**item, "worker": worker}

        return None

    def _claim_path(self, item: dict) -> Path:
        return self.root / "claimed" / f"{item['item']}__{item['worker']}.claim"

    def complete(self, item: dict, rollout: dict) -> None:
        _atomic_write(self.root / "done" / f"{item['item']}.json", {"item": item, "rollout": rollout})
        self._claim_path(item).unlink(missing_ok=True)

    def release(self, item: dict) -> None:
        """Hand a claimed trial back without a result (the worker is giving up on its lane)."""
        try:
            os.rename(self._claim_path(item), self.root / "pending" / f"{item['item']}.json")
        except OSError:
            pass

    def heartbeat(self, worker: str, **fields) -> None:
        _atomic_write(self.root / "workers" / f"{worker}.json", {"worker": worker, "ts": time.time(), **fields})
