"""Bounded per-task feedback for the optimizer prompt, with the full text one link away.

A scorer's feedback (an LLM judge's rationale above all) can run to thousands of
characters per trial, times every trial. The optimizer prompt lists one entry per task,
so each entry is bounded at ``entry_chars()`` (default 800). An entry that fits is shown
as it is. A longer one is condensed:

* by a summarizer model, ``summarize_batches`` — at most ``BATCH`` tasks per call; or,
  when no summarizer is reachable or a reply is unusable,
* by ``fallback`` — deterministic, no model.

Either way the entry starts with a code-written ``trials:`` line (every trial's reward,
the lowest marked), and the LOWEST-scoring trial is represented: a later good trial can
never hide an earlier failure. The full, untruncated text is written to
``feedback_full/<name>.md``; the entry ends with a pointer to it.

The summarizer is configured by the environment only, never by the run spec, so the
same run can use any model (``CAPEVOLVE_FEEDBACK_SUMMARY_MODEL``, else the Claude
default haiku alias ``ANTHROPIC_DEFAULT_HAIKU_MODEL``, else ``claude-haiku-4-5``) on any
Anthropic-Messages gateway (``CAPEVOLVE_FEEDBACK_SUMMARY_BASE_URL`` /
``CAPEVOLVE_FEEDBACK_SUMMARY_API_KEY``, else ``ANTHROPIC_BASE_URL`` /
``ANTHROPIC_AUTH_TOKEN`` or ``ANTHROPIC_API_KEY``). ``CAPEVOLVE_FEEDBACK_SUMMARY=off``
keeps the deterministic fallback only; ``CAPEVOLVE_FEEDBACK_SUMMARY_MAX_TOKENS`` sets the
output budget per call (default 32000). Pure stdlib.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import urllib.request
from pathlib import Path

ENV_CHARS = "CAPEVOLVE_FEEDBACK_ENTRY_CHARS"
DEFAULT_CHARS = 800
BATCH = 10
DIR = "feedback_full"
_LINK_RE = re.compile(r"\./" + DIR + r"/([A-Za-z0-9._-]+\.md)")
# A trial label line, as harness._join_trial_feedback writes it.
_LABEL_RE = re.compile(r"^\[((?:\S+ )?trial \d+[^\]\n]*)\]$", re.MULTILINE)
_TRIAL_RE = re.compile(r"((?:\S+ )?trial \d+)(?: (errored)| reward (-?[0-9.]+))?")


def entry_chars() -> int:
    try:
        return max(200, int(os.environ.get(ENV_CHARS) or DEFAULT_CHARS))
    except ValueError:
        return DEFAULT_CHARS


# ---- parsing the joined multi-trial text --------------------------------------------

def trials_of(pt: dict) -> list[tuple[str, float | None, str]]:
    """``[(trial name, reward or None, text)]`` for one per-task row.

    A row joined by ``harness._join_trial_feedback`` carries ``[trial k reward r]`` label
    lines; each label may name several trials that gave the same text. A row without
    labels is one block, rewarded with the row's own reward.
    """
    fb = str(pt.get("feedback") or "").strip()
    marks = list(_LABEL_RE.finditer(fb))
    if not marks:
        return [("", _num(pt.get("reward")), fb)] if fb else []
    out = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(fb)
        text = fb[m.end():end].strip()
        for part in m.group(1).split(", "):     # one label may name several trials
            t = _TRIAL_RE.fullmatch(part.strip())
            if t:
                out.append((t.group(1), None if t.group(2) else _num(t.group(3)), text))
    return out


def _num(x) -> float | None:
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        return None


def _lowest(trials):
    """The lowest-scoring scored trial (errored trials only when nothing was scored)."""
    scored = [t for t in trials if t[1] is not None]
    return min(scored, key=lambda t: t[1]) if scored else (trials[0] if trials else None)


def header(pt: dict) -> str:
    """The code-written first line of a condensed entry: every trial's reward, lowest marked."""
    trials = trials_of(pt)
    if len(trials) <= 1:
        return ""
    low = _lowest(trials)
    parts = []
    for name, r, _ in trials:
        s = f"{name} " + ("errored" if r is None else f"{r:.3f}")
        parts.append(s + (" (lowest)" if (name, r) == (low[0], low[1]) else ""))
    return "trials: " + ", ".join(parts)


# ---- the deterministic fallback -----------------------------------------------------

def middle_cut(text: str, n: int) -> str:
    """``text`` cut to at most ``n`` chars from the MIDDLE: a judge's verdict is often last."""
    text = text.strip()
    if len(text) <= n:
        return text
    mark = " … "
    head = max(0, int((n - len(mark)) * 0.35))
    return text[:head].rstrip() + mark + text[len(text) - (n - len(mark) - head):].lstrip()


def fallback(pt: dict, budget: int) -> str:
    """A bounded entry without a model: the lowest trial's text first, then the best one's."""
    trials = trials_of(pt)
    if not trials:
        return ""
    head_line = header(pt)
    room = budget - len(head_line) - (1 if head_line else 0)
    if len(trials) == 1 or len({t[2] for t in trials}) == 1:
        body = middle_cut(trials[0][2], room)
    else:
        low = _lowest(trials)
        scored = [t for t in trials if t[1] is not None and t[2] != low[2]]
        best = max(scored, key=lambda t: t[1]) if scored else None
        low_txt = f"lowest ({low[0]}): "
        if best is None or room < 300:
            body = low_txt + middle_cut(low[2], room - len(low_txt))
        else:
            best_txt = f"\nbest ({best[0]}): "
            low_room = int((room - len(low_txt) - len(best_txt)) * 0.65)
            body = (low_txt + middle_cut(low[2], low_room) + best_txt
                    + middle_cut(best[2], room - len(low_txt) - len(best_txt) - low_room))
    return (head_line + "\n" + body) if head_line else body


# ---- full text on disk --------------------------------------------------------------

def _file_name(task_id, text: str) -> str:
    """Content-addressed, so concurrent candidates with different parents never collide."""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", str(task_id)).strip("._")[:120] or "task"
    return f"{safe}-{hashlib.sha256(text.encode('utf-8')).hexdigest()[:10]}.md"


def store_full(run_dir, pt: dict) -> str:
    """Write the row's full feedback under the run dir; return its prompt-relative link."""
    fb = str(pt.get("feedback") or "")
    name = _file_name(pt.get("task_id"), fb)
    root = Path(run_dir.root) / DIR
    path = root / name
    if not path.exists():
        root.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {pt.get('task_id')} — full scorer feedback (reward "
                        f"{float(pt.get('reward', 0) or 0):.3f})\n\n{fb}\n", encoding="utf-8")
    return f"./{DIR}/{name}"


def copy_linked(instructions: str, workdir: Path, run_dir) -> int:
    """Copy every ``./feedback_full/<name>.md`` the prompt links to into the optimizer's workdir."""
    return 0 if run_dir is None else _copy(instructions, Path(run_dir.root) / DIR, Path(workdir))


def copy_linked_from(instructions: str, workdir: Path) -> int:
    """``copy_linked`` for a workdir under the run dir (``<run>/work/<cid>``): the files are
    found by walking up from it, so the optimizer runner needs no run-dir handle."""
    for up in Path(workdir).resolve().parents:
        if (up / DIR).is_dir():
            return _copy(instructions, up / DIR, Path(workdir))
    return 0


def _copy(instructions: str, src_root: Path, workdir: Path) -> int:
    names = set(_LINK_RE.findall(instructions or ""))
    if not names:
        return 0
    dst_root = workdir / DIR
    dst_root.mkdir(parents=True, exist_ok=True)
    n = 0
    for name in names:
        src = src_root / name
        if src.is_file():
            shutil.copyfile(src, dst_root / name)
            n += 1
    return n


# ---- the summarizer -----------------------------------------------------------------

def summarizer_config() -> dict | None:
    """Model + gateway from the environment, or None (fallback only)."""
    if str(os.environ.get("CAPEVOLVE_FEEDBACK_SUMMARY", "")).lower() in ("off", "0", "false", "no"):
        return None
    base = (os.environ.get("CAPEVOLVE_FEEDBACK_SUMMARY_BASE_URL") or os.environ.get("ANTHROPIC_BASE_URL")
            or "https://api.anthropic.com")
    key = os.environ.get("CAPEVOLVE_FEEDBACK_SUMMARY_API_KEY")
    bearer = key or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    api_key = None if key else os.environ.get("ANTHROPIC_API_KEY")
    if not (bearer or api_key):
        return None
    model = (os.environ.get("CAPEVOLVE_FEEDBACK_SUMMARY_MODEL") or os.environ.get("ANTHROPIC_DEFAULT_HAIKU_MODEL")
             or "claude-haiku-4-5")
    return {"base_url": base.rstrip("/"), "model": model, "bearer": bearer, "api_key": api_key}


_INSTRUCTIONS = """You condense scorer feedback for an optimizer that improves an AI agent.
Each task below has one or more trials. A trial's feedback explains why it got its reward (often the
rationale of an LLM judge). For EACH task, write a summary of at most {n} characters that keeps:
1. the issues of the LOWEST-scoring trial, first, in the scorer's own terms;
2. the issues that recur across trials;
3. when trials differ, what the higher-scoring trials did differently.
Rules: keep scores and verdicts exactly as the scorer states them. Do not invent facts, causes or
advice the feedback does not contain. No preamble.
Reply with ONLY a JSON object that maps each task id to its summary string."""


def _max_tokens() -> int:
    """Output budget per call. Generous: a reasoning model (GLM, for example) may think for many
    thousand tokens before it writes the JSON; 10 summaries themselves need about 3k."""
    try:
        return max(1024, int(os.environ.get("CAPEVOLVE_FEEDBACK_SUMMARY_MAX_TOKENS") or 32000))
    except ValueError:
        return 32000


def _call(cfg: dict, prompt: str, timeout: float = 600.0) -> str:
    headers = {"content-type": "application/json", "anthropic-version": "2023-06-01"}
    if cfg.get("bearer"):
        headers["authorization"] = f"Bearer {cfg['bearer']}"
    if cfg.get("api_key"):
        headers["x-api-key"] = cfg["api_key"]
    body = json.dumps({"model": cfg["model"], "max_tokens": _max_tokens(),
                       "messages": [{"role": "user", "content": prompt}]}).encode("utf-8")
    req = urllib.request.Request(cfg["base_url"] + "/v1/messages", data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — configured gateway URL
        data = json.loads(resp.read().decode("utf-8"))
    text = "".join(b.get("text", "") for b in data.get("content") or [] if b.get("type") == "text")
    if not text.strip() and data.get("stop_reason") == "max_tokens":
        raise ValueError(f"the reply hit max_tokens ({_max_tokens()}) before any text "
                         "(raise CAPEVOLVE_FEEDBACK_SUMMARY_MAX_TOKENS)")
    return text


def _parse(reply: str) -> dict:
    s, e = reply.find("{"), reply.rfind("}")
    if s < 0 or e <= s:
        raise ValueError("no JSON object in the summarizer reply")
    obj = json.loads(reply[s:e + 1])
    if not isinstance(obj, dict):
        raise ValueError("summarizer reply is not a JSON object")
    return {str(k): str(v) for k, v in obj.items()}


def summarize_batches(rows: list[dict], budget: int, cfg: dict, call=_call) -> tuple[dict, list[str]]:
    """``({task_id: summary}, [errors])`` for ``rows``, ``BATCH`` tasks per model call."""
    out, errors = {}, []
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        tasks = []
        for pt in chunk:
            trials = trials_of(pt)
            tasks.append({"task_id": str(pt.get("task_id")), "mean_reward": _num(pt.get("reward")),
                          "trials": [{"trial": n or "only", "reward": r, "feedback": t} for n, r, t in trials]})
        prompt = _INSTRUCTIONS.format(n=budget) + "\n\nTASKS:\n" + json.dumps(tasks, ensure_ascii=False, indent=1)
        try:
            got = _parse(call(cfg, prompt))
        except Exception as e:  # noqa: BLE001 — one bad batch never costs the iteration
            errors.append(f"batch {i // BATCH}: {type(e).__name__}: {str(e)[:200]}")
            continue
        for pt in chunk:
            s = got.get(str(pt.get("task_id")), "").strip()
            if s:
                out[str(pt.get("task_id"))] = s
    return out, errors


def _cache_path(run_dir) -> Path:
    return Path(run_dir.root) / "feedback_summaries.json"


def condense(rows: list[dict], run_dir=None, *, call=_call) -> dict:
    """``{task_id: bounded entry body}`` for every row whose feedback is over the bound.

    Rows within the bound are not returned (shown as they are). With ``run_dir`` the
    summarizer runs and its results are cached there by content, so an unchanged task is
    never summarized twice; without it (or with no summarizer configured) every long row
    gets the deterministic ``fallback``.
    """
    n = entry_chars()
    long_rows = [pt for pt in rows if len(str(pt.get("feedback") or "").strip()) > n]
    if not long_rows:
        return {}
    budgets = {str(pt.get("task_id")): n - len(header(pt)) - 1 for pt in long_rows}
    cfg = summarizer_config() if run_dir is not None else None
    out: dict = {}
    cache: dict = {}
    if cfg is not None:
        try:
            cache = json.loads(_cache_path(run_dir).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            cache = {}
        key = lambda pt: hashlib.sha256(f"{cfg['model']}|{n}|{pt.get('feedback')}".encode("utf-8")).hexdigest()
        todo = [pt for pt in long_rows if key(pt) not in cache]
        errors: list[str] = []
        if todo:
            got, errors = summarize_batches(todo, max(150, min(budgets.values())), cfg, call=call)
            for pt in todo:
                s = got.get(str(pt.get("task_id")))
                if s:
                    cache[key(pt)] = s
            try:
                _cache_path(run_dir).write_text(json.dumps(cache), encoding="utf-8")
            except OSError:
                pass
        used = 0
        for pt in long_rows:
            s = cache.get(key(pt))
            if s:
                tid, h = str(pt.get("task_id")), header(pt)
                out[tid] = ((h + "\n") if h else "") + middle_cut(s, budgets[tid])
                used += 1
        if hasattr(run_dir, "log_event"):
            run_dir.log_event("feedback_summary", model=cfg["model"], long=len(long_rows), summarized=used,
                              fallback=len(long_rows) - used, calls=-(-len(todo) // BATCH) if todo else 0,
                              errors=errors[:5])
    for pt in long_rows:
        out.setdefault(str(pt.get("task_id")), fallback(pt, n))
    return out
