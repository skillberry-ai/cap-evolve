"""proposer -- the one-shot LLM jobs the AO-2 conductor starts (propose, merge-resolve): prompt + parse.

A proposer job edits ONE working copy for ONE hypothesis and stops. It is bounded (``--budget`` turns,
a token cap the conductor reserves before launch) and it never evaluates, polls or waits: the conductor
owns time, money and statistics. The prompt is deliberately small (<= ``MAX_PROMPT_BYTES``): a hypothesis,
a <= 1.5k-token digest, the parent's identity and four rules. No SKILL.md is read by the job.
"""

from __future__ import annotations

import json
from pathlib import Path

MAX_PROMPT_BYTES = 7168
HYPOTHESIS_FILE = "hypothesis.json"

PROCEDURE = """Procedure (do every step; you may use subagents to read traces in parallel):
1. Read the failing traces listed above (./trajectories). For each failing task find the turn where the agent goes
   wrong; tau2_reward_info (action checks, database/env assertions, required communication) is the ground truth.
2. Group the failing tasks by root cause and fix as MANY groups as you can in this ONE edit, your primary tasks first.
   You are judged on how many of the parent's failing tasks your edit fixes, net of any passing task it breaks.
3. Prefer code over prose: where the agent computes prices/totals, looks things up or checks eligibility in its head,
   add a deterministic tool (or make an existing tool return the needed fields / validate the call) plus one policy
   line saying when to use it. Wording-only edits rarely move these tasks.
4. Keep a change only if it is REAL (a failing trace shows the problem), SAFE (re-read two passing traces: they would
   still pass) and general (no task id, expected answer or copied value).
5. Replay each task in predicted_tasks against your edit and name the turn it changes; drop tasks you cannot.
"""

RULES = """Rules:
- A hypothesis already attempted (see rejected) needs a different mechanism, not new wording.
- Edit only inside {workdir}. Do NOT run evaluations, sleep, poll or wait: the conductor evaluates your edit.
- REQUIRED, the candidate is refused without it: finish by writing {workdir}/hypothesis.json (valid JSON, exactly this name, even when no clusters.json exists): {{"id","cluster_ids":[...],"claim","predicted_tasks":[...],"predicted_mechanism","edit_scope"}}, then stop.
- ./trajectories holds the parent's traces (feedback tasks only; held-out data is not available); ./guidance has the
  capability guides and data-model sources."""

STRICT = "\nYour previous attempt produced no usable candidate. This time the edit MUST change a capability file and hypothesis.json MUST exist."


def pick_cluster(digest_dict: dict, slot: int, taken: set[str]) -> dict | None:
    """The cluster slot ``slot`` should target: open ones by headroom, each at most once per batch."""
    rows = [c for c in (digest_dict or {}).get("clusters") or [] if c.get("status") in ("open", "attempted")
            and c.get("id") not in taken]
    return rows[slot % len(rows)] if rows else None


def failing_block(rates: dict, traces: dict, primary: list, rejected: list) -> str:
    """The data a proposer needs inline: the parent's pass rate on every task it does not always pass,
    the failing trace files to read, this slot's primary tasks, and what was already tried."""
    rows = [f"{t}: {sum(v):g}/{len(v)}" for t, v in sorted(rates.items(), key=lambda kv: (sum(kv[1]) / len(kv[1]), kv[0]))
            if v and sum(v) < len(v)]
    out = [f"Parent's failing tasks (passes/trials): {', '.join(rows) or 'none'}."]
    if primary:
        out.append(f"Your PRIMARY tasks (sibling jobs take the others): {', '.join(primary)}.")
    files = [f for t in (primary or sorted(traces)) for f in traces.get(t, [])]
    if files:
        out.append("Failing traces to read first: " + ", ".join(files) + ".")
    if rejected:
        out.append("Already tried and rejected (measured): " + " | ".join(rejected) + ".")
    return "\n".join(out)


def build_prompt(*, workdir, parent: str, cluster: dict | None, digest_text: str = "", strict: bool = False,
                 kind: str = "propose", conflicts: list | None = None, refusal: str = "", failing: str = "") -> str:
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
    proc = PROCEDURE if kind == "propose" else ""
    body = f"{head}{target}\n{failing}\n\n{digest_text.strip()}\n\n{proc}{RULES.format(workdir=workdir)}"
    if strict:
        body += STRICT
    if refusal:
        body += (f"\nYour previous attempt was refused: {refusal.strip()[:300]}\nFix exactly that, and write "
                 f"{workdir}/hypothesis.json with the fields above.")
    data = body.encode("utf-8")
    if len(data) > MAX_PROMPT_BYTES:      # shrink the digest, never the rules
        room = MAX_PROMPT_BYTES - len(body.replace(digest_text, "").encode("utf-8")) - 16
        body = body.replace(digest_text, digest_text.encode("utf-8")[:max(room, 0)].decode("utf-8", "ignore") + "...")
    return body


def read_hypothesis(workdir) -> dict | None:
    p = Path(workdir) / HYPOTHESIS_FILE
    if not p.is_file():                      # a model may write HYPOTHESIS.json: same file, different case
        p = next((q for q in sorted(Path(workdir).glob("*")) if q.name.lower() == HYPOTHESIS_FILE and q.is_file()), p)
    try:
        h = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return h if isinstance(h, dict) else None


def usage_from_result(stdout: str) -> dict:
    """``{tokens, cache_read}`` of a finished job from run-optimizer's JSON report (``cost``).

    ``tokens`` is the campaign's registered basis: input + output + cache creation, i.e. NON-cache-read
    (the same quantity as the 4M guard). run-optimizer's ``cost.tokens`` also contains the cache reads,
    which are subtracted here and reported on their own; a job re-reads its context every turn, so
    cache reads are ~95% of the raw total and would exhaust a cap that was sized on the other basis."""
    for line in reversed((stdout or "").strip().splitlines()):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            cost = rec.get("cost") or {}
            total, cache = int(cost.get("tokens") or 0), int(cost.get("cache_read_tokens") or 0)
            return {"tokens": max(total - cache, 0), "cache_read": cache}
    return {"tokens": 0, "cache_read": 0}


def tokens_from_result(stdout: str) -> int:
    """Non-cache-read tokens of a finished job (see ``usage_from_result``); 0 when absent."""
    return usage_from_result(stdout)["tokens"]


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
