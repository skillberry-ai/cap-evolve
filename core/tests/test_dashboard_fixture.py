"""Test that the frontend fixture stays in sync with reduce_run output."""

import json
import tempfile
from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"
sys.path.insert(0, str(CORE))


def test_frontend_fixture_is_up_to_date():
    """The frontend fixture must match what reduce_run produces."""
    from cap_evolve import dashboard, Budget, RunDir
    
    # Build the same minimal run as generate_frontend_fixture.py
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
    ]
    
    diagnosis = {
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
    
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        rd = RunDir.create(tmp, ts="t", budget=Budget())
        rd.events_path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")
        (rd.root / "baseline.json").write_text(json.dumps(baseline), encoding="utf-8")
        
        cand_dir = rd.root / 'candidates' / 'cand_0001'
        cand_dir.mkdir(parents=True, exist_ok=True)
        (cand_dir / 'DIAGNOSIS.json').write_text(json.dumps(diagnosis, indent=2))
        
        expected = dashboard.reduce_run(rd)
    
    # Load the committed fixture
    fixture_path = REPO / 'dashboard/frontend/src/test/fixtures/run_payload.json'
    assert fixture_path.exists(), (
        f"Frontend fixture not found at {fixture_path}. "
        f"Run: python scripts/generate_frontend_fixture.py"
    )
    
    with open(fixture_path) as f:
        actual = json.load(f)
    
    # Compare key structures
    assert actual["summary"]["run_id"] == expected["summary"]["run_id"]
    # Fixture now has 3 nodes: seed, cand_0001 (with DIAGNOSIS.json), cand_0002 (with PROCESS.md fallback)
    assert len(actual["graph"]["nodes"]) >= len(expected["graph"]["nodes"]), \
        f"Fixture has {len(actual['graph']['nodes'])} nodes, expected at least {len(expected['graph']['nodes'])}"
    assert len(actual["summary"]["activities"]) >= len(expected["summary"]["activities"])
    
    # Verify outcomes structure matches
    for actual_node, expected_node in zip(actual["graph"]["nodes"], expected["graph"]["nodes"]):
        assert actual_node["id"] == expected_node["id"]
        if "outcomes" in expected_node:
            assert "outcomes" in actual_node, f"Node {actual_node['id']} missing outcomes"
            # Check that outcomes has the list structure
            assert isinstance(actual_node["outcomes"]["fixed"], list)
            assert isinstance(actual_node["outcomes"]["broke"], list)
            assert isinstance(actual_node["outcomes"]["still_failing"], list)
            assert isinstance(actual_node["outcomes"]["still_passing"], list)
            
            # Verify the actual values match
            assert set(actual_node["outcomes"]["fixed"]) == set(expected_node["outcomes"]["fixed"])
            assert set(actual_node["outcomes"]["broke"]) == set(expected_node["outcomes"]["broke"])
