import json, os
TRAJ = "trajectories"
def load(task):
    for f in sorted(os.listdir(TRAJ)):
        if f.startswith(task + "__"):
            return json.load(open(os.path.join(TRAJ, f)))
    return None
d = load("django__django-16667")
vs = ((d.get("rollout") or {}).get("metadata") or {}).get("verifier_stdout", "")
# The verifier failure: '9223372036854775808-12-1' != '0-0-0'
# So the GOLD patch returns "0-0-0" for out-of-range years. The agent's fix
# caught OverflowError but then fell to... let me see what the code does after catch.
# The agent's patch: except (ValueError, OverflowError): return "%s-%s-%s" % (y or 0, m or 0, d or 0)
# y=9223372036854775808 → returns '9223372036854775808-12-1'... 
# gold must convert int(y) into something safe. Actually gold (Django 16667) is:
# try: date_value = datetime.date(int(y), int(m), int(d))
# except ValueError: ... return "%s-%s-%s" % (y or 0, m or 0, d or 0)
# The real gold patch for 16667 uses regex validation. Let me check the issue.
i = vs.find("test_value_from_datadict")
print(vs[max(0,i-200):i+600])
