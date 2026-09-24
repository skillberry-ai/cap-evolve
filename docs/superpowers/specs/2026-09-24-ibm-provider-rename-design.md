# CI providers: rename to ibm-rits/ibm-ete/ibm-ete-int, add ibm-ete as a third provider

**Date:** 2026-09-24
**Status:** DESIGNED — pending implementation plan.
**Scope:** `.github/workflows/{benchmarks,integration-tests,sync-model-lists}.yml`,
`ci/benchmarks/lib/{resolve_provider,ci_setup,run_suite}.sh`, `ci/benchmarks/lib/sync_models.py`,
`ci/benchmarks/README.md`, plus the repo secrets themselves. No `core/` runtime change.

## Why

Today the benchmark CI has two providers, but the naming doesn't say so: the ete-litellm gateway
is wired under the CLI's own env var names (`ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN`), and RITS
under `RITS_API_BASE`/`RITS_API_KEY`, with only RITS carrying a `rits/` prefix in the
`agent_model`/`optimizer_model` dropdowns. There are actually **two distinct ete-litellm servers**:

- `https://ete-litellm.ai-models.vpc-int.res.ibm.com` (today's gateway, 31 models served,
  confirmed live — no GLM)
- `https://ete-litellm.ai-models.vpc.res.ibm.com` (a second, separate gateway — has GLM and other
  models the ete-int key cannot see; confirmed as a distinct auth domain — a key valid on one is
  unrecognized on the other)

A third provider is being added now, so this is also the point to make the naming pattern
extensible: every provider becomes `IBM_<NAME>_API_BASE`/`IBM_<NAME>_API_KEY`, and every dropdown
model id carries its provider as a prefix.

## Secret rename

| today | becomes | value source |
|---|---|---|
| `ANTHROPIC_BASE_URL` | `IBM_ETE_INT_API_BASE` | known: `https://ete-litellm.ai-models.vpc-int.res.ibm.com` |
| `ANTHROPIC_AUTH_TOKEN` | `IBM_ETE_INT_API_KEY` | recovered from `~/.zsh_secrets` on the user's machine, **verified live** (HTTP 200, 31 models served) against the vpc-int gateway directly |
| `RITS_API_BASE` | `IBM_RITS_API_BASE` | recovered from a prior session's `gh secret set` call |
| `RITS_API_KEY` | `IBM_RITS_API_KEY` | recovered from a prior session's `gh secret set` call |
| *(new)* | `IBM_ETE_API_BASE` | `https://ete-litellm.ai-models.vpc.res.ibm.com` |
| *(new)* | `IBM_ETE_API_KEY` | user-issued key, **verified live** (auth accepted; team is currently over its LiteLLM budget cap — a billing state on IBM's side, not a credential problem) |

GitHub Actions secrets are write-only (no `gh secret get`), so the rename is: set all six new-named
secrets with the values above, switch every workflow reference to the new names, confirm a real
dispatch works, then delete the four old-named secrets. Old and new can coexist harmlessly during
the transition since nothing reads the old names once the workflow files are updated.

## `resolve_provider.sh`: three-way prefix dispatch

Every `agent_model`/`optimizer_model` id must now carry one of three prefixes. An id without one of
these is a hard error (the three valid prefixes are named in the message) — no bare-id fallback,
since the dropdowns are the only source of these ids in normal use and every dropdown entry will
carry a prefix.

- `ibm-ete-int/<model>` → strip the prefix, wire model = `<model>` verbatim, credentials =
  `IBM_ETE_INT_API_BASE`/`IBM_ETE_INT_API_KEY`
- `ibm-ete/<model>` → strip the prefix, wire model = `<model>` verbatim, credentials =
  `IBM_ETE_API_BASE`/`IBM_ETE_API_KEY`
- `ibm-rits/<vendor>/<model>` → strip only the `ibm-` part, wire model = `rits/<vendor>/<model>`
  (lite-rits's own routing hook requires that literal `rits/` prefix — confirmed empirically:
  `rits/Qwen/Qwen3-8B` → 200, bare `Qwen/Qwen3-8B` → 400), credentials =
  `IBM_RITS_API_BASE`/`IBM_RITS_API_KEY`

`run_suite.sh`'s and `ci_setup.sh`'s call sites are unaffected beyond the renamed env vars they
source through `resolve_provider.sh` — both already consume `RESOLVED_MODEL`/`RESOLVED_API_BASE`/
`RESOLVED_API_KEY` generically, one role at a time, so a third provider needs no new call-site
logic there.

## `benchmarks.yml` / `integration-tests.yml`

- `env:` blocks switch to the six renamed secrets (the `bench` job needs all three providers'
  base/key pairs available; `integration-tests.yml` only exercises tau2 today but should get all
  three too, so a future dispatch of an `ibm-ete`/`ibm-rits` model there isn't silently broken).
- Every existing dropdown option gets `ibm-ete-int/` prepended (today's plain ids) or `ibm-rits/`
  (today's `rits/`-prefixed ids, which become `ibm-rits/<vendor>/<model>`).
- `ibm-ete` is added to both dropdowns with **zero seeded options.** The vpc gateway's catalog
  isn't visible yet (budget-capped right now, and even once it clears, hand-typing GLM model-id
  spellings risks the exact prefix/case-drift failure `check_models.py`'s docstring documents).
  The sync workflow below populates real entries automatically once the gateway is queryable — no
  guessed spellings ever land in the dropdown.
- Header comments and the `default:` values for both pickers get the `ibm-ete-int/` prefix (the
  defaults stay on today's models — this PR doesn't change what runs by default, only how it's
  named).

## `sync-model-lists.yml` + `sync_models.py`: multi-provider

- The workflow gains a second fetch step: `GET $IBM_ETE_API_BASE/models` with the `IBM_ETE_API_KEY`
  bearer token, alongside the existing `IBM_ETE_INT_*` fetch. Each is written to its own temp file.
- `sync_models.py` changes from a single `--models <path>` to a repeatable
  `--models <prefix>=<path>` (e.g. `--models ibm-ete-int=/tmp/int.json --models ibm-ete=/tmp/ete.json`).
  For each `(prefix, path)` pair it fetches served ids and treats them as `prefix/<id>`.
- Sync is scoped to exactly the prefixes passed on a given invocation: existing dropdown options
  under an unpolled prefix (in practice, everything under `ibm-rits/`, always) are left untouched.
  This preserves the current behavior — RITS stays hand-curated — for free, as an emergent property
  of "only overwrite what was actually polled," rather than a special case.
- Default-retention logic (an unserved default is kept, not silently dropped — see the module's
  existing docstring) applies per-picker exactly as today; it doesn't need to change shape.
- A failed poll of one gateway (e.g. `ibm-ete` still budget-capped) must not blank or corrupt that
  gateway's existing options — the fetch step already retries and the sync step already treats "no
  models returned" as a hard stop (`EXIT_DECISION`, "refusing to blank the pickers"); this behavior
  extends unchanged to a per-prefix fetch failure, it just means that prefix's options are left as
  they were rather than the whole sync aborting.

## `ci_setup.sh` preflight

Today's binary branch (`case "$PF_AGENT" in rits/*) ... esac`, skipping `/models` entitlement
listing only for RITS) generalizes to: skip listing only for `ibm-rits/*` (lite-rits's `/v1/models`
is always empty by design — it builds routes dynamically per request); do listing + entitlement
check via `check_models.py` for both `ibm-ete-int/*` and `ibm-ete/*`. The completion-probe budget
check (`probe_model`) already runs against whichever `RESOLVED_API_BASE`/`RESOLVED_API_KEY`
`resolve_provider.sh` returned, so it needs no change beyond following the renamed variables.

## `README.md`

New "ibm-ete" section mirroring the existing ibm-ete-int/ibm-rits write-up: base URL, secret names,
that its dropdown starts empty and fills in via `sync-model-lists.yml`, and the current
budget-capped state as a known caveat until IBM raises or resets the team's cap. A short note on the
`IBM_<NAME>_API_BASE`/`_API_KEY` naming convention for anyone adding a fourth provider later.

## Rollout sequence

1. `gh secret set` the six new-named secrets with the values already recovered/verified above.
2. Edit `resolve_provider.sh`, `ci_setup.sh` call sites' env expectations, `benchmarks.yml`,
   `integration-tests.yml`, `sync-model-lists.yml`, `sync_models.py`, `README.md`.
3. `bash -n` every edited shell script; `sync_models.py --validate`; actionlint on the workflow
   YAML.
4. Dispatch `integration-tests.yml` (tau2, task 9) manually against an `ibm-ete-int/*` model to
   prove the rename didn't break the existing path end-to-end on skillberry-1.
5. Manually dispatch `sync-model-lists.yml` (`apply: true`) once `ibm-ete`'s budget clears, to
   confirm the multi-provider sync populates real `ibm-ete/*` entries and leaves `ibm-rits/*` alone.
6. Delete the four old-named secrets (`ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `RITS_API_BASE`,
   `RITS_API_KEY`) only after step 4 passes on the new names.

## Known caveats carried into this design

- `ibm-ete`'s team budget is currently exceeded on IBM's side — the provider is wired and correct,
  but no real completion will succeed against it until that's raised/reset. Nothing here works
  around that; the preflight will report it clearly (429, "budget exceeded") rather than silently
  eating the failure.
- `OPTIMIZER_MODEL: ibm-rits/*` still points the `claude` CLI's `ANTHROPIC_BASE_URL`/
  `ANTHROPIC_AUTH_TOKEN` at lite-rits; whether lite-rits speaks the Anthropic Messages API shape the
  CLI expects remains unverified (pre-existing caveat, unchanged by this rename).
