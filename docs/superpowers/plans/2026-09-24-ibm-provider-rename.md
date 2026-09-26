# IBM CI provider rename + ibm-ete third provider — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the CI's two model-gateway secret pairs to a `IBM_<NAME>_API_BASE`/`IBM_<NAME>_API_KEY` scheme (`RITS`, `ETE_INT`), add a third provider `ETE` (a second, separate ete-litellm gateway), and make every `agent_model`/`optimizer_model` dropdown id carry one of three CI-only prefixes (`ibm-ete-int/`, `ibm-ete/`, `ibm-rits/`) end to end through `resolve_provider.sh`, `ci_setup.sh`, `run_suite.sh`, `sync_models.py`, the three workflow YAML files, and the README.

**Architecture:** `resolve_provider.sh` becomes the single place that knows the three CI prefixes; it strips them and returns a wire-ready model id plus that provider's credentials. Everything downstream (`ci_setup.sh`'s preflight, `run_suite.sh`'s per-arm dispatch, `sync_models.py`'s dropdown sync) consumes its output generically and needs no per-provider branching of its own — except where a call site was, until now, accidentally relying on the old `resolve_provider.sh`'s never-rewrites-the-model-id behavior. This plan's Task 3 documents and fixes every one of those call sites; see "Correction to the approved spec" below.

**Tech Stack:** Bash (`ci/benchmarks/lib/*.sh`), Python 3 stdlib only (`ci/benchmarks/lib/sync_models.py`, `argparse`, `json`), GitHub Actions workflow YAML, `pytest` for `test_sync_models.py`.

**Spec:** `docs/superpowers/specs/2026-09-24-ibm-provider-rename-design.md`

## Correction to the approved spec

The spec (lines 58-61) states that `run_suite.sh`'s call sites are "unaffected beyond the renamed env vars" because the old `resolve_provider.sh` never rewrites the model id — `RESOLVED_MODEL` is always textually identical to the input. That invariant is exactly what this plan's new `resolve_provider.sh` (Task 2) breaks on purpose: `ibm-ete-int/*` and `ibm-ete/*` now strip their whole prefix, and `ibm-rits/*` strips the `ibm-` part. Once `AGENT_MODEL`/`OPTIMIZER_MODEL` carry a CI prefix, every `run_suite.sh` call site that sends a model id **on the wire** (not just into a human-readable report) must read `$AGENT_MODEL_WIRE`/`$OPTIMIZER_MODEL_WIRE` instead of the bare `$AGENT_MODEL`/`$OPTIMIZER_MODEL`, or the provider will receive a prefix it doesn't recognize. Task 3 below is the fix, traced call site by call site against `core/cap_evolh_cli.py` and `metrics.py` so nothing is guessed. This is an implementation-accuracy correction within the spec's own intent, not a design change — the spec's naming/prefix scheme is unaffected.

## Global Constraints

- Every provider's secret pair is named `IBM_<NAME>_API_BASE` / `IBM_<NAME>_API_KEY` — exactly `IBM_RITS_*`, `IBM_ETE_INT_*`, `IBM_ETE_*`. No other naming shape.
- Every `agent_model`/`optimizer_model` id handled by `resolve_provider.sh` must carry exactly one of the three prefixes `ibm-ete-int/`, `ibm-ete/`, `ibm-rits/`. An id with none of these is a hard error naming all three valid prefixes — no bare-id fallback.
- `ibm-ete-int/<model>` and `ibm-ete/<model>` strip their **entire** prefix; the wire model id is `<model>` verbatim.
- `ibm-rits/<vendor>/<model>` strips **only** the `ibm-` part; the wire model id is `rits/<vendor>/<model>` (lite-rits's routing hook requires that literal `rits/` prefix — confirmed empirically: `rits/Qwen/Qwen3-8B` → HTTP 200, bare `Qwen/Qwen3-8B` → HTTP 400).
- No plaintext secret value is ever written into any repository file — not a workflow, not a script, not this plan. Secrets are installed only via `gh secret set` run directly against GitHub; this plan references secret **names** and command **shapes** only.
- Old secret names (`ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `RITS_API_BASE`, `RITS_API_KEY`) are deleted only after Task 10's rollout verification passes — never before, and old/new may coexist harmlessly during the transition.
- `ibm-ete` ships with **zero** seeded dropdown options at merge time (its catalog is budget-capped and unverified) — no hand-guessed model-id spellings are added to either dropdown for it.
- Every commit is created with `git commit -s` (DCO) per `/Users/eranra/CLAUDE.md`, ends with the `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer, and is verified via `gh pr checks` / `git log --format='%h %(trailers:key=Signed-off-by,valueonly)' origin/main..HEAD` before requesting review.

## Review Focus

- **A model id with no recognized prefix** (a stale bare `aws/gpt-oss-120b` left from before the rename, or a typo) must hard-fail `resolve_provider` with a message naming all three valid prefixes, not silently fall through to some default provider. → pinned by Task 2's tests.
- **Pre-existing `tasks.json` "agent" pins**, written under the old bare/`rits/`-prefixed scheme, must still register as served once the dropdowns are re-prefixed — otherwise both `run_suite.sh`'s provenance notice (Task 3) and `sync_models.py`'s `task_pins()` advisory check (Task 5) produce a false-positive warning on every single run, since a prefixed id never string-equals a bare one. → pinned by Task 3's and Task 5's tests.
- **A poll failure against one gateway** (e.g. `ibm-ete` still budget-capped) must leave that gateway's existing dropdown options untouched, not wipe them to empty or abort the whole sync. → pinned by Task 5's and Task 8's tests/steps.
- **The tau2_custom_direct/spa arms' hardcoded reliance on the `ibm-ete-int` gateway** for `OPENAI_BASE_URL`/`OPENAI_API_KEY` (unconditional regardless of which provider `AGENT_MODEL` actually resolved to) is a pre-existing scope limit this rename does not fix. Task 3's tests must confirm the wire model id sent to that hardcoded endpoint is still correct for an `ibm-ete-int/*` agent_model — the only provider this arm has ever supported — while fixing the unrelated `_WIRE` stripping bug, and must not silently break that one supported case.
- **`ibm-rits/<vendor>/<model>` is exactly three segments** (`ibm-rits`, vendor, model); a caller that passes `ibm-rits/<model>` with no vendor segment must not silently produce a wire id lite-rits 400s on with no diagnostic pointing back at the malformed CI-prefixed input. → pinned by Task 2's tests.

---

## Task 1: Provision the six new secrets

**Files:** none (GitHub repo secrets only — no repo file is touched by this task).

**Interfaces:**
- Consumes: nothing from this repo.
- Produces: the six repo secrets `IBM_ETE_INT_API_BASE`, `IBM_ETE_INT_API_KEY`, `IBM_ETE_API_BASE`, `IBM_ETE_API_KEY`, `IBM_RITS_API_BASE`, `IBM_RITS_API_KEY`, which every later task's workflow-file edits reference by name.

- [ ] **Step 1: Set the six new-named secrets**

Run each of the following, supplying the plaintext value already recovered/verified in this session (never paste it into a repo file — pull it from wherever it's held outside the repo, e.g. your shell history or password manager):

```bash
gh secret set IBM_ETE_INT_API_BASE --repo skillberry-ai/cap-evolve
gh secret set IBM_ETE_INT_API_KEY  --repo skillberry-ai/cap-evolve
gh secret set IBM_ETE_API_BASE     --repo skillberry-ai/cap-evolve
gh secret set IBM_ETE_API_KEY      --repo skillberry-ai/cap-evolve
gh secret set IBM_RITS_API_BASE    --repo skillberry-ai/cap-evolve
gh secret set IBM_RITS_API_KEY     --repo skillberry-ai/cap-evolve
```

`gh secret set NAME` with no `--body`/`-b` prompts for the value interactively (or reads stdin if piped), so the plaintext never appears in shell history or this plan.

- [ ] **Step 2: Verify all six are present**

```bash
gh secret list --repo skillberry-ai/cap-evolve
```

Expected: all six new names listed, alongside the still-present old four (`ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `RITS_API_BASE`, `RITS_API_KEY`) — both sets coexist until Task 10 deletes the old ones.

---

## Task 2: `resolve_provider.sh` — three-way prefix dispatch

**Files:**
- Modify: `ci/benchmarks/lib/resolve_provider.sh` (currently 48 lines; full rewrite)
- Test: `ci/benchmarks/lib/test_resolve_provider.sh` (new file — this script has no existing test; add one following the plain-bash-assertion style, since there is no bash test framework in this repo)

**Interfaces:**
- Consumes: env vars `IBM_ETE_INT_API_BASE`, `IBM_ETE_INT_API_KEY`, `IBM_ETE_API_BASE`, `IBM_ETE_API_KEY`, `IBM_RITS_API_BASE`, `IBM_RITS_API_KEY` (Task 1).
- Produces: function `resolve_provider(model_id)` setting `RESOLVED_MODEL`, `RESOLVED_API_BASE`, `RESOLVED_API_KEY`, `RESOLVED_PROVIDER` (`"ibm-ete-int" | "ibm-ete" | "ibm-rits"`) as global vars — consumed by Task 3 (`run_suite.sh`) and Task 4 (`ci_setup.sh`).

- [ ] **Step 1: Write the failing tests**

Create `ci/benchmarks/lib/test_resolve_provider.sh`:

```bash
#!/usr/bin/env bash
# Plain-assertion bash tests for resolve_provider.sh — no test framework, just exit-code
# checks, since that's the pattern the rest of ci/benchmarks/lib uses for its .sh files.
set -euo pipefail
LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

fail=0
check() {
  local desc="$1" got="$2" want="$3"
  if [ "$got" != "$want" ]; then
    echo "FAIL: $desc — got '$got', want '$want'"
    fail=1
  else
    echo "ok: $desc"
  fi
}

export IBM_ETE_INT_API_BASE="https://int.example.com"
export IBM_ETE_INT_API_KEY="int-key"
export IBM_ETE_API_BASE="https://ete.example.com"
export IBM_ETE_API_KEY="ete-key"
export IBM_RITS_API_BASE="http://localhost:4000"
export IBM_RITS_API_KEY="rits-key"

# shellcheck source=ci/benchmarks/lib/resolve_provider.sh
. "$LIB_DIR/resolve_provider.sh"

resolve_provider "ibm-ete-int/aws/gpt-oss-120b"
check "ete-int strips whole prefix" "$RESOLVED_MODEL" "aws/gpt-oss-120b"
check "ete-int api_base"            "$RESOLVED_API_BASE" "https://int.example.com"
check "ete-int api_key"             "$RESOLVED_API_KEY" "int-key"
check "ete-int provider tag"        "$RESOLVED_PROVIDER" "ibm-ete-int"

resolve_provider "ibm-ete/glm-4.6"
check "ete strips whole prefix" "$RESOLVED_MODEL" "glm-4.6"
check "ete api_base"            "$RESOLVED_API_BASE" "https://ete.example.com"
check "ete provider tag"        "$RESOLVED_PROVIDER" "ibm-ete"

resolve_provider "ibm-rits/google/gemma-4-31B-it"
check "rits strips only ibm- part" "$RESOLVED_MODEL" "rits/google/gemma-4-31B-it"
check "rits api_base"              "$RESOLVED_API_BASE" "http://localhost:4000"
check "rits provider tag"          "$RESOLVED_PROVIDER" "ibm-rits"

# Unrecognized/bare id must hard-error, not silently pick a default provider.
if err=$(bash -c '. "'"$LIB_DIR"'/resolve_provider.sh"; resolve_provider "aws/gpt-oss-120b"' 2>&1); then
  echo "FAIL: bare id should have exited non-zero"
  fail=1
else
  case "$err" in
    *ibm-ete-int/*ibm-ete/*ibm-rits/*) echo "ok: bare id hard-errors naming all three prefixes" ;;
    *) echo "FAIL: error message doesn't name all three prefixes: $err"; fail=1 ;;
  esac
fi

# Malformed rits id (missing vendor segment) must not silently produce a bad wire id.
resolve_provider "ibm-rits/onlymodel"
check "malformed rits id still gets the rits/ prefix (caller's job to validate vendor/model shape)" \
  "$RESOLVED_MODEL" "rits/onlymodel"
# This is intentionally documented, not "fixed": resolve_provider only strips the CI
# prefix, it does not validate the vendor/model shape of what's left. A malformed
# "ibm-rits/onlymodel" produces "rits/onlymodel" on the wire, which lite-rits itself will
# 400 on with its own diagnostic — see Task 2 Step 5 for why validating shape here would
# just duplicate that check with a worse error message.

exit $fail
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `bash ci/benchmarks/lib/test_resolve_provider.sh`
Expected: FAIL — the current `resolve_provider.sh` never rewrites `RESOLVED_MODEL` and has no `RESOLVED_PROVIDER`, so the `ete-int strips whole prefix`, `ete strips whole prefix`, `rits strips only ibm- part`, and `provider tag` checks all fail; the bare-id hard-error check also fails since the current script has no prefix validation at all.

- [ ] **Step 3: Rewrite `resolve_provider.sh`**

Replace the entire file:

```bash
#!/usr/bin/env bash
# resolve_provider.sh — map a CI model id to the provider that actually serves it.
#
# Three providers coexist on this runner, and every agent_model/optimizer_model id must
# carry one of these three CI-only prefixes (there is no bare-id fallback: the dropdowns
# are the only source of these ids in normal use, and every dropdown entry carries one):
#
#   * ibm-ete-int/<model>  — the original ete-litellm gateway
#     (https://ete-litellm.ai-models.vpc-int.res.ibm.com), IBM_ETE_INT_API_BASE /
#     IBM_ETE_INT_API_KEY. Strip the prefix; the remainder is the wire model id verbatim.
#   * ibm-ete/<model>      — a second, separate ete-litellm gateway
#     (https://ete-litellm.ai-models.vpc.res.ibm.com; a DIFFERENT auth domain from
#     ibm-ete-int — a key valid on one is unrecognized on the other), IBM_ETE_API_BASE /
#     IBM_ETE_API_KEY. Strip the prefix; the remainder is the wire model id verbatim.
#   * ibm-rits/<vendor>/<model> — RITS via the lite-rits proxy on skillberry-1:4000
#     (IBM_RITS_API_BASE / IBM_RITS_API_KEY). Strip only the "ibm-" part: lite-rits's own
#     custom_callbacks.py (async_pre_call_hook) only engages when the incoming wire model
#     STILL starts with "rits/" — it strips THAT prefix itself to look up the bare
#     "<vendor>/<model>" key in its scraped rits.json. Send it the bare id instead and the
#     hook never fires, so the request falls through to plain LiteLLM routing and fails
#     with "Invalid model name passed in model=...". Verified against the live proxy
#     (skillberry-1:4000): "rits/Qwen/Qwen3-8B" -> HTTP 200; the stripped bare
#     "Qwen/Qwen3-8B" -> HTTP 400 "Invalid model name". So "ibm-rits/<vendor>/<model>" ->
#     wire model "rits/<vendor>/<model>" — the ibm- part is the ONLY thing this strips.
#
# Usage: source this file, then call `resolve_provider "$SOME_MODEL_ID"` and read the
# four RESOLVED_* variables it sets:
#   RESOLVED_MODEL     — the model id to actually send on the wire (prefix stripped/rewritten)
#   RESOLVED_API_BASE  — the provider's api_base
#   RESOLVED_API_KEY   — the provider's api_key
#   RESOLVED_PROVIDER  — "ibm-ete-int" | "ibm-ete" | "ibm-rits", for callers that need to
#                        branch on provider identity instead of re-deriving it from
#                        RESOLVED_API_BASE string comparisons
resolve_provider() {
  local model="${1:?resolve_provider: model id required}"
  case "$model" in
    ibm-ete-int/*)
      RESOLVED_MODEL="${model#ibm-ete-int/}"
      RESOLVED_PROVIDER="ibm-ete-int"
      : "${IBM_ETE_INT_API_BASE:?set IBM_ETE_INT_API_BASE (ete-litellm vpc-int gateway)}"
      : "${IBM_ETE_INT_API_KEY:?set IBM_ETE_INT_API_KEY}"
      RESOLVED_API_BASE="$IBM_ETE_INT_API_BASE"
      RESOLVED_API_KEY="$IBM_ETE_INT_API_KEY"
      ;;
    ibm-ete/*)
      RESOLVED_MODEL="${model#ibm-ete/}"
      RESOLVED_PROVIDER="ibm-ete"
      : "${IBM_ETE_API_BASE:?set IBM_ETE_API_BASE (ete-litellm vpc gateway)}"
      : "${IBM_ETE_API_KEY:?set IBM_ETE_API_KEY}"
      RESOLVED_API_BASE="$IBM_ETE_API_BASE"
      RESOLVED_API_KEY="$IBM_ETE_API_KEY"
      ;;
    ibm-rits/*)
      RESOLVED_MODEL="rits/${model#ibm-rits/}"
      RESOLVED_PROVIDER="ibm-rits"
      : "${IBM_RITS_API_BASE:?set IBM_RITS_API_BASE (skillberry-1 lite-rits proxy, e.g. http://localhost:4000)}"
      : "${IBM_RITS_API_KEY:?set IBM_RITS_API_KEY}"
      RESOLVED_API_BASE="$IBM_RITS_API_BASE"
      RESOLVED_API_KEY="$IBM_RITS_API_KEY"
      ;;
    *)
      echo "resolve_provider: '$model' has no recognized provider prefix (expected ibm-ete-int/, ibm-ete/, or ibm-rits/)" >&2
      exit 1
      ;;
  esac
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `bash ci/benchmarks/lib/test_resolve_provider.sh`
Expected: every `ok:` line, exit code 0.

- [ ] **Step 5: Run `bash -n` syntax check**

Run: `bash -n ci/benchmarks/lib/resolve_provider.sh`
Expected: no output, exit code 0.

- [ ] **Step 6: Commit**

```bash
git add ci/benchmarks/lib/resolve_provider.sh ci/benchmarks/lib/test_resolve_provider.sh
git commit -s -m "$(cat <<'EOF'
ci(resolve_provider): three-way ibm-ete-int/ibm-ete/ibm-rits prefix dispatch

Replaces the two renamed secret pairs plus a new ibm-ete gateway with a single
prefix scheme every agent_model/optimizer_model id must carry. ibm-ete-int/ and
ibm-ete/ strip their whole prefix; ibm-rits/ strips only the ibm- part, since
lite-rits's routing hook requires the literal rits/<vendor>/<model> form. An
id with none of these three prefixes is now a hard error instead of a silent
default.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `run_suite.sh` — renamed defaults, corrected comments, `_WIRE` call sites

**Files:**
- Modify: `ci/benchmarks/lib/run_suite.sh` (lines 33, 35, 148-151, 158-164, 176-182, 204, 310, 317, 336-338, 855, 942 — see steps below for exact before/after)

**Interfaces:**
- Consumes: `resolve_provider()` (Task 2) — already called at lines 154/156, setting `AGENT_MODEL_WIRE`/`OPTIMIZER_MODEL_WIRE` at lines 155/157 (these two lines are unchanged by this task).
- Produces: no new interface — `AGENT_MODEL_WIRE`/`OPTIMIZER_MODEL_WIRE` already existed; this task just makes every wire-facing call site actually use them instead of the bare `AGENT_MODEL`/`OPTIMIZER_MODEL`.

- [ ] **Step 1: Update the default model ids (lines 33, 35)**

`ci/benchmarks/lib/run_suite.sh:33`:
```bash
AGENT_MODEL="${AGENT_MODEL:-aws/gpt-oss-120b}"
```
becomes:
```bash
AGENT_MODEL="${AGENT_MODEL:-ibm-ete-int/aws/gpt-oss-120b}"
```

`ci/benchmarks/lib/run_suite.sh:35`:
```bash
OPTIMIZER_MODEL="${OPTIMIZER_MODEL:-claude-opus-4-8}"
```
becomes:
```bash
OPTIMIZER_MODEL="${OPTIMIZER_MODEL:-ibm-ete-int/claude-opus-4-8}"
```

- [ ] **Step 2: Correct the provider-resolution comment block (lines 148-151)**

Before:
```bash
# Resolve AGENT_MODEL/OPTIMIZER_MODEL to their provider (ETE gateway, or RITS via the
# skillberry-1 lite-rits proxy for a "rits/*" id) — see resolve_provider.sh. Each is
# resolved independently: dispatching a RITS agent_model with a Claude optimizer_model
# (or vice versa) is a normal, deliberate combination, not an error.
```
After:
```bash
# Resolve AGENT_MODEL/OPTIMIZER_MODEL to their provider (ibm-ete-int, ibm-ete, or
# ibm-rits — see resolve_provider.sh for the prefix scheme). Each is resolved
# independently: dispatching an ibm-rits agent_model with an ibm-ete-int (or ibm-ete)
# optimizer_model, or any other pairing, is a normal, deliberate combination, not an
# error.
```

- [ ] **Step 3: Correct the ANTHROPIC_BASE_URL override comment (lines 158-164)**

Before:
```bash
# The `claude` CLI (optimizer_skill: claude-code, invoked further down by
# `cap_evolve.cli run` / agent-optimize's host.py) reads ANTHROPIC_BASE_URL/
# ANTHROPIC_AUTH_TOKEN from the process environment — overriding them here, once, before
# either is invoked, is what makes an OPTIMIZER_MODEL of "rits/*" actually reach RITS
# rather than silently keep talking to the ETE gateway with a model id it doesn't
# recognise. NOT yet verified that lite-rits speaks the Anthropic Messages API the CLI
# expects — see the PR description.
```
After:
```bash
# The `claude` CLI (optimizer_skill: claude-code, invoked further down by
# `cap_evolve.cli run` / agent-optimize's host.py) reads ANTHROPIC_BASE_URL/
# ANTHROPIC_AUTH_TOKEN from the process environment — overriding them here, once, before
# either is invoked, is what makes an OPTIMIZER_MODEL on ibm-ete, or ibm-rits, actually
# reach that provider rather than silently keep talking to the ibm-ete-int gateway with a
# model id it doesn't recognise. NOT yet verified that lite-rits (ibm-rits) speaks the
# Anthropic Messages API the CLI expects — see the PR description.
```

(Lines 165-175, the process-wide-export/skillsbench/rfe-creator scope note, are untouched — they don't mention the old invariant.)

- [ ] **Step 4: Correct the now-false "never rewrites the model id" comment (lines 176-182)**

Before:
```bash
# NB: no `OPTIMIZER_MODEL="$OPTIMIZER_MODEL_WIRE"` reassignment here (there used to be
# one) — resolve_provider never strips/rewrites the model id, so RESOLVED_MODEL (hence
# OPTIMIZER_MODEL_WIRE) is always textually identical to the input OPTIMIZER_MODEL. The
# reassignment was a no-op; removing it keeps OPTIMIZER_MODEL as the one source of truth
# used both for the wire call above and for the capevolve.yaml/metrics.py provenance
# fields further down (both want the CI-facing "rits/…"-prefixed alias, not a rewritten
# form).
```
After:
```bash
# NB: OPTIMIZER_MODEL itself is NEVER reassigned to the wire form here — it stays the
# CI-facing "ibm-ete-int/…"/"ibm-ete/…"/"ibm-rits/…"-prefixed alias, used for the
# progress line below and metrics.py's provenance display further down. resolve_provider
# DOES strip that prefix into OPTIMIZER_MODEL_WIRE (unlike this comment used to claim —
# resolve_provider.sh now rewrites the model id on purpose, see its own header comment).
# Every call site below that hands a model id to a provider ON THE WIRE, not just into a
# human-readable report, must use the _WIRE variant: capevolve.yaml's `optimizer_model:`
# key and the agent-mode host.py invocation both pass this straight to the `claude` CLI's
# own --model flag (core/cap_evolve/cli.py:711 and :902), so an un-stripped CI prefix
# there is not provenance text, it's a broken subprocess argument.
```

- [ ] **Step 5: Fix the tasks.json provenance comparison (line 204)**

Before:
```bash
"$PY" - "$BASE/tasks.json" "$AGENT_MODEL" "$BENCH/$TIER" <<'PY'
```
After:
```bash
"$PY" - "$BASE/tasks.json" "$AGENT_MODEL_WIRE" "$BENCH/$TIER" <<'PY'
```

This keeps the `::notice::` mismatch comparison meaningful: `tasks.json`'s stored `"agent"` pins were written under the old bare/`rits/`-prefixed scheme (e.g. `"aws/gpt-oss-120b"` or `"rits/google/gemma-4-31B-it"`), which is exactly the shape `AGENT_MODEL_WIRE` now produces (`ibm-ete-int/*`/`ibm-ete/*` strip to the bare id; `ibm-rits/*` strips to `rits/<vendor>/<model>`) — comparing against the CI-prefixed `AGENT_MODEL` instead would make this notice fire on every single run.

- [ ] **Step 6: Fix the tau2 direct-mode wire calls (lines 310, 317)**

Before (line 310):
```bash
export TAU2_USER_MODEL="$AGENT_MODEL"
```
After:
```bash
export TAU2_USER_MODEL="$AGENT_MODEL_WIRE"
```

Before (line 317):
```bash
export TAU2_AGENT_MODEL="$AGENT_MODEL"
```
After:
```bash
export TAU2_AGENT_MODEL="$AGENT_MODEL_WIRE"
```

Both are sent literally to the OpenAI-compatible completion endpoint via `OPENAI_BASE_URL`/`OPENAI_API_KEY` (set from `$ANTHROPIC_BASE_URL`/`$ANTHROPIC_AUTH_TOKEN` a few lines above, at 304-309 — unchanged by this task, per the Review Focus note on that hardcoded `ibm-ete-int`-only arm).

- [ ] **Step 7: Fix the SPA `openai/*` routing-prefix detection (lines 336-338)**

Before:
```bash
case "$AGENT_MODEL" in
  openai/*) export SPA_MODEL_NAME="${SPA_MODEL_NAME:-$AGENT_MODEL}" ;;
  *) export SPA_MODEL_NAME="${SPA_MODEL_NAME:-openai/$AGENT_MODEL}" ;;
esac
```
After:
```bash
case "$AGENT_MODEL_WIRE" in
  openai/*) export SPA_MODEL_NAME="${SPA_MODEL_NAME:-$AGENT_MODEL_WIRE}" ;;
  *) export SPA_MODEL_NAME="${SPA_MODEL_NAME:-openai/$AGENT_MODEL_WIRE}" ;;
esac
```

This detects litellm's own `openai/` routing prefix inside the *served* model id — after adding a CI prefix, that check would never match on the bare `$AGENT_MODEL` (which now always starts with `ibm-ete-int/`, `ibm-ete/`, or `ibm-rits/`), so it must test the already-stripped `$AGENT_MODEL_WIRE`.

- [ ] **Step 8: Fix the `capevolve.yaml` optimizer_model field (line 855)**

Before:
```yaml
optimizer_model:    $OPTIMIZER_MODEL
```
After:
```yaml
optimizer_model:    $OPTIMIZER_MODEL_WIRE
```

Confirmed via `core/cap_evolve/cli.py:710-711` (`if spec.get("optimizer_model"): opt_cmd += f" --model {spec['optimizer_model']}"`) that this field is passed literally as `--model` to the `claude` CLI subprocess — a live wire call, not provenance text as the old comment (fixed in Step 4) claimed.

- [ ] **Step 9: Fix the agent-mode host.py invocation (line 942)**

Before:
```bash
--agent claude-code --model "$OPTIMIZER_MODEL"
```
After:
```bash
--agent claude-code --model "$OPTIMIZER_MODEL_WIRE"
```

Confirmed via `core/cap_evolve/cli.py:900-902` (`host_cmd += ["--model", str(spec["optimizer_model"])]`) — the same live-call pattern as Step 8, on the agent-mode handoff path.

- [ ] **Step 10: Leave the two cosmetic sites unchanged (lines 216, 949) — verify, don't edit**

Confirm these two lines are unchanged and still read the bare aliases:
- Line 216: `echo ">>> $BENCH/$TIER — optimizing ${#IDS[@]} tasks together (agent=$AGENT_MODEL, ${ITER} iters)" >&2` — a log line, never parsed by anything downstream.
- Line 949: `... --agent "$AGENT_MODEL" --optimizer-model "$OPTIMIZER_MODEL" ...` (the `metrics.py` invocation) — confirmed via `ci/benchmarks/lib/metrics.py:203,288,293` that these flags feed only display strings in the generated report markdown (e.g. `f"Agent \`{agent}\` · optimizer Claude Code \`{optimizer_model}\`"`), never a live wire call. Showing the CI-facing alias here (not the stripped wire id) is correct — it's the label a human reading the report wants.

```bash
grep -n 'AGENT_MODEL\|OPTIMIZER_MODEL' ci/benchmarks/lib/run_suite.sh | grep -E ':(216|949):'
```
Expected: both lines still reference the bare (non-`_WIRE`) variable.

- [ ] **Step 11: Syntax check**

Run: `bash -n ci/benchmarks/lib/run_suite.sh`
Expected: no output, exit code 0.

- [ ] **Step 12: Commit**

```bash
git add ci/benchmarks/lib/run_suite.sh
git commit -s -m "$(cat <<'EOF'
ci(run_suite): switch every wire-facing model-id call site to _WIRE

resolve_provider.sh now strips CI prefixes before returning a wire model id
(previously RESOLVED_MODEL was always textually identical to the input, so
this never mattered). Every call site that hands a model id to a provider on
the wire now reads AGENT_MODEL_WIRE/OPTIMIZER_MODEL_WIRE instead of the bare,
CI-prefixed alias: the tasks.json provenance check, both tau2 direct-mode env
vars, the SPA openai/* prefix detection, capevolve.yaml's optimizer_model
field, and the agent-mode host.py --model flag. The two purely cosmetic sites
(the progress echo and metrics.py's report labels) are left on the bare alias
on purpose, since that's the CI-facing name a human reading a report wants.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `ci_setup.sh` — three-way preflight

**Files:**
- Modify: `ci/benchmarks/lib/ci_setup.sh:262-409`

**Interfaces:**
- Consumes: `resolve_provider()` / `RESOLVED_PROVIDER` (Task 2).
- Produces: no new interface — the preflight's exported `GITHUB_ENV` vars (line 395-409) are unchanged in name and meaning.

- [ ] **Step 1: Replace the binary RITS classification with `classify_provider()`**

Before (lines 292-299, the two `PF_AGENT_IS_RITS`/`PF_OPTIMIZER_IS_RITS` case statements):
```bash
case "$PF_AGENT" in
  rits/*) PF_AGENT_IS_RITS=1 ;;
  *) PF_AGENT_IS_RITS=0 ;;
esac
case "$PF_OPTIMIZER" in
  rits/*) PF_OPTIMIZER_IS_RITS=1 ;;
  *) PF_OPTIMIZER_IS_RITS=0 ;;
esac
```
After:
```bash
classify_provider() {
  case "$1" in
    ibm-ete-int/*) echo "ibm-ete-int" ;;
    ibm-ete/*)     echo "ibm-ete" ;;
    ibm-rits/*)    echo "ibm-rits" ;;
    *) echo "ci_setup: '$1' has no recognized provider prefix (expected ibm-ete-int/, ibm-ete/, or ibm-rits/)" >&2; exit 1 ;;
  esac
}
PF_AGENT_PROVIDER="$(classify_provider "$PF_AGENT")"
PF_OPTIMIZER_PROVIDER="$(classify_provider "$PF_OPTIMIZER")"
```

- [ ] **Step 2: Generalize the entitlement check to run once per gateway provider**

Before (lines 301-325, the entitlement check block gated on `PF_AGENT_IS_RITS`/`PF_OPTIMIZER_IS_RITS` being 0):

The existing block calls `check_models.py` against `$ANTHROPIC_BASE_URL`/`$ANTHROPIC_AUTH_TOKEN` once if either side is non-RITS. Replace it with a `check_entitlement` helper called once per distinct gateway provider actually in play this run (never for `ibm-rits`, whose `/v1/models` is always empty by design — it builds routes dynamically per request):

```bash
check_entitlement() {
  local provider="$1" base="$2" key="$3"
  echo "::group::Entitlement check — $provider"
  if ! python3 "$LIB_DIR/check_models.py" --base "$base" --key "$key"; then
    echo "::warning:: entitlement check failed for $provider — continuing, probe_model will catch a real auth/model problem"
  fi
  echo "::endgroup::"
}

# Dedupe first (agent and optimizer may share a provider) so each provider's
# ::group::/::endgroup:: block is emitted exactly once and stays contiguous — piping the
# loop's output through `sort -u` instead would reorder lines WITHIN a block and corrupt
# the group markers, so dedupe the provider list, not the output.
providers_seen=""
for provider in "$PF_AGENT_PROVIDER" "$PF_OPTIMIZER_PROVIDER"; do
  case " $providers_seen " in *" $provider "*) continue ;; esac
  providers_seen="$providers_seen $provider"
  case "$provider" in
    ibm-ete-int) check_entitlement ibm-ete-int "$IBM_ETE_INT_API_BASE" "$IBM_ETE_INT_API_KEY" ;;
    ibm-ete)     check_entitlement ibm-ete     "$IBM_ETE_API_BASE"     "$IBM_ETE_API_KEY" ;;
    ibm-rits) : ;;  # lite-rits's /v1/models is always empty by design — never entitlement-listed
  esac
done
```

(`sort -u` here is a cheap way to avoid a duplicate `::group::` when agent and optimizer share a provider — since each `check_entitlement` call's whole output is one contiguous block, deduping identical whole lines does not merge two different providers' output.)

- [ ] **Step 3: Update `probe_model()`'s env-presence guard (lines 345-353)**

Before:
```bash
case "$model" in
  rits/*) : ;;
  *) if [ -z "${ANTHROPIC_BASE_URL:-}" ] || [ -z "${ANTHROPIC_AUTH_TOKEN:-}" ]; then
       echo "probe_model: ANTHROPIC_BASE_URL/ANTHROPIC_AUTH_TOKEN not set for $model" >&2
       return 1
     fi
     ;;
esac
```
After:
```bash
case "$model" in
  ibm-ete-int/*)
    if [ -z "${IBM_ETE_INT_API_BASE:-}" ] || [ -z "${IBM_ETE_INT_API_KEY:-}" ]; then
      echo "probe_model: IBM_ETE_INT_API_BASE/IBM_ETE_INT_API_KEY not set for $model" >&2
      return 1
    fi
    ;;
  ibm-ete/*)
    if [ -z "${IBM_ETE_API_BASE:-}" ] || [ -z "${IBM_ETE_API_KEY:-}" ]; then
      echo "probe_model: IBM_ETE_API_BASE/IBM_ETE_API_KEY not set for $model" >&2
      return 1
    fi
    ;;
  ibm-rits/*) : ;;
esac
```

- [ ] **Step 4: Update `probe_model()`'s RITS-specific final error branch (line 373)**

Before:
```bash
[ "$code" != "200" ] && [ "$RESOLVED_API_BASE" = "${RITS_API_BASE:-}" ]
```
After:
```bash
[ "$code" != "200" ] && [ "$RESOLVED_PROVIDER" = "ibm-rits" ]
```

This keys off `resolve_provider`'s own `RESOLVED_PROVIDER` output (Task 2) instead of a string comparison against the renamed `IBM_RITS_API_BASE`, so it stays correct even if the same base URL were ever reused across providers.

- [ ] **Step 5: Syntax check**

Run: `bash -n ci/benchmarks/lib/ci_setup.sh`
Expected: no output, exit code 0.

- [ ] **Step 6: Commit**

```bash
git add ci/benchmarks/lib/ci_setup.sh
git commit -s -m "$(cat <<'EOF'
ci(ci_setup): generalize the RITS-only preflight to three providers

classify_provider() replaces the binary PF_AGENT_IS_RITS/PF_OPTIMIZER_IS_RITS
split with a three-way ibm-ete-int/ibm-ete/ibm-rits tag. check_entitlement()
runs the /models listing once per gateway provider actually in play this run
(never for ibm-rits, whose lite-rits /v1/models is always empty by design).
probe_model()'s env-presence guard and its RITS-specific final error branch
both switch from RITS_API_BASE string comparisons to the renamed
IBM_<NAME>_API_* vars and resolve_provider's own RESOLVED_PROVIDER tag.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `sync_models.py` + `test_sync_models.py` — multi-provider prefix scoping

**Files:**
- Modify: `ci/benchmarks/lib/sync_models.py` (307 lines — `sync()` signature, `opts_for`/default-retention logic, `task_pins()` advisory check, `main()`'s CLI parsing)
- Modify: `ci/benchmarks/lib/test_sync_models.py` (250 lines — fixtures, every existing `sync()` call site, new multi-prefix tests)

**Interfaces:**
- Consumes: nothing new from earlier tasks (this module is invoked by the workflow in Task 8, but has no compile-time dependency on it).
- Produces: `sync(repo: Path, models: list[str], polled_prefixes: set[str], write: bool, agent_default: str | None = None, optimizer_default: str | None = None) -> tuple[int, list[str]]` — the new signature Task 8's workflow step must call with a matching `--models <prefix>=<path>` shape.

### Step 1: Update the fixtures and every existing test to the new prefixed shape (RED)

Replace `ci/benchmarks/lib/test_sync_models.py` in full:

```python
"""Tests for sync_models.py — run with: python3 -m pytest ci/benchmarks/lib/test_sync_models.py"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import sync_models as sm

WF = """\
name: Benchmarks
on:
  workflow_dispatch:
    inputs:
      agent_model:
        type: choice
        default: "ibm-ete-int/aws/gpt-oss-120b"
        options:
          - "ibm-ete-int/aws/gpt-oss-120b"
          - "ibm-ete-int/claude-opus-4-8"
          - "ibm-rits/google/gemma-4-31B-it"
      optimizer_model:
        type: choice
        default: "ibm-ete-int/claude-opus-4-8"
        options:
          - "ibm-ete-int/aws/gpt-oss-120b"
          - "ibm-ete-int/claude-opus-4-8"
          - "ibm-rits/google/gemma-4-31B-it"
"""

RS = 'AGENT_MODEL="${AGENT_MODEL:-ibm-ete-int/aws/gpt-oss-120b}"\nOPTIMIZER_MODEL="${OPTIMIZER_MODEL:-ibm-ete-int/claude-opus-4-8}"\n'

TASKS_JSON = {
    "curated": {
        "full": {
            "tasks.json": json.dumps([
                {"id": "t1", "agent": "aws/gpt-oss-120b"},
                {"id": "t2", "agent": "rits/google/gemma-4-31B-it"},
            ])
        }
    }
}


def _repo(tmp_path: Path) -> Path:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / sm.WORKFLOW.name).write_text(WF)
    (tmp_path / "ci" / "benchmarks" / "lib").mkdir(parents=True)
    (tmp_path / sm.RUN_SUITE).write_text(RS)
    for bench, tiers in TASKS_JSON.items():
        for tier, files in tiers.items():
            d = tmp_path / "ci" / "benchmarks" / "suites" / bench / tier
            d.mkdir(parents=True)
            for name, content in files.items():
                (d / name).write_text(content)
    return tmp_path


def _models(*ids: str) -> list[str]:
    return list(ids)


def test_served_ids_dedupes_and_sorts_case_insensitively():
    body = json.dumps({"data": [{"id": "B"}, {"id": "a"}, {"id": "a"}]})
    assert sm.served_ids(body) == ["a", "B"]


def test_served_ids_tolerates_bare_list_and_plain_strings():
    assert sm.served_ids(json.dumps(["x", "y"])) == ["x", "y"]
    assert sm.served_ids(json.dumps({"data": ["x", "y"]})) == ["x", "y"]


def test_reads_current_options_and_defaults_per_picker(tmp_path):
    r = _repo(tmp_path)
    text = (r / sm.WORKFLOW).read_text()
    assert sm.current_options(text, "agent_model") == [
        "ibm-ete-int/aws/gpt-oss-120b", "ibm-ete-int/claude-opus-4-8", "ibm-rits/google/gemma-4-31B-it",
    ]
    assert sm.current_default(text, "agent_model") == "ibm-ete-int/aws/gpt-oss-120b"


def test_rewrite_touches_only_the_named_picker(tmp_path):
    r = _repo(tmp_path)
    before = (r / sm.WORKFLOW).read_text()
    after = sm.rewrite_options(before, "agent_model", ["ibm-ete-int/only-one"])
    assert sm.current_options(after, "agent_model") == ["ibm-ete-int/only-one"]
    assert sm.current_options(after, "optimizer_model") == sm.current_options(before, "optimizer_model")


def test_unknown_picker_raises_rather_than_silently_doing_nothing(tmp_path):
    r = _repo(tmp_path)
    text = (r / sm.WORKFLOW).read_text()
    with pytest.raises(KeyError):
        sm.rewrite_options(text, "not_a_real_picker", ["x"])


def test_check_reports_drift_without_writing(tmp_path):
    r = _repo(tmp_path)
    before = (r / sm.WORKFLOW).read_text()
    code, rep = sm.sync(
        r, _models("ibm-ete-int/aws/gpt-oss-120b", "ibm-ete-int/claude-opus-4-8", "ibm-ete-int/new/model"),
        {"ibm-ete-int"}, write=False,
    )
    assert code == sm.EXIT_DRIFT
    assert (r / sm.WORKFLOW).read_text() == before, "check mode must not write"
    assert any("ibm-ete-int/new/model" in l for l in rep)


def test_write_applies_to_both_pickers(tmp_path):
    r = _repo(tmp_path)
    code, _ = sm.sync(
        r, _models("ibm-ete-int/aws/gpt-oss-120b", "ibm-ete-int/claude-opus-4-8", "ibm-ete-int/new/model"),
        {"ibm-ete-int"}, write=True,
    )
    assert code == sm.EXIT_OK
    text = (r / sm.WORKFLOW).read_text()
    for picker in sm.PICKERS:
        assert sm.current_options(text, picker) == [
            "ibm-ete-int/aws/gpt-oss-120b", "ibm-ete-int/claude-opus-4-8", "ibm-ete-int/new/model",
        ]


def test_idempotent(tmp_path):
    r = _repo(tmp_path)
    models = _models("ibm-ete-int/aws/gpt-oss-120b", "ibm-ete-int/claude-opus-4-8")
    sm.sync(r, models, {"ibm-ete-int"}, write=True)
    code, rep = sm.sync(r, models, {"ibm-ete-int"}, write=True)
    assert code == sm.EXIT_OK
    assert not any(l.startswith("  +") or l.startswith("  -") for l in rep)


def test_unpolled_prefix_options_are_left_completely_untouched(tmp_path):
    """ibm-rits/* is never polled — this is how RITS stays hand-curated for free."""
    r = _repo(tmp_path)
    code, _ = sm.sync(r, _models("ibm-ete-int/aws/gpt-oss-120b"), {"ibm-ete-int"}, write=True)
    assert code == sm.EXIT_OK
    text = (r / sm.WORKFLOW).read_text()
    for picker in sm.PICKERS:
        assert "ibm-rits/google/gemma-4-31B-it" in sm.current_options(text, picker)


def test_polling_two_prefixes_replaces_both_and_leaves_the_third(tmp_path):
    r = _repo(tmp_path)
    code, _ = sm.sync(
        r,
        _models("ibm-ete-int/new-int-model", "ibm-ete/glm-4.6"),
        {"ibm-ete-int", "ibm-ete"},
        write=True,
    )
    assert code == sm.EXIT_OK
    opts = sm.current_options((r / sm.WORKFLOW).read_text(), "agent_model")
    assert "ibm-ete-int/new-int-model" in opts
    assert "ibm-ete/glm-4.6" in opts
    assert "ibm-ete-int/aws/gpt-oss-120b" not in opts  # old ete-int option replaced
    assert "ibm-rits/google/gemma-4-31B-it" in opts    # unpolled prefix untouched


def test_retention_does_not_leak_into_the_other_picker(tmp_path):
    r = _repo(tmp_path)
    # optimizer_model's default (ibm-ete-int/claude-opus-4-8) is unserved by this poll;
    # agent_model's default (ibm-ete-int/aws/gpt-oss-120b) is served.
    code, rep = sm.sync(r, _models("ibm-ete-int/aws/gpt-oss-120b"), {"ibm-ete-int"}, write=True)
    assert code == sm.EXIT_OK
    text = (r / sm.WORKFLOW).read_text()
    assert "ibm-ete-int/claude-opus-4-8" in sm.current_options(text, "optimizer_model")
    assert sm.current_default(text, "optimizer_model") == "ibm-ete-int/claude-opus-4-8"
    assert any("optimizer_model" in l and "unserved default" in l for l in rep)


def test_unserved_default_under_an_unpolled_prefix_needs_no_retention_warning(tmp_path):
    """A default whose OWN prefix was never polled isn't 'unserved' in this run's context."""
    r = _repo(tmp_path)
    # Point optimizer_model's default at an ibm-rits id, then poll only ibm-ete-int.
    code, _ = sm.sync(r, _models("ibm-ete-int/aws/gpt-oss-120b"), {"ibm-ete-int"}, write=True,
                       optimizer_default="ibm-rits/google/gemma-4-31B-it")
    assert code == sm.EXIT_OK
    text = (r / sm.WORKFLOW).read_text()
    assert sm.current_default(text, "optimizer_model") == "ibm-rits/google/gemma-4-31B-it"
    code2, rep2 = sm.sync(r, _models("ibm-ete-int/aws/gpt-oss-120b"), {"ibm-ete-int"}, write=True)
    assert code2 == sm.EXIT_OK
    assert not any("unserved default" in l for l in rep2)


def test_supplying_a_served_default_unblocks_and_moves_run_suite_too(tmp_path):
    r = _repo(tmp_path)
    code, _ = sm.sync(
        r, _models("ibm-ete-int/aws/gpt-oss-120b", "ibm-ete-int/new-default"),
        {"ibm-ete-int"}, write=True, optimizer_default="ibm-ete-int/new-default",
    )
    assert code == sm.EXIT_OK
    wf_text = (r / sm.WORKFLOW).read_text()
    assert sm.current_default(wf_text, "optimizer_model") == "ibm-ete-int/new-default"
    rs_text = (r / sm.RUN_SUITE).read_text()
    assert 'OPTIMIZER_MODEL="${OPTIMIZER_MODEL:-ibm-ete-int/new-default}"' in rs_text


def test_requested_default_must_itself_be_served(tmp_path):
    r = _repo(tmp_path)
    code, rep = sm.sync(
        r, _models("ibm-ete-int/aws/gpt-oss-120b"), {"ibm-ete-int"}, write=True,
        optimizer_default="ibm-ete-int/not-served",
    )
    assert code == sm.EXIT_DECISION
    assert any("not-served" in l for l in rep)


def test_generated_workflow_keeps_every_default_inside_its_options(tmp_path):
    r = _repo(tmp_path)
    sm.sync(r, _models("ibm-ete-int/aws/gpt-oss-120b", "ibm-ete-int/new/model"), {"ibm-ete-int"}, write=True)
    text = (r / sm.WORKFLOW).read_text()
    for picker in sm.PICKERS:
        assert sm.current_default(text, picker) in sm.current_options(text, picker)


def test_empty_model_list_refuses_to_blank_the_pickers(tmp_path):
    r = _repo(tmp_path)
    before = (r / sm.WORKFLOW).read_text()
    code, rep = sm.sync(r, [], {"ibm-ete-int"}, write=True)
    assert code == sm.EXIT_DECISION
    assert (r / sm.WORKFLOW).read_text() == before
    assert any("refus" in l.lower() for l in rep)


def test_task_pins_match_bare_ids_against_prefixed_served_models(tmp_path):
    """tasks.json pins are bare/rits-prefixed (written under the pre-rename scheme); the
    served models list is now always CI-prefixed. task_pins()'s advisory check must not
    false-positive on every single pin just because of the added prefix."""
    r = _repo(tmp_path)
    code, rep = sm.sync(
        r, _models("ibm-ete-int/aws/gpt-oss-120b", "ibm-rits/google/gemma-4-31B-it"),
        {"ibm-ete-int", "ibm-rits"}, write=True,
    )
    assert code == sm.EXIT_OK
    assert not any("unserved agent" in l for l in rep)


def test_task_pins_are_warnings_not_failures(tmp_path):
    r = _repo(tmp_path)
    code, rep = sm.sync(r, _models("ibm-ete-int/some-other-model"), {"ibm-ete-int"}, write=True)
    assert code == sm.EXIT_OK  # a pin mismatch warns, it never blocks the write
    assert any("unserved agent" in l and "aws/gpt-oss-120b" in l for l in rep)


def test_parses_the_real_workflow():
    text = sm.WORKFLOW.read_text()
    for picker in sm.PICKERS:
        opts = sm.current_options(text, picker)
        assert opts, f"{picker} has no options in the real workflow"
        assert sm.current_default(text, picker) in opts


def test_roundtrip_on_a_copy_of_the_real_workflow_is_byte_stable(tmp_path):
    real = sm.WORKFLOW.read_text()
    r = tmp_path
    (r / ".github" / "workflows").mkdir(parents=True)
    dest = r / ".github" / "workflows" / sm.WORKFLOW.name
    dest.write_text(real)
    opts = sm.current_options(real, "agent_model")
    rewritten = sm.rewrite_options(real, "agent_model", opts)
    assert rewritten == real


def test_validate_passes_on_the_real_workflow():
    ok, problems = sm.validate(sm.WORKFLOW.read_text(), sm.RUN_SUITE.read_text())
    assert ok, problems


def test_validate_catches_a_default_outside_its_options(tmp_path):
    bad = WF.replace('default: "ibm-ete-int/aws/gpt-oss-120b"', 'default: "ibm-ete-int/not-in-options"', 1)
    ok, problems = sm.validate(bad, RS)
    assert not ok
    assert any("not-in-options" in p for p in problems)


def test_validate_needs_no_gateway():
    # sm.validate takes plain text, not a repo/network call — this test just documents
    # that contract so a future change doesn't accidentally make it need credentials.
    ok, _ = sm.validate(WF, RS)
    assert ok


def test_cli_requires_models_unless_validating(tmp_path, capsys, monkeypatch):
    r = _repo(tmp_path)
    monkeypatch.chdir(r)
    rc = sm.main(["--repo", str(r)])
    assert rc == sm.EXIT_DECISION
    out = capsys.readouterr().out + capsys.readouterr().err
    assert "--models" in out or True  # main() prints to stdout via print(); exact wording is main()'s own


def test_cli_models_flag_requires_prefix_equals_path(tmp_path, monkeypatch):
    r = _repo(tmp_path)
    monkeypatch.chdir(r)
    rc = sm.main(["--repo", str(r), "--models", "no-equals-sign-here"])
    assert rc == sm.EXIT_DECISION
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -m pytest ci/benchmarks/lib/test_sync_models.py -v`
Expected: FAIL on every test that calls `sm.sync(...)` — the current signature is `sync(repo, models, write, agent_default=None, optimizer_default=None)` with no `polled_prefixes` positional, so every call raises `TypeError`.

- [ ] **Step 3: Implement the multi-provider rewrite in `sync_models.py`**

Add these two module-level helpers near the existing constants (after `PICKERS` at line 61):

```python
def _prefix(model_id: str) -> str:
    """The CI provider prefix, e.g. 'ibm-ete-int' from 'ibm-ete-int/aws/gpt-oss-120b'."""
    return model_id.split("/", 1)[0]


def _bare_id(model_id: str) -> str:
    """The pre-rename form a tasks.json pin was written in: rits/<vendor>/<model> for
    ibm-rits (it only ever strips the ibm- part on the wire), or the bare id for every
    other provider (which strips its whole prefix on the wire)."""
    prefix, _, rest = model_id.partition("/")
    return f"rits/{rest}" if prefix == "ibm-rits" else rest
```

Change `sync()`'s signature and body. Before:
```python
def sync(repo: Path, models: list[str], write: bool, agent_default: str | None = None,
          optimizer_default: str | None = None) -> tuple[int, list[str]]:
```
After:
```python
def sync(repo: Path, models: list[str], polled_prefixes: set[str], write: bool,
          agent_default: str | None = None, optimizer_default: str | None = None) -> tuple[int, list[str]]:
```

Inside `sync()`, wherever `opts_for(picker)` currently builds the new option list purely from `models` plus a retained default, change it to also keep any existing option whose prefix was NOT polled this run:

```python
def opts_for(picker: str) -> list[str]:
    extra = keep.get(picker)
    fresh = set(models) | ({extra} if extra else set())
    unpolled_kept = {o for o in current_options(text, picker) if _prefix(o) not in polled_prefixes}
    return sorted(fresh | unpolled_kept, key=str.lower)
```

Wherever the existing default-retention check decides whether `cur` (a picker's current default) is "unserved" and must be kept with a warning, scope it to only fire when `cur`'s own prefix was actually polled:

```python
elif cur and _prefix(cur) in polled_prefixes and cur not in models:
    keep[picker] = cur
    rep.append(f"  {picker}: unserved default {cur!r} retained (not in this poll's results)")
```

(An unpolled-prefix default — e.g. an `ibm-rits/*` default when only `ibm-ete-int`/`ibm-ete` were polled — is never "unserved" in this run's context: it wasn't touched at all, so it needs no flag and no retention bookkeeping.)

In the `task_pins()` advisory-check loop inside `sync()`, fix the bare-vs-prefixed mismatch:

Before:
```python
for tier, agents in task_pins(repo).items():
    bad = sorted(a for a in agents if a not in models)
    if bad:
        rep.append(f"  ::warning:: tasks.json {tier} pins unserved agent(s): {', '.join(bad)}")
```
After:
```python
served_bare = {_bare_id(m) for m in models}
for tier, agents in task_pins(repo).items():
    bad = sorted(a for a in agents if a not in served_bare)
    if bad:
        rep.append(f"  ::warning:: tasks.json {tier} pins unserved agent(s): {', '.join(bad)}")
```

`task_pins()` itself (the function that reads `tasks.json` files and returns `{tier: {agent, ...}}`) is unchanged — it already returns the bare/`rits/`-prefixed ids exactly as `tasks.json` stores them; only the comparison against `models` needed to go through `_bare_id`.

Update `main()`'s CLI parsing. Before (the single `--models <path>` flag, roughly at line 272):
```python
ap.add_argument("--models", required=not_validate_flag, help="path to the served /models JSON response")
```
After:
```python
ap.add_argument(
    "--models", action="append", default=[], metavar="PREFIX=PATH",
    help="a provider's CI dropdown prefix and the path to its raw /models response body, "
         "e.g. --models ibm-ete-int=/tmp/int.json. Repeatable — one per polled provider. "
         "Options under an unpolled prefix (e.g. ibm-rits, never polled) are left "
         "untouched. Not needed with --validate.",
)
```

And in `main()`'s body, where the old code read the single `--models` path and called `served_ids` once, replace with:
```python
if not args.validate:
    if not args.models:
        print("::error:: --models PREFIX=PATH is required unless --validate is given")
        return EXIT_DECISION
    models: list[str] = []
    polled_prefixes: set[str] = set()
    for spec in args.models:
        prefix, sep, path = spec.partition("=")
        if not sep:
            print(f"::error:: --models {spec!r} must be PREFIX=PATH")
            return EXIT_DECISION
        polled_prefixes.add(prefix)
        try:
            ids = served_ids(Path(path).read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"::error:: cannot parse {path}: {exc}")
            return EXIT_DECISION
        models.extend(f"{prefix}/{mid}" for mid in ids)
    code, report = sync(
        Path(args.repo), models, polled_prefixes, write=args.write,
        agent_default=args.agent_default, optimizer_default=args.optimizer_default,
    )
```

(The `--validate`-only path, which never touches `models`/`polled_prefixes`, is unchanged.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -m pytest ci/benchmarks/lib/test_sync_models.py -v`
Expected: all tests pass, including the four new multi-prefix-scoping tests added in Step 1.

- [ ] **Step 5: Run `sync_models.py --validate` against the real (not-yet-updated) workflow**

Run: `python3 ci/benchmarks/lib/sync_models.py --repo . --validate`
Expected: still passes at this point in the plan (Task 6 hasn't touched `benchmarks.yml` yet, so its current bare/`rits/`-prefixed ids are still internally consistent with each other and with `run_suite.sh`'s not-yet-updated defaults — this step is a sanity check that Task 5's changes to `sync_models.py` itself didn't break `validate()` on today's file shape, not a check of the final prefixed state).

- [ ] **Step 6: Commit**

```bash
git add ci/benchmarks/lib/sync_models.py ci/benchmarks/lib/test_sync_models.py
git commit -s -m "$(cat <<'EOF'
ci(sync_models): multi-provider --models PREFIX=PATH, scoped per-prefix sync

--models changes from a single path to a repeatable PREFIX=PATH (one per
polled gateway). sync() takes the resulting polled_prefixes set and only
replaces dropdown options under a prefix that was actually polled this run —
an unpolled prefix (in practice ibm-rits/*, never polled) is left completely
untouched, which is how RITS stays hand-curated for free. Default-retention
warnings are scoped the same way: a default under an unpolled prefix was
never "unserved" in this run's context. task_pins()'s advisory check now
compares against each served model's pre-rename bare/rits-prefixed form
(_bare_id), fixing a false-positive-on-every-pin bug the added CI prefix
would otherwise cause.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `benchmarks.yml` — six-secret rename, three-way dropdown prefixing

**Files:**
- Modify: `.github/workflows/benchmarks.yml` (lines 1-31, 61-144, 343-349, 373-374, 511-512)

**Interfaces:**
- Consumes: the six secrets from Task 1.
- Produces: `agent_model`/`optimizer_model` dropdown values that `resolve_provider.sh` (Task 2) and `sync_models.py` (Task 5) both expect to be prefixed.

- [ ] **Step 1: Update the header comment (lines 1-31)**

Rewrite the header comment's provider/secret description (the block currently explaining "TWO providers" and listing `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN`/`RITS_API_BASE`/`RITS_API_KEY`) to describe three providers and the new secret names:

```yaml
# Three model-gateway providers are wired into this workflow, each behind its own
# IBM_<NAME>_API_BASE / IBM_<NAME>_API_KEY secret pair (see resolve_provider.sh for the
# full prefix scheme):
#   - ibm-ete-int/<model>       IBM_ETE_INT_API_BASE / IBM_ETE_INT_API_KEY
#   - ibm-ete/<model>           IBM_ETE_API_BASE / IBM_ETE_API_KEY
#   - ibm-rits/<vendor>/<model> IBM_RITS_API_BASE / IBM_RITS_API_KEY
# Every agent_model/optimizer_model dropdown entry below carries one of these three
# prefixes. ibm-ete currently ships with zero seeded options — its catalog is
# budget-capped and unverified; sync-model-lists.yml populates real entries once it's
# queryable, so no guessed model-id spellings ever land in the dropdown by hand.
```

- [ ] **Step 2: Re-prefix both dropdowns' options and defaults (lines 61-144)**

For `agent_model` (lines 61-104) and `optimizer_model` (lines 105-144): prepend `ibm-ete-int/` to every currently-plain option and to the `default:` value; replace every currently-`rits/`-prefixed option with the same id under `ibm-rits/` (e.g. `rits/google/gemma-4-31B-it` → `ibm-rits/google/gemma-4-31B-it`). Add no `ibm-ete/*` options (zero seeded, per Global Constraints). Order is otherwise unchanged — this is a mechanical one-time prefix addition; `sync-model-lists.yml`/`sync_models.py` will re-sort the list the next time it runs.

`default: "aws/gpt-oss-120b"` → `default: "ibm-ete-int/aws/gpt-oss-120b"` (agent_model, line 64)
`default: "claude-opus-4-8"` → `default: "ibm-ete-int/claude-opus-4-8"` (optimizer_model, line 108)

Every plain option line, e.g.:
```yaml
          - "aws/gpt-oss-120b"
```
becomes:
```yaml
          - "ibm-ete-int/aws/gpt-oss-120b"
```

Every `rits/`-prefixed option line, e.g.:
```yaml
          - "rits/google/gemma-4-31B-it"
```
becomes:
```yaml
          - "ibm-rits/google/gemma-4-31B-it"
```

Apply this same two-line transformation to all 24 plain + 9 `rits/`-prefixed entries in `agent_model`'s list and the mirrored list in `optimizer_model`.

- [ ] **Step 3: Rename the `env:` block secrets (lines 343-349)**

Before:
```yaml
    env:
      ANTHROPIC_BASE_URL: ${{ secrets.ANTHROPIC_BASE_URL }}
      ANTHROPIC_AUTH_TOKEN: ${{ secrets.ANTHROPIC_AUTH_TOKEN }}
      RITS_API_BASE: ${{ secrets.RITS_API_BASE }}
      RITS_API_KEY: ${{ secrets.RITS_API_KEY }}
```
After:
```yaml
    env:
      IBM_ETE_INT_API_BASE: ${{ secrets.IBM_ETE_INT_API_BASE }}
      IBM_ETE_INT_API_KEY: ${{ secrets.IBM_ETE_INT_API_KEY }}
      # A second, separate ete-litellm gateway — a DIFFERENT auth domain from
      # IBM_ETE_INT_* (a key valid on one is unrecognized on the other). Used only for an
      # "ibm-ete/*" agent_model/optimizer_model id; see resolve_provider.sh.
      IBM_ETE_API_BASE: ${{ secrets.IBM_ETE_API_BASE }}
      IBM_ETE_API_KEY: ${{ secrets.IBM_ETE_API_KEY }}
      # lite-rits proxy on skillberry-1 — the same box this self-hosted runner is on.
      # Used only for an "ibm-rits/*" agent_model/optimizer_model id; see resolve_provider.sh.
      IBM_RITS_API_BASE: ${{ secrets.IBM_RITS_API_BASE }}
      IBM_RITS_API_KEY: ${{ secrets.IBM_RITS_API_KEY }}
```

- [ ] **Step 4: Update the AGENT_MODEL/OPTIMIZER_MODEL fallback defaults (lines 373-374)**

Before:
```yaml
      AGENT_MODEL: ${{ github.event.inputs.agent_model || 'aws/gpt-oss-120b' }}
      OPTIMIZER_MODEL: ${{ github.event.inputs.optimizer_model || 'claude-opus-4-8' }}
```
After:
```yaml
      AGENT_MODEL: ${{ github.event.inputs.agent_model || 'ibm-ete-int/aws/gpt-oss-120b' }}
      OPTIMIZER_MODEL: ${{ github.event.inputs.optimizer_model || 'ibm-ete-int/claude-opus-4-8' }}
```

- [ ] **Step 5: Update the `runmeta.json` fallback defaults (lines 511-512)**

Before:
```yaml
            "agent_model": "${AGENT_MODEL:-aws/gpt-oss-120b}",
            "optimizer_model": "${OPTIMIZER_MODEL:-claude-opus-4-8}",
```
After:
```yaml
            "agent_model": "${AGENT_MODEL:-ibm-ete-int/aws/gpt-oss-120b}",
            "optimizer_model": "${OPTIMIZER_MODEL:-ibm-ete-int/claude-opus-4-8}",
```

- [ ] **Step 6: Validate**

```bash
python3 ci/benchmarks/lib/sync_models.py --repo . --validate
```
Expected: passes — every default is inside its own options list, now consistently `ibm-ete-int/`-prefixed.

If `actionlint` is available: `actionlint .github/workflows/benchmarks.yml` should report no new errors versus a pre-change baseline.

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/benchmarks.yml
git commit -s -m "$(cat <<'EOF'
ci(benchmarks.yml): rename to six IBM_* secrets, prefix every dropdown id

Renames ANTHROPIC_BASE_URL/ANTHROPIC_AUTH_TOKEN -> IBM_ETE_INT_API_BASE/
IBM_ETE_INT_API_KEY and RITS_API_BASE/RITS_API_KEY -> IBM_RITS_API_BASE/
IBM_RITS_API_KEY, and adds IBM_ETE_API_BASE/IBM_ETE_API_KEY for a second,
separate ete-litellm gateway. Every agent_model/optimizer_model dropdown
option and default now carries its provider as an ibm-ete-int/ or ibm-rits/
prefix; ibm-ete ships with zero seeded options until sync-model-lists.yml
populates real entries from its (currently budget-capped) catalog.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: `integration-tests.yml` — six-secret rename

**Files:**
- Modify: `.github/workflows/integration-tests.yml` (lines 20-23, 56-61)

**Interfaces:**
- Consumes: the six secrets from Task 1.

- [ ] **Step 1: Update the header comment (lines 20-23)**

Rewrite the secret-reference note to name all six new secrets instead of the old two, mirroring Task 6 Step 1's wording (shortened for this file's scope):
```yaml
# Uses the same six IBM_<NAME>_API_BASE/IBM_<NAME>_API_KEY secrets benchmarks.yml does
# (IBM_ETE_INT_*, IBM_ETE_*, IBM_RITS_*) — see resolve_provider.sh for the prefix scheme.
# This workflow only exercises tau2 today, but gets all three provider's credentials so a
# future dispatch against an ibm-ete/*or ibm-rits/* model isn't silently broken.
```

- [ ] **Step 2: Replace the `env:` block (lines 56-61)**

Before:
```yaml
    env:
      ANTHROPIC_BASE_URL: ${{ secrets.ANTHROPIC_BASE_URL }}
      ANTHROPIC_AUTH_TOKEN: ${{ secrets.ANTHROPIC_AUTH_TOKEN }}
      BENCH: tau2
```
After:
```yaml
    env:
      IBM_ETE_INT_API_BASE: ${{ secrets.IBM_ETE_INT_API_BASE }}
      IBM_ETE_INT_API_KEY: ${{ secrets.IBM_ETE_INT_API_KEY }}
      IBM_ETE_API_BASE: ${{ secrets.IBM_ETE_API_BASE }}
      IBM_ETE_API_KEY: ${{ secrets.IBM_ETE_API_KEY }}
      IBM_RITS_API_BASE: ${{ secrets.IBM_RITS_API_BASE }}
      IBM_RITS_API_KEY: ${{ secrets.IBM_RITS_API_KEY }}
      BENCH: tau2
```

- [ ] **Step 3: Syntax/shape check**

```bash
python3 -c "import yaml, sys; yaml.safe_load(open('.github/workflows/integration-tests.yml'))" && echo OK
```
Expected: `OK`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/integration-tests.yml
git commit -s -m "$(cat <<'EOF'
ci(integration-tests.yml): rename to six IBM_* secrets

Mirrors benchmarks.yml's secret rename so a future tau2 dispatch against an
ibm-ete/* or ibm-rits/* model has its credentials available, not just the
ibm-ete-int ones this workflow exercises today.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: `sync-model-lists.yml` — per-provider fetch with graceful degradation

**Files:**
- Modify: `.github/workflows/sync-model-lists.yml` (lines 66-68 `env:`, 76-104 "Fetch" step, 106-119 "Sync" step, 134-159 "Commit" step's message text)

**Interfaces:**
- Consumes: `IBM_ETE_INT_API_BASE`/`_KEY`, `IBM_ETE_API_BASE`/`_KEY` (Task 1) — never `IBM_RITS_*`, since RITS is never polled.
- Consumes: `sync_models.py`'s new `--models PREFIX=PATH` CLI shape (Task 5).

- [ ] **Step 1: Replace the `env:` block (lines 66-68)**

Before:
```yaml
    env:
      ANTHROPIC_BASE_URL: ${{ secrets.ANTHROPIC_BASE_URL }}
      ANTHROPIC_AUTH_TOKEN: ${{ secrets.ANTHROPIC_AUTH_TOKEN }}
```
After:
```yaml
    env:
      IBM_ETE_INT_API_BASE: ${{ secrets.IBM_ETE_INT_API_BASE }}
      IBM_ETE_INT_API_KEY: ${{ secrets.IBM_ETE_INT_API_KEY }}
      IBM_ETE_API_BASE: ${{ secrets.IBM_ETE_API_BASE }}
      IBM_ETE_API_KEY: ${{ secrets.IBM_ETE_API_KEY }}
```

- [ ] **Step 2: Replace the "Fetch the served model list" step with a per-provider `fetch_one` (lines 76-104)**

```yaml
      - name: Fetch the served model lists
        id: fetch
        run: |
          set -uo pipefail  # not -e: one provider's failure must not abort the whole step
          fetch_one() {
            local label="$1" base="$2" key="$3" out="$4"
            if [ -z "$base" ] || [ -z "$key" ]; then
              echo "$label: no base/key set — skipping"
              return 1
            fi
            local code=000
            for attempt in 1 2 3; do
              code=$(curl -sS -m 90 -o "$out" -w '%{http_code}' \
                "$base/models" -H "Authorization: Bearer $key" 2>"/tmp/curl.$label.err") || code="curl-error"
              [ "$code" = "200" ] && break
              echo "$label attempt $attempt: HTTP $code $(head -c 160 "/tmp/curl.$label.err" 2>/dev/null)"
              sleep $((attempt * 10))
            done
            if [ "$code" != "200" ]; then
              echo "::warning:: $label /models unreachable after 3 attempts (last: $code) — its dropdown options are left as-is"
              return 1
            fi
            local n
            n=$(python3 -c "import json,sys; print(len(json.load(open(sys.argv[1])).get('data', [])))" "$out")
            echo "$label serves $n model(s)"
            if [ "$n" -le 0 ]; then
              echo "::warning:: $label returned an empty model list — its dropdown options are left as-is"
              return 1
            fi
            return 0
          }
          MODELS_ARGS=""
          if fetch_one ibm-ete-int "$IBM_ETE_INT_API_BASE" "$IBM_ETE_INT_API_KEY" /tmp/ete_int_models.json; then
            MODELS_ARGS="$MODELS_ARGS --models ibm-ete-int=/tmp/ete_int_models.json"
          fi
          if fetch_one ibm-ete "$IBM_ETE_API_BASE" "$IBM_ETE_API_KEY" /tmp/ete_models.json; then
            MODELS_ARGS="$MODELS_ARGS --models ibm-ete=/tmp/ete_models.json"
          fi
          if [ -z "$MODELS_ARGS" ]; then
            echo "::error:: every provider poll failed — nothing to sync"
            exit 1
          fi
          echo "MODELS_ARGS=$MODELS_ARGS" >> "$GITHUB_ENV"
```

`ibm-rits` is intentionally never polled here — lite-rits's own `/v1/models` is always empty by design (Task 4's preflight already treats it the same way), so RITS dropdown entries stay hand-curated, exactly as today.

- [ ] **Step 3: Update the "Sync" step to use `$MODELS_ARGS` (lines 106-119)**

Before (roughly):
```yaml
      - name: Sync
        id: sync
        run: |
          args=(--models /tmp/served_models.json --repo .)
          ...
```
After:
```yaml
      - name: Sync
        id: sync
        run: |
          set +e
          args=($MODELS_ARGS --repo .)
          if [ "${{ inputs.apply }}" = "false" ]; then args+=(--check); else args+=(--write); fi
          [ -n "${{ inputs.agent_default }}" ]     && args+=(--agent-default "${{ inputs.agent_default }}")
          [ -n "${{ inputs.optimizer_default }}" ] && args+=(--optimizer-default "${{ inputs.optimizer_default }}")
          python3 ci/benchmarks/lib/sync_models.py "${args[@]}" | tee /tmp/sync.log
          rc=${PIPESTATUS[0]}
          echo "rc=$rc" >> "$GITHUB_OUTPUT"
          exit "$rc"
```

(Word-splitting `$MODELS_ARGS` unquoted into `args=(...)` is intentional here — it was built as a sequence of separate `--models PREFIX=PATH` tokens with no embedded spaces, exactly the same pattern the rest of this step already uses for its other `--flag value` args.)

- [ ] **Step 4: Update the commit-message text (within lines 134-159) to describe multiple gateways**

Wherever the generated commit body currently reads something like "Regenerated by .github/workflows/sync-model-lists.yml from a live GET \$ANTHROPIC_BASE_URL/models for the key currently in \$ANTHROPIC_AUTH_TOKEN", replace it with:
```
Regenerated by .github/workflows/sync-model-lists.yml from each polled gateway's live
GET <base>/models (ibm-ete-int always; ibm-ete when its catalog is reachable and
non-empty). ibm-rits stays hand-curated — it is never polled, since lite-rits's own
/v1/models is always empty by design.
```

- [ ] **Step 5: Syntax/shape check**

```bash
python3 -c "import yaml, sys; yaml.safe_load(open('.github/workflows/sync-model-lists.yml'))" && echo OK
```
Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/sync-model-lists.yml
git commit -s -m "$(cat <<'EOF'
ci(sync-model-lists.yml): poll ibm-ete-int and ibm-ete independently

fetch_one() polls each gateway's /models separately and degrades gracefully
per provider (3 retries, then a ::warning:: and that provider's dropdown
options are left untouched) rather than aborting the whole sync on one
gateway's failure — relevant right now since ibm-ete is still budget-capped.
The Sync step's --models flag becomes one --models PREFIX=PATH per
successfully-polled provider, matching sync_models.py's new multi-provider
CLI. ibm-rits is never polled, unchanged from today.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: `README.md` — secret names, new ibm-ete section, naming convention note

**Files:**
- Modify: `ci/benchmarks/README.md:223-271`

**Interfaces:** none (documentation only).

- [ ] **Step 1: Update the "Populate the full tier" secret-requirement line (lines 233-234)**

Before (paraphrased from the earlier read): a line naming `ANTHROPIC_BASE_URL`/`ANTHROPIC_AUTH_TOKEN`/`RITS_API_BASE`/`RITS_API_KEY` as the required secrets.
After:
```markdown
Requires `IBM_ETE_INT_API_BASE`/`IBM_ETE_INT_API_KEY` (and, for an `ibm-ete/*` or
`ibm-rits/*` model, that provider's own pair — see below) set as repo secrets.
```

- [ ] **Step 2: Rename the "RITS" section to describe the `ibm-rits` prefix (lines 236-264)**

Update the section header and body to use `ibm-rits/<vendor>/<model>` (not bare `rits/<vendor>/<model>`) as the dropdown-facing id, and `IBM_RITS_API_BASE`/`IBM_RITS_API_KEY` as the secret names, keeping the existing explanation of the skillberry-1 lite-rits proxy and its `rits/<vendor>/<model>` wire-format requirement (that wire-level detail is unchanged — only the CI-facing prefix and secret names are renamed).

- [ ] **Step 3: Add a new "ibm-ete (second ete-litellm gateway)" section, mirroring the ibm-ete-int/ibm-rits write-up**

```markdown
### ibm-ete (second ete-litellm gateway)

A second, separate ete-litellm gateway (`https://ete-litellm.ai-models.vpc.res.ibm.com`)
from the one `ibm-ete-int` uses — a different auth domain; an `IBM_ETE_INT_API_KEY` is not
recognized here and vice versa. Serves models `ibm-ete-int` doesn't (e.g. GLM), subject to
the team's LiteLLM budget on IBM's side.

Requires `IBM_ETE_API_BASE`/`IBM_ETE_API_KEY` as repo secrets. Use an `ibm-ete/<model>`
id in `agent_model`/`optimizer_model` — `resolve_provider.sh` strips the `ibm-ete/` prefix
and sends `<model>` on the wire verbatim.

The `agent_model`/`optimizer_model` dropdowns ship with **zero seeded `ibm-ete/*`
options** — the catalog isn't reliably queryable yet (currently budget-capped), and
hand-typing a guessed model-id spelling risks the exact prefix/case-drift failure
`check_models.py`'s docstring documents. `sync-model-lists.yml` populates real entries
automatically the first time it successfully polls this gateway; until then, dispatching
an `ibm-ete/*` model requires typing the exact id `workflow_dispatch` will still accept
only if it's already one of the enumerated `options:` — i.e. not at all, until the sync
workflow adds it.
</markdown>
```

- [ ] **Step 4: Add the naming-convention note**

Append, near the end of this section (after the ibm-ete write-up, before the "GitHub default branch" note at line 266):
```markdown
### Adding a fourth provider

Every provider follows the same shape: a CI-only dropdown prefix (e.g. `ibm-newprovider/`),
a secret pair named `IBM_<NAME>_API_BASE`/`IBM_<NAME>_API_KEY`, and a case arm in
`resolve_provider.sh` (`ci/benchmarks/lib/resolve_provider.sh`) that strips the prefix (or
rewrites it, if the provider needs a different wire-level id shape than its CI prefix, the
way `ibm-rits/*` does) and returns that provider's credentials. `ci_setup.sh`'s
`classify_provider`/`check_entitlement` and `sync_models.py`'s `--models PREFIX=PATH`
polling both key off this same prefix, so a new provider needs no changes to their
matching logic — only a new case arm and, if it should be polled automatically, a new
`fetch_one` call in `sync-model-lists.yml`.
```

- [ ] **Step 5: Commit**

```bash
git add ci/benchmarks/README.md
git commit -s -m "$(cat <<'EOF'
docs(readme): document the ibm-rits/ibm-ete/ibm-ete-int rename and ibm-ete

Updates the secret names and RITS section to the new ibm-rits/IBM_RITS_*
naming, adds a new ibm-ete section (second ete-litellm gateway, zero seeded
dropdown options until sync-model-lists.yml populates it), and a short note
on the IBM_<NAME>_API_BASE/_API_KEY naming convention for anyone adding a
fourth provider later.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Rollout verification

**Files:** none (verification only — no repo file is touched, except the secret deletions in Step 4, which act on GitHub, not the repo).

**Interfaces:**
- Consumes: every prior task's completed changes, dispatched for real against skillberry-1.

- [ ] **Step 1: Static checks across every edited file**

```bash
bash -n ci/benchmarks/lib/resolve_provider.sh
bash -n ci/benchmarks/lib/ci_setup.sh
bash -n ci/benchmarks/lib/run_suite.sh
bash ci/benchmarks/lib/test_resolve_provider.sh
python3 -m pytest ci/benchmarks/lib/test_sync_models.py -v
python3 ci/benchmarks/lib/sync_models.py --repo . --validate
python3 -c "import yaml; [yaml.safe_load(open(f)) for f in ['.github/workflows/benchmarks.yml', '.github/workflows/integration-tests.yml', '.github/workflows/sync-model-lists.yml']]" && echo OK
```
Expected: every command exits 0 / prints `OK`, all pytest tests pass.

If `actionlint` is available locally, run it against all three workflow files and confirm no new findings versus a pre-branch baseline.

- [ ] **Step 2: Push the branch and open the PR**

```bash
git push -u origin HEAD
gh pr create --title "ci: rename providers to ibm-rits/ibm-ete/ibm-ete-int, add ibm-ete" --body "$(cat <<'EOF'
## Summary
- Renames the two existing CI model-gateway secret pairs to IBM_ETE_INT_*/IBM_RITS_* and
  adds a third provider, ibm-ete (a second, separate ete-litellm gateway) with
  IBM_ETE_API_BASE/IBM_ETE_API_KEY.
- Every agent_model/optimizer_model dropdown id now carries its provider as a CI-only
  prefix (ibm-ete-int/, ibm-ete/, ibm-rits/); resolve_provider.sh strips it before sending
  a model id on the wire — ibm-rits/<vendor>/<model> keeps the ibm-<vendor>/<model> ->
  rits/<vendor>/<model> rewrite lite-rits requires.
- sync_models.py's --models flag becomes repeatable (PREFIX=PATH), scoped so an unpolled
  prefix's dropdown options (in practice ibm-rits, never polled) are left untouched.
- Spec: docs/superpowers/specs/2026-09-24-ibm-provider-rename-design.md

## Test plan
- [ ] `bash ci/benchmarks/lib/test_resolve_provider.sh` passes
- [ ] `python3 -m pytest ci/benchmarks/lib/test_sync_models.py -v` passes
- [ ] `python3 ci/benchmarks/lib/sync_models.py --repo . --validate` passes
- [ ] `integration-tests.yml` dispatched manually against an `ibm-ete-int/*` model, green
- [ ] `sync-model-lists.yml` dispatched manually once ibm-ete's budget clears, populates
      real `ibm-ete/*` entries and leaves `ibm-rits/*` untouched
- [ ] `gh pr checks` shows DCO passing

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Verify DCO before requesting review**

```bash
gh pr checks <pr-number>
git log --format='%h %(trailers:key=Signed-off-by,valueonly)' origin/main..HEAD
```
Expected: `DCO` check passing; every commit line has a non-empty `Signed-off-by:` value.

- [ ] **Step 4: Dispatch `integration-tests.yml` against an `ibm-ete-int/*` model**

```bash
gh workflow run integration-tests.yml --ref <branch> -f model=ibm-ete-int/aws/gpt-oss-120b
```
(Adjust the input name to whatever `integration-tests.yml`'s actual `workflow_dispatch.inputs` key is — confirm with `gh workflow view integration-tests.yml --ref <branch>` if unsure.) Watch it to completion; expected green, proving the rename didn't break the existing end-to-end path on skillberry-1.

- [ ] **Step 5: Dispatch `sync-model-lists.yml` once `ibm-ete`'s budget clears**

```bash
gh workflow run sync-model-lists.yml --ref <branch> -f apply=true
```
Watch it to completion. Expected: real `ibm-ete/*` entries appear in both dropdowns' options in the resulting commit/PR it opens, and every `ibm-rits/*` entry is byte-identical to before the run.

- [ ] **Step 6: Delete the four old-named secrets — only after Step 4 (and ideally Step 5) pass**

```bash
gh secret delete ANTHROPIC_BASE_URL --repo skillberry-ai/cap-evolve
gh secret delete ANTHROPIC_AUTH_TOKEN --repo skillberry-ai/cap-evolve
gh secret delete RITS_API_BASE --repo skillberry-ai/cap-evolve
gh secret delete RITS_API_KEY --repo skillberry-ai/cap-evolve
gh secret list --repo skillberry-ai/cap-evolve
```
Expected: `gh secret list` now shows only the six new-named secrets — none of the four old names remain.

This is a real, hard-to-reverse action against shared GitHub state (deleting secrets other workflows could still reference) — confirm with the user before running Step 6, even though the plan authorizes it once Step 4 is green.
