"""Legacy spreadsheetbench unit tests build tiny fake datasets whose answer files sit inside DATA_DIR and
score them directly. Since #782 the adapter refuses that layout unless it is explicitly allowed, so default
the opt-out for the whole test session. test_spreadsheetbench_gold_isolation.py scrubs these variables and
tests the real defaults."""
import os

os.environ.setdefault("SPREADSHEETBENCH_AGENT_VIEW", "0")
os.environ.setdefault("SPREADSHEETBENCH_ALLOW_GOLD_IN_MOUNT", "1")


# Several test sessions can run at the same time on one machine (for example parallel checkouts of this
# repo). By default each pytest session deletes all but the newest 3 "pytest-N" folders under the shared
# pytest-of-<user> temp folder, so a newer session can delete the temp folders of one that is still
# running (seen as a random FileNotFoundError on a tmp_path file). Give each session its own temp folder
# instead, unless --basetemp was given. xdist workers get a subfolder of it from the main process.
import shutil
import tempfile

_OWN_BASETEMP = None


def pytest_configure(config):
    global _OWN_BASETEMP
    if hasattr(config, "workerinput") or config.option.basetemp:
        return
    _OWN_BASETEMP = tempfile.mkdtemp(prefix="cap-evolve-pytest-")
    config.option.basetemp = _OWN_BASETEMP


def pytest_unconfigure(config):
    if _OWN_BASETEMP:
        shutil.rmtree(_OWN_BASETEMP, ignore_errors=True)
