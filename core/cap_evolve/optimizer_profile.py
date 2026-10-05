"""Optimizer profile: adapt the optimizer's working context to a weaker optimizer model.

The optimizer instructions, the raw trajectories and the Claude Code tool set were all
written and tuned with Claude optimizers. When Gemma-4-31B-It ran as its own optimizer
(run 37204406089, #538), it failed on mechanics rather than ideas:

* its round-5 sub-agent made 169 Bash calls, 166 of which returned Claude Code's
  "Output too large ... saved to <file>" notice, and it answered 164 of those by `cat`-ing
  the saved file, which was too large again (~60 Claude sub-agents in the same dirs hit
  that notice 0-2 times each and switched to grep/head/python);
* a raw trajectory is ~60 KB, and ~56 KB of it is the turn-by-turn trace, often the same
  failing turn repeated;
* the per-round INSTRUCTIONS.md is ~32 KB.

This module holds the experimental changes for that hypothesis (#538 follow-up). Each is a
named feature, enabled through ``CAPEVOLVE_OPTIMIZER_PROFILE`` (comma-separated); the
alias ``gemma`` enables all of them. The default (unset) changes nothing.

* ``output_guard``  — add a short "reading large files" rule to INSTRUCTIONS.md.
* ``no_subagents``  — deny Claude Code's sub-agent tool (``Agent``/``Task``) to the optimizer.
* ``digest_trajectories`` — replace each copied trajectory with a compact digest: the task,
  the grader feedback, the final output, and the trace with long turns cut and repeated
  turns collapsed.
* ``short_instructions`` — drop the INSTRUCTIONS.md sections that explain method rather
  than state the task (see ``SHORT_DROP``).
"""

from __future__ import annotations

import json
import os
import re

ENV = "CAPEVOLVE_OPTIMIZER_PROFILE"
FEATURES = ("output_guard", "no_subagents", "digest_trajectories", "short_instructions")
ALIASES = {"gemma": FEATURES}

#: Claude Code's sub-agent tool. Newer CLIs call it ``Agent``, older ones ``Task``.
SUBAGENT_TOOLS = ("Agent", "Task")

OUTPUT_GUARD = """
## Reading large files (REQUIRED)
Trajectory files and command outputs can be larger than one tool result can show. When a
command answers "Output too large ... saved to <file>", do NOT `cat` that file: it is just
as large, and you will loop. Read in small pieces instead:
- `head -c 4000 FILE`, or `sed -n 'A,Bp' FILE` for a line range;
- `grep -n PATTERN FILE` to find the part you need;
- `python3 -c` with `json.load` to print only the fields you need (for a trajectory:
  `score.feedback`, `rollout.output`, and the last 2-3 entries of `rollout.trace`).
Read at most a few KB per call.
"""

#: Section headers (prefix match on the text after "## ") that ``short_instructions`` drops.
#: They explain method and quality bars; the task, the edit space, the failing/passing task
#: lists, the budget and the handover rule stay.
SHORT_DROP = (
    "The THREE TESTS",
    "Choose the lever",
    "VERIFY-THE-FIX",
    "NON-OVERFITTING",
    "What you are editing",
    "How your edit is judged",
    "Self-check before STOP",
    "Cross-iteration files",
)

DIGEST_TURN_CHARS = 700
DIGEST_FIRST_TURN_CHARS = 1500
DIGEST_MAX_TURNS = 16


def features(env: dict | None = None) -> frozenset[str]:
    """The enabled features. Unknown names are ignored, so a typo changes nothing."""
    raw = (env if env is not None else os.environ).get(ENV, "")
    out: set[str] = set()
    for name in (p.strip() for p in raw.split(",")):
        if not name:
            continue
        out.update(ALIASES.get(name, (name,)))
    return frozenset(f for f in out if f in FEATURES)


def enabled(feature: str, env: dict | None = None) -> bool:
    return feature in features(env)


def apply_to_instructions(text: str, env: dict | None = None) -> str:
    """Apply ``short_instructions`` and ``output_guard`` to a rendered INSTRUCTIONS.md."""
    feats = features(env)
    if "short_instructions" in feats:
        parts = re.split(r"(?m)^(## .*)$", text)
        kept = [parts[0]]
        for i in range(1, len(parts), 2):
            header, body = parts[i], parts[i + 1]
            title = header[3:].strip()
            if any(title.startswith(p) for p in SHORT_DROP):
                continue
            kept.extend([header, body])
        text = "".join(kept)
    if "output_guard" in feats:
        text = text.rstrip("\n") + "\n" + OUTPUT_GUARD
    return text


def _cut(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n] + f" …[{len(s) - n} more chars cut]"


def digest_trajectory(obj: dict) -> dict:
    """A compact copy of one rollout file, keeping the fields an optimizer diagnoses from.

    Consecutive identical turns are collapsed into one turn plus a count, each turn is cut to
    ``DIGEST_TURN_CHARS`` (the first, which holds the task prompt, to
    ``DIGEST_FIRST_TURN_CHARS``), and only the last ``DIGEST_MAX_TURNS`` turns are kept after
    the first.
    """
    rollout = dict(obj.get("rollout") or {})
    trace = rollout.get("trace") or []
    collapsed: list[dict] = []
    for turn in trace:
        if not isinstance(turn, dict):
            continue
        content = turn.get("content")
        content = content if isinstance(content, str) else json.dumps(content)
        if collapsed and collapsed[-1]["role"] == turn.get("role") and collapsed[-1]["_raw"] == content:
            collapsed[-1]["repeated"] = collapsed[-1].get("repeated", 1) + 1
            continue
        collapsed.append({"role": turn.get("role"), "_raw": content})
    # A failing agent often repeats the same (code, error) PAIR many times: fold each repeat
    # of the previous two turns into a counter on the pair's second turn.
    folded: list[dict] = []
    i = 0
    while i < len(collapsed):
        if (len(folded) >= 2 and i + 1 < len(collapsed)
                and (collapsed[i]["role"], collapsed[i]["_raw"]) == (folded[-2]["role"], folded[-2]["_raw"])
                and (collapsed[i + 1]["role"], collapsed[i + 1]["_raw"]) == (folded[-1]["role"], folded[-1]["_raw"])):
            folded[-1]["pair_repeated"] = folded[-1].get("pair_repeated", 1) + 1
            i += 2
            continue
        folded.append(collapsed[i])
        i += 1
    collapsed = folded
    digest = []
    for i, t in enumerate(collapsed):
        if 0 < i < len(collapsed) - DIGEST_MAX_TURNS:
            continue
        entry = {"role": t["role"],
                 "content": _cut(t["_raw"], DIGEST_FIRST_TURN_CHARS if i == 0 else DIGEST_TURN_CHARS)}
        if t.get("repeated"):
            entry["repeated"] = t["repeated"]
        if t.get("pair_repeated"):
            entry["previous_two_turns_repeated"] = t["pair_repeated"]
        digest.append(entry)
    omitted = max(0, len(collapsed) - 1 - DIGEST_MAX_TURNS)
    rollout["trace"] = digest
    rollout["trace_digest"] = {"turns_original": len(trace), "turns_after_collapse": len(collapsed),
                               "middle_turns_omitted": omitted}
    if isinstance(rollout.get("output"), str):
        rollout["output"] = _cut(rollout["output"], 2000)
    return {**obj, "rollout": rollout}


def extra_disallowed_tools(agent_name: str, env: dict | None = None) -> list[str]:
    """Tools to add to the optimizer CLI's deny list. Only claude-code has a sub-agent tool."""
    if agent_name == "claude-code" and enabled("no_subagents", env):
        return list(SUBAGENT_TOOLS)
    return []
