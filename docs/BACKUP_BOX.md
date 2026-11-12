# Evaluation-run backup to Box: procedure

**Procedure v2.0.** It applies to every benchmark in `benchmarks/`, every method (cap-evolve and
others) and every evaluation window. Each evaluation run found on any source is captured in full,
organized into one common folder layout, and checked for gaps and validity. It is then copied to the
Box archive with `rclone`. The companion checklist is `docs/VERIFICATION_SCAN.md` (v2.0).

**Rules for the executing agent**
- **This document and `docs/VERIFICATION_SCAN.md` are read-only.** Never edit them. Everything you
  learn, decide or measure goes into the result documents:
  - `SCAN_RESULTS_<TS>.md` and `.json`, one pair in each run folder (written by the verification scan);
  - `BACKUP_RESULTS_<TS>.md`, one at the root of each user folder that receives runs (§12).

  `<TS>` is a full UTC timestamp, `YYYYMMDDTHHMMSSZ`, taken when that step starts. If a rule here is
  wrong or a benchmark profile (Appendix B) is incomplete, say so in `BACKUP_RESULTS_<TS>.md`, apply
  the corrected rule there explicitly, and open an issue that proposes the change to this document.
- **Box is a private experiment archive, not redistribution.** Upload everything a run produced,
  including gold, benchmark data and licence-restricted material. Record each licence in `NOTICE.md`
  (§7.4). Never leave data out because of its licence.
- **Never drop data.** Re-organize it into the layout of §3, but keep every source byte. A source file
  is either copied unchanged, or redacted for secrets only (`REDACTIONS.json`). Anything required
  that is not in the folder is reported in the gap report (§6). Every re-organization is recorded in
  `MOVES.json`.
- **Never upload secrets.** Values from the host's secret files and environment never reach Box
  (§5.5).
- **Never delete or overwrite anything on Box.** Use `rclone copy`, never `sync`, `move` or `purge`.
  Never rename on Box, because a rename is a delete. Never change or delete a source on the host.
- **Never rewrite git history.** If a merge is needed, it is done on a new branch (§5.8).
- **Existing Box folders are never written to** (§2.6).
- **Two stages.** The capture stage (§5, §6) must be done at backup time. It ends only when the
  capture gate passes (§5.10). The organizing stage (§7, §8, the verification scan) may run then or
  later, from the captured copy.
- **Comprehensiveness comes before speed.** Do not leave out data that belongs to a run because it is
  large, odd or in an unexpected place.

---

## Why this protocol, not "copy everything now, process later"

The backup has four objectives: it must be **comprehensive**, **authentic**, **reproducible** and
**usable for analysis**. Most of the organizing work (a common layout, metrics, summaries, the
verification scan) can be done at any time, by a person or an agent working from a copy. What a
later stage cannot do is recover what the copy never held. A raw copy of the disks at hand falls
short of each objective in a way that later processing cannot repair:

1. **Comprehensive.** A raw copy holds only what is on the disk it was pointed at, at that moment.
   Much of a run lives elsewhere or expires before anyone processes the copy, and a gap noticed
   later can only be recorded as lost. *Examples:* the sealed held-out data sits in a sibling
   `<project>.sealed/` directory, outside the run dir; Harbor job dirs are deleted 6 hours after a
   CI run.
2. **Authentic.** Proof that the archive is the original needs the original: hashes taken on the
   source at capture. A raw copy can show only that it matches itself, and it does not say what it
   lacks. *Examples:* the GitHub copy of a tau2 final-eval window holds about 1% of the bytes of the
   Box copy, and none of the rollouts; that Box copy holds 1,815 of the 7,200 planned jobs.
3. **Reproducible.** Much of what a repeat needs is live state, not files, and it changes unless it
   is queried at capture. *Examples:* SWE-bench evaluation images built locally, which exist only
   in the container store; the subagent model a CLI inherits from user settings.
4. **Usable for analysis.** Some facts are in no file, and only the people who ran the experiment
   know them. Without their answers, analysis of the archive has to guess. *Examples:* which
   attempts are re-runs of the same plan after a fix; why a run was discarded.

**Where this procedure meets each objective.**

| Objective | Component or operation | Section |
|---|---|---|
| Comprehensive | Discovery beyond the run dir: sealed data, CLI transcripts, harness and service state, benchmark clones, agents' side copies | §5.3(a), (d), (e), (j) |
| Comprehensive | Sources on other hosts: cluster workareas, CI runners, gateway ledgers, posts from the API | §5.3(b), (f), (h), (i) |
| Comprehensive | Capture order (most volatile first), git sources pinned by commit and snapshotted first, discovery repeated at the end | §5.2, §5.4, §5.9 |
| Comprehensive | Capture gate: every required item present or recorded as a gap, with fetch attempts | §5.10 |
| Authentic | Source hashes taken on the host, compared with the archive and with Box | §5.5, §10, §11 |
| Authentic | Gap report per folder (requirement list, gap classes, coverage per source and union) and roll-up per backup | §6, §12 |
| Reproducible | Live-state snapshots: images, versions, inherited settings, services, freezes, host | §5.6, §8 |
| Reproducible | Code, upstream clones and benchmark data at the commits that ran; reproducibility level | §5.3(d), §8 |
| Usable for analysis | Owner answers recorded with the run | §5.7 |
| Usable for analysis | Common layout, profiles, schemas, metrics, verification scan (may run later) | §3, §4, §7, §9 |

---

## 1. Terms

- **Run.** One method trained or measured on one benchmark with one configuration and one replicate
  (search seed). Several training attempts made under the same plan for the same purpose (for
  example a re-run after a fix) are grouped as **attempts** of one run. A **sweep** of per-task
  optimizations (for example parsec v4 task-by-task, skillsbench task-by-task) is **one** run, with
  one **unit** per task.
- **Window.** An evaluation that scores one or more frozen artifacts on a held-out set. A window
  that scores several runs is copied into each of those runs (§3.4).
- **Folder kinds** (`runmeta.kind`):
  - `training-run`;
  - `test-window`: a window over champions trained elsewhere;
  - `campaign-material`: plans, scripts and shared data that belong to no single run.
- **Source copy, redacted, derived.** Every file in a folder is exactly one of these. A source copy
  is byte-identical to a file on a source. A redacted file is a source copy with secrets removed. A
  derived file is written by this procedure (summaries, metrics, indexes, `README.md`).
- **Gap.** Something the procedure requires that is not in the folder (§6).
- **Profile.** The per-benchmark facts this procedure needs (Appendix B).
- **Partial export.** A source that holds only part of a run: git result branches and repos, CI
  artifacts, committed `run_full/` dirs, dashboard UI snapshots.

## 2. Where things go on Box

### 2.1 User folders

Every run goes to the folder of the person **its data comes from**, not the person doing the backup:

```
box:skillberry-runs-backup/user/<user-id>/<bench-id>/<run-folder>/
```

- **The new root.** The root `skillberry-runs-backup/` on the `box:` remote, and the prefix
  `skillberry-runs-backup/user/`, are fixed. Every backup made with this procedure goes there.
  - The root was created by the owner on 2026-11-12, and was empty when checked that day.
  - Create `user/` and each `user/<user-id>/` the first time they are needed (§5.1).
  - Address every folder directly, as `box:skillberry-runs-backup/user/<user-id>/`. No rclone alias
    is needed.
- **The old root.** `box:cap-evolve-paper-data/user/` holds the folders made before this procedure
  (§2.6), with the same internal structure. It is read-only for this procedure. The rclone alias
  `eval-data`, if present, points into it (`box:cap-evolve-paper-data/user/<operator-id>`). Leave the
  alias unchanged, and never use it as an upload target.

Find the person with the first rule that applies:

| Where the data comes from | Person | How to find them |
|---|---|---|
| A human-authored git commit (history branches, `skillberry-runs/*`, `results/*` branches, run dirs committed under `benchmarks/`, `docs/experiments/`) | the **author** of the first commit that added the data | `git log --follow --diff-filter=A --format='%an <%ae>' -- <path>`. Skip pure moves and history migrations (for example `aeee7126d`, the `benchmarks/` move). Never use the committer field: it is often `GitHub <noreply@github.com>` (web merges), or whoever migrated a repo. |
| A `skillberry-bot` commit (`benchmark-history` runs and records) | the person who started the CI run | `gh api repos/skillberry-ai/cap-evolve/actions/runs/<run_id> --jq .triggering_actor.login`. For a local record with no run id, use the record's `source` field (for example `bcarmeli`). |
| Not from git (local `.capevolve*`, cluster workareas, archives) | the person who launched the run | owner of the run dir or workarea, LSF job user, `run_meta.txt`. If these disagree, ask the owner and record the answer (§5.7). |

Map the person to a `<user-id>` with the table in Appendix C. A person not in the table gets a **new
user folder, created without asking or notifying anyone**. The id is derived as follows:
1. the local part of a real (non-`noreply`) e-mail, lowercased: `avalappi@redhat.com` → `avalappi`;
2. otherwise the GitHub login, lowercased, with the `<digits>+` prefix of a `users.noreply` address
   stripped: `136134023+yyualvin@users.noreply.github.com` → `yyualvin`;
3. aliases of one person are merged by GitHub login before applying rule 1.

Create it with `rclone mkdir box:skillberry-runs-backup/user/<user-id>` and check it with
`rclone lsd`. A person who already has a folder under the old root gets one under the new root
with the **same** id. Record the new id and its derivation in `BACKUP_RESULTS_<TS>.md`.

A run goes to exactly one user folder: the person who launched it. Everyone else whose data is in
it is listed in `runmeta.contributors`.

### 2.2 Benchmark ids

`<bench-id>` is one of the ids in Appendix B, including the retired ones (B.12–B.15). Map every
bench name to its id with the table in B.16, so that names are never confused. For example,
`benchmarks/swe_bench` is `swebench-lite`, while CI `swebench` runs the Harbor adapter and is
`swebench-verified-harbor`. A benchmark that is not listed gets a new
id, lowercase with hyphens, and a profile written into `BACKUP_RESULTS_<TS>/profiles/<bench-id>.md`
(§4).

### 2.3 Folder names

```
<YYYY-MM-DD>-<bench-id>-<method>-<method-version>-<setting>-<replicate>-<agent>-<optimizer>
```

- `YYYY-MM-DD` is the run's start date (UTC).
- Each slot is lowercase `[a-z0-9.]`, or `none` if empty. The slot order is fixed. Model names are
  shortened by removing the provider prefix and `-`, `_` and `/`, for example
  `aws/claude-sonnet-5-5` → `claudesonnet55`.
- `<method>`: `capevolve`, or the other method's name.
- `<method-version>`: a release (`v014`), or the first 7 hex digits of the method's code commit.
- `<setting>`: one value from the profile's closed list. Examples: capability scope `p`, `pt`, `m`,
  `ptm`; an ablation name; a gate setting `k02`.
- `<replicate>`: `s<k>` for search seed k, or `s0` for a run with a single replicate.
- A test-window folder uses `<method>` = the window id followed by the method of the champion it
  scores, for example `testall5-gepa`.

**The status is never in the folder name.** It is in `runmeta.status`, `README.md` and the
benchmark's `INDEX.md`, so it can change without renaming on Box.

### 2.4 Status

`status` is one of `scored`, `qualified`, `invalid`, `discarded`, `superseded` or `smoke`.
- The first three follow from the worst finding of the verification scan: INVALIDATES → `invalid`;
  QUALIFIES → `qualified`; otherwise `scored`.
- `discarded`, `superseded` and `smoke` are owner decisions, recorded with the reason.
- `runmeta.inert_champion: true` marks a search whose champion is the seed. It is a field, not a
  status.

### 2.5 What may sit where

These rules apply to new content:
- **At a user folder's root:** `BACKUP_RESULTS_<TS>.md`, `BACKUP_RESULTS_<TS>/` (evidence, rclone
  logs, the git snapshot, corrected profiles), and `<bench-id>/` folders.
- **In a `<bench-id>/` folder:** `INDEX.md` and run folders.

Nothing else. No probe or test files are uploaded, because nothing on Box can be deleted.

`<bench-id>/INDEX.md` has one row per run folder, with these columns: folder, kind, method,
replicate, status, source kind, coverage, reproducibility, and the runs it shares windows with. Add
rows; never edit or remove an existing row. A status change is a new row dated with the change.

### 2.6 Existing folders

Folders made before this procedure are under the **old root**, `box:cap-evolve-paper-data/user/`.
They stay as they are, and are never migrated, renamed, copied to the new root, or added to:
- `erezh/appworld/`, `erezh/_campaign/`, `erezh/_campaign_pipeline_test/`,
  `erezh/_throughput_probe_20261104/`, and the `BACKUP_RESULTS_*` files at `erezh/`'s root;
- `osher.elhadad/overnight-backup/`;
- anything else found under the old root.

They are still used, read-only:
- for the duplicate check (§5.4);
- as other copies in coverage comparisons (§6.4).

## 3. Folder layout

### 3.1 The tree

Every folder of every kind has this tree:

```
<run-folder>/
  README.md  NOTICE.md  runmeta.json  MANIFEST.json  SYMLINKS.txt
  SCAN_RESULTS_<TS>.md  SCAN_RESULTS_<TS>.json
  GAPS.json  GAPS.md  REDACTIONS.json  MOVES.json          (always present; may be empty)
  data/           README.md, metrics_full.jsonl, metrics_full.html, metrics_summary.json,
                  metrics_summary.md, reward_check.json                                 [derived]
  method/         the method's run dir(s) as on the source                              [source]
                    cap-evolve: method/capevolve/{project/, run_<name>/, sealed/<run_name>/}
                    other:      method/<method-name>/...
  champion/       frozen artifact(s), capability.diff vs the seed, hashes                [derived]
  baselines/      <baseline-id>/ per baseline arm (seed, no_skill, warm_seed, reused-<run>) [derived]
  rounds/         rNN_<candidate-id>/: verdict.json, diff.patch, notes/                 [derived]
  eval/           external evaluation state, one sub-dir per profile-declared source    [source]
                    search/<source-id>/   harness job dirs, native sims, external run dirs
                    window/<window-id>/   frozen artifacts, results, analysis, registry
  optimizer/      sessions/<cli>/ (incl. subagents), stderr, launch args, rendered
                  instructions                                                          [source]
  agent/          transcripts and cost records of an agent under test that is itself a CLI  [source]
  isolation/      mechanism config, guard logs, pre-run checks, scan outputs,
                  agent_copies/                                                         [source]
  logs/           progress logs, console output, service logs, ledgers/                 [source]
  posts/          issue, PR and workflow comments; results_repo/<sha>/                  [source]
  docs/           plans, appendices, result pages at their commit, reference material   [source]
  reproduce/      see §8                                                       [source + derived]
  attempts/aNN_<label>/   one per attempt when a run groups several; same sub-tree from method/ on
  units/<task>/           one per task of a sweep; same sub-tree from method/ on
```

- **A slot that does not apply** holds one file, `NOT_APPLICABLE.md`, with the reason. A slot is
  never simply absent.
- **Round numbers** are zero-padded to two digits (`r01`), or three if the run has more than 99
  rounds.
- **Re-organization never replaces a source copy.** Derived slots (`champion/`, `baselines/`,
  `rounds/`, `data/`) are views. The source they are made from always stays under the source slots.
- **Symlinks** cannot be stored on Box. List every one, with its target, in `SYMLINKS.txt`. Copy the
  target's content if it belongs to the run.

### 3.2 Where existing layouts go

| On the source | In the folder |
|---|---|
| `.capevolve/project/`, `.capevolve*/run_<name>/` | `method/capevolve/project/`, `method/capevolve/run_<name>/` |
| `<project>.sealed/<run>/`, `$CAPEVOLVE_SEALED_DIR` | `method/capevolve/sealed/<run>/` |
| another method's run dir or store | `method/<method-name>/` |
| Harbor / BenchFlow job dirs, tau2 `native_sims/`, rfe-creator runs dir, parsec `_run/jobs` | `eval/search/<source-id>/` |
| final or held-out window dirs (`runs/final/`, `final_eval/<id>/`, `test/`) | `eval/window/<window-id>/` |
| `~/.claude/projects/<slug>/`, other CLIs' session stores, `host/transcript.jsonl` | `optimizer/sessions/<cli>/` |
| the session that orchestrated the evaluation | `reproduce/orchestration/` |
| `git` results at a commit (`skillberry-runs/*`, `*-history`, `results/*`, `records/*`) | `posts/results_repo/<repo-or-branch>@<sha>/` |
| dashboard UI exports (`benchmark-history/runs/*/ui`, `run/ui/`) | `method/capevolve/ui_export/` |

Each move is one line in `MOVES.json`: the canonical path, the source path, and the source host.

### 3.3 No packing or compression

Upload plain, uncompressed trees, whatever the file count. Box handles about 4.5 files/s, so large
trees take long. Plan for that, and raise rclone parallelism (§11) instead of using tars.

### 3.4 Shared windows

A window that scores several runs is copied **in full** into each run's `eval/window/<window-id>/`,
so that every folder stands alone. `INDEX.md` lists the runs that share it. Their copies must have
identical sha256 for every file. Cost totals count a shared window once per window, never once per
run (Appendix A.4).

## 4. Benchmark profiles

Every benchmark difference this procedure needs is in that benchmark's profile (Appendix B):
- reward, success criterion and second-level metric;
- the rule used for infra errors;
- where each metric field is recorded;
- cost categories;
- splits and baselines;
- gold paths, and which of them the optimizer may see;
- isolation mechanism and agent-under-test evidence;
- the source of the models as used;
- external and volatile state;
- other sources: hosts, archives, git, results repo, ledgers, posts;
- reproducibility inputs;
- licence;
- extra secret locations.

The procedure steps are the same for every benchmark; only the profile values differ.

**Before backing up a benchmark's first run in a backup,** check its profile against that run:
- every path and field it names exists, or is explained;
- every source of the run maps to a profile key.

Then:
- **If the profile is correct,** record `profile checked against <run>` in `BACKUP_RESULTS_<TS>.md`.
- **If it is wrong or incomplete,** write the corrected profile to
  `BACKUP_RESULTS_<TS>/profiles/<bench-id>.md`, use that for this backup, list the corrections, and
  propose them in an issue (Rules).
- **If the benchmark has no profile,** write one in that file, in the format of Appendix B, before
  capturing.

## 5. Capture stage (at backup time)

### 5.1 Check the rclone setup (before the capture starts)

Never print a token. Show only remote names, types and the alias target.
1. **rclone installed.** If missing, install the official release, checksum-verified, at least two
   weeks old, in user space only.
2. **The `box` remote exists** (`rclone listremotes --long` lists `box:` with type `box`). If it is
   missing, ask the user to create it. `rclone config create box box` needs a browser login, which
   only the user can do. On a host without a browser, the user runs `rclone authorize "box"` on a
   machine with one and pastes the token. Wait until the user says it is done.
3. **The `box` token is valid.** Run `rclone lsd box: --max-depth 1`. If it
   fails with an authentication error (`invalid_grant`, `token expired`, `401`), ask the user to run
   `rclone config reconnect box:` and log in. Wait for the user, then repeat the call. Do not start
   the capture until it succeeds.
4. **The new root and the user folders.**
   - `rclone lsd box: --max-depth 1` must list `skillberry-runs-backup`. If it is missing, ask the
     user to create it, or to confirm that you may create it. Never create a different root.
   - If `box:skillberry-runs-backup/user` is missing, create it with `rclone mkdir`, and check it
     with `rclone lsd`.
   - Find the operator's id in Appendix C. If they are not listed, ask them, and check the existing
     ids under both roots. Create `box:skillberry-runs-backup/user/<operator-id>` if it is missing.
   - Folders for other users are created as in §2.1, without asking.
5. **The old root, for reading.** `rclone lsd box:cap-evolve-paper-data/user` lists the existing
   user folders, which are needed for the duplicate check (§5.4). If the `eval-data` alias exists,
   `rclone config show eval-data` should show type `alias` pointing into the old root. Record what
   it shows, and leave it unchanged.
6. **Access, end to end.** `rclone lsd box:skillberry-runs-backup/user` lists the user folders.
   Upload no test file.

Record in `BACKUP_RESULTS_<TS>.md` what was found, what was built or fixed, and every point where the
user was asked to act. Box tokens expire, so repeat check 3 before the first `rclone copy` (§11).

### 5.2 Snapshot the git result sources first

Before anything else, bundle every git source that may hold results into the operator's
`BACKUP_RESULTS_<TS>/git_sources/`, with the commit SHA of every ref:
- `git bundle create` of `benchmark-history`, all `*-history` branches, all `results/*`, `records/*`
  and `exp*/*` branches, and any branch named in a run's docs;
- clones (`git clone --mirror` then `git bundle`) of the `skillberry-runs/*` repos and any other
  results repo named in a profile.

These branches are pruned and migrated, and some (for example `records/parsec-v6-g2-and-tmrg`) are
not merged anywhere. From here on, every git source is referred to **by commit SHA**, never by
branch name.

### 5.3 Discover the runs

Do not assume a list. Build one from evidence, using every profile's `sources` and `external_state`,
and search at least:
- **(a) cap-evolve run dirs:** every directory holding `events.jsonl` and `state.json` under any
  `.capevolve*/` (including `.capevolve-blackbox/`), plus the sibling `project/`, plus
  `<project>.sealed/<run>/` and `$CAPEVOLVE_SEALED_DIR`.
- **(b) CI state:** `ci/benchmarks/.work/suite_*` run dirs, kept-run slots (for example
  `~/.cache/capevolve-latest/*-slots/`), and the workflow run's artifacts. A CI artifact is a
  partial export, because files in it are cut to 256 KiB.
- **(c) Committed partial exports:** `run_full/`, `run_agentopt*/`, `run/` and similar dirs under
  `benchmarks/`, and `docs/experiments/*`.
- **(d) Each profile's `external_state`:** harness job dirs, native sims, external run dirs, service
  logs and databases, benchmark clones (`vendor/*`) and caches.
- **(e) Session transcripts for every CLI involved:** the optimizer CLI named in the run's spec
  (`optimizer_skill`, and the registry row in `skills/optimizers/registry.yaml`), any agent under
  test that is itself a CLI, and the orchestrating session. For Claude Code that means
  `~/.claude/projects/*` (with `subagents/`), `/tmp/claude-<uid>/*`, `~/.claude/file-history/*` and
  `~/.claude/session-env/*`, plus any transcript directory a wrapper redirected to. For other CLIs,
  use their own session stores.
- **(f) Other hosts and archives** in each profile's `sources.hosts` and `sources.archives`: cluster
  workareas, LSF logs, colleagues' machines, off-repo archives.
- **(g) Git result sources** (§5.2), as partial exports and as published claims: `benchmark-history`
  `records/`, `runs/` and `live/` (live-monitor snapshots), the `*-history` branches, `results/*`
  and `records/*` branches, and the `skillberry-runs/*` repos. Retired benchmarks are found mainly
  here (B.12–B.15).
- **(h) Gateway and proxy usage ledgers** for the run's time window (`sources.ledgers`), which are
  sometimes the only token record.
- **(i) Posts:** every comment on the tracking issue(s) and PRs, and the workflow runs, fetched from
  the API with ids, URLs and timestamps.
- **(j) Copies of data that agents made during the run:** new dirs in `/tmp` and workdirs, and
  `cp -r` targets found in transcripts.
- **(k) Evaluation docs** in the repository and its branches: plans, appendices, ledgers, results
  pages (`docs/EVAL_*`, `docs/experiments/`), and the issues and PRs they name.
- **(l) Progress logs, launch scripts, probes and acceptance checks.**

For each candidate decide:
- **Is it an evaluation run, and which?** Apply the grouping rules of §1 and record why.
- **Its kind** (§1).
- **Its owner** (§2.1).

Record in `BACKUP_RESULTS_<TS>.md`:
- the full list;
- what was grouped, and why;
- **every candidate excluded, with the reason.**

### 5.4 Duplicates and capture order

**Duplicates.** Before copying a run, compare it with every existing Box folder. That means every
user's folder under **both roots** (the old root of §2.6, and the new root, which holds the backups made
with this procedure), including other windows of the same campaign. Compare by run id, by window and arm × seed,
and by sha256. Use the folders' `MANIFEST.json`, or the `.tar.sha256` files and member manifests
where they exist. Otherwise list in parallel, one `rclone lsjson --recursive` per sub-directory,
about 32 at a time. A serial listing of a large folder can take hours.
- **Already archived in full:** do not upload it again. Record "already archived at `<box path>`".
- **Partly archived:** make a new folder that holds only the files not yet on Box. Its `README.md`
  points to the existing folder, and its gap report compares both copies (§6.4).

**Capture order.** Most volatile first, by the profile's `volatile: true` entries: harness job dirs
deleted on a timer, CI work dirs and slots, `/tmp`, unmerged branches. Then the rest.

### 5.5 Copy, hash and redact

- **Hash on the source.** Hash every source file (sha256) **on the source, before copying**. The
  result is `source_sha256` in `MANIFEST.json`.
- **Copy into staging.** Copy into a local staging tree laid out as in §3. Preserve timestamps.
- **Secrets.** Before anything is uploaded, scan every file for every value in the host's secret
  files (`.env` files, the CLIs' settings and credential stores, `secrets/` dirs), for
  credential-named environment variables, and for the profile's `secrets_extra` locations.
  Command-line tokens captured in logs count too.
  - **In-file occurrences:** replace each with `[REDACTED:<name>]`. Record the file, the count, and
    the sha256 before and after in `REDACTIONS.json`.
  - **Whole secret stores** (for example `.env`, `settings.json`, `*.pem`): never copy them. List
    each one in `REDACTIONS.json` as `excluded`, with path and size.

### 5.6 Live-state snapshots

At capture, take everything in the profile's `reproduce` block that exists only in the running
system, and write it into `reproduce/` (§8):
- **packages:** freezes per environment (`pip freeze`, `uv pip freeze`) and interpreter versions;
- **tools:** versions of every CLI and tool involved (optimizer CLI, agent CLI, `bench`, `harbor`,
  LibreOffice, Docker / podman);
- **container images:** image digests, plus `docker save` / `podman save` of every image that was
  built locally or cannot be pulled again;
- **services:** state at capture, with the state at run start where it was kept (for example the
  store database, parsec's `data/agent_learnings.md`);
- **inherited settings** of each CLI: subagent model, effort, thinking, plugins, hooks, MCP servers,
  redacted;
- **host facts:** OS, kernel, CPU/GPU, container and cgroup facts, and the cluster host and job id.

### 5.7 Owner context

Ask the owner what is not in any file, and record each answer in `runmeta.owner_notes`, with who
answered and when:
- groupings and attempts;
- the purpose of the run;
- why a run was discarded or re-run;
- which split or model was intended;
- where missing pieces might be.

### 5.8 Unmerged branches

If a run needs data from a branch that is not merged:
- archive every version **side by side, by SHA**, under `posts/results_repo/`. Note in `README.md`
  which version is current, and how the versions differ.
- If a git merge is needed to build the folder, do it on a **new** branch,
  `backup/merge-<what>-<TS>`. Never rewrite or force-push an existing branch, and never overwrite the
  original data.

### 5.9 Repeat discovery

At the end of capture, run §5.3 again. Anything new is captured. Anything that has disappeared since
the first pass is a gap of class `lost` (§6).

### 5.10 Capture gate

Capture is finished only when every item the procedure requires for the run is accounted for, as
either:
- **present** in staging, with `source_sha256`; or
- **a gap** in `GAPS.json` (§6), with its class and the fetch attempts made.

The required items are:
- every profile-declared source;
- VERIFICATION_SCAN D1–D3 and D5;
- every item of the requirement list in §6.1.

Record the time of the gate in `runmeta.captured.end`.

## 6. Gap report

Every folder has a gap report: `GAPS.json` (Appendix A.6) and `GAPS.md`, which shows the same content.
It says exactly what is missing, how much, why, what it affects, and where it might still be. A
folder with no gaps says "no gaps". A `LOST_SOURCES.json` in a folder under the old root is read as
a list of gaps.

### 6.1 The requirement list

Build the list of required items from three sources:
1. the layout slots of §3 that apply to the folder's kind and profile;
2. everything the profile declares: `external_state`, `sources`, the telemetry fields, the cost
   categories, the `reproduce` block;
3. **expected items derived from the run's own records**, and from any copy's records:
   - every rollout in `eval_index.jsonl`, or the `evaluate` events × trials;
   - every candidate in the graph and history;
   - every optimizer call in the `step` events and `optimizer_sessions.json`;
   - every round;
   - every window cell in the window's registry, and every job in a window's job plan or order file
     (for example `order_<window>.jsonl`);
   - every transcript the run refers to.

A plan in one copy (for example a git job plan) sets the expected count for every copy. If no record
gives a count, derive it from the configuration (splits × trials × candidates) and mark it
`estimated`.

### 6.2 Gap classes

| Class | Meaning |
|---|---|
| `not-produced` | the benchmark or adapter never records it (for example per-episode latency in skillsbench). Not a backup gap, but analysis needs to know. |
| `not-in-source` | the run produced it, but the source being backed up does not hold it (for example rollouts missing from a git export) |
| `truncated` | present but incomplete (for example CI artifact files cut at 256 KiB) |
| `snapshot-incomplete` | the source was captured before the run finished. The items present are complete, but later ones were never copied. Detected when the capture time precedes the run's last event or window end, or when job counts stop short of the plan. |
| `lost` | existed and is now destroyed. Record the evidence that it existed (for example `/tmp` wiped by a restart, a job dir deleted on a timer). |
| `unreadable` | present but cannot be read (for example files owned by another user with no read access) |
| `redacted` | secrets removed or a secret store excluded; points to `REDACTIONS.json` |

### 6.3 What each gap records

- `id`, `item`, `class`;
- `required_by`: the slot, profile key or check;
- `expected`: count or bytes, and how it was derived;
- `present` and `coverage`;
- `may_exist_at`: other hosts, archives, branches, Box folders;
- `fetch_attempts`: what was tried at capture, when, and with what result;
- `impact`:
  - the goals affected (C, A, R, N);
  - the VERIFICATION_SCAN checks it makes `not run`;
  - the metric fields it makes `null`;
  - its effect on the reproducibility level.

### 6.4 Coverage

Coverage goes at the top of `GAPS.md`, and also into `runmeta.coverage`:
- **by item type**, in items **and** in bytes, counted separately: rollouts or jobs, job specs,
  transcripts, candidates, logs, results. A single overall percentage hides the difference between
  "every spec, no rollouts" and "a quarter of the jobs, complete".
- per slot, and overall.
- **when other copies of the run are known** (an existing Box folder in any user's folder, another
  host, another branch):
  - coverage per source and for their union;
  - what is **unique to each source**;
  - whether contents agree where both copies have an item (by sha256, or by a field match such as
    the job spec).

  Match copies by run id, by window and arm × seed, and by hash.

A gap found in an existing Box copy (for example `snapshot-incomplete`) is reported in the new
folder's gap report. The existing folder is never edited.

### 6.5 Git-origin runs

A run backed up from git is `completeness: partial-export` unless the requirement list shows full
coverage. `may_exist_at` lists every location the git copy itself names:
- archive paths in its README;
- cluster hosts in `run_meta.txt`;
- run dirs named in `state.json`;
- Box folders found in §5.4.

## 7. Organizing stage (now or later, from the captured copy)

### 7.1 Derived views

Write:
- `champion/` (the frozen artifact, `capability.diff` against the seed, hashes);
- `baselines/` (one folder per baseline arm the profile lists);
- `rounds/` (per round: `verdict.json` taken from the events, `diff.patch`, and the optimizer's
  notes).

Each derived file names its sources in `MANIFEST.json` (`derived_from`).

### 7.2 Metrics

Write `data/metrics_full.jsonl` (Appendix A.3), `data/metrics_summary.json` and
`data/metrics_summary.md` (Appendix A.4), and `data/reward_check.json` (Appendix A.5). Take every
value from the sources the profile names.
- **Rewards** are fractions in [0, 1].
- **Every value carries its source:** `record`, `recovered:<path>` or `not_recorded`. A cost is
  `measured`, `reported` or `estimated` (with the price used), or it is `null` with the reason.
  **Never write 0 for a cost that was not measured.** A recorded 0 counts as $0 only if the profile
  says `zero_means: zero` for that category.
- **Infra-errored episodes** are scored both ways:
  - as the profile's `infra_error.published_rule` says (`as_published`);
  - with errors counted as failures (`errors_as_failures`).

  Leave them out of token and cost totals, and show their count next to each average.
- **No held-out split.** If `runmeta.splits.holdout` is false, the "test" score is labelled a fit
  metric (`kind: fit`), and it is not counted a second time as train.
- **Cross-check against the published results.** Recompute the published metric named in
  `runmeta.reward_metric`, and compare it with the published value in `reward_check.json`.

Render `metrics_full.jsonl` into `data/metrics_full.html`: one self-contained file, with inline CSS,
no scripts and no external resources, so that Box's preview shows it. It holds:
- a header naming the source file and its sha256;
- the run total and per-arm summary first;
- then one table per row level.

Every value keeps its source, and a `null` cost is shown with its reason.

### 7.3 runmeta.json

Write `runmeta.json` as in Appendix A.1, including:
- kind, owner and contributors;
- `status`;
- splits and holdout;
- models as actually used, per role, from the profile's `models_as_used_source`;
- `completeness`, `coverage` and `reproducibility`;
- `captured` times;
- `owner_notes`.

### 7.4 README.md and NOTICE.md

`README.md` covers:
- what the run is;
- its status and reason;
- the headline result, with its split and whether it is a fit metric;
- coverage and reproducibility level;
- how to read the folder;
- links to other copies and to shared windows;
- its caveats.

`NOTICE.md` lists the licence of each data source and every profile restriction or protected path,
with a do-not-publish note. It never says that data was left out.

## 8. Reproducibility

A run folder must hold enough for someone else to **repeat the run elsewhere**: the same procedure,
configuration, inputs and code, not necessarily the same numbers.

### 8.1 Contents of `reproduce/`

A slot that cannot be filled gets `NOT_APPLICABLE.md` or a gap.

| Slot | Holds |
|---|---|
| `code/` | `cap-evolve.bundle`: every commit any run or attempt used. `code_commits.json`: run or attempt → commit, and how that was determined (start time, plus byte comparison of the run's code copies). `uncommitted/`: code never committed, recovered from transcripts, copies or history, and checked byte for byte against every surviving copy. `upstream/<name>.bundle` for every benchmark, method and service clone, at its recorded commit. |
| `data/` | **The benchmark data itself, copied in full**: gold, task files, environment databases, dataset snapshots (with their fingerprint). Also the version, download method, and tree and split hashes. |
| `recipe/` | The exact launch: the resolved `capevolve*.yaml`, split files, the seed capability as delivered, the optimizer instructions as rendered, `run.sh` / `setup.sh` / LSF launcher, the CI workflow with the tier's `overrides.env` and the workflow inputs, and the names (not values) of the environment variables used. |
| `environments/` | Package freezes and interpreter, tool and CLI versions [live state, §5.6]. |
| `images/` | Image digests, and saved images where needed [live state]. |
| `services/` | How to bring up each external runtime, its config (redacted), and its state [live state]. |
| `models/` | Every model **as actually used**, per role (agent, user simulator, judge, simulator, optimizer main loop, subagents, helpers), taken from transcripts and logs, not from the plan. Also endpoint and provider, sampling parameters, seeds, and step, token and context limits. |
| `inherited_config/` | The settings each CLI inherited, redacted [live state]. |
| `host/` | Host facts [live state]. |
| `orchestration/` | The session(s) that ran the evaluation, redacted. |
| `REPRODUCE.md` | The steps in order, for this run: restore the code and data from this folder, rebuild the environments and images, start the services, and launch with `recipe/`. Then say which results of a repeat should match exactly (splits, hashes, seed capability) and which only within noise (rewards). |

### 8.2 Reproducibility level

`runmeta.reproducibility` is computed from which slots are filled. It is not a judgement:
- **`full`:** `code/`, `data/`, `recipe/`, `environments/`, `images/` (when the profile lists images),
  `services/` (when the profile lists services) and `models/` are filled. The only gaps are the
  profile's `unpinnable` items.
- **`procedure`:** `code/`, `recipe/`, the split files and the seed capability are present, but
  another slot or the trial-level records have a gap. The run can be repeated as a procedure, and
  compared at aggregate level only. This is the expected level for git-only partial exports.
- **`record-only`:** anything less. The folder is evidence of a result, not a recipe.

### 8.3 Checks

Reproducibility is checked statically, from hashes and checkouts (VERIFICATION_SCAN E1–E4). **No
repeat run is part of this procedure.** A smoke test (VERIFICATION_SCAN E5) checks that the
correct-version components are in place. It is run **only when the user asks for it**.

## 9. Verification scan

Run **`docs/VERIFICATION_SCAN.md`** on every assembled folder:
- D1–D3 and D5 run in the capture gate (§5.10);
- the rest may run later.

The scan writes `SCAN_RESULTS_<TS>.md` and `SCAN_RESULTS_<TS>.json` into the folder.
- If a finding changes a run's status, update `runmeta.status` and `README.md`, add an `INDEX.md`
  row, and say so in `BACKUP_RESULTS_<TS>.md`. The folder name does not change.
- Never hide a finding by leaving data out.

## 10. Before upload

- **cap-evolve tools,** run read-only on the staging copy of each complete cap-evolve run dir:
  - `cap-evolve tail <run_dir> --from-start --idle-timeout 5` must exit 0, or exit 3 (idle timeout)
    after reading at least one event;
  - `RunDir.open` + `dashboard.reduce_run` + `render_html` must succeed.

  Do not use `dashboard --export`: it overwrites the run's `dashboard.html`. For partial exports,
  other methods and test windows, write `NOT_APPLICABLE` with the reason.
- **Completeness:** every source copy's sha256 equals its `source_sha256`. Every other source file is
  listed in `REDACTIONS.json` or `GAPS.json`.
- **Secret scan:** 0 occurrences of any secret value (§5.5) in any file.
- **Conformance:** every file of Appendix A follows its schema. No USD of 0 whose source is not
  measured. Shared-window copies are identical (§3.4).
- **Write `MANIFEST.json` last.**

## 11. Upload

For each run, after repeating check 3 of §5.1:

```
rclone copy <staging>/<run> box:skillberry-runs-backup/user/<user-id>/<bench-id>/<run> \
       --transfers 16 --checkers 32 --log-file <log> --log-level INFO
rclone check <staging>/<run> box:skillberry-runs-backup/user/<user-id>/<bench-id>/<run> --one-way
```

- Upload folder trees as they are, uncompressed.
- `rclone check` must report 0 differences and 0 missing files for every run. Box keeps SHA-1, so this
  is a content check.
- Append the run's row to `<bench-id>/INDEX.md`.
- Keep the rclone logs in `<user-id>/BACKUP_RESULTS_<TS>/`.

Record per run the capture times (`runmeta.captured`), the upload end time, and the file and byte
counts. If data is added later (a second pass), it only adds files: the gap report is regenerated as
a new version, and both passes are reported.

## 12. Backup results

Write one `BACKUP_RESULTS_<TS>.md` at the root of each user folder that received runs, all with the
same `<TS>`. Each lists its own runs and links to the others.

It **opens with the gap roll-up.** For each run:
- source kind, coverage (items and bytes), reproducibility level;
- the main gaps;
- where the missing data may be.

Then a list of every `may_exist_at` location across the backup, to follow up.

It then records:
- what was searched, which runs were found, and how they were grouped, attributed and named;
- user folders created, with their ids and how each was derived;
- duplicates skipped, with their existing Box path;
- every excluded candidate, with the reason;
- profiles checked or corrected (§4);
- merges made (branch names);
- per run: Box path, files, bytes, status and its reason, with a pointer to that run's
  `SCAN_RESULTS_<TS>.md`;
- verification outcomes: tool checks, completeness, secret scan, conformance, `rclone check`;
- the owner's answers, the decisions taken with the owner, and anything still open;
- issues met during the backup, and how each was resolved.

---

## Appendix A. File schemas

All files are UTF-8 JSON (or JSONL) with these keys. Extra keys are allowed only inside the objects
marked `extra`. Rewards are fractions in [0, 1]. Times are ISO-8601 UTC.

### A.1 `runmeta.json`

The fields of the CI run record (`.github/workflows/benchmarks.yml`, `ci/benchmarks/lib/record.py`)
keep their names: `run_id, run_url, bench, tier, event, source, pr, branch, sha, date, iterations,
agent_model, optimizer_model, agent_model_requested, optimizer_model_requested, agent_provider,
optimizer_provider, gate_k_se, algorithm, warm_seed, reward_metric, conclusion`. In addition:

```
schema: "runmeta v2", procedure: "BACKUP_BOX v2.0"
kind: training-run | test-window | campaign-material
bench_id, method, method_version, setting, replicate
owner: <user-id>, contributors: [{name, email, role}]
status, status_reason, inert_champion: bool
dataset: {variant, version, version_source}
splits: {source, sizes: {train, val, test}, holdout: bool}
seed_variant, baselines: [<baseline-id>]
trials: {search, final}
models: {agent, usersim, judge, simulator, optimizer: {<role>: …}}   each {requested, actual, actual_source}
dates: {start, end, attempts: [{label, start, end, status}]}
champion_training_run: <box path> | null
completeness: full | partial-export
coverage: {items: {<type>: {expected, present}}, bytes: {<type>: {expected, present}}}
reproducibility: full | procedure | record-only
hosts: [<host>], captured: {start, end}
owner_notes: [{question, answer, who, when}]
extra: {}
```

### A.2 `MANIFEST.json`

```
{schema: "manifest v2", files: [{path, bytes, sha256, kind: source|redacted|derived,
  source_host, source_path, source_sha256, derived_from: [path]}]}
```

### A.3 `data/metrics_full.jsonl`

One row per line. `level` is one of:
- `episode`, with `phase: search|window|diagnostic`, `split`, `task_id`, `trial`, `arm`;
- `round`;
- `optimizer_call`;
- `aux_call`, with `role: usersim|judge|simulator|proxy|merger`;
- `phase_total`, for aggregates taken from a gateway or proxy ledger (`source: proxy-aggregate`);
- `run_total`.

Fields, where they apply: `reward, success, group_key, secondary{…}, infra_error, prompt_tokens,
completion_tokens, cache_tokens, latency_s, steps, termination`. Each field `x` has `x_source`, one of
`record`, `recovered:<path>`, `not_recorded`.

Cost is an object per category (`agent`, `usersim`, `judge`, `simulator`, `proxy`, `optimizer`):
`{usd, usd_source: measured|reported|estimated|null, usd_null_reason, usd_estimated, price_ref}`. A
`usd` of 0 is invalid when `usd_source` is `null`.

### A.4 `data/metrics_summary.json`

```
{schema: "metrics_summary v2", window, sources: [{path, sha256}], entries: [
  {kind: candidate|baseline, name, attempt,
   train_reward: {primary, success_rate, group_metric: {name, value}, split, n_tasks, round},
   test_reward:  {primary, success_rate, group_metric, window, n_tasks, n_trials, kind: heldout|fit},
   infra: {as_published: {…}, errors_as_failures: {…}, n_errored},
   phase_cost: {train: {optimizer, search_episodes, aux, total}, test: {agent, aux, total}},
   task_cost: {train|test|both: {all|success|failed: {n, tokens_total, tokens_mean, usd_total, usd_mean}}},
   comparison: {vs_baseline, paired_delta, se, se_method, ci95, clusters, n_paired,
                missing: {candidate, baseline}},
   rules_applied: [], sources: [{path, sha256}]}]}
```

Case rules:
- **Candidate's train reward:** the method's own end-of-search score of the champion it froze, on the
  split it searched. A re-score inside a window is reported beside it, labelled, never in its place.
  If the method never scored its frozen champion, use the earliest non-test scoring of it and name
  the split. If there is none, the train reward is `null` with the reason.
- **Baseline's train reward:** the seed's own scoring on the candidate's search split, or else on
  another non-test split, named. Its optimizer cost is `null`: "not applicable: no search".
- **Baselines** are computed once per window **per baseline id**. The entry is byte-identical in every
  summary that shares the window.
- **Attribution of episodes:** reused episodes count only in the entry that ran them. Diagnostic
  episodes belong to neither train nor test, and are reported apart. Each attempt is its own entry.
- **Costs:** unpriced USD is `null`. `usd_estimated` is a separate field, never added into a measured
  or reported USD. Totals show the known USD, and separately the known USD plus estimates.
- **Averages:** an average over zero tasks is `null`.
- **Successful task:** an episode (one task, one trial) that meets the profile's success criterion.

### A.5 `data/reward_check.json`

```
{published: {metric, value, source_path, source_sha256},
 recomputed: {value, from}, match: bool, episodes: {used, published}}
```

One object per arm.

### A.6 `GAPS.json`

```
{schema: "gaps v2", coverage: {by_type: {<type>: {expected, present, expected_bytes, present_bytes}},
  by_slot: {...}, overall: {...},
  sources: [{name, box_or_host_path, by_type: {...}, unique: [...]}], union: {...},
  agreement: [{type, compared, identical}]},
 gaps: [{id, item, class, required_by, expected, present, coverage, may_exist_at: [],
   fetch_attempts: [{what, when, result}],
   impact: {goals: [], checks_not_run: [], metrics_null: [], reproducibility: ""}}]}
```

### A.7 `REDACTIONS.json` and `MOVES.json`

```
REDACTIONS: [{path, kind: in-file|excluded, secret_names: [], count, sha256_source, sha256_backup, bytes}]
MOVES:      [{path, source_host, source_path}]
```

### A.8 `SCAN_RESULTS_<TS>.json`

Holds the same content as the `.md` (VERIFICATION_SCAN, format):

```
{procedure, profile, holdout, coverage, status, status_reason, reproducibility,
 checks: [{id, result, severity, evidence: [], gap_ids: []}], known_gaps: []}
```

## Appendix B. Benchmark profiles

**Status of these profiles.** Every benchmark in `benchmarks/` and every retired benchmark found in
the results has a profile, so every run is eligible for backup. They were drafted on 2026-11-11 and
2026-11-12 from the adapters, configs, CI tiers and committed results (for retired benchmarks, from
their code at the commit before removal and from their records), not from a backup of a real run. The first backup of each benchmark
checks its profile against a real run (§4). Every path is relative to the cap-evolve repo unless
stated otherwise.

### B.0 Values shared by every benchmark (from core)

- **Rollouts:** `rollouts/<split>/<task>__<cand>__t<k>.json`, holding `{input, rollout, score}`.
  `Rollout` has `cost_usd`, `tokens` (one total), `error`, `trace`, `tool_calls` and `metadata`.
  There is no per-episode latency in core.
- **Episode index:** `eval_index.jsonl`. Per-evaluation seconds are in the `evaluate` events. Run
  totals are in `state.json` `spent` (including `usersim_usd`, which is a list-price estimate already
  inside `usd`).
- **Infra errors:** core drops errored trials from the mean by default (`errored_trial_policy: drop`).
- **Test seal:** core seals test. In pooled mode, the sealed stratum is in `<project>.sealed/<run>/`
  or `$CAPEVOLVE_SEALED_DIR`.
- **Optimizer:** `claude -p … --allowedTools Bash` (`skills/optimizers/registry.yaml`). There is no
  sandbox unless the profile says so. Transcripts are in
  `~/.claude/projects/<slug of the work dir>/`, unless `CAPEVOLVE_OPTIMIZER_TRANSCRIPT` was set.
  Agent-mode runs also write `<run>/host/transcript.jsonl`.
- **CI:** the run dir is under `ci/benchmarks/.work/` and is wiped by the next run of the same
  tier×bench. If a tier has no `split_ids.json`, train = val = test (no holdout).
- **False positive in gold greps:** the term `ao_focus_canary`.

### B.1 `appworld` — `benchmarks/appworld/examples/react_agent`

| Key | Value |
|---|---|
| Reward | `success` (every requirement passes): binary. Success = `success`. Group metric SGC: per trial k, a scenario passes iff all its tasks pass (scenario = task-id prefix before `_`), averaged over k. TGC = mean task success. Analysis in `scripts/analyze.py`. |
| Infra rule | published: errors and missing cells count as failures (`analyze.py`); core search: drop. Detectors: `Rollout.error` "infrastructure: …", `metadata.infra_error`. |
| Telemetry | `prompt_tokens`, `completion_tokens`, `n_steps`, `termination`, `wall_seconds` / `episode_seconds`, all in rollout metadata; window: `runs/final/results.jsonl`. |
| Cost | agent: `cost_source="unpriced"` (RITS), `zero_means: unknown`. Optimizer: `state.json` `spent.optimizer_usd`, from the CLI. |
| Splits | train 90 / dev 57 / test_normal 168. Search split = train ∪ dev (fit). Test sealed by the adapter, scored in `scripts/final_window.py`. |
| Baselines | seed |
| Gold | `$AW_EVAL/root_full/data/tasks/*/ground_truth/` (`answer.json`, `compiled_solution.py`, `metadata.json`), `private_data`, `appworld/generate/`. Allowed to the optimizer: none. `root_opt` keeps train/dev ground truth: access to it is a finding to grade. Canary is release-wide, so only test ids count as evidence. |
| Isolation | `sandbox/` shim (bubblewrap or namespace), `progress/optimizer_guard.log`, `runs/isolation_check/*/report.json`, `scripts/isolation_gate.py`. |
| Agent evidence | per-episode `fs_probe`, `guard_blocked`, `guard_probe`. |
| Models as used | transcripts; window `results.jsonl`. |
| External state | `$AW_EVAL` (default `/tmp/aw_eval`, **volatile**): `root_opt`, `root_full`, `runs/` (manifest, final, isolation_check, optimizer_transcripts), `progress/`, `scratch/`, `reference/`, `lint_cache.json`. |
| Sources | posts: tracking issues. |
| Reproduce | launch: `scripts/setup_project.sh`, `capevolve.yaml`, `optimizer/INSTRUCTIONS.template.md`; data: `root_full`; clones: AppWorld @ `42b5bcf` + `patches/`; env: `venv-aw` freeze. |
| Licence | Apache-2.0; the protected part (API docs and implementations, solutions, tests, and `reference/api_index.md`) must not be published in plain text. |
| Secrets | the repo `.env`. |

### B.2 `tau2-airline` — `benchmarks/tau2/template`, `benchmarks/tau2/examples/airline`; CI `tau2`

| Key | Value |
|---|---|
| Reward | tau2 `reward_info.reward`, binary per trial in airline. Success: reward = 1. Group metric: pass^k (`final.json` `pass_k`). Secondary: `db_match`. |
| Infra rule | published: drop. Detectors: termination `INFRASTRUCTURE_ERROR`, `UNEXPECTED_ERROR`, `TIMEOUT`; user-simulator `###STOP###` leak. |
| Telemetry | tokens: sum of `trace[].usage`; latency: `<run>/native_sims/<tag>/<split>/results_*.json` `duration`; steps: count from the trace; termination: `metadata.termination_reason`. |
| Cost | agent: `metadata.cost_source` (`tau2`, `partial_messages`, `unpriced`), `zero_means: unknown` unless tagged `tau2`. User simulator: `metadata.usersim`, list estimate, **already inside `usd`** (report it apart). Optimizer: `step` events; in agent mode it may be null or hand-entered. |
| Splits | template: core ratios. airline: `split_ids.json` 50/50/50 (no holdout), `agentopt_split.json` 26/12/12 (holdout), `smoke_split.json`, `itest_split.json`. |
| Baselines | seed |
| Gold | `vendor/tau2-bench/data/tau2/domains/airline/tasks.json` (`evaluation_criteria`), `src/tau2/evaluator/`. In records: `metadata.tau2_reward_info.action_checks`, which is copied into `work/*/trajectories/`. Allowed: train/val. Forbidden: test ids. |
| Isolation | none |
| Agent evidence | the candidate's `tools.py` runs in-process. |
| Models as used | `native_sims` `info.agent_info.llm`, `info.user_info.llm`. |
| External state | `native_sims/`, `vendor/tau2-bench*`. |
| Sources | committed exports `run_full/`, `run_agentopt*/` (some made on another host); `erezh/_campaign/` on Box (duplicate check); git `research/capevolve-paper-*` branches. |
| Reproduce | launch: `setup.sh`, `run.sh`, `capevolve*.yaml`, split files; clone: tau2-bench at the recorded SHA (unpinned `main`; check `TAU2_COMMIT.txt` against `demo.cast`); unpinnable: gateway backends. |
| Licence | not recorded |
| Secrets | `native_sims/**` `llm_args`; `OPENAI_API_KEY` in `.env`. |

### B.3 `tau2-sierra-airline` — `benchmarks/tau2/examples/sierra_airline/{direct,blackbox}`; CI `tau2_sierra`, `tau2_sierra_blackbox`

| Key | Value |
|---|---|
| Reward | as `tau2-airline`. |
| Infra rule | as `tau2-airline`. |
| Telemetry | no `tokens`. Trace = `sim.model_dump()` (`duration`, `termination_reason`, `messages[].usage`). |
| Cost | agent not measured (`zero_means: unknown`); SPA reports no usage. User simulator: `sim.user_cost`. |
| Splits | `split_ids_budget.json`: 7 = 7 = 7 (no holdout); `split_ids.json`; `split_ids_smoke.json`. |
| Baselines | seed |
| Gold | **allowed by design:** `runner_repo_path: ../../vendor/tau2-bench`, and gold actions in `trajectories/`. Check for hardcoded task ids or values (VERIFICATION_SCAN A1b). |
| Isolation | none |
| Agent evidence | direct: in-process tools; blackbox: SPA (port 7000) + env manager (port 8004). |
| Models as used | native results `info.*.llm` (the spec, PROJECT.md and REPRODUCE disagree). |
| External state | `.capevolve/`, `.capevolve-blackbox/`, `vendor/{tau2-bench,skillberry-store,skillberry-agent}` and their venvs, the store DB, `/tmp/skillberry-*.log`, `/tmp/env_manager.log`, `/tmp/tools-*.log` (**volatile**). |
| Reproduce | tau2 @ `TAU2_REFERENCE_SHA`; store `aviweit/skillberry-store@c39d472`; SPA `skillberry-ai/skillberry-agent@e359494`. |
| Licence | not recorded |
| Secrets | `llm_args`; `.env`. |

### B.4 `skillsbench` — `benchmarks/skillsbench/{template,examples/shared_skills}`; CI `skillsbench`

| Key | Value |
|---|---|
| Reward | verifier `reward.txt`, `result*.json` or CTRF all-pass: binary. Success: all verifier tests pass. Group metric: pass^k. |
| Infra rule | published: drop. Detectors: no reward found, launch failure, timeout. |
| Telemetry | `cost_usd = 0` and `tokens = 0` are hard-coded (`not_recorded`). Latency, steps, termination: BenchFlow `result.json` under the jobs dir, if present. |
| Cost | agent (Claude Code in a container): not metered (`zero_means: unknown`). Optimizer: `step` events. |
| Splits | example: train = val = 7 tasks, test 3. smoke 1/1/1. |
| Baselines | seed |
| Gold | `vendor/skillsbench/tasks/<id>/{tests,solution}`, `.bench_cwd` dataset clone. Allowed: train-task verifiers (`runner_repo_path`). Forbidden: the 3 test tasks' tests and solutions. |
| Isolation | none |
| Agent evidence | `--sandbox docker`. |
| Models as used | the bench command (`--model`) and the agent trajectories. |
| External state | `<run>/bench_jobs/`, `.bench_cwd`, `vendor/skillsbench`, Docker images. |
| Sources | git `skillsbench-history`, `skillberry-runs/skillsbench`; CI records. |
| Reproduce | clone at the recorded SHA (`SKILLSBENCH_COMMIT.txt`), but tasks run from BenchFlow's own `--source-ref main` cache: record its SHA. `benchflow` version. |
| Licence | the four seed skills are Anthropic-licensed, not for redistribution (not to be published). |
| Secrets | `--agent-env ANTHROPIC_AUTH_TOKEN=…` on the command line, in logs and job configs; `.env`. |

### B.5 `spreadsheetbench` — `benchmarks/spreadsheetbench/template`; CI `spreadsheetbench`

| Key | Value |
|---|---|
| Reward | `SPREADSHEETBENCH_SCORING` (soft / hard) × `REWARD_RECALC`; name in `runmeta.reward_metric`. Success: hard = 1. Group metric: hard vs soft over the 3 cases (912/200 only); `instruction_type`. |
| Infra rule | published (exp895 campaign): infra retried, never scored 0, candidate errors score 0. Core: drop. Detector: `metadata.error_kind`. |
| Telemetry | `tokens` (sum over turns); steps from the `trace`; no latency or termination. Campaign: phase totals in `results/usage.json` (`phase_total`). |
| Cost | agent: litellm `response_cost` (`zero_means: unknown`). |
| Splits | smoke: fit; pilot 5/50/5; full 182/91/639; full_verified 80/40/280 (`split_source.json`). |
| Baselines | seed, `no_skill`, `warm_seed` (`seed_capability_warm`), empty seed (`SB_EMPTY_SEED`), reused-from-slot (`SB_REUSE_LATEST_BASELINE`). Find which from the seed snapshot, not from runmeta. |
| Gold | `<DATA>/spreadsheet/<id>/*_answer.xlsx`, `*golden.xlsx` in `~/.cache/capevolve-ci/spreadsheetbench-data/`; `third_party/spreadsheetbench/evaluation/`. |
| Isolation | none for the optimizer. |
| Agent evidence | gold-free agent view; `$OUT/gold_separate_from_agent_mount`. |
| External state | the data cache; kept slot `~/.cache/capevolve-latest/spreadsheetbench-slots/` (**volatile**, overwritten); `outputs/*.xlsx`; Docker executor. |
| Sources | `skillberry-runs/spreadsheetbench` (= `spreadsheet-history`): 11 systems × 3 seeds, each `results/<system>/s<k>/{search,test}`. Raw data stated at `cap-evolve-archive/spreadsheetbench-exp895/` (not found in any repo or on this host on 2026-11-11). Cluster workareas named in `run_meta.txt`. |
| Reproduce | data fetched from raw `main` (unpinned; hash the tree); harness @ `0d9dc14`; `recipes/<system>/` from the results repo. |
| Licence | CC BY-SA 4.0 (data); split ids MIT. |
| Secrets | `.env`. |

### B.6 `swebench-lite` — `benchmarks/swe_bench/template` (local only)

| Key | Value |
|---|---|
| Reward | resolved: binary. Success: resolved. Group metric: per `metadata.repo`. |
| Infra rule | published: drop. Detectors: `error_ids`, `incomplete_ids`, missing report (`raw.errored`). |
| Telemetry | `tokens`, `cost_usd`; single step; no latency or termination. |
| Cost | agent: litellm (`zero_means: unknown`). |
| Splits | core ratios 0.34 / 0.33 / 0.33 over HF `princeton-nlp/SWE-bench_Lite` test. |
| Baselines | seed |
| Gold | HF fields `patch`, `test_patch`, `FAIL_TO_PASS`, `PASS_TO_PASS`; `_oracle` dataset. `SWEBENCH_ORACLE=1` puts gold-derived text into `Task.input`: disclose it. |
| Isolation | none |
| External state | HF cache; Docker images `sweb.*` (built locally). |
| Reproduce | dataset snapshot and fingerprint; `swebench` package version; images saved. |
| Licence | code MIT; dataset licence unstated. |

### B.7 `swebench-verified-harbor` and `harbor-<dataset>` — `benchmarks/generic/harbor/template`; CI `swebench`

| Key | Value |
|---|---|
| Reward | verifier `reward.json` / `reward.txt` (possibly partial). Success: reward ≥ 1. Group metric: repo, from the instance-id prefix. |
| Infra rule | published: drop. Detector: `exception_info` with no reward. |
| Telemetry | trial `result.json` `stats` (input, output and cache tokens separately); latency per `harbor run` only. |
| Cost | agent: CLI-reported in `result.json` (`reported`). |
| Splits | CI full 100/50/100 (`split_ids.json`); pilot and smoke: fit. |
| Baselines | seed |
| Gold | task `tests/test.sh`, `solution/solve.sh` in Harbor's task cache; trial `verifier/`. |
| Isolation | none; the container network is public. |
| Agent evidence | packaged mode runs `/capability/score.sh` from the candidate (check that the grader is not candidate-supplied); registry mode delivers only `prompt.md` (B2 "capability as delivered"). |
| External state | `$HARBOR_JOBS_DIR/<job>/<trial>/` (**volatile: reaped after 6 h** by CI setup); containerd images; npm cache. |
| Reproduce | Harbor CLI version; dataset name and version; Claude Code npm version per container (unpinnable unless recorded). |
| Licence | SWE-bench Verified: none stated on its card. |

### B.8 `rfe-creator` — `benchmarks/rfe_creator/template`; CI `rfe-creator`

| Key | Value |
|---|---|
| Reward | `_reward/judges.json` `reward`: a weighted mean of 10 checks and 2 LLM judges, continuous. **Success: undefined** (the overlay sets `gate: false`): `success` is `null` with that reason. Group metric: per judge (`raw.per_judge`). |
| Infra rule | published: drop. |
| Telemetry | `tokens` not set (`not_recorded`); no latency, steps or termination. |
| Cost | agent: `run_result.json` `cost_usd` (`reported`). **Judges:** not recorded anywhere, and billed on the optimizer's gateway (`aux_call`, `null` with that reason). |
| Splits | none: train = val = test (no holdout). |
| Baselines | seed |
| Gold | `rfe-creator/eval/dataset/cases/*/annotations.yaml`, judge prompts in `eval.yaml`. **The agent's worktree contains them.** |
| Isolation | none |
| External state | `$RFE_RUNS_DIR` (`/tmp/cap-evolve-rfe-creator/runs/`, **volatile**); worktrees; clones in `~/.cache/capevolve-ci/rfe-creator-src/`. |
| Reproduce | rfe-creator and agent-eval-harness at the recorded SHAs (reset to `main` on every setup: record them). |
| Licence | rfe-creator unlicensed; agent-eval-harness Apache-2.0. |

### B.9 `parsec-rca` — `benchmarks/parsec/examples/rca_prompts`; CI `parsec`

| Key | Value |
|---|---|
| Reward | Harbor verifier `reward.json` (partial credit in [0, 1]: tool calls and answer, with a completion gate). Success: reward = 1.0 (convention). Group metric: per category. |
| Infra rule | published: drop. Detector: `_agent_failure` (dead agent). |
| Telemetry | `tokens` and `cost_usd` from parsec-live `usage` log lines; time window in `metadata.parsec_usage_window`. |
| Cost | agent: log-derived, 0 if the log is missing (`zero_means: unknown`). **Simulator LLMs:** not recorded (`aux_call` null). Merger (v6_t4): optimizer cost. |
| Splits | v6: pooled F / C / test (sealed dir). v4_t2_e1, h4, v6_t2: no holdout. |
| Baselines | seed |
| Gold | `<tree>/_run/tasks/*/tests/{verify.py,expected.json}`; trial `verifier/reward-detail.json`. Allowed: F-split verifier output. Forbidden: C / test material and `expected.json`. |
| Isolation | none |
| External state | `$PARSEC_V*N/_run/`: `jobs/`, `logs/sims/parsec-live.log` (**the cost source**), `h4-lanes/`, `v6-queue/`; `<proj>.sealed/`; the podman image. |
| Sources | cluster LSF logs (`$CCC_LOGS`); `skillberry-runs/parsec` (= `parsec-history`); `records/parsec-v6-g2-and-tmrg` (unmerged; two records whose content differs from the `benchmark-history` versions: archive both). |
| Reproduce | code commit **before `aeee7126d`**; private task bundles (MD5s in `build_v6_tree.py`); the podman image tar. |
| Licence | private; none stated. |
| Secrets | `config.local.yaml` LiteLLM key; `LLM_API_KEY`. |

### B.10 `toy` — `benchmarks/toy/examples/{calc,skill}`

| Key | Value |
|---|---|
| Reward | exact match: binary. |
| Cost | real $0 (`zero_means: zero`). |
| Splits | core ratios. |
| Gold | `target`, which also appears in the feedback (allowed). |
| Optimizer | mock (no transcripts: `not-produced`). |
| External state | `/tmp/toy_*`. |
| Licence | in-repo. |

### B.11 `generic-jsonl`, `generic-hf` — `benchmarks/generic/{jsonl_litellm,huggingface_litellm}/template`

| Key | Value |
|---|---|
| Reward | exact / contains / regex: binary. |
| Cost | litellm `response_cost`, 0 when unpriced (`zero_means: unknown`). |
| Telemetry | `tokens` only. |
| Splits | core ratios. For HF, `HF_SPLIT` (default `test`) is re-split by core: name both. |
| Gold | the `target` field (`TASKS_FILE`, or `TARGET_FIELD`). |
| External state | the HF cache. |
| Reproduce | dataset revision is not pinned: snapshot the dataset with its fingerprint. |
| Licence | user data, or the dataset card. |

### B.12 `tau2-custom-airline` (retired) — code at `5e570d29f^:examples/tau2_custom/{direct,blackbox}`

tau2 airline on the `skillberry-benchmarks` fork of tau2, with the `direct` and `blackbox` arms. Code:
`5e570d29f^:examples/tau2_custom/`. CI tiers: `8860d243a^:ci/benchmarks/tau2_custom/`.

| Key | Value |
|---|---|
| Bench names | `tau2_custom_direct`, `tau2_custom_blackbox`, `tau2_custom_spa`, `skillberry_tau2_direct`, `skillberry_tau2_spa`. `spa` and `blackbox` name the same arm. `<setting>` = the arm, `direct` or `blackbox`. |
| Reward | as `tau2-airline` (tau2 reward, binary per trial; pass^k). |
| Infra rule | as `tau2-airline`. |
| Telemetry, cost | as `tau2-sierra-airline`; the blackbox arm's agent cost is not measured. |
| Splits | `split_ids.json` 25 / 12 / 13 (seeded 0.5 / 0.25 / 0.25 over the 50 airline tasks); `smoke_split.json`; `split_ids_task9.json`. CI smoke: 10 tasks. |
| Baselines | seed |
| Capability | `tools` (the agent's tool surface); blackbox: the store skill `my_skill` + `primitive_tools/`. |
| Gold | `runner_repo_path: ../../vendor/skillberry-benchmarks` (tau2 fork): task definitions and reward checks are readable by the optimizer (allowed by design for train/val, as in B.3). Forbidden: test ids. |
| Isolation | none |
| Models as used | native results `info.*.llm`. The yaml says optimizer `claude-opus-4-6`; the CI records say `claude-opus-4-8`: a B2 item. |
| External state | `vendor/skillberry-benchmarks` (at `BENCH_REF`, recorded as `BENCH_SHA` by `setup.sh`), blackbox services as in B.3. |
| Sources | `benchmark-history` `records/*tau2_custom*`, `*skillberry_tau2*`; `runs/*/ui`; `live/<run_id>__<tier>-<bench>/data` (live-monitor snapshots, partial exports); branches `ci_skillberry_benchmarks_tau2*`, `rename_intervention_spa_to_blackbox`, `remove_ci_all`, `blackbox_require_make`. All are CI runs, so the owner is the workflow's triggering actor. |
| Reproduce | the code commit of the run (`runmeta.sha`); `skillberry-ai/skillberry-benchmarks` at `BENCH_SHA`; store and SPA SHAs as in B.3. |
| Licence | not recorded |
| Secrets | as B.3. |

`tau2_blackbox` (branch `tau2_vanilla_blackbox`; CI tier at `8860d243a^:ci/benchmarks/tau2_blackbox`)
is the blackbox arm on **vanilla** tau2, with tailoring applied from outside. It is
profiled as `tau2-sierra-airline`, setting `blackbox`.

### B.13 `epic-creator` (retired) — no adapter in any cap-evolve branch

| Key | Value |
|---|---|
| Bench names | `epic-creator`; experiment `epic-intake-v1`. |
| Run | `benchmark-history/runs/203__full-epic-creator/`: `baseline.json`, `final.json`, `state.json`, `report.md`, `candidates/`, `work/`, `rollouts/`, `ui/`. Made on `/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_epic-intake-v1`. Owner: `avalappi`. |
| Reward | per case `score.raw.verdicts`: deterministic checks (`budget_check`, `artifact_contract`, `dag_valid`, `implementation_type_rules`, `mandated_acceptance_criteria`, `run_report_consistent`, `review_discipline`, …), combined into a reward in [0, 1]. Success: reward = 1. Group metric: per check (pass rate of each verdict). The first backup confirms the combination rule from the adapter. |
| Infra rule | published: drop (core default). |
| Telemetry | `cost_usd` per rollout; `tokens` = 0 (`not_recorded`); `metadata.{segments, exit_code, seed}`. |
| Cost | agent: `cost_usd`, CLI-reported (the agent is GLM 5.3 in a Claude Code harness; budget cap $40 per case). Optimizer: `state.json` `spent.optimizer_usd`. A judge, if one is used: not recorded (`aux_call` null). |
| Splits | `splits.json` in the run; test n = 21. |
| Baselines | seed |
| Capability | skill package |
| Gold | the test cases' expected artifacts and review criteria. **Location unknown**: in the adapter's project, which is not in the repo. |
| Isolation | none known |
| Models as used | agent GLM 5.3 (Claude Code harness); optimizer GLM 5.3 via the PriceTag AI Gateway (record). Confirm from transcripts. |
| External state, sources | the run dir and project on the owner's machine (`may_exist_at`: the path above, and the ACE repo); `benchmark-history` record `203__full-epic-creator`. The git copy has rollouts but no transcripts or adapter, so expect `partial-export`. |
| Reproduce | adapter and project code: gap until found. Agent and optimizer endpoints are unpinnable. |
| Licence | not recorded |

### B.14 `epic-decompose` (retired) — no adapter in any cap-evolve branch

As `epic-creator` (B.13), except:

| Key | Value |
|---|---|
| Bench names | `epic-decompose`; experiment `epic-glm53-v5`. |
| Run | `benchmark-history/runs/202__full-epic-decompose/`: `candidates/`, `work/`, `rollouts/`, `ui/`, `epic-run/` (candidate skills `epic-decompose/SKILL.md` with `prompts/{decompose,fetch,review}-agent.md`). Made on `/Users/avalappi/Documents/ET/ACE/cap-evolve/.capevolve/run_epic-glm53-v5`. No `state.json` or `final.json` in the git copy. |
| Reward | checks plus a judge ("judge overflow fixed in this run", record note). Test n = 10. |
| Cost | as B.13. The record notes the optimizer hit GLM 5.3's 275k context limit: a C4 (truncation) item. |

### B.15 `rh-swebench` (retired) — Harbor on SWE-bench Verified

Values as B.7 (`swebench-verified-harbor`), except:

| Key | Value |
|---|---|
| Bench names | `rh-swebench`; runs `manual__full-rh-swebench-v4` and `manual__full-rh-swebench-v4__full-rh-swebench` (`<setting>` = `v4`). |
| Reward | resolved, on 119 SWE-bench Verified tasks. The published result is val, **a fit metric** (`results/rh-swe-bench-image-and-reorder` README: 0.580 → 0.765). |
| Capability | skill package + system prompt |
| Models | agent `claude-sonnet-4-6`, optimizer `claude-opus-4-6` (record). |
| Cost | `eval_usd` 0 in the record: unknown, not $0 (`zero_means: unknown`). |
| Sources | `benchmark-history` `runs/manual__full-rh-swebench-v4*/ui` (UI exports, `compare_ids_*`), `records/manual__full-rh-swebench-v4.json`; branch `results/rh-swe-bench-image-and-reorder` (`site/results.html`, `site/assets/rh_swe_bench.png`). Owner: `avalappi`. The full run dir is on the owner's machine (`may_exist_at`). |

Runs `200`, `201`, `202__full-swebench-verified` (bench name `swebench-verified`; `ui/` only; made in
`/private/tmp/ce-runs/s<k>/run_suite` by `avalappi`) are profiled as `swebench-verified-harbor`
(B.7), with `<replicate>` = `s<k>`. Their adapter at the run's commit is confirmed at the first
backup.

### B.16 Bench names → profile

Every bench name seen in the repo, CI and results maps to exactly one profile:

| Bench name (CI, records, run dirs) | Profile |
|---|---|
| `appworld` | B.1 `appworld` |
| `tau2` | B.2 `tau2-airline` |
| `tau2_sierra`, `tau2_sierra_blackbox`, `tau2_blackbox`, `sierra`, `direct`, `blackbox` (run-dir names under the sierra example) | B.3 `tau2-sierra-airline` |
| `skillsbench` | B.4 `skillsbench` |
| `spreadsheetbench` | B.5 `spreadsheetbench` |
| `swe_bench` (local template) | B.6 `swebench-lite` |
| `swebench` (CI), `swebench-verified` | B.7 `swebench-verified-harbor` |
| any other Harbor dataset | B.7 `harbor-<dataset>` |
| `rfe-creator`, `rfe_creator` | B.8 `rfe-creator` |
| `parsec` | B.9 `parsec-rca` |
| `toy` | B.10 `toy` |
| `jsonl_litellm`, `huggingface_litellm` | B.11 `generic-jsonl`, `generic-hf` |
| `tau2_custom_direct`, `tau2_custom_blackbox`, `tau2_custom_spa`, `skillberry_tau2_direct`, `skillberry_tau2_spa`, `spa` | B.12 `tau2-custom-airline` |
| `epic-creator` | B.13 `epic-creator` |
| `epic-decompose` | B.14 `epic-decompose` |
| `rh-swebench`, `rh-swebench-v4` | B.15 `rh-swebench` |

A bench name not in this table gets a new profile (§4) before its runs are captured.

## Appendix C. User ids

The same ids are used under both roots. On 2026-11-12, the old root had folders for `boazc`,
`eranra`, `erezh` and `osher.elhadad`. The new root was empty.

| Person (e-mails, GitHub logins) | `<user-id>` |
|---|---|
| Boaz Carmeli — `boazc@il.ibm.com`, `bcarmeli`, `boazc` | `boazc` |
| Eran Raichstein — `eranra@il.ibm.com` | `eranra` |
| Erez Hadad — `erezh@il.ibm.com` | `erezh` |
| Osher Elhadad — `osher.elhadad@live.biu.ac.il`, `OsherElhadad` | `osher.elhadad` |

Expected new ids (§2.1):
- `AIMikav` / Anamika (`avalappi@redhat.com`, `44390109+AIMikav@users.noreply.github.com`) → `avalappi`.
  This is the owner of the `epic-creator`, `epic-decompose`, `rh-swebench` and `swebench-verified` runs.
- `yyualvin` → `yyualvin`. Record each new id in `BACKUP_RESULTS_<TS>.md`. This table is updated by a change
proposal (Rules).
