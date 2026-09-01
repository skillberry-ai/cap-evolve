"""host.py — drive this skill's loop from a NON-INTERACTIVE caller (CI, cron, a script).

agent-optimize's loop is prose in ``SKILL.md``, executed by the conversational agent that
ran intake. ``cap-evolve run`` (agent mode) does check + baseline, prints a handoff, and
returns: no algorithm subprocess, no auto-finalize. That is exactly right with a human in
the loop and leaves the algorithm *unavailable* anywhere without one — a CI job gets the
handoff and then nothing happens.

This script is the missing host, and deliberately owns as little as possible. Everything it
borrows, and from where:

  * the **loop** stays in ``SKILL.md`` + this dir's helpers. The briefing points at them; it
    does not restate the algorithm, because a second copy of the loop would drift from the
    first and there would be no way to tell which one ran.
  * the **CLI invocation** goes through ``optimizers/run-optimizer``, which already resolves a
    registry row, substitutes ``{model}``, maps ``--budget``/``--usd-budget`` to that CLI's own
    flags, captures cost from its JSON output, and hard-fails when the CLI is absent — and
    whose ``load_registry`` also answers "is this a known agent?".
  * the **read-context** is ``harness.OptimizerContext``: ``inject()`` stages the capability
    skills, the diagnose method, the sources and the trajectories exactly as every
    deterministic algorithm gets them, and ``capability_brief()`` / ``reader_brief()`` /
    ``empty_seed_brief()`` supply the measured prompt blocks. This script previously
    hand-rolled thinner equivalents, and the consequence was measurable: with
    ``_CAP_EDIT_SPACE``'s "the highest-leverage edit is a new code-bearing tool" and the
    target-reader block both absent, the hosted optimizer only ever edited prose.
  * the **spec resolution** for ``optimizer_instructions_file`` is
    ``specfile.resolve_instructions_file``, shared with ``cli.py``. Two copies of a path
    resolution rule is how #252 happened.
  * the **seal** is ``measure.py``, the same script the skill documents.

What it does NOT borrow: ``OptimizerContext.instructions()``. That renders the per-iteration
contract — "fix many root causes in this ONE candidate and STOP; the harness re-scores you" —
which is false here, where the agent owns the search, the evaluation and the gate. The blocks
are composed instead, and an arm's own instructions template is included with its scope stated.

What is genuinely this script's own:

**A raised Bash-tool ceiling.** Every loop command is a shell call, and a full-val eval on
a real benchmark runs for hours. Claude Code caps one Bash call at ``BASH_MAX_TIMEOUT_MS``
(default 600000 = 10 min) and the effective ceiling is ``max(default, max)``, so both are
raised. Left alone, every eval is killed mid-flight and an entirely healthy run reads as a
broken runner.

**A guaranteed seal.** An agent that exhausts its turns or dies mid-loop leaves no
``final.json``. CI then cannot distinguish "stopped early" from "a step crashed", and there
is no honest number at all. So if the agent did not seal, the host does — through the same
``measure.py`` the skill documents, labelled ``seal: host`` so nobody mistakes it for the
agent's own judgement that it was finished.

The seal is idempotent: an already-sealed run reports ``seal: agent`` rather than raising
``TestSealError`` out of the host and failing a run that is actually complete.

**A foreground contract, and a backstop for when it is broken.** The turn budget is not the
only way an unattended loop stops short. On run 32814848187 the agent used 78 of 600 turns and
stopped on ``subtype: success`` / ``stop_reason: end_turn``: it had backgrounded round 2's gate
and ended its turn to await a notification, which ends the process here — there is no
conversation to resume it. So the briefing states the invariant (the turn that launches work is
the turn that collects it; delegate the work, never the waiting — subagents and parallel evals
stay encouraged), and ``unbooked_rounds`` reports candidates a round gated to a verdict that no
``commit.py`` booked, since ``spent.iterations`` cannot tell that from a round never attempted.
It reports rather than books: booking an accept after ``measure.py`` sealed against the old
``best_id`` would convert a visible gap into a wrong headline number.

That check runs AFTER the seal on purpose — the abandoned round's evals outlived the agent by
14 minutes, so a pre-seal check would have found an empty ``work/``.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import _bootstrap  # noqa: F401

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
SKILLS = SKILL_DIR.parents[1]
RUN_OPTIMIZER = SKILLS / "optimizers" / "run-optimizer" / "scripts" / "run.py"
REGISTRY = SKILLS / "optimizers" / "registry.yaml"

# 4h. Long enough for a full-val eval on the slowest benchmark in this repo
# (spreadsheetbench full: one Docker container per task x trials), while still bounding a
# genuinely hung command instead of waiting forever.
BASH_TIMEOUT_MS = 4 * 60 * 60 * 1000
#: Measurement concurrency handed to the agent when the spec names none. Matches ``round.py``'s
#: own default and its refusal bound; see the concurrency note in the briefing.
GATE_CONCURRENCY = 8


def _spec(project: Path, spec_path: Path | None) -> dict:
    from cap_evolve.specfile import read_yaml

    path = spec_path or (project / "capevolve.yaml")
    if not path.exists():
        return {}
    return read_yaml(path.read_text(encoding="utf-8")) or {}


def _known_agents() -> list[str]:
    """Registry rows, read by run-optimizer's own loader rather than a second parser."""
    try:
        sys.path.insert(0, str(RUN_OPTIMIZER.parent))
        import run as _run_optimizer  # run-optimizer/scripts/run.py

        return sorted((_run_optimizer.load_registry() or {}).keys())
    except Exception:  # noqa: BLE001 — a missing registry is reported by the caller below
        return []


def _editable_files(run_dir: Path, project: Path, spec: dict) -> list[str]:
    """The capability's real files, relative — the surface the agent may actually edit.

    ``capabilities`` names which capability skills' ``validate()`` runs; it does NOT restrict
    what may be written. Handing the agent only those names is what leaves most of the
    surface untouched: in one measured run a spec declaring both a prompt capability and a
    tool-code capability produced 2 of 2 candidates that edited only the prompt file, while
    the tool code sat writable and unopened in the same candidate dir.

    Read from the materialized seed candidate (what the agent copies and edits) rather than
    from the project's capability_path, so this is the same file set it will really see.
    """
    root = run_dir / "candidates" / "seed"
    if not root.is_dir():
        cap = str(spec.get("capability_path") or "seed_capability")
        root = (project / cap).resolve()
    if not root.is_dir():
        return []
    skip_dirs = {"__pycache__", ".git"}
    files = [
        p.relative_to(root).as_posix()
        for p in sorted(root.rglob("*"))
        if p.is_file()
        and not any(part in skip_dirs for part in p.parts)
        and p.suffix not in {".pyc", ".pyo"}
    ]
    return files


#: Suffixes that make a capability file CODE rather than prose. Drives whether the briefing
#: offers code-vs-prose advice at all — see _surface_section.
#:
#: KNOWN-GOOD, NOT EXHAUSTIVE. A missing suffix means the code-guard advice silently does not
#: fire, which is the same silent-miss this host was fixed for on ``.py``/``.js`` — just
#: relocated to whichever language nobody listed. It started at 14 entries and therefore
#: treated C, C++, C#, PHP, Swift, Kotlin and Objective-C surfaces as prose. So: ADD to this
#: set freely when a workload brings a new language; absence here is a gap, never a decision
#: that the language is prose.
#:
#: A suffix list is deliberately kept as the test rather than the capability's declared kind.
#: Kind is only a proxy — a ``tools`` capability can be schema-only and a ``system-prompt`` one
#: can ship a helper script — whereas the question the briefing actually asks is "does the
#: surface I am handing you contain code you could put a guard in".
_CODE_SUFFIXES = {
    # scripting / dynamic
    ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".rb", ".pl", ".lua", ".php",
    ".r", ".jl", ".dart", ".groovy", ".tcl",
    # shell
    ".sh", ".bash", ".zsh", ".fish", ".ps1",
    # compiled / systems
    ".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".cs", ".go", ".rs", ".java", ".kt",
    ".kts", ".swift", ".m", ".mm", ".scala", ".zig", ".nim", ".d", ".f90", ".vb",
    # functional
    ".ex", ".exs", ".erl", ".hs", ".ml", ".mli", ".clj", ".cljs", ".fs", ".fsx", ".rkt",
    ".scm", ".lisp", ".el",
    # query / template languages that carry real logic
    ".sql", ".vim",
}
#: Above this, the listing is grouped instead of enumerated. A skill-package capability can
#: be dozens of files, and a wall of paths crowds out the rest of the briefing.
_MAX_LISTED = 20


def _surface_section(files: list[str]) -> str:
    """Render the editable-file list, and say what a prompt-only edit leaves undone.

    Scaled to what is actually there, in two ways that matter for genericity:

    * **Code advice only when there is code.** A capability of two prose files (a system
      prompt plus a task template) told to "prefer an in-code guard" goes looking for code it
      does not own — the failure that once had a prompt-only optimizer editing ``adapter.py``.
    * **Grouped, never silently truncated, when large.** A skill-package capability can run to
      dozens of files. Bounding the list is fine; bounding it without saying so is not, since
      the reader then takes it as the complete surface.
    """
    if not files:
        return ""
    if len(files) == 1:
        return (f"## Your editable surface — one file\n\n- `{files[0]}`\n\n"
                "That file is the whole capability. There is no second surface, so do not go "
                "looking for one outside it.\n")

    has_code = any(Path(f).suffix in _CODE_SUFFIXES for f in files)

    if len(files) <= _MAX_LISTED:
        listing = "\n".join(f"- `{f}`" for f in files)
        head = f"## Your editable surface — ALL {len(files)} of these files\n\n{listing}\n"
    else:
        groups: dict[str, list[str]] = {}
        for f in files:
            parts = f.split("/")
            groups.setdefault(parts[0] if len(parts) > 1 else ".", []).append(f)
        rows = []
        shown = 0
        for g, gf in sorted(groups.items()):
            examples = ", ".join(f"`{x}`" for x in gf[:3])
            more = f", +{len(gf) - 3} more" if len(gf) > 3 else ""
            shown += min(len(gf), 3)
            label = f"`{g}/`" if g != "." else "top level"
            rows.append(f"- {label} — {len(gf)} file(s): {examples}{more}")
        head = (
            f"## Your editable surface — {len(files)} files\n\n" + "\n".join(rows) + "\n\n"
            f"Grouped because there are {len(files)}; {len(files) - shown} are not listed "
            f"individually above. **Enumerate the full set yourself** (`find` the candidate "
            f"dir) before deciding a file is out of scope — everything under it is editable, "
            f"not only the files named here.\n")

    body = (
        "\nEvery one of them is in your candidate copy and every one is fair game — prose, "
        "code, data, nested files alike. A round that changes **only the obvious prompt "
        "file** leaves the rest of the agent's instruction and behaviour surface exactly as "
        "it was, and that is the most common way a run produces nothing: the fix that was "
        "needed lived in a file nobody opened.\n\n"
        "So before you write an edit, decide *which file* is the right place for it — the "
        "allowed edit space per capability, and which form has the most leverage on each, is "
        "in the capability brief below rather than restated here. Name the file you chose in "
        "the `commit.py --note` for the round, so the run records which surface each decision "
        "was made on.\n\n"
             "### Precondition on round 3 and later\n\n"
             "**If your last two rounds were both rejected, the next round may not reuse the "
             "surface *and* form those two used.** Read the rejected candidate's trace first "
             "and ask whether the agent ever exercised your rule at all: never exercised means "
             "the FORM was wrong, so a third variation of the same wording will be rejected "
             "too. Change the form, or change the surface")
    if has_code:
        body += (" — and where the failing behaviour is one the agent has a criterion for and "
                 "violates anyway (it *should* call a tool and does not, it *should* validate "
                 "and does not), the form that works is a guard in the code, not a third "
                 "restatement in prose")
    body += (".\n\nTwo rejections are not a reason to stop — they are the signal to escalate. "
             "Spend every round the budget allows.\n")
    return head + body


def _arm_section(text: str) -> str:
    """Include the arm's own instructions — with their scope stated, not silently merged.

    That file was authored for the DETERMINISTIC per-iteration optimizer, so its process half
    actively contradicts this loop: it says to stop after editing and not to evaluate, because
    there the harness re-scores the candidate. Here the agent owns the evaluation and the gate,
    and an agent obeying that line would never gate anything.

    What is uniquely valuable in it is the benchmark's own constraints — which files are
    editable, which tokens are load-bearing, what silently zeroes a score. So the precedence is
    stated explicitly instead of leaving the agent to guess which half to follow.
    """
    if not text.strip():
        return ""
    return (
        "## Benchmark-specific instructions for THIS capability\n\n"
        "Authored for this project. Read them for the **benchmark's own facts and "
        "constraints** — which files are editable, which tokens are load-bearing, what "
        "silently zeroes a score. Those are measured on this benchmark, are repeated nowhere "
        "else in this briefing, and are binding.\n\n"
        "**Scope, because they were written for the other loop:** they address a per-iteration "
        "optimizer that proposes one edit and stops while the harness scores it. You own the "
        "whole search, so anything in them about stopping after an edit, not evaluating, or "
        "iteration budget does NOT apply — the loop in SKILL.md and this briefing wins there. "
        "On benchmark facts, they win.\n\n"
        "<arm_instructions>\n" + text.strip() + "\n</arm_instructions>\n")


def _shared_blocks(ctx, run_dir: Path, context: dict) -> str:
    """The prompt blocks the DETERMINISTIC path has always had, from the same source.

    Not re-authored here. Every deterministic algorithm gets these through
    ``OptimizerContext``; agent mode used to hand-roll thinner equivalents, and the measured
    consequence was an optimizer that only ever edited prose — because the block naming tool
    code as the highest-leverage surface (``harness._CAP_EDIT_SPACE``) and the block saying a
    weak reader needs code enforcement over terse prose (the target-reader profile) were both
    absent. Reusing them is the fix; writing better prose here would not have been.
    """
    parts = []
    brief = ctx.capability_brief()
    if brief:
        parts.append(brief)
        if context.get("staged"):
            parts.append("Each `./guidance/<cap>/SKILL.md` above is staged in your working "
                         "directory and also under the native skills dir. **Read the one for "
                         "the surface you are about to edit** — an edit made without it is a "
                         "guess, and the surface you have no guidance for is the one you will "
                         "avoid by default.")
    reader = ctx.reader_brief()
    if reader:
        parts.append(reader)
    empty = ctx.empty_seed_brief(run_dir / "candidates" / "seed")
    if empty:
        parts.append(empty)
    return "\n\n".join(p.strip() for p in parts if p and p.strip())


def _briefing(*, run_dir: Path, project: Path, spec: dict, skills: Path,
              rounds: int, workdir: Path, context: dict, arm: str = "",
              ctx=None) -> str:
    """The driver briefing: the handoff facts, then a pointer to the loop itself.

    Deliberately NOT a restatement of the algorithm. SKILL.md is the implementation and the
    agent reads it; what it cannot know are the paths, the spec values, the shared prompt
    blocks, and the fact that nobody is available to answer a question.
    """
    stop = str(spec.get("stop_condition") or "").strip()
    n_trials = spec.get("num_trials", 1)
    k_se = spec.get("gate_k_se", 1.0)
    gate_mode = spec.get("gate_mode", "paired")
    caps = spec.get("capabilities") or []
    cap_path = spec.get("capability_path") or "seed_capability"
    surface = _surface_section(_editable_files(run_dir, project, spec))
    guidance = _shared_blocks(ctx, run_dir, context) if ctx is not None else ""
    arm_block = _arm_section(arm)
    skill_md = SKILL_DIR / "SKILL.md"
    helpers = HERE
    # Quoted from the constant that actually sets BASH_*_TIMEOUT_MS below, so the briefing
    # cannot promise a ceiling the env does not grant.
    hours = round(BASH_TIMEOUT_MS / 3_600_000, 1)
    hours = int(hours) if hours == int(hours) else hours
    # The interpreter that launched us — see _agent_env for why this is the authority.
    interpreter = sys.executable
    gate_conc = int(spec.get("measure_concurrency") or GATE_CONCURRENCY)

    if not stop:
        stop = (f"Spend at most {rounds} rounds, gate every candidate on FULL val, and "
                "finish by sealing test exactly once with measure.py.")

    return f"""# Drive the agent-optimize loop on an existing run — unattended

You are the optimizer for a cap-evolve run that is ALREADY set up and baselined.
`cap-evolve run` finished check + baseline and handed the loop over. Your job is to run the
`agent-optimize` loop against it and finish with one honest sealed measurement.

## Read this first

`{skill_md}`

That file IS the algorithm — its "Agent-mode loop" section is what you execute, step by
step, including Phase 0. Its helper scripts are in `{helpers}`. Do not re-derive the loop
from this briefing; this briefing only gives you the facts SKILL.md cannot know.

## The handoff

```bash
R="{run_dir}"      # the run dir: splits, baseline, candidates, rollouts, events
P="{project}"      # the project: capevolve.yaml, adapters/, {cap_path}
S="{skills}"       # the skills dir (CAPEVOLVE_SKILLS_DIR is already set to it)
A="$S/algorithms/agent-optimize/scripts"
PY="{interpreter}"      # the ONLY interpreter that can import this benchmark's adapter deps
mkdir -p "$R/work"
```

Paths are absolute; use them as given rather than relative paths, because your working
directory is not necessarily either of theirs.

`$PY` is already first on your `PATH`, so plain `python` resolves to it and SKILL.md's commands
work as written. Use `"$PY"` explicitly anywhere you build a command yourself. Do **not**
substitute another interpreter, `uv run`, or a fresh venv: the adapter's packages are
installed into this one only, and an eval run under any other dies with `ModuleNotFoundError`
on the adapter's imports — which scores the candidate `null`, not zero, and wastes the round.

## The spec values your gate needs

| key | value |
| --- | --- |
| `num_trials` | {n_trials} |
| `gate_k_se` | {k_se} |
| `gate_mode` | {gate_mode} |
| `capabilities` (which capability rules validate your edits) | {caps} |
| `capability_path` | {cap_path} |
| `--concurrency` for every gate | {gate_conc} |

Pass these explicitly — `--n-trials {n_trials}` on every evaluate, `--k-se {k_se}` on every
gate — rather than relying on a default that may not match this spec.

**The concurrency is a measurement parameter, not a speed dial.** Measured on this benchmark,
byte-identical code at identical seeds moves ~0.03 at concurrency 8 and ~0.08 above 25 — so a
gate run hot cannot resolve the effect you are looking for, and `round.py` now refuses a value
that coarse rather than warning about it. Buy wall clock with fewer candidates per round, never
with concurrency.

{surface}
{guidance}
{arm_block}

## Default to 3+ candidates per round

**Default to proposing 3 sibling candidates per round via `round.py`'s parallel mode** —
address different failure clusters in parallel, not one at a time — unless `spend.py
--n-siblings N` says your remaining budget can't afford it. A round's fixed overhead
(baseline + null-control replicates) is paid regardless of how many candidates it gates, so
one candidate per round wastes most of it on a single shot at the gate.

## The primitives every round must go through

SKILL.md says why; this is the checklist, because nobody is watching and a round that
skipped one leaves artifacts that cannot be audited afterwards:

| helper | per round | what it is for |
| --- | --- | --- |
| `$A/spend.py` | before | affordability + your stop condition as checkable predicates |
| `$A/gate_check.py` | after the full-val eval | the paired significance gate — the accept decision |
| `$A/commit.py` | always, whatever the outcome | books the decision: snapshot, best_id, iteration, event |
| `$A/measure.py` | once, at the end | seals test exactly once and prints the honest table |

`commit.py` is the one most easily skipped on a reject, and skipping it is what makes a run
report zero iterations having done real work. `screen.py` and `round.py` are optional
accelerators; the four above are not.

`--decision` has THREE values, and the third is not a formality. `accept` = new champion.
`reject` = the edit was judged and refuted. `inconclusive` = the measurement could not resolve it
— which is exactly what `round.py` reports as `verdict: inconclusive` (`verdict_stable: false`,
the verdict flipping depending on which byte-identical control replicate was the reference). Book
that as `inconclusive`, not as a reject:

- a reject increments the STALL counter, and stall is the signal that means *the optimizer has run
  out of ideas* — the one thing an ambiguous measurement is no evidence of. Two ambiguous rounds
  booked as rejects can end your run early for a reason that never happened.
- a reject files the edit in `rejected.jsonl`, which later rounds read as *this was tried and it
  did not work*. An edit nothing could judge has not been tried in that sense; filing it there
  teaches you to avoid your own untested idea.
- `inconclusive` still charges the iteration (the budget really was spent) and still snapshots the
  candidate, so nothing is hidden. To resolve it, re-measure under a **fresh tag** — re-running the
  same tag REPLACES its rollouts rather than adding to them. The control side needs no care: a
  re-gate of the same iteration measures its own `ctl_null_i<N>a<k>` replicates and pools the
  earlier attempt's, so `null_delta_between_control_replicates` covers every replicate the round
  has paid for and the earlier attempt's table stays on disk beside the new one.

`--reject-basis gate` asserts the gate ran AND rejected; `commit.py` refuses it when the gate
accepted or returned inconclusive, because that field is the run's record of what the evidence was.

## Your stop condition

{stop}

`spend.py` parses that text into checkable predicates; run it before each round and act on
its single `recommendation` (`stop` | `narrow_scope` | `continue`), as SKILL.md describes.

## Files in your working directory that belong to the OTHER loop

Your always-on instructions mention `LEDGER.md`, `RUNMAP.md` and `prior_iterations/`. Those are
built by the *deterministic* loop, which calls one optimizer per iteration; you are driving the
whole search yourself, so they will not exist here and their absence is not a problem — do not
go looking for them or try to recreate them.

`JOURNAL.md` is different, and it has TWO halves — one of them is yours to write.

- The FRAMEWORK half: `commit.py` stamps an objective `RESULT` line under each entry (outcome,
  Δ, and the exact task ids that round broke and fixed). You get that for free.
- YOUR half, the handover: **before each `commit.py`, append your entry for the round to
  `<your working dir>/JOURNAL.md`** — the same `--from-dir` you are about to commit — as a
  block starting `## Iteration <candidate id> — <one-line headline>`, covering: the changes you
  made (file + cluster each targets), the effect you expected and why it was safe, which prior
  RESULT lines you built on, hypotheses a prior RESULT has already REFUTED (never re-test one),
  and your focus next round. Read the accumulated `$R/JOURNAL.md` before writing, so you build
  on every prior round rather than the last one.

Skipping your half is silent and cheap in the moment and expensive by round 3: the run-level
journal records "(no handover written by the optimizer)", and your later rounds can then see
WHICH tasks each edit broke but not WHAT WAS TRIED — so refuted ideas get re-tested with the
budget that should have gone to new ones. Measured: three-round runs where every entry read that
way. `commit.py` returns `handover_recorded` and warns when it books an empty one; if you see
that warning, write the entry before the next round rather than at the end of the run.

## Unattended — this is the one real difference from an interactive run

**Nobody is available to answer a question. Do not ask any; do not wait for input.** Where
SKILL.md's Phase 0 says to ask the user about a blocking ambiguity (including
`constraints.ambiguous` from `spend.py`), instead: pick the most conservative reading, state
the assumption in one line in your final summary, and proceed. A round spent on a
conservative assumption is worth far more than a run that stalls waiting for a reply.

Three consequences worth being explicit about:

1. **Never leave the run unsealed.** Finish with `measure.py` (which seals test exactly
   once) and the report phase, as SKILL.md's "Stop & seal" section shows. A run with no
   finalize has no result. If you are running out of budget, stop optimizing and seal —
   sealing what you have beats one more candidate.
2. **A null result is a valid outcome, honestly reported.** If nothing beat the baseline
   through the gate, say so and seal anyway. Do not lower the gate, gate on a screen
   subset, or present a screen `promote` as an accept to manufacture a gain.
3. **Drive the loop from the foreground, and never end a turn with work outstanding.**
   There is no conversation to come back to. When you end a turn with no tool call pending,
   this process exits and everything it started is orphaned — so anything that would report
   back *later* never reports at all: a job left running in the background, a watcher on a
   file, a completion notice, a wake-up you scheduled. There is nobody to wake.

   This is not a rule against doing several things at once. Fan out as widely as the work
   deserves — subagents, parallel diagnosers, a whole round's candidates evaluated
   concurrently (that is exactly what `round.py` is for). The one invariant is that **the
   turn that launched the work is still the turn that collects it**: stay blocked until the
   result is in your hands, read it, and act on it before that turn ends. Delegate the work,
   never the waiting.

   Waiting is safe: one Bash call may run for {hours} hours, a ceiling raised for precisely
   this reason, so a long eval does not need backgrounding to survive. If something really
   would outlast that, make it smaller — fewer trials, fewer candidates per round — rather
   than detaching it.

   Measured on run 32814848187: the driver backgrounded round 2's full-val gate and ended
   its turn to await a notification. The process exited; the gate finished 14 minutes later
   and wrote a real verdict that nobody was left to read. Two of three rounds went unspent,
   and the orphaned evals were still hitting the runner while the seal was being measured.

## When you are done

Finish your final message with the run's honest table: seed vs best on val, on train if it
adds information, and on the sealed test split — plus the accepted candidate id, the number
of rounds, and any assumption you had to make on your own.
"""


def _decided_candidates(run_dir: Path) -> set[str]:
    """Candidate tags that already carry an accept/reject decision in ``events.jsonl``.

    Same source and same event names ``commit.py`` writes and re-reads for its own
    double-booking guard — the audit log rather than in-process memory, because the driver
    that booked the decision is a different process that has already exited.
    """
    decided: set[str] = set()
    try:
        with (run_dir / "events.jsonl").open(encoding="utf-8") as f:
            for line in f:
                try:
                    ev = json.loads(line)
                except Exception:  # noqa: BLE001 — a torn line is not a decision
                    continue
                # ``inconclusive`` is a booking too. Leaving it out would report a round booked
                # with the honest decision as gated-but-never-booked, i.e. diagnose the run as
                # defective precisely for not misfiling an unresolvable verdict as a reject.
                if ev.get("kind") in ("accept", "reject", "inconclusive") and \
                        ev.get("candidate"):
                    decided.add(str(ev["candidate"]))
    except OSError:
        return decided
    return decided


def _unbooked_rounds(run_dir: Path) -> list[dict]:
    """Candidates a round GATED but nobody booked with ``commit.py``.

    ``spent.iterations`` counts ``commit.py`` calls, so a round whose full-val gate ran to a
    verdict and was then abandoned is indistinguishable from a round never attempted — the
    operator is left diffing candidate dirs by hand to find out which. Measured on run
    32814848187: ``r2_comm_search`` was gated to ``reject`` at val 0.44 against parent 0.58,
    the table was on disk, and the run reported 1 of 3 rounds with no hint the second existed.

    Recognised by SHAPE, not by filename: ``round.py`` prints its table to stdout and the
    driver chooses where to redirect it, so matching ``round*.log`` would only ever catch the
    one name that happened to be used. Any file under ``work/`` that parses as a round table
    counts.

    Deliberately reports rather than books. Which decision a verdict deserves is the driver's
    judgement — ``round.py``'s own docstring says so — and a host that booked accepts on its
    behalf would move ``best_id`` after ``measure.py`` had already sealed against the old one,
    turning a visible gap into a wrong headline number.
    """
    work = run_dir / "work"
    if not work.is_dir():
        return []
    decided = _decided_candidates(run_dir)
    seen: set[str] = set()
    found: list[dict] = []
    for log in sorted(work.iterdir()):
        if not log.is_file() or log.suffix not in (".log", ".json", ".txt"):
            continue
        try:
            payload = json.loads(log.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — not a round table; nothing to say about it
            continue
        if not isinstance(payload, dict) or not isinstance(payload.get("candidates"), list):
            continue
        for cand in payload["candidates"]:
            if not isinstance(cand, dict):
                continue
            tag = str(cand.get("tag") or "")
            # A row with no verdict never reached a decision anyone could have skipped
            # (a crashed eval, or a table written before the gate ran).
            if not tag or tag in decided or tag in seen or not cand.get("verdict"):
                continue
            seen.add(tag)
            found.append({"candidate": tag, "verdict": cand.get("verdict"),
                          "reward": cand.get("reward"),
                          "parent": (payload.get("parent") or {}).get("tag"),
                          "log": log.name})
    return found


def _seal(run_dir: Path, project: Path, spec: dict, *, timeout: float | None) -> dict:
    """Ensure the run has a sealed test number. Idempotent.

    Returns ``{"sealed": bool, "seal": "agent"|"host"|"failed", ...}``. ``agent`` means
    final.json was already there when the host looked — the normal, desired outcome.
    """
    final = run_dir / "final.json"
    if final.exists():
        return {"sealed": True, "seal": "agent"}

    n_trials = int(spec.get("num_trials", 1) or 1)
    cmd = [sys.executable, str(HERE / "measure.py"), "--run-dir", str(run_dir),
           "--project", str(project), "--n-trials", str(n_trials), "--train", "auto"]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                       env=_child_env())
    if final.exists():
        return {"sealed": True, "seal": "host", "measure_rc": p.returncode}
    return {"sealed": False, "seal": "failed", "measure_rc": p.returncode,
            "measure_error": (p.stderr or p.stdout)[-1200:]}


def _stage_context(*, run_dir: Path, project: Path, workdir: Path, spec: dict,
                   agent: str) -> tuple:
    """Stage the SAME optimizer read-context every deterministic algorithm receives.

    ``harness.OptimizerContext`` exists so "an algorithm cannot silently run on a thinner
    prompt than its siblings": it places the declared capability skills as
    ``./guidance/<cap>/`` *and* where the agent natively discovers skills, plus the diagnose
    method, any ``capability_sources``, and the agent's own features reference.

    Agent mode never called it. ``test_optimizer_context_parity.py`` names that gap in its own
    docstring — this algorithm "declares none of the context flags and drives its own loop", so
    it "can still run blind while this file stays green". It did: measured across two runs, 4
    of 4 candidates edited only the prompt file, because the agent had guidance for prose and
    none at all for the tool code sitting beside it. Naming the files in the briefing did not
    move it, since the file list was never the missing piece.

    Reported rather than swallowed: a run that silently skipped staging is indistinguishable
    from one that staged fine, and simply optimizes less surface.
    """
    caps = tuple(c for c in (spec.get("capabilities") or []) if c)
    from cap_evolve import harness

    # from_spec, not the field-by-field constructor: it also resolves the target profile, so
    # reader_brief() is populated exactly the way the deterministic path's from_args does it.
    ctx = harness.OptimizerContext.from_spec(spec, project_dir=project, optimizer_name=agent)
    try:
        from cap_evolve import RunDir
        from cap_evolve.check import load_adapter

        rd = RunDir.open(run_dir)
        adapter = load_adapter(project)
        # split="val" + the current best's tag: the parent step the agent builds on, which is
        # the same choice the deterministic loop makes.
        ctx.inject(adapter, rd, workdir, split="val", tag=rd.best_id or "seed")

        # Seed the run's continuous JOURNAL.md into the CURRENT BEST candidate's snapshot
        # (baseline's "seed" at round 1) so the agent's first `cp -r "$R/candidates/$BEST"
        # "$R/work/$TAG"` (SKILL.md step 2) carries a marker-terminated JOURNAL.md forward.
        # Without this, agent-optimize's continuous session never gets the per-iteration
        # workdir seed the deterministic loops get from `_augment_instructions`, so
        # JOURNAL.md never exists and every round's handover reads as empty — confirmed live.
        # `commit.py` re-seeds the same way (onto whichever candidate becomes $BEST) after
        # every round, so round 2+ inherits a clean append target automatically. Own
        # try/except: a journal-seed failure must not mark the whole context (guidance,
        # trajectories) unstaged — it is a nicety on top of staging, not staging itself.
        try:
            harness._seed_journal(rd.candidate_dir(rd.best_id or "seed"), rd)
        except Exception as exc:  # noqa: BLE001
            rd.log_event("optimizer_context_warning", what="JOURNAL.md", error=str(exc)[:300])

        guidance = (sorted(g.name for g in (workdir / "guidance").iterdir())
                    if (workdir / "guidance").is_dir() else [])
        # A DECLARED capability that got no guidance dir. `harness._stage_context` skips a
        # capability with no matching skill package (`if not src.is_dir(): continue`) and still
        # reports staged, so "some capabilities missing" was indistinguishable from "everything
        # staged" — while the all-missing case has always been loud. Silently optimizing a
        # surface with no guidance is the exact defect this host was fixed for; leaving half of
        # it quiet just moves the blind spot. The staged list was already reported; what was
        # missing is the comparison against what the spec asked for.
        staged = {"staged": True, "capabilities": list(caps), "guidance": guidance,
                  "guidance_missing": [c for c in caps if c not in guidance]}
        try:
            rd.log_event("host_context", capabilities=list(caps), agent=agent, staged=True)
        except Exception:  # noqa: BLE001 — the event is a nicety, the staging is the point
            pass
        return ctx, staged
    except Exception as exc:  # noqa: BLE001
        return ctx, {"staged": False, "capabilities": list(caps),
                     "error": f"{type(exc).__name__}: {exc}"[:400]}


def optimizer_spend_to_book(metered: dict, before: dict, now: dict) -> dict:
    """The share of THIS agent process's metered spend that is not already in the run's state.

    The host meters the whole agent process; the agent books its own proposal cost per round
    through ``commit.py --optimizer-usd/--optimizer-tokens/--optimizer-seconds``, which the skill
    asks it to do. Those are the SAME money — a round's proposal happens inside this process — so
    booking the metered total on top of them reports up to twice the optimizer spend actually
    used, and a run's `max_usd`/cost-based stop condition then fires against a number no one
    spent. Book the residual instead.

    ``before``/``now`` bracket THIS invocation: a ``--resume`` run carries an earlier host's
    optimizer spend in the same counter, and that is not this agent's attribution to net out.
    Each role is netted independently, and never below zero — an agent that over-attributes
    (guessing its own cost high) must not subtract from another role or from the run total.
    """
    out = {}
    for key in ("usd", "tokens", "seconds"):
        booked_by_agent = max(0, (now.get(key) or 0) - (before.get(key) or 0))
        out[key] = max(0, (metered.get(key) or 0) - booked_by_agent)
    return {"usd": float(out["usd"]), "tokens": int(out["tokens"]),
            "seconds": float(out["seconds"])}


def _child_env() -> dict:
    env = dict(os.environ)
    env.setdefault("CAPEVOLVE_SKILLS_DIR", str(SKILLS))
    return env


def _agent_env(model: str | None) -> dict:
    """The environment the hosted agent runs in — reported so a test can assert it."""
    env = {
        "CAPEVOLVE_SKILLS_DIR": str(SKILLS),
        # Both, because the effective ceiling is max(default, max): raising only one leaves
        # the other as the real limit.
        "BASH_DEFAULT_TIMEOUT_MS": str(BASH_TIMEOUT_MS),
        "BASH_MAX_TIMEOUT_MS": str(BASH_TIMEOUT_MS),
        # THE interpreter, first. An arm's adapter deps are installed into exactly one venv, and
        # `cap-evolve run` uses it — which is why on run 32861747778 the baseline scored 0.44
        # while every candidate eval died `ModuleNotFoundError` on the adapter's own imports:
        # CI's PATH never contains that venv's bin, and SKILL.md tells the agent to run
        # `python "$A/round.py"`. Bare `python` could therefore never resolve to the one that
        # works, and the run before it had survived on luck.
        #
        # Fixed here rather than by rewriting SKILL.md's commands: the interpreter that launched
        # this host IS the correct one (run_suite.sh invokes `"$PY" host.py`), so putting its bin
        # dir first makes every existing `python ...` line correct by construction. Prose the
        # agent must remember is the form that already failed.
        "PATH": os.pathsep.join([str(Path(sys.executable).parent),
                                 os.environ.get("PATH", "")]).rstrip(os.pathsep),
    }
    if model:
        env["CAPEVOLVE_OPTIMIZER_MODEL"] = model
    return env


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="host.py",
        description="Drive the agent-optimize loop headlessly against a baselined run dir.")
    p.add_argument("--run-dir", required=True, help="run dir from the agent-mode handoff")
    p.add_argument("--project", required=True, help="project dir (capevolve.yaml, adapters/)")
    p.add_argument("--spec", default=None,
                   help="spec file; defaults to <project>/capevolve.yaml")
    p.add_argument("--agent", default="claude-code",
                   help="host agent: a row in optimizers/registry.yaml (default claude-code)")
    p.add_argument("--model", default=None, help="model for the host agent")
    p.add_argument("--budget", type=int, default=None,
                   help="whole-loop turn cap, mapped to the CLI's own budget flag")
    p.add_argument("--usd-budget", type=float, default=None,
                   help="whole-loop $ cap, mapped to the CLI's native flag where it has one")
    p.add_argument("--timeout", type=float, default=None,
                   help="wall-clock seconds for the hosted agent (default: none)")
    p.add_argument("--prompt-only", action="store_true",
                   help="render the briefing and exit without invoking the agent")
    p.add_argument("--seal-only", action="store_true",
                   help="skip the agent; only ensure the run has a sealed test number")
    p.add_argument("--run-optimizer", default=None,
                   help="path to the run-optimizer script (test seam; defaults to the "
                        "sibling optimizers/run-optimizer)")
    args = p.parse_args(argv)

    run_dir = Path(args.run_dir).resolve()
    project = Path(args.project).resolve()
    if not run_dir.is_dir():
        print(json.dumps({"error": f"run dir not found: {run_dir}",
                          "fix": "pass the run_dir from the agent-mode handoff printed by "
                                 "`cap-evolve run`"}, indent=2))
        return 2
    if not project.is_dir():
        print(json.dumps({"error": f"project dir not found: {project}"}, indent=2))
        return 2

    spec = _spec(project, Path(args.spec).resolve() if args.spec else None)
    rounds = int(spec.get("max_iterations", 0) or 0) or 10

    if args.seal_only:
        out = _seal(run_dir, project, spec, timeout=args.timeout)
        # This is the rescue path an operator reaches for on a run that died mid-loop, so it
        # is the path most likely to be sitting on an abandoned round. Reporting it only on
        # the full host path would hide it from exactly the reader who came looking.
        out["unbooked_rounds"] = _unbooked_rounds(run_dir)
        print(json.dumps({"run_dir": str(run_dir), "seal_only": True, **out}, indent=2))
        return 0 if out["sealed"] else 1

    # Refuse an unknown host agent BEFORE anything is spent. The registry is where a host
    # agent is actually added, so name it in the fix.
    known = _known_agents()
    if known and args.agent not in known:
        print(json.dumps({
            "error": f"unknown host agent: {args.agent!r}",
            "known": known,
            "fix": f"pass --agent with one of the rows in {REGISTRY}, or add a row there "
                   "(one row per shell-invokable agent CLI — no new code needed)",
        }, indent=2))
        return 2

    # The agent needs write access to BOTH the run dir and the project; their common parent
    # is the natural workdir, and it is where the staged guidance + native skills land.
    workdir = _common_parent(run_dir, project)
    ctx, context = _stage_context(run_dir=run_dir, project=project, workdir=workdir,
                                  spec=spec, agent=args.agent)

    prompt_dir = run_dir / "host"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = prompt_dir / "driver_prompt.md"
    # ONE resolution rule, shared with cli.py's deterministic path (specfile). Two copies of
    # it is how #252 happened: a relative key resolved against different cwds, and a miss
    # silently downgraded the optimizer to the generic template.
    from cap_evolve.specfile import resolve_instructions_file

    arm_p, arm_exists, arm_warning = resolve_instructions_file(spec, project)
    arm_path = str(arm_p) if arm_exists else ""
    arm_text = ""
    if arm_exists:
        try:
            # Rendered through the shared renderer, not stripped by hand: the arm's template
            # arrives with its blocks filled from the same functions the deterministic path
            # uses, instead of as literal {{SLOT}} braces.
            arm_text = ctx.render_template(arm_p.read_text(encoding="utf-8"),
                                           parent_dir=run_dir / "candidates" / "seed")
        except OSError as exc:
            arm_warning = f"could not read {arm_p}: {exc}"
    briefing = _briefing(run_dir=run_dir, project=project, spec=spec, skills=SKILLS,
                         rounds=rounds, workdir=workdir, context=context, arm=arm_text,
                         ctx=ctx)
    prompt_path.write_text(briefing, encoding="utf-8")
    # Also as <workdir>/INSTRUCTIONS.md. Staging writes an always-on CLAUDE.md pointer whose
    # first instruction is "read ./INSTRUCTIONS.md FIRST" — written for the deterministic
    # per-iteration optimizer, which has one. Agent mode passes its briefing as the prompt, so
    # without this the agent's always-on context opens by pointing at a file that is not there.
    # Same bytes, so the two can never disagree; the run-dir copy stays the audit record.
    if context.get("staged"):
        try:
            (workdir / "INSTRUCTIONS.md").write_text(briefing, encoding="utf-8")
        except OSError as exc:
            context.setdefault("warnings", []).append(f"INSTRUCTIONS.md: {exc}")

    agent_env = _agent_env(args.model)
    if args.prompt_only:
        print(json.dumps({"run_dir": str(run_dir), "agent": args.agent,
                          "model": args.model, "prompt_only": True,
                          "prompt_path": str(prompt_path), "returncode": None,
                          "agent_env": agent_env, "budget": args.budget,
                          "usd_budget": args.usd_budget,
                          "workdir": str(workdir), "context": context,
                          "instructions_file": arm_path,
                          "instructions_warning": arm_warning}, indent=2))
        return 0
    if not context["staged"]:
        print(f"::warning::optimizer context not staged for the hosted agent "
              f"({context.get('error')}) — it will optimize with no capability guidance",
              file=sys.stderr)
    elif context.get("guidance_missing"):
        # Warned, not merely recorded: a field nobody greps is not a report, and this is the
        # partial case of the failure the branch above already shouts about.
        missing = ", ".join(context["guidance_missing"])
        print(f"::warning::agent-optimize: no guidance staged for declared capability/ies "
              f"[{missing}] — no skill package of that name exists under the capabilities "
              f"root, so the agent will edit that surface with no allowed-edit-space brief. "
              f"Check the spelling in capevolve.yaml `capabilities`, or add the skill.",
              file=sys.stderr)

    # Delegate the invocation. --json switches on run-optimizer's cost capture, which is how
    # the host's own spend reaches the run dir at all: the evaluate phase records the
    # runner's cost, and nothing records the proposer's.
    runner = Path(args.run_optimizer).resolve() if args.run_optimizer else RUN_OPTIMIZER
    cmd = [sys.executable, str(runner), "--name", args.agent, "--json",
           # Same workdir the guidance was staged into, so the agent's cwd is where its
           # native skills dir and ./guidance/ live.
           "--workdir", str(workdir),
           "--prompt", str(prompt_path),
           # The loop's own record. Four hours of run 32814848187 were unaccounted for and
           # unaccountable: the only trace kept was an 800-char stdout tail, so what the agent
           # was blocked on could be narrowed to "something that hit the Bash ceiling" and no
           # further. This lands beside driver_prompt.md, so the run dir holds both what the
           # host asked for and what the agent actually did.
           "--transcript", str(prompt_path.parent / "transcript.jsonl")]
    if args.model:
        cmd += ["--model", args.model]
    if args.budget:
        cmd += ["--budget", str(int(args.budget))]
    if args.usd_budget:
        cmd += ["--usd-budget", str(float(args.usd_budget))]

    # What the run had already booked as optimizer spend BEFORE this agent started. The agent
    # books its own proposal cost per round through commit.py --optimizer-usd (the skill asks it
    # to), and that is the SAME money this subprocess meters — so the host must book the
    # RESIDUAL, not the total, or a compliant agent makes the run report roughly twice the
    # optimizer spend it actually used. Snapshotted rather than read at the end because a
    # `--resume` run carries a PREVIOUS host invocation's spend in the same counter, and that is
    # not this agent's attribution to net out.
    booked_before = {"usd": 0.0, "tokens": 0, "seconds": 0.0}
    try:
        from cap_evolve import RunDir as _RunDir

        _sp = _RunDir.open(run_dir).spent
        booked_before = {"usd": float(_sp.optimizer_usd or 0.0),
                         "tokens": int(_sp.optimizer_tokens or 0),
                         "seconds": float(_sp.optimizer_seconds or 0.0)}
    except Exception:  # noqa: BLE001 — a missing snapshot must not stop the run
        pass

    started = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout,
                              env={**_child_env(), **agent_env})
        timed_out = False
    except subprocess.TimeoutExpired:
        proc = None
        timed_out = True
    seconds = time.time() - started

    payload: dict = {}
    if proc is not None:
        try:
            payload = json.loads(proc.stdout)
        except Exception:  # noqa: BLE001 — a non-JSON tail is reported, not fatal
            payload = {"stdout_tail": (proc.stdout or "")[-1200:]}

    # run-optimizer nests the figure under `cost.total_cost_usd` (see its `result["cost"]`).
    # Reading a flat `cost_usd`/`usd` booked 0.0 for every run: on run 32733635494 the payload
    # carried 8.370 USD / 68,432 tokens and the run recorded $0.00, which is indistinguishable
    # from the genuinely-unmetered case the skill warns about — so the wrong conclusion was
    # drawn twice. The flat keys stay as fallbacks for any optimizer row that reports that way.
    cost = payload.get("cost") or {}
    usd = float(cost.get("total_cost_usd") or payload.get("cost_usd")
                or payload.get("usd") or 0.0)
    tokens = int(cost.get("tokens") or payload.get("tokens") or 0)
    # Why the agent stopped. Reconstructing this from a truncated stdout tail is what the
    # previous version forced, and the answer (turns exhausted mid-round, with a better
    # candidate evaluated but never committed) mattered more than anything else in the payload.
    stop = payload.get("stop") or {}
    stop_reason = str(stop.get("subtype") or "") or None
    # Two different fields, and the discriminator is the SECOND one. Claude Code reports the
    # harness-level outcome in `subtype` and the model's own reason in `stop_reason`; on run
    # 32814848187 those were "success" and "end_turn". Reading only `subtype` sees a clean
    # finish and cannot tell a voluntary stop from a completed run.
    agent_stop = str(stop.get("stop_reason") or "") or None
    num_turns = stop.get("num_turns")

    # Book the host's own spend. The agent books per-round costs it knows about through
    # commit.py --optimizer-usd; it cannot know its own process cost, and the host can.
    try:
        from cap_evolve import RunDir

        rd = RunDir.open(run_dir)
        rd.log_event("host", agent=args.agent, model=args.model or "",
                     usd=usd, tokens=tokens, seconds=round(seconds, 3),
                     returncode=(None if proc is None else proc.returncode),
                     timed_out=timed_out, stop_reason=stop_reason, num_turns=num_turns)
        # Book only what the agent did not already attribute to a round during THIS invocation.
        # `seconds` is booked too: without it the run recorded `optimizer_seconds: 0.0` for a
        # loop that ran for hours, so metrics.py's whole-loop total rendered a dash and every
        # per-hour cost figure was undefined.
        now = rd.spent
        book = optimizer_spend_to_book(
            {"usd": usd, "tokens": tokens, "seconds": seconds},
            booked_before,
            {"usd": float(now.optimizer_usd or 0.0), "tokens": int(now.optimizer_tokens or 0),
             "seconds": float(now.optimizer_seconds or 0.0)})
        if book["usd"] or book["tokens"] or book["seconds"]:
            rd.update_spent(optimizer_usd=book["usd"], optimizer_tokens=book["tokens"],
                            optimizer_seconds=book["seconds"])
        # The run dir's budget, not the spec's: baseline freezes it there, `--resume` can
        # extend it, and it is what `budget_exhausted()` actually judges against.
        rounds_done = int(rd.spent.iterations or 0)
        rounds_budget = int(rd.budget.max_iterations or 0)
    except Exception as exc:  # noqa: BLE001 — spend accounting must not lose the run
        payload.setdefault("warnings", []).append(f"could not book host spend: {exc}")
        rounds_done, rounds_budget = -1, 0

    seal = _seal(run_dir, project, spec, timeout=args.timeout)

    # AFTER the seal on purpose. The abandoned round's evals were still running when the agent
    # exited — on run 32814848187 its table landed 14 minutes later, during measure.py — so a
    # check made before sealing would have found an empty work/ and reported nothing.
    unbooked = _unbooked_rounds(run_dir)

    # An agent that stopped with rounds left is a DEFECT, not a finished run — and it must not
    # read as completion. Measured: one run booked 1 of 3 rounds with a higher-scoring
    # candidate already evaluated but never committed, and reported success. The host cannot
    # un-spend that, but it can refuse to let it look finished.
    #
    # The advice has to be per-cause. One message served both stop causes and fit only the
    # first: run 32733635494 died on error_max_turns, where "raise optimizer_max_turns" was
    # exactly right, and run 32814848187 stopped at 78 of 600 turns on end_turn, where the same
    # sentence pointed at a knob already 7x larger than what the agent used — and sent the next
    # operator to raise it again.
    incomplete = ""
    if 0 <= rounds_done < rounds_budget:
        reasons = f"{stop_reason or ''} {agent_stop or ''}"
        turn_limited = "max_turns" in reasons
        # Ran to a clean stop of its own accord, with rounds and turns still to spend.
        voluntary = not turn_limited and ("end_turn" in reasons or "success" in reasons)

        # An agent that SEALED THE RUN ITSELF did not lose its loop — it finished it early. Both
        # facts needed to tell the two apart are already here: `seal == "agent"` (run 32814848187,
        # which really did end its turn on a running gate, left the host to seal) and an empty
        # `unbooked_rounds`. Without this branch the diagnosis fired on run 32871360361 — 4 of 10
        # rounds, test sealed, report written, 121 of 1650 turns — and told the operator it had
        # abandoned a backgrounded job. Accusing a complete run of the defect this warning exists
        # for is how a warning stops being read.
        finished_itself = (seal.get("seal") == "agent" and not unbooked)

        if turn_limited:
            fix = ("raise the turn budget (optimizer_max_turns) or lower the round count")
        elif finished_itself:
            fix = ("it sealed the run itself and left nothing unbooked, so this is UNSPENT "
                   "BUDGET, not a loop that died: it stopped when it ran out of edits it "
                   "trusted, not when it ran out of rounds. Read its final message for the "
                   "reason — if the honest answer is 'no further lever found', the lever is the "
                   "stop condition or the briefing, not the host")
        elif voluntary:
            fix = ("it stopped of its own accord with rounds still to spend, which is what a "
                   "turn ending on outstanding work looks like from here: a backgrounded job, "
                   "a file watcher, or anything else that reports back later cannot resume a "
                   "non-interactive run, because ending a turn ends the process. The loop must "
                   "be driven from the foreground — see the briefing's Unattended section. "
                   "Delegation is fine; detaching the wait is not")
        else:
            fix = ("the agent did not finish and did not run out of turns — read agent_error "
                   "and the optimizer payload for what killed it")

        evidence = ""
        if unbooked:
            evidence = "; gated but never booked with commit.py: " + ", ".join(
                f"{u['candidate']} (verdict {u['verdict']}, val {u['reward']}, in "
                f"work/{u['log']})" for u in unbooked)
        elif finished_itself:
            # Both checks came back clean, so say so. Hedging here sent a reader hunting for a
            # candidate that provably does not exist.
            evidence = ("; every round it ran was booked and it sealed the run itself, so no "
                        "measured candidate was lost")
        else:
            evidence = ("; a candidate it evaluated may never have been committed")

        incomplete = (f"the agent booked {rounds_done} of {rounds_budget} rounds"
                      + (f" and stopped on {stop_reason}" if stop_reason else "")
                      + (f"/{agent_stop}" if agent_stop and agent_stop != stop_reason else "")
                      + (f" after {num_turns} turns" if num_turns else "")
                      + evidence + " — " + fix)

    out = {
        "run_dir": str(run_dir),
        "agent": args.agent,
        "model": args.model,
        "prompt_path": str(prompt_path),
        "returncode": None if proc is None else proc.returncode,
        "timed_out": timed_out,
        "stop_reason": stop_reason,
        "agent_stop_reason": agent_stop,
        "num_turns": num_turns,
        "rounds_booked": rounds_done,
        "rounds_budget": rounds_budget,
        "unbooked_rounds": unbooked,
        "incomplete": incomplete,
        "seconds": round(seconds, 3),
        "usd": usd,
        "tokens": tokens,
        "agent_env": agent_env,
        "transcript": (payload.get("transcript") or {}).get("path", ""),
        "instructions_file": arm_path,
        "instructions_warning": arm_warning,
        "context": context,
        "optimizer": payload,
        **seal,
    }
    if proc is not None and proc.returncode != 0:
        out["agent_error"] = (proc.stderr or "")[-1200:]
    print(json.dumps(out, indent=2))
    if incomplete:
        print(f"::warning::agent-optimize: {incomplete}", file=sys.stderr)
    # The run's worth is its sealed number, so that — not the agent's exit code — decides
    # ours. An agent that ran out of turns after three honest rounds produced a result; one
    # that exited 0 without sealing did not.
    return 0 if seal["sealed"] else 1


def _common_parent(a: Path, b: Path) -> Path:
    try:
        return Path(os.path.commonpath([str(a), str(b)]))
    except ValueError:
        return a.parent


if __name__ == "__main__":
    sys.exit(main())
