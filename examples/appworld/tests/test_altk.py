"""altk/: converting cap-evolve rollouts to ALTK-Evolve trajectories (README: ALTK-Evolve arm)."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

# The modules under test live in ../adapters (and ../scripts, ../altk). `cap_evolve` normally comes
# from the installed package; core/ is a fallback so that
#     python3 examples/appworld/tests/test_altk.py -v
# works from a clean shell, as in examples/parsec/tests. Appended, not prepended: a second copy of
# cap_evolve ahead of the installed one would be worse than an awkward invocation.
EX = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EX / "altk"))
sys.path.append(str(Path(__file__).resolve().parents[3] / "core"))

from to_messages import rollout_to_messages  # noqa: E402


class TestToMessages(unittest.TestCase):
    def test_instruction_first_and_no_outcome_label(self):
        msgs = rollout_to_messages({"input": {"instruction": "Do X", "supervisor": "A B"},
                                    "rollout": {"trace": [{"thought": "t", "code": "print(1)", "output": "1"}]},
                                    "score": {"reward": 1.0}})
        self.assertEqual(msgs[0], {"role": "user", "content": "Do X\nSupervisor: A B"})
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant", "user"])
        self.assertNotIn("reward", json.dumps(msgs))


if __name__ == "__main__":
    unittest.main()
