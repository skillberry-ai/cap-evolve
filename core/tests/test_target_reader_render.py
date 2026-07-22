from cap_evolve import harness
from cap_evolve.loop import SplitResult
from cap_evolve import target_profile as tp


def _val():
    return SplitResult(split="val", reward=0.0, stderr=0.0,
                       per_task=[{"task_id": "t1", "reward": 0.0}])


def test_reader_block_injected_when_declared():
    reader = tp.reader_block(tp.resolve("gpt-oss-120b"))
    out = harness._focus_instructions(_val(), None, "all", capabilities=["system-prompt"],
                                      target_reader=reader)
    assert "THE READER" in out and "gpt-oss-120b" in out


def test_no_reader_block_and_no_token_when_agnostic():
    out = harness._focus_instructions(_val(), None, "all", capabilities=["system-prompt"],
                                      target_reader="")
    assert "THE READER" not in out
    assert "{{TARGET_READER}}" not in out  # token must be substituted away
