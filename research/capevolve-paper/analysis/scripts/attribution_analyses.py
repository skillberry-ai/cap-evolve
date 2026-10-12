#!/usr/bin/env python3
"""attribution_analyses.py: edit attribution, failure types, regressions, promotions, shrinkage, cost per point.

Re-runnable; works on SEARCH-TIME data now and adds FINAL-set columns when
campaign-scratch/final_eval/{A,B,C}/results_long.csv exists (columns arm,seed,task,reward,family; see real_numbers.py).
Read-only on run artifacts; reuses searchtime_results.py for run discovery, candidate diffs and gate bookkeeping.
Never reads a final set during search-time analyses: rollouts are read only from <run>/rollouts/val/ (the search split),
and the final_eval CSVs are read only for items (5) and (6).

Outputs  analysis/out/attrib/*.csv, summary.md, attrib.json
         paper/tables/attrib_*.tex       paper/figures/attrib_*.pdf
Run:     /home/dev/projects2/campaign-scratch/venv-paper/bin/python -I analysis/scripts/attribution_analyses.py

Definitions (all documented once here)
  selection split : the split a run's own gate uses (A: val-40; B: opt-49; C: opt-20); per-task reward = mean over trials.
  pass            : per-task mean reward >= 0.5.   FIXED = fails at the parent, passes at the candidate; BROKE = the reverse.
  parent          : graph.jsonl parent, else the seed.
  LEDGER fixed/broke : the framework's own lists (moves exceeding 2*SE of the per-task measurement error), parsed from the
                    run's latest work/*/LEDGER.md; the raw eval_index counts include noise flips and are reported beside them.
  protect set     : seed-solid tasks (seed mean reward >= 0.999); protect violation = a protect task whose candidate reward < 1.
  surface         : by path, as in searchtime_results.surface().  dominant surface = surface with most changed lines among
                    capability surfaces (system_prompt, task_template, tool_code, mcp, skill_files); process docs excluded.
  failure type    : deterministic regexes on scorer feedback of the seed's failed tasks (no LLM, nothing sent anywhere).
Selection-split numbers are optimistic and noisy (a single trial per task on A); FIXED counts include noise flips.
"""
import csv
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import searchtime_results as st  # noqa: E402

PAPER, SCRATCH = st.PAPER, st.SCRATCH
OUT = PAPER / "analysis" / "out" / "attrib"
TABLES, FIGS = st.TABLES, st.FIGS
FINAL = SCRATCH / "final_eval"
CAP_SURF = ["system_prompt", "task_template", "tool_code", "mcp", "skill_files"]
EDIT_ARMS = ("hc", "hcstock", "ao", "oneshot") + st.SUITE_D_CAP
PASS = 0.5

# ----------------------------------------------------------------------------- failure typing
# type -> coarse group used in the paper table
GROUPS = {
    "missing_action": "forgotten rule or step",
    "wrong_argument": "tool misuse",
    "state_side_effect": "unexpected side effect",
    "communication": "output / contract",
    "no_output_file": "output / contract",
    "wrong_result": "knowledge or rule gap",
    "partial_result": "knowledge or rule gap",
    "infra": "infra (unscorable)",
    "other": "other",
}


def label_failure(base, feedback, error, term):
    fb = feedback or ""
    flags = set()
    if error or fb.startswith("Rollout failed") or "infrastructure reason" in fb:
        return "infra", {"infra"}
    if base == "A":
        if "produced NO output file" in fb or "never wrote output_path" in fb:
            flags.add("no_output_file")
        m = re.search(r"(\d+)/(\d+) test cases passed", fb)
        if m and 0 < int(m.group(1)) < int(m.group(2)):
            flags.add("partial_result")
        if "produced an output file" in fb:
            flags.add("wrong_result")
        for t in ("no_output_file", "partial_result", "wrong_result"):
            if t in flags:
                return t, flags
        return "other", flags
    if "was never called" in fb:
        flags.add("missing_action")
    if "agent used" in fb:
        flags.add("wrong_argument")
    if "NO gold action mismatched" in fb:
        flags.add("state_side_effect")
    if "not clearly communicated" in fb or "behavioral expectation" in fb:
        flags.add("communication")
    for t in ("missing_action", "wrong_argument", "state_side_effect", "communication"):
        if t in flags:
            return t, flags
    return "other", flags


TYPE_WORDS = {"missing_action": "Missing action", "wrong_argument": "Wrong arg.", "state_side_effect": "Side effect",
              "communication": "Comm.", "no_output_file": "No output", "wrong_result": "Wrong result",
              "partial_result": "Partial", "infra": "Infra", "other": "Other", "was_passing_or_unlabelled": "Unlabelled"}


def spreadsheet_category(fb):
    m = re.search(r"\((Cell-Level|Sheet-Level)", fb or "")
    return m.group(1) if m else ""


def seed_failures(cap, base, suite, arm, seed):
    rows = []
    d = cap / "rollouts" / "val"   # search split only
    byt = defaultdict(list)
    for f in d.glob("*__seed__t*.json"):
        task = f.name.split("__seed__")[0]
        try:
            j = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        byt[task].append(j)
    for task, js in sorted(byt.items()):
        rew = [j["score"].get("reward") for j in js if j.get("score", {}).get("reward") is not None]
        if not rew:
            continue
        m = sum(rew) / len(rew)
        if m >= PASS:
            continue
        j = min(js, key=lambda x: x["score"].get("reward") or 0)
        ro = j.get("rollout", {})
        typ, flags = label_failure(base, j["score"].get("feedback"), ro.get("error"), (ro.get("metadata") or {}).get("termination_reason"))
        rows.append(dict(suite=suite, base_suite=base, arm=arm, seed=seed, task=task, seed_reward=m, failure_type=typ,
                         group=GROUPS[typ], flags="+".join(sorted(flags)), category=spreadsheet_category(j["score"].get("feedback"))
                         if base == "A" else ""))
    return rows


# ----------------------------------------------------------------------------- per-task rewards, ledger
def task_rewards(cap, excl=None):
    """{tag: {task: mean reward}} on the selection split, main tags only plus conf tags, non-subset rows."""
    acc = defaultdict(lambda: defaultdict(list))
    for r in st.jl(cap / "eval_index.jsonl"):
        if r.get("split") != "val" or r.get("subset") or r.get("reward") is None:
            continue
        if st.is_excluded(excl, r["tag"], r.get("ts")):
            continue
        acc[r["tag"]][str(r["task"])].append(r["reward"])
    return {t: {k: sum(v) / len(v) for k, v in d.items()} for t, d in acc.items()}


LEDGER_ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*(\S+)\s*\|\s*(\S+)\s*\|\s*(\w+)\s*\|\s*([\d.]+|-+)?\s*\|\s*([+\-\u2212][\d.]+|-+)?\s*\|\s*\{(.*?)\}\s*\|\s*\{(.*?)\}\s*\|\s*\{(.*?)\}\s*\|")


def ledger(cap):
    ls = sorted((cap / "work").glob("*/LEDGER.md"), key=lambda p: p.stat().st_mtime) if (cap / "work").is_dir() else []
    out = {}
    if not ls:
        return out
    for line in ls[-1].read_text(errors="replace").splitlines():
        m = LEDGER_ROW.match(line)
        if m:
            sp = lambda s: [x.strip() for x in s.split(",") if x.strip()]
            out[m.group(2)] = dict(outcome=m.group(4), broke=sp(m.group(7)), fixed=sp(m.group(8)), unresolved=sp(m.group(9)))
    return out


def parents(cap):
    p = {}
    for g in st.jl(cap / "graph.jsonl"):
        if g.get("parents"):
            p[g["id"]] = g["parents"][0]
    return p


# ----------------------------------------------------------------------------- statistics helpers
def ranks(v):
    o = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = (i + j) / 2.0 + 1
        i = j + 1
    return r


def spearman(x, y):
    if len(x) < 4 or len(set(x)) < 2 or len(set(y)) < 2:
        return None
    rx, ry = ranks(x), ranks(y)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    sx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    sy = math.sqrt(sum((b - my) ** 2 for b in ry))
    return sum((a - mx) * (b - my) for a, b in zip(rx, ry)) / (sx * sy) if sx and sy else None


def mean(v):
    v = [x for x in v if x is not None]
    return sum(v) / len(v) if v else None


def f(x, d=2):
    return "--" if x is None else "%.*f" % (d, x)


# ----------------------------------------------------------------------------- core build
def build():
    arm_rows, role = st.load_metrics()
    meta = []
    for r in st.discover():
        rec, info, sid, cs = st.run_record(r, arm_rows, role)
        meta.append((r, rec, info, sid))
    cand_rows, _ = st.edits([(rec, info, sid, None) for _, rec, info, sid in meta])
    edit_idx = {(c["suite"], c["arm"], c["seed"], c["candidate"]): c for c in cand_rows if c.get("available")}
    fails, cands = [], []
    for r, rec, info, sid in meta:
        cap = r["cap"]
        if r["arm"] not in EDIT_ARMS or not cap:
            continue
        suite, base, arm, seed = r["suite"], r["base"], r["arm"], r["seed"]
        excl = st.exclusions(suite, arm, seed)
        tr = task_rewards(cap, excl)
        seedr = tr.get("seed", {})
        if not seedr:
            continue
        fl = seed_failures(cap, base, suite, arm, seed)
        fails += fl
        ftype = {x["task"]: x["failure_type"] for x in fl}
        led = ledger(cap)
        par = parents(cap)
        gstat = {g["id"]: g.get("status") for g in st.jl(cap / "graph.jsonl")}
        ge = st.gate_events(cap, excl)
        statuses = ge["by_cand"]
        solid = {t for t, v in seedr.items() if v >= 0.999}
        for tag, rw in tr.items():
            if tag == "seed" or "__conf" in tag:
                continue
            p = par.get(tag, "seed")
            pr = tr.get(p) or seedr
            common = [t for t in rw if t in pr]
            if not common:
                continue
            fixed = [t for t in common if pr[t] < PASS <= rw[t]]
            broke = [t for t in common if rw[t] < PASS <= pr[t]]
            val, pval = mean([rw[t] for t in common]), mean([pr[t] for t in common])
            conf = tr.get(tag + "__conf"), tr.get(tag + "__confbase")
            cdelta = None
            if conf[0] and conf[1]:
                ct = [t for t in conf[0] if t in conf[1]]
                cdelta = mean([conf[0][t] - conf[1][t] for t in ct]) if ct else None
            e = edit_idx.get((suite, arm, seed, tag), {})
            capl = {s: e.get("lines_" + s, 0) for s in CAP_SURF}
            dom = max(capl, key=capl.get) if any(capl.values()) else ("unavailable" if not e else "none")
            L = led.get(tag, {})
            st_ = statuses.get(tag)
            if st_ is None:
                gs = gstat.get(tag)
                st_ = ("promoted" if gs == "accepted" else "rejected" if gs == "rejected" else
                       "promoted" if tag == rec["champion_id"] and tag != sid else "pending")
            cands.append(dict(
                suite=suite, base_suite=base, arm=arm, seed=seed, candidate=tag, parent=p, status=st_,
                promoted=int(st_ in ("promoted", "accepted")), n_tasks=len(common), val=val, parent_val=pval,
                delta_val=(val - pval) if val is not None and pval is not None else None, fresh_confirm_delta=cdelta,
                fixed=len(fixed), broke=len(broke), net=len(fixed) - len(broke),
                ledger_fixed=len(L["fixed"]) if L else None, ledger_broke=len(L["broke"]) if L else None,
                protect_violations=sum(1 for t in solid if t in rw and rw[t] < 1.0),
                protect_size=len(solid), dominant_surface=dom,
                surfaces_touched="+".join(s for s in CAP_SURF if e.get("files_" + s)) or ("unavailable" if not e else "none"),
                lines_changed=sum(capl.values()) if e else None,
                **{"lines_" + s: capl[s] for s in CAP_SURF},
                fixed_types=dict(Counter(ftype.get(t, "was_passing_or_unlabelled") for t in fixed)),
                broke_tasks=broke, fixed_tasks=fixed))
    return meta, fails, cands


# ----------------------------------------------------------------------------- tables
def agg_attribution(cands):
    rows = []
    groups = defaultdict(list)
    for c in cands:
        groups[(c["base_suite"], c["arm"])].append(c)
    for (base, arm), cs in sorted(groups.items()):
        for s in CAP_SURF + ["(none: process/other only)"]:
            if s in CAP_SURF:
                t = [c for c in cs if c["lines_" + s] > 0]
            else:
                t = [c for c in cs if not any(c["lines_" + x] for x in CAP_SURF)]
            if not t and s != CAP_SURF[0]:
                continue
            rho = spearman([c["lines_" + s] for c in cs], [c["delta_val"] for c in cs]) if s in CAP_SURF else None
            rows.append(dict(
                base_suite=base, arm=arm, surface=s, cands_total=len(cs), cands_touching=len(t),
                promoted_touching=sum(c["promoted"] for c in t),
                promotion_rate=(sum(c["promoted"] for c in t) / len(t)) if t else None,
                mean_delta_val=mean([c["delta_val"] for c in t]),
                mean_fixed=mean([c["fixed"] for c in t]), mean_broke=mean([c["broke"] for c in t]),
                mean_lines=mean([c["lines_" + s] for c in t]) if s in CAP_SURF else None,
                spearman_lines_vs_delta=rho,
                note=("surface touched by every candidate: no contrast available" if t and len(t) == len(cs) else "")))
    return rows


def agg_failure_surface(cands, fails):
    """rows: surface-led group x failure type -> fixed counts (selection split)."""
    rows = []
    for c in cands:
        for typ, n in c["fixed_types"].items():
            rows.append(dict(base_suite=c["base_suite"], arm=c["arm"], seed=c["seed"], candidate=c["candidate"],
                             promoted=c["promoted"], dominant_surface=c["dominant_surface"],
                             surfaces_touched=c["surfaces_touched"], failure_type=typ, group=GROUPS.get(typ, typ), n_fixed=n))
    return rows


def pivot(rows, key_cols):
    p = defaultdict(Counter)
    for r in rows:
        p[tuple(r[k] for k in key_cols)][(r["failure_type"], r["promoted"])] += r["n_fixed"]
    return p


def agg_regression(cands):
    rows = []
    g = defaultdict(list)
    for c in cands:
        g[(c["base_suite"], c["arm"])].append(c)
    for (base, arm), cs in sorted(g.items()):
        pro = [c for c in cs if c["promoted"]]
        rej = [c for c in cs if c["status"] not in ("promoted", "accepted", "pending")]
        rows.append(dict(
            base_suite=base, arm=arm, candidates=len(cs), promoted=len(pro),
            broke_per_candidate=mean([c["broke"] for c in cs]), fixed_per_candidate=mean([c["fixed"] for c in cs]),
            broke_per_promotion=mean([c["broke"] for c in pro]), fixed_per_promotion=mean([c["fixed"] for c in pro]),
            net_per_promotion=mean([c["net"] for c in pro]), delta_val_per_promotion=mean([c["delta_val"] for c in pro]),
            fresh_confirm_delta_per_promotion=mean([c["fresh_confirm_delta"] for c in pro]),
            broke_per_rejected=mean([c["broke"] for c in rej]), fixed_per_rejected=mean([c["fixed"] for c in rej]),
            ledger_broke_per_candidate=mean([c["ledger_broke"] for c in cs]),
            ledger_fixed_per_candidate=mean([c["ledger_fixed"] for c in cs]),
            protect_violations_per_candidate=mean([c["protect_violations"] for c in cs]),
            protect_violations_per_promotion=mean([c["protect_violations"] for c in pro]),
            protect_size_mean=mean([c["protect_size"] for c in cs])))
    return rows


def agg_promotions(runs):
    g = defaultdict(list)
    for r in runs:
        if r["arm"] != "seed":
            g[(r["base_suite"], r["suite"], r["arm"])].append(r)
    rows = []
    for (base, suite, arm), rs in sorted(g.items(), key=lambda kv: (kv[0][0], kv[0][1], st.ARM_ORDER.index(kv[0][2]))):
        rows.append(dict(
            base_suite=base, suite=suite, arm=arm, searches=len(rs), candidates_generated=sum(r["candidates_generated"] or 0 for r in rs),
            promotions=sum(r["candidates_promoted"] or 0 for r in rs),
            promotions_per_search=mean([r["candidates_promoted"] for r in rs]),
            searches_with_promotion=sum(1 for r in rs if (r["candidates_promoted"] or 0) > 0),
            inert_searches=sum(1 for r in rs if r["returned_equals_seed"]),
            searches_without_champion=sum(1 for r in rs if r["returned_equals_seed"] is None),
            still_running=sum(1 for r in rs if r["status"] == "running"), crashed=sum(1 for r in rs if r["status"] == "crash")))
    return rows


def load_final():
    out = {}
    for b in "ABC":
        p = FINAL / b / "results_long.csv"
        if p.exists():
            d = defaultdict(dict)
            for r in st.read_csv(p):
                v = st.num(r["reward"])
                if v is not None:
                    d[(r["arm"], r["seed"])][str(r["task"])] = v
            out[b] = d
    return out


def final_gain(fin, base, arm, seed):
    d = fin.get(base)
    if not d:
        return None, None
    a = d.get((arm, str(seed)))
    s = d.get(("seed", "0")) or d.get(("seed", "s0"))
    if not a or not s:
        return None, None
    ts = [t for t in a if t in s]
    if not ts:
        return None, None
    diffs = [a[t] - s[t] for t in ts]
    se = statistics.stdev(diffs) / math.sqrt(len(diffs)) if len(diffs) > 1 else None
    return sum(diffs) / len(diffs), se


def agg_shrink_cost(runs, fin):
    shr, cost = [], []
    for r in runs:
        if r["arm"] in ("seed",) or r["suite"] not in (r["base_suite"], r["base_suite"] + "-E12"):
            continue
        sel = r["champion_gain_vs_seed"]
        fg, fse = final_gain(fin, r["base_suite"], r["arm"], r["seed"])
        inert = r["returned_equals_seed"]
        sh = None
        if sel is not None and fg is not None:
            sh = 0.0 if inert else sel - fg
        shr.append(dict(base_suite=r["base_suite"], suite=r["suite"], arm=r["arm"], seed=r["seed"], split=r["split"],
                        selection_gain=sel, final_gain=fg, final_gain_se_task=fse, shrinkage=sh,
                        returned_equals_seed=inert, status=r["status"],
                        stage="final" if fg is not None else "pending final (selection gain is search-time)"))
        usd, tok = r["optimizer_usd"], r["optimizer_noncache_tokens"]
        pts = fg * 100 if fg is not None else None
        sel_pts = sel * 100 if sel is not None else None
        cost.append(dict(
            base_suite=r["base_suite"], suite=r["suite"], arm=r["arm"], seed=r["seed"], optimizer_usd=usd,
            optimizer_noncache_tokens=tok, counted_rollouts=r["counted_rollouts"], final_gain_points=pts,
            usd_per_final_point=(usd / pts) if usd is not None and pts and pts > 0 else None,
            tokens_per_final_point=(tok / pts) if tok is not None and pts and pts > 0 else None,
            selection_gain_points=sel_pts,
            usd_per_selection_point=(usd / sel_pts) if usd is not None and sel_pts and sel_pts > 0 else None,
            tokens_per_selection_point=(tok / sel_pts) if tok is not None and sel_pts and sel_pts > 0 else None,
            stage="final" if pts is not None else "pending final (selection-point columns are search-time)"))
    return shr, cost


# ----------------------------------------------------------------------------- writers
def wcsv(path, rows):
    st.wcsv(path, rows)


def cap(stage, split_note):
    return ("Search-time, %s, not held-out." % split_note) if stage == "search" else ("Final-set results. %s" % split_note)


def tex_table(name, caption, label, header, rows, spec, wide=True):
    env = "table*" if wide else "table"
    body = "\n".join(rows)
    pre, post = ("\\resizebox{\\textwidth}{!}{%\n", "}\n") if header.count("&") >= 8 else ("", "")
    s = ("\\begin{%s}[t]\n\\centering\n\\scriptsize\n\\caption{%s}\n\\label{%s}\n%s\\begin{tabular}{%s}\n\\toprule\n%s \\\\\n\\midrule\n%s\n"
         "\\bottomrule\n\\end{tabular}\n%s\\end{%s}\n") % (env, caption, label, pre, spec, header, body, post, env)
    p = TABLES / name
    p.write_text(s)
    return p


def make_tables(attr, regr, prom, fails, cands, shr, cost):
    out = []
    T = st.tex
    lab = st.arm_label
    # (1) attribution
    rows = []
    for a in attr:
        if a["surface"] not in CAP_SURF or not a["cands_touching"]:
            continue
        rows.append("%s & %s & %s & %d/%d & %d & %s & %s & %s & %s \\\\" % (
            a["base_suite"], lab(a["arm"]), T(a["surface"]), a["cands_touching"], a["cands_total"], a["promoted_touching"],
            f(a["mean_delta_val"], 3), f(a["mean_fixed"], 1), f(a["mean_broke"], 1),
            f(a["spearman_lines_vs_delta"], 2) if a["spearman_lines_vs_delta"] is not None else "n/a"))
    out.append(tex_table("attrib_surface.tex",
        "Edit attribution by capability surface for CapEvolve candidates. " + cap("search", "own selection split of each run (A: val-40, B: opt-49, C: opt-20)") +
        " Touching/total candidates, promoted among those touching, mean selection-split change vs parent, mean tasks fixed and broken (pass = reward $\\ge$ 0.5), and Spearman correlation between lines changed on the surface and the change. n/a: surface touched by all or none, so no contrast. Selection-split changes are optimistic and noisy.",
        "tab:attrib-surface", "Suite & Arm & Surface & Touch & Promoted & $\\Delta$ sel. & Fixed & Broke & $\\rho$", rows, "@{}llllrrrrr@{}"))
    # promoted vs rejected
    rows = []
    for r in regr:
        rows.append("%s & %s & %d & %d & %s & %s & %s & %s & %s & %s \\\\" % (
            r["base_suite"], lab(r["arm"]), r["candidates"], r["promoted"], f(r["fixed_per_promotion"], 1), f(r["broke_per_promotion"], 1),
            f(r["net_per_promotion"], 1), f(r["broke_per_rejected"], 1), f(r["protect_violations_per_promotion"], 1),
            f(r["fresh_confirm_delta_per_promotion"], 3)))
    out.append(tex_table("attrib_regression.tex",
        "Regressions per promotion and net gain for CapEvolve searches. " + cap("search", "own selection split of each run") +
        " Fixed and broke: tasks moving across the pass line (reward 0.5) relative to the parent. Protect viol.: seed-solid tasks that score below 1 at the candidate. Fresh $\\Delta$: promoted candidate minus its baseline on fresh confirmation trials (Rule P only), the least biased within-search gain. Rejected: mean tasks broken by rejected candidates (candidates still pending are excluded).",
        "tab:attrib-regression", "Suite & Arm & Cands & Promoted & Fixed/prom. & Broke/prom. & Net/prom. & Broke/rej. & Protect viol./prom. & Fresh $\\Delta$/prom.", rows, "@{}llrrrrrrrr@{}"))
    # promotions
    rows = []
    for r in prom:
        rows.append("%s & %s & %d & %d & %d & %s & %d & %d & %d \\\\" % (
            T(r["suite"]), lab(r["arm"]), r["searches"], r["candidates_generated"], r["promotions"], f(r["promotions_per_search"], 2),
            r["inert_searches"], r["still_running"], r["crashed"]))
    out.append(tex_table("attrib_promotions.tex",
        "Promotions per search and inert searches (the returned artifact equals the seed), per arm. " + cap("search", "each method's own selection split") +
        " Counts are for the state of each search at the time of the run (still running = searches not yet finished, so inert counts can still change). Promotion definitions differ by method (accepted by the method's own rule) and are not comparable across methods.",
        "tab:attrib-promotions", "Suite & Arm & Searches & Cands & Promotions & Per search & Inert & Running & Crashed", rows, "@{}llrrrrrrr@{}"))
    # failure types seed
    cnt = defaultdict(Counter)
    for x in fails:
        cnt[(x["base_suite"], x["arm"])][x["group"]] += 1
    groups = ["forgotten rule or step", "tool misuse", "unexpected side effect", "output / contract", "knowledge or rule gap", "infra (unscorable)", "other"]
    rows = []
    for (base, arm), c in sorted(cnt.items()):
        tot = sum(c.values())
        rows.append("%s & %s & %d & %s \\\\" % (base, lab(arm), tot, " & ".join("%d" % c[g] for g in groups)))
    out.append(tex_table("attrib_failure_types.tex",
        "Failure types of the seed artifact's failed tasks, summed over seeds and trials-pooled tasks. " + cap("search", "failed seed tasks on each run's selection split; deterministic labels from scorer feedback, no model judge") +
        " Forgotten rule or step: a required write was never called ($\\tau^2$). Tool misuse: a write with wrong arguments. Output/contract: no output file (Suite A) or unmet communication assertion ($\\tau^2$). Knowledge or rule gap: an output file exists and fails the checks (Suite A).",
        "tab:attrib-failure-types", "Suite & Arm & Failed & " + " & ".join(g.replace("&", "\\&") for g in groups), rows, "@{}llr" + "r" * len(groups) + "@{}"))
    # surface x failure
    fs = pivot(agg_failure_surface(cands, fails), ("base_suite", "dominant_surface"))
    types = sorted({k[0] for c in fs.values() for k in c})
    rows = []
    for (base, dom), c in sorted(fs.items()):
        rows.append("%s & %s & %s \\\\" % (base, T(dom), " & ".join("%d (%d)" % (sum(v for (t, p), v in c.items() if t == ty), c[(ty, 1)]) for ty in types)))
    out.append(tex_table("attrib_surface_failure.tex",
        "Surface by failure type: seed-failed tasks fixed by CapEvolve candidates, grouped by the candidate's dominant edited surface (most changed lines). " + cap("search", "fixes counted on each run's selection split over all candidates, promoted ones in parentheses") +
        " A task counts as fixed when it fails at the parent and passes at the candidate; the count includes noise flips and is not a measure of cause. Types not listed were not fixed.",
        "tab:attrib-surface-failure", "Suite & Dominant surface & " + " & ".join(TYPE_WORDS.get(t, t.replace("_", " ").capitalize()) for t in types), rows, "@{}ll" + "r" * len(types) + "@{}"))
    # shrinkage and cost
    rows = []
    for r in shr:
        rows.append("%s & %s & %s & %s & %s & %s & %s \\\\" % (
            T(r["suite"]), lab(r["arm"]), r["seed"], f(r["selection_gain"], 3), f(r["final_gain"], 3), f(r["shrinkage"], 3),
            "yes" if r["returned_equals_seed"] else ("--" if r["returned_equals_seed"] is None else "no")))
    final_ready = any(r["final_gain"] is not None for r in shr)
    out.append(tex_table("attrib_shrinkage.tex",
        ("Selection-to-final shrinkage (selection-split gain minus final-set gain), per arm and seed. " + ("Final-set shrinkage; selection gains are search-time." if final_ready else
         "PENDING FINAL: the final-set column is empty until the final evaluation (cutoff 2026-10-13 06:00 UTC); the selection gain shown is search-time, on each method's own selection split, not held-out.") +
         " Seeds that return the seed artifact have shrinkage 0 by construction (amendment 6)."),
        "tab:attrib-shrinkage", "Suite & Arm & Seed & Sel. gain & Final gain & Shrinkage & Inert", rows, "@{}llrrrrl@{}"))
    rows = []
    g = defaultdict(list)
    for r in cost:
        g[(r["suite"], r["arm"])].append(r)
    for (suite, arm), rs in sorted(g.items(), key=lambda kv: (kv[0][0], st.ARM_ORDER.index(kv[0][1]))):
        rows.append("%s & %s & %s & %s & %s & %s & %s \\\\" % (
            T(suite), lab(arm), f(mean([r["optimizer_usd"] for r in rs]), 2), f(mean([(r["optimizer_noncache_tokens"] or 0) / 1e6 if r["optimizer_noncache_tokens"] is not None else None for r in rs]), 2),
            f(mean([r["usd_per_final_point"] for r in rs]), 2), f(mean([r["tokens_per_final_point"] / 1e3 if r["tokens_per_final_point"] else None for r in rs]), 1),
            f(mean([r["usd_per_selection_point"] for r in rs]), 3)))
    out.append(tex_table("attrib_cost_per_point.tex",
        ("Optimizer cost per point of gain. " + ("PENDING FINAL: cost per final point is empty until the final evaluation. " if not final_ready else "") +
         "USD and tokens (non-cache-read, millions) are the cost of the search so far; USD per selection point is search-time, on each method's own selection split, not held-out, and optimistic. Points are percentage points; seeds with no positive gain are left out of the per-point means."),
        "tab:attrib-cost", "Suite & Arm & Opt.\\ USD & Opt.\\ Mtok & USD/final pt & ktok/final pt & USD/sel. pt", rows, "@{}llrrrrr@{}"))
    return out


def make_figures(cands, fails, prom):
    try:
        import common
        common.style()
        import matplotlib.pyplot as plt
    except Exception as e:
        print("figures skipped:", e)
        return []
    outs = []
    fig, axes = plt.subplots(1, 3, figsize=(common.FULL_W, 2.3))
    for ax, base in zip(axes, "ABC"):
        for c in cands:
            if c["base_suite"] != base:
                continue
            col = common.ARMS[c["arm"]][1] if c["arm"] in common.ARMS else "#999999"
            ax.scatter(c["broke"], c["fixed"], s=22 if c["promoted"] else 14, color=col, marker="o" if c["promoted"] else "x",
                       alpha=0.85, linewidths=1.0)
        m = max([1] + [max(c["broke"], c["fixed"]) for c in cands if c["base_suite"] == base])
        ax.plot([0, m], [0, m], color="#999999", lw=0.6)
        ax.set_title(common.SUITE_NAME[base], fontsize=8)
        ax.set_xlabel("tasks broken")
    axes[0].set_ylabel("tasks fixed")
    fig.suptitle("Search-time, own selection split, not held-out. Circles: promoted; crosses: rejected. Above the line: net fixes.", fontsize=7, y=1.03)
    p = FIGS / "attrib_regression.pdf"
    fig.savefig(p)
    plt.close(fig)
    outs.append(p)
    groups = ["forgotten rule or step", "tool misuse", "unexpected side effect", "output / contract", "knowledge or rule gap", "infra (unscorable)", "other"]
    pal = ["#0072B2", "#D55E00", "#CC79A7", "#009E73", "#E69F00", "#999999", "#000000"]
    fig, ax = plt.subplots(figsize=(common.COL_W * 1.3, 2.2))
    tot = defaultdict(Counter)
    for x in fails:
        if x["arm"] in ("hc", "hcstock"):
            tot[x["base_suite"]][x["group"]] += 1
    bot = [0] * 3
    for g, c in zip(groups, pal):
        v = [100.0 * tot[b][g] / max(1, sum(tot[b].values())) for b in "ABC"]
        if any(v):
            ax.bar(range(3), v, bottom=bot, color=c, label=g, width=0.6)
            bot = [a + b for a, b in zip(bot, v)]
    ax.set_xticks(range(3))
    ax.set_xticklabels(["A", "B", "C"])
    ax.set_ylabel("% of failed seed tasks")
    ax.legend(fontsize=5.5, frameon=False, loc="center left", bbox_to_anchor=(1.0, 0.5))
    ax.set_title("Search-time, selection split, not held-out", fontsize=7)
    ax.grid(axis="x", visible=False)
    p = FIGS / "attrib_failure_types.pdf"
    fig.savefig(p)
    plt.close(fig)
    outs.append(p)
    return outs


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    meta, fails, cands = build()
    runs = [rec for _, rec, _, _ in meta]
    fin = load_final()
    attr, regr, prom = agg_attribution(cands), agg_regression(cands), agg_promotions(runs)
    shr, cost = agg_shrink_cost(runs, fin)
    fsurf = agg_failure_surface(cands, fails)
    wcsv(OUT / "candidates.csv", [{k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in c.items()} for c in cands])
    wcsv(OUT / "seed_failures.csv", fails)
    sf = Counter((x["base_suite"], x["arm"], x["failure_type"], x["group"], x["category"]) for x in fails)
    wcsv(OUT / "seed_failure_summary.csv", [dict(base_suite=k[0], arm=k[1], failure_type=k[2], group=k[3], category=k[4], n=v) for k, v in sorted(sf.items())])
    wcsv(OUT / "attribution_by_surface.csv", attr)
    wcsv(OUT / "surface_x_failure.csv", fsurf)
    wcsv(OUT / "regression_by_arm.csv", regr)
    wcsv(OUT / "promotions_by_arm.csv", prom)
    wcsv(OUT / "shrinkage.csv", shr)
    wcsv(OUT / "cost_per_point.csv", cost)
    tp = make_tables(attr, regr, prom, fails, cands, shr, cost)
    fp = make_figures(cands, fails, prom)
    (OUT / "attrib.json").write_text(json.dumps(dict(
        stage="final" if fin else "search-time", final_suites_present=sorted(fin), attribution=attr, regression=regr,
        promotions=prom, shrinkage=shr, cost=cost), indent=1, default=str))
    write_md(attr, regr, prom, fails, cands, shr, cost, bool(fin))
    print("wrote", OUT)
    for p in tp + fp:
        print("wrote", p)


def write_md(attr, regr, prom, fails, cands, shr, cost, fin):
    L = ["# Attribution analyses", "",
         "Stage: %s. All search-time numbers are on each run's own selection split, not held-out; selection-split gains are optimistic and noisy (A has one trial per task), and fixed/broke counts include noise flips. Final-set columns stay empty until `final_eval/{A,B,C}/results_long.csv` exists." % ("final data present" if fin else "search-time only, final pending"),
         "", "## Promotions per search and inert searches", "", "| suite | arm | searches | cands | promotions | per search | inert | running | crashed |", "|---|---|---|---|---|---|---|---|---|"]
    for r in prom:
        L.append("| %s | %s | %d | %d | %d | %s | %d | %d | %d |" % (r["suite"], r["arm"], r["searches"], r["candidates_generated"], r["promotions"], f(r["promotions_per_search"], 2), r["inert_searches"], r["still_running"], r["crashed"]))
    L += ["", "## Regressions (CapEvolve arms)", "", "| suite | arm | cands | promoted | fixed/prom | broke/prom | net/prom | broke/rejected | protect viol/prom | fresh confirm delta/prom |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in regr:
        L.append("| %s | %s | %d | %d | %s | %s | %s | %s | %s | %s |" % (r["base_suite"], r["arm"], r["candidates"], r["promoted"], f(r["fixed_per_promotion"], 1), f(r["broke_per_promotion"], 1), f(r["net_per_promotion"], 1), f(r["broke_per_rejected"], 1), f(r["protect_violations_per_promotion"], 1), f(r["fresh_confirm_delta_per_promotion"], 3)))
    L += ["", "## Seed failure types (groups)", "", "| suite | arm | type | n |", "|---|---|---|---|"]
    sf = Counter((x["base_suite"], x["arm"], x["failure_type"]) for x in fails)
    for k, v in sorted(sf.items()):
        L.append("| %s | %s | %s | %d |" % (k[0], k[1], k[2], v))
    L += ["", "## Attribution by surface", "", "| suite | arm | surface | touching/total | promoted | mean delta | fixed | broke | rho | note |", "|---|---|---|---|---|---|---|---|---|---|"]
    for a in attr:
        if a["surface"] in CAP_SURF and a["cands_touching"]:
            L.append("| %s | %s | %s | %d/%d | %d | %s | %s | %s | %s | %s |" % (a["base_suite"], a["arm"], a["surface"], a["cands_touching"], a["cands_total"], a["promoted_touching"], f(a["mean_delta_val"], 3), f(a["mean_fixed"], 1), f(a["mean_broke"], 1), f(a["spearman_lines_vs_delta"], 2), a["note"]))
    L += ["", "## Shrinkage and cost per point", "", "See shrinkage.csv and cost_per_point.csv (final columns empty until the final evaluation)."]
    (OUT / "summary.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
