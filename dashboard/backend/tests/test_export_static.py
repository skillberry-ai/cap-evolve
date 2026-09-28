"""The static export must ship what the Process tab reads (issue #525).

The tab is gated on ``capabilities.process_html``. A flag that is true while the export
has no payload is the bug: the tab shows and renders a 404. So the flag must follow what
the export wrote, and the payload must be the whole page, not the 256 KiB ``/file`` cut.
"""
import json
import os

from conftest import BASE_EVENTS


def _export(tmp_base, rd, out):
    from capevolve_dashboard.export_static import Exporter

    exp = Exporter(tmp_base, rd.root.name, out)
    exp.export()
    return exp


def _caps(out, rid):
    detail = json.loads((out / f"runs_{rid}.json").read_text(encoding="utf-8"))
    return detail["summary"]["capabilities"]


def test_ships_the_whole_dashboard_html_and_flags_it(tmp_base, make_run, tmp_path):
    rd = make_run("run_t", events=BASE_EVENTS)
    # Bigger than the /file cap, so a cut copy is detectable.
    page = "<!doctype html><html><body>" + "<p>row</p>\n" * 30_000 + "</body></html>"
    assert len(page) > 256 * 1024
    (rd.root / "dashboard.html").write_text(page, encoding="utf-8")
    out = tmp_path / "data"

    exp = _export(tmp_base, rd, out)

    shipped = out / "runs_run_t_process_html.html"
    assert shipped.read_text(encoding="utf-8") == page
    assert shipped.name in exp.written
    assert _caps(out, "run_t")["process_html"] is True


def test_no_dashboard_html_means_no_file_and_no_tab(tmp_base, make_run, tmp_path):
    rd = make_run("run_t", events=BASE_EVENTS)
    out = tmp_path / "data"

    _export(tmp_base, rd, out)

    assert not list(out.glob("*.html"))
    assert _caps(out, "run_t")["process_html"] is False


def test_a_dashboard_html_symlink_out_of_the_run_dir_is_not_shipped(tmp_base, make_run, tmp_path):
    from capevolve_dashboard.export_static import Exporter

    rd = make_run("run_t", events=BASE_EVENTS)
    secret = tmp_path / "outside.html"
    secret.write_text("<p>not part of the run</p>", encoding="utf-8")
    os.symlink(secret, rd.root / "dashboard.html")
    out = tmp_path / "data"

    # Only this step: the /file dump has its own (raising) guard for the same symlink.
    exp = Exporter(tmp_base, "run_t", out)
    assert exp._emit_process_html("run_t", exp.run_path) is False
    assert not (out / "runs_run_t_process_html.html").exists()
