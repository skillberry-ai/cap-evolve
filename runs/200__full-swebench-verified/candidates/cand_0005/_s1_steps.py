import json, os, sys

fn = sys.argv[1]
d = json.load(open(fn))
out = (d.get('rollout') or {}).get('output') or {}
steps = out.get('steps') or []
for s in steps:
    src = s.get('source')
    msg = s.get('message') or ''
    tcs = s.get('tool_calls') or []
    obs = s.get('observation') or {}
    print(f"--- step {s.get('step_id')} [{src}] ---")
    if src == 'agent':
        # message may contain the thought + tool call
        print('MSG:', msg[:600].replace('\n', ' | '))
        for tc in tcs:
            args = tc.get('arguments') or {}
            cmd = args.get('command', args.get('cmd', ''))
            if cmd:
                print('CMD:', cmd[:500].replace('\n', ' ;; '))
        # observation content
        try:
            res = obs.get('results') or []
            for r in res:
                c = r.get('content', '')
                try:
                    j = json.loads(c)
                    print(f"OBS rc={j.get('returncode')} out:", str(j.get('output'))[:400].replace('\n', ' | '))
                except Exception:
                    print('OBS raw:', str(c)[:300].replace('\n', ' | '))
        except Exception as e:
            pass
    elif src == 'user':
        print('USER:', msg[:300].replace('\n', ' | '))
    else:
        print('SYS:', msg[:200].replace('\n', ' | '))
