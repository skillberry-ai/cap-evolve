#!/usr/bin/env bash
# run_suite.sh — optimize ALL of a tier's tasks TOGETHER in ONE optimization run.
#
#   run_suite.sh <bench> [out_dir]
#
# NOT task-by-task. The optimizer sees EVERY failing task each iteration and proposes one
# edit to improve across all of them. Split is a NO-HOLDOUT FIT: train == val == test ==
# all tier tasks — baseline and optimized are both measured on the same tasks, so the
# headline is a TRAIN-FIT number (how well the optimizer fits the tasks), NOT a
# generalization claim. One optimization = ITERATIONS opus passes total (not × #tasks).
#
# Reads ci/benchmarks/<bench>/<TIER>/tasks.json. Writes <out_dir>/{metrics.jsonl, steps.jsonl, report.md,
# optimized/}. Runs on the self-hosted runner (VPC gateway); dogfoods the adapter templates.
set -uo pipefail
LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$LIB_DIR/../../.." && pwd)"
BENCH="${1:?bench (tau2|swebench|skillsbench|spreadsheetbench)}"
PY="${CAPEVOLVE_PY:-$REPO/.venv-e2e/bin/python}"; [ -x "$PY" ] || PY="python3"
TIER="${TIER:-smoke}"

# Committed per-tier overrides (optional): ci/benchmarks/<bench>/<tier>/overrides.env.
# Env wins; the file only fills in what the dispatch did not set. See load_overrides.sh for
# why this is a committed file rather than a repo variable.
# shellcheck source=ci/benchmarks/lib/load_overrides.sh
. "$LIB_DIR/load_overrides.sh"
load_overrides "$REPO/ci/benchmarks/$BENCH/$TIER/overrides.env"

ITER="${ITERATIONS:-3}"
AGENT_MODEL="${AGENT_MODEL:-aws/gpt-oss-120b}"
NUM_TRIALS="${NUM_TRIALS:-10}"
OPTIMIZER_MODEL="${OPTIMIZER_MODEL:-claude-opus-4-8}"
GATE_K_SE="${GATE_K_SE:-1.0}"

# ---- algorithm selection ----------------------------------------------------
# ALGORITHM is the workflow's `algorithm` input. It names the algorithm AND, for
# hill-climb, its focus schedule in one token — because workflow_dispatch allows at most 10
# inputs and that list is full, so a separate `algorithm` input is not available (see the
# note in benchmarks.yml).
#
# agent-optimize is not just another value: it has NO deterministic loop and refuses a
# deterministic invocation outright (skills/algorithms/agent-optimize/scripts/run.py), so
# it must come with `orchestration_mode: agent` and a free-text `stop_condition` — the
# stopping rule that replaces max_iterations there. Both are emitted below and consumed by
# the capevolve.yaml heredoc further down.
#
# Back-compat: ALGORITHM_FOCUS was the old input name and may still be exported by hand or
# by a committed overrides.env. It is honoured when ALGORITHM is unset, so an existing
# invocation keeps producing the same run; ALGORITHM wins when both are set, so a stale
# alias can never override a deliberate dispatch choice.
ALGORITHM="${ALGORITHM:-}"
if [ -z "$ALGORITHM" ]; then
  case "${ALGORITHM_FOCUS:-all}" in
    all|cyclic|hardest-first) ALGORITHM="hill-climb-${ALGORITHM_FOCUS:-all}" ;;
    *) echo "::error:: unknown ALGORITHM_FOCUS='${ALGORITHM_FOCUS}'" >&2; exit 2 ;;
  esac
fi
ALGO_FOCUS=""
ORCH_MODE="deterministic"
STOP_CONDITION=""
case "$ALGORITHM" in
  hill-climb-all|hill-climb-cyclic|hill-climb-hardest-first)
    ALGO_SKILL="hill-climb"
    ALGO_FOCUS="${ALGORITHM#hill-climb-}"
    ;;
  agent-optimize)
    ALGO_SKILL="agent-optimize"
    ORCH_MODE="agent"
    # Derived from the SAME dispatch inputs that bound a deterministic run, so the two
    # algorithms are comparable at a given dispatch. The whole loop is ONE agent process
    # (unlike the deterministic path's one optimizer call per iteration), so a
    # per-iteration cap becomes a whole-loop cap by multiplying it by the iteration count.
    # OPTIMIZER_USD_PER_ITER=0 means unlimited everywhere else in this workflow; keep that
    # meaning by omitting the dollar clause entirely rather than writing a $0 ceiling.
    # Self-contained: fall back to the raw dispatch env so this block can be lifted and
    # executed on its own (core/tests/test_benchmarks_agent_optimize.py does exactly that).
    _rounds="${ITER:-${ITERATIONS:-3}}"
    _trials="${NUM_TRIALS:-10}"
    _k_se="${GATE_K_SE:-1.0}"
    _stop_usd=""
    if awk "BEGIN{exit !(${OPTIMIZER_USD_PER_ITER:-0} > 0)}" 2>/dev/null; then
      _stop_usd="$(awk "BEGIN{printf \"%.2f\", ${OPTIMIZER_USD_PER_ITER:-0} * $_rounds}")"
      _stop_usd=" Stop if your own (optimization) spend reaches \$${_stop_usd}."
    fi
    STOP_CONDITION="Spend at most ${_rounds} rounds, where a round is one candidate taken to a\
 full-val gate decision (accepted or rejected) and booked with commit.py. Stop early when\
 spend.py's recommendation is 'stop', or after ${_rounds} rounds, or when two consecutive\
 rounds are rejected with no new failure cluster left to attack.${_stop_usd} Gate every\
 candidate on FULL val at gate_k_se=${_k_se} over ${_trials} trial(s); never gate on\
 a screen subset. Always finish by sealing test exactly once with measure.py and writing\
 the report — a run with no finalize has no result."
    ;;
  *)
    echo "::error:: unknown ALGORITHM='$ALGORITHM' (expected hill-climb-all |" \
         "hill-climb-cyclic | hill-climb-hardest-first | agent-optimize)" >&2
    exit 2
    ;;
esac
# ---- end algorithm selection ------------------------------------------------

# The algorithm block above chose the skill, the orchestration mode and (agent mode only)
# the free-text stop_condition. Render the mode-specific lines here rather than emitting
# empty keys: `algorithm_focus` is a hill-climb concept, and a `stop_condition` on a
# deterministic run would be inert text that misleads whoever reads the spec back.
ALGO_YAML="algorithm_skill:    $ALGO_SKILL"
[ -n "$ALGO_FOCUS" ] && ALGO_YAML="$ALGO_YAML
algorithm_focus:    $ALGO_FOCUS"
if [ "$ORCH_MODE" = "agent" ]; then
  # json.dumps, not bare interpolation: the derived stop_condition is a paragraph of prose
  # containing ':', '$' and quotes, any of which makes an unquoted YAML scalar invalid or
  # (worse) silently truncated at the colon.
  ALGO_YAML="$ALGO_YAML
orchestration_mode: agent
$(STOP_CONDITION="$STOP_CONDITION" "$PY" -c 'import json,os;print("stop_condition:     " + json.dumps(os.environ["STOP_CONDITION"]))')"
fi

BASE="$REPO/ci/benchmarks/$BENCH/$TIER"
OUT="${2:-$REPO/ci/benchmarks/.work/suite_${TIER}_${BENCH}}"
mkdir -p "$OUT/optimized"
: > "$OUT/metrics.jsonl"

[ -f "$BASE/tasks.json" ] || { echo "::warning::no tasks.json for $BENCH/$TIER — nothing to run"; echo "## ${TIER^} suite — $BENCH" > "$OUT/report.md"; echo "(no tasks defined for this tier)" >> "$OUT/report.md"; exit 0; }

: "${ANTHROPIC_BASE_URL:?set ANTHROPIC_BASE_URL (IBM gateway)}"
: "${ANTHROPIC_AUTH_TOKEN:?set ANTHROPIC_AUTH_TOKEN}"

export PYTHONPATH="$REPO/core:$REPO"
export CAPEVOLVE_SKILLS_DIR="$REPO/skills"

# All task ids for this tier (this run optimizes them together). Agent is uniform across a
# tier; take the first task's agent and warn if the file mixes agents (this script can't mix).
readarray -t IDS < <("$PY" - "$BASE/tasks.json" <<'PY'
import json,sys
for t in json.load(open(sys.argv[1])):
    print(t["id"])
PY
)
[ "${#IDS[@]}" -gt 0 ] || { echo "::warning::tasks.json empty for $BENCH/$TIER"; echo "## ${TIER^} suite — $BENCH" > "$OUT/report.md"; echo "(no tasks)" >> "$OUT/report.md"; exit 0; }
# AGENT_MODEL (env — the workflow's `agent_model` input, or its default) is
# AUTHORITATIVE: it's what this run actually uses. tasks.json's per-task "agent"
# field is only consulted to WARN on a mismatch (e.g. a curated task pinned to a
# different model than requested) — it never silently overrides the caller's choice.
"$PY" - "$BASE/tasks.json" "$AGENT_MODEL" <<'PY'
import json,sys
ts=json.load(open(sys.argv[1]))
agents={t.get("agent") for t in ts if t.get("agent")}
env_model=sys.argv[2]
if agents and agents != {env_model}:
    sys.stderr.write(f"::warning::tasks.json pins agent(s) {sorted(agents)} but this run uses {env_model!r} (override)\n")
PY
IDS_CSV="$(IFS=,; echo "${IDS[*]}")"
echo ">>> $BENCH/$TIER — optimizing ${#IDS[@]} tasks together (agent=$AGENT_MODEL, ${ITER} iters)" >&2

# ---- scaffold ONE project over ALL tasks -----------------------------------
WORK="$REPO/ci/benchmarks/.work/suite_${TIER}_${BENCH}_proj"
rm -rf "$WORK"; mkdir -p "$WORK/.capevolve/project/adapters" "$WORK/.capevolve/project/inputs"
PROJ="$WORK/.capevolve/project"
TPL="$REPO/templates/adapters"
cp "$TPL/model_config.py" "$PROJ/adapters/" 2>/dev/null || true

case "$BENCH" in
  tau2)
    cp "$TPL/tau2_bench/adapter.py" "$PROJ/adapters/"
    cp -R "$REPO/examples/tau2_airline/seed_capability" "$PROJ/seed_capability"
    # tau2's FULL editable surface, for every tier (smoke/full/integration all reach here):
    # policy/policy.md (the agent's system prompt) AND tools/tools.py + reference/data_model.py
    # (the tool code it calls). Both capability skills are declared so both sets of rules
    # validate the candidate and both guidance docs reach the optimizer.
    #
    # This is the maximum that applies, not a subset. The other two capability skills are
    # deliberately absent: `mcp-tool` is for a toolset served by an EXTERNAL MCP server and
    # forbids editing tool code (its own SKILL.md says to use `tools` when the agent owns its
    # tools, which here it does), and `skill-package` optimizes a SKILL.md package, which this
    # seed is not. Adding either would narrow or invalidate the surface, not widen it.
    #
    # NB `capabilities` selects which capability `validate()` runs and which guidance is
    # surfaced — it does NOT gate writes. Declaring `tools` therefore does not by itself make
    # an optimizer USE it: on smoke run 32649063850 both candidates edited only policy.md
    # while tools.py sat writable and unopened. What closes that gap is naming the actual
    # files to the optimizer — the deterministic path's INSTRUCTIONS.md does, and agent mode's
    # briefing does it in host.py's `_surface_section`.
    CAPS="[system-prompt, tools]"
    cat > "$WORK/.env" <<ENV
MODEL=litellm_proxy/$AGENT_MODEL
LITELLM_PROXY_API_BASE=$ANTHROPIC_BASE_URL
LITELLM_PROXY_API_KEY=$ANTHROPIC_AUTH_TOKEN
MAX_TOKENS=8000
TEMPERATURE=0.0
ENV
    export TAU2_MAX_CONCURRENCY=10
    ;;
  swebench)
    # Harbor is the ONLY swebench path. The litellm single-shot adapter was removed: it needs
    # oracle code context to be viable, oracle context exists only for SWE-bench_Lite, and the
    # curated tiers are Verified-only (46 of full's 250 had it). Harbor's agent explores the
    # repo itself, so no oracle is required.
    # Harbor adapter reads os.environ (not .env/dotenv), so we export directly.
    cp "$TPL/harbor/adapter.py" "$PROJ/adapters/"
    cp -R "$TPL/harbor/seed_capability" "$PROJ/seed_capability"
    CAPS="[skill-package]"
    export HARBOR_DATASET=swe-bench/swe-bench-verified
    export HARBOR_AGENT=claude-code
    export HARBOR_MODEL="$AGENT_MODEL"
    # Concurrency. 16 was WRONG and pilot run 31274531220 proved it: 34 of 50 tasks
    # infra-errored, the box sat at load 30 of 32 cores, and the failures were agent-bootstrap
    # (npm exit 126/128, NetworkConnectionError) plus CancelledError from rollouts starved of
    # time. The 16 came from idle-state headroom, which was the wrong measurement — a harbor
    # task is a container running a real test suite, not a spare core.
    # 6 is the retry value: comfortably under 32 cores with room for image builds alongside.
    # Explicit HARBOR_PARALLEL in the environment still wins, so this is a default, not a
    # policy. NB: it cannot be a workflow_dispatch input — that list is at its cap of 10.
    case "${TIER:-smoke}" in
      smoke) _hp_default=4 ;;
      *)     _hp_default=6 ;;
    esac
    export HARBOR_PARALLEL="${HARBOR_PARALLEL:-$_hp_default}"
    echo "harbor parallelism: $HARBOR_PARALLEL (tier=${TIER:-smoke})"
    # 1800s was too tight once containers contend: 8 of the pilot's 34 failures were
    # CancelledError, i.e. the rollout was still waiting when the clock ran out. 3600s.
    export HARBOR_TIMEOUT="${HARBOR_TIMEOUT:-3600}"
    # Harbor applies a SEPARATE 360s budget to agent SETUP (harbor/trial/trial.py:
    # _AGENT_SETUP_TIMEOUT_SEC = 360), independent of HARBOR_TIMEOUT above. Pilot run
    # 31331458168 lost 5 of its 6 infra-errored tasks to it:
    #
    #   AgentSetupTimeoutError: Agent setup timed out after 360.0 seconds
    #
    # Setup is not cheap on these images. Harbor first installs Node itself
    # (`apt-get install curl bash nodejs npm procps`) and then fetches claude-code — and on
    # Debian-based swebench images it takes the non-Alpine branch, `curl -fsSL https://…`,
    # rather than npm. So the pre-warmed npm cache does NOT shorten this path: it only helps
    # the Alpine branch. Both steps are network-bound and 6 containers do them concurrently.
    #
    # x3 -> 1080s. Raising the ceiling is the honest fix here; baking Node and claude-code
    # into the task images would remove the work entirely and is the better long-term answer.
    export HARBOR_EXTRA_FLAGS="${HARBOR_EXTRA_FLAGS:---agent-setup-timeout-multiplier 3}"
    echo "harbor extra flags: $HARBOR_EXTRA_FLAGS"
    export HARBOR_TASK_IDS="$IDS_CSV"
    # Keep harbor OFF the root filesystem. Pilot run 31297290155 failed 50/50 with
    #   #10 importing to docker
    #   #10 ERROR: failed to ingest "blobs/sha256/..."
    # because / was 100% full (250G, 169M free). Harbor writes a job directory per run under
    # /tmp — agent sessions, trajectories, per-task artifacts — and 43 of them had accumulated
    # for 622M, which on a full disk is the difference between building and not. Docker's
    # data-root is already on /vol; these were not.
    # $CAPEVOLVE_CI_CACHE is on /vol on this runner; fall back to /tmp if it is unset so a
    # laptop run behaves as before.
    _hb_jobs_base="${CAPEVOLVE_CI_CACHE:-${HOME}/.cache/capevolve-ci}"
    if mkdir -p "$_hb_jobs_base/harbor-jobs" 2>/dev/null; then
      export HARBOR_JOBS_DIR="${HARBOR_JOBS_DIR:-$_hb_jobs_base/harbor-jobs}"
      # Harbor and docker compose also scratch-write via TMPDIR (the compose override JSONs
      # land in /tmp/tmp*). Point those at the same volume.
      export TMPDIR="${TMPDIR:-$_hb_jobs_base/tmp}"; mkdir -p "$TMPDIR" 2>/dev/null || true
      echo "harbor job dir: $HARBOR_JOBS_DIR   TMPDIR: $TMPDIR"
    else
      echo "::warning:: could not create $_hb_jobs_base/harbor-jobs — harbor will use /tmp"
    fi
    # Point the in-container claude-code agent at the VPC gateway.
    # Without HARBOR_AGENT_BASE_URL the adapter's _build_agent_env() falls through to bare
    # ANTHROPIC_API_KEY mode, which sends the agent to api.anthropic.com — unreachable from
    # this runner and wrong for a LiteLLM key. Setting it makes the adapter export
    # ANTHROPIC_BASE_URL plus the SONNET/HAIKU/OPUS model aliases into the container, so
    # every agent call goes through the same gateway the optimizer uses.
    export HARBOR_AGENT_BASE_URL="${HARBOR_AGENT_BASE_URL:-$ANTHROPIC_BASE_URL}"
    export HARBOR_AGENT_API_KEY="${HARBOR_AGENT_API_KEY:-$ANTHROPIC_AUTH_TOKEN}"
    export ANTHROPIC_API_KEY="$ANTHROPIC_AUTH_TOKEN"
    : > "$WORK/.env"
    ;;
  skillsbench)
    cp "$TPL/skillsbench/adapter.py" "$PROJ/adapters/"
    SB_SRC="${SKILLSBENCH_SRC:-$REPO/e2e/skillsbench-src}"
    [ -d "$SB_SRC/tasks" ] || { echo "::error:: skillsbench clone not found at $SB_SRC (set SKILLSBENCH_SRC)"; exit 1; }
    SEED="$PROJ/seed_capability"; mkdir -p "$SEED"
    cp -R "$SB_SRC/tasks/offer-letter-generator/environment/skills/docx" "$SEED/docx"
    cp -R "$SB_SRC/tasks/exceltable-in-ppt/environment/skills/pptx"      "$SEED/pptx"
    cp -R "$SB_SRC/tasks/exceltable-in-ppt/environment/skills/xlsx"      "$SEED/xlsx"
    cp -R "$SB_SRC/tasks/pdf-excel-diff/environment/skills/pdf"          "$SEED/pdf"
    CAPS="[skill-package]"
    cat > "$WORK/.env" <<ENV
ANTHROPIC_BASE_URL=$ANTHROPIC_BASE_URL
ANTHROPIC_AUTH_TOKEN=$ANTHROPIC_AUTH_TOKEN
SKILLSBENCH_MODEL=$AGENT_MODEL
SKILLSBENCH_TASKS_DIR=$SB_SRC/tasks
SKILLSBENCH_CONCURRENCY=10
ENV
    export SKILLSBENCH_MODEL="$AGENT_MODEL"
    export SKILLSBENCH_TASKS_DIR="$SB_SRC/tasks"
    export SKILLSBENCH_CONCURRENCY=10
    ;;
  spreadsheetbench)
    cp "$TPL/spreadsheetbench/adapter.py" "$PROJ/adapters/"
    cp -R "$TPL/spreadsheetbench/seed_capability" "$PROJ/seed_capability"
    # NO-SKILL CONTROL. Comparisons against published skill-optimization results (e.g.
    # SkillOpt, arXiv 2605.23904) report a "no skill" baseline: the same model with no skill
    # document at all. Our committed seed_capability/prompt.md is already a short expert
    # prompt (it states the answer_position restriction, literal-values-over-formulas, the
    # exact output_path and error-recovery), so a run against it measures "refine an existing
    # prompt", NOT "author a skill from nothing" — a materially easier task with far less
    # headroom. Blanking the seed reproduces their control; the adapter treats an EMPTY
    # prompt.md as "send no system message" and the harness's is_empty() path tells the
    # optimizer to author the capability from scratch.
    if [ "${SB_EMPTY_SEED:-0}" = "1" ] && [ "${SB_WARM_SEED:-0}" = "1" ]; then
      echo "::error:: SB_EMPTY_SEED and SB_WARM_SEED are mutually exclusive — 'no skill at all'" \
           "and 'start from an already-optimized skill' cannot both be the baseline." >&2
      exit 1
    fi
    if [ "${SB_EMPTY_SEED:-0}" = "1" ]; then
      : > "$PROJ/seed_capability/prompt.md"
      echo ">>> spreadsheetbench: EMPTY seed (no-skill control) — prompt.md blanked" >&2
    fi
    # WARM START. Learning was not cumulative: every run began from the pristine seed, so each
    # explored a different subset of rules and forgot the rest. Across the two pilots' champions,
    # 30799393875 learned "spill/volatile functions do not survive LibreOffice recalc — write the
    # literal" (_xlfn x4, TEXTJOIN x3) and fixed tasks 47741 and 51958; 30890657732 carried NONE
    # of it and both regressed. That is 2 tasks lost to forgetting, not to variance.
    #
    # seed_capability_warm/ is a verbatim optimizer artifact, never hand-edited — see its
    # PROVENANCE.md. A warm-started run's base->opt delta is NOT comparable to a pristine run's:
    # the baseline is already optimized, so the absolute score is higher and the measured gain
    # smaller. Hence opt-in only, and disclosed in runmeta.json as "warm_seed".
    if [ "${SB_WARM_SEED:-0}" = "1" ]; then
      WARM="$TPL/spreadsheetbench/seed_capability_warm"
      if [ ! -f "$WARM/prompt.md" ] || [ ! -f "$WARM/task_template.md" ]; then
        echo "::error:: SB_WARM_SEED=1 but $WARM is missing prompt.md/task_template.md" >&2
        exit 1
      fi
      cp "$WARM/prompt.md" "$WARM/task_template.md" "$PROJ/seed_capability/"
      echo ">>> spreadsheetbench: WARM seed — baseline is the champion of run 30890657732" \
           "(cand_0002, val 0.580). base->opt is NOT comparable to a pristine-seed run." >&2
    fi
    # Gate strictness vs scoring mode. Hard scoring makes per-task reward Bernoulli, which widens
    # the gate's SE, so the k_se that is sane under soft scoring rejects almost everything under
    # hard. This bit us twice and silently: pilots 30799393875 and 30890657732 both ran the
    # default k_se=1.0 against SB_SCORING=hard, and 30890657732's cand_0003 scored 0.600 — ABOVE
    # its accepted champion's 0.580 — and was rejected on a delta of 0.020. GATE_K_SE is always
    # set by the workflow so it cannot be corrected from overrides.env; warn loudly instead.
    if [ "${SB_SCORING:-soft}" = "hard" ]; then
      if awk "BEGIN{exit !(${GATE_K_SE:-1.0} >= 0.5)}"; then
        echo "::warning:: SB_SCORING=hard with gate_k_se=${GATE_K_SE:-1.0}. Bernoulli per-task" \
             "reward widens the gate's SE, so real gains are likely to be REJECTED (run" \
             "30890657732 rejected a 0.600 candidate in favour of 0.580). Dispatch with" \
             "gate_k_se=0.2 for hard scoring." >&2
      fi
    fi
    # Prompt-only optimizer instructions. The default template shipped in
    # templates/project/optimizer/INSTRUCTIONS.md is written for a capability that
    # includes TOOL CODE: it tells the optimizer to prefer in-body guards, names
    # `tools.py` and tau2's `get_*_details`, and its self-check demands "edits across BOTH
    # policy.md AND tools.py". This capability is `[system-prompt]` — one prompt.md, no
    # tools — so that guidance sends the optimizer hunting for code to change (in run
    # 30691123806 it went and edited adapter.py). The harness picks up
    # $PROJ/optimizer/INSTRUCTIONS.md automatically, and OPT_INSTRUCTIONS pins it by
    # absolute path so it cannot silently fall back to the generic template (#252). No
    # core change is needed either way.
    mkdir -p "$PROJ/optimizer"
    cp "$REPO/templates/project/optimizer/INSTRUCTIONS.prompt-only.md" \
       "$PROJ/optimizer/INSTRUCTIONS.md"
    # NAME THE ARTIFACTS. The shared template speaks of "the prompt" in the singular and the
    # rendered instructions mention no filename at all, so an optimizer handed TWO editable
    # files reasonably edits only the obvious one: in pilot 30736646559 it reported "all in
    # prompt.md — the system prompt" and never touched task_template.md, leaving the unlocked
    # surface inert. Both files are in its workdir; it just had no reason to know the second
    # one was fair game. This appendix is benchmark-specific, which is why it lives here
    # rather than in the shared template.
    cat >> "$PROJ/optimizer/INSTRUCTIONS.md" <<'OPTNOTE'

## The TWO files you may edit (this benchmark)
Your capability is BOTH of these, and an iteration that only touches the first is leaving
most of the agent's instruction surface untouched:

1. **`prompt.md`** — the agent's SYSTEM message: who it is, how it should work, what to
   check. ~40% of the words the agent reads.

2. **`task_template.md`** — the agent's FIRST USER message: how the job is framed, what each
   field means, and the interaction contract. ~60% of the words the agent reads. It is
   ordinary prose and you may reword, restructure, add to, or DELETE from it — including
   guidance that is actively unhelpful. (Read it critically: a line telling the agent it is
   finished as soon as an output file exists will discourage it from verifying values, which
   is the most common way tasks fail here.)

   The `{placeholders}` in it are filled in per task and are LOAD-BEARING. Keep every one of
   `{instruction}` `{spreadsheet_path}` `{spreadsheet_content}` `{instruction_type}`
   `{answer_position}` `{output_path}`; `{max_turns}` is optional; invent no others; write a
   literal brace as `{{` or `}}`. Break that and EVERY task scores 0 — the agent is never
   told where to write its answer — so the candidate is rejected outright.

Decide per cluster which file is the right place to fix it, and say which you chose in
PROCESS.md.
OPTNOTE
    OPT_INSTRUCTIONS="$PROJ/optimizer/INSTRUCTIONS.md"
    SB_CACHE="${CAPEVOLVE_CI_CACHE:-$HOME/.cache/capevolve-ci}/spreadsheetbench-data"
    SB_DEFAULT="$SB_CACHE/sample_data_200"
    # pilot draws its tasks from full's train split, so it needs the 912-task dataset too.
    case "$TIER" in full|pilot) SB_DEFAULT="$SB_CACHE/all_data_912_v0.1";; esac
    # SPREADSHEETBENCH_DATA_DIR is expected to be set (and exported to GITHUB_ENV) by
    # ci_setup.sh, which calls fetch_data.sh and echoes the resolved path. When running
    # locally without ci_setup.sh, the SB_DEFAULT fallback is used instead.
    SB_DATA="${SPREADSHEETBENCH_DATA_DIR:-$SB_DEFAULT}"
    [ -f "$SB_DATA/dataset.json" ] || { echo "::error:: spreadsheetbench dataset not found at $SB_DATA (run ci/benchmarks/spreadsheetbench/fetch_data.sh or set SPREADSHEETBENCH_DATA_DIR)"; exit 1; }
    # full runs 912 tasks in one go — bump container concurrency over smoke's default
    # (still bounded; each container is ~8GB RAM / 2 CPU, see adapter.py's NOTE ON SCORING)
    # unless the caller already pinned SPREADSHEETBENCH_CONCURRENCY explicitly.
    SB_CONCURRENCY_DEFAULT=4
    case "$TIER" in full|pilot) SB_CONCURRENCY_DEFAULT=8;; esac
    # Rounds of code-exec interaction the agent gets per task. SkillOpt runs SpreadsheetBench
    # as "multi-round codegen with up to 30 turns" (arXiv 2605.23904), and the adapter's own
    # default is 5 — a real handicap on a multi-round benchmark, so full (the comparison tier)
    # matches 30. Smoke stays at 5 to keep it a cheap, fast signal whose numbers remain
    # comparable to its own history. Override with SPREADSHEETBENCH_MAX_TURNS.
    SB_MAX_TURNS_DEFAULT=5
    # pilot exists to MEASURE the full tier, so it must match full's turn budget.
    case "$TIER" in full|pilot) SB_MAX_TURNS_DEFAULT=30;; esac
    CAPS="[system-prompt]"
    cat > "$WORK/.env" <<ENV
MODEL=litellm_proxy/$AGENT_MODEL
LITELLM_PROXY_API_BASE=$ANTHROPIC_BASE_URL
LITELLM_PROXY_API_KEY=$ANTHROPIC_AUTH_TOKEN
MAX_TOKENS=8000
TEMPERATURE=0.0
SPREADSHEETBENCH_HARNESS_DIR=$REPO/third_party/spreadsheetbench
SPREADSHEETBENCH_DATA_DIR=$SB_DATA
SPREADSHEETBENCH_TASK_IDS=$IDS_CSV
SPREADSHEETBENCH_CONCURRENCY=${SPREADSHEETBENCH_CONCURRENCY:-$SB_CONCURRENCY_DEFAULT}
SPREADSHEETBENCH_MAX_TURNS=${SPREADSHEETBENCH_MAX_TURNS:-$SB_MAX_TURNS_DEFAULT}
SPREADSHEETBENCH_SCORING=${SB_SCORING:-soft}
ENV
    export SPREADSHEETBENCH_HARNESS_DIR="$REPO/third_party/spreadsheetbench"
    export SPREADSHEETBENCH_DATA_DIR="$SB_DATA"
    export SPREADSHEETBENCH_CONCURRENCY="${SPREADSHEETBENCH_CONCURRENCY:-$SB_CONCURRENCY_DEFAULT}"
    export SPREADSHEETBENCH_MAX_TURNS="${SPREADSHEETBENCH_MAX_TURNS:-$SB_MAX_TURNS_DEFAULT}"
    # soft (default, matches this benchmark's own headline) | hard (all 3 test cases must
    # match — the "native hard score" that published comparisons report). Both are recorded
    # on every rollout either way; this picks the one the GATE optimizes against.
    export SPREADSHEETBENCH_SCORING="${SB_SCORING:-soft}"
    ;;
  *) echo "unknown bench: $BENCH" >&2; exit 2;;
esac

# SPLIT. A tier that ships its own split_ids.json gets a genuine HELD-OUT split (disjoint
# train/val/test, so `finalize` produces a real generalization number that can be compared
# against papers reporting held-out test scores). Otherwise: the NO-HOLDOUT FIT split
# (train == val == test == ALL tier tasks), which every tier used before and which the
# report labels as a FIT metric, not a generalization claim.
#
# Opt-in by committing <bench>/<tier>/split_ids.json — no other tier ships one, so this is a
# no-op for them. See ci/benchmarks/spreadsheetbench/utils/make_split.py for a generator.
if [ -f "$BASE/split_ids.json" ]; then
  echo ">>> held-out split: using $BASE/split_ids.json (NOT the no-holdout FIT split)"
  "$PY" - "$BASE/split_ids.json" "$IDS_CSV" > "$PROJ/inputs/split_ids.json" <<'PY'
import json,sys
split = json.load(open(sys.argv[1]))
want = {s for s in sys.argv[2].split(",") if s}
have = set()
for k in ("train", "val", "test"):
    ids = [str(i) for i in split.get(k, [])]
    if not ids and k != "train":
        raise SystemExit(f"::error:: committed split has an empty '{k}' split")
    have |= set(ids)
    split[k] = ids
# The split must describe exactly the tier's task list — a stale split silently evaluating a
# different task set is the kind of error that invalidates a whole comparison run.
if have != want:
    missing, extra = sorted(want - have)[:5], sorted(have - want)[:5]
    raise SystemExit(f"::error:: split_ids.json does not match {len(want)} tier tasks "
                     f"(missing e.g. {missing}, unexpected e.g. {extra})")
for a, b in (("train", "val"), ("train", "test"), ("val", "test")):
    dup = set(split[a]) & set(split[b])
    if dup:
        raise SystemExit(f"::error:: committed split is not held out — {a}/{b} overlap "
                         f"on {len(dup)} task(s), e.g. {sorted(dup)[:5]}")
print(json.dumps({k: split[k] for k in ("train", "val", "test")}))
PY
else
  "$PY" - "$IDS_CSV" > "$PROJ/inputs/split_ids.json" <<'PY'
import json,sys
ids=[s for s in sys.argv[1].split(",") if s]
print(json.dumps({"train":ids,"val":ids,"test":ids}))
PY
fi

cat > "$PROJ/capevolve.yaml" <<YAML
capabilities:       $CAPS
capability_path:    seed_capability
optimizer_skill:    claude-code
optimizer_model:    $OPTIMIZER_MODEL
target_model:       $AGENT_MODEL
optimizer_max_turns:    ${OPTIMIZER_MAX_TURNS:-80}
optimizer_usd_per_iter: ${OPTIMIZER_USD_PER_ITER:-0}
# Set (to an ABSOLUTE path) only by an arm that ships its own optimizer instructions;
# empty is falsy in core, which then uses its default optimizer/INSTRUCTIONS.md lookup —
# so this line is a no-op for every other benchmark. Absolute on purpose: a RELATIVE value
# resolves against different cwds in check vs run and can silently fall back to the generic
# template (issue #252), which would erase an arm's instructions with no error.
optimizer_instructions_file: "${OPT_INSTRUCTIONS:-}"
$ALGO_YAML
dataset_source:     adapter
split_ids_file:     "inputs/split_ids.json"
# With an explicit split_ids_file the partition is fixed, so split_seed only varies the
# per-trial ROLLOUT seeding (harness base_seed reads splits.seed). That is what makes
# ">=3 seeds" possible on one committed split: dispatch the same run with 42/43/44.
split_seed:         ${SPLIT_SEED:-0}
num_trials:         $NUM_TRIALS
gate_mode:          paired
gate_k_se:          $GATE_K_SE
max_iterations:     $ITER
stall:              $ITER
store:              git
YAML

cd "$WORK"
"$PY" -m cap_evolve.cli check .capevolve/project >&2

# ONE optimization: baseline (all tasks) + ITER optimize iterations + finalize (all tasks).
# A non-zero exit is deliberately NOT fatal here: metrics/report/UI below still turn the
# partial run dir into reviewable artifacts. The job is failed afterwards by the workflow's
# "Assert the suite run completed" gate (ci/benchmarks/lib/assert_run.py), so a crashed run
# cannot be mistaken for a clean one.
"$PY" -m cap_evolve.cli run --spec .capevolve/project/capevolve.yaml \
      --project .capevolve/project --run-ts suite --max-iterations "$ITER" </dev/null || \
  echo "::error::suite run exited non-zero for $BENCH — see the algorithm step's returncode/stderr above"
RUN_DIR="$WORK/.capevolve/run_suite"

# ---- agent mode: drive the handed-off loop ----------------------------------
# In agent mode `cap-evolve run` does check + baseline, prints a handoff and RETURNS — no
# algorithm subprocess and no auto-finalize, because the loop belongs to a conversational
# agent. CI has none, so the algorithm's own headless host drives it: it renders the driver
# briefing from the spec + handoff and delegates the CLI invocation to the existing
# optimizers/run-optimizer runner (registry row, model + budget flags, cost capture,
# CLI-present hard fail). It also guarantees a seal, so a host that runs out of budget
# mid-loop still leaves an honest final.json instead of a run dir that reads as crashed.
#
# Budget: the whole loop is ONE agent process, so the per-iteration caps become whole-loop
# caps (x the round count). 0 stays unlimited, as everywhere else in this workflow.
if [ "$ORCH_MODE" = "agent" ]; then
  HOST_TURNS="$(( ${OPTIMIZER_MAX_TURNS:-80} * ITER ))"
  HOST_USD_ARGS=()
  if awk "BEGIN{exit !(${OPTIMIZER_USD_PER_ITER:-0} > 0)}"; then
    HOST_USD_ARGS=(--usd-budget "$(awk "BEGIN{printf \"%.2f\", ${OPTIMIZER_USD_PER_ITER:-0} * $ITER}")")
  fi
  echo ">>> agent mode — handing the loop to the headless host (turns=$HOST_TURNS)" >&2
  "$PY" "$REPO/skills/algorithms/agent-optimize/scripts/host.py" \
        --run-dir "$RUN_DIR" --project "$PROJ" \
        --agent claude-code --model "$OPTIMIZER_MODEL" \
        --budget "$HOST_TURNS" "${HOST_USD_ARGS[@]}" </dev/null || \
    echo "::error::agent-optimize host exited non-zero for $BENCH — see its JSON above"
fi

# ---- metrics + report (per-task base→opt from the ONE run) -----------------
"$PY" "$LIB_DIR/metrics.py" suite "$RUN_DIR" --bench "$BENCH" --tier "$TIER" \
      --agent "$AGENT_MODEL" --optimizer-model "$OPTIMIZER_MODEL" --iters "$ITER" \
      --jsonl "$OUT/metrics.jsonl" \
      --steps-jsonl "$OUT/steps.jsonl" > "$OUT/report.md" 2>/dev/null || {
  echo "## ${TIER^} suite — $BENCH" > "$OUT/report.md"; echo "(no metrics — run failed; check logs)" >> "$OUT/report.md"; }

# reviewable optimized capability (diff vs seed). skillsbench skills are Anthropic-licensed
# → stat only, never content.
best="$(sed -n 's/.*"best_id": "\([^"]*\)".*/\1/p' "$RUN_DIR/state.json" 2>/dev/null | head -1)"
seed_dir="$RUN_DIR/candidates/seed"; opt_dir="$RUN_DIR/candidates/${best:-seed}"
dst="$OUT/optimized"; mkdir -p "$dst"
if [ "$BENCH" = "skillsbench" ]; then
  git --no-pager diff --no-index --stat "$seed_dir" "$opt_dir" > "$dst/capability.diffstat.txt" 2>/dev/null || true
  echo "(skillsbench skills are Anthropic-licensed — content not published; stat only)" >> "$dst/capability.diffstat.txt"
else
  git --no-pager diff --no-index "$seed_dir" "$opt_dir" > "$dst/capability.diff" 2>/dev/null || true
  [ -d "$opt_dir" ] && cp -R "$opt_dir"/. "$dst/optimized_capability/" 2>/dev/null || true
fi

cat "$OUT/report.md"
echo "RUN_DIR=$RUN_DIR"
