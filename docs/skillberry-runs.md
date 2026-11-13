# Benchmark-run data in `skillberry-runs`

[`skillberry-runs`](https://github.com/skillberry-runs) is the GitHub org that holds cap-evolve's
benchmark results, kept separate from the code repo `skillberry-ai/cap-evolve`. At its center is a
public **dashboard**, <https://skillberry-runs.github.io/dashboard/>. It shows every run as a row and
gives each benchmark that has write-ups its own section. Behind the dashboard:

- **Run data** lives in the dashboard repo: one JSON record per run.
- **Write-ups for each benchmark** live in a private repo per benchmark, all with the same layout.
  The dashboard renders them into that benchmark's section.

This page describes how the data is organized, gives the procedure for adding a **new benchmark**
so it is laid out like the existing ones and appears on the dashboard, and covers what is still
being migrated. It is accurate as of 2026-11-13.

## Contents

- [The org at a glance](#the-org-at-a-glance)
- [The dashboard](#the-dashboard)
- [The per-benchmark repo layout](#the-per-benchmark-repo-layout)
- [Adding a new benchmark](#adding-a-new-benchmark)
- [Adding runs to an existing benchmark](#adding-runs-to-an-existing-benchmark)
- [Migration status](#migration-status)
- [Existing documentation, compared](#existing-documentation-compared)

## The org at a glance

| repo | visibility | holds | on the dashboard as | came from (cap-evolve branch) |
|---|---|---|---|---|
| [`dashboard`](https://github.com/skillberry-runs/dashboard) | **public** | `records/` (one JSON per run, 211 today), `notes/`, the site, the deploy workflow | the runs table (`/`), `/notes/` | `benchmark-history` (records only, a snapshot) + cap-evolve `site/` |
| [`parsec`](https://github.com/skillberry-runs/parsec) | private | Parsec v1–v6 experiments | `/parsec/` | `parsec-history` (full history) |
| [`spreadsheetbench`](https://github.com/skillberry-runs/spreadsheetbench) | private | SpreadsheetBench `verified_400`, cap-evolve vs 9 optimizers | `/spreadsheetbench/` | `spreadsheet-history` (full history) |
| [`skillsbench`](https://github.com/skillberry-runs/skillsbench) | private | SkillsBench sweeps, evolved skills, insights | not yet; still rendered on the cap-evolve site (`skillberry-ai.github.io/cap-evolve/skillsbench/`) | `skillsbench-history` (full history) |

Each repo was checked against the branch it came from. The parsec and spreadsheetbench trees just
before their migration commit, and the skillsbench tree two commits back, are byte-identical to the
branch tips. The migration commits only edit `README.md` and `.gitignore` (plus a workflow swap in
skillsbench). The dashboard's `records/` matches `benchmark-history:records/` file for file.

None of these repos contains library code. Adapters, scoring and CI stay on cap-evolve `main`. Raw
run directories (`.capevolve/`, per-rollout ledgers, simulator logs) are deliberately kept out of all
of them.

## The dashboard

### Repo layout

```
records/<id>.json          one record per (run × benchmark × tier): the source of truth for the runs table
notes/runs/<name>.md       hand-written notes for locally-run records (linked from a row's Source)
site/index.html            the runs page (nav bar lists the benchmark sections)
site/benchmarks.js, js/, style.css, assets/
scripts/record.py          copy of cap-evolve ci/benchmarks/lib/record.py; cap-evolve owns the record schema
scripts/build_reports.py   renders a per-benchmark repo into site/<bench>/
.github/workflows/pages.yml
```

### Run records

- **Filename:** `<id>.json`, where `id` is `<run_id>__<tier>-<bench>`.
  - **CI runs:** `run_id` is the cap-evolve `benchmarks.yml` Actions run id, e.g.
    `40192418195__smoke-tau2_sierra_blackbox.json`.
  - **Local runs published by hand:** use a synthetic date-plus-sequence id, `YYYYMMDDNNN`, e.g.
    `20261019001__v6-parsec.json`. Older records use variants of this:
    `20260908001__local-20260814-parsec-v1-pilot.json`, `manual__full-rh-swebench-v4.json`.
  - The tier in the name keeps `smoke` and `full` of one benchmark from overwriting each other.
    Re-publishing under the same name corrects a record.
- **Content** (`schema: 1`):
  - Run metadata: `run_id`, `run_url`, `bench`, `tier`, `event`, `source`, `pr`, `branch`, `sha`,
    `date`, `iterations`, `trials`.
  - Models: requested vs. actually served, and the provider that served them (`ibm-rits` /
    `ibm-ete-int` / `ibm-ete`).
  - Settings and outcome: `gate_k_se`, `algorithm`, `warm_seed`, `conclusion`, `has_ui`.
  - Results: per-task `tasks`, per-iteration `steps`, and the `suite` rollup. The rollup is `null`
    unless `conclusion == "success"`, and also when no task has paired numeric baseline and
    optimized rewards.
  - An optional `summary_url`.
- **`bench` and `tier` are free text.** Nothing validates them, and the page has no per-benchmark
  code: a new `bench` value simply appears as a new filterable value. Experiment-style benchmarks use
  `tier` for the experiment version (parsec records have tiers `pilot`, `v2`, `v6`).
- **The Source column** links to the PR when `pr` is set, otherwise to `summary_url`. With
  neither, it is plain text. `summary_url` is what connects a row in the runs table to the write-up
  behind it. Only **hand-published** records set it today: 4 parsec records point into the parsec
  section, e.g. `https://skillberry-runs.github.io/dashboard/parsec/results/v6/v6_g2_e1/summary.html`,
  and 7 skillsbench records point at the cap-evolve SkillsBench pages or `/notes/`. **CI records
  never set it**, so none of the 92 spreadsheetbench rows (all from CI) links to the
  spreadsheetbench section. To link a CI row to its write-up, add `summary_url` to that record by
  hand.

### Deploy

`.github/workflows/pages.yml` runs on a push to `main` that touches `records/`, `site/`, `scripts/`
or the workflow, and on manual `workflow_dispatch`. It:

1. Renders `benchmarks.json`/`meta.json` from `records/` with `record.py aggregate`. These two files
   are **never committed**.
2. For each benchmark in its section list (today `parsec` and `spreadsheetbench`), shallow-clones the
   private repo `skillberry-runs/<bench>` with the `RESULTS_READ_TOKEN` secret, then runs
   `build_reports.py --src … --out site/<bench> --repo skillberry-runs/<bench> --title <Title>`.
   - `RESULTS_READ_TOKEN` is a `skillberry-bot` fine-grained token with *Contents: read*.
   - If the token is set but the clone fails, the deploy **fails**, and the log shows the token
     owner and GitHub's reason.
3. Renders `notes/` to `/notes/`, then deploys `site/` to Pages.

**What a section publishes** (`build_reports.py`):

| | |
|---|---|
| **Published** | every `*.md` (rendered in the site chrome) and every standalone `*.html` (copied, links rewritten), anywhere in the repo except the unpublished top-level dirs. `README.md` becomes the section's `index.html`, with a "Report pages" list of the HTML pages added on top. |
| **Not published** | `artifacts/`, `recipes/`, `presentations/`, `.github/`, and every other file type (`*.json`, `*.jsonl`, logs, …). Links to these point to the private repo on GitHub, labelled as such. |
| **Masked** | internal paths (`/dccstor/…`, `/proj/…`, `/u/…`), CCC host names (`ccc…NNN`) and `…@…ibm.com` emails, in the published copy only |

A push to a benchmark repo does **not** redeploy the dashboard; parsec and spreadsheetbench have no
workflows. Until a notify workflow exists (see step 7 below), run **Actions → Deploy dashboard → Run
workflow** on `skillberry-runs/dashboard` after pushing write-ups.

## The per-benchmark repo layout

All three repos follow one skeleton, first used on `skillsbench-history` and refined in parsec. A new
benchmark should copy it as is.

```
README.md        what the benchmark is; the dashboard section's front page (see below)
.gitignore       build noise and secrets only, never results (copy parsec's)
results/         the numbers: summary.md + derived ledgers per experiment/arm/system; no raw logs
recipes/         cap-evolve configs needed to rerun (capevolve*.yaml, split_ids*.json), with notes
                 on where a recipe differs from what the run actually did
artifacts/       the capability packages: seed, champion/best, rejected candidates
reports/         per-task or final tables (auto-generated header, hand-written narrative below)
scripts/         generators for every number that appears more than once (with --check where possible)
ui/              self-contained HTML pages (heatmaps, results tables) that open straight from a checkout
docs/            design record: specs, plans, decisions.md (append-only decision and incident log)
```

**Second-level keying** depends on the shape of the benchmark. Use whichever existing repo matches:

| shape of the work | key `results/`, `recipes/`, `artifacts/` by | example |
|---|---|---|
| successive experiment versions with arms | `v<N>/<arm-id>/` (arm id `v<N>_<arm><k>_e<n>`: `b` baseline, `g` Global, `t` task-by-task) | parsec: `results/v6/v6_g2_e1/` |
| one experiment comparing systems over seeds | `<system>/s<seed>/{search,test}/` | spreadsheetbench: `results/gepa/s0/test/summary.json` |
| a series of named sweeps | `<sweep-name>/` | skillsbench: `results/task-by-task-87/` |

**README sections**, in the order parsec and spreadsheetbench use them:

1. A title and one-paragraph description, linking to the cap-evolve issue or plan, and saying it is
   one of the per-benchmark repos in `skillberry-runs`.
2. "Why this repo exists": narrative vs. machine-written records.
3. The experiment(s): task set, splits, models, budget.
4. Result: the headline table, with "how to read it".
5. Layout: a table with one row per directory, describing what that directory holds in *this* repo.
6. "Not in this repo": where the raw data lives instead (e.g. `cap-evolve-archive/<bench>-…/`).
7. Caveats.

**Rules carried over from the existing repos:**
- **Generate, don't retype.** Every number that appears more than once is derived by a script in
  `scripts/` from a results ledger.
- **Derived data only.** Commit per-task score vectors, summaries and recipes, never raw rollouts,
  logs or benchmark gold data.
- **No empty directories.** Add `insights/`, `evidence/`, `handoffs/` or `proposals/` only when there
  is content for them (parsec's rule).
- **Write for publication.** Every `.md` and `.html` outside `artifacts/`, `recipes/` and
  `presentations/` becomes public, with only the masking above. Put anything that must stay internal
  in an unpublished directory or a non-`.md` file.

## Adding a new benchmark

Below, `<bench>` is the benchmark's id. It must be lowercase and identical everywhere: the repo name,
the `bench` field of its records, the section path `/<bench>/`, and, if CI runs the benchmark,
`ci/benchmarks/<bench>/` in cap-evolve. `<Title>` is its display name, e.g. `SpreadsheetBench`.

Steps 1–2 are done in the new repo, step 3 on the `skillberry-bot` account, and steps 4–6 in
`skillberry-runs/dashboard`, as one commit or PR.

1. **Create the repo**, private like the others:
   ```bash
   gh repo create skillberry-runs/<bench> --private \
     --description "<Title>: cap-evolve results, recipes, artifacts"
   ```
   If the content already exists on a cap-evolve orphan branch, migrate it with full history, as was
   done for the other three: push the branch to the new repo's `main`, then add one
   `chore: migrate from cap-evolve <branch> branch to standalone repo` commit that updates the README
   and `.gitignore`.

2. **Lay it out** with the skeleton above: `README.md` in the standard section order, parsec's
   `.gitignore`, and `results/ recipes/ artifacts/ reports/ scripts/ ui/ docs/`, keyed like the
   closest existing repo. Commit with `git commit -s`. A `README.md` must exist on `main`, because it
   becomes the section's front page.

3. **Give the dashboard read access.** Edit the `skillberry-bot` fine-grained token behind
   `RESULTS_READ_TOKEN` (on GitHub: *Settings → Developer settings → Fine-grained tokens*) and add
   `skillberry-runs/<bench>` to its repository list, with *Contents: read*. The secret value stays
   the same. If org policy requires a new token, update the `RESULTS_READ_TOKEN` secret on
   `skillberry-runs/dashboard`.

4. **Add the section to the deploy.** In `.github/workflows/pages.yml`, step *Render benchmark report
   sections*, add a spec to the loop:
   ```bash
   for spec in "parsec|Parsec|parsec-history" "spreadsheetbench|SpreadsheetBench|spreadsheet-history" \
               "<bench>|<Title>|"; do
   ```
   The third field is the legacy cap-evolve branch to read when the token is missing. A new
   benchmark has none, so leave it empty; with no token the deploy then fails loudly, which is the
   intended behavior. Also update the comment above the step, which lists the repos the token must
   reach.

5. **Add the section to the nav** in **both** places, after the existing sections:
   - `site/index.html`: `<a href="<bench>/"><Title></a>`
   - `scripts/build_reports.py`, `chrome()`: `<a href="{site}/<bench>/"><Title></a>`

   Also add `site/<bench>/` to `.gitignore` (rendered output, never committed), and list the new repo
   in `README.md` under "Benchmark report sections".

6. **Add its runs to the table**: one `records/<id>.json` per run (see
   [the next section](#adding-runs-to-an-existing-benchmark)), with `"bench": "<bench>"` and
   `summary_url` pointing at the run's write-up in the new section. Commit hand-published records
   directly to `skillberry-runs/dashboard`. Records from CI runs do **not** arrive here
   automatically yet (see [Migration status](#migration-status)): copy them from cap-evolve's
   `benchmark-history:records/`, adding `summary_url` as you copy.

7. **Optional, recommended: redeploy on push.** Copy skillsbench's `notify-cap-evolve-pages.yml` into
   the new repo, retargeted to `gh workflow run pages.yml --repo skillberry-runs/dashboard --ref main`.
   It needs a `skillberry-bot` token with *Actions: read and write* on `skillberry-runs/dashboard`,
   stored as a secret in the new repo. parsec and spreadsheetbench don't have this yet, so without it,
   dispatch the deploy by hand.

8. **Verify.** Push to the dashboard, or dispatch **Deploy dashboard**, then check that:
   - the deploy log shows `<Title>: rendered N .md, copied M .html, masked K internal paths/hosts`,
     with N > 0;
   - `https://skillberry-runs.github.io/dashboard/<bench>/` shows the README and its report-page list;
   - every rendered `.md` page has the new nav link, in the new and the existing sections (copied
     `ui/*.html` pages keep their own markup), and links into `artifacts/`/`recipes/` go to the
     private repo;
   - filtering the runs table to `<bench>` shows the new rows, with each Source link opening the
     right write-up.

   To preview before pushing:
   ```bash
   pip install markdown            # build_reports.py needs it; the deploy installs it the same way
   git clone git@github.com:skillberry-runs/<bench>.git _src_<bench>
   python3 scripts/build_reports.py --src _src_<bench> --out site/<bench> \
     --repo skillberry-runs/<bench> --title "<Title>"
   python3 scripts/record.py aggregate records --now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --out site
   python3 -m http.server -d site 8000
   ```

If CI should also run the benchmark (smoke/pilot/full legs), that is separate work on cap-evolve
`main` (`ci/benchmarks/<bench>/<tier>/tasks.json`, adapter), and goes through the `open-pr`/`testing`
skills. CI then builds its records automatically, but for now pushes them to cap-evolve's
`benchmark-history`, not to the dashboard (see [Migration status](#migration-status)).

## Adding runs to an existing benchmark

- **Write-ups:** commit to `skillberry-runs/<bench>` in its existing layout, then redeploy the
  dashboard (see the end of [Deploy](#deploy)).
- **A CI run:** `benchmarks.yml` builds the record by itself, but pushes it to cap-evolve's
  `benchmark-history` branch (`benchmarks.yml`, step "Push to benchmark-history"), not to
  `skillberry-runs/dashboard`. Until CI is repointed (see [Migration status](#migration-status)),
  the run appears only on cap-evolve's own benchmarks page. To show it on the dashboard now, copy
  `records/<id>.json` from `benchmark-history` into `skillberry-runs/dashboard/records/`, adding
  `summary_url` if the run has a write-up.
- **A run finished, resumed or run outside CI:** build the record with the same scripts CI uses,
  following `ci/benchmarks/PUBLISHING.md` steps 1–4 (`metrics.py suite`, a hand-written
  `runmeta.json` with an honest `source`, `record.py build`). Then:
  - Add `"summary_url"` pointing into the section.
  - Commit `records/<id>.json` to `skillberry-runs/dashboard` instead of PUBLISHING.md's step 5.
  - Optionally add `notes/runs/<name>.md` and point `summary_url` at
    `https://skillberry-runs.github.io/dashboard/notes/runs/<name>.html`.

  The push redeploys the dashboard.

## Migration status

| piece | state |
|---|---|
| parsec, spreadsheetbench | done: repos created 2026-11-10, rendered on the dashboard. cap-evolve's parsec doc references were updated in #962. |
| skillsbench | repo created 2026-11-09, but **not on the dashboard**. cap-evolve `pages.yml` on `main` still renders it from the legacy `skillsbench-history` branch. Open PR [#961](https://github.com/skillberry-ai/cap-evolve/pull/961) switches cap-evolve's site to the new repo. Moving it into a dashboard section (steps 3–5 above, with legacy branch `skillsbench-history`) would bring it in line with the other two. |
| run records | the dashboard is a **snapshot as of 2026-11-10**. cap-evolve CI still writes new records (and `runs/<id>/ui` snapshots, `live/`) to cap-evolve's `benchmark-history`. The plan is to repoint CI at `skillberry-runs/dashboard`, running as `skillberry-bot`. Until then, new CI runs appear only on cap-evolve's own benchmarks page. |
| "Open UI" / "Watch live" | still served from cap-evolve's `benchmark-history` (`runs/**`, ~3 GB, not migrated) and the Actions API |
| legacy branches | all four still exist on cap-evolve and are still read as fallbacks; deleting them comes after the above |

**Access.** Only `dashboard` is public. The benchmark repos are private on purpose: outside readers
get a 404, which is an access restriction, not a broken link. They see the write-ups only as
rendered on the site. The bot tokens, all owned by `skillberry-bot` and fine-grained:

| token | lives in | grants |
|---|---|---|
| `RESULTS_READ_TOKEN` | `dashboard` | read the benchmark repos |
| `SKILLSBENCH_READ_TOKEN` | cap-evolve (set 2026-11-11; no workflow on `main` reads it yet, only PR #961's `pages.yml`) | read skillsbench |
| `CAP_EVOLVE_DISPATCH_TOKEN` | skillsbench | dispatch cap-evolve's Pages deploy |

## Existing documentation, compared

cap-evolve has **no single document** describing the org, and nothing anywhere describes adding a
benchmark. The procedure above is derived from how parsec and spreadsheetbench were set up,
specifically dashboard commit `6b51993` ("Publish Parsec and SpreadsheetBench report sections").
The existing pieces:

| document | says | matches the org? |
|---|---|---|
| `benchmarks/parsec/examples/rca_prompts/README.md` (+ v6 `PLAN.md`s, `scaffold_*.py` comments) | parsec bundles and results live in private `skillberry-runs/parsec`, with public copies on the dashboard | **yes**, and the only doc on cap-evolve `main` that names the org |
| `ci/benchmarks/PUBLISHING.md` | records go to `records/<run_id>__<tier>-<bench>.json` on `benchmark-history` | matches what CI does today; does not mention `skillberry-runs/dashboard` |
| `docs/RESULTS.md` | SkillsBench narrative is on `skillsbench-history` | stale (PR #961 fixes it) |
| `skillberry-runs/dashboard` README | layout, report sections, publish policy, current limits | **yes**, the best existing overview |
| the three benchmark repos' READMEs | layout and rationale | mostly yes; caveats below |

Inconsistencies found:

- **skillsbench:** its README says it is rendered from the new repo. On cap-evolve `main` it is still
  rendered from the legacy branch, until #961 merges. It is also published on a different site from
  the other two.
- **dashboard:** its README says "one repo per benchmark". Only benchmarks with write-ups have a
  repo; CI-only benchmarks (tau2, swebench, appworld, …) exist in the org only as records.
- **parsec:** its README says raw run directories aren't committed, yet its layout table mentions
  "the raw `runs/` directories". `results/v1/runs` and `results/v2/runs` hold derived per-task
  files, not raw `.capevolve/` dirs.
- **`benchmark-history`:** still has stale committed `benchmarks.json`/`meta.json` (last touched
  2026-09-24), although PUBLISHING.md says these are no longer persisted there.
- **The section list is hardcoded in three places:** `pages.yml`, `site/index.html` and
  `build_reports.py`. Nothing checks that the three agree, so step 5 is easy to get half done.
