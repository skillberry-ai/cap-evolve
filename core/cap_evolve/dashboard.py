"""Observability reducer + renderers for a CapEvolve run. 

This module is the deterministic, stdlib-only builder the ``report`` skill calls.
It does three things:

1. ``reduce_run(run_dir)`` — fold the run dir's append-only ``events.jsonl`` (plus
   ``baseline.json``, ``final.json``, the persisted per-task ``rollouts/``, and the
   git iteration store) into a single ``{graph, summary}`` structure. The event log
   is the source of truth (``rundir`` keeps state.json only as a derived cache), so
   the reducer never trusts state.json for anything it can recompute from events.

2. ``render_html(reduced, run_dir)`` — emit a **self-contained** ``dashboard.html``:
   inline CSS + vanilla JS + inline SVG, no external CDNs, so the file opens offline
   from ``file://`` and is a single shareable artifact.

3. ``render_ansi(reduced, ...)`` — a colored terminal report (KPI strip + cumulative
   best chart + top-N table), sized to the terminal and CLAUDECODE-margin-aware.

Everything that reaches the HTML or the terminal first passes through ``redact`` so a
shared dashboard never leaks a credential pulled in from config/env.

The candidate **graph** schema (``reduced["graph"]``)::

    {"nodes": [
        {"id", "parent", "children": [...], "status": seed|accepted|rejected|failed,
         "val", "stderr", "per_task": {task_id: reward}, "feedback": {task_id: str},
         "cost_usd", "tokens", "seconds", "optimizer_seconds", "runner_seconds",
         "iteration", "reason", "epoch"?, "merge_of"?, "best_so_far"}
     ],
     "root": "seed", "best_id": "..."}

The **summary** schema (``reduced["summary"]``)::

    {"run_id", "baseline_val", "best_val", "delta_pct", "test_reward", "test_sealed",
     "test_pass_k", "counts": {accepted, rejected, failed, seed, total},
     "frontier": int, "tasks": [task_id, ...],
     "wall_clock_seconds", "optimizer_seconds", "runner_seconds",
     "cost": {optimizer_usd, runner_usd, total_usd}, "tokens": int,
     "gate_warnings": [...], "diagnoses": [...], "git_log": [...]}

Optional panels degrade silently: when per-task data / diffs / finalize are missing
the renderer hides the panel rather than crashing.
"""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

# ---------------------------------------------------------------------------
# Secret redaction
# ---------------------------------------------------------------------------

# Case-insensitive regexes over a KEY whose VALUE must be scrubbed before it can
# reach a shared artifact. Covers the providers CapEvolve talks to plus the generic
# shapes (``*_API_KEY``, ``*_TOKEN``, ``*_SECRET`` ...). Note ``token`` is matched as
# a word (``api_token``, ``access-token``) but NOT ``tokens`` — the cost metric — so
# the redactor doesn't eat a legitimate count.
_SECRET_KEY_RES = [
    re.compile(p, re.I) for p in (
        r"api[_\-]?key", r"secret", r"\btokens?\b" if False else r"token(?!s)",
        r"password", r"passwd", r"credential", r"watsonx", r"wx_api",
        r"authorization", r"bearer", r"private[_\-]?key", r"access[_\-]?key",
        r"\bsession\b", r"\bcookie\b",
    )
]

# Value-shaped secrets to mask even when the key looks innocent, and inline
# ``KEY=value`` leaks inside free-text (an optimizer error echoing the environment):
# long hex/base64 blobs, bearer headers, JWTs, the common vendor key prefixes, and
# any ``<SECRET_KEY>=<value>`` pair where the key name itself looks like a secret.
_SECRET_VALUE_RES = [
    re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{12,}\b", re.I),
    re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]{6,}\b"),  # JWT
    re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b"),  # long base64
    re.compile(r"\b[0-9a-fA-F]{40,}\b"),          # long hex
]

# KEY=secret / KEY: secret inside prose — mask the value, keep the key name so the
# message still reads ("RITS_API_KEY=«redacted»"). Two groups: (prefix)(value).
_INLINE_KV_RE = re.compile(
    r"((?:[A-Za-z0-9_\-]*(?:api[_\-]?key|secret|token|password|credential|key)"
    r"[A-Za-z0-9_\-]*)\s*[:=]\s*)(\S+)", re.I)

_REDACTED = "«redacted»"


def _key_is_secret(key: str) -> bool:
    k = str(key)
    return any(rx.search(k) for rx in _SECRET_KEY_RES)


def _scrub_value(val: str) -> str:
    out = _INLINE_KV_RE.sub(lambda m: m.group(1) + _REDACTED, val)
    for rx in _SECRET_VALUE_RES:
        out = rx.sub(_REDACTED, out)
    return out


def redact(obj):
    """Recursively redact secrets from ``obj`` before it reaches an artifact.

    - Dict values under a secret-looking key are replaced wholesale.
    - String values are scanned for secret-shaped tokens and masked in place.
    - Lists/tuples/dicts are walked recursively. Scalars pass through.

    Pure, returns a new structure; the caller's object is untouched.
    """
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if _key_is_secret(k) and v not in (None, "", 0):
                out[k] = _REDACTED
            else:
                out[k] = redact(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [redact(v) for v in obj]
    if isinstance(obj, str):
        return _scrub_value(obj)
    return obj


# ---------------------------------------------------------------------------
# Reducer
# ---------------------------------------------------------------------------

def _safe_subpath(base, *parts) -> Path | None:
    """``base`` joined with ``parts``, proven to stay *inside* ``base``, else ``None``.

    Every filesystem path this module builds goes through here. The run dir arrives
    from a caller — the dashboard backend resolves it from an HTTP path segment — and
    several of the segments joined onto it come from the run's own artifacts (a
    candidate id in the event log, a ``slug:`` in wiki front matter), so containment is
    proven *here*, locally and visibly, instead of being trusted from a resolver two
    modules away. ``realpath`` collapses ``..`` and resolves symlinks first, so a
    ``rollouts`` symlink pointing out of the run dir is refused just like ``../../etc``.

    ``None`` means "escapes the base"; every call site treats that as "not there".
    """
    base_dir = os.path.realpath(base) + os.sep
    p = os.path.realpath(os.path.join(base_dir, *(str(x) for x in parts)))
    if not p.startswith(base_dir):
        return None
    return Path(p)


def _exists_in(base, *parts) -> bool:
    """Does ``base/*parts`` exist *and* stay inside ``base``? (An escape is "no".)"""
    p = _safe_subpath(base, *parts)
    return p is not None and p.exists()


def _read_jsonl(path: Path | None) -> list[dict]:
    out = []
    if path is not None and path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out


def _read_json(path: Path | None) -> dict:
    if path is not None and path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _per_task_from_rollouts(run_dir, tag: str, split: str = "val"):
    """(per_task_reward, feedback) for ``tag`` rebuilt from persisted rollouts.

    Uses the canonical core helper so scores match the loop exactly. Returns two
    dicts keyed by task id; empty if no rollouts were persisted for this tag.
    """
    try:
        from . import harness
        sr = harness.split_result_from_rollouts(run_dir, tag, split)
    except Exception:  # noqa: BLE001 — degrade: a missing/odd rollout shouldn't crash the report
        return {}, {}
    per = {pt["task_id"]: pt["reward"] for pt in sr.to_dict().get("per_task", [])}
    fb = {pt["task_id"]: pt.get("feedback", "") for pt in sr.to_dict().get("per_task", [])}
    return per, fb


def _val_per_task_file(root: Path) -> dict:
    """``val_per_task.json`` — per-candidate per-task val rewards, when the run wrote it.

    Rollouts are the primary source, but they are not always kept: an agent-driven run
    commonly persists the re-derived per-candidate record as ``val_per_task.json`` and
    prunes the raw rollout files. Without this the per-task matrix showed a lone seed
    column and every candidate's "tasks scored" read 0 — for a run whose whole point was
    which tasks each edit fixed and broke.

    Three shapes exist across real runs and all three are read, because a reader who has
    the data on disk should not be shown a blank column over a serialisation detail::

        {tag: {"per_task": {tid: reward}, "stderr": .., "n_scored": .., "fixed": [..]}}
        {tag: {tid: reward}}
        {tag: {tid: {"reward": .., "feedback": ".."}}}

    Returns ``{tag: {per_task, feedback, stderr, n_scored, fixed, broke}}``; anything
    unrecognised is skipped rather than guessed at, so absent stays absent.
    """
    def _norm(inner: dict) -> tuple[dict, dict]:
        per, fb = {}, {}
        for k, v in inner.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                per[str(k)] = float(v)
            elif isinstance(v, dict) and isinstance(v.get("reward"), (int, float)):
                per[str(k)] = float(v["reward"])
                if isinstance(v.get("feedback"), str):
                    fb[str(k)] = v["feedback"]
        return per, fb

    raw = _read_json(_safe_subpath(root, "val_per_task.json"))
    out = {}
    for tag, rec in (raw.items() if isinstance(raw, dict) else ()):
        if not isinstance(rec, dict):
            continue
        inner = rec.get("per_task")
        per, fb = _norm(inner if isinstance(inner, dict) else rec)
        if per:
            out[str(tag)] = {"per_task": per, "feedback": fb,
                             "stderr": rec.get("stderr"), "n_scored": rec.get("n_scored"),
                             "fixed": [str(x) for x in (rec.get("fixed") or [])],
                             "broke": [str(x) for x in (rec.get("broke") or [])]}
    return out


def _trials_for(run_dir, tag: str, split: str) -> int:
    """How many trials a ``tag`` was evaluated with, read from its rollout files.

    Rollouts are persisted as ``{task_id}__{tag}__t{k}.json`` (see
    ``harness.evaluate_candidate``); the trial count is ``max(k)+1`` over the files
    of a single task. Returns 0 when no rollouts were persisted (synthetic logs).
    """
    vdir = _safe_subpath(run_dir.rollouts, split)
    if vdir is None or not vdir.exists():
        return 0
    best = 0
    seen_task = None
    for f in vdir.glob(f"*__{tag}__t*.json"):
        name = f.name
        # ``<tid>__<tag>__t<k>.json`` — k is the integer after the final "__t".
        try:
            k = int(name.rsplit("__t", 1)[1].split(".", 1)[0])
        except (IndexError, ValueError):
            continue
        tid = name.split("__", 1)[0]
        # Count trials within ONE task so distinct tasks don't inflate the number.
        if seen_task is None:
            seen_task = tid
        if tid == seen_task:
            best = max(best, k + 1)
    return best


def _trials_from_per_task(per_task: list) -> int:
    """Trial count from a SplitResult's per-task ``n`` (the honest per-task trials)."""
    ns = [int(pt.get("n") or 0) for pt in (per_task or []) if isinstance(pt, dict)]
    return max(ns) if ns else 0


def _git_log(root: Path) -> list[dict]:
    """One row per iteration commit from the run dir's git store (empty if none)."""
    gitdir = _safe_subpath(root, ".git")
    if gitdir is None or not gitdir.exists() or not shutil.which("git"):
        return []
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "log", "--format=%h%x09%s", "-n", "200"],
            capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    rows = []
    for line in r.stdout.splitlines():
        if "\t" in line:
            h, s = line.split("\t", 1)
            rows.append({"hash": h, "subject": s})
    rows.reverse()  # oldest first → reads top-to-bottom as the run progressed
    return rows


# Step-like events carry a candidate, an accept flag, and per-iteration cost/time.
# Different algorithms name the candidate field differently; normalise here.
def _step_candidate(ev: dict):
    return ev.get("candidate") or ev.get("candidate_id")


# ---------------------------------------------------------------------------
# Algorithm identity, run status, phases — all DERIVED FROM EVIDENCE
# ---------------------------------------------------------------------------

# An event kind that only one algorithm ever emits identifies the algorithm. Ordered
# most-specific first; the first hit wins. Nothing here guesses: a run with no
# distinguishing event stays ``None`` (the UI says "not recorded", never invents one).
_ALGO_MARKERS = (
    ("gepa", ("gepa_start", "gepa_val_gate", "gepa_local_gate", "gepa_select",
              "gepa_merge_local", "gepa_merge_skip", "gepa_stop", "gepa_resume")),
    ("skillopt", ("skillopt_start", "skillopt_step", "skillopt_slow_update",
                  "skillopt_slow_eval")),
    ("evograph", ("evograph_round", "evograph_weakness", "evograph_solution")),
    # ``screen`` is agent-optimize's tiered cheap-screen event (skills/algorithms/
    # agent-optimize/scripts/screen.py) and no other algorithm emits it. Without it a
    # real agent-optimize run that logs only screen/accept/reject — the shape every
    # actual run has, since the agent drives the loop and emits no "agent_round" —
    # matched nothing and rendered as "algorithm not recorded" with no agent panels.
    ("agent-optimize", ("agent_round", "agent_subset", "agent_optimize_step", "screen")),
    ("hill-climb", ("convergence", "step")),
)

#: Every event kind that means "one candidate was proposed and judged". The
#: deterministic loops log ``step``/``skillopt_step``/``gepa_val_gate``; the AGENT-mode
#: loops (agent-optimize, evograph) log ``accept``/``reject`` via the algorithm's
#: ``commit.py``. The reducer used to know only the first three, so every free-form
#: agentic run rendered as a graph with nothing but a seed node.
_STEP_KINDS = ("step", "skillopt_step", "gepa_val_gate", "accept", "reject")

#: Kinds whose presence means "this candidate was accepted" without an ``accept`` field.
_ACCEPT_KINDS = ("accept",)


def _algorithm_from_spec(root: Path) -> str | None:
    """``algorithm_skill`` from the sibling project spec, or None.

    A run dir does not record which algorithm produced it, so a free-form agent run
    (which emits no algorithm-specific event) has no marker in its log. The project
    spec that launched it sits next to the run dir (``<base>/project/capevolve.yaml``)
    and is real evidence — read, never guessed. Flat ``key: value`` only, matching the
    zero-dependency reader the rest of the codebase uses.
    """
    for spec in (_safe_subpath(root.parent, "project", "capevolve.yaml"),
                 _safe_subpath(root, "capevolve.yaml")):
        if spec is None or not spec.is_file():
            continue
        try:
            for line in spec.read_text(encoding="utf-8").splitlines():
                if line.startswith("algorithm_skill:"):
                    val = line.split(":", 1)[1].split("#", 1)[0].strip().strip("'\"")
                    if val:
                        return val
        except OSError:
            continue
    return None

#: How long the event log may be silent before a non-finalized run stops counting as
#: running. A real iteration can take tens of minutes (see run_wide: 25-min optimizer
#: calls), so the window is deliberately generous — better "running" for a while after
#: a kill than "dead" during a legitimately slow step.
STALE_AFTER_SECONDS = 45 * 60.0

_PHASE_OF_KIND = {
    "intake": "intake", "target_profile": "intake", "seed_dir_created": "intake",
    "splits": "baseline", "splits_warning": "baseline", "baseline": "baseline",
    "baseline_reused": "baseline",
    "finalize": "finalize",
}


def _phase_for(ev: dict) -> str:
    kind = str(ev.get("kind") or "")
    if kind in _PHASE_OF_KIND:
        return _PHASE_OF_KIND[kind]
    if kind == "evaluate":
        # The seed-on-val eval IS the baseline; the sealed test eval is finalize.
        if ev.get("split") == "test":
            return "finalize"
        if ev.get("tag") == "seed":
            return "baseline"
    return "optimize"


def _infer_algorithm(kinds: set) -> str | None:
    for name, markers in _ALGO_MARKERS:
        if kinds.intersection(markers):
            return name
    return None


def _budget_exhausted(budget, spent) -> str | None:
    """Which budget limit is spent out, or None. Mirrors RunDir.budget_exhausted."""
    if budget is None or spent is None:
        return None
    checks = (
        ("max_iterations", budget.max_iterations, spent.iterations),
        ("max_metric_calls", budget.max_metric_calls, spent.metric_calls),
        ("max_usd", budget.max_usd, spent.usd + spent.optimizer_usd + spent.intake_usd),
        ("max_optimizer_usd", budget.max_optimizer_usd, spent.optimizer_usd),
    )
    for name, limit, used in checks:
        if limit and used >= limit:
            return f"{name} reached ({used:g} / {limit:g})"
    if budget.stall and spent.stall >= budget.stall:
        return f"stalled ({spent.stall} consecutive non-improving iterations)"
    return None


def _orchestration_mode(root: Path) -> str | None:
    """``orchestration_mode`` from the sibling project spec (``agent`` / ``deterministic``)."""
    for spec in (_safe_subpath(root.parent, "project", "capevolve.yaml"),
                 _safe_subpath(root, "capevolve.yaml")):
        if spec is None or not spec.is_file():
            continue
        try:
            for line in spec.read_text(encoding="utf-8").splitlines():
                if line.startswith("orchestration_mode:"):
                    val = line.split(":", 1)[1].split("#", 1)[0].strip().strip("'\"")
                    if val:
                        return val
        except OSError:
            continue
    return None


def _paid_calls(spent, evaluations: list) -> int:
    """How many runner calls this run actually made (0 if we cannot tell)."""
    n = int(getattr(spent, "metric_calls", 0) or 0)
    if n:
        return n
    # No Spent state (e.g. a curated export): fall back to the evaluations that
    # actually scored something.
    return sum(1 for e in evaluations if (e.get("n_scored") or e.get("n_tasks") or 0))


def _spend_metered(total_usd: float, paid_calls: int) -> bool:
    """False when a run made calls yet recorded exactly $0 — no cost was REPORTED.

    Rendering that as "$0.000" states a fact nobody measured — the same class of lie
    as `pass^k NaN%` or a red `failed` badge for an absent status. Two very different
    runs land here:

      * a zero-API adapter (toy_calc, a mock optimizer) — genuinely free;
      * a real model behind a self-hosted vLLM, an internal RITS endpoint, or an
        OpenAI-compatible proxy that returns no usage, so litellm prices every call
        at 0.0 and the ledger sums to $0.0000 — real spend, unpriced.

    **The run dir cannot distinguish them.** Neither records tokens or cost, and the
    spec's target model is not reliably present. So this returns only what is
    certain — no per-call cost was reported — and callers must word it that way
    ("not reported"), never as a claim that money was or was not spent.

    What IS certain: zero dollars with zero calls is a real $0.00 (nothing ran), so
    that stays `True` and renders as a number.
    """
    return not (paid_calls > 0 and total_usd == 0.0)


def _derive_status(*, events: list, now: float, budget, spent, agent_mode: bool,
                   has_candidates: bool, has_baseline: bool) -> tuple[str, str]:
    """``(status, reason)`` for a run — the five outcomes an operator must tell apart.

    ``completed`` (finalize sealed the test) · ``budget_exhausted`` (a cap was hit and
    no finalize followed) · ``stalled`` (the algorithm declared convergence) ·
    ``running`` (the log is still moving) · ``interrupted`` (no finalize, no recent
    activity — died, was killed, or the shell went away) · ``failed`` (nothing ran).

    The old logic collapsed everything that was not finalized into ``live``, so a run
    that died weeks ago still reported as running. Here the last event's timestamp is
    the evidence, and a truncated/killed run is never called live.
    """
    kinds = [str(e.get("kind") or "") for e in events]
    if not events:
        return "failed", "no events recorded — the run never started"
    if "finalize" in kinds:
        return "completed", "finalize sealed the test split"
    if not has_baseline and not has_candidates:
        return "failed", "no baseline and no candidate was ever evaluated"
    if agent_mode and has_baseline and not has_candidates:
        # ``cap-evolve run`` in agent mode deliberately stops after baseline and hands
        # the loop to the coding agent. That is neither finished nor dead nor running —
        # it is waiting for a human/agent to drive it, and saying "live" (or "failed")
        # about it is the exact class of wrong status the old logic produced.
        return "awaiting_agent", (
            "baseline is done and `cap-evolve run` handed off — the agent has not "
            "committed a candidate yet (agent-mode runs end with `cap-evolve finalize`)")

    last_t = 0.0
    for e in reversed(events):
        try:
            last_t = float(e.get("t") or 0.0)
        except (TypeError, ValueError):
            last_t = 0.0
        if last_t:
            break
    silent = (now - last_t) if last_t else None

    exhausted = _budget_exhausted(budget, spent)
    stop_kinds = {"gepa_stop", "convergence"}
    stopped = next((k for k in reversed(kinds) if k in stop_kinds), None)

    fresh = silent is not None and silent < STALE_AFTER_SECONDS
    if fresh and not exhausted and not stopped:
        return "running", f"last event {silent:.0f}s ago"
    if stopped:
        return "stalled", f"algorithm stopped ({stopped}) without finalizing the test split"
    if exhausted:
        return "budget_exhausted", f"{exhausted}; test split never sealed"
    if silent is None:
        return "interrupted", "events carry no timestamps — cannot tell if it is still alive"
    return "interrupted", (
        f"no finalize and no event for {silent / 60.0:.0f} min — the run died, was "
        "killed, or is still being written by a process that is no longer logging")


def _sanitize_text(value, limit: int = 4000) -> str:
    """Model/subprocess-authored text, made safe to hand to a renderer.

    Strips C0/C1 control characters (ANSI escapes, NULs, carriage returns) that could
    otherwise smuggle terminal escapes into the ANSI report or break out of a JSON
    island, and caps the length. Markup is NOT escaped here — that is the renderer's
    job (``textContent`` in the HTML, JSX in the SPA) — but the value is guaranteed
    to be a plain, bounded, control-free string.
    """
    s = value if isinstance(value, str) else json.dumps(value, default=str)
    s = re.sub(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]", " ", s)
    if len(s) > limit:
        s = s[:limit] + f" …[+{len(s) - limit} chars truncated]"
    return s


#: Event fields that are huge and already surfaced elsewhere — dropped from the log
#: stream's detail blob so one event cannot balloon the payload.
_LOG_DROP_FIELDS = {"t", "kind", "optimizer_report", "error_full", "per_task", "report"}


def _now() -> float:
    import time
    return time.time()


def _front_matter(text: str) -> dict:
    """Parse the flat ``key: value`` YAML front matter evograph writes (stdlib only).

    Only the shapes evograph's contract uses: scalars and inline ``[a, b]`` lists.
    Anything else is kept as the raw string — a reader, not a YAML implementation.
    """
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    out: dict = {}
    for line in text[3:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip(), v.strip()
        if v.startswith("[") and v.endswith("]"):
            out[k] = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
        else:
            out[k] = v.strip("'\"")
    return out


def _read_evograph(root: Path) -> dict:
    """evograph's wiki, read straight from the run dir (no separate server, no iframe).

    evograph is agent-driven and records itself as files under the run dir:
    ``wiki/results/round-<N>.json``, ``wiki/weaknesses/<slug>.md`` front matter, and
    ``wiki/solutions/<slug>/<id>/solution.md``. Reading them here makes the weakness
    graph a first-class panel of the one dashboard instead of an embedded foreign app.
    Returns ``{}`` when the run is not an evograph run.
    """
    wiki = _safe_subpath(root, "wiki")
    if wiki is None or not wiki.is_dir():
        return {}
    rdir = _safe_subpath(wiki, "results")
    rounds = []
    for f in sorted(rdir.glob("*.json")) if rdir is not None and rdir.is_dir() else []:
        d = _read_json(f)
        if not d:
            continue
        metrics = d.get("metrics") or {}
        primary = next((k for k, v in metrics.items()
                        if isinstance(v, dict) and v.get("primary")), None)
        rounds.append({
            "round": d.get("round"), "split": d.get("split"),
            "started_at": d.get("started_at") or d.get("timestamp"),
            "completed_at": d.get("completed_at"),
            "num_tasks": d.get("num_tasks"),
            "primary_metric": primary,
            "metrics": {k: v.get("value") for k, v in metrics.items() if isinstance(v, dict)},
            "cost_usd": d.get("cost_usd"),
        })
    weaknesses = []
    wdir = _safe_subpath(wiki, "weaknesses")
    if wdir is not None and wdir.is_dir():
        for f in sorted(wdir.glob("*.md")):
            try:
                fm = _front_matter(f.read_text(encoding="utf-8"))
            except OSError:
                continue
            fm.setdefault("slug", f.stem)
            # ``slug`` is front matter an agent wrote — a traversal vector, not a name
            # we chose. _safe_subpath refuses anything that leaves wiki/solutions/.
            sol_dir = _safe_subpath(wiki, "solutions", str(fm.get("slug")))
            fm["num_solutions"] = (len([p for p in sol_dir.iterdir() if p.is_dir()])
                                   if sol_dir is not None and sol_dir.is_dir() else 0)
            weaknesses.append({k: (_sanitize_text(v, 400) if isinstance(v, str) else v)
                               for k, v in fm.items()})
    if not rounds and not weaknesses:
        return {}
    return {"rounds": rounds, "weaknesses": weaknesses}


def reduce_run(run_dir) -> dict:
    """Fold the run dir into ``{"graph": ..., "summary": ...}`` (redacted)."""
    root = Path(run_dir.root)
    events = _read_jsonl(_safe_subpath(root, "events.jsonl"))
    baseline = _read_json(_safe_subpath(root, "baseline.json"))
    final = _read_json(_safe_subpath(root, "final.json"))

    per_task_file = _val_per_task_file(root)

    base_val_obj = baseline.get("val") or {}
    baseline_val = base_val_obj.get("reward")
    tasks = [pt["task_id"] for pt in base_val_obj.get("per_task", [])]

    kinds = {str(e.get("kind") or "") for e in events}
    # An algorithm-specific event kind is the strongest evidence; the project spec that
    # launched the run is the fallback (a free-form agent run emits no marker). Both are
    # read from the run's own artifacts — never inferred from the run name.
    # `run_config` wins when present: it is what the CLI actually RESOLVED for this run,
    # not an inference. It is also the only reliable source for the agent-driven algorithms
    # (agent-optimize, evograph), which emit no distinctive event kind at all -- inferring
    # from kinds alone leaves those runs permanently labelled "algorithm not recorded".
    cfg_algo = next((str(e.get("algorithm")) for e in events
                     if e.get("kind") == "run_config" and e.get("algorithm")), None)
    algorithm = cfg_algo or _infer_algorithm(kinds)
    algorithm_source = "run_config" if cfg_algo else ("events" if algorithm else None)
    wiki_dir = _safe_subpath(root, "wiki")
    has_wiki = wiki_dir is not None and wiki_dir.is_dir()
    if algorithm is None or has_wiki:
        from_spec = _algorithm_from_spec(root)
        if has_wiki:
            algorithm, algorithm_source = "evograph", "run-dir wiki/"
        elif from_spec:
            algorithm, algorithm_source = from_spec, "capevolve.yaml"
    # Candidates the gate REFUSED TO JUDGE (low coverage, or an integrity tamper).
    # These are neither accepted nor rejected: the edit was never validly measured.
    indecisive_ids = {
        _step_candidate(e) for e in events
        if e.get("kind") in ("step_indecisive", "tamper_detected")
    } - {None}

    # --- nodes: start with the seed -------------------------------------
    nodes: dict[str, dict] = {}
    seed_per, seed_fb = _per_task_from_rollouts(run_dir, "seed", "val")
    if not seed_per:  # no rollouts persisted (synthetic logs) → fall back to baseline.json
        seed_per = {pt["task_id"]: pt["reward"] for pt in base_val_obj.get("per_task", [])}
        seed_fb = {pt["task_id"]: pt.get("feedback", "") for pt in base_val_obj.get("per_task", [])}
    if not seed_per and "seed" in per_task_file:
        seed_per = per_task_file["seed"]["per_task"]
        seed_fb = per_task_file["seed"]["feedback"] or seed_fb
    nodes["seed"] = {
        "id": "seed", "parent": None, "children": [], "status": "seed",
        "val": baseline_val, "stderr": base_val_obj.get("stderr"),
        "per_task": seed_per, "feedback": seed_fb,
        "cost_usd": (base_val_obj.get("cost_usd") or 0.0),
        "tokens": (base_val_obj.get("tokens") or 0),
        "seconds": (base_val_obj.get("seconds") or 0.0),
        "optimizer_seconds": 0.0, "runner_seconds": (base_val_obj.get("seconds") or 0.0),
        "iteration": 0, "reason": "baseline (seed)", "best_so_far": baseline_val,
    }

    gate_warnings: list[dict] = []
    diagnoses: list[dict] = []
    minibatch_evals: set[str] = set()  # tags only seen on a minibatch (gepa) — not full val

    # First pass: per-tag val stderr from the `evaluate` events. The `step` event
    # carries the mean but not its uncertainty, so without this every candidate's mean
    # rendered bare — the exact sloppiness the honesty rules forbid.
    val_stderr: dict = {}
    val_n_scored: dict = {}
    #: tag → its full-val ``evaluate`` event. An AGENT-mode commit (``accept``/``reject``)
    #: records the verdict but no spend, while the eval that produced the number recorded
    #: real cost/time/tokens one event earlier. Without this join every agent-driven
    #: candidate's eval cost read "—" in the evaluations table while the cost ledger right
    #: above it showed the same dollars — the tables contradicted each other.
    val_eval: dict = {}
    for ev in events:
        if ev.get("kind") == "evaluate" and ev.get("split") == "val":
            if ev.get("stderr") is not None:
                val_stderr[ev.get("tag")] = ev.get("stderr")
            if ev.get("n_scored") is not None:
                val_n_scored[ev.get("tag")] = ev.get("n_scored")
            val_eval[ev.get("tag")] = ev
    for tag, rec in per_task_file.items():
        val_stderr.setdefault(tag, rec.get("stderr"))
        val_n_scored.setdefault(tag, rec.get("n_scored"))

    # Which tags were evaluated on val (vs only minibatch).
    for ev in events:
        if ev.get("kind") == "evaluate" and ev.get("split") == "val":
            minibatch_evals.discard(ev.get("tag"))
        if ev.get("kind") == "minibatch":
            minibatch_evals.add(ev.get("tag"))

    best = baseline_val if baseline_val is not None else 0.0
    it = 0
    last_accepted = "seed"
    for ev in events:
        kind = ev.get("kind")
        if kind == "gate_warning":
            gate_warnings.append({"reason": ev.get("reason"), "context": ev.get("context"),
                                  "mode": ev.get("mode")})
            continue
        if kind in ("diagnose", "optimizer_error"):
            diagnoses.append({
                "kind": kind,
                "candidate": _step_candidate(ev),
                "text": ev.get("error") or ev.get("summary") or ev.get("note") or "",
            })
            continue
        if kind not in _STEP_KINDS:
            continue

        cid = _step_candidate(ev)
        if not cid:
            continue
        # One iteration per CANDIDATE, not per step-like event. skillopt logs both
        # ``skillopt_step`` and a plain ``step`` for the same candidate, and gepa logs a
        # local gate then a val gate — counting events made iteration numbers skip
        # (1,2,4,5) and the per-iteration charts lie about how many steps ran.
        if cid in nodes:
            it = nodes[cid].get("iteration") or it
        else:
            it = max((n.get("iteration") or 0) for n in nodes.values()) + 1
        accepted = bool(ev.get("accept")) or kind in _ACCEPT_KINDS
        parent = ev.get("parent_id") or ev.get("parent")
        if parent is None and kind in ("accept", "reject"):
            # Agent-mode commits carry no parent edge. The candidate WAS gated against
            # the run's current best (``gate_check --current`` defaults to ``best_id``),
            # so the last accepted candidate is the real comparison parent, not a guess.
            parent = last_accepted
        # gepa val-gate / step events don't always carry the parent edge; fall back
        # to "seed" if we have nothing better so the lineage tree stays connected.
        val = ev.get("val")
        parent_val = ev.get("parent_val")

        per, fb = _per_task_from_rollouts(run_dir, cid, "val")
        if not per and cid in per_task_file:
            per = per_task_file[cid]["per_task"]
            fb = per_task_file[cid]["feedback"] or fb
        if not per:
            # A candidate killed on a cheap screen has per-task rewards only under its
            # SCREEN tag (``<cid>__screenN``) and over a subset of val. Showing those is
            # the difference between "we can see it regressed task 12" and a blank row:
            # ``val`` stays None so nothing claims a val score, and the tasks the screen
            # never ran render as "not run" (missing), not as zeros.
            for tag, rec in per_task_file.items():
                if tag.startswith(f"{cid}__"):
                    per = {**(per or {}), **rec["per_task"]}
                    fb = {**(fb or {}), **rec["feedback"]}
        # Order matters. An INDECISIVE step (coverage collapse / integrity tamper) is
        # not a rejection and not a failure: the gate declined to judge, so the edit's
        # quality is unknown. Collapsing it into "rejected" (the old behaviour) told
        # the reader a measured verdict existed when none did.
        if cid in indecisive_ids:
            status = "indecisive"
        elif val is None and not per and kind not in ("accept", "reject"):
            # ``failed`` means NO VERDICT AND NO MEASUREMENT — a step that produced
            # nothing. An explicit ``accept``/``reject`` commit is a recorded verdict
            # even when ``val`` is null, which is the normal shape for a candidate
            # agent-optimize KILLED on a cheap screen before paying for full val.
            # Calling that "failed / no measurement" put a red failure badge on the
            # cheap-screen mechanism working exactly as designed.
            status = "failed"
        else:
            status = "accepted" if accepted else "rejected"

        # ONLY a candidate the gate ACCEPTED may set the running-best record. This used
        # to exclude `indecisive` alone, which let a REJECTED candidate raise the stair:
        # on the real v4 tau2 run two candidates scored a raw 0.5833, were vetoed on
        # no-regression, and every cumulative-best chart then read 58.3% while the run's
        # actual best was the seed at 0.5667 — the chart contradicted the KPI tile beside
        # it, and the chart was wrong. A rejected capability is one you cannot ship, so it
        # is not the best of anything. (`best` is seeded from baseline_val above, so the
        # seed's own score is already in.) The rejected candidate is still PLOTTED via
        # `val`; hiding a measurement would be its own dishonesty.
        if val is not None and status == "accepted":
            best = max(best, val)

        merge_of = ev.get("merge_of")
        # The eval that produced this candidate's val is the only record of what it cost.
        vev = val_eval.get(cid) or {}
        movement = per_task_file.get(cid) or {}
        node = {
            "id": cid,
            "parent": parent if parent in (None,) or True else parent,
            "children": [],
            "status": status,
            "val": val,
            "stderr": val_stderr.get(cid),
            "n_scored": val_n_scored.get(cid),
            "per_task": per,
            "feedback": fb,
            "cost_usd": ev.get("cost_usd") or vev.get("cost_usd") or 0.0,
            "tokens": ev.get("tokens") or vev.get("tokens") or 0,
            # Per-iteration optimizer cost/tokens (RITS runner cost is often $0/null,
            # but the optimizer agent CLI reports opt_cost_usd / opt_tokens per step).
            "opt_cost_usd": ev.get("opt_cost_usd") or ev.get("optimizer_cost_usd"),
            "opt_tokens": ev.get("opt_tokens") or ev.get("optimizer_tokens") or 0,
            "seconds": (ev.get("runner_seconds") or vev.get("seconds") or 0.0)
                       + (ev.get("optimizer_seconds") or 0.0),
            "optimizer_seconds": ev.get("optimizer_seconds") or 0.0,
            "runner_seconds": ev.get("runner_seconds") or vev.get("seconds") or 0.0,
            "iteration": it,
            # Agent-mode commits (``accept``/``reject``, written by the algorithm's
            # commit.py) put the gate rationale in ``note``; the deterministic loops use
            # ``reason``. Reading only ``reason`` silently discarded every agent-authored
            # justification — the single most informative field in an agent-driven run.
            "reason": ev.get("reason") or ev.get("note") or "",
            # Which tasks this edit fixed / broke versus its parent, when the run recorded
            # the movement. Not derived here: a mean-preserving edit that swaps which
            # tasks pass is churn, and only the recorded lists prove it.
            "fixed": movement.get("fixed") or [],
            "broke": movement.get("broke") or [],
            "parent_val": parent_val,
            "best_so_far": best,
        }
        if "epoch" in ev:
            node["epoch"] = ev.get("epoch")
        if merge_of:
            node["merge_of"] = merge_of
        # Last write wins if the same cid appears twice (e.g. gepa local-gate then
        # val-gate); keep the richer (val-bearing) record.
        if cid in nodes and nodes[cid].get("val") is not None and val is None:
            pass
        else:
            node["parent"] = parent
            nodes[cid] = node
        if accepted:
            last_accepted = cid

    # --- wire parent → children edges -----------------------------------
    for nid, n in nodes.items():
        p = n.get("parent")
        if p and p in nodes and p != nid:
            nodes[p]["children"].append(nid)
        # multi-parent (merge): also link the merge sources
        for mp in (n.get("merge_of") or []):
            if mp in nodes and nid not in nodes[mp]["children"]:
                nodes[mp]["children"].append(nid)

    # --- best id (prefer event log over state.json) ---------------------
    best_id = "seed"
    best_val = baseline_val if baseline_val is not None else None
    for nid, n in nodes.items():
        if n["status"] == "accepted" and n.get("val") is not None:
            if best_val is None or n["val"] >= best_val:
                best_val, best_id = n["val"], nid
    if final.get("best_id"):
        best_id = final["best_id"]

    # --- frontier: gated (accepted) leaves with no accepted child -------
    accepted_ids = {nid for nid, n in nodes.items() if n["status"] in ("accepted", "seed")}
    frontier = 0
    for nid in accepted_ids:
        kids = [c for c in nodes[nid]["children"] if nodes.get(c, {}).get("status") == "accepted"]
        if not kids:
            frontier += 1

    # --- counts ----------------------------------------------------------
    counts = {"accepted": 0, "rejected": 0, "failed": 0, "seed": 0, "indecisive": 0}
    for n in nodes.values():
        counts[n["status"]] = counts.get(n["status"], 0) + 1
    counts["total"] = len(nodes)

    # --- cost / time / tokens split (intake vs optimizer vs runner) ------
    # state.json's Spent is the authoritative, role-tagged accumulator (runner +
    # optimizer + best-effort intake). Prefer it; fall back to event/node-derived
    # sums for synthetic fixtures that log events but never wrote a Spent.
    try:
        sp = run_dir.spent
    except Exception:  # noqa: BLE001
        sp = None
    opt_secs = sum(n.get("optimizer_seconds") or 0.0 for n in nodes.values())
    run_secs = sum(n.get("runner_seconds") or 0.0 for n in nodes.values())
    runner_usd = sum(float(n.get("cost_usd") or 0.0) for n in nodes.values())
    # cost_usd on a step is the RUNNER eval cost; optimizer cost is captured
    # separately by headless backends as opt_cost_usd when present.
    opt_usd = 0.0
    for ev in events:
        if ev.get("kind") in _STEP_KINDS:
            opt_usd += float(ev.get("opt_cost_usd") or ev.get("optimizer_cost_usd") or 0.0)
    tokens = sum(int(n.get("tokens") or 0) for n in nodes.values())
    intake_usd = intake_tokens = intake_secs = 0.0
    opt_tokens = 0
    if sp is not None and (sp.total_usd or sp.metric_calls or sp.optimizer_seconds):
        runner_usd = sp.usd
        opt_usd = sp.optimizer_usd
        intake_usd = sp.intake_usd
        opt_secs = sp.optimizer_seconds
        run_secs = sp.runner_seconds
        intake_secs = sp.intake_seconds
        opt_tokens = sp.optimizer_tokens
        intake_tokens = sp.intake_tokens
        tokens = sp.runner_tokens + sp.optimizer_tokens + sp.intake_tokens

    test = final.get("test") or {}
    test_reward = test.get("reward")
    try:
        sealed = run_dir.read_splits().test_used
    except Exception:  # noqa: BLE001
        sealed = bool(final)

    # --- per-iteration cost/time (optimizer vs runner), intake row ------
    # Time is ALWAYS available (optimizer_seconds + runner seconds per step);
    # cost is shown only when present (runner cost is often $0/null on RITS).
    per_iteration = []
    for n in sorted((x for x in nodes.values() if (x.get("iteration") or 0) > 0),
                    key=lambda x: x.get("iteration") or 0):
        runner_cost = n.get("cost_usd")
        per_iteration.append({
            "iteration": n.get("iteration"),
            "candidate": n["id"],
            "status": n.get("status"),
            "optimizer_usd": n.get("opt_cost_usd"),  # nullable
            "optimizer_seconds": round(n.get("optimizer_seconds") or 0.0, 2),
            "optimizer_tokens": int(n.get("opt_tokens") or 0),
            # Runner cost is nullable: only surface a real number, not a synthetic 0.
            "runner_usd": (float(runner_cost) if runner_cost else None),
            "runner_seconds": round(n.get("runner_seconds") or 0.0, 2),
            "runner_tokens": int(n.get("tokens") or 0),
        })
    # Intake: prefer the explicit "intake" event (richer — carries output_summary +
    # implemented list) and fall back to the spent-derived numbers above when absent.
    intake_ev = next((e for e in events if e.get("kind") == "intake"), None)
    if intake_ev is not None:
        intake = {
            "usd": round(float(intake_ev.get("usd") or intake_usd or 0.0), 4),
            "seconds": round(float(intake_ev.get("seconds") or intake_secs or 0.0), 2),
            "tokens": int(intake_ev.get("tokens") or intake_tokens or 0),
            "output_summary": intake_ev.get("output_summary") or "",
            "implemented": list(intake_ev.get("implemented") or []),
        }
    else:
        intake = {
            "usd": round(intake_usd, 4),
            "seconds": round(intake_secs, 2),
            "tokens": int(intake_tokens),
            "output_summary": "",
            "implemented": [],
        }

    # Consuming-LLM profile (the runtime model the capabilities are optimized FOR;
    # distinct from the optimizer model). Absent for profile-agnostic runs.
    tp_ev = next((e for e in events if e.get("kind") == "target_profile"), None)
    target_profile = ({
        "model": tp_ev.get("model") or "",
        "tier": tp_ev.get("tier") or "",
        "resolution_note": tp_ev.get("resolution_note") or "",
    } if tp_ev is not None else None)

    # --- first-class evaluations (split-oriented, distinct from per_iteration) ---
    # An evaluation is one scoring of a candidate on one split: the seed baseline on
    # val, every candidate that earned a full val score on val, and the sealed test
    # eval on test. This is the eval-centric view (vs per_iteration's optimizer-step
    # view): kind, candidate, split, reward±stderr, n_tasks × trials, runner spend.
    evaluations: list[dict] = []

    # baseline (seed on val)
    base_trials = (_trials_from_per_task(base_val_obj.get("per_task", []))
                   or _trials_for(run_dir, "seed", "val") or 1)
    if baseline_val is not None or base_val_obj:
        evaluations.append({
            "id": "baseline",
            "kind": "baseline",
            "candidate": "seed",
            "split": "val",
            "reward": baseline_val,
            "stderr": base_val_obj.get("stderr"),
            "n_tasks": len(base_val_obj.get("per_task", [])) or len(tasks),
            "trials": base_trials,
            "cost_usd": (base_val_obj.get("cost_usd") or 0.0),
            "seconds": (base_val_obj.get("seconds") or 0.0),
            "tokens": int(base_val_obj.get("tokens") or 0),
        })

    # candidates (one per candidate node that earned a full val score)
    for n in sorted((x for x in nodes.values() if x["id"] != "seed"),
                    key=lambda x: x.get("iteration") or 0):
        if n.get("val") is None:
            continue
        cid = n["id"]
        n_tasks = len(n.get("per_task") or {}) or (val_n_scored.get(cid) or 0)
        trials = _trials_for(run_dir, cid, "val") or 1
        evaluations.append({
            "id": cid,
            "kind": "candidate",
            "candidate": cid,
            "split": "val",
            "reward": n.get("val"),
            "stderr": n.get("stderr"),
            "n_tasks": n_tasks,
            "trials": trials,
            "cost_usd": float(n.get("cost_usd") or 0.0),
            "seconds": float(n.get("runner_seconds") or 0.0),
            "tokens": int(n.get("tokens") or 0),
        })

    # test (the sealed test eval, from final.json)
    test_obj = final.get("test") or {}
    if test_obj:
        test_trials = (_trials_from_per_task(test_obj.get("per_task", []))
                       or _trials_for(run_dir, "FINAL", "test") or 1)
        evaluations.append({
            "id": "test",
            "kind": "test",
            "candidate": final.get("best_id") or best_id,
            "split": "test",
            "reward": test_obj.get("reward"),
            "stderr": test_obj.get("stderr"),
            "n_tasks": len(test_obj.get("per_task", [])),
            "trials": test_trials,
            "cost_usd": float(test_obj.get("cost_usd") or 0.0),
            "seconds": float(test_obj.get("seconds") or 0.0),
            "tokens": int(test_obj.get("tokens") or 0),
        })

    # --- gate decisions (accept / reject / INDECISIVE, with Δ̄, SE, n) -----
    # The reason string the gate wrote is the audit record; Δ̄/SE/n are parsed back out
    # of it so the UI can show the uncertainty next to the mean instead of a bare Δ.
    # A number that isn't in the reason stays None — never a fabricated 0.
    gate_decisions: list[dict] = []
    for n in sorted((x for x in nodes.values() if x["id"] != "seed"),
                    key=lambda x: x.get("iteration") or 0):
        reason = str(n.get("reason") or "")
        verdict = ("accept" if n["status"] == "accepted"
                   else "indecisive" if n["status"] == "indecisive"
                   else "reject" if n["status"] == "rejected" else "no measurement")
        m_delta = re.search(r"Δ̄?\s*=\s*([+-]?\d*\.?\d+)", reason)
        # The bar `0.2·SE=0.0062` comes FIRST in the reason and also matches `SE=`, so an
        # unanchored search put the bar's value in the SE column — the gate then appeared
        # to have compared Δ̄ against five times its own standard error. Skip the `k·SE`
        # form and take the standalone `SE=` that follows it.
        m_se = re.search(r"(?<!·)\bSE\s*=\s*(\d*\.?\d+)", reason)
        m_n = re.search(r"\bn\s*=\s*(\d+)", reason)
        m_bar = re.search(r"([\d.]+)·SE\s*=\s*(\d*\.?\d+)", reason)
        gate_decisions.append({
            "iteration": n.get("iteration"),
            "candidate": n["id"],
            "verdict": verdict,
            "val": n.get("val"),
            "parent": n.get("parent"),
            "parent_val": n.get("parent_val"),
            "delta": float(m_delta.group(1)) if m_delta else None,
            "stderr": float(m_se.group(1)) if m_se else None,
            "n": int(m_n.group(1)) if m_n else None,
            "k_se": float(m_bar.group(1)) if m_bar else None,
            "threshold": float(m_bar.group(2)) if m_bar else None,
            "reason": _sanitize_text(reason, 600),
        })

    # --- cost ledger: every dollar, attributed to the thing that spent it -----
    # Rows are built from the events that actually recorded a spend (intake, each
    # ``evaluate``, each optimizer call on a step) and reconciled against the run's
    # authoritative Spent total. A row whose cost was never recorded carries
    # ``usd: None`` (shown as "—"), and whatever the rows cannot account for is
    # published as ``unattributed_usd`` rather than quietly dropped.
    ledger: list[dict] = []
    # Intake is ALWAYS a row. A run whose intake genuinely cost nothing shows $0.0000
    # (a recorded measurement); a run with no spend accounting at all shows "—". The
    # one thing it must never do is be absent, which is what made intake cost invisible.
    ledger.append({
        "phase": "intake", "kind": "intake", "label": "Intake + scaffold",
        "candidate": None, "split": None,
        "usd": (intake["usd"] if (sp is not None or intake_ev is not None) else None),
        "seconds": intake["seconds"], "tokens": intake["tokens"],
        "note": intake.get("output_summary") or "",
    })
    opt_error_ids = {_step_candidate(e) for e in events if e.get("kind") == "optimizer_error"}
    for ev in events:
        kind = ev.get("kind")
        if kind == "evaluate":
            tag, split = ev.get("tag") or "?", ev.get("split") or "?"
            is_base = tag == "seed" and split == "val"
            ledger.append({
                "phase": _phase_for(ev), "split": split,
                "kind": "baseline_eval" if is_base else ("test_eval" if split == "test"
                                                         else "candidate_eval"),
                "label": ("Baseline eval — seed on val" if is_base else
                          f"Sealed test eval — {tag}" if split == "test" else
                          f"Eval {tag} on {split}"),
                "candidate": tag,
                "usd": ev.get("cost_usd"), "seconds": ev.get("seconds") or 0.0,
                "tokens": int(ev.get("tokens") or 0),
                "note": (f"reward {ev['reward']:.3f}" if isinstance(ev.get("reward"), (int, float))
                         else ""),
            })
        elif kind in _STEP_KINDS:
            cid = _step_candidate(ev)
            if not cid:
                continue
            usd = ev.get("opt_cost_usd")
            if usd is None:
                usd = ev.get("optimizer_cost_usd")
            truncated = cid in opt_error_ids
            ledger.append({
                "phase": "optimize", "kind": "optimizer_call", "split": None,
                "label": f"Optimizer call → {cid}" + (" (exited non-zero)" if truncated else ""),
                "candidate": cid,
                "usd": (float(usd) if usd is not None else None),
                "seconds": ev.get("optimizer_seconds") or 0.0,
                "tokens": int(ev.get("opt_tokens") or ev.get("optimizer_tokens") or 0),
                "note": ("the optimizer process exited non-zero (commonly its own budget "
                         "cap) — the spend below is real and was still charged"
                         if truncated else ""),
            })
    attributed = sum(r["usd"] for r in ledger if r["usd"] is not None)
    total_usd = round(opt_usd + runner_usd + intake_usd, 6)
    metered = _spend_metered(total_usd, _paid_calls(sp, evaluations))
    cost_ledger = {
        "rows": ledger,
        "attributed_usd": round(attributed, 6),
        "total_usd": total_usd,
        # Positive => the run's Spent total exceeds what the events attribute (spend
        # recorded without a corresponding event). Negative is possible too and is
        # equally worth seeing. Never hidden, never rounded to zero.
        "unattributed_usd": round(total_usd - attributed, 4),
        "rows_missing_cost": sum(1 for r in ledger if r["usd"] is None),
        "metered": metered,
    }

    # --- splits: is there a real holdout at all? -------------------------
    split_ev = next((e for e in events if e.get("kind") == "splits"), None)
    splits_info = None
    if split_ev is not None:
        tr, va, te = (split_ev.get("train"), split_ev.get("val"), split_ev.get("test"))
        n = lambda x: (len(x) if isinstance(x, (list, tuple)) else  # noqa: E731
                       (int(x) if isinstance(x, int) else None))
        n_tr, n_va, n_te = n(tr), n(va), n(te)
        same = (isinstance(tr, list) and isinstance(va, list) and isinstance(te, list)
                and set(map(str, tr)) == set(map(str, va)) == set(map(str, te)))
        splits_info = {
            "train": n_tr, "val": n_va, "test": n_te, "seed": split_ev.get("seed"),
            # A run where train==val==test has NO holdout: its "test" number is not a
            # generalization estimate and the UI must say so rather than presenting it
            # as a sealed result.
            "no_holdout": bool(same),
            "warning": next((_sanitize_text(e.get("msg") or "", 300) for e in events
                             if e.get("kind") == "splits_warning"), ""),
        }

    # --- activity log: every event, sanitized, phase-tagged --------------
    # "we don't see any logs and what is happening (not just high level stage)".
    log_rows: list[dict] = []
    for i, ev in enumerate(events):
        detail = {k: v for k, v in ev.items() if k not in _LOG_DROP_FIELDS}
        full = ev.get("error_full") or ev.get("error")
        log_rows.append({
            "seq": i,
            "t": (float(ev["t"]) if isinstance(ev.get("t"), (int, float)) else None),
            "kind": str(ev.get("kind") or "event"),
            "phase": _phase_for(ev),
            "candidate": _step_candidate(ev) or ev.get("tag"),
            "detail": {k: (_sanitize_text(v, 1200) if isinstance(v, str) else v)
                       for k, v in detail.items()},
            # stderr / diagnosis prose gets its own field so the UI can render it as a
            # block rather than a key/value pair.
            "text": (_sanitize_text(full, 6000) if full else
                     (_sanitize_text(ev.get("reason"), 800) if ev.get("reason") else "")),
        })

    # --- per-algorithm extras (present only when the run emitted the signal) ---
    algo_extra: dict = {}
    mb = [e for e in events if e.get("kind") == "minibatch"]
    if mb:
        # gepa's minibatch event names the subset ``ids`` and the count ``fired`` — it
        # never writes ``tasks``/``n_tasks``, so the panel printed "n tasks —" and an
        # empty task list for every row while the event recorded both.
        algo_extra["minibatch"] = [{
            "candidate": _step_candidate(e) or e.get("tag"),
            "reward": e.get("reward"),
            "n_tasks": (e.get("n_tasks") or e.get("n") or e.get("fired")
                        or len(e.get("ids") or []) or None),
            "tasks": [str(x) for x in (e.get("tasks") or e.get("ids") or [])][:64],
            "t": e.get("t"),
        } for e in mb]
    gepa_ev = [e for e in events if str(e.get("kind") or "").startswith("gepa_")]
    if gepa_ev:
        algo_extra["gepa"] = [{"kind": e.get("kind"), "t": e.get("t"),
                               "candidate": _step_candidate(e),
                               "detail": {k: v for k, v in e.items()
                                          if k not in _LOG_DROP_FIELDS}} for e in gepa_ev]
    sk_ev = [e for e in events if str(e.get("kind") or "").startswith("skillopt_")]
    if sk_ev:
        algo_extra["skillopt"] = [{"kind": e.get("kind"), "t": e.get("t"),
                                   "epoch": e.get("epoch"), "lr": e.get("lr"),
                                   "candidate": _step_candidate(e),
                                   "detail": {k: v for k, v in e.items()
                                              if k not in _LOG_DROP_FIELDS}} for e in sk_ev]
    epochs = sorted({e["epoch"] for e in events if isinstance(e.get("epoch"), int)})
    if epochs:
        algo_extra["epochs"] = epochs
    focus_vals = [e.get("focus") for e in events if e.get("focus")]
    if focus_vals:
        algo_extra["focus"] = [str(x) for x in focus_vals]
    # agent-optimize's tiered cheap screens: a paired subset eval that decides whether a
    # candidate is worth a full val run. The event carries the decision; the matching
    # ``screens/<tag>.json`` carries WHICH tasks were in the subset and which the edit
    # fixed/regressed, which is the whole reason to look at a screen at all. Both were
    # written to the run dir and neither was ever read.
    screen_files = {}
    sdir = _safe_subpath(root, "screens")
    if sdir is not None and sdir.is_dir():
        for f in sorted(sdir.glob("*.json")):
            d = _read_json(f)
            if d:
                screen_files[str(d.get("screen_tag") or f.stem)] = d
    screens = []
    for e in events:
        if e.get("kind") != "screen":
            continue
        tag = str(e.get("tag") or "")
        d = screen_files.get(tag) or next(
            (v for k, v in screen_files.items() if str(v.get("tag")) == tag), {})
        sub = d.get("subset") or {}
        paired = d.get("paired") or {}
        screens.append({
            "candidate": tag, "screen_tag": d.get("screen_tag") or tag,
            "tier": e.get("tier"), "decision": e.get("decision"),
            "inconclusive": bool(e.get("inconclusive")),
            "mean_delta": e.get("mean_delta"), "se": e.get("se"), "n": e.get("n"),
            "threshold": d.get("threshold"),
            "net_rollouts": e.get("net_rollouts"),
            "ids": [str(x) for x in (e.get("ids") or sub.get("ids") or [])],
            "holdout": [str(x) for x in (sub.get("holdout") or [])],
            "informative": [str(x) for x in (sub.get("informative") or [])],
            "fixed": [str(x) for x in (paired.get("fixed") or [])],
            "regressed": [str(x) for x in (paired.get("regressed") or [])],
            "pool_n": sub.get("pool_n"),
            "t": e.get("t"),
        })
    if screens:
        algo_extra["screens"] = screens

    evograph = _read_evograph(root)
    if evograph:
        algo_extra["evograph"] = evograph
    par = [e for e in events if e.get("kind") == "parallel"]
    if par:
        algo_extra["parallel"] = [{k: v for k, v in e.items()
                                   if k not in _LOG_DROP_FIELDS} for e in par]

    # --- capabilities: which panels this run has real data for -----------
    # The UI is algorithm-agnostic: it renders the generic panels always and asks this
    # map before mounting an extra one. An absent signal means the panel is omitted —
    # never rendered empty, never faked.
    capabilities = {
        "per_task": any(n.get("per_task") for n in nodes.values()),
        "lineage": len(nodes) > 1,
        "gate": bool(gate_decisions),
        "cost": bool(ledger),
        "log": bool(log_rows),
        "trajectories": _exists_in(root, "rollouts"),
        "diffs": _exists_in(root, "candidates"),
        "minibatch": "minibatch" in algo_extra,
        "gepa": "gepa" in algo_extra,
        "skillopt": "skillopt" in algo_extra,
        "epochs": "epochs" in algo_extra,
        "focus": "focus" in algo_extra,
        "evograph": "evograph" in algo_extra,
        "screens": "screens" in algo_extra,
        "parallel": "parallel" in algo_extra,
        # A free-form (agent-driven) run has no deterministic step loop: candidates
        # arrive from an agent's own decisions, so iteration numbers are not a schedule.
        "freeform": algorithm in ("evograph", "agent-optimize"),
    }

    status, status_reason = _derive_status(
        events=events, now=_now(), budget=(run_dir.budget if sp is not None else None),
        spent=sp, agent_mode=(_orchestration_mode(root) == "agent"),
        has_candidates=len(nodes) > 1, has_baseline=baseline_val is not None)
    ts = [float(e["t"]) for e in events if isinstance(e.get("t"), (int, float))]

    delta_pct = None
    if baseline_val not in (None, 0) and best_val is not None:
        delta_pct = round((best_val - baseline_val) / abs(baseline_val) * 100.0, 1)
    elif baseline_val == 0 and best_val:
        delta_pct = None  # undefined %Δ off a zero baseline; show absolute Δ instead

    summary = {
        "run_id": root.name,
        "algorithm": algorithm,
        # Where the identity came from: a distinguishing event kind, the run dir's own
        # evograph wiki, or the project spec. None ⇒ the UI shows "not recorded".
        "algorithm_source": algorithm_source,
        "capabilities": capabilities,
        "status": status,
        "status_reason": status_reason,
        "started_t": (min(ts) if ts else None),
        "last_event_t": (max(ts) if ts else None),
        # Real elapsed wall time between first and last event — distinct from
        # wall_clock_seconds, which is the SUM of measured optimizer+runner+intake time
        # and therefore excludes idle/queueing gaps.
        "elapsed_seconds": (round(max(ts) - min(ts), 1) if len(ts) > 1 else None),
        "event_count": len(events),
        "splits": splits_info,
        "gate_decisions": gate_decisions,
        "cost_ledger": cost_ledger,
        "log": log_rows,
        "algo_extra": algo_extra,
        "baseline_val": baseline_val,
        # The seed's own measured uncertainty. It was already in baseline.json and in the
        # evaluations table, but not on the summary, so the KPI card claimed "no stderr
        # recorded" beside a table that showed one.
        "baseline_stderr": base_val_obj.get("stderr"),
        "best_val": best_val,
        "best_id": best_id,
        "delta_abs": (round(best_val - baseline_val, 4)
                      if (best_val is not None and baseline_val is not None) else None),
        "delta_pct": delta_pct,
        "test_reward": test_reward,
        "test_stderr": test.get("stderr"),
        "test_pass_k": test.get("pass_k"),
        # The sealed test only means something NEXT TO the seed's test score: a run whose
        # best candidate is the seed has test_delta 0 by construction, and a run that
        # improved val but not test is the failure this project exists to catch. Both
        # numbers were already in final.json and neither reached the UI, so the headline
        # tile could not say whether the shipped edit was actually better.
        "test_baseline_reward": final.get("test_baseline", {}).get("reward")
                                if isinstance(final.get("test_baseline"), dict)
                                else final.get("test_baseline_reward"),
        "test_delta": final.get("test_delta"),
        "test_sealed": sealed,
        "counts": counts,
        "frontier": frontier,
        "tasks": tasks,
        "wall_clock_seconds": round(opt_secs + run_secs + intake_secs, 1),
        "optimizer_seconds": round(opt_secs, 1),
        "runner_seconds": round(run_secs, 1),
        "intake_seconds": round(intake_secs, 1),
        "cost": {"optimizer_usd": round(opt_usd, 4), "runner_usd": round(runner_usd, 4),
                 "intake_usd": round(intake_usd, 4),
                 "total_usd": round(opt_usd + runner_usd + intake_usd, 4),
                 "metered": _spend_metered(opt_usd + runner_usd + intake_usd,
                                           _paid_calls(sp, evaluations))},
        "tokens": tokens,
        "tokens_by_role": {"runner": tokens - opt_tokens - int(intake_tokens),
                           "optimizer": opt_tokens, "intake": int(intake_tokens)},
        "per_iteration": per_iteration,
        "evaluations": evaluations,
        "intake": intake,
        "target_profile": target_profile,
        "budget": (run_dir.budget.to_dict() if sp is not None else None),
        "spent": (sp.to_dict() if sp is not None else None),
        "budget_warnings": [e for e in events if e.get("kind") == "budget_warning"],
        "gate_warnings": gate_warnings,
        "diagnoses": diagnoses,
        "git_log": _git_log(root),
    }

    graph = {"nodes": list(nodes.values()), "root": "seed", "best_id": best_id}
    return redact({"graph": graph, "summary": summary})


# ---------------------------------------------------------------------------
# Diff view (candidate vs parent) — computed from candidate dirs
# ---------------------------------------------------------------------------

# Optimizer prompt/memory files that live alongside the capability in a candidate
# snapshot but are NOT capability edits — skipped when diffing iterations so the diff
# shows only the real change. (The big read-context dirs trajectories/ and guidance/
# are already excluded from the snapshot itself; see harness._SNAPSHOT_IGNORE.)
_DIFF_SKIP = {"INSTRUCTIONS.md", "MEMORY.md", "STATE.md",
              "LEDGER.md", "JOURNAL.md", "PROCESS.md", "RUNMAP.md"}


def _read_dir_files(d: Path) -> dict[str, str]:
    out = {}
    if not d.exists():
        return out
    for f in sorted(d.rglob("*")):
        if f.is_file():
            rel = str(f.relative_to(d))
            if rel in _DIFF_SKIP or rel.split("/", 1)[0] in ("trajectories", "guidance"):
                continue
            try:
                out[rel] = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
    return out


def build_diffs(run_dir, graph: dict) -> dict:
    """For every node with a parent, compute a unified-ish diff vs its parent dir.

    Returns ``{node_id: [{"file", "hunks": [{"old","new","tag"}...]}]}``. Empty when
    candidate dirs were not snapshotted (synthetic logs) — the panel hides itself.
    """
    import difflib
    cand_root = Path(run_dir.candidates)
    diffs: dict[str, list] = {}
    for n in graph["nodes"]:
        nid, parent = n["id"], n.get("parent")
        if not parent:
            continue
        # nid/parent are candidate ids read out of the event log, not names we chose.
        cdir, pdir = _safe_subpath(cand_root, nid), _safe_subpath(cand_root, parent)
        if cdir is None or pdir is None or not cdir.exists() or not pdir.exists():
            continue
        cf, pf = _read_dir_files(cdir), _read_dir_files(pdir)
        file_diffs = []
        for path in sorted(set(cf) | set(pf)):
            a = pf.get(path, "").splitlines()
            b = cf.get(path, "").splitlines()
            if a == b:
                continue
            rows = []
            for line in difflib.unified_diff(a, b, lineterm="", n=2):
                if line.startswith("+++") or line.startswith("---"):
                    continue
                tag = ("add" if line.startswith("+") else "del" if line.startswith("-")
                       else "hunk" if line.startswith("@@") else "ctx")
                rows.append({"t": tag, "l": line})
            if rows:
                file_diffs.append({"file": path, "rows": rows})
        if file_diffs:
            diffs[nid] = file_diffs
    return redact(diffs)


# ---------------------------------------------------------------------------
# HTML rendering — self-contained (inline CSS + JS + SVG, no CDN)
# ---------------------------------------------------------------------------

def render_html(reduced: dict, run_dir=None) -> str:
    """Render the self-contained dashboard HTML from a reduced run."""
    diffs = {}
    if run_dir is not None:
        try:
            diffs = build_diffs(run_dir, reduced["graph"])
        except Exception:  # noqa: BLE001 — diff panel is optional
            diffs = {}
    payload = {"graph": reduced["graph"], "summary": reduced["summary"], "diffs": diffs}
    data = json.dumps(payload, default=str).replace("</", "<\\/")
    return _HTML_TEMPLATE.replace("/*__RUN_DATA__*/null", data)


def write_dashboard(run_dir) -> Path:
    """Reduce + render + write ``dashboard.html`` next to the run state."""
    reduced = reduce_run(run_dir)
    html_text = render_html(reduced, run_dir)
    out = _safe_subpath(run_dir.root, "dashboard.html")
    if out is None:  # only reachable if dashboard.html is a symlink out of the run dir
        raise ValueError(f"dashboard.html escapes the run dir: {run_dir.root}")
    out.write_text(html_text, encoding="utf-8")
    # Write through the proven path, but hand back the caller's own (possibly relative)
    # spelling of it: `cap-evolve run` prints this in its JSON and compares runs by it.
    return Path(run_dir.root) / "dashboard.html"


# ---------------------------------------------------------------------------
# ANSI terminal report — CLAUDECODE margin-aware
# ---------------------------------------------------------------------------

class _C:
    RESET = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
    RED = "\033[31m"; GREEN = "\033[32m"; YELLOW = "\033[33m"
    BLUE = "\033[34m"; CYAN = "\033[36m"; GREY = "\033[90m"
    BG_GREEN = "\033[42m"; BG_RED = "\033[41m"


def _term_width(default: int = 100) -> int:
    """Usable terminal width, minus the CLAUDECODE tool-output frame margin.

    Inside Claude Code (``CLAUDECODE=1``) the tool-output frame eats ~6 columns; if
    we print to the real width the lines wrap inside the frame. Subtract the margin
    so the report stays inside the box.
    """
    try:
        cols = shutil.get_terminal_size((default, 24)).columns
    except OSError:
        cols = default
    if os.environ.get("CLAUDECODE") == "1":
        cols -= 6
    return max(40, min(cols, 200))


def render_ansi(reduced: dict, *, color: bool = True, top_n: int = 8) -> str:
    s = reduced["summary"]
    g = reduced["graph"]
    width = _term_width()
    use = color and os.environ.get("NO_COLOR") is None

    def c(code: str, text: str) -> str:
        return f"{code}{text}{_C.RESET}" if use else text

    lines: list[str] = []
    title = f" cap-evolve report · {s['run_id']} "
    lines.append(c(_C.BOLD, title) + c(_C.GREY, "─" * max(0, width - len(title))))

    # --- KPI strip ------------------------------------------------------
    base = s["baseline_val"]
    best = s["best_val"]
    test = s["test_reward"]
    delta = (f"{s['delta_pct']:+.1f}%" if s.get("delta_pct") is not None
             else (f"{s['delta_abs']:+.3f}" if s.get("delta_abs") is not None else "—"))
    fmt = lambda v: "—" if v is None else f"{v:.3f}"  # noqa: E731
    cnt = s["counts"]
    kpi = [
        ("baseline", fmt(base), _C.GREY),
        ("best val", fmt(best), _C.CYAN),
        ("Δ vs base", delta, _C.GREEN if (s.get("delta_abs") or 0) > 0 else _C.GREY),
        ("test" + (" (sealed)" if s["test_sealed"] else ""), fmt(test), _C.BOLD),
        ("cands", str(cnt["total"]), _C.BLUE),
        ("accept", str(cnt["accepted"]), _C.GREEN),
        ("reject", str(cnt["rejected"]), _C.YELLOW),
        ("failed", str(cnt["failed"]), _C.RED),
        ("frontier", str(s["frontier"]), _C.CYAN),
        ("$", f"{s['cost']['total_usd']:.4f}", _C.GREY),
        ("tok", str(s["tokens"]), _C.GREY),
        ("wall", f"{s['wall_clock_seconds']:.0f}s", _C.GREY),
    ]
    row = "  ".join(c(_C.DIM, k + " ") + c(col, v) for k, v, col in kpi)
    lines.append(row)
    tp = s.get("target_profile")
    if tp:
        lines.append(c(_C.DIM, "consuming model ")
                     + c(_C.CYAN, f"{tp['model']} (tier {tp['tier']})")
                     + c(_C.DIM, "  — capabilities optimized for this reader"))
    lines.append("")

    # --- cumulative-best chart (per iteration) --------------------------
    nodes = sorted([n for n in g["nodes"] if n.get("iteration") is not None],
                   key=lambda n: n["iteration"])
    series = [(n["iteration"], n.get("best_so_far"), n.get("val"), n["status"]) for n in nodes]
    series = [(i, b, v, st) for (i, b, v, st) in series if b is not None]
    if series:
        lines.append(c(_C.BOLD, "cumulative best"))
        chart_h = 6
        vals = [b for _, b, _, _ in series] + [v for _, _, v, _ in series if v is not None]
        lo, hi = min(vals), max(vals)
        span = (hi - lo) or 1.0
        chart_w = min(len(series), width - 10)
        # downsample columns to chart_w
        step = max(1, len(series) // chart_w)
        cols = series[::step]
        grid = [[" "] * len(cols) for _ in range(chart_h)]
        for x, (_, b, v, st) in enumerate(cols):
            yb = chart_h - 1 - int(round((b - lo) / span * (chart_h - 1)))
            grid[yb][x] = "█"
            if v is not None:
                yv = chart_h - 1 - int(round((v - lo) / span * (chart_h - 1)))
                if grid[yv][x] == " ":
                    grid[yv][x] = "·" if st == "rejected" else ("x" if st == "failed" else "○")
        for r, gr in enumerate(grid):
            axis = f"{hi:.2f}" if r == 0 else (f"{lo:.2f}" if r == chart_h - 1 else "    ")
            painted = "".join(c(_C.GREEN, ch) if ch == "█" else
                              (c(_C.RED, ch) if ch == "x" else
                               (c(_C.YELLOW, ch) if ch == "·" else c(_C.CYAN, ch)))
                              for ch in gr)
            lines.append(f"{c(_C.GREY, axis.rjust(5))} {painted}")
        lines.append(c(_C.GREY, "      " + "█ best  ○ accept  · reject  x fail"))
        lines.append("")

    # --- top-N candidate table ------------------------------------------
    ranked = sorted([n for n in g["nodes"] if n.get("val") is not None],
                    key=lambda n: n["val"], reverse=True)[:top_n]
    if ranked:
        lines.append(c(_C.BOLD, f"top {len(ranked)} candidates"))
        hdr = f"{'id':<14}{'status':<10}{'val':>7}{'Δparent':>9}{'iter':>6}"
        lines.append(c(_C.DIM, hdr))
        for n in ranked:
            star = "★" if n["id"] == s["best_id"] else " "
            dlt = (n["val"] - n["parent_val"]) if n.get("parent_val") is not None else None
            stcol = {"accepted": _C.GREEN, "rejected": _C.YELLOW,
                     "failed": _C.RED, "seed": _C.GREY}.get(n["status"], _C.RESET)
            line = (f"{star}{n['id']:<13}" + c(stcol, f"{n['status']:<10}") +
                    f"{n['val']:>7.3f}" +
                    (f"{dlt:>+9.3f}" if dlt is not None else f"{'—':>9}") +
                    f"{n.get('iteration', 0):>6}")
            lines.append(line)
        lines.append("")

    if s["gate_warnings"]:
        lines.append(c(_C.YELLOW, f"⚠ {len(s['gate_warnings'])} gate warning(s):"))
        for w in s["gate_warnings"][:3]:
            txt = (w.get("reason") or "")[: width - 4]
            lines.append(c(_C.GREY, "  " + txt))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# HTML template (inline CSS + JS + SVG). Run data is injected as a JSON island.
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>cap-evolve · run dashboard</title>
<style>
:root{--bg:#08090e;--card:#0e1017;--card2:#161923;--card3:#1e222e;--line:#232936;--text:#e9edf5;
--muted:#949cad;--muted2:#b6bdcb;--accent:#7c5cff;--champion:#f0b429;--ok:#35c88a;--bad:#f2565a;
--warn:#f0b429;--idk:#4aa8ff;--fail:#c05fd8;--radius:12px}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.num{font-variant-numeric:tabular-nums}
header{position:sticky;top:0;z-index:5;background:rgba(14,16,23,.9);backdrop-filter:blur(8px);
border-bottom:1px solid var(--line);padding:14px 28px;display:flex;align-items:baseline;gap:16px}
header h1{font-size:17px;margin:0;font-weight:700;letter-spacing:-.02em}
header .meta{color:var(--muted);font-size:12px}
main{max-width:1180px;margin:0 auto;padding:26px;display:flex;flex-direction:column;gap:26px}
section{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:18px 20px}
section h2{font-size:13px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin:0 0 14px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(132px,1fr));gap:12px}
.kpi{background:var(--card2);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.kpi .l{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em}
.kpi .v{font-size:23px;font-weight:700;margin-top:4px}
.kpi .v.ok{color:var(--ok)} .kpi .v.bad{color:var(--bad)} .kpi .v.acc{color:var(--accent)} .kpi .v.champ{color:var(--champion)}
header .logo{flex:none}
header .tag{color:var(--muted);font-size:12px;margin-left:auto}
.phases{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.phase{background:var(--card2);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.phase .nm{font-weight:600} .phase .st{font-size:11px;text-transform:uppercase;letter-spacing:.05em}
.phase.done{border-color:#1f3a23} .phase.done .st{color:var(--ok)}
.phase.active{border-color:var(--accent)} .phase.active .st{color:var(--accent)}
.phase.pending .st{color:var(--muted)}
.phase .d{color:var(--muted);font-size:11px;margin-top:4px}
.dead{background:var(--card2);border:1px solid var(--line);border-left:3px solid var(--bad);border-radius:0 8px 8px 0;padding:6px 12px;margin:6px 0}
.dead .x{color:var(--bad);font-size:11px;float:right}
.kpi .s{color:var(--muted);font-size:11px;margin-top:2px}
svg{display:block;max-width:100%}
.legend{color:var(--muted);font-size:12px;margin-top:8px;display:flex;gap:16px;flex-wrap:wrap}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}
.tip{position:fixed;pointer-events:none;background:#000d;border:1px solid var(--line);
border-radius:8px;padding:7px 10px;font-size:12px;z-index:50;display:none;max-width:320px;white-space:pre-line}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.04em}
td.r,th.r{text-align:right}
.badge{display:inline-block;padding:1px 8px;border-radius:20px;font-size:11px;font-weight:600}
.b-accepted{background:#1f3a23;color:var(--ok)} .b-rejected{background:#3a2f12;color:var(--warn)}
.b-failed{background:#31173a;color:var(--fail)} .b-seed{background:#22262f;color:var(--muted2)}
.b-indecisive{background:#152a3f;color:var(--idk)}
.pill{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);background:var(--card2);
border-radius:999px;padding:3px 10px;font-size:12px;font-weight:600}
.banner{display:flex;gap:10px;border:1px solid var(--line);border-left:3px solid var(--warn);
background:var(--card2);border-radius:0 10px 10px 0;padding:10px 14px;font-size:12.5px;line-height:1.6;color:var(--muted2)}
.banner.info{border-left-color:var(--accent)} .banner.bad{border-left-color:var(--bad)}
input[type=search],input[type=text]{background:var(--card2);color:var(--text);border:1px solid var(--line);
border-radius:8px;padding:6px 10px;font:inherit}
.logrow{display:grid;grid-template-columns:64px 74px 130px 1fr;gap:8px;align-items:baseline;
padding:3px 6px;border-radius:6px;font-size:12px;cursor:pointer}
.logrow:hover{background:var(--card2)} .logrow .k{font-family:ui-monospace,Menlo,monospace;font-weight:600}
.logdet{background:var(--card2);border:1px solid var(--line);border-radius:8px;margin:2px 0 8px 70px;
padding:8px 10px;font:12px/1.55 ui-monospace,Menlo,monospace;color:var(--muted2);white-space:pre-wrap;overflow:auto;max-height:320px}
.eyebrow{font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.bar{height:5px;border-radius:5px;background:var(--card3);overflow:hidden;max-width:360px}
.bar>i{display:block;height:100%;border-radius:5px}
.hide{display:none!important}
.row{display:flex;gap:18px;flex-wrap:wrap}
.col{flex:1;min-width:280px}
select,button{background:var(--card2);color:var(--text);border:1px solid var(--line);
border-radius:8px;padding:5px 9px;font:inherit;cursor:pointer}
.diff{font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;background:#0b0e13;border:1px solid var(--line);
border-radius:8px;padding:10px;overflow:auto;max-height:420px;white-space:pre}
.diff .add{color:var(--ok)} .diff .del{color:var(--bad)} .diff .hunk{color:var(--accent)} .diff .ctx{color:var(--muted)}
.diff .file{color:var(--text);font-weight:700;margin:8px 0 2px}
.ann{border-left:3px solid var(--warn);padding:6px 12px;margin:8px 0;background:var(--card2);border-radius:0 8px 8px 0}
.ann.diag{border-left-color:var(--accent)}
.ann .who{color:var(--muted);font-size:11px}
.heat rect{cursor:pointer} .heat text{fill:var(--muted);font-size:10px}
code{background:var(--card2);padding:1px 5px;border-radius:5px;font-size:12px}
.muted{color:var(--muted)}
</style></head><body>
<header><svg class="logo" width="26" height="26" viewBox="0 0 48 48" aria-label="cap-evolve">
<path d="M4 40 L16 34 L26 24 L36 14 L44 8" fill="none" stroke="#7c5cff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="44" cy="8" r="2.6" fill="#7c5cff"/>
<g fill="#e6edf3"><ellipse cx="22" cy="33" rx="13" ry="8.5"/><ellipse cx="34" cy="28" rx="7.5" ry="6.5"/>
<ellipse cx="40.5" cy="29.5" rx="3.2" ry="2.6"/><circle cx="31" cy="22" r="1.8"/><circle cx="36" cy="22" r="1.8"/>
<rect x="14" y="38" width="2.8" height="6" rx="1.4"/><rect x="26" y="38" width="2.8" height="6" rx="1.4"/></g>
<circle cx="34" cy="26.5" r="1" fill="#07090d"/></svg>
<h1>cap<span style="color:#7c5cff">·</span>evolve</h1><span class="meta" id="hdr"></span>
<span class="tag">watch capability evolve</span></header>
<main id="main"></main>
<div class="tip" id="tip"></div>
<script type="application/json" id="run-data">/*__RUN_DATA__*/null</script>
<script>
const DATA = JSON.parse(document.getElementById('run-data').textContent);
const G = DATA.graph, S = DATA.summary, DIFFS = DATA.diffs||{};
const $ = (t,a={},...k)=>{const e=document.createElement(t);for(const[p,v]of Object.entries(a)){
  if(p==='html')e.innerHTML=v;else if(p==='text')e.textContent=v;else e.setAttribute(p,v);}
  for(const c of k)if(c!=null)e.append(c);return e;};
const NS='http://www.w3.org/2000/svg';
const svg=(t,a={})=>{const e=document.createElementNS(NS,t);for(const[p,v]of Object.entries(a))e.setAttribute(p,v);return e;};
/* SVG text node WITH content. `el.append(node)` returns undefined, so the old
   `el.append(svg('text',...)).textContent = x` threw a TypeError on the very first axis
   label — which aborted the whole inline script and silently dropped every panel below
   the fitness chart (heatmap, lineage, cost, evaluations, candidates). */
const txt=(el,a,content)=>{const n=svg('text',a);n.textContent=content==null?'':String(content);el.append(n);return n;};
const fmt=v=>v==null?'—':(+v).toFixed(3);
const main=document.getElementById('main'), tip=document.getElementById('tip');
const STATUS_META={running:['running','var(--accent)'],awaiting_agent:['awaiting agent','var(--idk)'],
  completed:['completed','var(--ok)'],budget_exhausted:['budget exhausted','var(--warn)'],
  stalled:['stalled','var(--warn)'],interrupted:['interrupted','var(--fail)'],failed:['failed','var(--bad)']};
document.getElementById('hdr').textContent =
  `${S.run_id} · ${S.algorithm||'algorithm not recorded'} · ${S.counts.total-1} candidates · ` +
  `${S.test_sealed?'test sealed':'test not sealed'}`;
function showTip(e,txt){tip.textContent=txt;tip.style.display='block';
  tip.style.left=Math.min(e.clientX+14,innerWidth-330)+'px';tip.style.top=(e.clientY+14)+'px';}
function hideTip(){tip.style.display='none';}
function sec(title){const s=$('section');s.append($('h2',{text:title}));main.append(s);return s;}
function dsecs(v){v=Math.max(0,Math.round(v||0));if(v<60)return v+'s';
  const m=Math.floor(v/60);if(m<60)return m+'m '+(v%60)+'s';return Math.floor(m/60)+'h '+(m%60)+'m';}

/* ---------- 1. KPI strip ---------- */
(function(){
  const s=sec('Summary'); const g=$('div',{class:'kpis'});
  const dpct=S.delta_pct!=null?`${S.delta_pct>0?'+':''}${S.delta_pct}%`:
            (S.delta_abs!=null?`${S.delta_abs>0?'+':''}${S.delta_abs.toFixed(3)}`:'—');
  const kp=(l,v,cls='',s2='')=>{const k=$('div',{class:'kpi'});k.append($('div',{class:'l',text:l}),
    $('div',{class:'v '+cls,text:v}));if(s2)k.append($('div',{class:'s',text:s2}));return k;};
  const c=S.counts, cost=S.cost;
  g.append(
    kp('best val',fmt(S.best_val),'champ',S.best_id),
    kp('baseline',fmt(S.baseline_val)),
    kp('Δ vs baseline',dpct,(S.delta_abs>0?'ok':'')),
    kp('held-out test',fmt(S.test_reward),'',S.test_sealed?'sealed once':'not finalized'),
    kp('candidates',c.total-(c.seed||0),'',
       `${c.accepted} accept · ${c.rejected} reject · ${c.indecisive||0} indecisive · ${c.failed} no-measure`),
    kp('frontier',S.frontier,'','gated leaves with no accepted child'),
    kp('wall clock',`${S.wall_clock_seconds}s`,'',`opt ${S.optimizer_seconds}s · run ${S.runner_seconds}s`),
    kp('cost',`$${cost.total_usd.toFixed(4)}`,'',`opt $${cost.optimizer_usd.toFixed(4)} · run $${cost.runner_usd.toFixed(4)}`),
    kp('tokens',S.tokens.toLocaleString()),
    kp('unattributed $',
       S.cost_ledger?`$${S.cost_ledger.unattributed_usd.toFixed(4)}`:'—',
       (S.cost_ledger&&Math.abs(S.cost_ledger.unattributed_usd)>0.0005?'champ':''),
       'recorded spend the events cannot explain'),
    kp('events',S.event_count!=null?S.event_count:'—','','every line in events.jsonl')
  );
  s.append(g);
})();

/* ---------- 1b. Run status + split honesty ---------- */
(function(){
  const s=sec('Run status');
  const meta=STATUS_META[S.status]||['unknown','var(--muted)'];
  const head=$('div',{style:'display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-bottom:10px'});
  const pill=$('span',{class:'pill',style:`color:${meta[1]};border-color:${meta[1]}66`});
  pill.append($('span',{style:`width:8px;height:8px;border-radius:50%;background:${meta[1]}`}),
              $('span',{text:meta[0]}));
  head.append(pill);
  if(S.algorithm)head.append($('span',{class:'pill',style:'color:var(--accent);border-color:#7c5cff66',
    text:S.algorithm+(S.algorithm_source?' · from '+S.algorithm_source:'')}));
  head.append($('span',{class:'pill',text:S.test_sealed?'test sealed':'test not sealed'}));
  if(S.elapsed_seconds!=null)head.append($('span',{class:'muted num',text:dsecs(S.elapsed_seconds)+' elapsed'}));
  s.append(head);
  if(S.status_reason)s.append($('p',{class:'muted',style:'margin:0 0 10px',text:S.status_reason}));
  const sp=S.splits;
  if(sp&&sp.no_holdout){
    s.append($('div',{class:'banner',html:'<b>No holdout.</b> train, val and test hold the same tasks, so the '+
      '&ldquo;test&rdquo; number is NOT a generalization estimate &mdash; the optimizer saw those tasks. '+
      'Read it as a sanity check only.'}));
  }
  if(sp&&sp.warning)s.append($('div',{class:'banner',text:sp.warning}));
  if(sp)s.append($('p',{class:'muted num',style:'margin:10px 0 0',
    text:`splits · train ${sp.train??'—'} · val ${sp.val??'—'} · test ${sp.test??'—'}`+
         (sp.seed!=null?` · seed ${sp.seed}`:'')+
         '   —   val decides selection; test is scored exactly once and never optimized against.'}));
})();

/* ---------- 1c. Phases timeline ---------- */
(function(){
  const c=S.counts, total=c.total, evaluated=c.accepted+c.rejected;
  const hasBase=S.baseline_val!=null, finalized=(S.test_reward!=null)||S.test_sealed;
  const D=b=>b?'done':'pending';
  const phases=[
    {nm:'Intake',st:D(total>0||hasBase),d:'Interview + scaffold project, adapter, seed.'},
    {nm:'Implement & check',st:D(total>0||hasBase),d:'Hard gate before any budget is spent.'},
    {nm:'Baseline',st:D(hasBase),d:`Freeze splits; seed val ${fmt(S.baseline_val)}.`},
    {nm:'Optimize'+(S.algorithm?' · '+S.algorithm:''),st:finalized?'done':(hasBase?'active':'pending'),
     d:`${evaluated} iters · ${c.accepted} accepted · best ${fmt(S.best_val)}.`},
    {nm:'Finalize',st:D(finalized),d:`Sealed test ${fmt(S.test_reward)}.`},
    {nm:'Report',st:D(finalized),d:'This dashboard.'},
  ];
  const s=sec('Pipeline phases'); const g=$('div',{class:'phases'});
  for(const p of phases){const e=$('div',{class:'phase '+p.st});
    e.append($('div',{class:'nm',text:p.nm}),$('div',{class:'st',text:p.st}),$('div',{class:'d',text:p.d}));
    g.append(e);}
  s.append(g);
})();

/* ---------- 1d. Rejected edits, deduplicated by reason ---------- */
(function(){
  const norm=r=>(r||'rejected').replace(/-?\d+\.\d+/g,'N').replace(/-?\d+/g,'N').trim();
  const map=new Map();
  for(const n of G.nodes){ if(n.status!=='rejected')continue;
    const k=norm(n.reason); const cur=map.get(k)||{reason:k,count:0,ex:[]};
    cur.count++; if(cur.ex.length<3)cur.ex.push(n.id); map.set(k,cur);}
  const ends=[...map.values()].sort((a,b)=>b.count-a.count);
  if(!ends.length)return;
  const s=sec('Rejected edits, grouped by the gate reason');
  for(const d of ends){const e=$('div',{class:'dead'});
    if(d.count>1)e.append($('span',{class:'x',text:'×'+d.count}));
    e.append($('div',{class:'muted',text:d.ex.join(', ')}),$('div',{text:d.reason}));
    s.append(e);}
})();

/* ---------- 2. Cumulative-best stair over per-iteration scatter ---------- */
(function(){
  const pts=G.nodes.filter(n=>n.iteration!=null&&n.best_so_far!=null)
    .sort((a,b)=>a.iteration-b.iteration);
  if(pts.length<2)return;
  const s=sec('Score over iterations — cumulative best');
  const W=1080,H=300,m={l:46,r:16,t:16,b:30};
  const xs=pts.map(p=>p.iteration), allv=pts.flatMap(p=>[p.best_so_far,p.val].filter(v=>v!=null));
  const xmin=Math.min(...xs),xmax=Math.max(...xs)||1,vmin=Math.min(...allv,0),vmax=Math.max(...allv,1);
  const X=i=>m.l+(i-xmin)/((xmax-xmin)||1)*(W-m.l-m.r);
  const Y=v=>H-m.b-(v-vmin)/((vmax-vmin)||1)*(H-m.t-m.b);
  const el=svg('svg',{viewBox:`0 0 ${W} ${H}`,width:W,height:H});
  for(let g2=0;g2<=4;g2++){const v=vmin+(vmax-vmin)*g2/4;
    el.append(svg('line',{x1:m.l,x2:W-m.r,y1:Y(v),y2:Y(v),stroke:'var(--line)','stroke-width':1}));
    txt(el,{x:6,y:Y(v)+4,fill:'var(--muted)','font-size':10},v.toFixed(2));}
  // stair polyline of running best
  let d='';let prevY=null;
  pts.forEach((p,i)=>{const x=X(p.iteration),y=Y(p.best_so_far);
    if(i===0)d=`M${x},${y}`;else d+=` L${x},${prevY} L${x},${y}`;prevY=y;});
  el.append(svg('path',{d,fill:'none',stroke:'var(--ok)','stroke-width':2}));
  // record-holder rings + per-iter scatter
  let rec=-1;
  pts.forEach(p=>{
    if(p.val!=null){const col=p.status==='accepted'?'var(--ok)':p.status==='failed'?'var(--bad)':'var(--warn)';
      const c=svg('circle',{cx:X(p.iteration),cy:Y(p.val),r:4,fill:col,'fill-opacity':.85,stroke:'var(--bg)'});
      const dpar=p.parent_val!=null?(p.val-p.parent_val).toFixed(3):'—';
      c.addEventListener('mousemove',e=>showTip(e,`${p.id}\n${p.status}  val=${fmt(p.val)}\nΔ parent=${dpar}\niter ${p.iteration}`));
      c.addEventListener('mouseleave',hideTip);el.append(c);}
    if(p.best_so_far>rec){rec=p.best_so_far;
      el.append(svg('circle',{cx:X(p.iteration),cy:Y(p.best_so_far),r:7,fill:'none',stroke:'var(--accent)','stroke-width':1.5}));}
  });
  // champion star + label
  const champ=pts.reduce((a,b)=>(b.best_so_far>=a.best_so_far?b:a),pts[0]);
  const cx=X(champ.iteration),cy=Y(champ.best_so_far);
  el.append(svg('path',{d:starPath(cx,cy-12,7,3),fill:'var(--champion)',stroke:'var(--bg)'}));
  txt(el,{x:cx+10,y:cy-8,fill:'var(--text)','font-size':12},fmt(champ.best_so_far));
  s.append(el);
  s.append($('div',{class:'legend',html:
    '<span><i style="background:var(--ok)"></i>running best / accept</span>'+
    '<span><i style="background:var(--warn)"></i>rejected</span>'+
    '<span><i style="background:var(--bad)"></i>failed</span>'+
    '<span><i style="background:var(--accent);border-radius:50%"></i>record-holder ring</span>'}));
  function starPath(cx,cy,R,r){let p='';for(let i=0;i<10;i++){const ang=Math.PI/5*i-Math.PI/2;
    const rad=i%2?r:R;p+=(i?'L':'M')+(cx+rad*Math.cos(ang))+','+(cy+rad*Math.sin(ang));}return p+'Z';}
})();

/* ---------- 3. tasks × iterations pass/fail heatmap ---------- */
(function(){
  const tasks=S.tasks||[];
  const iters=G.nodes.filter(n=>Object.keys(n.per_task||{}).length).sort((a,b)=>a.iteration-b.iteration);
  if(!tasks.length||iters.length<1)return;
  const s=sec('Per-task pass/fail across iterations');
  // sort rows worst-first by mean reward
  const meanFor=t=>{let sum=0,n=0;iters.forEach(it=>{if(it.per_task[t]!=null){sum+=it.per_task[t];n++;}});return n?sum/n:0;};
  const rows=[...tasks].sort((a,b)=>meanFor(a)-meanFor(b));
  const cw=Math.max(10,Math.min(26,Math.floor(1000/iters.length))),ch=16,labW=120;
  const W=labW+iters.length*cw+10,H=rows.length*ch+24;
  const el=svg('svg',{viewBox:`0 0 ${W} ${H}`,width:W,height:H,class:'heat'});
  iters.forEach((it,j)=>txt(el,{x:labW+j*cw+cw/2,y:12,'text-anchor':'middle'},it.iteration));
  rows.forEach((t,i)=>{
    txt(el,{x:labW-6,y:24+i*ch+11,'text-anchor':'end'},t.length>16?t.slice(0,15)+'…':t);
    iters.forEach((it,j)=>{
      const v=it.per_task[t];
      const col=v==null?'var(--card3)':v>=0.999?'var(--ok)':v<=0.001?'var(--bad)':'var(--warn)';
      const rect=svg('rect',{x:labW+j*cw,y:24+i*ch,width:cw-1.5,height:ch-1.5,rx:2,fill:col});
      const fb=(it.feedback&&it.feedback[t])||'';
      rect.addEventListener('mousemove',e=>showTip(e,`${t} @ iter ${it.iteration} (${it.id})\nreward=${v==null?'—':v.toFixed(3)}\n${fb.slice(0,180)}`));
      rect.addEventListener('mouseleave',hideTip);
      el.append(rect);
    });
  });
  s.append(el);
  s.append($('div',{class:'legend',html:
    '<span><i style="background:var(--ok)"></i>pass</span><span><i style="background:var(--bad)"></i>fail</span>'+
    '<span><i style="background:var(--warn)"></i>partial</span><span><i style="background:var(--card3)"></i>not run</span>'+
    '<span class="muted">rows sorted worst-first · hover a cell for feedback</span>'}));
})();

/* ---------- 4. Per-iteration diff view ---------- */
(function(){
  const ids=Object.keys(DIFFS); if(!ids.length)return;
  const s=sec('Diff vs parent');
  const bar=$('div',{class:'row'});
  const sel=$('select'); ids.forEach(id=>sel.append($('option',{value:id,text:id})));
  const mode=$('select'); mode.append($('option',{value:'unified',text:'unified'}),$('option',{value:'split',text:'split'}));
  bar.append($('span',{class:'muted',text:'candidate '}),sel,$('span',{class:'muted',text:' view '}),mode);
  s.append(bar);
  const out=$('div',{class:'diff'}); s.append(out);
  function esc(t){return t.replace(/&/g,'&amp;').replace(/</g,'&lt;');}
  function render(){
    const id=sel.value, files=DIFFS[id]||[], split=mode.value==='split';
    out.innerHTML='';
    files.forEach(f=>{
      out.append($('div',{class:'file',text:'━ '+f.file}));
      if(!split){
        f.rows.forEach(r=>out.append($('div',{class:r.t,text:r.l})));
      }else{
        const tbl=$('div'); f.rows.forEach(r=>{
          if(r.t==='hunk'){tbl.append($('div',{class:'hunk',text:r.l}));return;}
          const cls=r.t; const line=$('div',{class:cls});
          line.textContent=(r.t==='del'?'◀ ':r.t==='add'?'▶ ':'  ')+r.l.slice(1);
          tbl.append(line);
        }); out.append(tbl);
      }
    });
  }
  sel.addEventListener('change',render); mode.addEventListener('change',render); render();
})();

/* ---------- 5. Lineage tree (DAG, best-spine highlighted) ---------- */
(function(){
  const nodes=G.nodes, byId=Object.fromEntries(nodes.map(n=>[n.id,n]));
  if(nodes.length<2)return;
  const s=sec('Lineage');
  // depth = distance from root; assign columns by BFS order within depth
  const depth={}; const order=[];
  (function walk(id,d){const n=byId[id];if(!n||depth[id]!=null)return;depth[id]=d;order.push(id);
    (n.children||[]).forEach(c=>walk(c,d+1));})('seed',0);
  nodes.forEach(n=>{if(depth[n.id]==null){depth[n.id]=0;order.push(n.id);}});
  const cols={}; const maxd=Math.max(...Object.values(depth));
  const byDepth={}; order.forEach(id=>{const d=depth[id];(byDepth[d]=byDepth[d]||[]).push(id);});
  const pos={};
  for(let d=0;d<=maxd;d++){(byDepth[d]||[]).forEach((id,i)=>pos[id]={x:60+d*150,y:40+i*46});}
  // best-lineage spine
  const spine=new Set(); let cur=S.best_id;
  while(cur){spine.add(cur);cur=byId[cur]?byId[cur].parent:null;}
  const W=80+( maxd+1)*150, H=40+Math.max(...Object.values(byDepth).map(a=>a.length))*46+20;
  const el=svg('svg',{viewBox:`0 0 ${W} ${H}`,width:W,height:H});
  nodes.forEach(n=>{const p=pos[n.id];if(!p)return;
    const parents=[n.parent,...(n.merge_of||[])].filter(x=>x&&pos[x]);
    parents.forEach(pp=>{const a=pos[pp];const onSpine=spine.has(n.id)&&spine.has(pp);
      el.append(svg('path',{d:`M${a.x+14},${a.y} C${(a.x+p.x)/2},${a.y} ${(a.x+p.x)/2},${p.y} ${p.x-14},${p.y}`,
        fill:'none',stroke:onSpine?'var(--champion)':'var(--line)','stroke-width':onSpine?2.5:1.2}));});
  });
  nodes.forEach(n=>{const p=pos[n.id];if(!p)return;
    const col=n.status==='accepted'?'var(--ok)':n.status==='rejected'?'var(--warn)':n.status==='failed'?'var(--bad)':'var(--accent)';
    const c=svg('circle',{cx:p.x,cy:p.y,r:n.id===S.best_id?9:6,fill:col,
      stroke:spine.has(n.id)?'var(--champion)':'var(--bg)','stroke-width':spine.has(n.id)?2:1});
    c.addEventListener('mousemove',e=>showTip(e,`${n.id}\n${n.status}  val=${fmt(n.val)}\n${n.reason||''}`));
    c.addEventListener('mouseleave',hideTip); el.append(c);
    txt(el,{x:p.x+12,y:p.y+4,fill:'var(--muted)','font-size':10},n.id);
  });
  s.append(el);
  s.append($('div',{class:'legend',html:'<span><i style="background:var(--champion)"></i>best lineage spine</span>'+
    '<span class="muted">merges shown as multi-parent edges</span>'}));
})();

/* ---------- 6d. Evaluations (split-oriented, distinct from per-iteration) ---------- */
(function(){
  const evals=S.evaluations||[];
  if(!evals.length)return;
  const s=sec('Evaluations');
  s.append($('p',{class:'muted',text:'Each scoring of a candidate on a split — '+
    'baseline (seed on val), every full val eval, and the sealed test eval. '+
    'Distinct from the optimizer-step view above.'}));
  const t=$('table');
  t.append($('tr',{},$('th',{text:'kind'}),$('th',{text:'candidate'}),$('th',{text:'split'}),
    $('th',{class:'r',text:'reward ± stderr'}),$('th',{class:'r',text:'runner $'}),
    $('th',{class:'r',text:'time'}),$('th',{class:'r',text:'tokens'}),$('th',{class:'r',text:'tasks × trials'})));
  const dsec=v=>{v=Math.max(0,Math.round(v||0));if(v<60)return v+'s';
    const m=Math.floor(v/60);if(m<60)return m+'m '+(v%60)+'s';return Math.floor(m/60)+'h '+(m%60)+'m';};
  const kindBadge={baseline:'b-seed',candidate:'b-accepted',test:'b-failed'};
  evals.forEach(e=>{
    const re=e.reward==null?'—':fmt(e.reward)+(e.stderr!=null?' ± '+(+e.stderr).toFixed(3):'');
    t.append($('tr',{},
      $('td',{},$('span',{class:'badge '+(kindBadge[e.kind]||'b-seed'),text:e.kind})),
      $('td',{},$('code',{text:e.candidate})),
      $('td',{class:'muted',text:e.split}),
      $('td',{class:'r num',text:re}),
      $('td',{class:'r num',text:e.cost_usd?'$'+(+e.cost_usd).toFixed(4):'—'}),
      $('td',{class:'r num',text:dsec(e.seconds)}),
      $('td',{class:'r num',text:(e.tokens||0).toLocaleString()}),
      $('td',{class:'r num',text:(e.n_tasks||0)+' × '+(e.trials||1)})));
  });
  s.append(t);
})();

/* ---------- 6e. Cost ledger — every dollar, attributed ---------- */
(function(){
  const L=S.cost_ledger; if(!L||!L.rows.length)return;
  const s=sec('Cost ledger — where every dollar went');
  const head=$('div',{style:'display:flex;flex-wrap:wrap;gap:22px;margin-bottom:12px'});
  const stat=(l,v,cls='')=>{const d=$('div');d.append($('div',{class:'eyebrow',text:l}),
    $('div',{class:'num '+cls,style:'font-weight:700;margin-top:2px',text:v}));return d;};
  const off=Math.abs(L.unattributed_usd)>0.0005;
  head.append(stat('total recorded','$'+L.total_usd.toFixed(4),''),
              stat('attributed to events','$'+L.attributed_usd.toFixed(4)),
              stat('unattributed','$'+L.unattributed_usd.toFixed(4),off?'':'muted'),
              stat('rows with no cost recorded',String(L.rows_missing_cost)));
  s.append(head);
  if(off)s.append($('div',{class:'banner',text:
    '$'+Math.abs(L.unattributed_usd).toFixed(4)+' of recorded spend is not accounted for by the rows '+
    'below. That happens when a phase records into the run spend accounting without emitting a '+
    'cost-bearing event (agent-mode commits are the common case). Shown rather than hidden.'}));
  const KC={intake:'var(--muted2)',baseline_eval:'var(--accent)',candidate_eval:'var(--ok)',
            optimizer_call:'var(--champion)',test_eval:'var(--idk)'};
  const PH={intake:'Intake',baseline:'Baseline',optimize:'Optimize',finalize:'Finalize (sealed test)'};
  const maxRow=Math.max(1e-9,...L.rows.map(r=>r.usd||0));
  for(const ph of ['intake','baseline','optimize','finalize']){
    const rows=L.rows.filter(r=>r.phase===ph); if(!rows.length)continue;
    const sum=rows.reduce((a,r)=>a+(r.usd||0),0), miss=rows.filter(r=>r.usd==null).length;
    s.append($('h2',{style:'margin:16px 0 6px;text-transform:none;letter-spacing:0;font-size:13px;color:var(--text)',
      text:`${PH[ph]} — $${sum.toFixed(4)}`+(miss?`  (+${miss} unrecorded)`:'')}));
    const t2=$('table');
    rows.forEach(r=>{
      const label=$('td');
      const line=$('div',{style:'display:flex;align-items:center;gap:8px'});
      line.append($('span',{style:`width:9px;height:9px;border-radius:2px;flex:none;background:${KC[r.kind]||'var(--muted)'}`}),
                  $('span',{text:r.label}));
      label.append(line);
      if(r.note)label.append($('div',{class:'muted',style:'font-size:11px;margin-left:17px',text:r.note}));
      const bar=$('div',{class:'bar',style:'margin:5px 0 0 17px'});
      bar.append($('i',{style:`width:${((r.usd||0)/maxRow*100).toFixed(1)}%;background:${KC[r.kind]||'var(--muted)'}`}));
      label.append(bar);
      t2.append($('tr',{},label,
        $('td',{class:'r num',text:r.usd==null?'—':'$'+(+r.usd).toFixed(4)}),
        $('td',{class:'r num muted',text:dsecs(r.seconds)}),
        $('td',{class:'r num muted',text:r.tokens?(+r.tokens).toLocaleString():'—'})));
    });
    s.append(t2);
  }
  s.append($('div',{class:'legend',html:'<span class="muted">a &ldquo;—&rdquo; is a cost that was never '+
    'recorded; it is never rendered as $0</span>'}));
})();

/* ---------- 6f. Gate decisions — Δ̄ with its SE and n ---------- */
(function(){
  const D=S.gate_decisions||[]; if(!D.length)return;
  const s=sec('Gate decisions');
  const idk=D.filter(d=>d.verdict==='indecisive');
  if(idk.length)s.append($('div',{class:'banner',html:'<b>'+idk.length+' step(s) indecisive.</b> The gate '+
    'REFUSED to judge — too little of the split ran, or the candidate edited a protected file. That is '+
    'missing data, not a bad edit: these are excluded from the running best and from the stall counter.'}));
  const t2=$('table');
  t2.append($('tr',{},$('th',{text:'iter'}),$('th',{text:'candidate'}),$('th',{text:'verdict'}),
    $('th',{class:'r',text:'val'}),$('th',{class:'r',text:'parent val'}),$('th',{class:'r',text:'Δ̄'}),
    $('th',{class:'r',text:'SE'}),$('th',{class:'r',text:'n'}),$('th',{class:'r',text:'bar (k·SE)'})));
  const BADGE={accept:'b-accepted',reject:'b-rejected',indecisive:'b-indecisive'};
  const n4=v=>v==null?'—':(+v).toFixed(4);
  D.forEach(d=>{
    t2.append($('tr',{},
      $('td',{class:'num muted',text:d.iteration??'—'}),
      $('td',{},$('code',{text:d.candidate})),
      $('td',{},$('span',{class:'badge '+(BADGE[d.verdict]||'b-failed'),text:d.verdict})),
      $('td',{class:'r num',text:fmt(d.val)}),
      $('td',{class:'r num muted',text:fmt(d.parent_val)}),
      $('td',{class:'r num',style:d.delta==null?'':('color:'+(d.delta>0?'var(--ok)':d.delta<0?'var(--bad)':'var(--muted)')),
              text:d.delta==null?'—':(d.delta>0?'+':'')+d.delta.toFixed(4)}),
      $('td',{class:'r num muted',text:d.stderr==null?'—':'±'+d.stderr.toFixed(4)}),
      $('td',{class:'r num muted',text:d.n??'—'}),
      $('td',{class:'r num muted',text:n4(d.threshold)+(d.k_se!=null?'  k='+d.k_se:'')})));
  });
  s.append(t2);
  D.forEach(d=>s.append($('div',{class:'ann',style:'margin:6px 0'},
    $('div',{class:'who',text:d.candidate}),$('div',{text:d.reason}))));
})();

/* ---------- 9. Activity log — every event, filterable ---------- */
(function(){
  const LOG=S.log||[]; if(!LOG.length)return;
  const s=sec('Activity log — every event this run recorded');
  const bar=$('div',{class:'row',style:'margin-bottom:10px;align-items:center'});
  const q=$('input',{type:'search',placeholder:'search kind, candidate, message…',style:'flex:1;min-width:180px'});
  const phase=$('select'); ['all','intake','baseline','optimize','finalize'].forEach(p2=>
    phase.append($('option',{value:p2,text:p2})));
  const kind=$('select');
  ['all',...[...new Set(LOG.map(r=>r.kind))].sort()].forEach(k=>kind.append($('option',{value:k,text:k})));
  const count=$('span',{class:'muted num'});
  bar.append(q,$('span',{class:'muted',text:'phase'}),phase,$('span',{class:'muted',text:'kind'}),kind,count);
  s.append(bar);
  const list=$('div'); s.append(list);
  const TONE={optimizer_error:'var(--bad)',tamper_detected:'var(--bad)',step_indecisive:'var(--idk)',
    accept:'var(--ok)',finalize:'var(--ok)',reject:'var(--bad)',evaluate:'var(--accent)',
    minibatch:'var(--accent)',gate_warning:'var(--warn)',budget_warning:'var(--warn)',
    splits_warning:'var(--warn)'};
  const clock=t2=>t2==null?'--:--:--':new Date(t2*1000).toLocaleTimeString([], {hour12:false});
  function gist(r){
    const d=r.detail||{}, b=[];
    if(d.split)b.push('split='+d.split);
    if(typeof d.reward==='number')b.push('reward='+d.reward.toFixed(3));
    if(typeof d.val==='number')b.push('val='+d.val.toFixed(3));
    if(typeof d.cost_usd==='number')b.push('$'+d.cost_usd.toFixed(4));
    if(typeof d.opt_cost_usd==='number')b.push('opt $'+d.opt_cost_usd.toFixed(4));
    if(d.accept!==undefined)b.push(d.accept?'ACCEPT':'reject');
    return b.length?b.join('  '):(r.text||Object.keys(d).join(', '));
  }
  const open=new Set();
  function render(){
    const needle=q.value.trim().toLowerCase();
    const rows=LOG.filter(r=>{
      if(phase.value!=='all'&&r.phase!==phase.value)return false;
      if(kind.value!=='all'&&r.kind!==kind.value)return false;
      if(!needle)return true;
      return (r.kind+' '+(r.candidate||'')+' '+(r.text||'')+' '+JSON.stringify(r.detail||{}))
        .toLowerCase().includes(needle);
    });
    count.textContent=rows.length+'/'+LOG.length;
    list.innerHTML='';
    if(!rows.length){list.append($('p',{class:'muted',text:'No event matches this filter.'}));return;}
    rows.forEach(r=>{
      const row=$('div',{class:'logrow'});
      row.append($('span',{class:'muted num',text:clock(r.t)}),
        $('span',{class:'muted',style:'font-size:10px;text-transform:uppercase;letter-spacing:.05em',text:r.phase}),
        $('span',{class:'k',style:'color:'+(TONE[r.kind]||'var(--muted2)'),
                  text:r.kind+(r.candidate?' '+r.candidate:'')}),
        $('span',{class:'muted2',style:'color:var(--muted2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap',
                  text:gist(r)}));
      list.append(row);
      const det=$('div',{class:'logdet'});
      // textContent only: this text is model/subprocess-authored and must never be parsed as markup.
      det.textContent=(r.text?r.text+'\n\n':'')+
        Object.entries(r.detail||{}).map(([k,v])=>k+' = '+(typeof v==='object'&&v!==null?JSON.stringify(v):String(v))).join('\n');
      det.style.display=open.has(r.seq)?'block':'none';
      list.append(det);
      row.addEventListener('click',()=>{
        if(open.has(r.seq)){open.delete(r.seq);det.style.display='none';}
        else{open.add(r.seq);det.style.display='block';}
      });
    });
  }
  q.addEventListener('input',render);phase.addEventListener('change',render);
  kind.addEventListener('change',render);render();
})();

/* ---------- 10. evograph weakness graph (replaces the embedded viewer) ---------- */
(function(){
  const EG=(S.algo_extra||{}).evograph; if(!EG)return;
  const s=sec('Weakness graph — evograph');
  const rounds=(EG.rounds||[]).filter(r=>r.split!=='test');
  const final=(EG.rounds||[]).find(r=>r.split==='test');
  const prim=r=>r.primary_metric?r.metrics[r.primary_metric]:null;
  if(rounds.length){
    const max=Math.max(1e-9,...rounds.map(r=>prim(r)||0),(final?prim(final):0)||0);
    const wrap=$('div',{style:'display:flex;align-items:flex-end;gap:14px;margin-bottom:12px'});
    const col=(label,v,color,note)=>{const d=$('div',{style:'display:flex;flex-direction:column;align-items:center;gap:5px;flex:1'});
      d.append($('span',{class:'num',style:'font-weight:700;font-size:12px',text:v==null?'—':(v*100).toFixed(1)+'%'}),
        $('div',{style:`width:100%;max-width:64px;height:${Math.max(4,(v||0)/max*110)}px;border-radius:4px 4px 0 0;background:${color}`}),
        $('span',{class:'eyebrow',text:label}),$('span',{class:'muted num',style:'font-size:10px',text:note||''}));
      return d;};
    rounds.forEach(r=>wrap.append(col('round '+r.round,prim(r),'var(--accent)',
      (r.num_tasks??'—')+' tasks'+(r.completed_at==null?' · running':''))));
    if(final)wrap.append(col('sealed test',prim(final),'var(--ok)',
      final.cost_usd!=null?'$'+(+final.cost_usd).toFixed(4):''));
    s.append(wrap);
    s.append($('p',{class:'muted',style:'margin:0 0 12px',text:
      'The sealed test sits apart from the rounds on purpose — it is scored once, on data no round touched.'}));
  }
  (EG.weaknesses||[]).forEach(w=>{
    const box=$('div',{class:'dead',style:'border-left-color:var(--accent)'});
    const head=$('div',{style:'display:flex;flex-wrap:wrap;gap:8px;align-items:center'});
    head.append($('code',{text:w.slug}),$('span',{class:'badge b-seed',text:String(w.status||'unknown')}));
    (w.tags||[]).forEach(tg=>head.append($('span',{class:'muted',style:'font-size:11px',text:tg})));
    head.append($('span',{class:'muted num',style:'margin-left:auto;font-size:11px',
      text:(w.num_solutions||0)+' solution(s)'}));
    box.append(head);
    const bits=['discovered round '+(w.discovered_in_round??'—')];
    if(w.solved_in_round!=null)bits.push('solved round '+w.solved_in_round);
    if((w.affected_tasks||[]).length)bits.push('affects '+w.affected_tasks.join(', '));
    if((w.related||[]).length)bits.push('related → '+w.related.join(', '));
    box.append($('div',{class:'muted num',style:'font-size:11px;margin-top:4px',text:bits.join('  ·  ')}));
    s.append(box);
  });
})();

/* ---------- 8. Candidate leaderboard + git log ---------- */
(function(){
  const s=sec('Candidates'); const t=$('table');
  t.append($('tr',{},$('th',{text:'id'}),$('th',{text:'status'}),$('th',{class:'r',text:'val'}),
    $('th',{class:'r',text:'Δ parent'}),$('th',{class:'r',text:'iter'}),$('th',{text:'reason'})));
  G.nodes.slice().sort((a,b)=>(b.val||-1)-(a.val||-1)).forEach(n=>{
    const dlt=n.parent_val!=null&&n.val!=null?(n.val-n.parent_val):null;
    t.append($('tr',{},
      $('td',{},n.id===S.best_id?'★ '+n.id:n.id),
      $('td',{},$('span',{class:'badge b-'+n.status,text:n.status})),
      $('td',{class:'r num',text:fmt(n.val)}),
      $('td',{class:'r num',text:dlt==null?'—':(dlt>0?'+':'')+dlt.toFixed(3)}),
      $('td',{class:'r num',text:n.iteration}),
      $('td',{class:'muted',text:(n.reason||'').slice(0,80)})));
  });
  s.append(t);
  if(S.git_log&&S.git_log.length){
    s.append($('h2',{text:'Iteration store (git)',style:'margin-top:18px'}));
    const g=$('div',{class:'diff'});
    S.git_log.forEach(r=>g.append($('div',{class:'ctx',text:r.hash+'  '+r.subject})));
    s.append(g);
  }
})();
</script></body></html>
"""
