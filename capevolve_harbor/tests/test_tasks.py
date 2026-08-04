"""Tests for capevolve_harbor.tasks — task packaging and TOML escaping."""
import json
from pathlib import Path

from capevolve_harbor.tasks import package_task, package_dataset, _toml_escape


def test_toml_escape_quotes():
    assert _toml_escape('say "hello"') == 'say \\"hello\\"'


def test_toml_escape_newlines():
    assert _toml_escape("line1\nline2") == "line1\\nline2"


def test_toml_escape_backslashes():
    assert _toml_escape("path\\to\\file") == "path\\\\to\\\\file"


def test_toml_escape_combined():
    assert _toml_escape('a "b"\nc\\d') == 'a \\"b\\"\\nc\\\\d'


def test_package_task_creates_structure(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "SKILL.md").write_text("test skill")

    output = tmp_path / "output"
    task_dir = package_task(
        task_id="test-task",
        instruction="Fix the bug",
        candidate_dir=candidate,
        output_dir=output,
    )

    assert task_dir.exists()
    assert (task_dir / "task.toml").exists()
    assert (task_dir / "instruction.md").exists()
    assert (task_dir / "environment" / "Dockerfile").exists()
    assert (task_dir / "environment" / "capability" / "SKILL.md").exists()
    assert (task_dir / "tests" / "test.sh").exists()


def test_package_task_copies_candidate_files(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "prompt.md").write_text("my prompt")
    (candidate / "config.json").write_text('{"key": "val"}')

    output = tmp_path / "output"
    task_dir = package_task(
        task_id="t1",
        instruction="do stuff",
        candidate_dir=candidate,
        output_dir=output,
    )

    cap_dir = task_dir / "environment" / "capability"
    assert (cap_dir / "prompt.md").read_text() == "my prompt"
    assert (cap_dir / "config.json").read_text() == '{"key": "val"}'


def test_package_task_instruction_includes_capability_note(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    output = tmp_path / "output"

    task_dir = package_task(
        task_id="t1",
        instruction="Fix the bug",
        candidate_dir=candidate,
        output_dir=output,
    )

    content = (task_dir / "instruction.md").read_text()
    assert "/capability/" in content
    assert "Fix the bug" in content


def test_package_task_toml_valid(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    output = tmp_path / "output"

    task_dir = package_task(
        task_id="task-with-special",
        instruction="Fix it",
        candidate_dir=candidate,
        output_dir=output,
        description='A task with "quotes" and\nnewlines',
    )

    toml_content = (task_dir / "task.toml").read_text()
    assert '\\"quotes\\"' in toml_content
    assert "\\n" in toml_content


def test_package_task_sanitizes_id(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    output = tmp_path / "output"

    task_dir = package_task(
        task_id="org/repo__issue-123",
        instruction="Fix",
        candidate_dir=candidate,
        output_dir=output,
    )

    assert task_dir.name == "org__repo__issue-123"


def test_package_dataset_creates_multiple_tasks(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "SKILL.md").write_text("skill")
    output = tmp_path / "output"

    tasks = [
        {"id": "task-1", "input": "Fix bug 1"},
        {"id": "task-2", "input": "Fix bug 2"},
        {"id": "task-3", "input": "Fix bug 3"},
    ]

    dataset_dir = package_dataset(tasks, candidate, output)

    assert dataset_dir.exists()
    assert (dataset_dir / "task-1" / "task.toml").exists()
    assert (dataset_dir / "task-2" / "task.toml").exists()
    assert (dataset_dir / "task-3" / "task.toml").exists()


def test_package_dataset_all_share_same_candidate(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "prompt.md").write_text("shared prompt")
    output = tmp_path / "output"

    tasks = [{"id": "t1", "input": ""}, {"id": "t2", "input": ""}]
    package_dataset(tasks, candidate, output)

    for tid in ("t1", "t2"):
        content = (output / tid / "environment" / "capability" / "prompt.md").read_text()
        assert content == "shared prompt"


def test_test_sh_is_executable(tmp_path):
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    output = tmp_path / "output"

    task_dir = package_task("t1", "Fix", candidate, output)
    test_sh = task_dir / "tests" / "test.sh"
    assert test_sh.stat().st_mode & 0o111
