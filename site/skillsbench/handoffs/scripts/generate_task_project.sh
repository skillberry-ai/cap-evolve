#!/bin/bash
# Generate a task-by-task cap-evolve project directory for a single SkillsBench
# task, cloned from the project_edit-pdf template. Idempotent; skips if exists.
#
# Usage: bash generate_task_project.sh <task-name>
set -eo pipefail

TASK="${1:?task name required, e.g. bike-rebalance}"
FORCE="${2:-}"   # pass "force" to overwrite existing config
ROOT="/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-worktrees/intake_skillbench_c3"
TEMPLATE="$ROOT/.capevolve/project_edit-pdf"
TASKS_DIR="/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-benchmarks/skillsbench/tasks"
DEST="$ROOT/.capevolve/project_${TASK}"

if [ -e "$DEST" ] && [ "$FORCE" != "force" ]; then
    echo "[gen] $DEST already exists — skip"
    exit 0
fi
rm -rf "$DEST"

if [ ! -d "$TASKS_DIR/$TASK" ]; then
    echo "[gen] ERROR: task not found: $TASKS_DIR/$TASK" >&2
    exit 2
fi

# Clone template
cp -r "$TEMPLATE" "$DEST"
rm -rf "$DEST/adapters/__pycache__"

# Rename yaml + split_ids
mv "$DEST/capevolve.edit-pdf.yaml" "$DEST/capevolve.${TASK}.yaml"
mv "$DEST/split_ids.edit-pdf.json" "$DEST/split_ids.${TASK}.json"

# Substitute task name inside yaml + split_ids
sed -i "s/edit-pdf/${TASK}/g" "$DEST/capevolve.${TASK}.yaml" "$DEST/split_ids.${TASK}.json"

# Replace seed_capability with the task's own shipped skills
rm -rf "$DEST/seed_capability"
if [ -d "$TASKS_DIR/$TASK/environment/skills" ]; then
    cp -r "$TASKS_DIR/$TASK/environment/skills" "$DEST/seed_capability"
else
    # Empty seed_capability if the task has no shipped skills
    mkdir -p "$DEST/seed_capability"
    echo "[gen] WARN: $TASK has no environment/skills/; seed_capability empty" >&2
fi

echo "[gen] $DEST"
