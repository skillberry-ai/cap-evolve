"""The static dashboard must disclose a test-seal override, not say "sealed once" (T-76)."""

from cap_evolve.dashboard import write_dashboard
from test_report_test_seal_override import _finalized_run


def _html(rd):
    return write_dashboard(rd).read_text(encoding="utf-8")


def test_override_dashboard_shows_warning(tmp_path, monkeypatch):
    rd = _finalized_run(tmp_path, monkeypatch, override=True)
    html = _html(rd)
    # The page is rendered by JS, so the "sealed once"/"exactly once" strings stay in the
    # template but only on the branch taken when the summary has no override field.
    assert "S.test_rescore_override?'re-scored '" in html
    assert "S.test_rescore_override?' · re-scored '" in html
    assert "(S.test_rescore_override||S.test_reuse_count)\n           ?'" in html
    assert "WARNING: the test split was re-scored" in html
    assert "re-scored '+S.test_rescore_override.count+' time(s)" in html
    assert '"test_rescore_override": {"used": true, "count": 1}' in html
    assert "CAPEVOLVE_ALLOW_TEST_RESCORE" not in html


def test_normal_dashboard_keeps_old_text(tmp_path, monkeypatch):
    rd = _finalized_run(tmp_path, monkeypatch, override=False)
    html = _html(rd)
    assert "sealed once" in html
    assert "scored exactly once" in html
    assert '"test_rescore_override": {' not in html
