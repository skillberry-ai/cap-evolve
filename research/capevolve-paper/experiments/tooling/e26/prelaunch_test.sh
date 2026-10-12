#!/usr/bin/env bash
# throwaway one-iteration E26 pre-launch test with the real claude: prelaunch_test.sh <seed id e.g. 97>
set -e
N=$1; R=/home/dev/projects2/campaign-scratch/runs
python3 /home/dev/projects2/campaign-scratch/scripts/E20/build_d.py E20-PT $N --root $R/E26test >/dev/null
W=$R/E26test/PT/s$N; cd $W
python3 - $N <<'P'
import json,shutil,sys
n=sys.argv[1]
s=open('env.sh').read()
s=s.replace('/home/dev/projects2/wt-tau/core','/home/dev/projects2/wt-nohist/core').replace('CAPEVOLVE_SKILLS_DIR=/home/dev/projects2/wt-tau/skills','CAPEVOLVE_SKILLS_DIR=/home/dev/projects2/campaign-scratch/runs/E26/_skills')
s=s.replace(f'tag:E20-PT-s{n}',f'tag:E26test-NOHIST-s{n}').replace('runs/E10B/_sbx_bin','runs/E26/_sbx_bin')+'export CAPEVOLVE_HISTORY=0\n'
open('env.sh','w').write(s)
sp=json.load(open('.capevolve/project/split_ids.json'))
json.dump({'train':sp['train'][:4],'val':sp['train'][:4],'test':sp['test'][:2]},open('.capevolve/project/split_ids.json','w'))
y=open('.capevolve/project/capevolve.yaml').read().replace('max_iterations: 10','max_iterations: 2').replace('max_metric_calls: 550','max_metric_calls: 60')
open('.capevolve/project/capevolve.yaml','w').write(y)
shutil.copy('/home/dev/projects2/campaign-scratch/runs/E26/INSTRUCTIONS.nohist.md','.capevolve/project/optimizer/INSTRUCTIONS.md')
P
cat > driver.sh <<D
#!/usr/bin/env bash
cd $W && source env.sh
\$PY -u -c "import sys; from cap_evolve.cli import main; sys.exit(main(sys.argv[1:]))" run --spec .capevolve/project/capevolve.yaml --project .capevolve/project --run-ts main --dashboard off > run.log 2>&1
echo "exit \$?" >> run.log
D
chmod +x driver.sh; (setsid nohup ./driver.sh >/dev/null 2>&1 &)
