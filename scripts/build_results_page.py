#!/usr/bin/env python3
"""Build ui/results.html for the spreadsheet-history branch: one self-contained, sortable page for the issue #895 comparison.

Reads only files that are on the branch, so it can be re-run from a checkout of it:
  results/full_table.json      per-seed train / val / test (from results_table.py)
  results/usage.json           per-seed tokens, calls and wall time (from usage_table.py)
  results/<arm>/s<seed>/test/summary.json   the paired test window
Usage: build_results_page.py <branch_root>        (writes <branch_root>/ui/results.html)
No external assets: styles and script are inline; data is embedded as JSON.
"""
import json, math, sys
from pathlib import Path

ROOT = Path(sys.argv[1])
T = json.loads((ROOT / "results/full_table.json").read_text())
U = json.loads((ROOT / "results/usage.json").read_text())
NAME = {"capevolve": "CapEvolve v1", "capevolve_v2": "CapEvolve v2", "skillopt": "SkillOpt", "trace2skill": "Trace2Skill",
        "meta_harness": "Meta-Harness", "evoskill": "EvoSkill", "gepa": "GEPA", "gepa_full": "GEPA-full", "miprov2": "MIPROv2",
        "wikiskill": "WikiSkill", "ace": "ACE"}
INERT = {"trace2skill|0", "evoskill|0", "ace|2"}
MIN_N = 10   # train/val cells need at least this many tasks scored for both seed and champion


def pair(z):
    return None if not z or z[2] < MIN_N else {"seed": z[0], "champ": z[1], "n": z[2]}


seeds = []
for k, (val, train, test) in T.items():
    arm, s = k.split("|")
    summ = json.loads((ROOT / f"results/{arm}/s{s}/test/summary.json").read_text())
    u = U.get(k, {})
    seeds.append({
        "arm": arm, "system": NAME[arm], "seed": int(s), "inert": k in INERT, "cev": arm.startswith("capevolve"),
        "train": None if arm == "ace" else pair(train), "val": None if arm == "ace" else pair(val),
        "test_seed": test["seed_test_mean"], "test_champ": test["champion_test_mean"], "gain": test["paired_delta"],
        "se": test["paired_se_cr1"], "ci": test["ci95"], "n": test["n_tasks_paired"],
        "infra_missing": summ.get("infra_missing_trials"), "cand_err": summ.get("candidate_error_trials"),
        "opt_in": u.get("search_optimizer", {}).get("prompt"), "opt_out": u.get("search_optimizer", {}).get("completion"),
        "opt_calls": u.get("search_optimizer", {}).get("calls"),
        "agent_in": u.get("search_agent", {}).get("prompt"), "agent_out": u.get("search_agent", {}).get("completion"),
        "agent_calls": u.get("search_agent", {}).get("calls"),
        "search_h": u.get("search_wall_h"), "test_h": u.get("test_wall_h"),
    })


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def sd(xs):
    xs = [x for x in xs if x is not None]
    if len(xs) < 2:
        return None
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


systems = []
for arm, nm in NAME.items():
    rs = sorted([r for r in seeds if r["arm"] == arm], key=lambda r: r["seed"])
    if not rs:
        continue

    def mp(key):
        z = [r[key] for r in rs if r[key]]
        return None if not z else {"seed": mean([q["seed"] for q in z]), "champ": mean([q["champ"] for q in z]),
                                   "seeds": len(z), "of": len(rs)}

    systems.append({
        "arm": arm, "system": nm, "cev": arm.startswith("capevolve"), "seeds": len(rs),
        "train": mp("train"), "val": mp("val"),
        "test_seed": mean([r["test_seed"] for r in rs]), "test_champ": mean([r["test_champ"] for r in rs]),
        "gain": mean([r["gain"] for r in rs]), "gain_sd": sd([r["gain"] for r in rs]),
        "per_seed": [{"seed": r["seed"], "gain": r["gain"], "inert": r["inert"]} for r in rs],
        "opt_out": mean([r["opt_out"] for r in rs]), "opt_in": mean([r["opt_in"] for r in rs]),
        "agent_in": mean([r["agent_in"] for r in rs]), "agent_out": mean([r["agent_out"] for r in rs]),
        "search_h": mean([r["search_h"] for r in rs]), "search_h_n": sum(1 for r in rs if r["search_h"] is not None),
        "test_h": mean([r["test_h"] for r in rs]),
    })

DATA = json.dumps({"systems": systems, "seeds": seeds}, separators=(",", ":"))

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SpreadsheetBench verified_400 — cap-evolve vs 9 optimizers (issue #895)</title>
<style>
:root{--bg:#07090d;--soft:#0d1117;--border:#1e2733;--ink:#e6edf3;--body:#c2ccd8;--muted:#8b98a9;--accent:#3b82f6;--accent-ink:#93c5fd;
--amber:#f59e0b;--amber-soft:rgba(245,158,11,.14);--good:#4ade80;--bad:#f87171;--radius:12px}
[data-theme=light]{--bg:#fff;--soft:#f7f8fb;--border:#e4e7ec;--ink:#0f1620;--body:#333a45;--muted:#5b6472;--accent:#2563eb;--accent-ink:#1d4ed8;
--amber:#b45309;--amber-soft:rgba(180,83,9,.10);--good:#15803d;--bad:#b91c1c}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--body);font:15px/1.55 "Fira Sans",system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1240px;margin:0 auto;padding:28px 22px 60px}
h1{color:var(--ink);font-size:26px;margin:0 0 6px}h2{color:var(--ink);font-size:19px;margin:34px 0 8px}
p{margin:6px 0 10px}.muted{color:var(--muted)}a{color:var(--accent-ink)}code{font-family:"Fira Code",ui-monospace,monospace;font-size:13px}
.top{display:flex;justify-content:space-between;align-items:flex-start;gap:16px}
button{background:var(--soft);color:var(--ink);border:1px solid var(--border);border-radius:8px;padding:5px 11px;cursor:pointer;font:inherit;font-size:13px}
button.on{border-color:var(--accent);color:var(--accent-ink)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:10px;margin:16px 0}
.card{background:var(--soft);border:1px solid var(--border);border-radius:var(--radius);padding:11px 13px}
.card b{display:block;color:var(--ink);font-size:20px}.card span{font-size:12.5px;color:var(--muted)}
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:10px 0}
.wrap{overflow-x:auto;border:1px solid var(--border);border-radius:var(--radius)}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{padding:7px 10px;border-bottom:1px solid var(--border);text-align:right;white-space:nowrap}
th:first-child,td:first-child,th.l,td.l{text-align:left}
th{position:sticky;top:0;background:var(--soft);color:var(--ink);font-weight:600;cursor:pointer;user-select:none}
th .ar{color:var(--muted);font-size:11px}th.sorted .ar{color:var(--accent-ink)}
tbody tr:hover{background:var(--soft)}tr.cev td.sys{color:var(--amber);font-weight:700}
tr.cev{background:var(--amber-soft)}
.pos{color:var(--good)}.neg{color:var(--bad)}.dim{color:var(--muted)}
.gbar{display:inline-block;height:9px;border-radius:3px;background:var(--accent);vertical-align:middle;margin-right:6px}
.det td{background:var(--soft);text-align:left;white-space:normal}.det table{font-size:12.5px}
.note{border-left:3px solid var(--accent);background:var(--soft);padding:9px 13px;border-radius:0 8px 8px 0;margin:12px 0;font-size:14px}
.note.warn{border-left-color:var(--amber)}
footer{margin-top:40px;font-size:12.5px;color:var(--muted)}
</style>
</head>
<body>
<main>
<div class="top">
 <div>
  <h1>SpreadsheetBench <code>verified_400</code>: cap-evolve vs 9 optimizers</h1>
  <p class="muted">Issue <a href="https://github.com/skillberry-ai/cap-evolve/issues/895">#895</a> ·
   Gemma-4-31B agent · GLM-5.3 optimizer · R = 2,160 rollouts per search · k = 3 trials · 3 seeds per system · 280 sealed test tasks</p>
 </div>
 <button id="theme" type="button">Light</button>
</div>

<div class="cards" id="cards"></div>

<div class="note"><b>How to read the gain.</b> Each test window scores the frozen champion and the seed on the same 280 tasks in the
 same window; the gain is the mean of champion − seed over tasks. Use it rather than the absolute score: the seed's own score ranged
 0.592–0.657 across the 33 windows. Ranks 4–8 lie within 0.010 of each other while one system's seeds differ by an SD of
 0.016–0.081, so with 3 seeds only the top and bottom groups are separated. Validation is optimistic: champions were chosen on it.</div>

<h2>One row per system</h2>
<p class="muted">Means over the system's 3 seeds. Click a column to sort; click a row for its seeds.</p>
<div class="bar"><span class="muted">Sort:</span>
 <button data-sort="gain" class="on">By test gain</button><button data-sort="test_champ">By absolute test score</button></div>
<div class="wrap"><table id="sys"><thead></thead><tbody></tbody></table></div>

<h2>Every seed</h2>
<p class="muted">33 searches. * = inert seed: the search returned the seed itself as champion.</p>
<div class="bar"><label class="muted"><input type="checkbox" id="hideinert"> hide inert seeds</label>
 <label class="muted">System <select id="fsys"><option value="">all</option></select></label></div>
<div class="wrap"><table id="seed"><thead></thead><tbody></tbody></table></div>

<h2>Cost and time</h2>
<div class="note warn">Tokens and times come from the experiment's own metering gateway. <b>No dollar figures</b>: there is no
 price list for these endpoints, so a cost in $ would have to be invented. Optimizer tokens are GLM-5.3 tokens; agent tokens are
 Gemma tokens. <b>Search time is elapsed wall time</b>, not effort: it includes periods when searches were frozen to relieve the model
 endpoint, and retry waits after endpoint failures, so it mostly reflects how the run was scheduled. GEPA s2 has no search time (its
 resumed job left no end marker). Test time is the window's elapsed time from first to last episode (1,680 episodes), so a window
 that was paused and resumed counts its pause; CapEvolve v1 s0's window, for example, ran in several resumed stretches.</div>

<p class="muted">Means over each system's 3 seeds. Click a column to sort.</p>
<div class="wrap"><table id="cost"><thead></thead><tbody></tbody></table></div>

<footer>Generated by <code>scripts/build_results_page.py</code> from <code>results/full_table.json</code>,
 <code>results/usage.json</code> and the <code>results/&lt;system&gt;/s&lt;seed&gt;/test/summary.json</code> files on this branch.
 Every headline number can be re-derived from <code>per_task_test_scores.json</code>.</footer>
</main>
<script>
const D = __DATA__;
const f3 = v => v == null ? "—" : v.toFixed(3);
const sg = v => v == null ? "—" : (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(3);
const cls = v => v == null ? "dim" : v > 0.0005 ? "pos" : v < -0.0005 ? "neg" : "dim";
const M = v => v == null ? "—" : v >= 1e6 ? (v/1e6).toFixed(1) + "M" : v >= 1e3 ? (v/1e3).toFixed(0) + "k" : String(Math.round(v));
const H = v => v == null ? "—" : v.toFixed(1) + " h";
const pr = (p, note) => !p ? '<span class="dim">n/a</span>' :
  `${f3(p.seed)} → ${f3(p.champ)} <span class="${cls(p.champ - p.seed)}">(${sg(p.champ - p.seed)})</span>` +
  (note && p.of && p.seeds < p.of ? ` <span class="dim">${p.seeds} of ${p.of}</span>` : "") +
  (p.n != null && note === undefined ? ` <span class="dim">n=${p.n}</span>` : "");
const maxGain = Math.max(...D.systems.map(s => s.gain));

const SYS_COLS = [
  ["#", null, false], ["System", "system", true], ["Train (80)", "train", true], ["Val (40)", "val", true],
  ["Test: seed → champion", "test_champ", false], ["Mean gain", "gain", false], ["SD", "gain_sd", false],
  ["Gain per seed (s0 / s1 / s2)", null, true]];
const COST_COLS = [
  ["System", "system", true], ["Mean gain", "gain", false], ["Search wall time", "search_h", false], ["Test window wall time", "test_h", false],
  ["Optimizer tokens in", "opt_in", false], ["Optimizer tokens out", "opt_out", false], ["Agent tokens in (search)", "agent_in", false],
  ["Agent tokens out (search)", "agent_out", false]];
const SEED_COLS = [
  ["System", "system", true], ["Seed", "seed", false], ["Train (80)", "train", true], ["Val (40)", "val", true],
  ["Test seed", "test_seed", false], ["Test champion", "test_champ", false], ["Gain", "gain", false], ["95% CI", null, false],
  ["Tasks", "n", false], ["Infra-missing trials", "infra_missing", false]];

let sysSort = {key: "gain", dir: -1}, seedSort = {key: "gain", dir: -1}, open = null;
const val = (r, k) => { const v = r[k]; return v && typeof v === "object" ? v.champ - v.seed : v; };
function sorter(s) { return (a, b) => { const x = val(a, s.key), y = val(b, s.key);
  if (x == null && y == null) return 0; if (x == null) return 1; if (y == null) return -1;
  return (typeof x === "string" ? x.localeCompare(y) : x - y) * s.dir; }; }
function head(el, cols, st, onSort) {
  el.innerHTML = "<tr>" + cols.map(([t, k, l]) => `<th class="${l ? "l" : ""} ${st.key === k ? "sorted" : ""}" data-k="${k || ""}">${t}` +
    (k ? ` <span class="ar">${st.key === k ? (st.dir < 0 ? "▼" : "▲") : "↕"}</span>` : "") + "</th>").join("") + "</tr>";
  el.querySelectorAll("th[data-k]").forEach(th => { if (!th.dataset.k) return; th.onclick = () => onSort(th.dataset.k); });
}
function renderSys() {
  const t = document.getElementById("sys"); head(t.tHead, SYS_COLS, sysSort, k => {
    sysSort = {key: k, dir: sysSort.key === k ? -sysSort.dir : (k === "system" ? 1 : -1)}; syncButtons(); renderSys(); });
  const rows = [...D.systems].sort(sorter(sysSort));
  t.tBodies[0].innerHTML = rows.map((s, i) => {
    const per = s.per_seed.map(p => `<span class="${cls(p.gain)}">${sg(p.gain)}${p.inert ? "*" : ""}</span>`).join(" / ");
    const w = Math.max(2, Math.round(70 * Math.max(0, s.gain) / maxGain));
    let h = `<tr class="${s.cev ? "cev" : ""}" data-arm="${s.arm}" style="cursor:pointer"><td>${i + 1}</td><td class="l sys">${s.system}</td>` +
      `<td class="l">${pr(s.train, true)}</td><td class="l">${pr(s.val, true)}</td>` +
      `<td>${f3(s.test_seed)} → <b>${f3(s.test_champ)}</b></td>` +
      `<td><span class="gbar" style="width:${w}px"></span><b class="${cls(s.gain)}">${sg(s.gain)}</b></td><td>${f3(s.gain_sd)}</td>` +
      `<td class="l">${per}</td></tr>`;
    if (open === s.arm) {
      const sd = D.seeds.filter(r => r.arm === s.arm).sort((a, b) => a.seed - b.seed);
      h += `<tr class="det"><td colspan="${SYS_COLS.length}"><table><tr><th class="l">Seed</th><th>Test seed → champion</th><th>Gain [95% CI]</th>` +
        `<th>Tasks</th><th>Infra-missing trials</th><th>Search time</th><th>Optimizer out</th></tr>` +
        sd.map(r => `<tr><td class="l">s${r.seed}${r.inert ? " *" : ""}</td><td>${f3(r.test_seed)} → ${f3(r.test_champ)}</td>` +
          `<td class="${cls(r.gain)}">${sg(r.gain)} [${sg(r.ci[0])}, ${sg(r.ci[1])}]</td><td>${r.n}</td><td>${r.infra_missing ?? "—"}</td>` +
          `<td>${H(r.search_h)}</td><td>${M(r.opt_out)}</td></tr>`).join("") + "</table></td></tr>";
    }
    return h; }).join("");
  t.tBodies[0].querySelectorAll("tr[data-arm]").forEach(tr => tr.onclick = () => { open = open === tr.dataset.arm ? null : tr.dataset.arm; renderSys(); });
}
function renderSeed() {
  const t = document.getElementById("seed"); head(t.tHead, SEED_COLS, seedSort, k => {
    seedSort = {key: k, dir: seedSort.key === k ? -seedSort.dir : (k === "system" ? 1 : -1)}; renderSeed(); });
  const hide = document.getElementById("hideinert").checked, fs = document.getElementById("fsys").value;
  const rows = D.seeds.filter(r => (!hide || !r.inert) && (!fs || r.arm === fs)).sort(sorter(seedSort));
  t.tBodies[0].innerHTML = rows.map(r => `<tr class="${r.cev ? "cev" : ""}"><td class="l sys">${r.system}</td><td>s${r.seed}${r.inert ? " *" : ""}</td>` +
    `<td class="l">${pr(r.train)}</td><td class="l">${pr(r.val)}</td><td>${f3(r.test_seed)}</td><td><b>${f3(r.test_champ)}</b></td>` +
    `<td><b class="${cls(r.gain)}">${sg(r.gain)}</b></td><td>[${sg(r.ci[0])}, ${sg(r.ci[1])}]</td><td>${r.n}</td><td>${r.infra_missing ?? "—"}</td>` +
    `</tr>`).join("");
}
let costSort = {key: "gain", dir: -1};
function renderCost() {
  const t = document.getElementById("cost"); head(t.tHead, COST_COLS, costSort, k => {
    costSort = {key: k, dir: costSort.key === k ? -costSort.dir : (k === "system" ? 1 : -1)}; renderCost(); });
  const rows = [...D.systems].sort(sorter(costSort));
  t.tBodies[0].innerHTML = rows.map(s => `<tr class="${s.cev ? "cev" : ""}"><td class="l sys">${s.system}</td>` +
    `<td><b class="${cls(s.gain)}">${sg(s.gain)}</b></td>` +
    `<td>${H(s.search_h)}${s.search_h_n < s.seeds ? ' <span class="dim">(' + s.search_h_n + ' of ' + s.seeds + ' seeds)</span>' : ""}</td>` +
    `<td>${H(s.test_h)}</td><td>${M(s.opt_in)}</td><td>${M(s.opt_out)}</td><td>${M(s.agent_in)}</td><td>${M(s.agent_out)}</td></tr>`).join("");
}
function syncButtons() { document.querySelectorAll("[data-sort]").forEach(b => b.classList.toggle("on", b.dataset.sort === sysSort.key)); }
document.querySelectorAll("[data-sort]").forEach(b => b.onclick = () => { sysSort = {key: b.dataset.sort, dir: -1}; syncButtons(); renderSys(); });
document.getElementById("hideinert").onchange = renderSeed; document.getElementById("fsys").onchange = renderSeed;
document.getElementById("fsys").innerHTML += D.systems.map(s => `<option value="${s.arm}">${s.system}</option>`).join("");
const best = [...D.systems].sort((a, b) => b.gain - a.gain)[0], cevs = D.systems.filter(s => s.cev);
document.getElementById("cards").innerHTML = [
  [D.seeds.length + " searches", "11 systems × 3 seeds, all finished"],
  [best.system + " " + sg(best.gain), "highest mean test gain"],
  [cevs.map(s => s.system.replace("CapEvolve ", "") + " " + sg(s.gain)).join(" · "), "CapEvolve mean test gain"],
  [D.seeds.filter(r => r.inert).length + " inert seeds", "champion = seed (Trace2Skill s0, EvoSkill s0, ACE s2)"]]
  .map(([b, s]) => `<div class="card"><b>${b}</b><span>${s}</span></div>`).join("");
const th = document.getElementById("theme");
th.onclick = () => { const l = document.documentElement.dataset.theme === "light"; document.documentElement.dataset.theme = l ? "" : "light"; th.textContent = l ? "Light" : "Dark"; };
renderSys(); renderSeed(); renderCost();
</script>
</body>
</html>
"""
out = ROOT / "ui" / "results.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(HTML.replace("__DATA__", DATA))
print(f"wrote {out} ({out.stat().st_size} bytes), {len(systems)} systems, {len(seeds)} seeds")
