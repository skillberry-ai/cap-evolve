"""Version store — how each accepted iteration is persisted so the whole process
is inspectable.

Three backends (chosen at intake; **git is the default**):
  - ``git``   — init a git repo in the run dir and commit after every iteration, so
                the full optimization process (candidates, rollouts, state, memory)
                is a browsable history (`git log`, `git diff`). Default.
  - ``copy``  — plain directory snapshots only (no VCS); lightest, used in tests.
  - ``command`` — user-supplied shell commands for commit/snapshot, e.g. to push a
                skill to a *skills store* (`npx skills publish …`) or any external
                versioning system. Placeholders: {msg} {dir} {tag}.

The store records *every* iteration (accepted or not) so rejected attempts remain
auditable; the run's ``best_id`` still tracks only accepted candidates.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


class VersionStore:
    def __init__(self, kind: str = "git", root: Path | None = None,
                 commit_cmd: str | None = None):
        self.kind = kind
        self.root = Path(root) if root else None
        self.commit_cmd = commit_cmd
        self._git_ready = False

    # ---- git helpers ----
    def _git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=str(self.root),
                              capture_output=True, text=True)

    def _ensure_git(self) -> bool:
        if self._git_ready:
            return True
        if self.root is None:
            return False
        if not (self.root / ".git").exists():
            r = self._git("init", "-q")
            if r.returncode != 0:
                return False
            self._git("config", "user.email", "cap-evolve@local")
            self._git("config", "user.name", "cap-evolve")
            # don't track heavy/per-trial rollout files by default
            (self.root / ".gitignore").write_text("rollouts/\nwork/\n", encoding="utf-8")
        self._git_ready = True
        return True

    # ---- public API ----
    def init(self) -> None:
        if self.kind == "git":
            self._ensure_git()

    def commit(self, message: str, tag: str | None = None, accepted: bool = True) -> dict:
        """Record the current run-dir state. Returns {kind, ref?, ok}.

        ``git`` commits every call (full process history). A ``command`` store
        (e.g. publishing to a skills store) only fires on ``accepted`` candidates —
        you don't want to publish rejected/unchanged iterations.
        """
        if self.kind == "git":
            if not self._ensure_git():
                return {"kind": "git", "ok": False, "error": "git unavailable"}
            self._git("add", "-A")
            r = self._git("commit", "-q", "--allow-empty", "-m", message)
            sha = self._git("rev-parse", "--short", "HEAD").stdout.strip()
            if tag:
                self._git("tag", "-f", tag)
            return {"kind": "git", "ok": r.returncode == 0, "ref": sha}
        if self.kind == "command" and self.commit_cmd:
            if not accepted:
                return {"kind": "command", "ok": True, "skipped": "not accepted"}
            cmd = (self.commit_cmd
                   .replace("{msg}", message)
                   .replace("{dir}", str(self.root or "."))
                   .replace("{tag}", tag or ""))
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return {"kind": "command", "ok": r.returncode == 0,
                    "stdout": r.stdout[-300:], "stderr": r.stderr[-300:]}
        return {"kind": self.kind, "ok": True}  # copy: snapshots are handled by RunDir

    def log(self, limit: int = 50) -> list[str]:
        if self.kind == "git" and self._ensure_git():
            r = self._git("log", f"-{limit}", "--pretty=%h %s")
            return [l for l in r.stdout.splitlines() if l.strip()]
        return []


def make_store(spec: dict | None, run_root: Path) -> VersionStore:
    """Build a store from a capevolve.yaml-style spec (``store`` + ``store_commit_cmd``)."""
    spec = spec or {}
    kind = (spec.get("store") or "git").strip()
    return VersionStore(kind=kind, root=run_root, commit_cmd=spec.get("store_commit_cmd"))
