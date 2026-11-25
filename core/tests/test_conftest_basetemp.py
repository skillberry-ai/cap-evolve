"""conftest.py gives each test session its own temp folder, so a test session running at the same time
cannot delete this session's tmp_path folders (pytest keeps only the newest 3 shared "pytest-N" folders)."""
import pytest


def test_tmp_path_is_under_this_sessions_own_folder(tmp_path, pytestconfig):
    if not str(pytestconfig.option.basetemp or "").count("cap-evolve-pytest-"):
        pytest.skip("--basetemp was given on the command line")
    assert "cap-evolve-pytest-" in str(tmp_path)
    assert "pytest-of-" not in str(tmp_path)
