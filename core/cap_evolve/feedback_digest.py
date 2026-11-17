"""Per-trial scorer feedback for the optimizer: one shared format, one budget per prompt.

A scorer's feedback (an LLM judge's rationale above all) can run to thousands of
characters per trial, times every trial. This module is the ONE place that handles it:

* **The trial-label grammar.** ``join_trial_feedback`` joins a task's trials into one text,
  each distinct text under a ``[trial k reward r]`` label (``[trial k errored]`` for an
  infra error); ``pooled_feedback`` puts several evaluations of one candidate under
  ``[evaluation i of n]`` lines; ``trials_of`` parses both back; ``strip_labels`` removes
  them. Core, HC2, SkillOpt and agent-optimize all go through these functions.

* **One feedback budget per optimizer prompt** (``CAPEVOLVE_FEEDBACK_BUDGET_BYTES``,
  default ``DEFAULT_BUDGET``). It covers ALL feedback text in one prompt: the failure
  index, GEPA's reflection, SkillOpt's slow/meta-update block. ``fit`` shares it between
  the tasks of one block: when everything fits, every entry is shown in full and nothing
  is summarized; otherwise only the LONGEST entries are condensed, all to one common size
  chosen so the block fills the budget (short entries keep their text, and what they leave
  goes to the long ones), and only as many tasks are listed as can each get a useful
  ``MIN_ENTRY`` bytes; the rest are named. It is in UTF-8 bytes because that is what the
  optimizer row's inline-argv limit counts (``run-optimizer``'s ``MAX_INLINE_PROMPT_BYTES``).

* **Condensing.** A condensed entry is summarized by the run's OWN optimizer (the same
  agent CLI, model and budget flags the algorithm proposes edits with), or, without one or
  when a call gives no usable result, cut deterministically by ``fallback``. Either way it
  starts with a code-written, bounded ``trials:`` line (every trial's reward, the lowest
  marked) and represents the LOWEST-scoring trial: a later good trial can never hide an
  earlier failure. Its full text is written to ``<run>/feedback_full/<name>.md`` and
  linked; ``provide_linked`` copies the linked files into the optimizer's workdir.

The summary calls count as optimizer spend, are not started when the run's USD budget has
no room for them, and run at the run's ``workers`` concurrency.
``CAPEVOLVE_FEEDBACK_SUMMARY=off`` keeps the deterministic cut only. Pure stdlib.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

ENV_BUDGET = "CAPEVOLVE_FEEDBACK_BUDGET_BYTES"
#: The default feedback budget of one optimizer prompt. The rest of a rendered prompt (the
#: template, the capability and algorithm briefs, the passing-task ids, section headers) is
#: about 25 KB, so the whole prompt stays well under the 96 KiB inline-argv limit.
DEFAULT_BUDGET = 48_000
MIN_BUDGET = 4_000
#: The smallest condensed entry body worth showing: a task that cannot get this much is
#: named, not listed.
MIN_ENTRY = 300
DIR = "feedback_full"
LINK_RE = re.compile(r"\./" + DIR + r"/([A-Za-z0-9._-]+\.md)")

# ---- the trial-label grammar ------------------------------------------------------------

#: A trial label line, e.g. ``[trial 0 reward 0.500, trial 2 errored]`` (``<tag> trial k``
#: when several tags' rollouts are pooled).
TRIAL_LABEL_RE = re.compile(r"^\[((?:\S+ )?trial \d+[^\]\n]*)\]$", re.MULTILINE)
#: A pooled evaluation's header line, e.g. ``[evaluation 1 of 2]``.
EVAL_LABEL_RE = re.compile(r"^\[evaluation (\d+) of (\d+)\]$", re.MULTILINE)
#: Either label line.
LABEL_LINE_RE = re.compile(r"^\[(?:(?:\S+ )?trial \d+[^\]\n]*|evaluation \d+ of \d+)\]$", re.MULTILINE)
_TRIAL_RE = re.compile(r"((?:\S+ )?trial \d+)(?: (errored)| reward (-?[0-9.]+))?")
#: The text shown under trials that gave no feedback, so their rewards are still listed.
NO_FEEDBACK = "(no feedback)"


def join_trial_feedback(trials: list) -> str:
    """One task's feedback from ALL its trials, each labelled with that trial's reward.

    ``trials`` is ``[(trial_label, reward_or_None, feedback)]``; the label is the trial index,
    or ``"<tag> <index>"`` when several tags' rollouts are pooled; a reward of ``None`` is an
    errored trial (it never ran the target). The text is returned unlabelled only when every
    trial gave the SAME text and none errored. Otherwise each distinct text is kept once,
    under the trials that produced it, and trials that gave no text are listed under
    ``(no feedback)``: an LLM judge's verdict varies between trials, the last one alone may
    praise a task whose mean is low, and an infra error must never read as a capability
    failure. Never shortened here: ``fit`` bounds the prompt, the full text stays on disk.
    """
    def order(t):   # by tag, then numerically by trial index
        tag, _, k = str(t[0]).rpartition(" ")
        return tag, int(k)

    def name(k) -> str:
        tag, _, i = str(k).rpartition(" ")
        return f"{tag} trial {i}" if tag else f"trial {i}"

    rows = [(k, r, str(fb or "").strip()) for k, r, fb in sorted(trials, key=order)]
    texts = [fb for _, _, fb in rows if fb]
    if not texts:
        return ""
    if len(set(texts)) == 1 and len(texts) == len(rows) and all(r is not None for _, r, _ in rows):
        return texts[0]
    by_text: dict[str, list] = {}
    for k, r, fb in rows:
        by_text.setdefault(fb or NO_FEEDBACK, []).append((k, r))
    out = []
    for fb, ks in by_text.items():
        head = ", ".join(name(k) + (" errored" if r is None else f" reward {float(r):.3f}") for k, r in ks)
        out.append(f"[{head}]\n{fb}")
    return "\n\n".join(out)


def has_labels(text: str) -> bool:
    return bool(LABEL_LINE_RE.search(str(text or "")))


def label_unlabelled(text: str, trial_rewards) -> str:
    """``text`` under a label naming every trial, when it has no labels yet.

    ``join_trial_feedback`` leaves a text unlabelled only when all trials gave it; once two
    evaluations are pooled side by side, each needs its rewards stated again.
    """
    text = str(text or "").strip()
    if not text or has_labels(text) or not trial_rewards:
        return text
    head = ", ".join(f"trial {k} reward {float(r):.3f}" for k, r in enumerate(trial_rewards))
    return f"[{head}]\n{text}"


def pooled_feedback(parts: list) -> str:
    """One task's feedback from several pooled evaluations of the same candidate.

    ``parts`` holds one ``(text, trial_rewards or None)`` per evaluation, distinct texts only.
    One part is returned as it is. Several are each put under an ``[evaluation i of n]``
    line (every evaluation numbers its own trials from 0), each one labelled.
    """
    parts = [(str(t or "").strip(), r) for t, r in parts if str(t or "").strip()]
    if len(parts) <= 1:
        return parts[0][0] if parts else ""
    return "\n\n".join(f"[evaluation {i} of {len(parts)}]\n{label_unlabelled(t, r)}"
                       for i, (t, r) in enumerate(parts, 1))


def strip_labels(text: str) -> str:
    """``text`` without its trial and evaluation label lines."""
    return LABEL_LINE_RE.sub("", str(text or "")).strip()


def _num(x) -> float | None:
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        return None


def trials_of(pt: dict) -> list[tuple[str, float | None, str]]:
    """``[(trial name, reward or None, text)]`` for one per-task row; no text is ever dropped.

    Trial names are unique: inside a pooled ``[evaluation i of n]`` section they are prefixed
    ``e<i>``. Text with no trial label (a whole row, or a section, that every trial agreed
    on) is one block with the row's mean reward.
    """
    fb = str(pt.get("feedback") or "").strip()
    if not fb:
        return []
    row_r = _num(pt.get("reward"))
    evals = list(EVAL_LABEL_RE.finditer(fb))
    sections: list[tuple[str, str]] = []          # (name prefix, text)
    if not evals:
        sections.append(("", fb))
    else:
        if fb[:evals[0].start()].strip():
            sections.append(("", fb[:evals[0].start()]))
        for i, m in enumerate(evals):
            end = evals[i + 1].start() if i + 1 < len(evals) else len(fb)
            sections.append((f"e{m.group(1)} ", fb[m.end():end]))
    out = []
    for prefix, sec in sections:
        sec = sec.strip()
        marks = list(TRIAL_LABEL_RE.finditer(sec))
        lead = sec[:marks[0].start()].strip() if marks else sec
        if lead:
            out.append((f"evaluation {prefix[1:].strip()}" if prefix else ("" if not marks else "unlabelled"),
                        row_r, lead))
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(sec)
            text = sec[m.end():end].strip()
            for part in m.group(1).split(", "):     # one label may name several trials
                t = _TRIAL_RE.fullmatch(part.strip())
                if t:
                    out.append((prefix + t.group(1), None if t.group(2) else _num(t.group(3)), text))
    return out


def _lowest_index(trials) -> int | None:
    """The lowest-scoring scored trial (an errored one only when nothing was scored)."""
    scored = [i for i, t in enumerate(trials) if t[1] is not None]
    if scored:
        return min(scored, key=lambda i: trials[i][1])
    return 0 if trials else None


def header(pt: dict, limit: int | None = None) -> str:
    """The code-written first line of a condensed entry: every trial's reward, lowest marked.

    Over ``limit`` bytes (many pooled trials, long tag names) it becomes a compact line: the
    trial count, the reward range and the lowest trial.
    """
    trials = trials_of(pt)
    if len(trials) <= 1:
        return ""
    low = _lowest_index(trials)
    parts = []
    for i, (name, r, _) in enumerate(trials):
        s = f"{name} " + ("errored" if r is None else f"{r:.3f}")
        parts.append(s + (" (lowest)" if i == low else ""))
    full = "trials: " + ", ".join(parts)
    if limit is None or _size(full) <= limit:
        return full
    scored = [r for _, r, _ in trials if r is not None]
    n_err = len(trials) - len(scored)
    lname, lr = trials[low][0], trials[low][1]
    compact = (f"trials: {len(trials)}" + (f" ({n_err} errored)" if n_err else "")
               + (f", rewards {min(scored):.3f} to {max(scored):.3f}" if scored else "")
               + f", lowest: {lname} " + ("errored" if lr is None else f"{lr:.3f}"))
    return compact if _size(compact) <= limit else _clip(compact, limit)


# ---- sizes and cuts ---------------------------------------------------------------------

def _size(s: str) -> int:
    return len(s.encode("utf-8"))


def middle_cut(text: str, n: int) -> str:
    """``text`` cut to at most ``n`` chars from the MIDDLE: a judge's verdict is often last."""
    text = text.strip()
    if len(text) <= n:
        return text
    mark = " … "
    if n < 4 * len(mark):
        return text[:max(0, n)]
    head = max(0, int((n - len(mark)) * 0.35))
    return text[:head].rstrip() + mark + text[len(text) - (n - len(mark) - head):].lstrip()


def _clip(text: str, n: int, measure=None) -> str:
    """``middle_cut`` of ``text`` to at most ``n`` by ``measure`` (UTF-8 bytes by default).

    Always cuts the ORIGINAL text (shrinking the char target), so there is one cut mark."""
    measure = measure or _size
    text = str(text or "").strip()
    if measure(text) <= n:
        return text
    m = min(len(text), max(0, n))
    for _ in range(12):
        out = middle_cut(text, m)
        over = measure(out) - n
        if over <= 0:
            return out
        m = max(0, m - max(1, over))
    return text.encode("utf-8")[:max(0, n)].decode("utf-8", errors="ignore")


def render(head: str, body: str, link: str | None = None) -> str:
    """One listed entry: ``head`` then the body, every continuation line indented two spaces
    (so a multi-line body stays inside its markdown list item), then the link line."""
    out = head + body.replace("\n", "\n  ")
    if link:
        out += _link_line(link)
    return out


def _link_line(link: str) -> str:
    return f"\n  (full feedback, every trial: {link})"


def _rendered_size(body: str) -> int:
    return _size(body) + 2 * body.count("\n")


def _fit_rendered(body: str, n: int) -> str:
    """``body`` at a RENDERED size (with ``render``'s indentation) of at most ``n``: a safety
    net, since the pieces are sized to fit already."""
    return body if _rendered_size(body) <= n else _clip(body, n, _rendered_size)


def _join_lines(first: str, rest: str, n: int) -> str:
    """``first`` (the header, may be empty), then ``rest`` cut to what remains of ``n``."""
    if not first:
        return _clip(rest, n, _rendered_size)
    room = n - _rendered_size(first) - 3          # the newline and its two-space indent
    return first + "\n" + _clip(rest, max(0, room), _rendered_size)


def fallback(pt: dict, n: int) -> str:
    """A body of at most ``n`` rendered bytes, without a model: the bounded ``trials:`` line,
    then the lowest trial's text, then the best one's."""
    trials = trials_of(pt)
    if not trials:
        return ""
    h = header(pt, max(40, n // 3))
    room = n - (_rendered_size(h) + 3 if h else 0)
    clip = lambda t, k: _clip(t, max(0, k), _rendered_size)
    if len({t[2] for t in trials}) == 1:
        body = clip(trials[0][2], room)
    else:
        low = trials[_lowest_index(trials)]
        scored = [t for t in trials if t[1] is not None and t[2] != low[2]]
        best = max(scored, key=lambda t: t[1]) if scored else None
        low_txt = f"lowest ({low[0] or 'only trial'}): "
        if best is None or room < MIN_ENTRY:
            body = low_txt + clip(low[2], room - _size(low_txt))
        else:
            best_txt = f"\nbest ({best[0]}): "
            avail = room - _size(low_txt) - _rendered_size(best_txt)
            low_room = int(avail * 0.65)
            body = low_txt + clip(low[2], low_room) + best_txt + clip(best[2], avail - low_room)
    return _fit_rendered((h + "\n" + body) if h else body, n)


# ---- the budget -------------------------------------------------------------------------

def budget_bytes() -> int:
    """The feedback budget of one optimizer prompt (``CAPEVOLVE_FEEDBACK_BUDGET_BYTES``)."""
    try:
        return max(MIN_BUDGET, int(os.environ.get(ENV_BUDGET) or DEFAULT_BUDGET))
    except ValueError:
        return DEFAULT_BUDGET


class Budget:
    """What is left of one optimizer prompt's feedback budget, shared by its blocks."""

    def __init__(self, total: int | None = None):
        self.total = budget_bytes() if total is None else max(0, int(total))
        self.used = 0

    @property
    def left(self) -> int:
        return max(0, self.total - self.used)

    def spend(self, n: int) -> None:
        self.used += max(0, int(n))


def rest_line(rest: list[dict]) -> str:
    """The line naming the tasks the budget left out (at most 60 ids, then a count)."""
    if not rest:
        return ""
    ids = [str(pt.get("task_id")) for pt in rest]
    named = ", ".join(ids[:60]) + (f" … (+{len(ids) - 60} more)" if len(ids) > 60 else "")
    return (f"(+{len(rest)} more failing task(s) not listed, over the feedback budget "
            f"({ENV_BUDGET}): {named}. Their traces are in ./trajectories/.)")


@dataclass
class Fit:
    """``fit``'s result: the rendered entry of every listed task, in order."""
    entries: dict = field(default_factory=dict)     # task id -> rendered entry
    shown: list = field(default_factory=list)       # listed rows, in the given order
    rest: list = field(default_factory=list)        # rows over the budget (name them)
    used: int = 0                                   # bytes: entries + the rest line
    condensed: int = 0
    cut: int | None = None                          # the common condensed body size, if any

    @property
    def rest_line(self) -> str:
        return rest_line(self.rest)


def fit(rows: list[dict], limit: int, *, head=lambda pt: "", run_dir=None, optimizer=None) -> Fit:
    """Share ``limit`` bytes between ``rows`` (most important first) and render their entries.

    * Everything fits: every entry in full, nothing summarized.
    * Otherwise as many rows are listed as can each get ``MIN_ENTRY`` bytes (a short entry
      costs only its own size), and the rest are named in ``rest_line``.
    * The listed rows share the room: the largest common cap ``c`` is found such that each
      entry shorter than ``c`` is shown in full and each longer one is condensed to ``c``;
      what short entries do not use goes to the long ones.

    ``head(pt)`` is each entry's first-line prefix (``"- t7 (reward 0.00): "``). With
    ``run_dir`` a condensed entry's full text is written there and linked; with the run's
    ``optimizer`` too, condensed entries are summarized by it (``_summaries``).
    """
    if not rows:
        return Fit()
    heads = [head(pt) for pt in rows]
    full = [render(h, str(pt.get("feedback") or "").strip()) for h, pt in zip(heads, rows)]
    sizes = [_size(e) for e in full]
    if sum(sizes) <= limit:
        return Fit(entries={str(pt.get("task_id")): e for pt, e in zip(rows, full)},
                   shown=list(rows), used=sum(sizes))
    links = [link_for(pt) if run_dir is not None else None for pt in rows]
    link_sz = [_size(_link_line(lk)) if lk else 0 for lk in links]
    head_sz = [_size(h) for h in heads]

    def cost(i, c):
        return sizes[i] if sizes[i] - head_sz[i] <= c else head_sz[i] + c + link_sz[i]

    n = len(rows)
    while n > 1 and sum(cost(i, MIN_ENTRY) for i in range(n)) + _size(rest_line(rows[n:])) > limit:
        n -= 1
    room = limit - _size(rest_line(rows[n:]))
    lo = MIN_ENTRY if sum(cost(i, MIN_ENTRY) for i in range(n)) <= room else \
        max(40, room - head_sz[0] - link_sz[0])
    hi = max(lo, max(sizes[i] - head_sz[i] for i in range(n)))
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if sum(cost(i, mid) for i in range(n)) <= room:
            lo = mid
        else:
            hi = mid - 1
    c = lo
    shown = rows[:n]
    long_rows = [pt for i, pt in enumerate(shown) if sizes[i] - head_sz[i] > c]
    bodies = _condense(long_rows, c, run_dir, optimizer)
    entries = {}
    for i, pt in enumerate(shown):
        tid = str(pt.get("task_id"))
        if tid in bodies:
            link = store_full(run_dir, pt) if run_dir is not None else None
            entries[tid] = render(heads[i], bodies[tid], link)
        else:
            entries[tid] = full[i]
    used = sum(_size(e) for e in entries.values()) + _size(rest_line(rows[n:]))
    return Fit(entries=entries, shown=shown, rest=rows[n:], used=used, condensed=len(bodies), cut=c)


# ---- full text on disk ------------------------------------------------------------------

def _file_name(task_id, text: str) -> str:
    """Content-addressed, so concurrent candidates with different parents never collide."""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", str(task_id)).strip("._")[:120] or "task"
    return f"{safe}-{hashlib.sha256(text.encode('utf-8')).hexdigest()[:10]}.md"


def link_for(pt: dict) -> str:
    return f"./{DIR}/{_file_name(pt.get('task_id'), str(pt.get('feedback') or ''))}"


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


def provide_linked(instructions: str, workdir, run_dir) -> int:
    """Copy every ``./feedback_full/<name>.md`` the prompt links to into ``workdir``.

    Called where the algorithm hands the prompt to its optimizer, for EVERY kind of
    ``OptimizerFn`` and wherever its workdir is. Returns the number of files copied.
    """
    if run_dir is None:
        return 0
    names = set(LINK_RE.findall(instructions or ""))
    if not names:
        return 0
    src_root, dst_root = Path(run_dir.root) / DIR, Path(workdir) / DIR
    dst_root.mkdir(parents=True, exist_ok=True)
    n = 0
    for name in names:
        src = src_root / name
        if src.is_file():
            shutil.copyfile(src, dst_root / name)
            n += 1
    return n


# ---- the summarizer: the run's own optimizer -------------------------------------------

def enabled() -> bool:
    return str(os.environ.get("CAPEVOLVE_FEEDBACK_SUMMARY", "")).lower() not in ("off", "0", "false", "no")


_RULES = """You condense scorer feedback for an optimizer that improves an AI agent. This is NOT an
editing task: do not change, create or delete any file except ./summaries.json.

Each file in ./tasks/ is one task: its trials, each trial's reward, and each trial's feedback
(often the rationale of an LLM judge). Read EVERY file in full.

For EACH task write a summary of at most {n} characters that keeps:
1. the issues of the LOWEST-scoring trial, first, in the scorer's own terms;
2. the issues that recur across trials;
3. when trials differ, what the higher-scoring trials did differently.
Keep scores and verdicts exactly as the scorer states them. Do not invent facts, causes or
advice the feedback does not contain. No preamble.

Write ./summaries.json: ONE JSON object that maps each task id below to its summary string.
Then stop.

Task ids (file -> id):
{index}
"""


def _write_batch(workdir: Path, rows: list[dict], target: int) -> str:
    """The batch as one markdown file per task, plus the instructions; returns the prompt."""
    (workdir / "tasks").mkdir(parents=True, exist_ok=True)
    index = []
    for i, pt in enumerate(rows):
        name = f"tasks/{i:02d}.md"
        lines = [f"# task {pt.get('task_id')}", f"mean reward: {_num(pt.get('reward'))}", ""]
        for t, r, text in trials_of(pt):
            lines += [f"## {t or 'only trial'} - " + ("errored (no reward)" if r is None else f"reward {r:.3f}"),
                      "", text, ""]
        (workdir / name).write_text("\n".join(lines), encoding="utf-8")
        index.append(f"- {name} -> {pt.get('task_id')}")
    return _RULES.format(n=target, index="\n".join(index))


def _read_summaries(workdir: Path) -> dict:
    obj = json.loads((workdir / "summaries.json").read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("summaries.json is not a JSON object")
    return {str(k): str(v) for k, v in obj.items()}


def batches(rows: list[dict], limit: int) -> list[list[dict]]:
    """``rows`` in order, packed into batches of at most ``limit`` bytes of feedback each (a
    row larger than ``limit`` alone is its own batch). A summary call reads no more feedback
    than one optimizer prompt may carry."""
    out: list[list[dict]] = []
    cur, cur_sz = [], 0
    for pt in rows:
        sz = _size(str(pt.get("feedback") or ""))
        if cur and cur_sz + sz > limit:
            out.append(cur)
            cur, cur_sz = [], 0
        cur.append(pt)
        cur_sz += sz
    if cur:
        out.append(cur)
    return out


def _workers() -> int:
    """The run's own concurrency setting (``--workers`` / ``CAPEVOLVE_WORKERS``)."""
    from .harness import _resolve_workers
    return _resolve_workers(None)


def usd_headroom(run_dir) -> float | None:
    """USD the run may still spend on the optimizer (the tighter of ``max_optimizer_usd`` and
    ``max_usd``), or None when neither is set."""
    try:
        b, s = run_dir.budget, run_dir.spent
    except Exception:  # noqa: BLE001 — a run dir double without budgets
        return None
    caps = []
    if getattr(b, "max_optimizer_usd", 0):
        caps.append(float(b.max_optimizer_usd) - float(s.optimizer_usd))
    if getattr(b, "max_usd", 0):
        caps.append(float(b.max_usd) - float(s.total_usd))
    return min(caps) if caps else None


def summarize_batches(chunks: list[list[dict]], target: int, optimizer, scratch: Path,
                      run_dir=None, workers: int | None = None) -> tuple[dict, list[str], int]:
    """``({task_id: summary}, [errors], skipped)``: ``optimizer(workdir, prompt)`` once per
    batch, each in its own workdir under ``scratch``, at most ``workers`` calls at a time.

    Before each wave of calls the run's USD headroom is checked: none left, no more calls
    (``skipped`` batches fall back). While the cost of one call is not yet known the first
    wave is a single call; after that a wave is as many calls as the headroom pays for, at
    the mean cost seen so far. Every call's cost counts as optimizer spend, a failed one too.
    """
    workers = max(1, int(workers or _workers()))

    def one(k):
        wd = scratch / f"batch_{k:02d}"
        t0 = time.time()
        try:
            report = optimizer(wd, _write_batch(wd, chunks[k], target)) or {}
        except Exception as e:  # noqa: BLE001 — one bad batch never costs the iteration
            report, err = getattr(e, "cost", None) or {}, f"batch {k}: {type(e).__name__}: {str(e)[:200]}"
        else:
            err = None
        usd = float(report.get("cost_usd") or 0.0)
        if run_dir is not None and hasattr(run_dir, "update_spent"):
            run_dir.update_spent(optimizer_seconds=time.time() - t0, optimizer_usd=usd,
                                 optimizer_tokens=int(report.get("tokens") or 0))
        if err:
            return {}, err, usd
        try:
            return _read_summaries(wd), None, usd
        except Exception as e:  # noqa: BLE001
            return {}, f"batch {k}: no usable summaries.json ({type(e).__name__}: {str(e)[:150]})", usd

    out, errors, costs = {}, [], []
    todo = list(range(len(chunks)))
    while todo:
        room = usd_headroom(run_dir) if run_dir is not None else None
        if room is None:
            wave = todo[:workers]
        elif room <= 0:
            break
        elif not costs:
            wave = todo[:1]
        else:
            per_call = sum(costs) / len(costs)
            k = workers if per_call <= 0 else min(workers, int(room // per_call))
            if k < 1:
                break
            wave = todo[:k]
        todo = todo[len(wave):]
        with ThreadPoolExecutor(max_workers=len(wave)) as pool:
            for got, err, usd in pool.map(one, wave):
                costs.append(usd)
                if err:
                    errors.append(err)
                for pt_id, text in got.items():
                    if text.strip():
                        out[pt_id] = text.strip()
    return out, errors, len(todo)


def _cache_path(run_dir) -> Path:
    return Path(run_dir.root) / "feedback_summaries.json"


def _read_cache(run_dir) -> dict:
    try:
        obj = json.loads(_cache_path(run_dir).read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except (OSError, ValueError):
        return {}


def _merge_cache(run_dir, new: dict) -> None:
    """Merge ``new`` into the cache file under the run dir's file lock, written atomically:
    concurrent prompt builders never lose each other's (paid-for) summaries."""
    if not new:
        return
    from .rundir import _atomic_write, _file_lock
    path = _cache_path(run_dir)
    try:
        with _file_lock(path.with_name(path.name + ".lock")):
            cur = _read_cache(run_dir)
            cur.update(new)
            _atomic_write(path, json.dumps(cur))
    except OSError:
        pass


def _condense(rows: list[dict], c: int, run_dir=None, optimizer=None) -> dict:
    """``{task_id: body}`` of at most ``c`` rendered bytes for each of ``rows``: the run's
    optimizer's summary (cached by content, reused while it fits), else ``fallback``."""
    if not rows:
        return {}
    out: dict = {}
    if run_dir is not None and optimizer is not None and enabled():
        optimizer_key = str(getattr(optimizer, "command", "") or getattr(optimizer, "__qualname__", ""))
        hdr = {str(pt.get("task_id")): header(pt, max(40, c // 3)) for pt in rows}
        room = {tid: c - (_rendered_size(h) + 3 if h else 0) for tid, h in hdr.items()}
        key = lambda pt: hashlib.sha256(
            f"{optimizer_key}|{pt.get('task_id')}|{pt.get('feedback')}".encode("utf-8")).hexdigest()
        cache = _read_cache(run_dir)
        # A cached summary is reused while it fits this prompt's room; a too-long one is redone.
        fits = lambda pt: (key(pt) in cache
                           and _rendered_size(cache[key(pt)]) <= room[str(pt.get("task_id"))])
        todo = [pt for pt in rows if not fits(pt)]
        errors: list[str] = []
        calls = skipped = 0
        if todo:
            target = max(MIN_ENTRY // 2, min(room[str(pt.get("task_id"))] for pt in todo))
            work = Path(run_dir.root) / "work"
            work.mkdir(parents=True, exist_ok=True)
            scratch = Path(tempfile.mkdtemp(prefix="feedback_summary_", dir=work))
            chunks = batches(todo, budget_bytes())
            try:
                got, errors, skipped = summarize_batches(chunks, target, optimizer, scratch, run_dir)
            finally:
                shutil.rmtree(scratch, ignore_errors=True)
            calls = len(chunks) - skipped
            new = {key(pt): got[str(pt.get("task_id"))] for pt in todo if got.get(str(pt.get("task_id")))}
            _merge_cache(run_dir, new)
            cache.update(new)
        for pt in rows:
            tid = str(pt.get("task_id"))
            s = cache.get(key(pt))
            if s:
                out[tid] = _fit_rendered(_join_lines(hdr[tid], s.strip(), c), c)
        if hasattr(run_dir, "log_event"):
            run_dir.log_event("feedback_summary", optimizer=optimizer_key[:200], condensed=len(rows),
                              summarized=len(out), fallback=len(rows) - len(out), cut=c,
                              calls=calls, skipped_for_budget=skipped, errors=errors[:5])
    for pt in rows:
        out.setdefault(str(pt.get("task_id")), fallback(pt, c))
    return out
