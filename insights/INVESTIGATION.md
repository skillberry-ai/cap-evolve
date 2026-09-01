# SkillsBench task-by-task — insights, findings, and open investigations

Consolidated after the 2026-08-22 update covering task-by-task-20 (batch 1 +
batch 2 + Track A + v7 podman fix reruns).

## Headline

Task-by-task cap-evolve on SkillsBench (each task gets its OWN cap-evolve
process with the task's OWN shipped skills as seed) delivers **+23.0 pp
average lift across 20 tasks (0.577 → 0.807)**. Compared to whole-suite
optimization on the same 10 batch-1 tasks (+7.3 pp), task-native seed is
**~3× more effective in aggregate lift**.

- 9 of 20 tasks lifted from seed to val=1.0 by the optimizer.
- 4 of 20 already saturated at baseline (val=1.0 seed).
- 3 of 20 landed at 0.4-0.85 (partial lift).
- 2 of 20 stuck at 0.000 through 2 iterations.

## Insight 0 — the v8 podman fix (2026-08-25): unblocking 44 more tasks

**Problem:** After task-by-task-43 finished, 44 SkillsBench tasks were
still blocked by CCC's rootless-podman constraints — same `_apt`-user
`seteuid 42` failure that ubuntu:24.04-v2 originally fixed, but on
different base images:

- **29 python:3.x-slim** tasks (26× `python:3.12-slim`, 2× `python:3.11-slim`,
  1× `python:3.12.8-slim`) — direct debian-slim `apt-get install` fails
  before any task-specific setup runs.
- **10 ubuntu:24.04 heavy-dep** tasks (Java Druid, Erlang OTP, Java Flink,
  Playwright browsers, Lean 4 toolchain, PDDL planning, LibreOffice+gnumeric,
  Node/React) — v7 base applies, but each still had per-task quirks worth
  trying to run.
- **5 misc-base** tasks — `ubuntu:20.04`, `bugswarm/cached-images`,
  `gcr.io/oss-fuzz-base/base-builder-python`, `jasonish/suricata:7.0.11`.

**Fix (v8 of the patched base images, `_patch_slim_base` helper in
[`setup_podman.sh`](../../scripts/ccc/setup_podman.sh)):**

- Refactored the v7 ubuntu:24.04-specific Dockerfile block into a shell
  function `_patch_slim_base <base_tag> <marker_name>` that applies the
  same recipe (apt-sandbox-user root, chown/adduser/dpkg-statoverride
  wrappers, TAR_OPTIONS=--no-same-owner, uv-preinstall at both
  `/usr/local/bin` and `/root/.local/bin`) to any Debian-based image.
- Added apt-installed `curl` and `ca-certificates` at the start of the
  helper — python-slim images ship without either, and the uv installer
  needs both.
- Applied to: `python:3.12-slim`, `python:3.11-slim`, `python:3.12.8-slim`,
  and `ubuntu:20.04`.
- ubuntu:24.04 v7 block kept as-is (still has task-shared heavy preinstalls
  `poppler-utils build-essential` which python-slim tasks don't need).

**Verification:** bike-rebalance's downstream image (FROM python:3.12-slim,
apt-installs bash+ca-certificates+curl+libgfortran5, pip-installs
pytest+pyscipopt) now builds cleanly. First live rollout
(econ-detrending-correlation seed_t0) verified end-to-end on the v8 image
at reward=1.0 (4/4 pytest passing).

**Impact:** 44 tasks unblocked at the image-build layer. Runtime failures
still possible per-task, but the systemic "can't apt-install anything"
class is now solved for these bases too.

**PR:** [`bcarmeli/cap-evolve` `add-python-slim-base-support`](https://github.com/bcarmeli/cap-evolve/tree/add-python-slim-base-support),
branched off `add-ccc-support`.

**Cache invalidation note:** the cache-key bug from v7 (Layer 3 of
Insight 3) means cap-evolve caches from pre-v8 runs may collide with
fresh v8 evaluations. For c2 tasks re-run in c3 with v8, ensure the
run dir is fresh (different `--run-ts`) OR rename any stale
`.bench_runs/.../<task>__<hash>/` subdirs (all 10 seed dirs, not just
seed0) with a `_STALE_pre_v8` suffix before submitting.

### 2026-08-25 landing of the 44-task push in c3

Submitted 44 tasks task-by-task with `--max-iterations 4` on dedicated
LSF hosts.

**Buckets 1–3 baseline classification (as of ~11:00 UTC):**

- **11 saturated at seed val=1.0** (killed per standing rule; run dirs
  renamed `_KILLED_saturated_1.0`): dialogue-parser,
  econ-detrending-correlation, exoplanet-detection-period,
  gravitational-wave-detection, llm-prefix-cache-replay,
  mario-coin-counting, mars-clouds-clustering, parallel-tfidf-search,
  pddl-tpp-planning, powerlifting-coef-calc, radar-vital-signs.
- **12 with real signal (0.1–0.998)** — optimizer has room:
  lab-unit-harmonization (0.998), earthquake-plate-calculation (0.90),
  lean4-proof (0.90), tictoc-unnecessary-abort-detection (0.885),
  manufacturing-fjsp-optimization (0.80),
  manufacturing-equipment-maintenance (0.70),
  react-performance-debugging (0.60), debug-trl-grpo (0.425),
  civ6-adjacency-optimizer (0.31), software-dependency-audit (0.30),
  bike-rebalance (0.10), video-silence-remover (0.10).
- **3 baseline=0.0, genuinely hard for agent** (verifier ran, agent
  fails 1 of N strict checks — NOT infra-broken):
  - `azure-bgp-oscillation-route-leak` — 21/22 solution-classification
    tests pass; agent misses the RPKI origin-validation case.
  - `paratransit-routing` — agent produces routes serving 0 trips vs
    required 442 (≥95% of reference-solved).
  - `travel-planning` — Day-1 attraction returned as '-' (empty
    placeholder); other 9 tests pass.
- **7 baseline=0.0, infra-broken** (killed; run dirs renamed
  `_INFRA_BROKEN_baseline_0.0`):
  1. `fix-build-agentops` — `FROM bugswarm/cached-images:AgentOps-AI-*`
     hits uv-install tar-chown at STEP 10 (uid=1001/gid=117). Same
     tar-chown class we solved on ubuntu:24.04/python-slim, but on a
     third-party base we don't patch. **Fixable:** extend
     `_patch_slim_base` to bugswarm base tags. Task-specific — one
     tag per bugswarm-based task.
  2. `fix-build-google-auto` — multi-stage: `FROM bugswarm/... AS auto`
     + `FROM --platform=linux/amd64 ubuntu:20.04 AS final`. Second stage
     fails: `_apt` seteuid 100 in ubuntu:20.04 apt-get. Root cause:
     `--platform=linux/amd64` FORCES podman to auto-pull the vanilla
     remote ubuntu:20.04 for that platform, OVERWRITING our locally-
     patched tag mid-build. Our marker file survives, but the tag's
     contents (`/etc/apt/apt.conf.d/00-rootless`) are gone. `pull_policy
     = "missing"` in containers.conf does NOT prevent this — the
     `--platform` flag bypasses the policy.
     **Fixable options** (deferred):
     - patch benchflow's `docker.py` to pass `--pull=never` to the
       `podman build` invocation, so downstream builds cannot pull;
     - modify the two affected task Dockerfiles at build time to
       strip `--platform=linux/amd64` (task-data-modifying);
     - author a local buildah policy that pins by digest.
     Content-check in setup_podman.sh (added in commit `7c5b3314`)
     detects the overwrite on the NEXT setup run, but not within the
     same job.
  3. `glm-lake-mendota` — same `--platform=linux/amd64 ubuntu:20.04`
     overwrite issue as fix-build-google-auto.
  4. `setup-fuzzing-py` — `FROM gcr.io/oss-fuzz-base/base-builder-python`
     hits uv-install tar-chown at STEP 10 (same as agentops). Would
     need extending `_patch_slim_base` to the oss-fuzz base.
  5. `suricata-custom-exfil` — `FROM jasonish/suricata:7.0.11`
     (Fedora-based, dnf not apt). RPM cpio chown fails installing
     `wireshark-cli`: `error: unpacking of archive failed on file
     /usr/bin/dumpcap;6a8ddca7: cpio: chown failed - No data
     available`. Different failure class (rpm not tar). Fixable but
     needs different mechanism than the apt-family wrappers.
  6. `earthquake-phase-association` — `FROM python:3.12-slim`, apt +
     pip succeed (v8 works), then STEP 6 runs a Python inline script
     that downloads a PhaseNet ML model from `https://seisbench.
     github.io/` (with 6-retry backoff). Compute nodes without
     outbound access to that host fail all 6 retries. **Fixable:**
     pre-download the seisbench model into /dccstor and volume-mount
     into the container's `~/.seisbench/` cache dir; or run
     containerization on a login node that has network reach and
     export the built image.
  7. `fix-visual-stability` — task ships its own
     `docker-compose.yaml` with `networks: task-net` (a bridge
     network) that overrides our benchflow-level
     `network_mode: host` patch. Bridge → netavark → aardvark-dns
     → systemd (missing on compute nodes) → boot fails. **Fixable
     options** (deferred): patch this specific task's
     docker-compose.yaml to `network_mode: host`; or set up
     aardvark-dns via a userspace systemd substitute.

**Post-diagnostic active set:** 24 running (23 mine + 1 c2 391812) + 1
pending (energy-unit-commitment, waiting on LSF advance reservation) +
2 zombies (seismic-phase-picking + crystallographic-wyckoff-position-
analysis on unavail hosts — real progress on disk, will resume with
`--resume` after LSF reaps).

## Insight 1 — the v7 podman fix (2026-08-21)

**Problem discovered:** 8 of the initial 20 batch-2 tasks scored 0.000 across
seed + cand_0001 + cand_0002. Interpreted at first as "genuinely hard OOD
tasks" — but Track B diagnosis showed every one of them was infra-broken
inside the container:

```
/verifier/test.sh: line 8: /root/.local/bin/env: No such file or directory
/verifier/test.sh: line 15: uvx: command not found
```

Root cause: SkillsBench verifier test.sh scripts almost universally begin:

```bash
curl -LsSf https://astral.sh/uv/<ver>/install.sh | sh > /dev/null 2>&1
source $HOME/.local/bin/env
uvx --with pytest ... pytest ...
```

Two independent failure modes cause the install to fail silently:

1. **Compute nodes lack outbound access to `https://astral.sh`**. `curl` errors,
   `2>/dev/null` swallows it, `/root/.local/bin/env` never exists,
   `source` errors, `uvx: command not found`.
2. **When curl works, the tar-extract still fails** — Astral's uv tarball
   embeds file entries with uid=1001/gid=117 (uv's build user). Under
   rootless podman single-UID user namespace, `tar` fails with
   `Cannot change ownership to uid 1001, gid 117: Invalid argument`.

**Fix (v7 of the patched-ubuntu base image, in
[`../../scripts/ccc/setup_podman.sh`](../../scripts/ccc/setup_podman.sh)):**

- Pre-install `uv`/`uvx` to `/usr/local/bin` (system-wide).
- Pre-install `uv`/`uvx` **also** to `/root/.local/bin` at build time,
  including the verifier-expected `env` activation script (installer honors
  `HOME=/root`). This is what the verifier's hardcoded `source
  $HOME/.local/bin/env` uses.
- Set `TAR_OPTIONS=--no-same-owner` in the container env as a
  belt-and-braces fallback for other tar-based installers.

**Impact:** 6 of 8 previously "stuck at 0" tasks unblocked:

| task | pre-v7 | post-v7 best | change |
|---|---|---|---|
| `offer-letter-generator` | 0.000 | **1.000** (saturated at seed) | +1.000 |
| `threejs-to-obj` | 0.000 | **1.000** (saturated at seed) | +1.000 |
| `sec-financial-report` | 0.000 | **1.000** (0.9 → cand_0002 1.0) | +1.000 |
| `drone-planning-control` | 0.000 | 0.847 (seed 0.85) | +0.847 |
| `jax-computing-basics` | 0.000 | 0.500 (seed 0.5) | +0.500 |
| `paper-anonymizer` | 0.000 | 0.400 (seed 0.4) | +0.400 |
| `financial-modeling-qa` | 0.000 | 0.000 | 0 |
| `python-scala-translation` | 0.000 | 0.000 | 0 |

**Lesson:** always check verifier `test-stdout.txt` before treating an
all-zero task as "genuinely hard". Infra failure and genuine hardness are
indistinguishable from the reward-only signal.

**Not fixed by v7:**
- `python-scala-translation` — Scala/GraalVM native-image runtime crashes inside
  the container. Different infra class. Needs task-specific Dockerfile
  patch or a v8 base image with `openjdk-21` / `sbt` preinstalled.
- `financial-modeling-qa` — verifier now runs; agent produces output but
  verifier says wrong. Genuinely hard on task semantics.

## Insight 2 — Track A: iter 3-4 saved 2 of 3 partial-lift tasks

Batch 1 finished with 3 tasks at 0.9 or below despite showing real signal:
adaptive-cruise-control (0.7→0.9), multilingual-video-dubbing (0.7→0.9),
invoice-fraud-detection (0.3→0.4). Question: was max_iterations=2 too small?

Ran `--resume` on each with `max_iterations=4`. Result:

| task | seed | c2 (iter 2) | c3 (iter 3) | c4 (iter 4) | verdict |
|---|---|---|---|---|---|
| `adaptive-cruise-control` | 0.7 | 0.9 | **1.0** | 1.0 | iter 3 unlocked |
| `multilingual-video-dubbing` | 0.7 | 0.9 | 0.9 | **1.0** | iter 4 unlocked |
| `invoice-fraud-detection` | 0.3 | 0.4 | 0.2 | 0.2 | plateau at 0.4 (real ceiling) |

**Lesson:** `max_iterations=2` was too small for tasks with real signal
between iter 2 and 4. Default should be `max_iterations=4` for future
task-by-task runs. Cost trade-off: ~$25/task extra optimizer for iters 3-4.

## Insight 3 — UN-RETRACTED: "optimizer hurts baseline" is real, confirmed by v5 rerun after clearing 4 layers of infra bugs

**Final date: 2026-08-24.** The original hypothesis (optimizer degrades
already-good baselines) is **correct** — but proving it required peeling
through four independent infrastructure caching/config bugs first, each
of which was returning fake 0.0 rewards that made the optimizer look
worse than it is on 3 tasks, and made it impossible to tell what the
real behavior was on 2 more. Only after all four were resolved did
truly-fresh evaluations reveal the real optimizer pattern.

### The 4-layer bug chain (chronological order of discovery)

**Layer 1 — patched-ubuntu image v7 (2026-08-21).** Base image lacked
pre-installed `uv`/`uvx`, so verifier `test.sh` scripts crashed at
`tar: Cannot change ownership to uid 1001, gid 117` when trying to
install uv at test time. Fixed by adding uv to `/usr/local/bin` AND
`/root/.local/bin` at image build. Unblocked 6 of 8 previously "stuck
at 0" tasks. Documented in `CCC_PODMAN_SETUP.md`.

**Layer 2 — stale `.skillsbench.lock` from crashed Aug 22 job.** All
concurrent bench jobs try to `flock()` the same source-cache file;
when a previous job died, its PID still lived in the lockfile and new
jobs got "Timed out waiting for source cache lock" for the entire
baseline. Fixed by moving the stale lock aside. Documented as a
cap-evolve issue: **stale-flock recovery is missing.**

**Layer 3 — bench cache-key includes only content hash, not image
version — AND uses per-seed dirs (seed0…seed9).** After Layer 1 and 2
were fixed, cand_0001/cand_0002 evaluations still returned 0.0 in
70–100 seconds. Root cause: cap-evolve+bench cache is stored at
`.bench_runs/default/<cand>/seed<N>/<dated>/<task>__<content_hash>/`.
On the Aug 22 --resume, the optimizer proposed candidates that hashed
identically to Aug 20 attempts. Cap-evolve reused the Aug 20 rewards
(which were 0.0 from verifier crashes) without re-running bench.
My first rename attempt targeted seed0 only (10% of cache).
The complete fix required renaming across all 10 seed dirs — 90 subdirs
total for the 5 v3-rerun tasks. Documented as a cap-evolve issue:
**cache key needs image-version and preferably a `cache_invalidation_key`
config option.**

**Layer 4 — c2/.env had old ANTHROPIC creds while ~/.claude/settings.json
had new ones.** After the base image, flock, and 90-dir cache were all
cleared, v4 rewards still came back 0.0. Feedback showed
`ACP error -32603: Internal error: API Error`. The ETE proxy had
migrated from `.vpc-int.res.ibm.com` (old) to `.vpc.res.ibm.com` (new),
and the auth token changed. User updated `~/.claude/settings.json` and
`~/.bashrc`, but c2/.env was Aug 18 stale (`vpc-int` URL + old token).
Cap-evolve adapter passes .env vars to bench, so agent's ACP calls hit
the dead old proxy. Fixed by updating .env to match settings.json.
Documented as user-side: **anywhere ANTHROPIC creds are duplicated,
they need a single source of truth.**

### v5 result: the pattern IS real (finally)

After all four layers cleared, v5 ran fully-fresh evaluations:

| task | seed | c1 | c2 | c3 | c4 | best |
|---|---|---|---|---|---|---|
| `offer-letter-generator` | **1.000** | — | — | — | — | 1.000 (saturated, killed early) |
| `jax-computing-basics` | **0.900** | 0.000 | 0.000 | 0.400 | 0.100 | 0.900 (seed) |
| `drone-planning-control` | **0.720** | 0.000 | 0.000 | 0.300 | 0.300 | 0.720 (seed) |
| `paper-anonymizer` | **0.600** | 0.000 | 0.000 | 0.200 | 0.000 | 0.600 (seed) |
| `financial-modeling-qa` | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 (all zero, truly hard) |

Every single cand for 3 non-zero, non-saturated tasks scored below its
own seed. cand_0003 shows partial recovery (0.2–0.4) but never matches.
The pattern is real, consistent, and reproducible on fresh data.

### Root cause of the optimizer failure (jax as worked example)

For `jax-computing-basics`, the optimizer's cand_0001 edit was a
"helpful" addition to `jax-skills/jax_skills.py`: a new `mlp_forward`
helper defined as `relu(X @ W1 + b1) @ W2 + b2`, with SKILL.md guidance
"prefer this helper, do NOT reimplement the MLP by hand". The agent
faithfully used the helper on the `jit_mlp` sub-task.

**Result:** the agent's numerical output differed from the reference
by more than `rtol=1e-5, atol=1e-6` (the verifier's `np.allclose`
tolerance). The reference was pre-computed by the task author with
plain `relu(X @ W1 + b1) @ W2 + b2` (no wrapper). Wrapping the same
math in a helper introduces micro-differences from JIT tracing paths,
op-order rearrangement, and possible dtype promotion. Verifier
compared byte-for-byte within tolerance and said "wrong". Every trial
scored 0.

The agent's transcript ends with "All five tasks are complete and
verified against reference/" — the agent believed it succeeded.

### The generalized pattern

Across drone, jax, and paper-anonymizer, the optimizer's edits share a
family shape:

- **Add a "reference implementation" or "helper" file** meant to
  reduce agent variance
- **Add SKILL.md guidance** with "execute intent" language ("prefer
  this helper", "do NOT reimplement", "run this script first")
- **Verify locally on task fixtures** — the optimizer claims (in
  JOURNAL) it ran and matched reference

The failure modes:

1. **Numerical drift** (jax): helper produces same math but different
   float32 bytes; verifier is strict.
2. **Contract mismatch** (drone): "verified" helper expected specific
   input parsing; real task input has minor structural differences
   the optimizer didn't test against.
3. **Skill fragmentation** (paper-anonymizer): the optimizer split
   the skill's cohesive prose into "read this reference for redaction
   rules" pointers that the agent skimmed instead of following.

The core failure isn't ONE bad optimizer choice — it's a systematic
tendency to over-specify with "look like it should help" edits that
create surface area for tiny divergences to fail strict verifiers.

Cap-evolve's optimizer never sees:
- The verifier's tolerance settings
- The reference-computation code
- Whether the "verified locally" step actually mimicked the container's
  execution path (JIT compile order, dtype, etc.)

So it optimizes with an intuition of "clearer, more helpful skill"
without knowing that clearer is worse when the verifier expects
byte-identical output.

### Cap-evolve issues to file

1. **Cache key needs image + base-env identity.** `<task>__<hash>` should
   incorporate `podman image inspect ubuntu:24.04 | grep Id` (or similar
   image-content hash) so image upgrades invalidate cache.
2. **Cache key needs a user-settable invalidation flag.** A
   `cache_invalidation_key: "any-string"` in the spec YAML that gets
   folded into `<hash>` would let users force fresh runs without
   filesystem surgery.
3. **Optimizer needs verifier-tolerance signal.** If the verifier uses
   `np.allclose(rtol=1e-5)`, the optimizer should be told "prefer
   preserving the reference computation exactly; do NOT wrap math in
   helpers that could reorder ops". Otherwise every helper-wrapper edit
   is a coin flip against a strict tolerance.
4. **Stale-flock recovery.** Bench's source-cache flock should include
   a PID health check: if the recorded PID is dead, force-release.
5. **Regression guard.** Currently paired-SE gate rejects a proposal
   that drops the mean but doesn't punish the OPTIMIZER for the drop.
   The optimizer keeps proposing similar edits. A regression guard —
   "if baseline was ≥0.5, reject any candidate that drops below
   baseline − 2·SE" — would stop the optimizer from wasting iters
   repeating the same failure mode.

### Optimizer improvements to test (in order of expected impact)

- **A. Baseline-anchored edit rule.** In hill-climb's optimizer prompt,
  add: "Never add scripts, wrapper functions, or 'reference
  implementations' that recompute existing math. If the seed skill
  already has a computation, edit its prose, not its code."
- **B. Fewer, smaller edits per iter.** Constrain `optimizer_max_turns`
  from 200 → 50. Forces the optimizer to make one focused edit rather
  than 3-5 "helpful additions".
- **C. Failure-feedback ingestion.** Pass the verifier's failure
  messages (CTRF, stdout, first failing assertion) to the optimizer's
  prompt on the NEXT iteration. Currently the optimizer proposes iter 2
  based on the SAME state as iter 1, so it makes similar mistakes.
- **D. Verifier-tolerance annotation.** If the task has a numerical
  verifier with a tolerance, add a note to the optimizer's system
  prompt: "This task's verifier uses np.allclose(rtol=1e-5). Byte-level
  output changes count as failures."

### Task-level skill improvements (for the 3 hurt tasks)

- **jax-computing-basics:** the seed already documents the exact
  functions and their semantics. The optimizer should be BLOCKED from
  adding helper wrappers. Alternatively: teach the seed to say "use
  the reference implementation verbatim; do not JIT unless the task
  explicitly asks".
- **drone-planning-control:** seed ships 6 tightly-coupled controllers.
  The optimizer's tendency to add a "unified reference runner" script
  breaks integration. Better: the seed should include an explicit
  "test invocation" section so the optimizer sees "this is how the
  agent uses these skills together".
- **paper-anonymizer:** the seed's `academic-pdf-redaction/SKILL.md`
  is a single 112-line doc. The optimizer tends to split this into
  reference files. Better: mark the seed skill as `structure_locked: true`
  in the spec (once cap-evolve supports it) so the optimizer only
  changes SKILL.md prose, not adds sibling files.

<hr style="border: 0; border-top: 1px dashed #ccc; margin: 2em 0;">

**Historical context (2026-08-22 retraction, now retracted):** I had
briefly retracted this insight thinking the whole pattern was Layer 3
caching (see "the smoking gun" below). That was true for THE FIRST
observation — the Aug 22 pre-v3 reruns had cached data. But the pattern
came back with the same shape after cache clear (v5). Layers 1–4 all
had to be resolved before the underlying optimizer behavior was
visible.

---

**Historical Aug 22 retraction text (kept for the record):**

Cap-evolve did not re-run these candidates when I
did the v7 reruns on Aug 21 because it reused cached rewards keyed only
by skill-package content hash — but not by base-image version.

### The pattern that was observed

Five tasks looked like:

| task | seed (post-v7 real) | cand_0001 (stale pre-v7) | cand_0002 (stale pre-v7) |
|---|---|---|---|
| `offer-letter-generator` | 1.000 | 0.000 (cached) | 0.000 (cached) |
| `drone-planning-control` | 0.847 | 0.000 (cached) | 0.000 (cached) |
| `jax-computing-basics` | 0.500 | 0.000 (cached) | 0.000 (cached) |
| `paper-anonymizer` | 0.400 | 0.000 (cached) | 0.000 (cached) |
| `financial-modeling-qa` | 0.000 | 0.000 (cached, indistinguishable) | 0.000 (cached, indistinguishable) |

### How the caching bug works

Cap-evolve stores per-candidate bench outputs under
`.capevolve/.bench_runs/default/<candidate>/seed0/<dated>/<task>__<hash>/`
where `<hash>` is a content hash of the skill package. On re-submission,
if the optimizer proposes a candidate whose skill package hashes to the
same value as a prior attempt, cap-evolve reuses the cached rewards and
skips re-execution. Between Aug 20 (v6 image, verifier crashes) and Aug 22
(v7 image, verifier works), the base image changed but the skill package
hashes did NOT — the optimizer, given the same seed skill and same
optimizer state on --resume, proposed cand_0001 with identical content.
Cap-evolve found matching stale cache from Aug 20 and returned 0.0
without re-running.

### The smoking gun

Inspecting `.bench_runs/default/cand_0001/seed0/<dated>/<task>__<hash>/`
mtimes: all 5 "hurt" tasks show Aug 20 timestamps on config.json,
trajectory JSONL, verifier reward.txt, and verifier test-stdout.txt.
The `verifier/test-stdout.txt` file for each still shows the exact
uvx/tar-chown error from the pre-v7 verifier crash.

In contrast, **sec-financial-report cand_0002 shows an Aug 22 timestamp**
— because iter 1 was accepted, iter 2 was proposed from a DIFFERENT
starting state, its hash differed from the Aug 20 attempt, cache MISSED,
and cap-evolve re-ran it fresh with v7. That re-run scored 1.0. This is
the pattern-buster and it points directly at the cache-key bug.

### Corrected interpretation

The observed "0.0 across cand_0001+cand_0002" for these 5 tasks is
**pre-v7 verifier crashes reappearing through the cache**, NOT the
optimizer making bad proposals. The true post-v7 optimizer behavior on
these tasks is unknown until re-run with cache cleared.

The "prefer small edits" hypothesis in Insight 3 was built on this bad
data and should be discarded.

### The real cap-evolve issue to file

**Cache key bug:** `<task>__<hash>` uses only skill-package content
hash. It should also incorporate:
- Base image version (or a full image-content hash)
- OR: an explicit "cache_invalidation_key" the user can bump in the spec

Currently there is no way to force a re-run except by deleting the
cache dir or renaming it aside.

### Fix plan for the 5 affected tasks

1. Rename each stale `.bench_runs/default/cand_000{1,2}/seed0/<dated>/<task>__<hash>/`
   subdir with a `_STALE_pre_v7` suffix (preserves data, breaks cache
   lookup).
2. Rename each run dir `run_task_<task>_v1` → `run_task_<task>_v1_STALE_cand_data`.
3. Submit a fresh run with `--run-ts task_<task>_v2` (fresh baseline +
   iters, all with v7 image).

Expected outcome: some tasks (offer-letter, drone) likely stay high,
some (paper-anonymizer, jax) may reveal real optimizer behavior. Either
way we get truth, not stale artifacts.

## Insight 4 — sec-financial-report's cand_0002 was the only real optimizer lift

sec-financial-report: seed 0.9 → cand_0002 1.0 (accepted). Timestamps
show cand_0002 ran fresh on Aug 22 post-v7 — its skill package hashed
differently from the Aug 20 attempt because iter 1's acceptance shifted
the optimizer's starting state. This is the ONLY task among the v7-rerun
set where cand_0002 was a real re-execution, and it was the ONLY one
that lifted.

**This does NOT support the "prefer small edits" hypothesis** anymore
(retracted with Insight 3). It just means when caching didn't hide the
result, we saw one real optimizer improvement. Whether the optimizer
actually helps or hurts the other 4 tasks remains unknown until we clear
the cache and re-run.

## Cost tally

Approximate spend across the task-by-task work (2026-08-19 → 2026-08-22):

| phase | tasks | approx cost |
|---|---|---|
| batch 1 (10 tasks × 2 iters) | 10 | ~$500 |
| batch 2 (10 tasks × 2 iters) | 10 | ~$500 |
| Track A (3 tasks × 2 extra iters) | 3 | ~$150 |
| v7 podman fix + reruns (8 tasks × 2 iters) | 8 | ~$300 |
| smoke/diagnostic bsub | — | ~$30 |
| **TOTAL** | **20 unique tasks** | **~$1,480** |

Cost per unique-task-evaluated: ~$74.

## Where things stand for future work

**Ready:**
- Task-by-task pipeline (scripts/ccc/*.sh, .capevolve/project_<task>/*)
- v7 patched-ubuntu image (unblocks most SkillsBench verifiers)
- Dedicated-host LSF submission pattern
- Results folder with heatmap + summary + CSV + per-task logs

**Open:**
- **Root-cause the optimizer-hurts-baseline pattern** on drone, jax,
  paper-anonymizer (see Insight 3 above for investigation lines)
- **v8 base image** to unblock python-scala-translation (openjdk-21 +
  sbt or GraalVM native-image)
- **Optimizer improvements** — small-edit constraint, failure feedback,
  regression guard — see Insight 3 suggestions

Not open (already decided):
- Whether task-by-task beats whole-suite: yes, confirmed +23 pp vs +7 pp.
- Whether more iters on partial-lift tasks helps: yes, Track A validated
  bumping max_iterations to 4 as the new default.
