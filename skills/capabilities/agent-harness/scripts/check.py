"""Smoke test: config / lesson / code edits, the policy, and the two honesty invariants."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

import abstract

LESSON = {"id": "verify-before-final", "when": "before the final answer on a write task",
          "do": "re-read the changed record and confirm each requested field",
          "evidence": "train: 4 traces ended after a write that set the wrong field",
          "source_split": "train"}
HOOK = ("def compact(messages, keep_last=5):\n"
        "    old, recent = messages[:-keep_last], messages[-keep_last:]\n"
        "    masked = [dict(m, content='[tool output omitted]') if m.get('role') == 'tool' else m\n"
        "              for m in old]\n"
        "    return masked + recent\n")


def main() -> int:
    report = {"skill": "agent-harness", "ok": False, "problems": [], "notes": []}
    bad = report["problems"].append

    with tempfile.TemporaryDirectory() as root:
        cap = Path(root) / "cand"
        base = Path(root) / "parent"
        cap.mkdir()
        base.mkdir()
        v = abstract.validate(cap)
        if not (v["ok"] and v.get("empty")):
            bad(f"empty dir should validate as an empty seed: {v}")
        (cap / "harness.json").write_text(json.dumps({"loop": {"max_steps": 30}}), encoding="utf-8")
        (base / "harness.json").write_text((cap / "harness.json").read_text(), encoding="utf-8")

        rep = abstract.apply(cap, [
            {"op": "set", "path": "context.compaction", "value": "observation_masking"},
            {"op": "set", "path": "sampling.n_candidates", "value": 3},
            {"op": "set", "path": "sampling.selector", "value": "verifier"},
            {"op": "add_lesson", "lesson": LESSON},
            {"op": "code", "file": "hooks/compact.py", "text": HOOK},
        ])
        if rep["refused"] or len(rep["changed"]) != 5:
            bad(f"default policy should apply all 5 edits: {rep}")
        cfg = abstract.load_config(cap)
        if abstract.get_path(cfg, "context.compaction") != "observation_masking" \
                or abstract.get_path(cfg, "loop.max_steps") != 30:
            bad(f"set did not merge into harness.json: {cfg}")
        if [x["id"] for x in abstract.load_lessons(cap)] != ["verify-before-final"]:
            bad("add_lesson did not persist to memory/lessons.jsonl")
        v = abstract.validate(cap, baseline=base)
        if not v["ok"]:
            bad(f"valid artifact failed validate: {v['problems']}")
        if not any("cost_factor grew" in w for w in v["warnings"]):
            bad("best-of-3 + verifier did not raise a cost warning against the baseline")
        if set(abstract.materialize(cap)) != {"harness.json", "memory/lessons.jsonl",
                                              "hooks/compact.py"}:
            bad(f"materialize parts wrong: {sorted(abstract.materialize(cap))}")
        report["notes"].append("config/lesson/code edits round-trip; cost growth is flagged")

        # Refusals: out-of-range value, lesson from test, stub hook, path escape.
        rep = abstract.apply(cap, [
            {"op": "set", "path": "sampling.temperature", "value": 5},
            {"op": "add_lesson", "lesson": {**LESSON, "id": "leak", "source_split": "test"}},
            {"op": "code", "file": "hooks/verify.py", "text": "def verify(x):\n    ...\n"},
            {"op": "code", "file": "../evil.py", "text": "x = 1\n"},
            {"op": "add_lesson", "lesson": LESSON},  # duplicate id
        ])
        if len(rep["refused"]) != 5 or rep["changed"]:
            bad(f"expected 5 refusals and no change: {rep}")
        if (cap / "hooks" / "verify.py").exists() or (cap.parent / "evil.py").exists():
            bad("a refused code edit was written to disk")
        report["notes"].append("out-of-range, test-split lesson, stub hook, path escape refused")

        # Invariant: memory written during a scored rollout is a problem, not a warning.
        abstract.apply(cap, [{"op": "set", "path": "memory.write_during_eval", "value": True}])
        if abstract.validate(cap)["ok"]:
            bad("memory.write_during_eval=true passed validate")
        abstract.apply(cap, [{"op": "set", "path": "memory.write_during_eval", "value": False}])
        # A lesson file edited by hand to cite test must fail too.
        with (cap / "memory" / "lessons.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({**LESSON, "id": "hand", "source_split": "test"}) + "\n")
        if abstract.validate(cap)["ok"]:
            bad("a hand-written test-split lesson passed validate")
        abstract.apply(cap, [{"op": "remove_lesson", "id": "hand"}])
        if not abstract.validate(cap)["ok"]:
            bad("removing the leaked lesson did not restore a valid artifact")
        report["notes"].append("write_during_eval and test-split lessons fail validate")

        # Tightened policy: only lessons, and only wired settings.
        (cap / "harness_policy.json").write_text(json.dumps(
            {"allow": ["config", "lesson"], "wired": ["memory.*"]}), encoding="utf-8")
        rep = abstract.apply(cap, [
            {"op": "set", "path": "loop.max_steps", "value": 50},
            {"op": "set", "path": "memory.top_k", "value": 5},
            {"op": "code", "file": "hooks/compact.py", "text": HOOK},
        ])
        if rep["changed"] != ["set:memory.top_k"] or len(rep["refused"]) != 2:
            bad(f"tight policy should allow only memory.top_k: {rep}")
        report["notes"].append("harness_policy.json refuses unwired settings and disallowed kinds")

        try:
            abstract.apply(cap, [{"op": "nope"}])
        except ValueError:
            pass
        else:
            bad("apply accepted an unknown op")

    report["ok"] = not report["problems"]
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
