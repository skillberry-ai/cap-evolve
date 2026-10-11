"""Summarize gateway spend by experiment/arm prefix: python3.12 -I spend.py [prefix-filter]"""
import collections, json, sys, os
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs", "gateway_calls.jsonl")
PRICE = json.load(open("/home/dev/projects2/cap-evolve-campaign/research/capevolve-paper/protocol/pricing.json"))["usd_per_mtok"]
flt = sys.argv[1] if len(sys.argv) > 1 else ""
agg = collections.defaultdict(lambda: collections.Counter())
for line in open(LOG):
    r = json.loads(line)
    tag = r.get("tag", "untagged")
    if flt not in tag:
        continue
    exp = ":".join(tag.split(":")[1:2]) or tag
    role = tag.split(":")[-1]
    u = r.get("usage") or {}
    a = agg[(exp, role, r.get("model"))]
    a["calls"] += 1
    a["err"] += r.get("status") != 200
    inp = u.get("prompt_tokens", u.get("input_tokens", 0)) or 0
    out = u.get("completion_tokens", u.get("output_tokens", 0)) or 0
    cw = u.get("cache_creation_input_tokens", 0) or 0
    cr = u.get("cache_read_input_tokens", 0) or 0
    a["in"] += inp; a["out"] += out; a["cw"] += cw; a["cr"] += cr
    p = PRICE.get(r.get("model"))
    if p:
        a["usd_x1e6"] += int(inp * p["input"] + out * p["output"] + cw * p["cache_write_5m"] + cr * p["cache_read"])
print(f"{'experiment':28} {'role':10} {'model':28} {'calls':>6} {'err':>4} {'in':>11} {'out':>9} {'cache_r':>11} {'usd':>8}")
tot = collections.Counter()
for (e, role, m), a in sorted(agg.items()):
    usd = a["usd_x1e6"] / 1e6 if a["usd_x1e6"] else (None if not PRICE.get(m) else 0.0)
    print(f"{e[:28]:28} {role[:10]:10} {str(m)[:28]:28} {a['calls']:6} {a['err']:4} {a['in']:11} {a['out']:9} {a['cr']:11} {('%.2f' % usd) if usd is not None else 'unknown':>8}")
    tot.update(a)
print("TOTAL calls", tot["calls"], "in", tot["in"], "out", tot["out"], "cache_read", tot["cr"], "priced_usd %.2f" % (tot["usd_x1e6"] / 1e6))
