import json, math, sys
from pathlib import Path
H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
import p2_budget_sim as p
AL = 0.12
M = {"A": dict(F=62, C=58, minc=2, K=4, r=(8, 24), S=1, tc=2, mc=1), "D": dict(F=38, C=36, minc=3, K=4, r=(8, 24), S=1, tc=2, mc=2),
     "E": dict(F=16, C=14, minc=2, K=4, r=(8, 16), S=1, tc=3, mc=3)}
B2 = {"A": 1200, "D": 1100, "E": 600}
def rule(name, B, R, K=4):
    c = dict(M[name]); c["K"] = K; r1, r2 = c["r"]
    rung = K * r1 + (K // 2) * (r2 - r1); n = int(((B - c["minc"] * c["F"]) / R - rung) // c["C"])
    c["tc"], c["mc"] = math.ceil(n / 2), n // 2; return c
variants = {}
for n in M:
    variants[f"{n} matched (2 rounds)"] = (M[n], {"A": 600, "D": 550, "E": 300}[n])
    variants[f"{n} 2x same shape"] = (M[n], B2[n])
    variants[f"{n} 2x, 2 rounds, rule n"] = (rule(n, B2[n], 2), B2[n])
    variants[f"{n} 2x, 3 rounds, rule n"] = (rule(n, B2[n], 3), B2[n])
    variants[f"{n} 2x, K=8, 2 rounds, rule n"] = (rule(n, B2[n], 2, 8), B2[n])
out = {}
for k, (cfg, B) in variants.items():
    W = p.worst(cfg); base = cfg["minc"] * cfg["F"]; R = (B - base) // W
    fw = [p.run(cfg, "null", h, 12000, AL, 31)[0] for h in (0.0, 0.1, 0.2)]
    pw = {e: [p.run(cfg, f"alt:{e}", h, 12000, AL, 33)[1] for h in (0.0, 0.1, 0.2)] for e in (0.10, 0.15, 0.20, 0.25)}
    cost = p.run(cfg, "alt:0.2", 0.1, 6000, AL, 35)[2]
    out[k] = dict(cfg=cfg, B=B, worst=W, rounds_fit=R, fwer=fw, power=pw, cost_round=cost)
    print(k, json.dumps(out[k]), flush=True)
json.dump(out, open(H / "p2_verify2.json", "w"), indent=1)
