# all87 — broken wiring reveal (killed at seed0)

**Date:** 2026-07-30 (LSF 1408890)
**Model (agent):** claude-opus-4-6
**Optimizer:** claude-opus-4-8 (never reached iter 1)
**Task set:** all 87 SkillsBench tasks (attempted `capevolve.all87.yaml`)
**Run dir:** `.capevolve/run_all87_iter7_v2_KILLED_11pct_errors/`

## What this run was for

First attempt at the full 87-task suite. Used to expose which tasks
actually build+run on CCC rootless podman vs. which hit infrastructure
failures. Killed mid-seed0 once the pattern was clear.

## What it revealed

Of the 87 tasks (seed0 = 1 trial per task):

| Class | Count | % |
|---|---|---|
| Real verifier fail (agent ran, output rejected) | 46 | 30.7% |
| **PASS (agent ran, output accepted)** | **10** | **6.7%** |
| Infra error: `compose_build` (image build failed) | 58 | 38.7% |
| Infra error: `install_rc127` (agent install failed) | 27 | 18.0% |
| Timeout | 7 | 4.7% |
| Unknown | 2 | 1.3% |
| **Total rollouts (with retries)** | **150** | 100% |

**Real pass-rate on tasks that could actually run: 10/56 = 17.9%.**
This is the number the paired-SE gate would score if we could get past
the two dominant infra-error classes.

## Root causes of the infra errors

- **`python:3.12-slim` base image** (~26 tasks): apt postinst chown/setuid
  fails; our patched-ubuntu wrappers don't apply. Needs equivalent
  patching for the slim Python base.
- **Task-level `docker-compose.yaml` with `networks:` block**
  (~14 tasks): conflicts with our forced `network_mode: host` (which we
  use to skip aardvark-dns on compute nodes without systemd).
- **Exotic base images** (~4 tasks): `jasonish/suricata`,
  `gcr.io/oss-fuzz-base/*`, `bugswarm/cached-images`.

## Impact

The **43 tasks** that ran to a verifier verdict on seed0 became the
`RUNNABLE subset` used in the next phase (`runnable-43task-opt/`), via
`.capevolve/project/split_ids.runnable.json`.
