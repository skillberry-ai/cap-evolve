#!/usr/bin/env python3
"""assert.py — deterministic pass/fail for a microcase, no LLM judge.

Reads reproduce.py's result JSON and case.yaml's `assert` spec (metric/op/value),
evaluates the comparison, and writes {status, metric, observed, expected} to --out.
Exit 0 = pass, 1 = fail, 2 = reproduce.py reported an environment error (not a fail).
"""
import argparse
import json
import operator
from pathlib import Path

OPS = {"==": operator.eq, "!=": operator.ne, "<": operator.lt,
       "<=": operator.le, ">": operator.gt, ">=": operator.ge}


def _read_case_yaml(text: str) -> dict:
    """Tiny reader for THIS script's own case.yaml shape (flat keys + one nested
    `assert:` block) — no PyYAML dependency needed for a file this script itself
    wrote via its rigid template.
    """
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text) or {}
    except Exception:
        pass
    out: dict = {}
    section = None
    for raw in text.splitlines():
        if not raw.strip():
            continue
        if not raw.startswith(" "):
            key, _, val = raw.partition(":")
            key, val = key.strip(), val.strip()
            if val == "":
                section = {}
                out[key] = section
            else:
                section = None
                out[key] = json.loads(val) if val[:1] in ('[', '{', '"') or val[:1].isdigit() or val in (
                    "true", "false") else val
        elif section is not None:
            key, _, val = raw.strip().partition(":")
            key, val = key.strip(), val.strip().strip('"')
            try:
                section[key] = json.loads(val)
            except json.JSONDecodeError:
                section[key] = val
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True, help="the case directory (holds case.yaml)")
    ap.add_argument("--result", required=True, help="reproduce.py's output JSON")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    case = _read_case_yaml(Path(args.case, "case.yaml").read_text())
    result = json.loads(Path(args.result).read_text())

    if result.get("status") == "error":
        out = {"status": "error", "reason": result.get("reason", "unknown")}
        Path(args.out).write_text(json.dumps(out, indent=2))
        print(json.dumps(out, indent=2))
        return 2

    spec = case["assert"]
    metric, op, expected = spec["metric"], spec["op"], spec["value"]
    if metric not in result:
        out = {"status": "error",
               "reason": f"reproduce.py's result has no {metric!r} field"}
        Path(args.out).write_text(json.dumps(out, indent=2))
        print(json.dumps(out, indent=2))
        return 2

    observed = result[metric]
    passed = OPS[op](observed, expected)
    out = {"status": "pass" if passed else "fail",
           "metric": metric, "op": op, "observed": observed, "expected": expected}
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
