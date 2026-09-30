#!/usr/bin/env python3
"""Generate a test fixture for frontend tests from a minimal run."""

import json
import tempfile
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))

from cap_evolve import dashboard, Budget, RunDir


def create_test_run():
    """Build a minimal run with diagnosis for testing."""
    baseline = {
        'val': {'reward': 0.5, 'per_task': [
            {'task_id': 't1', 'reward': 0.0, 'feedback': 'wrong'},
            {'task_id': 't2', 'reward': 1.0, 'feedback': 'correct'},
            {'task_id': 't3', 'reward': 0.0, 'feedback': 'wrong'},
            {'task_id': 't4', 'reward': 1.0, 'feedback': 'correct'},
        ]},
        'best_id': 'seed'
    }
    
    events = [
        {'kind': 'splits', 'train': 4, 'val': 4, 'test': 2, 'seed': 0, 't': 100.0},
        {'kind': 'eval_start', 'split': 'val', 'tag': 'seed', 't': 100.0},
        {'kind': 'evaluate', 'split': 'val', 'tag': 'seed', 'reward': 0.5,
         'stderr': 0.0, 'cost_usd': 0.0, 'tokens': 0, 'seconds': 5.0, 't': 105.0,
         'per_task': [
             {'task_id': 't1', 'reward': 0.0, 'feedback': 'wrong'},
             {'task_id': 't2', 'reward': 1.0, 'feedback': 'correct'},
             {'task_id': 't3', 'reward': 0.0, 'feedback': 'wrong'},
             {'task_id': 't4', 'reward': 1.0, 'feedback': 'correct'},
         ]},
        {'kind': 'baseline', 'val': 0.5, 'stderr': 0.0, 't': 105.0},
        {'kind': 'eval_start', 'split': 'val', 'tag': 'cand_0001', 't': 205.0},
        {'kind': 'evaluate', 'split': 'val', 'tag': 'cand_0001', 'reward': 0.75,
         'stderr': 0.0, 'cost_usd': 0.01, 'tokens': 500, 'seconds': 10.0, 't': 215.0,
         'per_task': [
             {'task_id': 't1', 'reward': 1.0, 'feedback': 'fixed'},
             {'task_id': 't2', 'reward': 0.0, 'feedback': 'broke'},
             {'task_id': 't3', 'reward': 0.0, 'feedback': 'still wrong'},
             {'task_id': 't4', 'reward': 1.0, 'feedback': 'still correct'},
         ]},
        {'kind': 'step', 'candidate': 'cand_0001', 'accept': True, 'reason': 'up',
         'val': 0.75, 'parent': 'seed', 'parent_val': 0.5,
         'optimizer_seconds': 100.0, 'runner_seconds': 10.0, 'cost_usd': 0.01, 'tokens': 500,
         'fixed': ['t1'], 'broke': ['t2'], 't': 220.0},
        {'kind': 'eval_start', 'split': 'val', 'tag': 'cand_0002', 't': 320.0},
        {'kind': 'evaluate', 'split': 'val', 'tag': 'cand_0002', 'reward': 1.0,
         'stderr': 0.0, 'cost_usd': 0.01, 'tokens': 500, 'seconds': 10.0, 't': 330.0,
         'per_task': [
             {'task_id': 't1', 'reward': 1.0, 'feedback': 'still fixed'},
             {'task_id': 't2', 'reward': 1.0, 'feedback': 'fixed back'},
             {'task_id': 't3', 'reward': 1.0, 'feedback': 'fixed'},
             {'task_id': 't4', 'reward': 1.0, 'feedback': 'still correct'},
         ]},
        {'kind': 'step', 'candidate': 'cand_0002', 'accept': True, 'reason': 'up',
         'val': 1.0, 'parent': 'cand_0001', 'parent_val': 0.75,
         'optimizer_seconds': 100.0, 'runner_seconds': 10.0, 'cost_usd': 0.01, 'tokens': 500,
         'fixed': ['t2', 't3'], 'broke': [], 't': 335.0},
    ]
    
    # Add diagnosis to cand_0001 (JSON format)
    diagnosis_0001 = {
        'candidate': 'cand_0001',
        'headline': 'Fix task t1',
        'clusters': [
            {'id': 'A', 'name': 'Wrong calculation', 'tasks': ['t1'], 'detail': 'Math error'}
        ],
        'edits': [
            {'id': 'E1', 'title': 'Fix math', 'files': ['prompt.md'], 'clusters': ['A']}
        ],
        'skipped': []
    }
    
    # PROCESS.md for cand_0002 (fallback format - no DIAGNOSIS.json)
    process_md_0002 = """
## Ranked issue list

| rank | cluster | tasks | shared root cause | tag | planned change class |
|------|---------|-------|-------------------|-----|---------------------|
| 1 | **B** | t2, t3 | Incorrect logic | CONTRACT | Fix logic |

## Changes made this iteration

| cluster | edit class | file / tool | what & why | protects passing? |
|---------|-----------|-------------|------------|-------------------|
| **B** | CONTRACT | prompt.md | Fix the logic error | yes |
"""
    
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        rd = RunDir.create(tmp, ts="t", budget=Budget())
        rd.events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
        (rd.root / "baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
        
        # Add diagnosis file for cand_0001
        cand_dir_0001 = rd.root / 'candidates' / 'cand_0001'
        cand_dir_0001.mkdir(parents=True, exist_ok=True)
        (cand_dir_0001 / 'DIAGNOSIS.json').write_text(json.dumps(diagnosis_0001, indent=2))
        
        # Add PROCESS.md for cand_0002 (no DIAGNOSIS.json - tests fallback)
        cand_dir_0002 = rd.root / 'candidates' / 'cand_0002'
        cand_dir_0002.mkdir(parents=True, exist_ok=True)
        (cand_dir_0002 / 'PROCESS.md').write_text(process_md_0002)
        
        result = dashboard.reduce_run(rd)
        return result


if __name__ == '__main__':
    payload = create_test_run()
    
    # Write to frontend fixture
    fixture_path = REPO / 'dashboard/frontend/src/test/fixtures/run_payload.json'
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    with open(fixture_path, 'w') as f:
        json.dump(payload, f, indent=2)
    
    print(f'Wrote fixture to {fixture_path}')
    print(f'Fixture has {len(payload["graph"]["nodes"])} nodes')
    print(f'Activities: {len(payload["summary"]["activities"])}')
    
    # Verify outcomes structure
    for node in payload["graph"]["nodes"]:
        if "outcomes" in node:
            print(f'{node["id"]} outcomes: {list(node["outcomes"].keys())}')
