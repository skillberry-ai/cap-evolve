"""SWE-bench adapter template — optimize a coding agent's system prompt for SWE-bench.

Ready-to-use cap-evolve adapter for SWE-bench / SWE-bench Lite
(https://github.com/princeton-nlp/SWE-bench). Supports ANY litellm-compatible
provider — configure via env vars (see model_config.py).

SETUP:
  1. Install swebench:
       pip install swebench

  2. Install Docker (required for the evaluation harness).

  3. Copy this directory to .capevolve/project/adapters/

  4. Copy model_config.py to .capevolve/project/adapters/

  5. Set env vars (in .env or shell) — any litellm provider, see model_config.py:
       MODEL=gpt-4.1-mini  OPENAI_API_KEY=sk-…       # OpenAI
       MODEL=anthropic/claude-sonnet-4-6  ANTHROPIC_API_KEY=…  # Anthropic
       MODEL=vertex_ai/claude-sonnet-4-6              # Vertex AI (ADC, no key)
       MODEL=ollama/qwen2.5:7b-instruct  API_BASE=http://localhost:11434  # local
       MODEL=litellm_proxy/my-model  LITELLM_PROXY_API_BASE=http://proxy:4000  LITELLM_PROXY_API_KEY=…

  6. Optional env vars:
       SWEBENCH_DATASET=princeton-nlp/SWE-bench_Lite  # default dataset
       SWEBENCH_SPLIT=test                             # dataset split
       SWEBENCH_MAX_WORKERS=4                          # parallel evaluations
       SWEBENCH_TIMEOUT=1800                           # per-instance timeout (s)
       SWEBENCH_NAMESPACE=none                         # "none" builds images locally (arm64/Mac);
                                                       #   set "swebench" to pull prebuilt x86 images

  7. Run: cap-evolve check && cap-evolve run

WHAT THIS OPTIMIZES:
  - The coding agent's system prompt (prompt.md in the seed capability).
  - The prompt guides how the agent analyses issues, writes patches, and tests.

HOW IT WORKS:
  - tasks()      → loads SWE-bench instances from HuggingFace datasets.
  - run_target() → calls litellm with the candidate prompt + instance context,
                   produces a unified-diff patch.
  - score()      → runs swebench's evaluation harness (Docker-based) to test
                   the patch against the instance's test suite. Binary reward.

NOTE ON SCORING:
  SWE-bench evaluation requires Docker and runs each patch in an isolated
  container against the repository's test suite. This is the gold-standard
  evaluation — there is no shortcut. Ensure Docker is running and you have
  sufficient disk space for repository images.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cap_evolve import CapabilityAdapter, Rollout, Score, Task

import model_config

# --- configuration ----------------------------------------------------------
DATASET = os.environ.get("SWEBENCH_DATASET", "princeton-nlp/SWE-bench_Lite")
SPLIT = os.environ.get("SWEBENCH_SPLIT", "test")
MAX_WORKERS = int(os.environ.get("SWEBENCH_MAX_WORKERS", "4"))
TIMEOUT = int(os.environ.get("SWEBENCH_TIMEOUT", "1800"))
# "none" → build images locally (correct on arm64/Mac); "swebench" → pull prebuilt x86.
NAMESPACE = os.environ.get("SWEBENCH_NAMESPACE", "none")
# Optional comma-separated subset — the "config, not code" knob for a small/cheap
# run (each instance is a Docker build). Empty → use the whole split.
INSTANCE_IDS = [s.strip() for s in os.environ.get("SWEBENCH_INSTANCE_IDS", "").split(",") if s.strip()]

# Cache loaded instances so tasks() is stable across calls.
_instances_cache: list[dict] | None = None


def _load_instances() -> list[dict]:
    """Load SWE-bench instances from HuggingFace datasets (cached, optional subset)."""
    global _instances_cache
    if _instances_cache is not None:
        return _instances_cache

    try:
        from datasets import load_dataset

        ds = load_dataset(DATASET, split=SPLIT)
        rows = [dict(row) for row in ds]
    except Exception as e:
        raise RuntimeError(
            f"Failed to load SWE-bench dataset {DATASET}/{SPLIT}: {e}. "
            "Install: pip install datasets"
        ) from e

    if INSTANCE_IDS:
        want = set(INSTANCE_IDS)
        rows = [r for r in rows if r["instance_id"] in want]
        if not rows:
            raise RuntimeError(
                f"None of SWEBENCH_INSTANCE_IDS={INSTANCE_IDS} are in {DATASET}/{SPLIT}."
            )
    _instances_cache = rows
    return _instances_cache


class Adapter(CapabilityAdapter):

    # ---- tasks -----------------------------------------------------------

    def tasks(self, split: str) -> list[Task]:
        """Return SWE-bench instances as cap-evolve Tasks."""
        instances = _load_instances()
        return [
            Task(
                id=inst["instance_id"],
                input={
                    "instance_id": inst["instance_id"],
                    "problem_statement": inst.get("problem_statement", ""),
                    "repo": inst.get("repo", ""),
                    "base_commit": inst.get("base_commit", ""),
                    "hints_text": inst.get("hints_text", ""),
                },
                metadata={"benchmark": "swebench", "repo": inst.get("repo", "")},
            )
            for inst in instances
        ]

    # ---- running ---------------------------------------------------------

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        """Generate a patch for one SWE-bench instance using litellm.

        Reads the candidate prompt from ctx (the candidate directory), combines
        it with the instance's problem statement, and calls the configured model
        to produce a unified diff patch.
        """
        candidate_dir = Path(ctx)
        prompt_path = candidate_dir / "prompt.md"

        if prompt_path.exists():
            system_prompt = prompt_path.read_text(encoding="utf-8")
        else:
            system_prompt = _DEFAULT_PROMPT

        instance = task.input if isinstance(task.input, dict) else {}
        problem = instance.get("problem_statement", "")
        repo = instance.get("repo", "")
        hints = instance.get("hints_text", "")

        user_message = f"""You are working on the repository: {repo}

## Problem Description
{problem}
"""
        if hints:
            user_message += f"""
## Hints
{hints}
"""
        user_message += """
## Instructions
Analyze the problem and produce a unified diff patch that fixes the issue.
Output ONLY the patch in unified diff format (starting with --- and +++).
Do not include any explanation before or after the patch.
"""

        try:
            import litellm

            response = litellm.completion(
                model=model_config.MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                seed=seed,  # forwarded per the stochastic-runner contract
                **model_config.llm_kwargs(),
            )
            output = response.choices[0].message.content or ""

            # Extract patch from response (handle markdown code blocks).
            patch = _extract_patch(output)

            cost = float(getattr(response, "_hidden_params", {}).get("response_cost", 0) or 0)
            usage = getattr(response, "usage", None)
            tokens = usage.total_tokens if usage else 0

            return Rollout(
                task_id=task.id,
                output=patch,
                trace=output,
                cost_usd=cost,
                tokens=tokens,
                metadata={
                    "instance_id": task.id,
                    "model": model_config.MODEL,
                    "seed": seed,
                },
            )

        except Exception as e:  # noqa: BLE001
            return Rollout(
                task_id=task.id,
                error=f"LLM call failed: {e}",
                metadata={"instance_id": task.id, "model": model_config.MODEL},
            )

    # ---- scoring ---------------------------------------------------------

    def score(self, task: Task, rollout: Rollout) -> Score:
        """Score a patch using SWE-bench's evaluation harness.

        Runs the patch in a Docker container against the instance's test suite.
        Returns binary reward: 1.0 if all tests pass, 0.0 otherwise.
        """
        if rollout.error:
            return Score(
                task_id=task.id,
                reward=0.0,
                feedback=(
                    f"Rollout failed: {rollout.error}. Infrastructure error, "
                    "not a prompt defect; do not optimize against it."
                ),
            )

        patch = rollout.output or ""
        if not patch.strip():
            return Score(
                task_id=task.id,
                reward=0.0,
                feedback="Empty patch produced. The prompt must instruct the model "
                "to output a valid unified diff.",
            )

        # A non-diff can never resolve an instance — reject cheaply without paying
        # for a Docker build. This also keeps `cap-evolve check`'s scorer probe
        # (a synthetic non-diff rollout) offline and fast.
        if not _looks_like_diff(patch):
            return Score(
                task_id=task.id,
                reward=0.0,
                feedback="Output is not a valid unified diff (no diff/---/@@ markers). "
                "The prompt must instruct the model to output ONLY a unified diff.",
            )

        instance_id = task.id

        try:
            reward, feedback = self._evaluate_patch(instance_id, patch)
        except Exception as e:  # noqa: BLE001
            return Score(
                task_id=task.id,
                reward=0.0,
                feedback=f"Evaluation harness error: {e}. Check Docker is running.",
            )

        return Score(task_id=task.id, reward=reward, feedback=feedback)

    def _evaluate_patch(self, instance_id: str, patch: str) -> tuple[float, str]:
        """Run the swebench Docker harness for one instance + patch.

        Uses the current ``swebench.harness.run_evaluation`` CLI
        (``--dataset_name/--predictions_path/--max_workers/--run_id``) and reads
        the ``<model>.<run_id>.json`` report it writes (``resolved_ids``).
        Returns ``(reward, feedback)``.
        """
        run_id = f"capevolve_{instance_id}"
        with tempfile.TemporaryDirectory(prefix="swebench_eval_") as tmpdir:
            tmp = Path(tmpdir)
            predictions_path = tmp / "predictions.jsonl"
            predictions_path.write_text(
                json.dumps(
                    {
                        "instance_id": instance_id,
                        "model_patch": patch,
                        "model_name_or_path": model_config.MODEL,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            cmd = [
                sys.executable,
                "-m",
                "swebench.harness.run_evaluation",
                "--dataset_name", DATASET,
                "--split", SPLIT,
                "--instance_ids", instance_id,
                "--predictions_path", str(predictions_path),
                "--max_workers", str(MAX_WORKERS),
                "--timeout", str(TIMEOUT),
                "--namespace", NAMESPACE,   # "none" → build locally (arm64-safe)
                "--run_id", run_id,
            ]

            try:
                # Run inside tmpdir so the report JSON + ./logs land there.
                proc = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=TIMEOUT + 600, cwd=tmpdir,
                )
            except subprocess.TimeoutExpired:
                return 0.0, (
                    f"Evaluation timed out. Docker image builds can be slow on the "
                    f"first run; raise SWEBENCH_TIMEOUT (currently {TIMEOUT}s)."
                )

            # The harness writes <model_name_or_path sanitized>.<run_id>.json to cwd.
            reports = list(tmp.glob(f"*{run_id}.json")) + list(tmp.glob("*.json"))
            for rf in reports:
                try:
                    report = json.loads(rf.read_text(encoding="utf-8"))
                except Exception:  # not the report file — skip
                    continue
                resolved_ids = report.get("resolved_ids", [])
                if instance_id in resolved_ids:
                    return 1.0, "Instance resolved — the patch makes the tests pass."
                if report.get("completed_ids") or report.get("submitted_instances"):
                    return 0.0, (
                        "Instance NOT resolved: the patch applied/ran but did not make "
                        "the failing tests pass. Guide the model toward a correct, "
                        "minimal fix for the described issue."
                    )

            stderr_tail = (proc.stderr or "")[-800:]
            return 0.0, (
                f"No evaluation report produced (harness exit {proc.returncode}). "
                f"Check Docker is running and the image built. stderr: {stderr_tail}"
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _looks_like_diff(text: str) -> bool:
    """True if ``text`` contains unified-diff markers (cheap, no Docker)."""
    return any(m in text for m in ("diff --git", "\n--- ", "--- ", "@@ ")) or text.startswith("--- ")


def _extract_patch(text: str) -> str:
    """Extract a unified diff patch from LLM output.

    Handles raw diffs, markdown code blocks, and mixed text+diff output.
    """
    # Try to extract from markdown code block first.
    import re

    code_block = re.search(r"```(?:diff|patch)?\s*\n(.*?)```", text, re.DOTALL)
    if code_block:
        return code_block.group(1).strip()

    # Look for unified diff markers.
    lines = text.split("\n")
    patch_lines: list[str] = []
    in_patch = False
    for line in lines:
        if line.startswith("---") or line.startswith("+++") or line.startswith("@@"):
            in_patch = True
        if in_patch:
            patch_lines.append(line)

    if patch_lines:
        return "\n".join(patch_lines)

    # Fallback: return entire text (may fail at eval, but scorer handles it).
    return text.strip()


_DEFAULT_PROMPT = """\
You are an expert software engineer tasked with fixing bugs in open-source repositories.

Given a problem description from a GitHub issue, analyze the issue carefully and produce
a minimal, correct patch in unified diff format that resolves the problem.

Guidelines:
- Read the problem statement thoroughly before making changes.
- Make the MINIMAL change necessary to fix the issue.
- Do not refactor unrelated code.
- Do not change test files unless the issue specifically requires it.
- Ensure your patch applies cleanly to the repository.
- Output ONLY the unified diff patch — no explanations, no markdown.
"""


if __name__ == "__main__":
    # ponytail self-check: patch extraction + diff detection (no Docker / model).
    md = "Here is the fix:\n```diff\n--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-a\n+b\n```\ndone"
    assert _extract_patch(md).startswith("--- a/f.py"), _extract_patch(md)
    assert _looks_like_diff("--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@")
    assert not _looks_like_diff("__probe_output__")  # check probe stays offline
    assert not _looks_like_diff("I could not find the bug.")
    print("swe_bench extract/diff self-check: OK")
