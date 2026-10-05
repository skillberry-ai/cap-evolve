import json, os, sys

def load(task):
    fn = f'trajectories/{task}__cand_0002__t0.json'
    return json.load(open(fn))

def steps_of(d):
    return (d['rollout'].get('trace') or {}).get('steps') or []

def cmd_of(s):
    for tc in (s.get('tool_calls') or []):
        c = (tc.get('arguments') or {}).get('command', '')
        if c:
            return c
    return ''

def obs_of(s):
    try:
        c = s['observation']['results'][0]['content']
        j = json.loads(c)
        return j.get('output', ''), j.get('returncode')
    except Exception:
        return '', None

if __name__ == '__main__':
    task = sys.argv[1]
    d = load(task)
    steps = steps_of(d)
    print(f"### {task}: {len(steps)} steps")
    for i, s in enumerate(steps):
        if s.get('source') != 'agent':
            continue
        cmd = cmd_of(s)
        obs, rc = obs_of(s)
        obslen = len(obs or '')
        print(f"--- [{i}] rc={rc} obslen={obslen}")
        print("CMD:", cmd[:600].replace('\n', '\\n'))
    # last user message (final agent output)
    out = (d['rollout'].get('output') or {})
    final = (out.get('agent') or {}).get('final_message') or ''
    print("=== FINAL MESSAGE (first 2000) ===")
    print(final[:2000])
