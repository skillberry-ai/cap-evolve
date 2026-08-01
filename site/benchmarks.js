const RAW = "https://raw.githubusercontent.com/skillberry-ai/cap-evolve/benchmark-history";
const GH_API = "https://api.github.com/repos/skillberry-ai/cap-evolve";
// Tier is matched GENERICALLY: the workflow's TIERS list grows (smoke, pilot, full, …) and
// hardcoding it here silently hides new tiers from the live panel — a `pilot` run was
// invisible while it was executing. The bench allowlist stays explicit so unrelated jobs
// ("plan legs", "aggregate history") never match.
const JOB_RE = /^([a-z][a-z0-9-]*) \/ (tau2|swebench|skillsbench|spreadsheetbench)$/;
let RECORDS = [], sortKey = "date", sortDir = -1;

const $ = (s) => document.querySelector(s);
const fmt = (v, d = 3) => (typeof v === "number" ? v.toFixed(d) : "—");
// Wall-time seconds as minutes+seconds (e.g. 14m48s), matching metrics.py's _fmt_duration.
const fmtDuration = (v) => {
  if (typeof v !== "number") return "—";
  const total = Math.round(v);
  const m = Math.floor(total / 60), s = total % 60;
  return m ? `${m}m${String(s).padStart(2, "0")}s` : `${s}s`;
};
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
// Elapsed time since a job started, e.g. "3m07s" or "1h05m" (no seconds once past an hour).
const fmtElapsed = (ms) => {
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600), m = Math.floor((total % 3600) / 60), s = total % 60;
  if (h) return `${h}h${String(m).padStart(2, "0")}m`;
  return m ? `${m}m${String(s).padStart(2, "0")}s` : `${s}s`;
};

async function loadRunning() {
  const panel = $("#running-now");
  try {
    // Filter on the terminal state ("completed") rather than enumerating non-terminal
    // ones: GitHub reports runs/jobs that haven't finished as "queued", "pending", or
    // "in_progress" depending on matrix position and concurrency-group state, and a
    // 6-way matrix (tier × bench) run can sit in any mix of those before its legs start.
    // per_page=100 (the API max): PR-triggered benchmark runs churn fast (labeled event,
    // several per PR) and can push a long-running manual dispatch — the thing this panel
    // most needs to surface — past a small page before it finishes. Cheap to raise: only
    // non-completed runs in the page trigger a follow-up jobs fetch below.
    const runsResp = await fetch(`${GH_API}/actions/workflows/benchmarks.yml/runs?per_page=100`);
    if (!runsResp.ok) throw new Error(String(runsResp.status));
    const { workflow_runs: runs } = await runsResp.json();
    const active = (runs || []).filter((r) => r.status !== "completed");
    const items = [];
    for (const run of active) {
      const jobsResp = await fetch(`${GH_API}/actions/runs/${run.id}/jobs`);
      if (!jobsResp.ok) continue;
      const { jobs } = await jobsResp.json();
      for (const job of jobs || []) {
        if (job.status === "completed") continue;
        const m = JOB_RE.exec(job.name);
        if (!m) continue;
        items.push({
          runId: run.id, tier: m[1], bench: m[2], jobUrl: job.html_url,
          startedAt: job.started_at, live: job.status === "in_progress",
        });
      }
    }
    renderRunning(items);
  } catch (e) {
    panel.hidden = true;
  }
}

function renderRunning(items) {
  const panel = $("#running-now");
  const list = $("#running-list");
  if (!items.length) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  const sorted = [...items].sort((a, b) => (a.live === b.live ? 0 : a.live ? -1 : 1));
  list.innerHTML = sorted.map((it) => {
    if (!it.live) {
      return `<li><span class="badge badge-amber">queued</span>
        <a href="${esc(it.jobUrl)}" target="_blank" rel="noopener">${esc(it.tier)} / ${esc(it.bench)}</a></li>`;
    }
    const dataBase = encodeURIComponent(`${RAW}/live/${it.runId}__${it.tier}-${it.bench}/data`);
    return `<li><span class="badge badge-accent">live</span>
      <a href="${esc(it.jobUrl)}" target="_blank" rel="noopener">${esc(it.tier)} / ${esc(it.bench)}</a>
      <span class="elapsed" data-started="${esc(it.startedAt)}"></span>
      — <a href="./dashboard-ui/index.html?dataBase=${dataBase}#/runs/run_suite" target="_blank" rel="noopener">Watch live</a></li>`;
  }).join("");
  updateElapsed();
}

// Ticks independently of loadRunning's poll interval so the elapsed time reads smoothly
// between polls, instead of jumping only when a new snapshot of "in progress" jobs loads.
function updateElapsed() {
  document.querySelectorAll("#running-list .elapsed").forEach((el) => {
    const started = el.dataset.started;
    if (!started) return;
    el.textContent = `· ${fmtElapsed(Date.now() - Date.parse(started))}`;
  });
}

async function load() {
  try {
    const [recs, meta] = await Promise.all([
      fetch(`${RAW}/benchmarks.json?t=${Date.now()}`).then((r) => r.json()),
      fetch(`${RAW}/meta.json?t=${Date.now()}`).then((r) => r.json()).catch(() => null),
    ]);
    RECORDS = Array.isArray(recs) ? recs : [];
    if (meta && meta.updated) {
      $("#updated").textContent = `· last updated ${new Date(meta.updated).toLocaleString()}`;
    }
    render();
  } catch (e) {
    $("#error").hidden = false;
  }
}

// current time window (ms epoch), recomputed each render() from the Time filter.
let WIN = { start: null, end: null };

function timeWindow() {
  const v = $("#f-time").value;
  if (v === "all") return { start: null, end: null };
  if (v === "custom") {
    const f = $("#f-from").value, t = $("#f-to").value;
    return { start: f ? new Date(f).getTime() : null, end: t ? new Date(t).getTime() : null };
  }
  return { start: Date.now() - Number(v) * 1000, end: null }; // last N seconds
}

function passes(r) {
  const b = $("#f-bench").value, s = $("#f-source").value, c = $("#f-conc").value;
  const t = $("#f-tier").value;
  const q = $("#f-q").value.toLowerCase();
  const ts = Date.parse(r.date);
  if (WIN.start != null && !(ts >= WIN.start)) return false;
  if (WIN.end != null && !(ts <= WIN.end)) return false;
  if (b && r.bench !== b) return false;
  if (t && (r.tier || "smoke") !== t) return false;
  if (s === "pr" && r.event !== "pull_request") return false;
  if (s === "manual" && r.event === "pull_request") return false;
  if (c && r.conclusion !== c) return false;
  if (q) {
    const hay = `${r.branch || ""} ${(r.tasks || []).map((t) => t.task).join(" ")}`.toLowerCase();
    if (!hay.includes(q)) return false;
  }
  return true;
}

function sortVal(r, k) {
  if (k === "reward") return r.suite ? r.suite.reward_opt : -1;
  if (k === "eval_usd") return r.suite ? (r.suite.eval_usd ?? -1) : -1;
  if (k === "optimizer_usd") return r.suite ? r.suite.optimizer_usd : -1;
  if (k === "latency_s") return r.suite
    ? (r.suite.eval_seconds ?? 0) + (r.suite.optimizer_seconds ?? 0) : -1;
  if (k === "tier") return r.tier || "smoke";
  return r[k] ?? "";
}

function render() {
  WIN = timeWindow();
  const rows = RECORDS.filter(passes).sort((a, b) => {
    const x = sortVal(a, sortKey), y = sortVal(b, sortKey);
    return (x < y ? -1 : x > y ? 1 : 0) * sortDir;
  });
  const tb = $("#rows");
  tb.innerHTML = "";
  const empty = $("#empty");
  if (rows.length === 0) {
    empty.hidden = false;
    empty.innerHTML = RECORDS.length
      ? "No runs match the current filters — try widening the time range."
      : "No runs recorded yet — trigger the suite (add a <code>benchmark-smoke</code> label to a PR, or Actions → Benchmarks).";
  } else {
    empty.hidden = true;
  }
  for (const r of rows) {
    const tr = document.createElement("tr");
    tr.className = "run-row";
    const reward = r.suite ? `${fmt(r.suite.reward_base)} → ${fmt(r.suite.reward_opt)}` : "—";
    const evalUsd = r.suite && r.suite.eval_usd != null ? `$${fmt(r.suite.eval_usd, 4)}` : "—";
    const optUsd = r.suite ? `$${fmt(r.suite.optimizer_usd, 4)}` : "—";
    const latency = r.suite && (r.suite.eval_seconds != null || r.suite.optimizer_seconds != null)
      ? fmtDuration((r.suite.eval_seconds ?? 0) + (r.suite.optimizer_seconds ?? 0)) : "—";
    const ui = r.has_ui
      ? `<a href="./benchmark-ui/runs/${encodeURIComponent(r.run_id)}__${esc(r.tier || "smoke")}-${encodeURIComponent(r.bench)}/ui/index.html#/runs/run_suite" target="_blank" rel="noopener">Open UI</a>`
      : `<span class="muted">—</span>`;
    // Source column: link to the PR when set, else to `summary_url` when set
    // (per-run detail page for local/manual runs). Backward compatible: records
    // without `pr` or `summary_url` render as plain text.
    const src = r.pr
      ? `<a href="https://github.com/skillberry-ai/cap-evolve/pull/${encodeURIComponent(r.pr)}">${esc(r.source)}</a>`
      : r.summary_url
        ? `<a href="${esc(r.summary_url)}" target="_blank" rel="noopener">${esc(r.source || "—")}</a>`
        : esc(r.source || "—");
    const badge = `<span class="badge ${esc(r.conclusion)}">${esc(r.conclusion)}</span>`;
    const date = esc((r.date || "").replace("T", " ").replace("Z", ""));
    const tier = esc(r.tier || "smoke");
    tr.innerHTML = `<td><a href="${esc(r.run_url)}">${date}</a></td>
      <td>${src}</td><td>${esc(r.bench)}</td><td>${tier}</td><td>${r.iterations ?? "—"}</td>
      <td>${r.trials ?? "—"}</td>
      <td>${reward}</td><td>${evalUsd}</td><td>${optUsd}</td><td>${latency}</td>
      <td><code>${esc(r.agent_model || "—")}</code></td><td><code>${esc(r.optimizer_model || "—")}</code></td>
      <td>${badge}</td><td>${ui}</td>`;
    tb.appendChild(tr);

    const detail = document.createElement("tr");
    detail.className = "detail-row";
    detail.hidden = true;
    detail.innerHTML = `<td colspan="14">${taskTable(r.tasks || [])}${stepsTable(r.steps || [])}</td>`;
    tb.appendChild(detail);

    tr.addEventListener("click", (e) => {
      if (e.target.tagName !== "A") detail.hidden = !detail.hidden;
    });
  }
}

function taskTable(tasks) {
  if (!tasks.length) return `<em class="muted">no per-task metrics</em>`;
  // Latency/cost are never per-task in a whole-suite optimization (every task is
  // scored together in the same eval call) — see stepsTable() for that.
  const head = `<tr><th>task</th><th>reward base→opt</th></tr>`;
  const body = tasks.map((t) => `<tr><td><code>${esc(t.task)}</code></td>
    <td>${fmt(t.reward_baseline)} → ${fmt(t.reward_opt)}</td></tr>`).join("");
  return `<table class="detail">${head}${body}</table>`;
}

function stepsTable(steps) {
  if (!steps.length) return `<em class="muted">no per-iteration metrics</em>`;
  const head = `<tr><th>phase</th><th>iter</th><th>candidate</th><th>accepted</th>` +
    `<th>reward</th><th>optimizer $</th><th>optimizer time</th><th>eval $</th><th>eval time</th></tr>`;
  const body = steps.map((s) => `<tr><td>${esc(s.phase)}</td><td>${s.iter ?? "—"}</td>
    <td><code>${esc(s.candidate)}</code></td>
    <td>${s.accepted == null ? "—" : (s.accepted ? "✅" : "❌")}</td>
    <td>${fmt(s.reward)}</td>
    <td>$${fmt(s.optimizer_usd, 4)}</td><td>${fmtDuration(s.optimizer_seconds)}</td>
    <td>$${fmt(s.eval_usd, 4)}</td><td>${fmtDuration(s.eval_seconds)}</td></tr>`).join("");
  return `<table class="detail">${head}${body}</table>`;
}

document.querySelectorAll("#runs thead th").forEach((th) =>
  th.addEventListener("click", () => {
    const k = th.dataset.k;
    if (!k) return;
    sortDir = sortKey === k ? -sortDir : -1;
    sortKey = k;
    render();
  })
);
["f-time", "f-from", "f-to", "f-bench", "f-tier", "f-source", "f-conc", "f-q"].forEach((id) =>
  $("#" + id).addEventListener("input", render)
);
// reveal the custom datetime inputs only when Time = "Custom…"
$("#f-time").addEventListener("change", () => {
  const custom = $("#f-time").value === "custom";
  $("#f-from-wrap").hidden = !custom;
  $("#f-to-wrap").hidden = !custom;
});
load();
loadRunning();
// 5 minutes, matching live_push.sh's own snapshot cadence — polling more often buys
// nothing (the data can't have changed) and risks exhausting the unauthenticated GitHub
// API's 60 req/hour rate limit (this call + one /jobs lookup per in-progress run, every
// poll), which made the panel silently disappear (loadRunning's catch just hides it).
setInterval(loadRunning, 300000);
setInterval(updateElapsed, 1000);
