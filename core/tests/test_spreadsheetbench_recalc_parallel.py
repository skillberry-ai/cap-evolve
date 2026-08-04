"""Formula recalculation must be per-call isolated, so it can run concurrently.

The vendored `just_open_libreoffice` lets soffice use its default user profile, so two
headless instances collide and it had to run behind a process-global lock. At full-tier scale
that lock IS the scoring bottleneck: 912 tasks x 3 test cases = 2,736 serialized soffice
startups per evaluation, completely unaffected by SPREADSHEETBENCH_CONCURRENCY.

`_recalc_workbook` replaces it and gives every invocation its own `-env:UserInstallation`
profile. These tests drive it against a FAKE soffice script, so they verify the contract
(profile isolation, no global lock, in-place replacement, failure reporting) on any machine —
no LibreOffice required.
"""

import ast
import importlib.util
import stat
import sys
import textwrap
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
ADAPTER_DIR = REPO / "templates" / "adapters" / "spreadsheetbench"
ADAPTER = ADAPTER_DIR / "adapter.py"


def _load():
    for p in (REPO / "core", ADAPTER_DIR, ADAPTER_DIR.parent):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    spec = importlib.util.spec_from_file_location("_sb_recalc", ADAPTER)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_soffice(tmp_path: Path, *, body: str) -> Path:
    """A stand-in for soffice. `body` runs after args are recorded."""
    p = tmp_path / "fake_soffice"
    p.write_text(textwrap.dedent(f"""\
        #!/usr/bin/env python3
        import sys, pathlib
        args = sys.argv[1:]
        rec = pathlib.Path({str(tmp_path / "calls.log")!r})
        with rec.open("a") as fh:
            fh.write("\\t".join(args) + "\\n")
        outdir = args[args.index("--outdir") + 1]
        src = pathlib.Path(args[-1])
        {textwrap.indent(body, " " * 8).lstrip()}
    """), encoding="utf-8")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return p


CONVERT_OK = """
dest = pathlib.Path(outdir) / (src.stem + ".xlsx")
dest.write_bytes(b"RECALCULATED")
"""


def _book(tmp_path: Path, name="1_42_output.xlsx") -> Path:
    p = tmp_path / name
    p.write_bytes(b"ORIGINAL")
    return p


def test_recalc_replaces_the_workbook_in_place(tmp_path):
    mod = _load()
    book = _book(tmp_path)
    soffice = _fake_soffice(tmp_path, body=CONVERT_OK)
    assert mod._recalc_workbook(book, str(soffice)) is True
    assert book.read_bytes() == b"RECALCULATED", "recalculated values must land in the original path"


def test_each_call_gets_its_own_user_profile(tmp_path):
    """This is what makes concurrency safe — a shared profile is why the lock existed."""
    mod = _load()
    soffice = _fake_soffice(tmp_path, body=CONVERT_OK)
    for i in range(3):
        assert mod._recalc_workbook(_book(tmp_path, f"{i}_42_output.xlsx"), str(soffice)) is True

    calls = [ln.split("\t") for ln in (tmp_path / "calls.log").read_text().splitlines()]
    profiles = []
    for args in calls:
        env = [a for a in args if a.startswith("-env:UserInstallation=")]
        assert env, f"no -env:UserInstallation in {args}"
        profiles.append(env[0])
    assert len(set(profiles)) == len(profiles) == 3, f"profiles must be unique: {profiles}"
    assert all(p.startswith("-env:UserInstallation=file://") for p in profiles)


def test_headless_and_no_leftover_profile_dirs(tmp_path):
    mod = _load()
    soffice = _fake_soffice(tmp_path, body=CONVERT_OK)
    assert mod._recalc_workbook(_book(tmp_path), str(soffice)) is True
    args = (tmp_path / "calls.log").read_text().split("\t")
    assert "--headless" in args and "--calc" in args
    # the temp profile/outdir tree is cleaned up
    leftovers = [p.name for p in Path("/tmp").glob("capevolve_sb_libre_*")]
    assert leftovers == [], f"left temp dirs behind: {leftovers[:3]}"


def test_concurrent_recalc_all_succeed(tmp_path):
    """The full-tier shape: many recalcs at once, which the global lock used to prevent."""
    mod = _load()
    soffice = _fake_soffice(tmp_path, body=CONVERT_OK)
    books = [_book(tmp_path, f"c{i}_42_output.xlsx") for i in range(24)]
    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda b: mod._recalc_workbook(b, str(soffice)), books))
    assert all(results), f"{results.count(False)} of {len(results)} concurrent recalcs failed"
    assert all(b.read_bytes() == b"RECALCULATED" for b in books)


def test_no_global_libreoffice_lock_remains():
    """A surviving module-level lock would silently re-serialize everything."""
    tree = ast.parse(ADAPTER.read_text(encoding="utf-8"))
    names = [t.id for n in tree.body if isinstance(n, ast.Assign)
             for t in n.targets if isinstance(t, ast.Name)]
    assert "_libre_lock" not in names, "module-level _libre_lock is back — recalc is serialized again"


def test_the_serialized_vendored_helper_is_not_called():
    """Checked by AST, so the explanatory comments naming it do not count as usage."""
    tree = ast.parse(ADAPTER.read_text(encoding="utf-8"))
    used = set()
    for node in ast.walk(tree):
        # vendor["just_open_libreoffice"](...)  /  _open_spreadsheet.just_open_libreoffice
        if isinstance(node, ast.Constant) and node.value == "just_open_libreoffice":
            used.add("subscript")
        if isinstance(node, ast.Attribute) and node.attr == "just_open_libreoffice":
            used.add("attribute")
    assert not used, (
        f"adapter still references the vendored serialized recalc helper ({sorted(used)}); "
        "it shares one soffice profile and prints to stdout — use _recalc_workbook"
    )


# ---- failures are reported, never raised --------------------------------------

def test_nonzero_exit_reports_failure(tmp_path):
    mod = _load()
    soffice = _fake_soffice(tmp_path, body="sys.exit(3)")
    assert mod._recalc_workbook(_book(tmp_path), str(soffice)) is False


def test_missing_converted_file_reports_failure(tmp_path):
    mod = _load()
    soffice = _fake_soffice(tmp_path, body="pass  # convert silently produces nothing")
    assert mod._recalc_workbook(_book(tmp_path), str(soffice)) is False


def test_timeout_reports_failure(tmp_path):
    mod = _load()
    soffice = _fake_soffice(tmp_path, body="import time; time.sleep(5)")
    assert mod._recalc_workbook(_book(tmp_path), str(soffice), timeout=0.5) is False


def test_missing_binary_reports_failure(tmp_path):
    mod = _load()
    assert mod._recalc_workbook(_book(tmp_path), str(tmp_path / "nope")) is False


def test_original_is_left_intact_on_failure(tmp_path):
    """A failed recalc must not corrupt the workbook — scoring still reads it."""
    mod = _load()
    book = _book(tmp_path)
    soffice = _fake_soffice(tmp_path, body="sys.exit(1)")
    assert mod._recalc_workbook(book, str(soffice)) is False
    assert book.read_bytes() == b"ORIGINAL"


def test_recalc_writes_nothing_to_stdout(tmp_path, capfd):
    """Phase stdout is a pure-JSON contract; the vendored helper printed on every failure."""
    mod = _load()
    soffice = _fake_soffice(tmp_path, body="print('LibreOffice chatter'); sys.exit(1)")
    assert mod._recalc_workbook(_book(tmp_path), str(soffice)) is False
    out, _ = capfd.readouterr()
    assert out == "", f"recalc leaked to stdout: {out!r}"
