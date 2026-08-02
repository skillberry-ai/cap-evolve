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
ALGORITHM_FOCUS="${ALGORITHM_FOCUS:-all}"
BASE="$REPO/ci/benchmarks/$BENCH/$TIER"
OUT="${2:-$REPO/ci/benchmarks/.work/suite_${TIER}_${BENCH}}"
mkdir -p "$OUT/optimized"
: > "$OUT/metrics.jsonl"

[ -f "$BASE/tasks.json" ] || { echo "::warning::no tasks.json for $BENCH/$TIER — nothing to run"; echo "## ${TIER^} suite — $BENCH" > "$OUT/report.md"; echo "(no tasks defined for this tier)" >> "$OUT/report.md"; exit 0; }

: "${ANTHROPIC_BASE_URL:?set ANTHROPIC_BASE_URL (IBM gateway)}"
: "${ANTHROPIC_AUTH_TOKEN:?set ANTHROPIC_AUTH_TOKEN}"

export PYTHONPATH="$REPO/core"
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
    cp "$TPL/swe_bench/adapter.py" "$PROJ/adapters/"
    cp -R "$TPL/swe_bench/seed_capability" "$PROJ/seed_capability"
    CAPS="[system-prompt]"
    cat > "$WORK/.env" <<ENV
MODEL=litellm_proxy/$AGENT_MODEL
LITELLM_PROXY_API_BASE=$ANTHROPIC_BASE_URL
LITELLM_PROXY_API_KEY=$ANTHROPIC_AUTH_TOKEN
MAX_TOKENS=8000
TEMPERATURE=0.0
SWEBENCH_INSTANCE_IDS=$IDS_CSV
SWEBENCH_MAX_WORKERS=10
SWEBENCH_NAMESPACE=${SWEBENCH_NAMESPACE:-swebench}
SWEBENCH_ORACLE=${SWEBENCH_ORACLE:-1}
ENV
    export SWEBENCH_MAX_WORKERS=10
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
    if [ "${SB_EMPTY_SEED:-0}" = "1" ]; then
      : > "$PROJ/seed_capability/prompt.md"
      echo ">>> spreadsheetbench: EMPTY seed (no-skill control) — prompt.md blanked" >&2
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
algorithm_skill:    hill-climb
algorithm_focus:    $ALGORITHM_FOCUS
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
