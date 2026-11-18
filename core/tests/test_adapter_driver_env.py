"""``check.load_adapter`` tells an adapter who drives the run, through ``CAPEVOLVE_DRIVER``.

Every cap-evolve entry point loads the project adapter with ``load_adapter``. An optimizer outside cap-evolve imports
the adapter itself, so for it the variable is unset (or holds a value it chose). An adapter reads the variable to
decide, for example, that the loop already runs the helper gate and its own gate must stay out of the way.
What is proved here:

* ``load_adapter`` sets ``CAPEVOLVE_DRIVER=cap-evolve`` before the adapter module runs, so the module can read it
  while it is imported;
* it replaces a value that an outside harness set, because a process that loaded the adapter through cap-evolve
  is a cap-evolve process.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO / "core") not in sys.path:
    sys.path.insert(0, str(REPO / "core"))

from cap_evolve.check import DRIVER_CAP_EVOLVE, DRIVER_ENV, load_adapter  # noqa: E402

# The class body runs while the module is imported, so SEEN is what the adapter module could read at import time.
ADAPTER_SRC = (
    "import os\n"
    "class Adapter:\n"
    "    SEEN = os.environ.get('CAPEVOLVE_DRIVER')\n"
)


@pytest.fixture
def driver_unset(monkeypatch):
    """Start with the variable unset, and make the teardown remove whatever ``load_adapter`` sets.

    ``setenv`` first, so monkeypatch remembers that the variable was unset; ``delenv`` then removes it for the test.
    """
    monkeypatch.setenv(DRIVER_ENV, "placeholder")
    monkeypatch.delenv(DRIVER_ENV)


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "p"
    (project / "adapters").mkdir(parents=True)
    (project / "adapters" / "adapter.py").write_text(ADAPTER_SRC, encoding="utf-8")
    return project


def test_load_adapter_sets_the_driver_before_the_adapter_module_runs(driver_unset, tmp_path):
    adapter = load_adapter(_project(tmp_path))
    assert type(adapter).SEEN == "cap-evolve"
    assert os.environ[DRIVER_ENV] == "cap-evolve" == DRIVER_CAP_EVOLVE


def test_load_adapter_replaces_a_value_an_external_harness_set(driver_unset, tmp_path, monkeypatch):
    monkeypatch.setenv(DRIVER_ENV, "external:gepa")
    adapter = load_adapter(_project(tmp_path))
    assert type(adapter).SEEN == "cap-evolve"
    assert os.environ[DRIVER_ENV] == "cap-evolve"
