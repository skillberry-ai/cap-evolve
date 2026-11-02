"""Proposer-input ablations: ``abl_history`` (none | state) and ``abl_info`` (reward | eval | fail).

Everything here changes ONLY what the proposer is shown (its working dir and instructions). The
gate, the evaluator and scoring never read it. With no ``abl_*`` key every function is a no-op, so
the stock path is unchanged.

Spec keys (top-level in capevolve.yaml, read with ``specfile.spec_for_run``):
  abl_history: none | state     none = no history of any kind; state = state md files, no earlier traces
  abl_info:    reward | eval | fail
The harness may run in a subprocess, so ``export_env(spec)`` (called from ``cli``) also mirrors the
values into ``CAPEVOLVE_ABL_HISTORY`` / ``CAPEVOLVE_ABL_INFO``; ``settings(run_dir)`` re-derives
them from the run's spec and activates them for this process.
"""

from __future__ import annotations

import json
import shutil
import os
import re
import sys
from pathlib import Path

HISTORY_VALUES = ("none", "state")
INFO_VALUES = ("reward", "eval", "fail")
GATE_VALUES = ("none", "disjoint")
ENV_HISTORY = "CAPEVOLVE_ABL_HISTORY"
ENV_INFO = "CAPEVOLVE_ABL_INFO"

_ACTIVE: dict = {"history": None, "info": None}


def _norm(spec: dict | None) -> tuple[str | None, str | None]:
    spec = spec or {}

    def one(key, allowed):
        if key not in spec or spec[key] is None:
            return None
        v = str(spec[key]).strip().lower()
        if v not in allowed:
            raise ValueError(f"{key}={spec[key]!r}: expected one of {list(allowed)}")
        return v

    return one("abl_history", HISTORY_VALUES), one("abl_info", INFO_VALUES)


def settings_from_spec(spec: dict | None) -> tuple[str | None, str | None]:
    """``(history, info)`` of a spec dict; ValueError on an unknown value."""
    return _norm(spec)


def settings(run_dir) -> tuple[str | None, str | None]:
    """``(history, info)`` of the run's spec (``(None, None)`` for a stock run). Also activates them
    for this process so the hooks without a run dir (``_fmt``, ``history_enabled``) see them."""
    from .specfile import spec_for_run
    h, i = _norm(spec_for_run(run_dir))
    if h is not None or i is not None or _ACTIVE["history"] or _ACTIVE["info"]:
        _ACTIVE["history"], _ACTIVE["info"] = h, i
    return h, i


def export_env(spec: dict | None) -> tuple[str | None, str | None]:
    """cli hook: validate the spec values, mirror them into the environment (inherited by the
    harness subprocesses) and route ``abl_history=none`` through the existing ``CAPEVOLVE_HISTORY=0``."""
    h, i = _norm(spec)
    _ACTIVE["history"], _ACTIVE["info"] = h, i
    for k, v in ((ENV_HISTORY, h), (ENV_INFO, i)):
        if v:
            os.environ[k] = v
    if h == "none":
        os.environ["CAPEVOLVE_HISTORY"] = "0"
    return h, i


def _current(env_key: str, field: str, allowed) -> str | None:
    v = os.environ.get(env_key, "").strip().lower()
    if v:
        if v not in allowed:
            raise ValueError(f"{env_key}={v!r}: expected one of {list(allowed)}")
        return v
    return _ACTIVE[field]


def current_history() -> str | None:
    return _current(ENV_HISTORY, "history", HISTORY_VALUES)


def current_info() -> str | None:
    return _current(ENV_INFO, "info", INFO_VALUES)


def history_none() -> bool:
    return current_history() == "none"


# ---------------------------------------------------------------- history: instructions text

_HIST_KW = re.compile(
    r"LEDGER|JOURNAL|RUNMAP|prior_iterations|INSIGHTS|FRAMEWORK_IMPROVEMENTS|"
    r"rejected\.jsonl|history\.jsonl|Currently PASSING")
_ITEM_START = re.compile(r"^(?:- |\d+\. )")
_PAREN = re.compile(r"\s*\([^()]*(?:" + _HIST_KW.pattern + r")[^()]*\)")

# Known phrases where the history reference is only a clause of an otherwise needed item.
_PRE_SUBS = (
    (re.compile(r" Don't re-add\s+anything `LEDGER\.md` / `JOURNAL\.md` show was already tried and rejected\."), ""),
    (re.compile(r"Fill `PROCESS\.md` and APPEND your entry to `JOURNAL\.md`\."), "Fill `PROCESS.md`."),
    (re.compile(r"PROCESS\.md \+ JOURNAL\.md are filled\."), "PROCESS.md is filled."),
    (re.compile(r"Read your capability SKILL\(s\) \+ the diagnose method \+ the cross-iteration files"),
     "Read your capability SKILL(s) + the diagnose method"),
)


def strip_history_refs(text: str) -> str:
    """Remove every reference to the cross-iteration history files from rendered instructions.

    Bullet items (``- `` / ``1. `` plus continuation lines) whose first line names a history file are
    dropped; elsewhere parentheticals and sentences that name one are cut. PROCESS.md stays."""
    for pat, rep in _PRE_SUBS:
        text = pat.sub(rep, text)
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if _ITEM_START.match(ln):
            j = i + 1
            while j < len(lines) and lines[j].strip() and not _ITEM_START.match(lines[j]):
                j += 1
            block = lines[i:j]
            i = j
            if ln.startswith("- ") and _HIST_KW.search(ln):
                continue
            out.extend(_clean_block(block))
            continue
        if ln.strip() and _HIST_KW.search(ln):
            j = i + 1
            while j < len(lines) and lines[j].strip() and not _ITEM_START.match(lines[j]):
                j += 1
            out.extend(_clean_block(lines[i:j]))
            i = j
            continue
        out.append(ln)
        i += 1
    return re.sub(r"\n{3,}", "\n\n", "\n".join(out))


def _clean_block(block: list[str]) -> list[str]:
    text = "\n".join(block)
    if not _HIST_KW.search(text):
        return block
    text = _PAREN.sub("", text)
    if _HIST_KW.search(text):
        m = _ITEM_START.match(text)
        prefix = m.group(0) if m else ""
        body = text[len(prefix):]
        sents = re.split(r"(?<=[.!?])\s+", body.replace("\n", " "))
        kept = [s for s in sents if s and not _HIST_KW.search(s)]
        if not kept:
            return []
        text = prefix + " ".join(kept)
    text = re.sub(r" +([.,;])", r"\1", text)
    return text.split("\n")


RUNMAP_TRACE_SENTENCE = re.compile(
    r"The live run dir \(read-only\) is at `[^`]*` if you need `rollouts/<split>/` traces or the git log\.\n\n")


def runmap_text(text: str) -> str:
    """HIST-STATE: RUNMAP.md must not point at earlier-step traces."""
    if current_history() != "state":
        return text
    return RUNMAP_TRACE_SENTENCE.sub("", text)


# ---------------------------------------------------------------- info

_NOTES = {
    "reward": ("## Information available this run (ablation)\n"
               "`./trajectories/` holds the full conversations and tool calls, but grading detail is "
               "withheld: each rollout carries only its reward (`score.feedback` is just the reward "
               "number). Failure lines name the task and its reward only. Infer why a run lost "
               "reward from the conversation itself.\n"),
    "eval": ("## Information available this run (ablation)\n"
             "`./trajectories/` holds NO conversation traces, outputs or tool calls. Each file is one "
             "rollout's evaluation block only: task id, trial, reward, the grader's feedback and "
             "its checks (`score`, `metadata.tau2_reward_info`, `metadata.termination_reason`). Work "
             "from what the grader says went wrong.\n"),
    "fail": ("## Information available this run (ablation)\n"
             "`./trajectories/` holds ONLY the trials that failed (reward < 1.0); every successful "
             "trial was removed. A task id may appear for some trials and not others.\n"),
}


def info_note(info: str | None) -> str:
    return _NOTES.get(info or "", "")


def fmt_failure(pt) -> str | None:
    """INFO-REWARD hook for ``harness._fmt``: ``- <task> (reward r)`` with no feedback text."""
    if current_info() != "reward":
        return None
    return f"- {pt.get('task_id')} (reward {float(pt.get('reward', 0) or 0):.2f})"


_STRIP_META = ("tau2_reward_info", "judge", "usersim", "termination_reason")


def _trial_of(name: str):
    m = re.search(r"__t(\d+)\.json$", name)
    return int(m.group(1)) if m else None


def transform_rollout(d: dict, info: str, name: str = "") -> dict | None:
    """Apply ``info`` to one rollout dict; ``None`` means drop the file."""
    score = d.get("score") or {}
    reward = score.get("reward", 0) or 0
    if info == "fail":
        return d if float(reward) < 1.0 else None
    if info == "reward":
        score["feedback"] = f"Task reward: {float(reward):.3f}."
        score["raw"] = {}
        meta = (d.get("rollout") or {}).get("metadata")
        if isinstance(meta, dict):
            for k in _STRIP_META:
                meta.pop(k, None)
        d["score"] = score
        return d
    if info == "eval":
        meta = (d.get("rollout") or {}).get("metadata") or {}
        out: dict = {"task_id": (d.get("rollout") or {}).get("task_id", score.get("task_id", d.get("input")))}
        t = _trial_of(name)
        if t is not None:
            out["trial"] = t
        out["reward"] = score.get("reward")
        out["score"] = {k: score[k] for k in ("feedback", "raw") if k in score}
        out["metadata"] = {k: meta[k] for k in ("tau2_reward_info", "termination_reason") if k in meta}
        return out
    return d


def transform_trajectories(dst_dir, info: str | None) -> None:
    """Rewrite the copied ``workdir/trajectories`` in place for ``info`` (no-op when unset)."""
    if not info:
        return
    if info not in INFO_VALUES:
        raise ValueError(f"abl_info={info!r}: expected one of {list(INFO_VALUES)}")
    dst = Path(dst_dir)
    if not dst.is_dir():
        return
    for f in sorted(dst.rglob("*")):
        if not f.is_file():
            continue
        if f.suffix != ".json":
            # the native-dir fallback can copy adapter files (tau2 results_*.json aside, logs, dbs) that
            # we cannot rewrite; in reward/eval they could carry the withheld detail, so drop them
            if info != "fail":
                f.unlink()
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            if info != "fail":      # an unreadable file could carry anything: never pass it through
                f.unlink()
            continue
        if not isinstance(d, dict):
            f.unlink()
            continue
        new = transform_rollout(d, info, f.name)
        if new is None:
            f.unlink()
        else:
            f.write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- sandbox hiding

_HIDE_NONE = ["rollouts", "native_sims", "candidates", "work", "baseline.json", "champion.json", "state.json", "rejected.jsonl", "history.jsonl",
              "JOURNAL.md", "LEDGER.md", "INSIGHTS.md", "META_INSIGHTS.md",
              "FRAMEWORK_IMPROVEMENTS.md", "graph.jsonl", "eval_index.jsonl", "candidates.jsonl"]
# baseline.json / champion.json / state.json carry per-task rewards, grader feedback or the full-split val;
# candidates/ holds every earlier step's rendered INSTRUCTIONS.md (its failure index quotes grader feedback).
_HIDE_TRACES = ["rollouts", "native_sims", "eval_index.jsonl", "baseline.json", "champion.json", "state.json",
                "candidates"]


def hidden_paths(history: str | None, info: str | None, gate: str | None = None) -> list[str]:
    """Names under run_main the sandbox must hide (see ABL DESIGN.md "Sandbox hiding")."""
    for v, allowed, key in ((history, HISTORY_VALUES, "abl_history"), (info, INFO_VALUES, "abl_info"),
                            (gate, GATE_VALUES, "abl_gate")):
        if v is not None and v not in allowed:
            raise ValueError(f"{key}={v!r}: expected one of {list(allowed)}")
    names: list[str] = []

    def add(xs):
        names.extend(x for x in xs if x not in names)

    if history == "none":
        add(_HIDE_NONE)
    if history == "state" or info:
        add(_HIDE_TRACES)
    if gate == "disjoint":
        add(_HIDE_TRACES + ["graph.jsonl"])
    return names


def _main(argv) -> int:
    if len(argv) == 2 and argv[0] == "hidden":
        from .specfile import read_yaml
        spec = read_yaml(Path(argv[1]).read_text(encoding="utf-8")) or {}
        h, i = _norm(spec)
        g = spec.get("abl_gate")
        g = str(g).strip().lower() if g is not None else None
        print(",".join(hidden_paths(h, i, g)))
        return 0
    print("usage: python -m cap_evolve.abl_context hidden <spec.yaml>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))


def clean_carryover(run_dir, workdir) -> list:
    """HIST-NONE: the workdir starts as a copy of the parent candidate, which also holds the files an earlier
    proposer left at the top level (PROCESS.md, DIAGNOSIS.json, notes dirs). Remove every top-level entry that the
    SEED capability does not have, so no earlier step's analysis rides along. No-op for every other run."""
    hist, _ = settings(run_dir)
    if hist != "none":
        return []
    seed = Path(run_dir.candidate_dir("seed"))
    keep = {p.name for p in seed.iterdir()} if seed.is_dir() else {"policy", "tools", "reference"}
    removed = []
    for p in sorted(Path(workdir).iterdir()):
        if p.name in keep:
            continue
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p)
        else:
            p.unlink()
        removed.append(p.name)
    return removed
