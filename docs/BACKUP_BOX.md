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
  wrong, say so in `BACKUP_RESULTS_<TS>.md`, apply the corrected rule there explicitly, and open an
  issue that proposes the change to this document. Benchmark profiles (`docs/backup_profiles/`) are
  not part of this procedure: they are created and corrected as Appendix B says.
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
- **Profile.** The per-benchmark facts this procedure needs: one file per benchmark in
  `docs/backup_profiles/` (§4, Appendix B).
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

`<bench-id>` is the id of the benchmark's profile. Map every bench name to its id with the table in
`docs/backup_profiles/INDEX.md`, so that names are never confused. For example,
`benchmarks/swe_bench` is `swebench-lite`, while CI `swebench` runs the Harbor adapter and is
`swebench-verified-harbor`. A bench name that is not listed gets a new id
and a new profile (§4, Appendix B.2).

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
  logs, the git snapshot), and `<bench-id>/` folders.
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
  README.md  NOTICE.md  PROFILE.md  runmeta.json  MANIFEST.json  SYMLINKS.txt
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

Every benchmark difference this procedure needs is in that benchmark's profile, a file in
`docs/backup_profiles/`:
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

The procedure steps are the same for every benchmark; only the profile values differ. Profile values
that every benchmark shares are in `docs/backup_profiles/_core.md`.

**For each run, before capturing it:**
1. **Look the profile up.** Find the run's bench name in `docs/backup_profiles/INDEX.md`, and load the
   profile it names, together with `_core.md`.
2. **If there is no profile,** create one as Appendix B.2 says. Use it for this backup, and propose it
   in a pull request.
3. **Check the profile, the first time it is used in a backup,** against that run:
   - every path and field it names exists, or is explained;
   - every source of the run maps to a profile key;
   - every `unverified` value is now settled, if the run settles it.

   If anything is wrong or missing, correct the profile as Appendix B.3 says. Otherwise record
   `profile checked against <run>` in `BACKUP_RESULTS_<TS>.md`, and set the profile's status in
   `INDEX.md` the same way.
4. **Record the profile used** in the run folder (`PROFILE.md`) and in `runmeta.profile`
   (Appendix B.4).

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
  here.
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
profile: {bench_id, path: "docs/backup_profiles/<bench-id>.md", commit, sha256, state: as-is|corrected|new}
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

## Appendix B. Benchmark profiles: format, and how to create or correct one

Profiles are files in `docs/backup_profiles/`:
- one file per benchmark id, `<bench-id>.md`;
- `_core.md`, the values every benchmark shares (they come from cap-evolve's core);
- `INDEX.md`, which maps every bench name to its profile file and records each profile's status.

The profiles are not part of this procedure, and they are not read-only. They are corrected and
extended through pull requests.

### B.1 Format

A profile starts with a title line, `# Backup profile: \`<bench-id>\` — <where the code is>`, then
a pointer to `_core.md` and a one-line description. It then has a two-column table (`Key | Value`)
with the keys below, in this order. Every key is present, and its value is exactly one of:
- the value itself;
- `as _core.md`, or `as <other-profile>`;
- `not applicable: <reason>`;
- `unverified: <what was found> — <why it could not be confirmed>`.

| Key | What it holds |
|---|---|
| Bench names | every name the benchmark appears under (CI bench, record `bench`, repo dir, run-dir names), and the closed list of `<setting>` values (§2.3) |
| Code | the adapter and config paths, at the commit where they exist |
| Reward | the primary reward and its range; the **success** criterion; the second-level (group) metric and its grouping key; secondary metrics; where the published metric's name is recorded |
| Infra rule | the rule the published results used (`drop` or `fail`, or something else, stated); the detectors that mark an episode as infra-errored |
| Telemetry | for each of prompt tokens, completion tokens, latency, steps and termination: where it is recorded, or `not-produced` |
| Cost | for each category (agent, usersim, judge, simulator, proxy, optimizer): its source, whether it is measured, reported or estimated, and `zero_means: zero` or `zero_means: unknown` |
| Splits | the split files or rules, their sizes, and whether there is a held-out split |
| Baselines | every baseline arm the benchmark uses, and how to tell which one a run used |
| Capability | what the optimizer edits, and how it is delivered to the agent |
| Gold | gold paths and file names; gold carried inside records; `allowed_to_optimizer`; `forbidden`; false-positive grep terms |
| Isolation | the isolation mechanism and its evidence files, or `none` |
| Agent evidence | where to look to check that the agent under test did not touch gold |
| Models as used | the record that gives each model as actually used, per role |
| External state | every location outside the run dir that the run writes or reads, each marked `volatile` when it expires or is overwritten |
| Sources | other hosts, archives, git sources, results repo, gateway ledgers, posts |
| Reproduce | launch files; data to copy; upstream clones and where their commits are recorded; services; images; environment freezes; `unpinnable` items; the smoke command (E5) |
| Licence | the licence of each data source; restrictions and protected paths (for `NOTICE.md`) |
| Secrets | secret locations beyond the host's secret files (for example tokens on command lines, keys in service configs) |

**Locations.** Together with `_core.md`, the keys **Code**, **External state**, **Sources** and
**Reproduce** must name every place where the benchmark's runs leave data. Check them against these
categories, and name concrete paths, with each volatile one marked:
1. code and configs (adapter, configs, split files, launch scripts, CI tiers);
2. run dirs and sealed dirs;
3. session transcripts of every CLI involved (optimizer, an agent under test that is a CLI, judges);
4. harness, service and evaluation state (job dirs, native results, window results, databases);
5. clones, caches, datasets and container images;
6. logs (progress, service, proxy);
7. other hosts and archives;
8. git sources and results repos;
9. posts (issues, PRs, workflow runs);
10. gateway and proxy usage ledgers;
11. docs (plans, results pages).

A category the benchmark does not use is `not applicable`. A location that the sources name but that
cannot be found is `unverified`, with where it may be (`may_exist_at`).

### B.2 Creating a profile

Do this when a run's bench name is not in `INDEX.md` (§4). Use the benchmark's code **at the run's
own commit**.
1. **Choose the id.** Lowercase with hyphens, naming the benchmark and, when one benchmark has
   several environments, the environment (for example `tau2-airline`). It must not be an id already
   in `INDEX.md`.
2. **Read the sources, in this order:**
   1. the adapter (`tasks`, `run_target`, `score`, and the rollout metadata it writes);
   2. `capevolve*.yaml` and the split files;
   3. `setup.sh`, `run.sh` and any launch scripts;
   4. the CI tier: `ci/benchmarks/<bench>/<tier>/` (`overrides.env`, `split_ids.json`) and the
      bench's branch of `ci/benchmarks/lib/run_suite.sh`;
   5. the optimizer instructions;
   6. the benchmark's README and docs;
   7. one real run of the benchmark: rollout files, events, and the external dirs it names.
3. **Fill every key of B.1, and cover every location category.** Next to each value, cite its evidence as `path:line`, or as the run path.
   Where a value equals core's, write `as _core.md`. Where it equals another profile's, write `as
   <profile>`. Never guess: a value the sources do not settle is `unverified`, with what was found.
4. **Save it.** Write it to `docs/backup_profiles/<bench-id>.md`, add its bench names to the `INDEX.md`
   table and its row to the status table (`draft, checked against <run>`), and open a pull request
   for both. Use the new profile for this backup without waiting for the merge.

### B.3 Correcting a profile

When the check of §4 finds a value that is wrong or missing:
- edit the profile file;
- set its `INDEX.md` status to `checked against <run>, corrected`;
- list each correction, with its evidence, in `BACKUP_RESULTS_<TS>.md`;
- open a pull request.

Use the corrected profile for this backup.

### B.4 Recording which profile was used

Copy the profile used for a run into the run folder as `PROFILE.md` (a source copy). Record it in
`runmeta.profile` (Appendix A.1): the bench id, the repo path, the commit it was read at (or
`uncommitted`), its sha256, and its state (`as-is`, `corrected` or `new`).

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
