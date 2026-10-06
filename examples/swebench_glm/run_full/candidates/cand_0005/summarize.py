#!/usr/bin/env python3
import json, sys

def summarize(path, maxcalls=400, show_results=0):
    d = json.load(open(path))
    steps = d['rollout']['output']['steps']
    print(f"### {path}  reward={d['score']['reward']}")
    print(f"### n_steps={len(steps)}")
    for s in steps:
        if s.get('source') != 'agent':
            continue
        sid = s['step_id']
        txt = s.get('message') or ''
        rc = s.get('reasoning_content') or ''
        for tc in s.get('tool_calls') or []:
            fn = tc.get('function_name')
            args = tc.get('arguments', {})
            a = json.dumps(args)
            a = a[:260]
            print(f"[{sid}] {fn}: {a}")
        if show_results:
            obs = s.get('observation') or {}
            for res in obs.get('results', []):
                print(f"      => {res.get('content','')[:show_results]}")
        if txt.strip():
            print(f"[{sid}] TEXT: {txt[:600]}")
        elif rc.strip() and sid % 1 == 0:
            pass

if __name__ == '__main__':
    summarize(sys.argv[1], show_results=int(sys.argv[2]) if len(sys.argv) > 2 else 0)
