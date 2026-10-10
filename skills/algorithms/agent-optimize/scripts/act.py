"""act -- the six verbs of the DAG optimizer; every one a thin orchestration over existing scripts (#712).

    python act.py <verb> --run-dir $R [--project $P] [--strict] ...

  propose  TAG [--parent P] [--hypothesis-file F]   first call: prepare_candidate.py --parent copies
           the parent to work/TAG (you then edit it); second call (dir exists): hypothesis rule
           (>= 2 tasks or headroom >= 0.06, hypotheses.validate), pregate.py, then records the
           node (stage checked) + hypotheses.jsonl. A failed pregate returns its text, stage stays
           `proposed`.
  probe    TAG [--tasks a,b | --auto] [--n N] [--budget R] [--plan]   evaluate ONLY the cells the
           ledger lacks (evaluate/run.py --topup-to N). --auto = posterior allocator (needs
           active_eval; otherwise full val). --plan prints the missing cells and spends nothing.
  promote  TAG [--verbose]   needs full-val ledger coverage; a SEQUENTIALLY VALID test vs the champion
           (gate_check reward_gated; when cost_gating is off the posterior rule, never the plain paired
           gate); accept -> commit.py --decision accept (best_id moves), otherwise the node is `alive`
           as a contender and best_id is untouched. Output is trimmed; --verbose adds the full gate.
  prune    TAG --reason R   commit.py --decision reject (driver_judgement), stage `pruned`.
  merge    A B [C..] [--tag T]   merge_n.plan (fold + interaction + probe price); builds
           work/T and records the merge node; the probe it asks for is yours to run (`probe T ...`).
  finalize [--n-confirm 3] [--n-trials N] [--seal-anyway REASON]   confirm-evaluate the champion's
           committed snapshot on full val with fresh seeds, test it against the seed, seal test ONCE
           (phases/finalize), write final.json. A confirm that does not accept refuses to seal unless
           --seal-anyway REASON (then the result is recorded as "no accepted change").

Spending verbs (propose, probe, promote-accept, finalize confirm) refuse when the budget is exhausted
(the digest's EXHAUSTED) unless --over-budget REASON (recorded as an event). A full-val probe prints its
estimate and needs --yes. Concurrent probes claim (cap_hash, task) cells, so one set of rollouts runs.

Every verb: meters optimizer spend first (digest.meter, idempotent), logs a `decision` event that
records whether the verb followed the last digest's suggestions, and prints the digest.
Ablations (optimizer_config.py): dag_parallel off => propose parents on best_id; active_eval off
=> probe --auto means full val; smart_merge off => merge refuses (use merge_search.py);
cost_gating off => paired gate; failure_clustering off => no hypothesis rule; pregate off =>
skipped; context_digest off => no digest. Infra errors fail OPEN with a loud warning
(`warnings` in the output); --strict turns them into refusals. Exit 0 ok, 1 not applied (gate
says no / merge conflict), 2 refused.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path

import _bootstrap  # noqa: F401  # side-effect import: seeds sys.path for cap_evolve

import digest
from cap_evolve import (RunDir, eval_index, graph, harness, hypotheses, optimizer_config, posterior, sched,
                        schema_v2)
from cap_evolve.candidate_graph import CandidateGraph
from cap_evolve.rundir import _file_lock
from cap_evolve.specfile import spec_for_run

HERE = Path(__file__).resolve().parent
SKILLS = Path(os.environ.get("CAPEVOLVE_SKILLS_DIR", HERE.parents[2]))
PY = sys.executable
CLAIM_STALE_S = 2 * 3600   # an in-progress evaluation claim older than this is stolen
DECISION = {"propose": "propose", "probe": "screen", "promote": "promote", "prune": "kill",
            "merge": "merge", "finalize": "stop"}


class Refused(Exception):
    def __init__(self, msg, **extra):
        super().__init__(msg)
        self.extra = extra


def sh(cmd: list[str], env: dict | None = None) -> tuple[int, str, str]:
    """Run a sibling script. Module-level so tests can replace it."""
    p = subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                       env={**os.environ, **(env or {})})
    return p.returncode, p.stdout, p.stderr


def jload(text: str):
    """Parse a script's stdout as JSON; tolerate stray log lines before the object (the first
    line that starts a JSON object/array and parses wins)."""
    try:
        return json.loads(text)
    except ValueError:
        pass
    for m in re.finditer(r"^[\[{]", text or "", re.M):
        try:
            return json.JSONDecoder().raw_decode(text[m.start():])[0]
        except ValueError:
            continue
    return None


class Ctx:
    def __init__(self, a):
        self.run_dir = RunDir.open(Path(a.run_dir).resolve())  # absolute: metering finds the session log from it
        self.root = Path(self.run_dir.root)
        self.project = Path(a.project) if a.project else None
        self.strict = a.strict
        self.spec = spec_for_run(self.run_dir, self.project)
        self.cfg = optimizer_config.resolve(self.spec)
        self.warnings: list[str] = []

    def warn(self, msg):
        self.warnings.append(msg)
        print(f"act WARNING: {msg}", file=sys.stderr)

    def infra(self, msg):
        """Infra error: refuse under --strict, otherwise warn loudly (stderr, output, and the
        digest's INFRA line) and carry on."""
        if self.strict:
            raise Refused(f"{msg} (--strict)")
        self.warnings.append(msg)
        digest.infra(self.run_dir, f"act: {msg}")

    def check_budget(self, a):
        """Refuse a spend when the run's budget is exhausted (what the digest calls EXHAUSTED),
        unless ``--over-budget REASON`` is given; the override is recorded in events."""
        stop, why = self.run_dir.budget_exhausted()
        if not stop:
            return
        reason = (getattr(a, "over_budget", None) or "").strip()
        if not reason:
            raise Refused(f"budget exhausted: {why}; refusing to spend",
                          next="act.py finalize (seal what you have) or re-run with --over-budget REASON")
        self.run_dir.log_event("over_budget_override", verb=a.verb, reason=reason, budget=why)
        self.warn(f"over-budget override recorded: {reason}")

    def val_ids(self) -> list[str]:
        return [str(t) for t in self.run_dir.read_splits().ids("val")]

    def champion(self) -> str:
        return self.run_dir.best_id or "seed"

    def work(self, tag) -> Path:
        return self.root / "work" / tag

    def need_project(self):
        if not self.project:
            raise Refused("--project is required for this verb")
        return self.project

    def node(self, tag, status, **extra):
        return graph.append_node(self.run_dir, node_id=tag, parents=None, status=status, **extra)

    def decision(self, verb, tag, near=(), **evidence):
        """Log the decision; ``followed_digest`` = the last digest suggested this verb on ``tag``
        (or on one of ``near``, e.g. the cluster a proposal targets)."""
        followed = False
        try:
            last = json.loads((self.root / "digest_last.json").read_text(encoding="utf-8"))
            names = {tag, *near}
            followed = any(s["verb"] == verb and names & set(str(s["target"]).split()) for s in last["suggested"])
        except (OSError, ValueError, KeyError):
            pass
        schema_v2.emit(self.run_dir, "decision", id=tag, decision=DECISION[verb],
                       evidence=evidence, followed_digest=followed,
                       optimizer_usd=round(self.run_dir.spent.optimizer_usd, 4))
        return followed

    def opt_delta(self, tag) -> float:
        n = graph.latest_node(self.run_dir, tag) or {}
        return round(self.run_dir.spent.optimizer_usd - float(n.get("opt_usd_at_propose") or 0.0), 4)


# ---- propose ---------------------------------------------------------------------------------

def _hypothesis(a, ctx) -> dict | None:
    raw = a.hypothesis_file
    if not raw:
        return None
    try:
        h = json.loads(Path(raw).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Refused(f"--hypothesis-file unreadable: {e}")
    return h


def propose(a, ctx):
    run_dir, tag = ctx.run_dir, a.tag
    ctx.check_budget(a)
    best = ctx.champion()
    saved = ctx.work(tag).parent / f".parent_{tag}"      # 1st call records it: the 2nd must not re-parent
    parent = a.parent or (saved.read_text().strip() if saved.is_file() else best)
    if not ctx.cfg["dag_parallel"] and parent != best:
        ctx.warn(f"dag_parallel is off: parenting on best_id {best!r}, not {parent!r}")
        parent = best
    work = ctx.work(tag)
    if not work.is_dir():
        rc, out, err = sh([PY, HERE / "prepare_candidate.py", "-r", ctx.root, "-t", tag, "--parent", parent])
        if rc != 0:
            raise Refused("prepare_candidate failed", output=jload(out) or out, stderr=err[-400:])
        saved.write_text(parent)
        return 0, {"stage": "proposed", "parent": parent, "work": str(work),
                   "next": f"edit {work} (one coherent edit for ONE hypothesis), then re-run: "
                           f"act.py propose {tag} --parent {parent} --hypothesis-file H.json"}
    h = _hypothesis(a, ctx)
    out = {"parent": parent, "work": str(work)}
    if ctx.cfg["failure_clustering"]:
        if h is None:
            raise Refused("a hypothesis is required (--hypothesis-file: {id, cluster_ids, claim, "
                          "predicted_tasks, predicted_mechanism, edit_scope})")
        clusters = digest.load_clusters(run_dir)
        if clusters is None:
            ctx.infra("no clusters.json: hypothesis size rule NOT checked")
        else:
            ok, why = hypotheses.validate(h, clusters, a.small_edit_justification or "")
            if not ok:
                raise Refused(f"hypothesis rejected: {why}")
            if why:
                out["hypothesis_note"] = why
            rep = hypotheses.repeat_of(h, hypotheses.load(run_dir))
            if rep:
                out["repeat_of"] = rep
    pg = {"skipped": "ablation pregate=false"}
    if ctx.cfg["pregate"]:
        cmd = [PY, HERE / "pregate.py", "--candidate", work, "--parent", digest.cand_dir(run_dir, parent),
               "--run-dir", ctx.root] + (["--strict"] if ctx.strict else [])
        rc, so, se = sh(cmd)
        pg = jload(so)
        if pg is None or rc not in (0, 1):
            ctx.infra(f"pregate infra error rc={rc}: {(se or so)[-300:]}")
            pg = {"ok": True, "skipped": True, "warnings": ["pregate did not run"]}
        elif rc == 1 or not pg.get("ok", True):
            ctx.node(tag, "proposed", stage="proposed", pregate=pg)
            raise Refused(f"pregate failed: {pg.get('failure')}", pregate=pg, stage="proposed")
        for w in pg.get("warnings") or []:
            ctx.warn(f"pregate: {w}")
    rec = None
    if h is not None:
        rec = hypotheses.append(run_dir, {**h, "id": h.get("id") or f"h_{tag}", "candidate": tag})
    ctx.node(tag, "proposed", stage="checked", pregate=pg, hypothesis_id=(rec or {}).get("id"),
             cluster_ids=(h or {}).get("cluster_ids"), capability_hash=eval_index.cap_hash(work),
             opt_usd_at_propose=round(run_dir.spent.optimizer_usd, 4), base_for_eval=parent)
    schema_v2.emit(run_dir, "candidate_proposed", id=tag, parents=[parent])
    out.update(stage="checked", pregate=pg.get("ok"), hypothesis_id=(rec or {}).get("id"),
               next=f"act.py probe {tag} --auto")
    ctx.decision("propose", tag, near=(h or {}).get("cluster_ids") or (), hypothesis=(rec or {}).get("id"),
                 pregate=pg.get("ok"))
    return 0, out


def topup_cmd(ctx, tag, n, ids) -> list[str]:
    """evaluate/run.py --topup-to n for ``tag`` (a work dir or a committed snapshot)."""
    cmd = eval_index.eval_cmd(ctx.root, ctx.need_project(), tag, "val", n, ids=ids, skills_dir=SKILLS)
    cmd[cmd.index("--candidate") + 1] = str(digest.cand_dir(ctx.run_dir, tag))
    return cmd + ["--topup-to", str(n)]


# ---- probe -----------------------------------------------------------------------------------

def probe_ids(a, ctx, tag, parent, val_ids) -> tuple[list[str], str]:
    if a.tasks:
        ids = [t.strip() for t in a.tasks.split(",") if t.strip()]
        bad = [t for t in ids if t not in val_ids]
        if bad:
            raise Refused(f"tasks {bad} are not in the frozen val split (test is never probed)")
        return ids, "explicit"
    if a.auto and ctx.cfg["active_eval"]:
        P = digest.pair(ctx.run_dir, tag, parent, val_ids)
        picks = sched.pick(P, [max(0.0, a.n - n) for n in P.nc], [0.0] * P.T, a.budget)
        return sorted({val_ids[i] for _, i in picks}), "posterior allocator (active_eval)"
    if a.auto:
        ctx.warn("probe --auto is running FULL val: " + digest.ENGINE_FIX)
    return list(val_ids), "full val" + ("" if ctx.cfg["active_eval"] else " (active_eval off)")


def _owner() -> str:
    return f"{os.getpid()}:{threading.get_ident()}"


def _alive(c) -> bool:
    if time.time() - float(c.get("t") or 0) > CLAIM_STALE_S:
        return False
    try:
        os.kill(int(c["pid"]), 0)
        return True
    except (OSError, ValueError, KeyError):
        return False


def claim_cells(ctx, h: str, ids, n: int, poll: float = 0.5, wait_s: float = CLAIM_STALE_S):
    """Claim the (cap_hash, task) cells that still lack ``n`` trials, so concurrent probes launch
    ONE set of rollouts. Returns (missing_for_me, claim_keys). A cell claimed by a live process
    (pid alive, younger than CLAIM_STALE_S) is waited for, then re-read from the ledger; a dead or
    stale claim is stolen. Claims live in ``$R/eval_claims.json`` under a file lock."""
    path = ctx.root / "eval_claims.json"
    end = time.time() + wait_s
    while True:
        with _file_lock(ctx.root / ".claims.lock"):
            try:
                claims = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                claims = {}
            miss = eval_index.missing(ctx.run_dir, h, ids, n)
            theirs = {t for t in miss if f"{h}|{t}" in claims and _alive(claims[f"{h}|{t}"])
                      and claims[f"{h}|{t}"].get("owner") != _owner()}
            mine = {t: v for t, v in miss.items() if t not in theirs}
            if mine or not theirs:
                keys = [f"{h}|{t}" for t in mine]
                for k in keys:
                    claims[k] = {"pid": os.getpid(), "owner": _owner(), "t": time.time()}
                tmp = path.with_suffix(f".{os.getpid()}.tmp")
                tmp.write_text(json.dumps(claims), encoding="utf-8")
                os.replace(tmp, path)
                return mine, keys
        if time.time() > end:
            raise Refused("cells are claimed by another running probe that never finished", cells=sorted(theirs)[:10])
        time.sleep(poll)


def release_cells(ctx, keys) -> None:
    path = ctx.root / "eval_claims.json"
    with _file_lock(ctx.root / ".claims.lock"):
        try:
            claims = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for k in keys:
            if claims.get(k, {}).get("owner") == _owner():
                claims.pop(k)
        path.write_text(json.dumps(claims), encoding="utf-8")


def probe(a, ctx):
    run_dir, tag = ctx.run_dir, a.tag
    d = digest.cand_dir(run_dir, tag)
    if not d.is_dir():
        raise Refused(f"no candidate dir for {tag!r}")
    val_ids = ctx.val_ids()
    node = graph.latest_node(run_dir, tag) or {}
    parent = (node.get("parents") or ["seed"])[0]
    ids, how = probe_ids(a, ctx, tag, parent, val_ids)
    h = eval_index.cap_hash(d)
    miss = eval_index.missing(run_dir, h, ids, a.n)
    out = {"tasks": ids, "selected_by": how, "n": a.n, "missing_cells": sum(miss.values()),
           "missing": dict(list(miss.items())[:12])}
    sp = run_dir.spent
    upr = sp.usd / sp.metric_calls if sp.metric_calls and sp.usd else None
    out["estimate"] = {"rollouts": sum(miss.values()), "usd": round(upr * sum(miss.values()), 2) if upr else None}
    if a.plan or not miss:
        out["next"] = "nothing missing: every requested cell is in the ledger (free)" if not miss else "--plan: nothing run"
        return 0, out
    if how.startswith("full val") and not a.yes:
        raise Refused(f"full-val probe would run ~{out['estimate']['rollouts']} rollouts"
                      + (f" (~${out['estimate']['usd']})" if upr else "") + "; confirm with --yes, or pick "
                      "--tasks / --auto (active_eval on)", estimate=out["estimate"])
    ctx.check_budget(a)
    miss, keys = claim_cells(ctx, h, ids, a.n)   # concurrent probes of the same cells launch one set of rollouts
    out["missing_cells"] = sum(miss.values())
    if not miss:
        out["next"] = "another probe produced these cells while we waited (free)"
        return 0, out
    try:
        cmd = topup_cmd(ctx, tag, a.n, list(miss))
        env = {}
        cap = ctx.spec.get("gateway_max_concurrency")
        if cap and not os.environ.get("CAPEVOLVE_WORKERS"):
            env["CAPEVOLVE_WORKERS"] = str(cap)  # one gateway cap shared by every branch
        rc, so, se = sh(cmd, env)
    finally:
        release_cells(ctx, keys)
    if rc != 0:
        raise Refused(f"evaluation failed rc={rc}", stderr=(se or so)[-500:])
    P = digest.pair(run_dir, tag, parent, val_ids)
    st = digest.stats(P)
    cost = round(sum(r.get("cost") or 0.0 for r in eval_index.rows(run_dir) if r["cap_hash"] == h), 4)
    ctx.node(tag, "proposed", stage="probed", eval_state="full" if st["cov"] == st["T"] else "partial",
             coverage={"split": "val", "task_ids": ids, "n_tasks": len(ids), "n_val_tasks": st["T"],
                       "full": st["cov"] == st["T"]},
             post={"mean": st["mean"], "se": st["se"], "p_beat_parent": digest.p_beat(P)},
             cost_ledger={"eval_agent_usd": cost})
    out.update(ran_cells=sum(miss.values()), post={"mean": st["mean"], "se": st["se"], "cov": f"{st['cov']}/{st['T']}",
                                                    "p_beat_parent": digest.p_beat(P)})
    ctx.decision("probe", tag, cells=out["ran_cells"], tasks=len(ids))
    return 0, out


# ---- promote / prune -------------------------------------------------------------------------

GATE_KEYS = ("accept", "indecisive", "delta", "se", "z", "reason")


def judge(ctx, tag, ref) -> dict:
    """The accept test for ``tag`` vs ``ref``; ALWAYS sequentially valid (promote and finalize are
    re-run as evidence grows). cost_gating on: gate_check --mode reward_gated (Bonferroni over its
    looks). cost_gating off: the posterior rule (posterior.py: accept needs P(D>dmin)>=0.95 and canary
    cover, validated under repeated looks) -- never the plain paired gate, whose cumulative false-accept
    rate over 8 looks was measured at 39%."""
    P = digest.pair(ctx.run_dir, tag, ref, ctx.val_ids())
    v = P.verdict(random.Random(0), int(sum(P.nc)))
    base = {"p_beat": round(v["p_beat"], 3)}
    if ctx.cfg["cost_gating"]:
        rc, so, se = sh([PY, HERE / "gate_check.py", "--run-dir", ctx.root, "--candidate", tag,
                         "--current", ref, "--mode", "reward_gated"])
        g = jload(so)
        if g is None or "error" in g:
            raise Refused(f"gate_check could not judge {tag}: {(g or {}).get('error') or se[-300:]}")
        return {**base, "verdict": g["verdict"], "gate_mode": "reward_gated", "reward": g["candidate"]["reward"],
                "gate": {k: g["gate"][k] for k in GATE_KEYS if k in g["gate"]}, "full_gate": g["gate"]}
    reward = harness.split_result_from_rollouts(ctx.run_dir, tag, "val").reward
    verdict = {"accept": "accept", "prune": "reject"}.get(v["decision"], "indecisive")
    return {**base, "verdict": verdict, "gate_mode": "posterior", "reward": reward,
            "gate": {"d_mean": round(v["d_mean"], 4), "canary_tasks": v["canary_tasks"]}}


def commit(ctx, tag, decision, note, extra: list[str]) -> tuple[int, dict]:
    rc, so, se = sh([PY, HERE / "commit.py", "--run-dir", ctx.root, "--candidate-id", tag,
                     "--from-dir", ctx.work(tag), "--decision", decision, "--note", note, *extra])
    return rc, (jload(so) or {"stdout": so[-500:], "stderr": se[-300:]})


def promote(a, ctx):
    run_dir, tag = ctx.run_dir, a.tag
    champ = ctx.champion()
    if tag == champ:
        raise Refused(f"{tag} is already the champion")
    d = digest.cand_dir(run_dir, tag)
    miss = eval_index.missing(run_dir, eval_index.cap_hash(d), ctx.val_ids(), 1)
    if miss:
        raise Refused(f"{tag} lacks full-val ledger coverage ({len(miss)} tasks unmeasured)",
                      next=f"act.py probe {tag} --tasks {','.join(list(miss)[:10])} --n 1")
    j = judge(ctx, tag, champ)
    out = {"champion": champ, "verdict": j["verdict"], "p_beat_champion": j["p_beat"],
           "gate_mode": j["gate_mode"], "gate": j["gate"]}
    if a.verbose:
        out["full_gate"] = j.get("full_gate")
    extra = shlex.split(a.commit_extra or "")
    accept = j["verdict"] == "accept"
    if accept:
        ctx.check_budget(a)
        rc, res = commit(ctx, tag, "accept", a.note or "act.py promote", ["--val", str(j["reward"]), *extra])
        if rc != 0:
            raise Refused("commit.py refused the accept", commit=res)
        out["best_id"] = RunDir.open(ctx.root).best_id
    ctx.node(tag, "accepted" if accept else "gated", stage="alive", tip=True,
             post={"p_beat_champion": j["p_beat"]}, cost_ledger={"optimizer_usd": ctx.opt_delta(tag)})
    out.update(stage="alive", champion_changed=accept)
    ctx.decision("promote", tag, verdict=j["verdict"], p_beat_champion=j["p_beat"])
    return (0 if accept else 1), out


def prune(a, ctx):
    run_dir, tag = ctx.run_dir, a.tag
    if not a.reason.strip():
        raise Refused("--reason is required")
    if not ctx.work(tag).is_dir():
        raise Refused(f"unknown candidate {tag!r}: no work dir to prune")
    why = f"act.py prune: {a.reason}"
    rc, res = commit(ctx, tag, "reject", why, [
        "--reject-basis", "driver_judgement", "--bypassed-gate-justification", why,
        "--missing-handover-justification", why, "--missing-diagnosis-justification", why,
        "--missing-ranked-issues-justification", why, "--retry-justification", why,
        *shlex.split(a.commit_extra or "")])
    if rc != 0:
        raise Refused("commit.py refused the prune", commit=res)
    if optimizer_config.new_engine(ctx.spec):
        run_dir.update_spent(accepted=True)  # new engine has no stall rule: undo commit's reject count
    ctx.node(tag, "rejected", stage="pruned", tip=False, cost_ledger={"optimizer_usd": ctx.opt_delta(tag)})
    node = graph.latest_node(run_dir, tag) or {}
    for h in digest.hyp_latest(run_dir):
        if h.get("candidate") == tag or h.get("id") == node.get("hypothesis_id"):
            hypotheses.append(run_dir, {**h, "status": "pruned"})
    ctx.decision("prune", tag, reason=a.reason)
    return 0, {"stage": "pruned", "reason": a.reason}


# ---- merge -----------------------------------------------------------------------------------

def merge(a, ctx):
    if not ctx.cfg["smart_merge"]:
        raise Refused("smart_merge is off: use the pairwise path (merge_search.py without --nway)")
    import merge_n
    run_dir, tags = ctx.run_dir, a.tags
    if len(tags) < 2:
        raise Refused("merge needs at least two candidate tags")
    g = CandidateGraph.load(run_dir)
    dir_of = lambda t: digest.cand_dir(run_dir, t)  # noqa: E731
    out_tag = a.tag or "merge_" + "_".join(tags)
    tt = {t: [] for t in tags}
    try:
        import merge_search
        tt = {t: merge_search._mechanisms_targets(ctx.root, t) for t in tags}
    except Exception as e:  # noqa: BLE001
        ctx.warn(f"touched-task evidence unavailable ({type(e).__name__}): interaction will be 'unknown'")
    wins = merge_n.wins_from_run(run_dir, tags, ctx.champion()) or {}
    res = merge_n.plan(tags, dir_of, g, touched_tasks=tt, wins=wins, all_tasks=ctx.val_ids(),
                       out_dir=ctx.work(out_tag), run_dir=run_dir)
    rec = merge_n.node_record(res, out_tag)
    out = {k: res.get(k) for k in ("merged", "unmerged", "conflicts", "max_I", "unknown_pairs", "probe", "eval_request")}
    out["tag"] = out_tag
    if rec is None:
        return 1, {**out, "stage": None, "next": "nothing merged: resolve the conflicts above by hand"}
    kw = dict(rec)
    graph.append_node(run_dir, node_id=kw.pop("id"), parents=kw.pop("parents"),
                                       status=kw.pop("status"), edit_kind=kw.pop("edit_kind"),
                                       **{**kw, "capability_hash": eval_index.cap_hash(ctx.work(out_tag)),
                                          "opt_usd_at_propose": round(run_dir.spent.optimizer_usd, 4)})
    req = res.get("eval_request")
    out["stage"] = "built"
    out["next"] = (f"act.py probe {out_tag} --tasks {','.join(req['task_ids'])} --n {req['n_trials']}"
                   f"  ({req['reason']}; {sum((req.get('missing') or {}).values())} cells not in the ledger)"
                   if req else f"auto-merged without a probe (max I {res.get('max_I')} below the probe bar)")
    ctx.decision("merge", out_tag, parents=res["merged"], max_I=res.get("max_I"), probe=res.get("probe"))
    return (0 if res["built"] else 1), out


# ---- finalize --------------------------------------------------------------------------------

def finalize(a, ctx):
    run_dir = ctx.run_dir
    project = ctx.need_project()
    if run_dir.read_splits().test_used:
        raise Refused("test is already sealed (scored once): a second finalize is refused")
    champ = ctx.champion()
    d = digest.cand_dir(run_dir, champ)   # the committed snapshot: the bytes the finalize phase seals
    out = {"champion": champ}
    if a.n_confirm > 0 and champ != "seed":
        ctx.check_budget(a)
        have = eval_index.counts(run_dir, eval_index.cap_hash(d), "val")
        want = max((n for _, n in have.values()), default=0) + a.n_confirm  # fresh seeds: ledger trial_idx continues
        rc, so, se = sh(topup_cmd(ctx, champ, want, ctx.val_ids()))
        if rc != 0:
            raise Refused(f"confirm evaluation failed rc={rc}", stderr=(se or so)[-500:])
        j = judge(ctx, champ, "seed")
        out["confirm"] = {"n_trials": want, "verdict_vs_seed": j["verdict"], "gate_mode": j["gate_mode"],
                          "p_beat_seed": j["p_beat"], "gate": j["gate"]}
        if j["verdict"] != "accept":
            if not (a.seal_anyway or "").strip():
                raise Refused(f"confirm gate says {j['verdict']} vs the seed: test NOT sealed", confirm=out["confirm"],
                              next="keep optimizing, or finalize --seal-anyway REASON to score test with no accepted change")
            out["no_accepted_change"] = True
            out["seal_anyway_reason"] = a.seal_anyway
            out["claim"] = ("the champion did NOT beat the seed on confirmation: report this run as having no "
                            "accepted change (the test score below is for the best-so-far, not an improvement)")
    n_trials = a.n_trials or int(ctx.spec.get("num_trials") or 1)
    rc, so, se = sh([PY, SKILLS / "phases" / "finalize" / "scripts" / "run.py", "--run-dir", ctx.root,
                     "--project", project, "--n-trials", str(n_trials)])
    if rc != 0:
        raise Refused(f"finalize phase failed rc={rc}", stderr=(se or so)[-500:])
    out["final"] = jload(so) or so[-500:]
    (ctx.root / "final.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    ctx.decision("finalize", champ, verdict=(out.get("confirm") or {}).get("verdict_vs_seed"))
    return 0, out


# ---- cli -------------------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="act", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--run-dir", required=True)
    common.add_argument("--project", default=None)
    common.add_argument("--strict", action="store_true", help="infra errors refuse instead of warning")
    sub = p.add_subparsers(dest="verb", required=True)
    s = sub.add_parser("propose", parents=[common]); s.add_argument("tag"); s.add_argument("--parent")
    s.add_argument("--hypothesis-file"); s.add_argument("--small-edit-justification"); s.add_argument("--over-budget", metavar="REASON")
    s = sub.add_parser("probe", parents=[common]); s.add_argument("tag")
    s.add_argument("--tasks"); s.add_argument("--auto", action="store_true")
    s.add_argument("--n", type=int, default=1, help="trials per cell to reach (default 1)")
    s.add_argument("--budget", type=int, default=sched.ROUND, help="--auto: max new rollouts picked")
    s.add_argument("--plan", action="store_true", help="show the missing cells, spend nothing")
    s.add_argument("--yes", action="store_true", help="confirm a full-val probe (shows the estimate otherwise)")
    s.add_argument("--over-budget", metavar="REASON", help="spend although the budget is exhausted (recorded)")
    s = sub.add_parser("promote", parents=[common]); s.add_argument("tag")
    s.add_argument("--note"); s.add_argument("--commit-extra", help="extra commit.py flags (quoted)")
    s.add_argument("--verbose", action="store_true", help="include the full gate evidence")
    s.add_argument("--over-budget", metavar="REASON")
    s = sub.add_parser("prune", parents=[common]); s.add_argument("tag")
    s.add_argument("--reason", required=True); s.add_argument("--commit-extra")
    s = sub.add_parser("merge", parents=[common]); s.add_argument("tags", nargs="+"); s.add_argument("--tag")
    s = sub.add_parser("finalize", parents=[common])
    s.add_argument("--n-confirm", type=int, default=3, help="extra full-val trials on the champion (0 = skip)")
    s.add_argument("--n-trials", type=int, default=0, help="test trials (default: spec num_trials)")
    s.add_argument("--seal-anyway", metavar="REASON", help="seal test although the confirm gate did not accept (recorded)")
    s.add_argument("--over-budget", metavar="REASON")
    return p


VERBS = {"propose": propose, "probe": probe, "promote": promote, "prune": prune, "merge": merge,
         "finalize": finalize}


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    try:
        ctx = Ctx(a)
    except ValueError as e:  # an unknown ablation key: a typo must not run the wrong experiment
        print(json.dumps({"verb": a.verb, "ok": False, "error": str(e)}, indent=2))
        return 2
    digest.meter(ctx.run_dir, ctx.strict)
    try:
        rc, res = VERBS[a.verb](a, ctx)
        body = {"verb": a.verb, "ok": rc == 0, "result": res}
    except Refused as e:
        rc, body = 2, {"verb": a.verb, "ok": False, "error": str(e), **e.extra}
    if ctx.warnings:
        body["warnings"] = ctx.warnings
    if ctx.cfg["context_digest"]:
        try:
            d, text = digest.fit(digest.build(ctx.run_dir, ctx.project, ctx.spec, ctx.strict))
            digest.save_suggestions(ctx.run_dir, d)
            body["digest"] = text
        except Exception as e:  # noqa: BLE001 - the verb already happened; do not lose its result
            body.setdefault("warnings", []).append(f"digest failed: {type(e).__name__}: {e}")
    print(json.dumps(body, indent=2, default=str))
    return rc


if __name__ == "__main__":
    sys.exit(main())
