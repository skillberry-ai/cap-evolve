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
       SWEBENCH_ORACLE=1                               # attach Oracle code context (gold-patch
                                                       #   file[s]) to the prompt — makes single-shot
                                                       #   patching feasible for weaker readers
       SWEBENCH_ORACLE_DATASET=princeton-nlp/SWE-bench_Lite_oracle  # source of the `text` context

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

# Oracle-retrieval mode. When on, attach the "Oracle" prompt context — the file(s)
# the gold patch modifies — to each instance so a SINGLE-SHOT model can produce a
# diff that actually applies (blind problem-statement-only prompting is near-hopeless
# for a mid-tier reader). Context is borrowed from the parallel ``*_oracle`` dataset's
# ``text`` field, keyed by instance_id; SCORING still uses the base DATASET above, so
# the well-tested eval path is unchanged. Off by default → exactly today's behavior.
ORACLE = os.environ.get("SWEBENCH_ORACLE", "").strip().lower() in ("1", "true", "yes", "on")
ORACLE_DATASET = os.environ.get("SWEBENCH_ORACLE_DATASET", "princeton-nlp/SWE-bench_Lite_oracle")

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

    if ORACLE:
        _attach_oracle_text(rows)

    _instances_cache = rows
    return _instances_cache


def _attach_oracle_text(rows: list[dict]) -> None:
    """Attach the Oracle-retrieval prompt (``text``) to each row, keyed by instance_id.

    The ``*_oracle`` dataset packs the gold-patch file(s) + issue statement into its
    ``text`` field; we borrow only that context for the prompt. Instances absent from
    the oracle set keep an empty ``oracle_text`` and fall back to blind prompting.
    """
    from datasets import load_dataset

    want = {r["instance_id"] for r in rows}
    try:
        ods = load_dataset(ORACLE_DATASET, split=SPLIT)
    except Exception as e:
        raise RuntimeError(
            f"SWEBENCH_ORACLE is set but loading {ORACLE_DATASET}/{SPLIT} failed: {e}. "
            "Install: pip install datasets (and check the oracle dataset name/split)."
        ) from e

    text_by_id = {
        row["instance_id"]: row.get("text", "")
        for row in ods
        if row["instance_id"] in want
    }
    for r in rows:
        r["oracle_text"] = text_by_id.get(r["instance_id"], "")


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
                    "oracle_text": inst.get("oracle_text", ""),
                },
                metadata={"benchmark": "swebench", "repo": inst.get("repo", "")},
            )
            for inst in instances
        ]

    # ---- running ---------------------------------------------------------

    def run_trials(self, tasks: list[Task], ctx, *, n_trials: int, base_seed: int) -> dict:
        """Generate all task×trial patches concurrently (bounded by SWEBENCH_MAX_WORKERS).

        Parallelizes patch GENERATION only — the harness scores (Docker eval) each
        returned rollout sequentially. Each trial k uses seed = base_seed + k.
        """
        from cap_evolve import run_trials_pool

        return run_trials_pool(
            lambda task, seed: self.run_target(task, ctx, seed=seed),
            tasks, n_trials=n_trials, base_seed=base_seed, max_workers=MAX_WORKERS,
        )

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
        oracle_text = instance.get("oracle_text", "")

        if oracle_text:
            # Oracle mode: the dataset-provided prompt already bundles the relevant
            # code context + issue statement + a patch-output instruction, so a
            # single-shot model can produce an APPLYING diff. Our (optimizable)
            # system prompt still steers HOW to analyze and format the fix.
            user_message = oracle_text
        else:
            # Blind mode: only the issue text — the model must reconstruct file paths
            # and surrounding context from memory (hard for a mid-tier reader).
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
        pre = _cheap_score_precheck(task.id, rollout)
        if pre is not None:
            return pre

        try:
            reward, feedback = self._evaluate_patch(task.id, rollout.output or "")
        except Exception as e:  # noqa: BLE001
            return Score(
                task_id=task.id,
                reward=0.0,
                feedback=f"Evaluation harness error: {e}. Check Docker is running.",
            )

        return Score(task_id=task.id, reward=reward, feedback=feedback)

    def score_batch(self, tasks: list[Task], rollouts: dict) -> dict:
        """Score a WHOLE trial's rollouts with ONE swebench harness invocation.

        A single-instance call (the ``score()`` path) has nothing for
        ``--max_workers`` to parallelize over; batching every instance in this
        trial into one ``run_evaluation`` call with multiple ``--instance_ids``
        lets the harness build/run those Docker containers concurrently. Cheap
        local checks (error/empty/non-diff) still run per-rollout first, so they
        never occupy a Docker slot — same as ``score()``.
        """
        out: dict[str, Score] = {}
        batchable: list[tuple[str, str]] = []
        for task in tasks:
            rollout = rollouts.get(task.id) or Rollout(task_id=task.id, error="omitted from batch result")
            pre = _cheap_score_precheck(task.id, rollout)
            if pre is not None:
                out[task.id] = pre
                continue
            batchable.append((task.id, rollout.output or ""))

        if batchable:
            try:
                results = self._evaluate_patches_batch(batchable)
            except Exception as e:  # noqa: BLE001
                results = {
                    iid: (0.0, f"Evaluation harness error: {e}. Check Docker is running.")
                    for iid, _ in batchable
                }
            for iid, (reward, feedback) in results.items():
                out[iid] = Score(task_id=iid, reward=reward, feedback=feedback)

        return out

    def _evaluate_patch(self, instance_id: str, patch: str) -> tuple[float, str]:
        """Run the swebench Docker harness for one instance + patch.

        Thin wrapper over ``_evaluate_patches_batch`` with a single pair, so the
        harness-invocation/report-parsing logic exists in exactly one place.
        """
        return self._evaluate_patches_batch([(instance_id, patch)])[instance_id]

    def _evaluate_patches_batch(self, pairs: list[tuple[str, str]]) -> dict:
        """Run the swebench Docker harness for MULTIPLE (instance_id, patch) pairs
        in ONE subprocess call.

        Uses the current ``swebench.harness.run_evaluation`` CLI
        (``--dataset_name/--predictions_path/--max_workers/--run_id``), passing
        ALL instance ids as one comma-separated ``--instance_ids`` list so
        ``--max_workers`` actually parallelizes Docker evaluation across them —
        a single-id call has nothing to parallelize. Reads the
        ``<model>.<run_id>.json`` report it writes (``resolved_ids``) and returns
        ``{instance_id: (reward, feedback)}`` with one entry per input pair.
        """
        if not pairs:
            return {}

        run_id = f"capevolve_batch_{pairs[0][0]}_{len(pairs)}"
        with tempfile.TemporaryDirectory(prefix="swebench_eval_") as tmpdir:
            tmp = Path(tmpdir)
            predictions_path = tmp / "predictions.jsonl"
            with predictions_path.open("w", encoding="utf-8") as f:
                for instance_id, patch in pairs:
                    f.write(json.dumps({
                        "instance_id": instance_id,
                        "model_patch": patch,
                        "model_name_or_path": model_config.MODEL,
                    }) + "\n")

            instance_ids_csv = ",".join(iid for iid, _ in pairs)
            cmd = [
                sys.executable,
                "-m",
                "swebench.harness.run_evaluation",
                "--dataset_name", DATASET,
                "--split", SPLIT,
                "--instance_ids", instance_ids_csv,
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
                msg = (
                    f"Evaluation timed out. Docker image builds can be slow on the "
                    f"first run; raise SWEBENCH_TIMEOUT (currently {TIMEOUT}s)."
                )
                return {iid: (0.0, msg) for iid, _ in pairs}

            report = _parse_swebench_report(tmp, run_id)
            if report is None:
                stderr_tail = (proc.stderr or "")[-800:]
                msg = (
                    f"No evaluation report produced (harness exit {proc.returncode}). "
                    f"Check Docker is running and the image built. stderr: {stderr_tail}"
                )
                return {iid: (0.0, msg) for iid, _ in pairs}

            return {
                iid: _score_from_report(iid, report, proc.returncode)
                for iid, _ in pairs
            }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _looks_like_diff(text: str) -> bool:
    """True if ``text`` contains unified-diff markers (cheap, no Docker)."""
    return any(m in text for m in ("diff --git", "\n--- ", "--- ", "@@ ")) or text.startswith("--- ")


def _cheap_score_precheck(instance_id: str, rollout: Rollout) -> Score | None:
    """Local, Docker-free checks shared by ``score()`` and ``score_batch()``.

    Returns a terminal ``Score`` for an infra-error/empty/non-diff rollout so it
    never occupies a Docker slot, or ``None`` when the patch is diff-shaped and
    should proceed to the harness. This also keeps `cap-evolve check`'s scorer
    probe (a synthetic non-diff rollout) offline and fast.
    """
    if rollout.error:
        return Score(
            task_id=instance_id,
            reward=0.0,
            feedback=(
                f"Rollout failed: {rollout.error}. Infrastructure error, "
                "not a prompt defect; do not optimize against it."
            ),
        )

    patch = rollout.output or ""
    if not patch.strip():
        return Score(
            task_id=instance_id,
            reward=0.0,
            feedback="Empty patch produced. The prompt must instruct the model "
            "to output a valid unified diff.",
        )

    if not _looks_like_diff(patch):
        return Score(
            task_id=instance_id,
            reward=0.0,
            feedback="Output is not a valid unified diff (no diff/---/@@ markers). "
            "The prompt must instruct the model to output ONLY a unified diff.",
        )

    return None


def _parse_swebench_report(tmp: Path, run_id: str) -> dict | None:
    """Load the swebench harness's report JSON for ``run_id`` from ``tmp``, if any.

    The harness writes ``<model_name_or_path sanitized>.<run_id>.json`` to cwd;
    fall back to any ``*.json`` in ``tmp`` in case the naming doesn't match.
    """
    reports = list(tmp.glob(f"*{run_id}.json")) + list(tmp.glob("*.json"))
    for rf in reports:
        try:
            return json.loads(rf.read_text(encoding="utf-8"))
        except Exception:  # not the report file — skip
            continue
    return None


def _score_from_report(instance_id: str, report: dict, harness_exit: int) -> tuple[float, str]:
    """Read ``instance_id``'s outcome out of a (possibly multi-instance) report."""
    resolved_ids = report.get("resolved_ids", [])
    if instance_id in resolved_ids:
        return 1.0, "Instance resolved — the patch makes the tests pass."

    ran_ids = set(report.get("completed_ids") or []) | set(report.get("submitted_instances") or [])
    if instance_id in ran_ids:
        return 0.0, (
            "Instance NOT resolved: the patch applied/ran but did not make "
            "the failing tests pass. Guide the model toward a correct, "
            "minimal fix for the described issue."
        )

    return 0.0, (
        f"No evaluation report produced (harness exit {harness_exit}). "
        f"Check Docker is running and the image built."
    )


def _extract_patch(text: str) -> str:
    """Extract a unified diff patch from LLM output.

    Handles raw diffs, markdown code blocks, and mixed text+diff output.
    """
    import re

    # Oracle-format output: the model is asked to wrap the diff in <patch>…</patch>.
    patch_tag = re.search(r"<patch>\s*(.*?)\s*</patch>", text, re.DOTALL)
    if patch_tag:
        return patch_tag.group(1).strip()

    # Try to extract from markdown code block next.
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
    # Oracle-format output wraps the diff in <patch>…</patch>.
    tagged = "Sure.\n<patch>\n--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@\n-a\n+b\n</patch>\nthanks"
    assert _extract_patch(tagged).startswith("--- a/f.py"), _extract_patch(tagged)
    assert _extract_patch(tagged).endswith("+b"), _extract_patch(tagged)
    assert _looks_like_diff("--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@")
    assert not _looks_like_diff("__probe_output__")  # check probe stays offline
    assert not _looks_like_diff("I could not find the bug.")
    print("swe_bench extract/diff self-check: OK")

    # Cheap precheck: error/empty/non-diff never reach Docker; a real diff passes through.
    assert _cheap_score_precheck("i1", Rollout(task_id="i1", error="boom")) is not None
    assert _cheap_score_precheck("i1", Rollout(task_id="i1", output="")) is not None
    assert _cheap_score_precheck("i1", Rollout(task_id="i1", output="not a diff")) is not None
    assert _cheap_score_precheck("i1", Rollout(task_id="i1", output="--- a/f.py\n+++ b/f.py\n@@ -1 +1 @@")) is None

    # Batch report parsing (no subprocess/Docker): a multi-instance report resolves
    # one instance, runs-but-fails a second, and never mentions a third.
    fake_report = {
        "resolved_ids": ["repo__a-1"],
        "completed_ids": ["repo__a-1", "repo__b-2"],
    }
    assert _score_from_report("repo__a-1", fake_report, 0) == (
        1.0, "Instance resolved — the patch makes the tests pass.")
    reward, feedback = _score_from_report("repo__b-2", fake_report, 0)
    assert reward == 0.0 and "NOT resolved" in feedback
    reward, feedback = _score_from_report("repo__c-3", fake_report, 1)
    assert reward == 0.0 and "No evaluation report" in feedback
    print("swe_bench batch-scoring self-check: OK")
