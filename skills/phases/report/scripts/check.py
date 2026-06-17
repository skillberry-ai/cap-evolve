"""Contract: report summarizes baseline → best val → sealed test and writes
report.md; and the Wave-4 dashboard builder reduces a synthetic event log into a
well-formed candidate graph + a self-contained, parseable dashboard.html with no
leaked secrets.
"""

from __future__ import annotations

import html.parser
import json
import sys
import tempfile
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve.skillcheck import Checker, import_run, quiet, temp_run_dir


def _synthetic_events():
    """A minimal but realistic event log: splits, baseline, an accept, a gate
    warning, a reject — plus an optimizer_error echoing a secret to prove redaction."""
    return [
        {"kind": "splits", "train": 4, "val": 2, "test": 2, "seed": 0},
        {"kind": "evaluate", "split": "val", "tag": "seed", "reward": 0.25,
         "stderr": 0.0, "cost_usd": 0.0, "tokens": 0, "seconds": 0.0},
        {"kind": "baseline", "val": 0.25, "stderr": 0.0},
        {"kind": "step", "candidate": "cand_0001", "accept": True, "reason": "Δ up",
         "val": 0.75, "parent": "seed", "parent_val": 0.25,
         "optimizer_seconds": 1.0, "runner_seconds": 0.5, "cost_usd": 0.01, "tokens": 500},
        {"kind": "gate_warning", "mode": "paired", "reason": "SE collapsed to 0", "context": "se=0"},
        {"kind": "step", "candidate": "cand_0002", "accept": False, "reason": "Δ<=0",
         "val": 0.6, "parent": "cand_0001", "parent_val": 0.75,
         "optimizer_seconds": 0.9, "runner_seconds": 0.4, "cost_usd": 0.008, "tokens": 400},
        {"kind": "optimizer_error", "candidate": "cand_0002",
         "error": "auth failed RITS_API_KEY=rits-supersecret0123456789 retry"},
    ]


def main() -> int:
    c = Checker("report")
    run = import_run()
    c.require_main(run)

    # --- 1. report.md: baseline → sealed test ----------------------------
    with tempfile.TemporaryDirectory() as d:
        rd, _ = temp_run_dir(Path(d))
        (rd.root / "baseline.json").write_text(
            json.dumps({"val": {"reward": 0.4}, "best_id": "seed"}), encoding="utf-8")
        (rd.root / "final.json").write_text(
            json.dumps({"test": {"reward": 0.8, "pass_k": 0.7}, "best_id": "cand_0001"}),
            encoding="utf-8")

        with quiet():
            rc = run.main(["--run-dir", str(rd.root), "--no-dashboard"])
        c.check(rc == 0, "report returned nonzero")

        md_path = rd.root / "report.md"
        c.check(md_path.exists(), "report.md was not written", note="writes report.md")
        md = md_path.read_text()
        c.check("0.4" in md and "0.8" in md,
                f"report.md missing baseline/test numbers:\n{md}",
                note="report carries baseline → sealed test")
        c.check("sealed" in md.lower(),
                "report does not state the test was scored once on the sealed split")

    # --- 2. reducer → well-formed graph from a synthetic event log -------
    from cap_evolve import dashboard
    with tempfile.TemporaryDirectory() as d:
        rd, _ = temp_run_dir(Path(d))
        rd.events_path.write_text(
            "\n".join(json.dumps(e) for e in _synthetic_events()) + "\n", encoding="utf-8")
        (rd.root / "baseline.json").write_text(json.dumps({
            "val": {"reward": 0.25, "per_task": [
                {"task_id": "t1", "reward": 0.0, "feedback": "wrong"},
                {"task_id": "t2", "reward": 0.5, "feedback": ""}]}, "best_id": "seed"}),
            encoding="utf-8")
        (rd.root / "final.json").write_text(
            json.dumps({"test": {"reward": 0.8}, "best_id": "cand_0001"}), encoding="utf-8")

        reduced = dashboard.reduce_run(rd)
        g, s = reduced["graph"], reduced["summary"]

        c.check(set(g.keys()) == {"nodes", "root", "best_id"},
                f"graph keys malformed: {sorted(g.keys())}", note="reducer → {nodes,root,best_id}")
        nodes = {n["id"]: n for n in g["nodes"]}
        c.check(set(nodes) == {"seed", "cand_0001", "cand_0002"},
                f"graph nodes wrong: {sorted(nodes)}")
        required = {"id", "parent", "children", "status", "val", "per_task",
                    "cost_usd", "tokens", "seconds", "optimizer_seconds",
                    "runner_seconds", "iteration", "reason", "best_so_far"}
        for n in g["nodes"]:
            missing = required - set(n)
            c.check(not missing, f"node {n['id']} missing fields: {missing}")
            c.check(n["status"] in ("seed", "accepted", "rejected", "failed"),
                    f"node {n['id']} bad status {n['status']!r}")
        c.check(nodes["seed"]["children"] == ["cand_0001"]
                and nodes["cand_0001"]["parent"] == "seed",
                "lineage edges not wired", note="parent↔child edges wired both ways")
        c.check(s["counts"] == {"accepted": 1, "rejected": 1, "failed": 0,
                                "seed": 1, "total": 4 - 1},
                f"status counts wrong: {s['counts']}")
        c.check(s["best_val"] == 0.75 and s["best_id"] == "cand_0001",
                f"best wrong: {s['best_val']} / {s['best_id']}")
        c.check(len(s["gate_warnings"]) == 1, "gate warning not surfaced")

        # --- 3. self-contained, parseable HTML, no leaked secret ---------
        out = dashboard.write_dashboard(rd)
        c.check(out.exists(), "dashboard.html not written", note="renders dashboard.html")
        text = out.read_text(encoding="utf-8")
        try:
            html.parser.HTMLParser().feed(text)
            parsed = True
        except Exception:  # noqa: BLE001
            parsed = False
        c.check(parsed, "dashboard.html is not parseable HTML")
        for marker in ('src="http', 'href="http', "<link", "cdn.", "fetch("):
            c.check(marker not in text, f"dashboard pulls external resource ({marker})",
                    note="self-contained (no CDN / network)")
        for panel in ("Summary", "Score over iterations", "Per-task pass/fail", "Lineage"):
            c.check(panel in text, f"dashboard missing panel: {panel}")
        c.check("supersecret" not in text,
                "secret leaked into dashboard.html", note="secret redaction holds")

        # --- 4. ANSI terminal report renders --------------------------
        with quiet():
            rc2 = run.main(["--run-dir", str(rd.root), "--terminal", "--no-color"])
        c.check(rc2 == 0, "report --terminal returned nonzero",
                note="ANSI terminal report mode")

    return c.emit()


if __name__ == "__main__":
    sys.exit(main())
