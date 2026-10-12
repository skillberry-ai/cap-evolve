#!/usr/bin/env bash
# E26-nohist: copy of the skills tree with the one diagnose-skill line that points at the run history removed.
# usage: make_nohist_skills.sh <wt-nohist skills dir> <dest>   (export CAPEVOLVE_SKILLS_DIR=<dest> for E26 cells)
set -e
rm -rf "$2"; cp -r "$1" "$2"
python3 - "$2/phases/diagnose/SKILL.md" <<'P'
import sys,re
p=sys.argv[1]; s=open(p).read()
s2=re.sub(r"- cross-check the run history \(LEDGER / prior iterations\) and skip any cluster whose\n  fix was already tried and rejected — do not re-diagnose a refuted approach\.\n","",s)
assert s2!=s; open(p,"w").write(s2)
P
! grep -rniE 'ledger|runmap|prior_iterations|JOURNAL\.md|INSIGHTS' "$2/phases/diagnose" "$2/capabilities/system-prompt" "$2/capabilities/tools" && echo clean
