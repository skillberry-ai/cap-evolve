import json, os, sys

TRAJ = 'trajectories'
def load(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    return json.load(open(fn))

# For each task, extract "Updated N paths from <hash>" and the model patch info from verifier stdout.
# The key question: does the verifier apply the agent's patch via git apply? Look for 'model_patch' or 'git apply' lines.
FAILING = ["astropy__astropy-13453","django__django-10554","django__django-11555","django__django-12325",
"django__django-12708","django__django-14007","django__django-14376","django__django-15629","django__django-16032",
"django__django-16667","pydata__xarray-6461","pydata__xarray-6992","pylint-dev__pylint-4661","pylint-dev__pylint-4970",
"pytest-dev__pytest-10356","pytest-dev__pytest-5787","sympy__sympy-15599","sympy__sympy-17630","sympy__sympy-21612","sympy__sympy-24213"]

import re
for task in FAILING:
    d = load(task)
    vs = d['rollout']['metadata']['verifier_stdout']
    # find 'Updated N paths from X' — this is git apply output
    upd = re.findall(r"Updated (\d+) paths from ([0-9a-f]+)", vs)
    # git apply --check lines
    ap = re.findall(r"\+ git apply[^\n]*", vs)
    print(f"### {task}: updated={upd} apply_lines={ap[:2]}")
