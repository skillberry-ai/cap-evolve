"""Logging-only change: an INFRASTRUCTURE_ERROR simulation records the exception detail in Rollout.metadata['infra_detail']; classification and scoring are unchanged."""
import importlib.util, sys
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parents[1] / "core")); sys.path.insert(0, str(HERE / "adapters"))
spec = importlib.util.spec_from_file_location("ad_infra", HERE / "adapters/adapter.py"); ad = importlib.util.module_from_spec(spec); spec.loader.exec_module(ad)
from tau2.data_model.simulation import SimulationRun, TerminationReason
import datetime

def _sim(term, info=None):
    now = datetime.datetime.now().isoformat()
    return SimulationRun(id="x", task_id="7", timestamp=now, start_time=now, end_time=now, duration=0.0, termination_reason=term, messages=[], trial=0, seed=1, info=info)

def test_infra_error_is_logged_and_classification_unchanged():
    info = {"error": "boom: modify_pending_order_items failed", "error_type": "ValueError",
            "error_traceback": 'Traceback (most recent call last):\n  File "x.py", line 1, in get_response\n    modify_pending_order_items()\nValueError: boom\n', "failed_after_attempts": 4}
    r = ad.Adapter._sim_to_rollout(_sim(TerminationReason.INFRASTRUCTURE_ERROR, info))
    assert r.error and "infrastructure reason" in r.error                       # classification unchanged
    assert r.metadata["error_kind"] == "infra" and r.metadata["tau2_reward"] == 0.0
    d = r.metadata["infra_detail"]
    assert d["error_type"] == "ValueError" and "boom" in d["error"] and d["failed_after_attempts"] == 4 and "get_response" in d["traceback_functions"]
    s = ad.Adapter().score(ad.Task(id="7", input="7"), r)                        # scoring unchanged: infra noise -> 0.0 with the infra feedback
    assert s.reward == 0.0 and "infrastructure reason" in s.feedback

def test_normal_sim_has_no_infra_detail_and_same_keys():
    r = ad.Adapter._sim_to_rollout(_sim(TerminationReason.USER_STOP))
    assert "infra_detail" not in r.metadata and r.error is None

def test_timeout_still_infra_without_info():
    r = ad.Adapter._sim_to_rollout(_sim(TerminationReason.TIMEOUT))
    assert r.error and r.metadata["error_kind"] == "infra" and "infra_detail" not in r.metadata
