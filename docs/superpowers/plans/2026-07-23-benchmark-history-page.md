# Benchmark CI History Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a durable, sortable/filterable HTML table of every `ci/benchmarks` execution (PR + manual runs) on the GitHub Pages site.

**Architecture:** Each benchmark job writes a small `runmeta.json` alongside its existing `metrics.jsonl` (both captured in the uploaded artifact). A single `aggregate` job (`needs: [bench]`, `if: always()`) turns each into one per-`(run×bench)` record via `record.py`, pushes the records to a `benchmark-history` orphan branch, and regenerates `benchmarks.json` + `meta.json`. A static `site/benchmarks.html` fetches that JSON at load and renders rollup rows that expand to per-task detail.

**Tech Stack:** Python 3.12 stdlib (no new deps), GitHub Actions, vanilla HTML/CSS/JS (no build step, matches existing `site/`), pytest for unit tests.

## Global Constraints

- No new Python dependencies — stdlib only (`json`, `pathlib`, `argparse`).
- No JS framework / build step — one plain `site/benchmarks.js`, reuse `site/style.css` + existing `.nav`/`.page-*` classes.
- Data model: one record per `(run × benchmark)`, `schema: 1`, exactly as in the design spec `docs/superpowers/specs/2026-07-23-benchmark-ci-history-page-design.md`.
- Suite rollup math must match `ci/benchmarks/lib/metrics.py` `table()`: `reward_base`=mean of numeric `reward_baseline`, `reward_opt`=mean of numeric `reward_opt`, `flips`=count of `flipped`, `n`=len(tasks), `optimizer_usd`=sum of `optimizer_usd`.
- `suite` is `null` unless the job `conclusion == "success"` and metrics exist.
- History branch name: `benchmark-history`. Raw URL the page fetches: `https://raw.githubusercontent.com/skillberry-ai/cap-evolve/benchmark-history/benchmarks.json`.
- Run `python3` (repo venv `.venv` or `.venv-e2e`); tests via `python3 -m pytest`.

---

### Task 1: `record.py` — build one record + aggregate records

**Files:**
- Create: `ci/benchmarks/lib/record.py`
- Test: `ci/benchmarks/lib/test_record.py`

**Interfaces:**
- Produces:
  - `build_record(metrics_jsonl: pathlib.Path, runmeta: dict) -> dict` — returns a record dict with keys `schema, tasks, suite` merged over `runmeta`.
  - `rollup(tasks: list[dict]) -> dict | None` — the suite rollup, or `None` if no numeric rewards.
  - `aggregate(records_dir: pathlib.Path, now: str) -> tuple[list[dict], dict]` — `(records_newest_first, meta)`.
  - CLI: `record.py build <metrics.jsonl> --runmeta <runmeta.json>` → prints record JSON to stdout; `record.py aggregate <records_dir> --now <iso> --out <dir>` → writes `<dir>/benchmarks.json` + `<dir>/meta.json`.

- [ ] **Step 1: Write the failing tests**

```python
# ci/benchmarks/lib/test_record.py
import json
from pathlib import Path
import record  # same dir; run pytest from ci/benchmarks/lib

TASK_OK = {
    "bench": "tau2", "task": "35",
    "reward_baseline": 0.0, "reward_opt": 1.0, "reward_delta": 1.0, "flipped": True,
    "latency_baseline_s": 10.0, "latency_opt_s": 11.0,
    "cost_baseline_usd": 0.0, "cost_opt_runner_usd": 0.0,
    "optimizer_usd": 0.05, "optimizer_tokens": 0, "optimizer_seconds": 0, "iterations": 1,
}
TASK2 = {**TASK_OK, "task": "37", "reward_baseline": 0.0, "reward_opt": 0.0,
         "flipped": False, "optimizer_usd": 0.03}

def _write_jsonl(p: Path, rows):
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")

def test_rollup_math():
    r = record.rollup([TASK_OK, TASK2])
    assert r == {"reward_base": 0.0, "reward_opt": 0.5, "flips": 1, "n": 2, "optimizer_usd": 0.08}

def test_rollup_empty_is_none():
    assert record.rollup([]) is None

def test_build_success(tmp_path):
    m = tmp_path / "metrics.jsonl"; _write_jsonl(m, [TASK_OK, TASK2])
    meta = {"run_id": 1, "bench": "tau2", "conclusion": "success", "date": "2026-07-23T00:00:00Z"}
    rec = record.build_record(m, meta)
    assert rec["schema"] == 1
    assert rec["run_id"] == 1 and rec["bench"] == "tau2"
    assert len(rec["tasks"]) == 2
    assert rec["suite"]["flips"] == 1 and rec["suite"]["n"] == 2

def test_build_failed_run_has_null_suite(tmp_path):
    m = tmp_path / "metrics.jsonl"; _write_jsonl(m, [TASK_OK])
    meta = {"run_id": 2, "bench": "tau2", "conclusion": "failure", "date": "d"}
    rec = record.build_record(m, meta)
    assert rec["suite"] is None
    assert len(rec["tasks"]) == 1

def test_build_missing_metrics(tmp_path):
    meta = {"run_id": 3, "bench": "swebench", "conclusion": "success", "date": "d"}
    rec = record.build_record(tmp_path / "nope.jsonl", meta)
    assert rec["tasks"] == [] and rec["suite"] is None

def test_aggregate_sorts_and_counts(tmp_path):
    d = tmp_path / "records"; d.mkdir()
    (d / "1__tau2.json").write_text(json.dumps({"run_id": 1, "bench": "tau2", "date": "2026-07-20T00:00:00Z"}))
    (d / "2__tau2.json").write_text(json.dumps({"run_id": 2, "bench": "tau2", "date": "2026-07-22T00:00:00Z"}))
    recs, meta = record.aggregate(d, now="2026-07-23T09:00:00Z")
    assert [r["run_id"] for r in recs] == [2, 1]  # newest first
    assert meta == {"count": 2, "runs": 2, "updated": "2026-07-23T09:00:00Z"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ci/benchmarks/lib && python3 -m pytest test_record.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'record'`.

- [ ] **Step 3: Write `record.py`**

```python
#!/usr/bin/env python3
"""Build & aggregate benchmark-history records for the CI history page.

  record.py build <metrics.jsonl> --runmeta <runmeta.json>   # -> record JSON on stdout
  record.py aggregate <records_dir> --now <iso> --out <dir>  # -> benchmarks.json + meta.json
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

SCHEMA = 1


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def rollup(tasks: list[dict]) -> dict | None:
    rb = [t["reward_baseline"] for t in tasks if _num(t.get("reward_baseline"))]
    ro = [t["reward_opt"] for t in tasks if _num(t.get("reward_opt"))]
    if not (rb and ro):
        return None
    return {
        "reward_base": round(sum(rb) / len(rb), 6),
        "reward_opt": round(sum(ro) / len(ro), 6),
        "flips": sum(1 for t in tasks if t.get("flipped")),
        "n": len(tasks),
        "optimizer_usd": round(sum(t.get("optimizer_usd") or 0 for t in tasks), 6),
    }


def build_record(metrics_jsonl: Path, runmeta: dict) -> dict:
    tasks: list[dict] = []
    if metrics_jsonl.exists():
        for line in metrics_jsonl.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                tasks.append(json.loads(line))
    rec = dict(runmeta)
    rec["schema"] = SCHEMA
    rec["tasks"] = tasks
    rec["suite"] = rollup(tasks) if runmeta.get("conclusion") == "success" else None
    return rec


def aggregate(records_dir: Path, now: str) -> tuple[list[dict], dict]:
    recs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(records_dir.glob("*.json"))]
    recs.sort(key=lambda r: (r.get("date", ""), r.get("run_id", 0)), reverse=True)
    meta = {"count": len(recs), "runs": len({r.get("run_id") for r in recs}), "updated": now}
    return recs, meta


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("metrics"); b.add_argument("--runmeta", required=True)
    a = sub.add_parser("aggregate"); a.add_argument("records_dir"); a.add_argument("--now", required=True); a.add_argument("--out", required=True)
    ns = ap.parse_args(argv[1:])
    if ns.cmd == "build":
        runmeta = json.loads(Path(ns.runmeta).read_text(encoding="utf-8"))
        print(json.dumps(build_record(Path(ns.metrics), runmeta)))
        return 0
    if ns.cmd == "aggregate":
        recs, meta = aggregate(Path(ns.records_dir), ns.now)
        out = Path(ns.out); out.mkdir(parents=True, exist_ok=True)
        (out / "benchmarks.json").write_text(json.dumps(recs, indent=2), encoding="utf-8")
        (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ci/benchmarks/lib && python3 -m pytest test_record.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add ci/benchmarks/lib/record.py ci/benchmarks/lib/test_record.py
git commit -m "feat(bench): record.py — build + aggregate benchmark-history records"
```

---

### Task 2: Emit `runmeta.json` per bench job + `aggregate` job in the workflow

**Files:**
- Modify: `.github/workflows/benchmarks.yml` (add a runmeta step to the `bench` job; add a new `aggregate` job)
- Modify: `ci/benchmarks/README.md` (document the `benchmark-history` branch + one-time bootstrap)

**Interfaces:**
- Consumes: `ci/benchmarks/lib/record.py` (`build`, `aggregate` CLI) from Task 1; the existing `run_suite.sh` output dir `ci/benchmarks/.work/suite_<bench>/` containing `metrics.jsonl`.
- Produces: on the `benchmark-history` branch, `records/<run_id>__<bench>.json`, `benchmarks.json`, `meta.json`.

- [ ] **Step 1: Bootstrap the orphan branch (one-time, manual)**

Run locally (documented in README, done once by a maintainer):

```bash
git switch --orphan benchmark-history
mkdir -p records
echo '[]' > benchmarks.json
echo '{"count":0,"runs":0,"updated":null}' > meta.json
git add records benchmarks.json meta.json 2>/dev/null; : > records/.gitkeep; git add records/.gitkeep benchmarks.json meta.json
git commit -m "chore: init benchmark-history branch"
git push origin benchmark-history
git switch feat/benchmark-history-page
```

- [ ] **Step 2: Add a `runmeta.json` step to the `bench` job**

In `.github/workflows/benchmarks.yml`, inside the `bench` job, **after** the "Run suite" step, add (this step runs even on failure so failed runs are still recorded):

```yaml
      - name: Write run metadata
        if: steps.gate.outputs.run == 'true' && always()
        run: |
          out="$GITHUB_WORKSPACE/ci/benchmarks/.work/suite_${{ matrix.bench }}"
          mkdir -p "$out"
          if [ "${{ github.event_name }}" = "pull_request" ]; then
            source="PR #${{ github.event.pull_request.number }}"; pr="${{ github.event.pull_request.number }}"
          else
            source="manual (${{ github.ref_name }})"; pr="null"
          fi
          cat > "$out/runmeta.json" <<JSON
          {
            "run_id": ${{ github.run_id }},
            "run_url": "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}",
            "bench": "${{ matrix.bench }}",
            "event": "${{ github.event_name }}",
            "source": "$source",
            "pr": $pr,
            "branch": "${{ github.head_ref || github.ref_name }}",
            "sha": "${{ github.event.pull_request.head.sha || github.sha }}",
            "date": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
            "iterations": ${ITERATIONS:-1},
            "agent_model": "aws/gpt-oss-120b",
            "optimizer_model": "claude-opus-4-8",
            "conclusion": "${{ job.status }}"
          }
          JSON
          cat "$out/runmeta.json"
```

Note: `${{ job.status }}` at this late `always()` step reflects success/failure of prior steps. The `upload-artifact` step already globs `ci/benchmarks/.work/suite_<bench>/**`, so `runmeta.json` and `metrics.jsonl` are both included.

- [ ] **Step 3: Add the `aggregate` job**

Append to `.github/workflows/benchmarks.yml` under `jobs:` (sibling of `bench`):

```yaml
  aggregate:
    name: aggregate history
    needs: [bench]
    if: always()
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4              # for ci/benchmarks/lib/record.py

      - name: Download all benchmark artifacts
        uses: actions/download-artifact@v4
        with:
          path: _artifacts
          pattern: benchmarks-*

      - name: Build records
        run: |
          mkdir -p _new_records
          for d in _artifacts/benchmarks-*; do
            [ -d "$d" ] || continue
            bench="$(basename "$d" | sed 's/^benchmarks-//')"
            suite="$d/suite_$bench"
            rm="$suite/runmeta.json"; metrics="$suite/metrics.jsonl"
            [ -f "$rm" ] || { echo "no runmeta for $bench, skipping"; continue; }
            rid="$(python3 -c "import json,sys;print(json.load(open('$rm'))['run_id'])")"
            python3 ci/benchmarks/lib/record.py build "$metrics" --runmeta "$rm" \
              > "_new_records/${rid}__${bench}.json"
            echo "built _new_records/${rid}__${bench}.json"
          done
          ls -la _new_records || true

      - name: Push to benchmark-history (single writer, with rebase-retry)
        run: |
          [ -n "$(ls -A _new_records 2>/dev/null)" ] || { echo "no records to push"; exit 0; }
          git config --global user.name "skillberry-bot"
          git config --global user.email "actions@github.com"
          for attempt in 1 2 3 4 5; do
            rm -rf _hist
            git clone --depth 1 --branch benchmark-history \
              "https://x-access-token:${{ github.token }}@github.com/${{ github.repository }}.git" _hist || {
                echo "branch missing — bootstrap it per ci/benchmarks/README.md"; exit 1; }
            mkdir -p _hist/records
            cp _new_records/*.json _hist/records/
            python3 ci/benchmarks/lib/record.py aggregate _hist/records \
              --now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --out _hist
            cd _hist
            git add records benchmarks.json meta.json
            git commit -m "bench: record run ${{ github.run_id }}" || { echo "nothing to commit"; exit 0; }
            if git push origin benchmark-history; then echo "pushed"; exit 0; fi
            echo "push race, retrying ($attempt)"; cd ..; sleep 3
          done
          echo "failed to push after retries"; exit 1
```

- [ ] **Step 4: Document the branch in the README**

Add to `ci/benchmarks/README.md` under a new `## Benchmark history page` section:

```markdown
## Benchmark history page

Every run appends a per-`(run×bench)` record to the **`benchmark-history`** orphan branch
(`records/<run_id>__<bench>.json`) and regenerates `benchmarks.json` + `meta.json` there
(single-writer `aggregate` job → no races). The Pages page `site/benchmarks.html` fetches
`benchmarks.json` at load. Bootstrap the branch once:

    git switch --orphan benchmark-history
    mkdir -p records && : > records/.gitkeep
    echo '[]' > benchmarks.json
    echo '{"count":0,"runs":0,"updated":null}' > meta.json
    git add records/.gitkeep benchmarks.json meta.json
    git commit -m "chore: init benchmark-history branch" && git push origin benchmark-history
```

- [ ] **Step 5: Validate locally (workflow can't be unit-tested)**

Simulate the aggregate logic against a fixture that mimics a downloaded artifact:

Run:
```bash
cd /tmp && rm -rf aggchk && mkdir -p aggchk/records
printf '%s\n' '{"bench":"tau2","task":"35","reward_baseline":0.0,"reward_opt":0.0,"flipped":false,"optimizer_usd":0.02}' > aggchk/metrics.jsonl
printf '%s' '{"run_id":999,"bench":"tau2","conclusion":"success","date":"2026-07-23T10:00:00Z"}' > aggchk/runmeta.json
python3 "$OLDPWD/ci/benchmarks/lib/record.py" build aggchk/metrics.jsonl --runmeta aggchk/runmeta.json > aggchk/records/999__tau2.json
python3 "$OLDPWD/ci/benchmarks/lib/record.py" aggregate aggchk/records --now 2026-07-23T10:01:00Z --out aggchk
cat aggchk/benchmarks.json aggchk/meta.json
```
Expected: `benchmarks.json` is a 1-element array whose record has `suite.n == 1`; `meta.json` shows `count: 1, runs: 1`.

Also lint the YAML:
Run: `python3 -c "import yaml,sys; yaml.safe_load(open('.github/workflows/benchmarks.yml'))" && echo "YAML OK"`
Expected: `YAML OK`. (If PyYAML is absent, `pip install pyyaml` in the venv or skip — GitHub validates on push.)

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/benchmarks.yml ci/benchmarks/README.md
git commit -m "feat(bench): aggregate job pushes run records to benchmark-history branch"
```

---

### Task 3: `site/benchmarks.html` + `site/benchmarks.js` + nav link

**Files:**
- Create: `site/benchmarks.html`
- Create: `site/benchmarks.js`
- Modify: `site/index.html`, `site/results.html`, `site/getting-started.html`, `site/architecture.html`, `site/agent-orchestration.html`, `site/optimize-your-own.html`, `site/adapter-templates.html` (add the nav link to each page's `.nav-links`)
- Create: `site/benchmarks.fixture.json` (local eyeball fixture; not deployed data)

**Interfaces:**
- Consumes: the record schema from Task 1 (`benchmarks.json` = array of records; each has `source, pr, run_url, bench, date, iterations, conclusion, suite{reward_base,reward_opt,flips,n,optimizer_usd}, tasks[]`).
- Produces: a deployed page at `/benchmarks.html`.

- [ ] **Step 1: Create `site/benchmarks.html`**

Mirror the `<head>`/nav/footer of `site/results.html` (same `style.css`, Inter font, `.nav`). Body:

```html
<main class="page doc">
  <h1>Benchmark runs</h1>
  <p class="lead">Every <code>ci/benchmarks</code> execution (PR &amp; manual). Rollup rows expand to per-task detail.
    <span id="updated" class="muted"></span></p>

  <div class="filters">
    <label>Benchmark <select id="f-bench"><option value="">all</option><option>tau2</option><option>swebench</option><option>skillsbench</option></select></label>
    <label>Source <select id="f-source"><option value="">all</option><option value="pr">PR</option><option value="manual">manual</option></select></label>
    <label>Result <select id="f-conc"><option value="">all</option><option>success</option><option>failure</option><option>cancelled</option></select></label>
    <label>Search <input id="f-q" type="search" placeholder="branch or task…"></label>
  </div>

  <table id="runs">
    <thead><tr>
      <th data-k="date">Date</th><th data-k="source">Source</th><th data-k="bench">Bench</th>
      <th data-k="iterations">Iters</th><th data-k="reward">Reward base→opt</th>
      <th data-k="flips">Flips</th><th data-k="optimizer_usd">Optimizer $</th><th data-k="conclusion">Result</th>
    </tr></thead>
    <tbody id="rows"></tbody>
  </table>
  <p id="empty" class="muted" hidden>No runs recorded yet.</p>
  <p id="error" class="muted" hidden>Couldn't load benchmark history.</p>
</main>
<script src="benchmarks.js"></script>
```

- [ ] **Step 2: Create `site/benchmarks.js`**

```javascript
const RAW = "https://raw.githubusercontent.com/skillberry-ai/cap-evolve/benchmark-history";
let RECORDS = [], sortKey = "date", sortDir = -1;

const $ = (s) => document.querySelector(s);
const fmt = (v, d = 3) => (typeof v === "number" ? v.toFixed(d) : "—");

async function load() {
  try {
    const [recs, meta] = await Promise.all([
      fetch(`${RAW}/benchmarks.json?t=${Date.now()}`).then((r) => r.json()),
      fetch(`${RAW}/meta.json?t=${Date.now()}`).then((r) => r.json()).catch(() => null),
    ]);
    RECORDS = Array.isArray(recs) ? recs : [];
    if (meta && meta.updated) $("#updated").textContent = `· last updated ${new Date(meta.updated).toLocaleString()}`;
    render();
  } catch (e) {
    $("#error").hidden = false;
  }
}

function passes(r) {
  const b = $("#f-bench").value, s = $("#f-source").value, c = $("#f-conc").value, q = $("#f-q").value.toLowerCase();
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
  const tb = $("#rows"); tb.innerHTML = "";
  $("#empty").hidden = rows.length > 0;
  for (const r of rows) {
    const tr = document.createElement("tr");
    tr.className = "run-row";
    const reward = r.suite ? `${fmt(r.suite.reward_base)} → ${fmt(r.suite.reward_opt)}` : "—";
    const flips = r.suite ? `${r.suite.flips}/${r.suite.n}` : "—";
    const usd = r.suite ? `$${fmt(r.suite.optimizer_usd, 4)}` : "—";
    const src = r.pr ? `<a href="https://github.com/skillberry-ai/cap-evolve/pull/${r.pr}">${r.source}</a>` : r.source;
    const badge = `<span class="badge ${r.conclusion}">${r.conclusion}</span>`;
    tr.innerHTML = `<td><a href="${r.run_url}">${(r.date || "").replace("T", " ").replace("Z", "")}</a></td>
      <td>${src}</td><td>${r.bench}</td><td>${r.iterations ?? "—"}</td>
      <td>${reward}</td><td>${flips}</td><td>${usd}</td><td>${badge}</td>`;
    tb.appendChild(tr);
    const detail = document.createElement("tr");
    detail.className = "detail-row"; detail.hidden = true;
    detail.innerHTML = `<td colspan="8">${taskTable(r.tasks || [])}</td>`;
    tb.appendChild(detail);
    tr.addEventListener("click", (e) => { if (e.target.tagName !== "A") detail.hidden = !detail.hidden; });
  }
}

function taskTable(tasks) {
  if (!tasks.length) return `<em class="muted">no per-task metrics</em>`;
  const head = `<tr><th>task</th><th>reward base→opt</th><th>flip</th><th>latency (s)</th><th>runner $</th><th>opt $</th><th>iters</th></tr>`;
  const body = tasks.map((t) => `<tr><td><code>${t.task}</code></td>
    <td>${fmt(t.reward_baseline)} → ${fmt(t.reward_opt)}</td>
    <td>${t.flipped ? "✅" : "—"}</td>
    <td>${fmt(t.latency_baseline_s, 1)} → ${fmt(t.latency_opt_s, 1)}</td>
    <td>$${fmt(t.cost_opt_runner_usd, 4)}</td><td>$${fmt(t.optimizer_usd, 4)}</td>
    <td>${t.iterations ?? "—"}</td></tr>`).join("");
  return `<table class="detail">${head}${body}</table>`;
}

document.querySelectorAll("#runs thead th").forEach((th) =>
  th.addEventListener("click", () => {
    const k = th.dataset.k; if (!k) return;
    sortDir = sortKey === k ? -sortDir : -1; sortKey = k; render();
  })
);
["f-bench", "f-source", "f-conc", "f-q"].forEach((id) => $("#" + id).addEventListener("input", render));
load();
```

- [ ] **Step 3: Add table/badge/filter styles**

Append to `site/style.css`:

```css
.filters { display: flex; flex-wrap: wrap; gap: 1rem; margin: 1rem 0; }
.filters label { display: flex; flex-direction: column; font-size: .8rem; color: #555; gap: .25rem; }
.run-row { cursor: pointer; }
.run-row:hover { background: #f6f8fa; }
.detail-row > td { background: #fafbfc; padding: .5rem 1rem; }
table.detail { width: 100%; font-size: .85rem; }
.badge { padding: .1rem .5rem; border-radius: 999px; font-size: .75rem; font-weight: 600; }
.badge.success { background: #d5f5e3; color: #1e7a46; }
.badge.failure { background: #fbdcdc; color: #a12; }
.badge.cancelled { background: #eee; color: #666; }
.muted { color: #777; font-weight: 400; }
```

- [ ] **Step 4: Add the nav link to every page**

In each `site/*.html`, inside `<div class="nav-links">`, add after the Results link:

```html
      <a href="benchmarks.html">Benchmark runs</a>
```
On `benchmarks.html` itself give it `class="active"`.

- [ ] **Step 5: Eyeball with a local fixture**

Create `site/benchmarks.fixture.json` with two records (one `success` with 2 tasks, one `failure` with `suite: null`), temporarily point `RAW` fetch at `./benchmarks.fixture.json`, then:

Run: `cd site && python3 -m http.server 8099`
Open: `http://localhost:8099/benchmarks.html`
Verify: rows render, clicking a row expands the per-task table, sort headers reorder, filters narrow the list, the failed run shows a red badge with no metrics. Then revert `RAW` to the live URL and delete/keep the fixture (keep it — it's a test aid, not deployed data).

Expected: all interactions work; empty/error states show when data is absent.

- [ ] **Step 6: Commit**

```bash
git add site/benchmarks.html site/benchmarks.js site/style.css site/benchmarks.fixture.json site/*.html
git commit -m "feat(site): benchmark runs history page (sortable/filterable, expandable rows)"
```

---

## Self-Review

**1. Spec coverage:**
- Forward-only, per-(run×bench) records → Task 1 (`build_record`) + Task 2 (runmeta + aggregate). ✓
- Rollup + expandable per-task rows → Task 3 (`render` + `taskTable`). ✓
- Approach 1: history branch, single aggregator, client fetch → Task 2 (aggregate job, orphan branch) + Task 3 (`RAW` fetch + cache-buster). ✓
- PR + manual runs labelled; failures visible → Task 2 runmeta `source`/`conclusion`, `if: always()`; Task 3 badge + null-suite handling. ✓
- Sort/filter (bench, source, conclusion, search) → Task 3 filters. ✓
- No new deps / no build step / reuse style → Global Constraints + Task 3. ✓
- README bootstrap of orphan branch → Task 2 Step 1 + Step 4. ✓
- meta.json "last updated" → Task 1 `aggregate` + Task 3 `#updated`. ✓
- Error handling (missing metrics, failed job, empty history, fetch failure) → Task 1 `build_record` guards, Task 3 `#empty`/`#error`. ✓

**2. Placeholder scan:** No TBD/TODO; every code step shows full code; every run step shows the command + expected output. ✓

**3. Type consistency:** `rollup`/`build_record`/`aggregate` signatures identical across Task 1 definition and Task 2 CLI usage. `benchmarks.json` = array of records; `meta.json` = `{count,runs,updated}` — consumed exactly by Task 3 `load()`. Record fields used in JS (`source, pr, run_url, bench, date, iterations, conclusion, suite.*, tasks[].*`) all match Task 1 output + `metrics.py` task shape. ✓

## Notes / risks flagged during planning

- The `aggregate` job pushes with `GITHUB_TOKEN` (`contents: write`). If branch/org policy blocks it, the maintainer will relax it (admin available). Fork PRs are already blocked by the existing fork guard, so the token has write access on same-repo runs.
- `${{ job.status }}` in the runmeta step reflects the job outcome at that late `always()` step (post-Run-suite). Cancelled jobs may skip the step; those simply won't produce a record (acceptable — no data to show).
