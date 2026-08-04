"""The bind mount must be USABLE before a run is allowed to spend money.

SPREADSHEETBENCH_DATA_DIR is bind-mounted at /mnt/data inside a container running as uid
1000, so if that ONE directory is not traversable by other uids then every path under the
mount is unreachable — `open()` on an input workbook and even `Path.exists()` raise EACCES
(a missing search bit, not a missing file). The upstream 912-task archive ships its
top-level dir as `drwx------` while everything below it is 0755 (the 200-task sample ships
0755), and `tar` preserves stored modes — so the extracted tree passes every casual
inspection while locking the sandbox out completely.

That is not hypothetical: pilot run 30691123806 burned $77.49 and ~3h of wall time, scored
0.000 on 50 tasks with an EACCES traceback in all 50 rollouts, and reported the cause as
"the output dir is not writable" — which sent the diagnosis after SELinux and output-dir
modes for hours. Then the optimizer, told to prefer code edits, "fixed" it by patching
adapter.py, so the run's apparent 0.000 → 0.567 gain was pure infrastructure repair with
the prompt under optimization left byte-identical.

So: heal what we own, verify before the first LLM call, fail loudly, and describe the
fault correctly when it happens anyway.
"""

import importlib.util
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ADAPTER_DIR = REPO / "templates" / "adapters" / "spreadsheetbench"
FETCH_SH = REPO / "ci" / "benchmarks" / "spreadsheetbench" / "fetch_data.sh"
RUN_SUITE = REPO / "ci" / "benchmarks" / "lib" / "run_suite.sh"
TPL_DIR = REPO / "templates" / "project" / "optimizer"


def _load_adapter_module():
    """Import the adapter template for its pure helpers (see test_spreadsheetbench_recalc_perms)."""
    for p in (REPO / "core", ADAPTER_DIR, ADAPTER_DIR.parent):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("_sb_adapter_mount", ADAPTER_DIR / "adapter.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _dataset_tree(root: Path, *, root_mode: int) -> Path:
    """A minimal dataset tree whose top-level dir carries `root_mode`, as tar would leave it."""
    tree = root / "all_data_912_v0.1"
    task = tree / "spreadsheet" / "110-2"
    task.mkdir(parents=True)
    (task / "1_110-2_input.xlsx").write_bytes(b"PK\x03\x04")
    (task / "1_110-2_answer.xlsx").write_bytes(b"PK\x03\x04")
    (tree / "dataset.json").write_text("[]", encoding="utf-8")
    os.chmod(tree, root_mode)
    return tree


# --- the mount preflight ----------------------------------------------------------------


def test_preflight_heals_the_0700_root_the_912_archive_ships():
    mod = _load_adapter_module()
    with tempfile.TemporaryDirectory() as td:
        tree = _dataset_tree(Path(td), root_mode=0o700)
        mod._preflight_mount(tree)                       # must widen, not raise
        mode = os.stat(tree).st_mode
        assert mode & stat.S_IROTH and mode & stat.S_IXOTH, "root must be o+rX for the container"
        assert mode & stat.S_IRGRP and mode & stat.S_IXGRP, "and g+rX — group class matches first"
        # a+w is NOT granted: the dataset tree is read-only INPUT.
        assert not mode & stat.S_IWOTH and not mode & stat.S_IWGRP


def test_preflight_creates_a_container_writable_outputs_root():
    mod = _load_adapter_module()
    with tempfile.TemporaryDirectory() as td:
        tree = _dataset_tree(Path(td), root_mode=0o755)
        mod._preflight_mount(tree)
        outputs = tree / "outputs"
        assert outputs.is_dir()
        assert os.stat(outputs).st_mode & stat.S_IWOTH, "container's uid must be able to write"
        assert os.stat(outputs).st_mode & stat.S_ISVTX, "sticky: one rollout must not delete another's"


def test_preflight_is_idempotent_on_a_healthy_tree():
    mod = _load_adapter_module()
    with tempfile.TemporaryDirectory() as td:
        tree = _dataset_tree(Path(td), root_mode=0o755)
        mod._preflight_mount(tree)
        before = os.stat(tree).st_mode, os.stat(tree / "outputs").st_mode
        mod._preflight_mount(tree)
        assert (os.stat(tree).st_mode, os.stat(tree / "outputs").st_mode) == before


def test_preflight_heals_workbooks_the_extracting_umask_left_unreadable():
    """`tar` ANDs stored modes with the extracting shell's umask, so the workbooks
    themselves can land 0640/0600 — fixing only the root would still deny the read."""
    mod = _load_adapter_module()
    with tempfile.TemporaryDirectory() as td:
        tree = _dataset_tree(Path(td), root_mode=0o750)
        wb = tree / "spreadsheet" / "110-2" / "1_110-2_input.xlsx"
        os.chmod(wb, 0o600)
        os.chmod(wb.parent, 0o750)
        mod._preflight_mount(tree)                       # heals the tree we own
        mode = os.stat(wb).st_mode
        # BOTH classes: the container's gid usually matches the tree's group, and POSIX
        # stops at the first matching class — `-rw----r--` is still EACCES for it.
        assert mode & stat.S_IROTH and mode & stat.S_IRGRP, "workbook must be container-readable"
        dmode = os.stat(wb.parent).st_mode
        assert dmode & stat.S_IXOTH and dmode & stat.S_IXGRP, "and its dir traversable"
        assert not mode & stat.S_IWOTH, "read-only input stays read-only"


def test_preflight_aborts_when_the_inputs_cannot_be_widened():
    """A tree we do NOT own must stop the run, not produce 50 rollouts of EACCES."""
    mod = _load_adapter_module()
    with tempfile.TemporaryDirectory() as td:
        tree = _dataset_tree(Path(td), root_mode=0o755)
        wb = tree / "spreadsheet" / "110-2" / "1_110-2_input.xlsx"
        os.chmod(wb, 0o600)
        real_chmod = os.chmod

        def _refuse(path, mode, *a, **k):
            if Path(path) == wb:
                raise PermissionError(13, "Operation not permitted")
            return real_chmod(path, mode, *a, **k)

        os.chmod = _refuse
        try:
            with pytest.raises(RuntimeError) as e:
                mod._preflight_mount(tree)
        finally:
            os.chmod = real_chmod
        msg = str(e.value)
        assert "not readable by the container's uid" in msg
        assert "chmod -R a+rX" in msg, "the message must state the fix"


def test_preflight_error_names_the_mode_and_the_fix(monkeypatch):
    """The 0700-root message is the one a future reader will act on — keep it specific."""
    mod = _load_adapter_module()
    with tempfile.TemporaryDirectory() as td:
        tree = _dataset_tree(Path(td), root_mode=0o700)

        # Simulate a root we do NOT own (a shared cache): the chmod cannot land, so
        # preflight has nothing to heal and must refuse to start the run.
        real_chmod = os.chmod

        def _refuse(path, mode, *a, **k):
            if Path(path) == tree:
                raise PermissionError(13, "Operation not permitted")
            return real_chmod(path, mode, *a, **k)

        monkeypatch.setattr(os, "chmod", _refuse)
        with pytest.raises(RuntimeError) as e:
            mod._preflight_mount(tree)
        msg = str(e.value)
        assert "0o700" in msg, "state the mode we actually found"
        assert "cannot traverse" in msg
        assert "read AND write" in msg, "reads fail too — that is the whole misdiagnosis"
        assert "912" in msg, "point at the known-bad archive"


def test_preflight_runs_before_the_sandbox_is_started():
    """Ordering is the saving: run_target calls _get_sandbox() before its first LLM call,
    so a bad mount costs ~$0 per rollout instead of a full 30-turn eval."""
    src = (ADAPTER_DIR / "adapter.py").read_text(encoding="utf-8")
    body = src.split("def _get_sandbox()", 1)[1].split("\ndef ", 1)[0]
    assert "_preflight_mount(_data_dir())" in body
    assert body.index("_preflight_mount") < body.index("_Sandbox()")


# --- classifying the denial --------------------------------------------------------------


_OUT = "/mnt/data/outputs/110-2_0_fb4ec95f"


def _traceback(path: str) -> str:
    return (
        "PermissionError                        Traceback (most recent call last)\n"
        "Cell In[1], line 3\n"
        "----> 3 wb = openpyxl.load_workbook(path)\n"
        f"PermissionError: [Errno 13] Permission denied: '{path}'"
    )


def test_denied_input_read_is_infrastructure_not_a_zero_reward_miss():
    """The 912 fault denies READS. Classified as a capability miss, it would teach the
    optimizer that 50 tasks are simply unsolvable."""
    mod = _load_adapter_module()
    hit = mod._sandbox_access_denied([_traceback("/mnt/data/spreadsheet/110-2/1_110-2_input.xlsx")], _OUT)
    assert hit is not None and "1_110-2_input.xlsx" in hit


def test_denied_output_write_still_classifies():
    mod = _load_adapter_module()
    assert mod._sandbox_access_denied([_traceback(f"{_OUT}/1_110-2_output.xlsx")], _OUT) is not None


def test_another_rollouts_output_dir_is_not_our_fault():
    """50 rollouts share the outputs root; a denial in someone else's dir is not ours."""
    mod = _load_adapter_module()
    assert mod._sandbox_access_denied([_traceback("/mnt/data/outputs/other_tag/1_x_output.xlsx")], _OUT) is None


def test_ordinary_code_errors_are_left_to_the_optimizer():
    mod = _load_adapter_module()
    assert mod._sandbox_access_denied(["NameError: name 'wb' is not defined"], _OUT) is None
    assert mod._sandbox_access_denied([], _OUT) is None


def test_read_and_write_denials_get_different_diagnoses():
    """Same classifier, two causes, two fixes — the run must say which one it hit."""
    src = (ADAPTER_DIR / "adapter.py").read_text(encoding="utf-8")
    assert "sandbox denied writes to the bind-mounted output dir" in src
    assert "sandbox denied access through the bind mount" in src
    assert "traverse/read SPREADSHEETBENCH_DATA_DIR" in src


# --- fetch-time normalization -------------------------------------------------------------


def test_fetch_data_normalizes_modes_after_extract():
    sh = FETCH_SH.read_text(encoding="utf-8")
    assert "chmod -R a+rX" in sh, "tar preserves the archive's 0700 root — normalize it"
    assert "chmod -R a+rw" not in sh and "chmod -R 777" not in sh, "input data stays read-only"
    # The cached-tree early exit must normalize too, or a tree fetched by an older
    # revision of this script keeps its bad root forever.
    cached_branch = sh.split('if [ -f "$OUT/dataset.json" ]; then', 1)[1].split("fi", 1)[0]
    assert "chmod a+rX" in cached_branch


def test_fetch_data_is_valid_bash():
    assert subprocess.run(["bash", "-n", str(FETCH_SH)]).returncode == 0


# --- Fix 2: prompt-only optimizer instructions --------------------------------------------


def test_prompt_only_template_has_no_tools_guidance():
    """spreadsheetbench's capability is `[system-prompt]` — one prompt.md, no tools. The
    default template names tau2's artifacts, so the optimizer goes looking for code."""
    txt = (TPL_DIR / "INSTRUCTIONS.prompt-only.md").read_text(encoding="utf-8")
    for leak in ("tools.py", "get_*_details", "policy.md", "docstring"):
        assert leak not in txt, f"prompt-only instructions must not mention {leak}"


def test_prompt_only_template_keeps_the_placeholders_the_harness_substitutes():
    """A template without {{FOCUS_SUMMARY}} is silently discarded for a minimal built-in
    prompt (harness._focus_instructions), which would drop this fix without a trace."""
    txt = (TPL_DIR / "INSTRUCTIONS.prompt-only.md").read_text(encoding="utf-8")
    for ph in ("{{FOCUS_SUMMARY}}", "{{FAILURES}}", "{{PASSING}}", "{{CAP_BRIEF}}",
               "{{ALGO_BRIEF}}", "{{BENCH_REPO}}", "{{PARALLEL_NOTE}}", "{{EMPTY_SEED}}",
               "{{TARGET_READER}}"):
        assert ph in txt, f"missing {ph}"


def test_prompt_only_template_forbids_editing_the_harness():
    """cand_0002 of run 30691123806 scored 0.567 by patching adapter.py while leaving
    prompt.md byte-identical. Nothing in the instructions told it not to."""
    txt = (TPL_DIR / "INSTRUCTIONS.prompt-only.md").read_text(encoding="utf-8")
    assert "may NOT edit the adapter" in txt
    assert "ENVIRONMENT fault" in txt, "and it must say what to do INSTEAD: hand the fault back"


def test_default_template_is_untouched_for_code_bearing_capabilities():
    """tau2 ([system-prompt, tools]) must keep the prefer-code guidance — this PR is
    additive, not a rewrite of the shared default."""
    txt = (TPL_DIR / "INSTRUCTIONS.md").read_text(encoding="utf-8")
    assert "tools.py" in txt


def test_run_suite_uses_the_prompt_only_template_for_spreadsheetbench_only():
    sh = RUN_SUITE.read_text(encoding="utf-8")
    arm = sh.split("  spreadsheetbench)", 1)[1].split("\n  *)", 1)[0]
    assert "INSTRUCTIONS.prompt-only.md" in arm
    assert '"$PROJ/optimizer/INSTRUCTIONS.md"' in arm, "must land at the path cli.py defaults to"
    assert sh.count("INSTRUCTIONS.prompt-only.md") == 1, "other benchmarks keep the default"


def test_run_suite_pins_the_instructions_file_absolutely():
    """A RELATIVE optimizer_instructions_file resolves against different cwds in check vs
    run and can silently fall back to the generic template (#252) — which would erase this
    fix with no error. Pin it, and keep the spec line a no-op for every other arm."""
    sh = RUN_SUITE.read_text(encoding="utf-8")
    assert 'optimizer_instructions_file: "${OPT_INSTRUCTIONS:-}"' in sh
    arm = sh.split("  spreadsheetbench)", 1)[1].split("\n  *)", 1)[0]
    assert 'OPT_INSTRUCTIONS="$PROJ/optimizer/INSTRUCTIONS.md"' in arm
    assert sh.count("OPT_INSTRUCTIONS=") == 1, "only the spreadsheetbench arm sets it"
    # $PROJ is absolute (built from $REPO), so the pinned value is absolute.
    assert 'PROJ="$WORK/.capevolve/project"' in sh and 'WORK="$REPO/ci/benchmarks/' in sh


def test_an_empty_instructions_spec_value_is_falsy_in_both_yaml_parsers():
    """core reads `spec.get(...) or <default>`, so the no-op depends on "" being falsy —
    in PyYAML AND in the hand-rolled fallback parser used when PyYAML is absent."""
    sys.path.insert(0, str(REPO / "core"))
    from cap_evolve import specfile

    sample = 'capabilities: [system-prompt]\noptimizer_instructions_file: ""\nalgorithm_skill: x\n'
    parsed = specfile.read_yaml(sample)
    assert not parsed.get("optimizer_instructions_file")
    assert parsed.get("algorithm_skill") == "x", "the empty value must not swallow later keys"


def test_run_suite_is_valid_bash():
    assert subprocess.run(["bash", "-n", str(RUN_SUITE)]).returncode == 0
