"""The install/run path must work with NO third-party module importable (#143).

cap-evolve claims a stdlib-only fallback so the suite degrades gracefully on a host
that provides no native tooling — and `install.sh` depends on it literally, since it
shells `python3 -m cap_evolve.hosts` *before* `pip install ./core` has happened.

Proving that by reading the source is worthless: an `import yaml` that only runs on the
PyYAML-present path looks fine and breaks on a bare host. So these tests run the real
path in a **subprocess whose `sys.meta_path` raises ImportError for every module that
is not in `sys.stdlib_module_names`**. If anything on this path grows a third-party
dependency, the test fails here instead of on a user's bare machine.

Covered under blocked imports:
  * `cap_evolve.hosts` — per-host metadata + `--dest`, i.e. what install.sh calls
  * `cap_evolve.specfile.read_yaml` on the real `optimizers/registry.yaml`
  * `skills/_registry/build_manifest.py` — the manifest install.sh rebuilds
  * `cap-evolve version` / `check` — the CLI entry points
"""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "core"

# Installed as sys.meta_path[0] in the child: refuse every non-stdlib top-level module
# except cap_evolve itself (the package under test) and pytest-free plain scripts.
_BLOCKER = '''
import sys
_ALLOW = {"cap_evolve", "_bootstrap", "__main__", "build_manifest"}
class _Block:
    def find_module(self, name, path=None):
        top = name.split(".")[0]
        if top in _ALLOW or top in sys.stdlib_module_names or top in sys.builtin_module_names:
            return None
        return self
    def load_module(self, name):
        raise ImportError(f"third-party import blocked by test_stdlib_only: {name}")
    # PEP 451 path, which is the one CPython actually uses.
    def find_spec(self, name, path=None, target=None):
        top = name.split(".")[0]
        if top in _ALLOW or top in sys.stdlib_module_names or top in sys.builtin_module_names:
            return None
        raise ImportError(f"third-party import blocked by test_stdlib_only: {name}")
sys.meta_path.insert(0, _Block())
'''


def _run_blocked(body: str, *, argv: list[str] | None = None) -> subprocess.CompletedProcess:
    """Execute ``body`` in a child where non-stdlib imports raise ImportError."""
    return subprocess.run(
        [sys.executable, "-c", _BLOCKER + body] + (argv or []),
        capture_output=True, text=True, cwd=str(REPO),
        env={"PYTHONPATH": str(CORE), "PATH": "/usr/bin:/bin", "HOME": str(Path.home()),
             "CAPEVOLVE_HOSTS_FILE": str(REPO / "skills" / "_registry" / "hosts.yaml")},
    )


def test_the_blocker_actually_blocks():
    """Guard the guard: if the hook were a no-op every test below would vacuously pass."""
    out = _run_blocked("import yaml; print('NOT BLOCKED')")
    assert out.returncode != 0, f"the import blocker did not fire: {out.stdout}"
    assert "blocked by test_stdlib_only" in out.stderr


def test_hosts_metadata_resolves_with_no_third_party_modules():
    """What install.sh shells, with PyYAML unavailable."""
    out = _run_blocked(
        "from cap_evolve import hosts\n"
        "rows = hosts.load_hosts()\n"
        "assert rows, 'no host rows'\n"
        "import json; print(json.dumps({'n': len(rows), 'claude': hosts.dest_for('claude'),"
        " 'status': hosts.status_for('claude'), 'display': rows['claude-code']['display'],"
        " 'dests': len(hosts.verified_dests())}))\n")
    assert out.returncode == 0, out.stderr
    got = json.loads(out.stdout)
    assert got["n"] >= 12 and got["dests"] == got["n"]
    assert got["claude"].endswith("/.claude/skills")
    assert got["status"] == "verified" and got["display"]


def test_hosts_cli_dest_works_with_no_third_party_modules():
    """`python3 -m cap_evolve.hosts --dest claude` — the literal install.sh call."""
    out = subprocess.run(
        [sys.executable, "-c", _BLOCKER + "from cap_evolve.hosts import main; raise SystemExit(main())",
         "--dest", "codex"],
        capture_output=True, text=True, cwd=str(REPO),
        env={"PYTHONPATH": str(CORE), "PATH": "/usr/bin:/bin", "HOME": str(Path.home()),
             "CAPEVOLVE_HOSTS_FILE": str(REPO / "skills" / "_registry" / "hosts.yaml")},
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip().endswith("/.agents/skills")


def test_optimizer_registry_parses_with_no_third_party_modules():
    """read_yaml's fallback must handle the real registry, not just a toy doc."""
    out = _run_blocked(
        "from pathlib import Path\n"
        "from cap_evolve.specfile import read_yaml\n"
        f"reg = read_yaml(Path({str(REPO / 'skills' / 'optimizers' / 'registry.yaml')!r}).read_text())\n"
        "assert 'mock' in reg and 'claude-code' in reg, sorted(reg)\n"
        "assert '_mock_apply.py' in reg['mock']['command_template']\n"
        "import json; print(json.dumps({'rows': len(reg)}))\n")
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout)["rows"] >= 12


def test_manifest_build_works_with_no_third_party_modules(tmp_path):
    """install.sh rebuilds the manifest on every run; it must not need PyYAML."""
    out = _run_blocked(
        "import runpy, sys\n"
        f"sys.argv = ['build_manifest.py', {str(REPO / 'skills')!r}]\n"
        f"runpy.run_path({str(REPO / 'skills' / '_registry' / 'build_manifest.py')!r},"
        " run_name='__main__')\n")
    assert out.returncode == 0, out.stderr + out.stdout
    manifest = json.loads((REPO / "skills" / "_registry" / "manifest.json").read_text())
    assert manifest["errors"] == [] and len(manifest["skills"]) >= 12


def test_cli_version_and_check_work_with_no_third_party_modules():
    out = _run_blocked("from cap_evolve.cli import main; raise SystemExit(main(['version']))")
    assert out.returncode == 0, out.stderr
    assert "cap-evolve" in json.loads(out.stdout)

    # `check` on a nonexistent project must report, not traceback.
    out = _run_blocked(
        "from cap_evolve.cli import main; main(['check', '/nonexistent-project-xyz'])")
    assert "traceback" not in out.stderr.lower(), out.stderr
    assert out.stdout.strip().startswith("{")
