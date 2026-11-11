# Evaluation-run backup to Box: plan

A generic procedure for the end of an evaluation campaign. Find every evaluation run on the host,
capture each one in full, organize it as a self-contained folder tree, verify it, and copy it to the
Box archive with `rclone`. The whole operation is timed.

**Rules for the executing agent**
- **This document and `docs/VERIFICATION_SCAN.md` are read-only.** Never edit them. Everything you
  learn, decide or measure goes into the result documents:
  - `SCAN_RESULTS_<TS>.md`, one in each run folder (§6, written by the verification scan);
  - `BACKUP_RESULTS_<TS>.md`, one at the root of `eval-data:` (§9).
  `<TS>` is a full UTC timestamp, `YYYYMMDDTHHMMSSZ`, taken when that step starts.
- Comprehensiveness comes before speed. Do not leave out data that belongs to a run because it is
  large, odd or in an unexpected place.
- Never delete anything on Box: use `rclone copy`, never `sync` or `purge`. Never change or delete a
  source on the host.
- Never upload secrets. Ask the owner before uploading anything whose licence or sensitivity is
  unclear.

---

## 1. Discover the evaluation runs

Do not assume a list; build one from evidence. Search at least:
- **cap-evolve run dirs:** every `run_*` dir that contains `events.jsonl` and `state.json`, under any
  `.capevolve/` on the host (`find / -xdev -path '*/.capevolve/run_*' -name events.jsonl`). Include the
  sibling `project/`.
- **Other methods' run dirs** (baselines, competitor methods): look for their stores, pipelines and
  logs, guided by the docs below.
- **Evaluation docs** in the repository and its branches: plans, appendices, ledgers, results pages
  (`docs/EVAL_*`, `docs/experiments/`). The tracking issues and PRs they name.
- **Final or held-out windows** that score several arms together: results, frozen artifacts, analysis.
- **Optimizer and orchestrator sessions:** `~/.claude/projects/*`, `/tmp/claude-<uid>/*`,
  `~/.claude/file-history/*`, `~/.claude/session-env/*`, the host agent's journals, and any
  transcript directory a run's wrapper redirected to.
- **Progress logs, launch scripts, probes and acceptance checks**, and any copies of data that agents
  made during a run.

For each candidate decide: **is this an evaluation run, and which?** A run is one method trained or
measured on one benchmark with one configuration. Several training attempts made under the same plan
for the same purpose (for example a re-run after a fix) may be grouped as attempts inside one run
folder, each labelled with its status. Record the full list, what was grouped and why, and **every
candidate you excluded, with the reason**, in `BACKUP_RESULTS_<TS>.md`. If a run's data is only
partly on this host, back up what is here and say what is missing and where it lives.

## 2. Names on Box

```
eval-data:<benchmark>/
  <start-date>-<benchmark>-<method>-<key-setting>-<agent-model>-<optimizer-model>-<status>/
```

This follows the repo's archive convention (`docs/experiments/<date>-<bench>-<…>-<models>/`).
`<status>` says whether the run's result stands (for example `scored`, `discarded`, `breach`,
`invalid`), so it must reflect the verification scan (§6). Use plain ASCII only, with no spaces.

## 3. Folder tree of a run

Follow `docs/experiments/` and the CI artifact layout. Keep cap-evolve's own trees **unchanged**, so
its tools can load the backup.

```
<run>/
  README.md        what the run is, its status and outcome, how to read this folder, its caveats
  NOTICE.md        licence or redistribution notes for the data in it (if any)
  MANIFEST.json    every file: relative path, bytes, sha256
  runmeta.json     run identity in the CI schema (.github/workflows/benchmarks.yml: run_id, bench, tier,
                   models, providers, algorithm, iterations, trials, gate_k_se, sha, dates, conclusion)
  SCAN_RESULTS_<TS>.md   the verification scan's findings for this run (§6)
  data/            metrics.jsonl, steps.jsonl, report.md (ci/benchmarks/lib/metrics.py suite)
                   + metrics_full.jsonl (§4) and its README, rendered as metrics_full.md/.html
                   + metrics_summary.json/.md: high-level reward and cost, candidate and baseline (§4)
  capevolve/       project/ + run_<name>/ exactly as on disk (incl. .git, work/, rollouts/, candidates/)
  champion/        the scored artifact + capability.diff vs the seed
  rounds/rN_<id>/  per round: verdict (from events), diff.patch, the optimizer's PROCESS/DIAGNOSIS notes
  <method>/        a non-cap-evolve method's run dir as it was, unchanged
  host/            the optimizer as an agent: launch args, instructions received, every session transcript
                   (incl. subagents), file-history, session-env, task outputs, stderr
  final_window/    the held-out window this run owns or shares: frozen artifacts with hashes, results,
                   analysis. A shared window goes into each run that it scores, and each copy says so
  isolation/       isolation evidence: scans, checks, audit scripts, anything an agent copied
  logs/            progress logs and console output of this run
  posts/           the public record: every comment on the tracking issue(s) as .md, with id, URL and
                   timestamps, from the API; the full thread as JSON; local drafts; linked issues and
                   PRs as JSON
  docs/            the plans, appendices and result pages as of the backup commit
  env/             manifests, data hashes, patches, reference material, the example code, launch scripts
  reproduce/       everything a repeat needs (§5)
  attempt*/        when a run groups several training attempts: one sub-tree each, as above, labelled
```

Ledgers, journals, insights, rejected/accepted history, dashboards and per-candidate workdirs are part
of the run: copy them all. Symlinks cannot be stored on Box, so list every one with its target in
`SYMLINKS.txt`.

## 4. Metrics

Every run folder has `data/metrics_full.jsonl` with **reward, tokens, latency and cost** in one
place, one row per:
- held-out episode: reward, prompt/completion tokens, latency, steps, termination;
- search round or pipeline step: search-set reward, accepted, optimizer tokens, optimizer USD,
  optimizer and evaluation time;
- optimizer call, where a method logs calls;
- run total.

Each value carries its **source**: measured, reported by a tool, or **estimated**, with the price
used. If a cost is not available, write `null` with the reason (for example an unpriced endpoint).
Never write `0` for an unpriced cost. Cross-check the episode rewards against the published results.

Every run folder also has `data/metrics_summary.json` and `data/metrics_summary.md`, written from
`metrics_full.jsonl` during the verification scan (`docs/VERIFICATION_SCAN.md` §D4). They give, for the
run's candidate and for the baseline: the champion's train (search) and test reward (TGC, SGC), the
token and USD cost of the train and test phases, and the total and average cost per task (all,
successful, failed) for train, test and both. The baseline entry is computed once per window and is
identical in every run that the window scores.

## 5. Reproducibility

A run folder must hold enough for someone else to **repeat the run elsewhere**: the same procedure,
configuration and inputs, not necessarily the same numbers. `reproduce/` holds:
- **code:** a git bundle containing every commit any run used (`git bundle verify`; check out each
  one), and `code_commits.json` mapping each run or attempt to the commit in effect. Find that commit
  from the run's start time and from byte comparison of the run's code copies. Code that was never
  committed must be recovered (from transcripts, copies or history) and checked byte for byte against
  whatever copy survives;
- **data:** benchmark version, download method, tree and split hashes. Copy the data only if its
  licence allows;
- **environments:** exact package freezes, interpreter versions, tool versions;
- **models:** every model **as actually used**, taken from the transcripts and logs, not from the plan.
  This includes the optimizer's subagents and any setting the CLI inherited (such as
  `CLAUDE_CODE_SUBAGENT_MODEL`, effort and thinking). Also the endpoint, sampling parameters and
  seeds;
- **inherited config:** the user settings the CLIs inherit, redacted;
- **host:** OS, kernel, container facts relevant to the run (for example isolation behaviour);
- **orchestration record:** the session(s) that ran the evaluation, redacted;
- **`REPRODUCE.md`:** the steps in order, for this run.

Check every hash in `reproduce/` against the files it describes.

## 6. Verification scan

Run **`docs/VERIFICATION_SCAN.md`** on every assembled run folder before upload. It writes
`SCAN_RESULTS_<TS>.md` into each run folder. If the scan finds something that changes a run's status,
change the folder name (§2) and the README to match, and say so in `BACKUP_RESULTS_<TS>.md`. Never
hide a finding by leaving data out.

## 7. Before upload

- Run the cap-evolve tools on the backup copy, read-only:
  - `cap-evolve tail <run_dir> --from-start --idle-timeout 5` must exit 0;
  - `RunDir.open` + `dashboard.reduce_run` + `render_html` must succeed.
  Do not use `dashboard --export`: it overwrites the run's `dashboard.html`.
- **Completeness:** every regular file of every source tree that belongs to a run must have a
  byte-identical copy (same sha256) in that run's folder.
- **Secret scan:** 0 occurrences of any key, token or header value from the host's secret files or
  environment, in any file.
- Write `MANIFEST.json` last.

## 8. Upload and timing

### 8.1 Check the rclone setup (before T0, not timed)

The upload uses the remote `eval-data`, an `alias` of the `box` remote pointing at the user's folder in
the archive: `box:cap-evolve-paper-data/user/<user-id>`. The prefix `cap-evolve-paper-data/user/` is
fixed. `<user-id>` is the folder under which this user's evaluation runs are filed (for example
`erezh`). Check each part in this order, and build or fix only what is missing. Never print a token:
show only remote names, types and the alias target.
1. **rclone installed.** If missing, install the official release, checksum-verified, at least two
   weeks old, user space only.
2. **`box` remote exists** (`rclone listremotes --long` lists `box:` with type `box`). If it is
   missing, ask the user to create it: `rclone config create box box` needs a browser login, which
   only the user can do. On a host without a browser, the user runs `rclone authorize "box"` on a
   machine with one and pastes the token into the prompt. Wait for the user to say it is done.
3. **The `box` token is valid.** Make one read-only call that needs a token, for example
   `rclone lsd box: --max-depth 1`. If it fails with an authentication error (`invalid_grant`, `token
   expired`, `401`), ask the user to run `rclone config reconnect box:` and log in. Wait for the user,
   then repeat the call. Do not start the capture until it succeeds. A stale token found only at
   upload time leaves a finished capture waiting.
4. **The user's folder exists on Box.** If `eval-data` already exists and points at
   `box:cap-evolve-paper-data/user/<user-id>` (check 5), confirm that `<user-id>` with the user and go
   to check 5. Otherwise:
   - list the existing user folders: `rclone lsd box:cap-evolve-paper-data/user`;
   - ask the user to choose their id from that list, with one more choice, **other**, for a user who
     is not listed. For **other**, ask for the id: plain lowercase ASCII, no spaces, matching the
     convention of the existing ids;
   - for a new id, create the sub-folder after the user confirms the name:
     `rclone mkdir box:cap-evolve-paper-data/user/<user-id>`, then check it with `rclone lsd`.

   Never create, rename or delete anything else under `cap-evolve-paper-data/`, and never file one
   user's runs under another user's id.
5. **`eval-data` remote exists** with type `alias` and `remote = box:cap-evolve-paper-data/user/<user-id>`
   (`rclone config show eval-data` prints only that, since an alias holds no secret). If it is missing,
   create it with `rclone config create eval-data alias remote=box:cap-evolve-paper-data/user/<user-id>`.
   If it points elsewhere, ask the user before changing it.
6. **End to end:** `rclone lsd eval-data:` lists the archive. Then copy a small test file to
   `eval-data:` and `rclone check` it, or confirm that an earlier backup's results file is listed
   there.

Record in `BACKUP_RESULTS_<TS>.md` what was found, what was built or fixed, and every step where the
user was asked to act. Box tokens expire. Before the first `rclone copy`, repeat check 3. If it
fails, ask the user to reconnect, and record the wait between T1 and the transfer.

### 8.2 Upload

```
T0  start of capture         discover, assemble, derive, scan, verify
T1  end of capture
    rclone copy <run> eval-data:<benchmark>/<run>   per run, --transfers 8 --checkers 16, log per run
T2  end of transfer
    rclone check <run> eval-data:<benchmark>/<run> --one-way   (Box keeps SHA-1: content check)
T3  end of verification
```

Upload folder trees as they are, uncompressed. `rclone check` must report 0 differences and 0
missing files for every run. Record T0–T3, per run and in total, with file and byte counts. If data is
added later (a second pass), time that pass separately and report both passes.

## 9. Backup results

Write `BACKUP_RESULTS_<TS>.md` (`<TS>` = when the backup started) and upload it to the **root** of
`eval-data:`. It records:
- what was searched, which runs were found, and how they were grouped and named;
- every excluded candidate, with the reason;
- per run: Box path, files, bytes, status and its reason (with a pointer to that run's
  `SCAN_RESULTS_<TS>.md`);
- timing (§8), per pass and in total;
- verification outcomes: tool checks, completeness, secret scan, `rclone check`;
- decisions taken with the owner, and anything still open;
- issues met during the backup, and how each was resolved.
