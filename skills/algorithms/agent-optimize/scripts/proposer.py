"""proposer -- the one-shot LLM jobs the AO-2 conductor starts (propose, merge-resolve): prompt + parse.

A proposer job edits ONE working copy for ONE hypothesis and stops. It is bounded (``--budget`` turns,
a token cap the conductor reserves before launch) and it never evaluates, polls or waits: the conductor
owns time, money and statistics. The prompt is deliberately small (<= ``MAX_PROMPT_BYTES``): a hypothesis,
a <= 1.5k-token digest, the parent's identity and four rules. No SKILL.md is read by the job.
"""

from __future__ import annotations

import json
from pathlib import Path

MAX_PROMPT_BYTES = 3072
HYPOTHESIS_FILE = "hypothesis.json"

RULES = """Rules:
- One coherent edit for ONE hypothesis. General rules only: never a task id, an expected answer or a copied value.
- Edit only inside {workdir}. Do NOT run evaluations, sleep, poll or wait: the conductor evaluates your edit.
- Finish by writing {workdir}/hypothesis.json: {{"id","cluster_ids":[...],"claim","predicted_tasks":[...],"predicted_mechanism","edit_scope"}}, then stop.
- Reasoning about failures: read traces under ./trajectories if present (feedback tasks only; held-out data is not available)."""

STRICT = "\nYour previous attempt produced no usable candidate. This time the edit MUST change a capability file and hypothesis.json MUST exist."


def pick_cluster(digest_dict: dict, slot: int, taken: set[str]) -> dict | None:
    """The cluster slot ``slot`` should target: open ones by headroom, each at most once per batch."""
    rows = [c for c in (digest_dict or {}).get("clusters") or [] if c.get("status") in ("open", "attempted")
            and c.get("id") not in taken]
    return rows[slot % len(rows)] if rows else None


def build_prompt(*, workdir, parent: str, cluster: dict | None, digest_text: str = "", strict: bool = False,
                 kind: str = "propose", conflicts: list | None = None) -> str:
    head = {
        "propose": f"You are proposing one edit to candidate {parent!r} (already copied into {workdir}).",
        "merge": (f"{workdir} is a copy of branch {parent!r}; merging another branch into it conflicts in: "
                  f"{'; '.join(map(str, conflicts or []))}. Rewrite each conflicting part so BOTH branches' "
                  "intended changes survive (read the other branch's version where given)."),
    }[kind]
    target = ""
    if cluster:
        target = (f"\nTarget cluster {cluster.get('id')}: {cluster.get('label') or ''}; failing tasks "
                  f"{', '.join(map(str, cluster.get('tasks') or []))}; headroom {cluster.get('headroom')}.")
    body = f"{head}{target}\n\n{digest_text.strip()}\n\n{RULES.format(workdir=workdir)}"
    if strict:
        body += STRICT
    data = body.encode("utf-8")
    if len(data) > MAX_PROMPT_BYTES:      # shrink the digest, never the rules
        room = MAX_PROMPT_BYTES - len(body.replace(digest_text, "").encode("utf-8")) - 16
        body = body.replace(digest_text, digest_text.encode("utf-8")[:max(room, 0)].decode("utf-8", "ignore") + "...")
    return body


def read_hypothesis(workdir) -> dict | None:
    p = Path(workdir) / HYPOTHESIS_FILE
    try:
        h = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return h if isinstance(h, dict) else None


def tokens_from_result(stdout: str) -> int:
    """Billed optimizer tokens from run-optimizer's JSON report (``cost.tokens``); 0 when absent."""
    for line in reversed((stdout or "").strip().splitlines()):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            return int(((rec.get("cost") or {}).get("tokens")) or 0)
    return 0


def _billed(usage: dict) -> int:
    """input + output + cache creation: the quantity the token watchdog counts (cache reads are not billed as new work)."""
    return sum(int(usage.get(k) or 0) for k in ("input_tokens", "output_tokens", "cache_creation_input_tokens"))


def transcript_tokens(path) -> int:
    """Tokens a still-running job has used so far, from its stream-json transcript (one ``usage`` per
    assistant message id, the last one seen; the final ``result`` record, when present, is the total)."""
    per_msg: dict = {}
    try:
        lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return 0
    for n, line in enumerate(lines):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if not isinstance(rec, dict):
            continue
        if rec.get("type") == "result" and isinstance(rec.get("usage"), dict):
            return _billed(rec["usage"])
        msg = rec.get("message")
        if isinstance(msg, dict) and isinstance(msg.get("usage"), dict):
            per_msg[msg.get("id") or f"line{n}"] = _billed(msg["usage"])
    return sum(per_msg.values())
