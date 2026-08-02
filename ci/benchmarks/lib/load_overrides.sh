#!/usr/bin/env bash
# load_overrides.sh — apply a tier's committed `overrides.env`, if it ships one.
#
#   load_overrides <path-to-overrides.env>
#
# WHY A COMMITTED FILE. `workflow_dispatch` allows at most 10 inputs and that list is full,
# so a setting without an input needs another channel. A repo variable works (see
# BENCH_SPLIT_SEED) but is mutable and invisible afterwards; a run whose number will be
# compared against published results should carry its exact configuration IN GIT, next to the
# split it ran on, so the result can be reproduced and audited later. Hence: commit the file.
#
# FORMAT. `KEY=value` lines; blank lines and `#` comments ignored; no quoting rules, the value
# is the rest of the line verbatim. The file is PARSED, never sourced — a committed config
# cannot execute anything in the runner.
#
# PRECEDENCE. The ENVIRONMENT WINS. A key already set (a workflow input, or an operator
# running by hand) is left alone and reported; the file only fills in what was not specified.
# That way adding an override can never silently override a deliberate dispatch choice.
load_overrides() {
  local file="$1"
  [ -f "$file" ] || return 0
  local line key value current
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ''|\#*) continue ;;
      *=*) ;;
      *) continue ;;
    esac
    key="${line%%=*}"
    value="${line#*=}"
    case "$key" in
      *[!A-Za-z0-9_]*|'') continue ;;   # ignore anything that is not a plain shell name
    esac
    eval "current=\${$key-}"
    if [ -n "$current" ]; then
      echo ">>> overrides.env: $key already set in the environment — keeping it" >&2
    else
      export "$key=$value"
      echo ">>> overrides.env: $key=$value" >&2
    fi
  done < "$file"
}
