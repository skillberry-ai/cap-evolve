const RAW = "https://raw.githubusercontent.com/skillberry-ai/cap-evolve/benchmark-history";
let RECORDS = [], sortKey = "date", sortDir = -1;

const $ = (s) => document.querySelector(s);
const fmt = (v, d = 3) => (typeof v === "number" ? v.toFixed(d) : "—");
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

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

function passes(r) {
  const b = $("#f-bench").value, s = $("#f-source").value, c = $("#f-conc").value;
  const q = $("#f-q").value.toLowerCase();
  if (b && r.bench !== b) return false;
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
  if (k === "flips") return r.suite ? r.suite.flips : -1;
  if (k === "optimizer_usd") return r.suite ? r.suite.optimizer_usd : -1;
  return r[k] ?? "";
}

function render() {
  const rows = RECORDS.filter(passes).sort((a, b) => {
    const x = sortVal(a, sortKey), y = sortVal(b, sortKey);
    return (x < y ? -1 : x > y ? 1 : 0) * sortDir;
  });
  const tb = $("#rows");
  tb.innerHTML = "";
  $("#empty").hidden = rows.length > 0;
  for (const r of rows) {
    const tr = document.createElement("tr");
    tr.className = "run-row";
    const reward = r.suite ? `${fmt(r.suite.reward_base)} → ${fmt(r.suite.reward_opt)}` : "—";
    const flips = r.suite ? `${r.suite.flips}/${r.suite.n}` : "—";
    const usd = r.suite ? `$${fmt(r.suite.optimizer_usd, 4)}` : "—";
    const src = r.pr
      ? `<a href="https://github.com/skillberry-ai/cap-evolve/pull/${encodeURIComponent(r.pr)}">${esc(r.source)}</a>`
      : esc(r.source || "—");
    const badge = `<span class="badge ${esc(r.conclusion)}">${esc(r.conclusion)}</span>`;
    const date = esc((r.date || "").replace("T", " ").replace("Z", ""));
    tr.innerHTML = `<td><a href="${esc(r.run_url)}">${date}</a></td>
      <td>${src}</td><td>${esc(r.bench)}</td><td>${r.iterations ?? "—"}</td>
      <td>${reward}</td><td>${flips}</td><td>${usd}</td><td>${badge}</td>`;
    tb.appendChild(tr);

    const detail = document.createElement("tr");
    detail.className = "detail-row";
    detail.hidden = true;
    detail.innerHTML = `<td colspan="8">${taskTable(r.tasks || [])}</td>`;
    tb.appendChild(detail);

    tr.addEventListener("click", (e) => {
      if (e.target.tagName !== "A") detail.hidden = !detail.hidden;
    });
  }
}

function taskTable(tasks) {
  if (!tasks.length) return `<em class="muted">no per-task metrics</em>`;
  const head = `<tr><th>task</th><th>reward base→opt</th><th>flip</th><th>latency (s)</th>` +
    `<th>runner $</th><th>opt $</th><th>iters</th></tr>`;
  const body = tasks.map((t) => `<tr><td><code>${esc(t.task)}</code></td>
    <td>${fmt(t.reward_baseline)} → ${fmt(t.reward_opt)}</td>
    <td>${t.flipped ? "✅" : "—"}</td>
    <td>${fmt(t.latency_baseline_s, 1)} → ${fmt(t.latency_opt_s, 1)}</td>
    <td>$${fmt(t.cost_opt_runner_usd, 4)}</td><td>$${fmt(t.optimizer_usd, 4)}</td>
    <td>${t.iterations ?? "—"}</td></tr>`).join("");
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
["f-bench", "f-source", "f-conc", "f-q"].forEach((id) =>
  $("#" + id).addEventListener("input", render)
);
load();
