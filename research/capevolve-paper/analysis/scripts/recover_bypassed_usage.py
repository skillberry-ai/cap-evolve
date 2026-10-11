#!/usr/bin/env python3
"""Recover optimizer usage that bypassed the campaign gateway (127.0.0.1:4111) and therefore is missing from the cost ledger.

Method: for every campaign run that drives the Claude CLI, sum the usage recorded in the CLI's own session transcripts
(CLAUDE_CONFIG_DIR/projects/**/*.jsonl; de-duplicated by message.id) and compare it with the gateway ledger
(campaign-scratch/logs/gateway_calls.jsonl, role "optimizer"/"proposer"/...) for the same exp-arm-seed tag.
bypassed = max(0, transcript - ledger) per token class.  Priced with protocol/pricing.json (proxy list prices).

Sources of transcripts
  * Suite B/C : runs/E10B|E10C/<arm>/s<k>/claude_cfg           (uid dev)
  * Suite A   : /tmp/e10-opt-<arm>-s<k>/.claude                (uid capopt; read via `sudo -n`, usage fields only)
  * default ~/.claude/projects/*campaign-scratch*              (any `claude` run by uid dev with no CLAUDE_CONFIG_DIR picks the
                                                                real-gateway settings.json: this is bypass by construction)
Only usage fields are read; no credential file is opened.  Output: analysis/out/metrics/bypassed_usage.csv (one row per
run, bypassed_* = 0 when the ledger covers the transcripts) and a one-line summary on stdout.
"""
from __future__ import annotations
import csv, glob, json, os, subprocess, sys
from collections import defaultdict
from pathlib import Path

SCRATCH = Path(os.environ.get("CAMPAIGN_SCRATCH", "/home/dev/projects2/campaign-scratch"))
HERE = Path(__file__).resolve().parent
PAPER = HERE.parents[1]
PRICING = json.loads((PAPER / "protocol/pricing.json").read_text())["usd_per_mtok"]
DEFAULT_MODEL = "aws/claude-sonnet-5-5"
OUT = PAPER / "analysis/out/metrics/bypassed_usage.csv"
LEDGER_ROLES = {"optimizer", "proposer"}   # the Claude-CLI-driven roles; judge/reflection tokens must not mask CLI usage
FIELDS = ("input", "output", "cache_read", "cache_creation")


def price(model: str, v: dict) -> float:
    p = PRICING.get(model) or PRICING.get(model.removeprefix("aws/")) or PRICING[DEFAULT_MODEL]
    return (v["input"] * p["input"] + v["output"] * p["output"] + v["cache_read"] * p["cache_read"]
            + v["cache_creation"] * p["cache_write_5m"]) / 1e6


def ledger() -> dict:
    """(exp-arm-seed) -> summed usage over model-calling optimizer-like roles (not target/user)."""
    acc = defaultdict(lambda: dict.fromkeys(("calls",) + FIELDS, 0))
    for line in open(SCRATCH / "logs/gateway_calls.jsonl", errors="replace"):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        p = d.get("tag", "").split(":")
        if len(p) < 4 or p[3] not in LEDGER_ROLES:
            continue
        u = d.get("usage") or {}
        r = acc[p[1]]
        r["calls"] += 1
        r["input"] += u.get("input_tokens") or 0
        r["output"] += u.get("output_tokens") or 0
        r["cache_read"] += u.get("cache_read_input_tokens") or 0
        r["cache_creation"] += u.get("cache_creation_input_tokens") or 0
    return acc


def scan_text_lines(lines, msgs: dict) -> None:
    for line in lines:
        try:
            d = json.loads(line)
        except ValueError:
            continue
        m = d.get("message") or {}
        u = m.get("usage")
        if d.get("type") != "assistant" or not u:
            continue
        v = dict(input=u.get("input_tokens") or 0, output=u.get("output_tokens") or 0,
                 cache_read=u.get("cache_read_input_tokens") or 0, cache_creation=u.get("cache_creation_input_tokens") or 0,
                 model=m.get("model") or DEFAULT_MODEL)
        k = m.get("id") or d.get("uuid")
        if k not in msgs or sum(v[f] for f in FIELDS) >= sum(msgs[k][f] for f in FIELDS):
            msgs[k] = v


def transcript_usage(files) -> dict:
    msgs: dict = {}
    for f in files:
        with open(f, errors="replace") as fh:
            scan_text_lines(fh, msgs)
    return msgs


def capopt_usage(home: str) -> dict:
    """uid capopt transcripts: extract ONLY usage fields under sudo, never the content."""
    code = ("import json,glob,sys\nfor f in glob.glob(sys.argv[1]+'/.claude/projects/**/*.jsonl',recursive=True):\n"
            " for l in open(f,errors='replace'):\n"
            "  try:d=json.loads(l)\n  except Exception:continue\n"
            "  m=d.get('message') or {}\n"
            "  if d.get('type')=='assistant' and m.get('usage'):print(json.dumps({'type':'assistant','uuid':d.get('uuid'),'message':{'id':m.get('id'),'model':m.get('model'),'usage':m['usage']}}))\n")
    r = subprocess.run(["sudo", "-n", "python3", "-c", code, home], capture_output=True, text=True)
    msgs: dict = {}
    scan_text_lines(r.stdout.splitlines(), msgs)
    return msgs


def totals(msgs: dict) -> dict:
    t = dict.fromkeys(FIELDS, 0)
    for v in msgs.values():
        for f in FIELDS:
            t[f] += v[f]
    t["msgs"] = len(msgs)
    t["usd"] = sum(price(v["model"], v) for v in msgs.values())
    return t


def main() -> int:
    led = ledger()
    rows = []

    def add(suite, arm, seed, key, src, msgs):
        t = totals(msgs)
        L = led.get(key, dict.fromkeys(("calls",) + FIELDS, 0))
        byp = {f: max(0, t[f] - L[f]) for f in FIELDS}
        model = next((v["model"] for v in msgs.values()), DEFAULT_MODEL)
        rows.append(dict(suite=suite, arm=arm, seed=seed, tag_key=key, source=src, transcript_msgs=t["msgs"], ledger_calls=L["calls"],
                         **{f"transcript_{f}": t[f] for f in FIELDS}, **{f"ledger_{f}": L[f] for f in FIELDS},
                         **{f"bypassed_{f}": byp[f] for f in FIELDS}, model=model, bypassed_usd=round(price(model, byp), 4)))

    for suite in ("E10B", "E10C"):
        for cfg in sorted(glob.glob(str(SCRATCH / f"runs/{suite}/*/s*/claude_cfg"))):
            _, arm, seed = Path(cfg).parts[-4], Path(cfg).parts[-3], Path(cfg).parts[-2]
            if arm.startswith("superseded"):
                continue
            files = glob.glob(cfg + "/projects/**/*.jsonl", recursive=True)
            add(suite, arm, seed[1:], f"{suite}-{arm}-{seed}", "claude_cfg", transcript_usage(files))
    for home in sorted(glob.glob("/tmp/e10-opt-*-s[0-9]*")):
        name = Path(home).name[len("e10-opt-"):]
        arm, seed = name.rsplit("-s", 1)
        if int(seed) >= 90:  # smoke/negtest seeds (s98, s99) are not campaign arms but are reported if present
            pass
        add("E10", arm, seed, f"E10-{arm}-s{seed}", "capopt_home", capopt_usage(home))
    # default ~/.claude: any session whose project dir is a campaign run was started without CLAUDE_CONFIG_DIR => real gateway
    for pdir in sorted(glob.glob(os.path.expanduser("~/.claude/projects/*campaign-scratch-runs*"))):
        msgs = transcript_usage(glob.glob(pdir + "/**/*.jsonl", recursive=True))
        add("default-config", Path(pdir).name, "", "", "~/.claude/projects", msgs)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["suite"])
        w.writeheader()
        w.writerows(rows)
    tot = {f: sum(r[f"bypassed_{f}"] for r in rows) for f in FIELDS}
    usd = sum(r["bypassed_usd"] for r in rows)
    print(f"{len(rows)} runs reconciled; bypassed tokens {tot}; bypassed USD (proxy list price) {usd:.2f}; wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
