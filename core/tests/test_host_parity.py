"""``skills/_registry/hosts.yaml`` is the SINGLE source of per-host metadata (#143).

Before this file the host list lived in five places — ``install.sh``'s ``case``,
``doctor._VERIFIED_HOST_DIRS``, and the two tables in ``docs/HOST_SUPPORT.md`` — and
drifted (doctor's tuple listed 6 of the 12 real destinations, so six correct host
dirs were reported "best-guess"). These tests are the guard: every consumer must
agree with ``hosts.yaml``, byte for byte on the paths, so adding a host is one row.

They are deliberately *derivation* checks, not restatements: nothing here hardcodes a
destination, so the tests cannot themselves become a sixth copy.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "core"))

from cap_evolve import hosts as H  # noqa: E402

HOST_SUPPORT = REPO / "docs" / "HOST_SUPPORT.md"
INSTALL_SH = REPO / "install.sh"

# The destination table's rows: | `a` / `b` | `dest` | status |
_ROW = re.compile(r"^\|\s*(?P<aliases>[^|]+?)\s*\|\s*`(?P<dest>[^`]+)`\s*\|\s*(?P<status>[^|]+?)\s*\|\s*$")
_BADGE = {"✅": "verified", "🟡": "docs-checked", "➖": "best-guess"}


def _support_dest_rows() -> dict[str, tuple[list[str], str]]:
    """Parse HOST_SUPPORT.md's 'Skill-install destinations' table.

    Returns ``{dest: ([aliases], status)}``. Only that table's rows have a
    backticked destination in column 2, so the regex picks them out unambiguously.
    """
    out: dict[str, tuple[list[str], str]] = {}
    for line in HOST_SUPPORT.read_text(encoding="utf-8").splitlines():
        m = _ROW.match(line)
        if not m:
            continue
        dest = m.group("dest")
        if not dest.startswith(("$HOME/", "$PWD/", "~/")):
            continue
        aliases = [a.strip().strip("`") for a in m.group("aliases").split("/")]
        badge = next((v for k, v in _BADGE.items() if k in m.group("status")), None)
        if badge:
            out[dest] = (aliases, badge)
    return out


def test_hosts_yaml_parses_and_rows_are_well_formed():
    rows = H.load_hosts()
    assert rows, "hosts.yaml is empty or unparseable"
    for name, row in rows.items():
        assert row.get("aliases"), f"{name}: no aliases"
        # Strict membership only. The old `or name.replace("-","") in "".join(aliases)`
        # escape hatch passed on unrelated substrings (a key `bo` would "match"
        # `ibm-bob`) and no row needs it — every key is literally in its own aliases.
        assert name in row["aliases"], \
            f"{name}: the row key must appear verbatim in its own aliases {row['aliases']}"
        assert str(row.get("dest", "")).startswith(("$HOME/", "$PWD/")), \
            f"{name}: dest must be written with the literal $HOME/$PWD install.sh uses"
        assert row.get("status") in H.STATUSES, f"{name}: bad status {row.get('status')!r}"
        assert row.get("evidence"), f"{name}: every row must say what justifies its grade"
        for k in ("display", "description", "invoke"):
            assert row.get(k), f"{name}: missing per-host metadata {k!r}"


def test_verified_rows_cite_an_executing_artifact_that_exists():
    """The exact defect PR #202's review caught: a ✅ with no proving artifact.

    A ``verified`` row's evidence must name a file in this repo that is really there.
    """
    for name, row in H.load_hosts().items():
        if row.get("status") != "verified":
            continue
        ev = str(row["evidence"])
        cited = [t for t in re.findall(r"[\w./-]+\.(?:sh|py|yml|yaml|md)", ev)
                 if "/" in t and not t.startswith("$")]
        assert cited, f"{name}: verified but evidence cites no artifact path"
        for t in cited:
            assert (REPO / t).exists(), f"{name}: verified, but cited artifact {t} does not exist"


def test_install_sh_derives_its_mapping_from_hosts_yaml():
    """install.sh must not carry a second copy of the host->dir table.

    Scoped to the ``--host`` branch: ``$HOME/.claude/skills`` legitimately appears
    further down as the *auto-detect* fallback, which is a different mechanism.
    """
    txt = INSTALL_SH.read_text(encoding="utf-8")
    assert "cap_evolve.hosts --dest" in txt, "install.sh no longer derives dests from hosts.yaml"
    assert 'case "$HOST" in' not in txt, "the hardcoded --host case is back (#143 removed it)"
    branch = txt.split('if [[ -n "$HOST" ]]; then', 1)[1].split("\n  fi", 1)[0]
    for row in H.load_hosts().values():
        # ~/.claude/skills is also the auto-detect default, so only flag rows that
        # are NOT that path; the mapping's job is the other eleven.
        if row["dest"] == "$HOME/.claude/skills":
            continue
        assert row["dest"] not in branch, (
            f"install.sh's --host branch hardcodes {row['dest']} — #143 removed that copy")


@pytest.mark.parametrize("alias", sorted(a for r in H.load_hosts().values() for a in r["aliases"]))
def test_every_alias_resolves_through_the_cli_install_sh_calls(alias, tmp_path):
    """Per alias, the exact command install.sh shells must print the row's dest.

    install.sh runs `python3 -m cap_evolve.hosts --dest $HOST` with the repo's core on
    PYTHONPATH (it runs before anything is pip-installed), so this subprocess is the
    installer's real resolution path — including that it works from an unrelated cwd.
    """
    out = subprocess.run(
        [sys.executable, "-m", "cap_evolve.hosts", "--dest", alias],
        capture_output=True, text=True, cwd=str(tmp_path),
        env={**os.environ, "PYTHONPATH": str(REPO / "core"),
             "CAPEVOLVE_HOSTS_FILE": str(REPO / "skills" / "_registry" / "hosts.yaml")},
    )
    assert out.returncode == 0, out.stderr
    raw = next(str(r["dest"]) for r in H.load_hosts().values() if alias in r["aliases"])
    # $PWD rows expand against the *subprocess'* cwd, which is tmp_path.
    want = raw.replace("$HOME", os.path.expanduser("~")).replace("$PWD", str(tmp_path))
    assert out.stdout.strip() == want, f"--dest {alias} -> {out.stdout.strip()}, want {want}"


def test_host_support_md_destination_table_matches_hosts_yaml():
    """The docs table and hosts.yaml cannot disagree — same aliases, dests, grades."""
    doc = _support_dest_rows()
    yml = {str(r["dest"]): (list(r["aliases"]), str(r["status"])) for r in H.load_hosts().values()}
    assert set(doc) == set(yml), (
        "HOST_SUPPORT.md destination table and hosts.yaml disagree on destinations.\n"
        f"  only in docs:      {sorted(set(doc) - set(yml))}\n"
        f"  only in hosts.yaml:{sorted(set(yml) - set(doc))}")
    for dest, (aliases, status) in yml.items():
        d_aliases, d_status = doc[dest]
        assert d_status == status, f"{dest}: docs say {d_status}, hosts.yaml says {status}"
        assert d_aliases == aliases, f"{dest}: docs aliases {d_aliases} != hosts.yaml {aliases}"


def test_doctor_known_host_dirs_come_from_hosts_yaml():
    """doctor's host-dir list is derived, not a sixth hand-maintained copy."""
    from cap_evolve import doctor
    assert not hasattr(doctor, "_VERIFIED_HOST_DIRS"), \
        "the hand-maintained tuple is back — derive from cap_evolve.hosts instead"
    known = doctor._known_host_dirs()
    for row in H.load_hosts().values():
        tail = str(row["dest"]).replace("$HOME", "", 1).replace("$PWD", "", 1).rstrip("/")
        assert tail in known, f"doctor does not know {row['dest']}"
    # These are matched with str.endswith, so an expanded absolute path would make the
    # check depend on this machine's $HOME/cwd (a $PWD row used to leak the cwd in).
    for k in known:
        assert str(Path.home()) not in k and os.getcwd() not in k, \
            f"doctor's known-dir {k!r} bakes in this machine's $HOME/cwd"


def test_installer_copies_hosts_yaml_so_an_installed_tree_has_the_metadata():
    """Same bug class as #193: a plain file under skills/ that the copy loop skips."""
    txt = INSTALL_SH.read_text(encoding="utf-8")
    assert '_registry/hosts.yaml' in txt, "install.sh does not install hosts.yaml"


def test_cli_reports_dest_and_json(capsys):
    assert H.main(["--dest", "claude"]) == 0
    assert capsys.readouterr().out.strip() == H.dest_for("claude")
    assert H.main(["--dest", "no-such-host"]) == 1
    assert capsys.readouterr().out.strip() == ""
    assert H.main(["--json"]) == 0
    assert "claude-code" in capsys.readouterr().out
