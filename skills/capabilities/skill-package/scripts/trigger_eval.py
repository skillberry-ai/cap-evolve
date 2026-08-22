"""Measure a candidate `description`'s trigger rate on a held-out split.

The `description` is the only text loaded before a skill fires, so triggering is
its own measurable objective. Doing this by hand costs a decision per query and
drifts run to run; this script makes it deterministic: it splits the eval set by
seed, asks a judge the same question N times per query (a trigger decision is
stochastic — one sample is noise), scores both halves, and prints JSON. Select
the description by the HELD-OUT score, never the train score.

Eval set (JSON list, the shape skill-creator uses):

    [{"query": "the user prompt", "should_trigger": true}, ...]

The judge is whatever the host has, so this stays model-agnostic: `--judge-cmd`
is shelled once per (query, trial) with the prompt on stdin and must print a
verdict containing `yes`/`trigger` or `no`. Example:

    python trigger_eval.py --eval-set eval.json --skill ../my-skill \
        --judge-cmd 'llm -m gpt-4o-mini' --trials 3

    {"train_score": 0.83, "heldout_score": 0.75, "per_query": [...]}

`--self-check` runs the whole pipeline against a built-in keyword judge (no
model, no network) and asserts the scoring is right, so the plumbing is verified
without spending anything.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PROMPT = """You decide whether one skill should be consulted for a user request.

Skill name: {name}
Skill description: {description}

User request: {query}

Answer with one word: YES if the skill should be consulted, NO if it should not."""


def _description(skill_dir: Path) -> tuple[str, str]:
    """(name, description) from a skill package's frontmatter."""
    text = (Path(skill_dir) / "SKILL.md").read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    fm = {}
    if m:
        key = None
        for line in m.group(1).splitlines():
            if ":" in line and not line[:1].isspace():
                key, _, v = line.partition(":")
                key = key.strip()
                fm[key] = v.strip().strip('"').strip("'")
            elif key and line.strip():
                fm[key] = (fm[key] + " " + line.strip()).strip()
    return fm.get("name", ""), fm.get("description", "")


def _keyword_judge(prompt: str) -> str:
    """Offline stand-in used by --self-check: does the request share the description's words?"""
    desc = re.search(r"Skill description: (.*)", prompt).group(1).lower()
    query = re.search(r"User request: (.*)", prompt, re.S).group(1).lower()
    words = {w for w in re.findall(r"[a-z]{4,}", desc)}
    hits = sum(1 for w in re.findall(r"[a-z]{4,}", query) if w in words)
    return "YES" if hits >= 2 else "NO"


def _ask(judge_cmd: str | None, prompt: str) -> bool:
    if judge_cmd is None:
        verdict = _keyword_judge(prompt)
    else:
        p = subprocess.run(judge_cmd, shell=True, input=prompt, text=True,
                           capture_output=True, timeout=120)
        verdict = (p.stdout or "").strip()
    low = verdict.lower()
    return ("yes" in low or "trigger" in low) and "no" != low[:2]


def evaluate(items: list[dict], name: str, description: str, *, trials: int = 3,
             judge_cmd: str | None = None) -> list[dict]:
    """Per-query trigger rate over `trials` samples, plus whether it matches expectation."""
    out = []
    for it in items:
        prompt = PROMPT.format(name=name, description=description, query=it["query"])
        fired = [_ask(judge_cmd, prompt) for _ in range(trials)]
        rate = sum(fired) / len(fired)
        want = bool(it["should_trigger"])
        out.append({"query": it["query"], "should_trigger": want,
                    "trigger_rate": rate,
                    "score": rate if want else 1.0 - rate})
        out[-1]["correct"] = out[-1]["score"] > 0.5
    return out


def _mean(rows: list[dict]) -> float:
    return round(sum(r["score"] for r in rows) / len(rows), 4) if rows else 0.0


def split(items: list[dict], *, seed: int = 0, train_frac: float = 0.6) -> tuple[list, list]:
    """Deterministic train/held-out split (skill-creator uses 60/40)."""
    idx = list(range(len(items)))
    random.Random(seed).shuffle(idx)
    cut = max(1, int(round(len(items) * train_frac)))
    return [items[i] for i in idx[:cut]], [items[i] for i in idx[cut:]]


def run(eval_set: list[dict], skill_dir: Path, *, trials: int = 3, seed: int = 0,
        train_frac: float = 0.6, judge_cmd: str | None = None,
        description: str | None = None) -> dict:
    name, current = _description(skill_dir)
    desc = description if description is not None else current
    train, heldout = split(eval_set, seed=seed, train_frac=train_frac)
    tr = evaluate(train, name, desc, trials=trials, judge_cmd=judge_cmd)
    ho = evaluate(heldout, name, desc, trials=trials, judge_cmd=judge_cmd)
    return {"skill": name, "trials": trials, "seed": seed,
            "n_train": len(tr), "n_heldout": len(ho),
            "train_score": _mean(tr), "heldout_score": _mean(ho),
            "per_query": tr + ho,
            "select_on": "heldout_score"}


def _self_check() -> int:
    """Prove the split + scoring + judge plumbing with no model and no network."""
    items = [{"query": f"please export the sales table to csv {i}", "should_trigger": True}
             for i in range(5)]
    items += [{"query": f"write a haiku about rain {i}", "should_trigger": False}
              for i in range(5)]
    with tempfile.TemporaryDirectory() as d:
        pkg = Path(d)
        (pkg / "SKILL.md").write_text(
            "---\nname: csv-export\ndescription: Exports records to csv table files. "
            "Use when the user asks to export or download a sales table.\n---\n# x\n",
            encoding="utf-8")
        out = run(items, pkg, trials=3, seed=0)
    a, b = split(items, seed=0), split(items, seed=0)
    assert [i["query"] for i in a[0]] == [i["query"] for i in b[0]], "split is not deterministic"
    assert out["n_train"] == 6 and out["n_heldout"] == 4, out
    assert out["heldout_score"] > 0.5, f"keyword judge should mostly agree: {out}"
    assert all(0.0 <= r["trigger_rate"] <= 1.0 for r in out["per_query"])
    print(json.dumps({"self_check": "ok", "train_score": out["train_score"],
                      "heldout_score": out["heldout_score"]}))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="trigger-eval")
    p.add_argument("--self-check", action="store_true", help="offline pipeline check")
    p.add_argument("--eval-set", help="JSON [{query, should_trigger}]")
    p.add_argument("--skill", help="skill package dir (contains SKILL.md)")
    p.add_argument("--description", default=None, help="candidate description to test "
                                                       "instead of the one in SKILL.md")
    p.add_argument("--judge-cmd", default=None, help="shell command; prompt on stdin, "
                                                     "YES/NO on stdout")
    p.add_argument("--trials", type=int, default=3)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--train-frac", type=float, default=0.6)
    args = p.parse_args(argv)
    if args.self_check:
        return _self_check()
    if not (args.eval_set and args.skill):
        p.error("--eval-set and --skill are required (or use --self-check)")
    items = json.loads(Path(args.eval_set).read_text(encoding="utf-8"))
    print(json.dumps(run(items, Path(args.skill), trials=args.trials, seed=args.seed,
                         train_frac=args.train_frac, judge_cmd=args.judge_cmd,
                         description=args.description), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
