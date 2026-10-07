"""specfile.read_yaml's tolerant fallback (no PyYAML): #676 added block-sequence-of-
mappings support (`key:\n  - a: 1\n    b: 2`) and flow-mapping support (`key: {a: 1}`),
needed to parse `objectives:` — a key no real capevolve.yaml used before #665/#667's
pareto gate shipped. Covers both forms the real template/project files use, plus a
regression check that the existing scalar/flow-list/one-level-nesting behavior these
tests already exercised elsewhere is unaffected.
"""
import tempfile
from pathlib import Path

from cap_evolve.specfile import read_yaml, resolve_spec_path, spec_for_run


def test_block_sequence_of_multiline_mappings():
    """The real run_v2_multiobjective project yaml's `objectives:` shape."""
    y = (
        "gate_mode: pareto\n"
        "objectives:\n"
        "  - name: reward\n"
        "    direction: maximize\n"
        "  - name: cost\n"
        "    direction: minimize\n"
        "max_iterations: 12\n"
    )
    assert read_yaml(y) == {
        "gate_mode": "pareto",
        "objectives": [
            {"name": "reward", "direction": "maximize"},
            {"name": "cost", "direction": "minimize"},
        ],
        "max_iterations": 12,
    }


def test_block_sequence_of_flow_mappings():
    """The templates/project/capevolve.yaml documented example's `objectives:` shape."""
    y = (
        "objectives:\n"
        "  - {name: reward, direction: maximize}\n"
        "  - {name: cost, direction: minimize}\n"
    )
    assert read_yaml(y)["objectives"] == [
        {"name": "reward", "direction": "maximize"},
        {"name": "cost", "direction": "minimize"},
    ]


def test_flow_mapping_scalar_value():
    assert read_yaml("x: {a: 1, b: two}\n")["x"] == {"a": 1, "b": "two"}


def test_existing_scalar_list_and_one_level_nesting_still_work():
    """Regression check: #676 only ADDS sequence support, scalars/flow-lists/single-
    level map nesting (the forms every other test's spec fixtures already rely on)
    must read exactly as before."""
    y = (
        "gate_mode: paired\n"
        "capabilities: [system-prompt, tools]\n"
        "metrics_display: []\n"
        "intervention:\n"
        "  type: direct\n"
    )
    assert read_yaml(y) == {
        "gate_mode": "paired",
        "capabilities": ["system-prompt", "tools"],
        "metrics_display": [],
        "intervention": {"type": "direct"},
    }


def test_resolve_spec_path_prefers_the_run_s_own_recorded_spec():
    """A non-default spec filename (`cap-evolve run --spec capevolve.v2.yaml`) must
    resolve to ITSELF, not silently fall back to project/capevolve.yaml — this is the
    bug behind #676's Config tab showing the wrong (generic) spec for a real
    multi-objective run."""
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        project = base / "project"
        project.mkdir()
        (project / "capevolve.yaml").write_text("gate_mode: paired\n", encoding="utf-8")
        variant = project / "capevolve.v2.yaml"
        variant.write_text("gate_mode: pareto\nobjectives:\n  - name: reward\n    direction: maximize\n",
                            encoding="utf-8")

        class _RD:
            events_path = base / "events.jsonl"

        _RD.events_path.write_text("", encoding="utf-8")
        assert resolve_spec_path(_RD, project) == project / "capevolve.yaml"
        assert spec_for_run(_RD, project)["gate_mode"] == "paired"

        _RD.events_path.write_text(
            '{"kind": "run_config", "spec": "%s"}\n' % variant, encoding="utf-8")
        assert resolve_spec_path(_RD, project) == variant
        assert spec_for_run(_RD, project)["gate_mode"] == "pareto"
