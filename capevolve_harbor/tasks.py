"""Generate self-contained Harbor task packages from cap-evolve tasks.

Each cap-evolve Task becomes a Harbor task directory:

    <task-id>/
        task.toml           # Harbor task metadata
        instruction.md      # What the agent should do
        environment/
            Dockerfile      # Container definition
            capability/     # Candidate capability files (injected)
        tests/
            test.sh         # Verifier: runs scoring, writes reward.txt
"""

from __future__ import annotations

import shutil
from pathlib import Path


_TASK_TOML_TEMPLATE = """\
schema_version = "1.4"

[task]
name = "{name}"
description = "{description}"

[environment]
docker_image = "{docker_image}"
network_mode = "{network_mode}"
cpus = {cpus}
memory_mb = {memory_mb}

[agent]
timeout_sec = {agent_timeout}

[verifier]
timeout_sec = {verifier_timeout}
"""

_DOCKERFILE_TEMPLATE = """\
FROM {base_image}

RUN apt-get update -qq && apt-get install -y -qq python3 >/dev/null 2>&1 || true

COPY capability/ /capability/
"""

_TEST_SH_TEMPLATE = """\
#!/bin/bash
set -e

# Harbor verifier: write reward to /logs/verifier/reward.txt
mkdir -p /logs/verifier

# If a custom score script exists in /capability, run it
if [ -f /capability/score.sh ]; then
    bash /capability/score.sh > /logs/verifier/reward.txt 2>/logs/verifier/test-stderr.txt
elif [ -f /capability/score.py ]; then
    python3 /capability/score.py > /logs/verifier/reward.txt 2>/logs/verifier/test-stderr.txt
else
    # Default: check if /logs/agent/output.txt exists and is non-empty
    if [ -s /logs/agent/output.txt ]; then
        echo "1" > /logs/verifier/reward.txt
    else
        echo "0" > /logs/verifier/reward.txt
    fi
fi
"""

_DEFAULTS = {
    "docker_image": "ubuntu:22.04",
    "network_mode": "public",
    "cpus": 1,
    "memory_mb": 2048,
    "agent_timeout": 1800,
    "verifier_timeout": 120,
}


def package_task(
    task_id: str,
    instruction: str,
    candidate_dir: Path,
    output_dir: Path,
    *,
    config: dict | None = None,
    description: str = "",
    dockerfile: str | None = None,
    test_script: str | None = None,
) -> Path:
    """Write one Harbor task directory under output_dir/<task_id>/.

    Returns the path to the generated task directory.
    """
    cfg = {**_DEFAULTS, **(config or {})}
    safe_id = task_id.replace("/", "__").replace(" ", "_")
    task_dir = output_dir / safe_id
    task_dir.mkdir(parents=True, exist_ok=True)

    _write_task_toml(task_dir / "task.toml", safe_id, description or task_id, cfg)
    _write_instruction(task_dir / "instruction.md", instruction)
    _write_environment(task_dir / "environment", candidate_dir, cfg, dockerfile)
    _write_tests(task_dir / "tests", test_script)

    return task_dir


def package_dataset(
    tasks: list[dict],
    candidate_dir: Path,
    output_dir: Path,
    *,
    config: dict | None = None,
    dockerfile: str | None = None,
    test_script: str | None = None,
) -> Path:
    """Generate a Harbor dataset (directory of task packages).

    Each item in tasks should have keys: id, input, and optionally
    description and metadata.

    Returns the dataset root directory.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    for t in tasks:
        package_task(
            task_id=str(t["id"]),
            instruction=str(t.get("input", "")),
            candidate_dir=candidate_dir,
            output_dir=output_dir,
            config=config,
            description=str(t.get("description", t["id"])),
            dockerfile=dockerfile,
            test_script=test_script,
        )

    return output_dir


def _toml_escape(s: str) -> str:
    """Escape a string for safe embedding in a TOML quoted value."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _write_task_toml(dest: Path, name: str, description: str, cfg: dict) -> None:
    content = _TASK_TOML_TEMPLATE.format(
        name=_toml_escape(name),
        description=_toml_escape(description),
        docker_image=cfg.get("docker_image", _DEFAULTS["docker_image"]),
        network_mode=cfg.get("network_mode", _DEFAULTS["network_mode"]),
        cpus=cfg.get("cpus", _DEFAULTS["cpus"]),
        memory_mb=cfg.get("memory_mb", _DEFAULTS["memory_mb"]),
        agent_timeout=cfg.get("agent_timeout", _DEFAULTS["agent_timeout"]),
        verifier_timeout=cfg.get("verifier_timeout", _DEFAULTS["verifier_timeout"]),
    )
    dest.write_text(content, encoding="utf-8")


def _write_instruction(dest: Path, instruction: str) -> None:
    preamble = (
        "The capability files for this task are located at `/capability/` "
        "inside the container.\n\n"
    )
    dest.write_text(preamble + instruction, encoding="utf-8")


def _write_environment(
    env_dir: Path, candidate_dir: Path, cfg: dict, dockerfile: str | None
) -> None:
    env_dir.mkdir(parents=True, exist_ok=True)

    cap_dest = env_dir / "capability"
    if cap_dest.exists():
        shutil.rmtree(cap_dest)

    candidate_dir = Path(candidate_dir)
    if candidate_dir.is_dir():
        shutil.copytree(candidate_dir, cap_dest)
    else:
        cap_dest.mkdir(parents=True, exist_ok=True)

    df_path = env_dir / "Dockerfile"
    if dockerfile:
        df_path.write_text(dockerfile, encoding="utf-8")
    else:
        base = cfg.get("docker_image", _DEFAULTS["docker_image"])
        df_path.write_text(
            _DOCKERFILE_TEMPLATE.format(base_image=base), encoding="utf-8"
        )


def _write_tests(tests_dir: Path, test_script: str | None) -> None:
    tests_dir.mkdir(parents=True, exist_ok=True)
    script = test_script or _TEST_SH_TEMPLATE
    test_sh = tests_dir / "test.sh"
    test_sh.write_text(script, encoding="utf-8")
    test_sh.chmod(0o755)
