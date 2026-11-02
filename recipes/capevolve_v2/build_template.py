import re, shutil, hashlib, os
EXP="/dccstor/knewedge2/boazc/workarea/python/skillberry_ai/cap-evolve-spread-worktrees/exp895"
K=EXP+"/../sbv400-k02"; K=os.path.realpath(K)
OLD=EXP+"/arms/capevolve/template/.capevolve/project"
NEW=EXP+"/arms/capevolve_v2/template/.capevolve/project"
os.makedirs(NEW+"/adapters",exist_ok=True); os.makedirs(NEW+"/optimizer",exist_ok=True)
shutil.copytree(OLD+"/seed_capability_v2",NEW+"/seed_capability_v2",dirs_exist_ok=True)
for f in ["split_ids.json","all_task_ids.txt"]: shutil.copy(OLD+"/"+f,NEW+"/"+f)
shutil.copy(K+"/templates/adapters/spreadsheetbench/adapter.py",NEW+"/adapters/adapter.py")
shutil.copy(K+"/templates/adapters/model_config.py",NEW+"/adapters/model_config.py")
# INSTRUCTIONS
lines=open(K+"/templates/project/optimizer/INSTRUCTIONS.md").read().split("\n")
i=[n for n,l in enumerate(lines) if l.strip()=="{{BENCH_REPO}}"]; assert len(i)==1
add=open(EXP+"/arms/capevolve/INSTRUCTIONS.exp895_addendum.md").read().rstrip("\n").split("\n")
out=lines[:i[0]+1]+[""]+add+lines[i[0]+1:]   # same splice as the capevolve arm (verified: old = old template + [""] + block)
open(NEW+"/optimizer/INSTRUCTIONS.md","w").write("\n".join(out))
# YAML
y=open(EXP+"/arms/capevolve_v2/intake_scratch/.capevolve/project/capevolve.yaml").read()
def setkey(k,v):
    global y
    y,n=re.subn(r"(?m)^%s:[^\n]*?(\s+#[^\n]*)?$"%re.escape(k),lambda m:"%s: %s%s"%(k,v,m.group(1) or ""),y,count=1)
    assert n==1,k
V2=NEW
for k,v in [("capabilities","[system-prompt, skill-package]"),("capability_path","seed_capability_v2"),
 ("optimizer_skill","claude-code"),("optimizer_model","rits/zai-org/glm-5-3"),("optimizer_max_turns","80"),
 ("optimizer_usd_per_iter","0"),("optimizer_instructions_file",V2+"/optimizer/INSTRUCTIONS.md"),
 ("target_model","google/gemma-4-31B-it"),("dataset_source","adapter"),("split_ids_file","split_ids.json"),
 ("num_trials","3"),
 ("metrics_display","[hard_restriction, soft_restriction]"),("metric_primary","hard_restriction"),("metric_directions","[higher, higher]"),("store","copy"),("max_iterations","1000"),("stall","0"),("max_metric_calls","2160")]:
    setkey(k,v)
y+="""
# --- exp895 capevolve_v2 settings (issue skillberry-ai/cap-evolve#895); everything above keeps the main template default
# gate_k_se stays at the template default (0.2); gate_footprint is deliberately ABSENT (main default = masking on).
errored_trial_policy: fail               # candidate-attributed errors score 0; infra errors stay missing (retryable)
budget_reserve: true                     # hard counter: refuse an eval that would overshoot R
finalize: false                          # the test split is scored only in the common final window

# --- helper scripts: same block as the capevolve arm, paths re-pointed to v2
surface:
  executable_dirs: ["skills/*/scripts"]
helpers:
  enabled: true
  lint: true
  smoke: true
  suffixes: [".py"]
  max_file_bytes: 65536
  max_total_bytes: 262144
  smoke_timeout: 20
  ids_file: %s/all_task_ids.txt
  deny_roots: [%s/data, %s/third_party/spreadsheetbench/evaluation]
"""%(NEW,EXP,K)
open(NEW+"/capevolve.yaml","w").write(y)
