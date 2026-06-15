# VHS tape for the tau2-airline COMPOSITE run demo. Renders from a FINISHED run dir:
#   RUN=/tmp/tau2_comp_smoke RID=run_smoke vhs docs/tau2_demo.tape   (or the full run)
# Produces docs/tau2_demo.gif.

Output docs/tau2_demo.gif

Set Shell bash
Set Width 1240
Set Height 760
Set FontSize 15
Set Padding 22
Set Theme "Catppuccin Frappe"

Hide
Type "export RUN=${RUN:-/tmp/tau2_comp_smoke} RID=${RID:-run_smoke}" Enter
Type "clear" Enter
Show

Type "# agent-capo x tau2-airline: optimize the POLICY + TOOLS together"
Enter
Sleep 800ms
Type "# (claude-opus-4-6 optimizer, gpt-oss-120b agent+user, git iteration store)"
Enter
Sleep 800ms
Type "cat $RUN/.agentcapo/project/acapo.yaml"
Enter
Sleep 3800ms
Type "clear"
Enter
Type "# the optimizer edited BOTH the policy and the tool docstrings each iteration:"
Enter
Sleep 900ms
Type "ls $RUN/seed_composite/policy $RUN/seed_composite/tools"
Enter
Sleep 2200ms
Type "# every iteration is committed to git — the whole process is inspectable:"
Enter
Sleep 900ms
Type "git -C $RUN/.agentcapo/$RID log --oneline"
Enter
Sleep 3000ms
Type "# optimizer memory (rejected approaches it will not retry):"
Enter
Sleep 700ms
Type "cat $RUN/.agentcapo/$RID/rejected.jsonl"
Enter
Sleep 2500ms
Type "cat $RUN/.agentcapo/$RID/report.md"
Enter
Sleep 3500ms
