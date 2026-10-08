"""intake's new `objectives` interview question (issue #684 item 4): when the user
opts into multi-objective but doesn't name objectives, intake's own INPUTS.md
contract says to default to the standard reward+cost pair -- the SAME pair
`cap_evolve.gate.decide(mode="pareto")` itself falls back to when `objectives:` is
omitted from `capevolve.yaml`. Pins that documented default against the real
`_DEFAULT_PARETO_OBJECTIVES` constant so the two cannot silently diverge, and against
the scaffolded template's own commented example.
"""

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
INPUTS_MD = REPO / "skills" / "phases" / "intake" / "inputs" / "INPUTS.md"
TEMPLATE_SPEC = REPO / "templates" / "project" / "capevolve.yaml"


def test_default_objectives_constant_is_reward_maximize_cost_minimize():
    from cap_evolve.gate import _DEFAULT_PARETO_OBJECTIVES

    assert _DEFAULT_PARETO_OBJECTIVES == [
        {"name": "reward", "direction": "maximize"},
        {"name": "cost", "direction": "minimize"},
    ]


def test_intake_inputs_md_documents_the_objectives_question_and_its_default():
    text = INPUTS_MD.read_text(encoding="utf-8")
    assert "**objectives**" in text
    # Default behaviour: unset -> single-objective, no behavior change.
    assert "default: unset = single-objective" in text
    # The standard pair, named explicitly, matching gate.py's own fallback constant.
    assert "reward` (maximize) + `cost` (minimize)" in text
    assert "_DEFAULT_PARETO_OBJECTIVES" in text
    # Honesty-cost note, matching how other RECOMMENDED inputs in this file are documented.
    assert "ParetoObjectiveError" in text


def test_template_capevolve_yaml_default_objectives_comment_matches_gate_default():
    from cap_evolve.gate import _DEFAULT_PARETO_OBJECTIVES

    text = TEMPLATE_SPEC.read_text(encoding="utf-8")
    assert "objectives:" in text
    for obj in _DEFAULT_PARETO_OBJECTIVES:
        assert f"{{name: {obj['name']}, direction: {obj['direction']}}}" in text
