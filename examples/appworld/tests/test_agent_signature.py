"""PR 874 review finding 9: the constructor arguments match AppWorld's agent at the pinned commit.

AppWorld is not installed for the offline tests, so the two upstream ``__init__`` signatures at
42b5bcf are copied here (experiments/code/simplified/agent.py and react_code_agent.py). A drift is
reported by name instead of as an opaque ``infra_error``.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aw_testlib import EX  # noqa: E402

import aw_agent  # noqa: E402


class Agent:  # appworld_agents.code.simplified.agent.Agent @ 42b5bcf
    def __init__(self, model_config: dict[str, Any], appworld_config: dict[str, Any] | None = None,
                 logger_config: dict[str, Any] | None = None, usage_tracker_config: dict[str, Any] | None = None,
                 max_steps: int = 40, log_lm_calls: bool = False, skip_if_finished: bool = False):
        pass


class SimplifiedReActCodeAgent(Agent):  # ...react_code_agent @ 42b5bcf
    def __init__(self, prompt_file_path: str, ignore_multiple_calls: bool = True,
                 max_prompt_length: int | None = None, max_output_length: int | None = None, **kwargs: Any):
        super().__init__(**kwargs)


class CapLike(SimplifiedReActCodeAgent):  # same shape as aw_agent.build_agent_class()
    def __init__(self, candidate, memory_block: str = "", **kwargs: Any):
        super().__init__(**kwargs)


class DriftedAgent(Agent):  # upstream renamed max_output_length
    def __init__(self, prompt_file_path: str, ignore_multiple_calls: bool = True,
                 max_prompt_length: int | None = None, max_observation_length: int | None = None, **kwargs: Any):
        super().__init__(**kwargs)


class CapOnDrifted(DriftedAgent):
    def __init__(self, candidate, memory_block: str = "", **kwargs: Any):
        super().__init__(**kwargs)


SPEC = {"candidate_dir": str(EX / "seed_capability"), "random_seed": 100, "log_lm_calls": False}


class AgentSignatureTests(unittest.TestCase):
    def test_every_kwarg_is_accepted_at_the_pin(self):
        kw = aw_agent.agent_kwargs(SPEC, dict(aw_agent.MODEL_CONFIG))
        self.assertEqual(len(kw), 10)
        self.assertEqual(aw_agent.unaccepted_kwargs(CapLike, kw), [])
        CapLike(candidate={}, **kw)  # and it really constructs

    def test_drift_is_named(self):
        kw = aw_agent.agent_kwargs(SPEC, dict(aw_agent.MODEL_CONFIG))
        self.assertEqual(aw_agent.unaccepted_kwargs(CapOnDrifted, kw), ["max_output_length"])

    def test_check_injection_runs_the_signature_check(self):
        src = (EX / "scripts" / "check_injection.py").read_text()
        self.assertIn("unaccepted_kwargs", src)
        self.assertIn("A4.0", src)


if __name__ == "__main__":
    unittest.main()
