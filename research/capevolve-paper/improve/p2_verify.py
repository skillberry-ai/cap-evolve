import json, sys
from pathlib import Path
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
import p2_budget_sim as p
REG = {"A": dict(F=62, C=58, minc=2, K=4, r=(8, 24), S=1, tc=2, mc=1), "D": dict(F=38, C=36, minc=3, K=4, r=(8, 24), S=1, tc=2, mc=2),
       "E": dict(F=16, C=14, minc=2, K=4, r=(8, 16), S=1, tc=3, mc=3)}
ALT = {"A runner alt (minc1,K6,r[8,24],tc1,mc1)": dict(F=62, C=58, minc=1, K=6, r=(8, 24), S=1, tc=1, mc=1),
       "A main defaults-ish (minc4,K6,r[12,36],S1,tc2.5->3,mc4)": dict(F=62, C=58, minc=4, K=6, r=(12, 36), S=1, tc=3, mc=4)}
out = {}
for name, cfg in list(REG.items()) + list(ALT.items()):
    res = {}
    for al in (0.12,):
        fw = [p.run(cfg, "null", h, 24000, al, 21)[0] for h in (0.0, 0.1, 0.2)]
        pw = [p.run(cfg, "alt", h, 24000, al, 23)[1] for h in (0.0, 0.1, 0.2)]
        cost = p.run(cfg, "alt", 0.1, 12000, al, 25)[2]
        res = dict(alpha=al, tcrit=p.t_crit(cfg["C"] - 1, al), fwer=fw, power=pw, cost_round=cost, worst=p.worst(cfg))
    out[name] = dict(cfg=cfg, **res); print(name, json.dumps(out[name]), flush=True)
json.dump(out, open(H / "p2_verify.json", "w"), indent=1)
