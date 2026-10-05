import json, os, sys

TRAJ = 'trajectories'
def load(task):
    fn = os.path.join(TRAJ, f"{task}__cand_0002__t0.json")
    return json.load(open(fn))

PASSING = ["django__django-12039","django__django-12276","django__django-13121","django__django-13401",
"django__django-13410","django__django-13569","django__django-14580","django__django-15103","django__django-15380",
"django__django-15851","django__django-15863","django__django-15930","matplotlib__matplotlib-22871",
"matplotlib__matplotlib-24637","scikit-learn__scikit-learn-25232","sphinx-doc__sphinx-7910","sphinx-doc__sphinx-8035",
"sphinx-doc__sphinx-8475","sphinx-doc__sphinx-8595","sphinx-doc__sphinx-9258","sympy__sympy-12096","sympy__sympy-13480",
"sympy__sympy-17139","sympy__sympy-18211"]

import re
n_with_diff = 0
for task in PASSING:
    d = load(task)
    vs = d['rollout']['metadata']['verifier_stdout']
    upd = re.findall(r"Updated (\d+) paths from ([0-9a-f]+)", vs)
    print(f"{task:45s} updated={upd}")
