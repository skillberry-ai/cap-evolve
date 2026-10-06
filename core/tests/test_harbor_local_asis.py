"""HARBOR_LOCAL_ASIS must not silently under-deliver a skill-package candidate.

``HARBOR_LOCAL_ASIS=1`` hands a hand-authored local dataset to ``harbor run`` verbatim so
the default ``package_dataset`` repack cannot overwrite a task's real task.toml / tests/
verifier / Dockerfile with generic templates. The cost of skipping that repack is that the
candidate no longer travels in each task's ``environment/capability/`` dir: the ONLY channel
left is ``--extra-instruction-path``, and ``_write_candidate_instruction`` puts nothing on it
but the text of ``prompt.md``/``SKILL.md``.

The harbor template's own declared default is ``capabilities: [skill-package]``
(templates/adapters/harbor/capevolve.yaml), so the two features compose into a silent bug: a
skill-package candidate under ASIS loses its bundled ``scripts/``/``references/`` while the
run completes, the gate runs and the numbers get published — every edit outside the SKILL.md
body was never delivered, and nothing says so. ``_assert_asis_can_deliver`` turns that into a
loud failure before any container starts.
"""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
ADAPTER_DIR = REPO / "templates" / "adapters" / "harbor"
ADAPTER_PY = ADAPTER_DIR / "adapter.py"


def _load(asis: str | None = None):
    """Import the harbor adapter with HARBOR_LOCAL_ASIS set, since it is read at import."""
    for p in (REPO / "core", ADAPTER_DIR, ADAPTER_DIR.parent):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    prev = os.environ.get("HARBOR_LOCAL_ASIS")
    if asis is None:
        os.environ.pop("HARBOR_LOCAL_ASIS", None)
    else:
        os.environ["HARBOR_LOCAL_ASIS"] = asis
    try:
        spec = importlib.util.spec_from_file_location(f"_harbor_asis_{asis}", ADAPTER_PY)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        if prev is None:
            os.environ.pop("HARBOR_LOCAL_ASIS", None)
        else:
            os.environ["HARBOR_LOCAL_ASIS"] = prev


def _run_batch_body(src: str) -> str:
    """The text of run_batch only — the guard's placement is what this file asserts."""
    return src.split("def run_batch(", 1)[1].split("\n    def ", 1)[0]


# --- the flag itself ---------------------------------------------------------------------


def test_asis_is_off_by_default_and_opt_in():
    """Existing harbor benchmarks must keep repacking; ASIS is a per-benchmark override."""
    assert _load(None).HARBOR_LOCAL_ASIS is False
    assert _load("1").HARBOR_LOCAL_ASIS is True
    assert _load("yes").HARBOR_LOCAL_ASIS is True


# --- the guard ---------------------------------------------------------------------------


def test_instruction_only_candidate_is_deliverable(tmp_path):
    """A bare SKILL.md is fully carried by --extra-instruction-path — nothing is lost."""
    mod = _load("1")
    (tmp_path / "SKILL.md").write_text("# skill\nbody\n", encoding="utf-8")
    mod._assert_asis_can_deliver(tmp_path)  # must not raise


def test_a_skill_package_candidate_is_refused_before_the_run_starts(tmp_path):
    """scripts/ cannot reach the container under ASIS, so the run must not be allowed to
    start and publish a number that silently measures the SKILL.md text alone."""
    mod = _load("1")
    (tmp_path / "SKILL.md").write_text("# skill\nbody\n", encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "solve.py").write_text("print(1)\n", encoding="utf-8")

    with pytest.raises(ValueError) as e:
        mod._assert_asis_can_deliver(tmp_path)
    msg = str(e.value)
    assert "HARBOR_LOCAL_ASIS" in msg, "name the flag that caused this"
    assert "scripts" in msg, "name the path that would have been dropped"
    assert "unset HARBOR_LOCAL_ASIS" in msg, "the message must state the fix"


def test_every_undeliverable_extra_is_named_not_just_the_first(tmp_path):
    """A reader fixing this needs the whole list, not one path and a rerun per file."""
    mod = _load("1")
    (tmp_path / "prompt.md").write_text("do the thing\n", encoding="utf-8")
    (tmp_path / "references").mkdir()
    (tmp_path / "assets").mkdir()
    (tmp_path / "helper.py").write_text("x = 1\n", encoding="utf-8")

    with pytest.raises(ValueError) as e:
        mod._assert_asis_can_deliver(tmp_path)
    msg = str(e.value)
    for name in ("assets", "helper.py", "references"):
        assert name in msg


# --- where the guard is wired ------------------------------------------------------------


def test_the_guard_gates_only_the_asis_branch(tmp_path):
    """It must not become a global gate: the default path DOES repack the whole candidate
    into environment/capability/, so a skill-package candidate is legitimate there."""
    src = ADAPTER_PY.read_text(encoding="utf-8")
    body = _run_batch_body(src)
    before_asis, asis_onwards = body.split("elif HARBOR_LOCAL_ASIS:", 1)
    asis_branch, default_branch = asis_onwards.split("\n        else:", 1)

    assert "_assert_asis_can_deliver" not in before_asis, "not a gate on every run"
    assert "_assert_asis_can_deliver(candidate_dir)" in asis_branch
    assert "_assert_asis_can_deliver" not in default_branch, "package_dataset delivers it all"
    assert body.count("_assert_asis_can_deliver") == 1, "exactly one call site"


def test_the_guard_runs_before_any_container_work():
    """Ordering is the point: a candidate ASIS cannot deliver must fail at zero cost, not
    after a full harbor run has spent money producing an under-delivered number."""
    src = ADAPTER_PY.read_text(encoding="utf-8")
    body = _run_batch_body(src)
    assert "_assert_asis_can_deliver(" in body
    assert "harbor_run(" in body
    assert body.index("_assert_asis_can_deliver(") < body.index("harbor_run(")
