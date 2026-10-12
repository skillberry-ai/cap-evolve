set -e
PY=/home/dev/projects2/campaign-scratch/bench/venv/bin/python
rm -rf /tmp/idc/A /tmp/idc/B; mkdir -p /tmp/idc/A /tmp/idc/B
cat > /tmp/idc/stage2.py <<'P'
import sys, json
from pathlib import Path
core, root, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, core)
from cap_evolve import RunDir, harness
rd = RunDir.create(root / ".capevolve", ts="hist")
rd.candidate_dir("seed").mkdir(parents=True, exist_ok=True)
rd.log_event("step", candidate="cand_1", parent="seed", accept=False, val=0.5)
rd.log_event("step", candidate="cand_2", parent="cand_1", accept=True, val=0.6)
work = root / "work"; work.mkdir()
text = harness._augment_instructions("BASE", work, rd)
solid = [{"task_id": str(i)} for i in range(5)]
out.write_text(json.dumps({"text": text.replace(str(root), "ROOT"), "passing": harness._passing_block(solid),
    "files": {str(p.relative_to(work)): p.read_text().replace(str(root), "ROOT") for p in sorted(work.rglob("*")) if p.is_file()}}, indent=1, sort_keys=True))
P
env -u CAPEVOLVE_HISTORY $PY /tmp/idc/stage2.py /home/dev/projects2/wt-tau/core /tmp/idc/A /tmp/idc/A.json
env -u CAPEVOLVE_HISTORY $PY /tmp/idc/stage2.py /home/dev/projects2/wt-nohist/core /tmp/idc/B /tmp/idc/B.json
python3 - <<'P'
import json,re
a=json.load(open('/tmp/idc/A.json')); b=json.load(open('/tmp/idc/B.json'))
norm=lambda s: re.sub(r'\d{4}-\d\d-\d\dT[\d:.]+Z?|\d{8}_\d{6}','TS',s)
def n(d): return json.dumps(d,sort_keys=True)
print('files',len(a['files']),'identical text' , norm(a['text'])==norm(b['text']), 'passing', a['passing']==b['passing'], 'files', norm(n(a['files']))==norm(n(b['files'])))
P
