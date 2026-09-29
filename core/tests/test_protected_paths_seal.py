"""The protected-path seal must reach the algorithm, or say loudly that it cannot.

`protected_paths` is how a spec keeps a candidate away from the part of the seed that makes the
measurement comparable — a benchmark's own policy (the text the agent is GRADED against), or a
frozen substrate. Editing a sealed path makes a candidate INDECISIVE rather than scored 0.0.

The failure this file exists to prevent: `cli.py` forwards the seal as `--protected-paths` only to
the algorithms whose entry script accepts it. Agent mode's host has no such flag, so a spec that
declares a seal under agent mode used to have it SILENTLY DROPPED — leaving a spec that READS
sealed while nothing enforced it. That is worse than an unsealed spec, because a reviewer trusts
the declaration.
"""

import re
from pathlib import Path

import pytest

from cap_evolve import cli

REPO = Path(__file__).resolve().parents[2]
CLI_SRC = (REPO / "core" / "cap_evolve" / "cli.py").read_text(encoding="utf-8")


# --- the forwarding rule ----------------------------------------------------------------

def test_the_supported_algorithms_are_named_not_inlined():
    """A literal tuple at the use site drifts from the warning that names it."""
    assert cli.PROTECTED_PATHS_ALGORITHMS
    assert "PROTECTED_PATHS_ALGORITHMS" in CLI_SRC


def test_agent_mode_is_deliberately_excluded():
    """Its host.py has no --protected-paths, so the seal cannot be enforced there. If that ever
    changes, this test should fail and be updated together with the warning."""
    assert "agent-optimize" not in cli.PROTECTED_PATHS_ALGORITHMS
    host = REPO / "skills" / "algorithms" / "agent-optimize" / "scripts" / "host.py"
    if host.exists():
        assert "--protected-paths" not in host.read_text(encoding="utf-8"), \
            "agent mode now accepts a seal — add it to PROTECTED_PATHS_ALGORITHMS"


@pytest.mark.parametrize("alg", ["hill-climb", "skillopt", "gepa"])
def test_every_supported_algorithm_accepts_the_flag(alg):
    """The tuple is only true if each named algorithm's entry script really takes the flag."""
    assert alg in cli.PROTECTED_PATHS_ALGORITHMS
    run_py = REPO / "skills" / "algorithms" / alg / "scripts" / "run.py"
    assert run_py.exists(), run_py
    assert "--protected-paths" in run_py.read_text(encoding="utf-8")


# --- the silent-drop fix ----------------------------------------------------------------

def _seal_block() -> str:
    """The source of the seal-forwarding block, so the branch structure is assertable.

    Fails with a DIAGNOSIS rather than a raw ValueError when the anchors move: the block being
    unfindable is itself the finding, and a stack trace from `str.index` tells the next reader
    nothing about what to look for.
    """
    start = 'pp = spec.get("protected_paths")'
    end = 'if spec.get("convergence"):'
    i = CLI_SRC.find(start)
    assert i != -1, (
        f"cannot find {start!r} in cli.py at module scope. Either the seal block moved, or the "
        "read is back inside an `if algorithm_name in (...)` guard — which is the silent-drop "
        "bug this file exists to prevent.")
    j = CLI_SRC.find(end, i)
    assert j != -1, f"cannot find {end!r} after the seal block; the file has been restructured"
    return CLI_SRC[i:j]


def test_an_unsupported_algorithm_is_warned_about_not_silently_ignored():
    block = _seal_block()
    assert "else:" in block, "a seal that cannot be forwarded must take a branch, not vanish"
    assert "warn:" in block and "protected_paths" in block
    assert "file=sys.stderr" in block, "human chrome goes to stderr; stdout is the JSON contract"


def test_the_warning_states_the_consequence_not_just_the_fact():
    """'Ignoring it' is not enough — the reader needs to know the paths are editable."""
    block = _seal_block()
    assert re.search(r"NOTHING IS SEALED", block), \
        "the warning must say what it costs, so it cannot be read as cosmetic"


def test_the_seal_is_evaluated_for_every_algorithm_not_only_the_supported_ones():
    """The bug was the guard: `if algorithm_name in (...)` wrapped the whole read, so an
    unsupported algorithm never even looked at the key and could not warn."""
    block = _seal_block()
    first_line = block.splitlines()[0]
    assert first_line.lstrip().startswith("pp = spec.get"), first_line
    # the algorithm check must come AFTER the key is read, not around it
    assert block.index("PROTECTED_PATHS_ALGORITHMS") > block.index('spec.get("protected_paths")')


def test_absent_or_empty_seal_adds_no_flag_and_no_warning():
    """OPT-IN: the surrounding comment promises an existing spec runs byte-identically."""
    block = _seal_block()
    assert 'or []' in block, "a missing or null key must normalize to empty"
    assert "if pp:" in block, "an empty seal must not warn and must not add a flag"


def test_a_comma_string_is_accepted_as_well_as_a_list():
    """The zero-dependency spec reader can hand back either shape."""
    block = _seal_block()
    assert "isinstance(pp, str)" in block
    assert 'pp.split(",")' in block


# --- reading a spec without PyYAML ------------------------------------------------------
# `core` ships with ZERO runtime dependencies (docs/INSTALL.md), and its CI installs exactly that,
# so `import yaml` here failed the suite. Skipping instead would quietly stop asserting the very
# specs this PR changes, so parse the handful of FLAT top-level keys these tests need. Adequate
# because every key read below is a top-level scalar or an inline list; `test_the_flat_reader_agrees
# _with_pyyaml` cross-checks it wherever PyYAML happens to be installed.

def _strip_comment(v: str) -> str:
    out, quote = [], None
    for ch in v:
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#":
            break
        out.append(ch)
    return "".join(out).strip()


def _spec(path: Path) -> dict:
    """Top-level keys of a flat spec: scalars and inline `[a, b]` lists."""
    d: dict = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line[0].isspace() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, _, raw = line.partition(":")
        if not key or key != key.strip():
            continue
        val = _strip_comment(raw)
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            d[key] = [i.strip().strip("\"'") for i in inner.split(",") if i.strip()] if inner else []
        else:
            d[key] = val.strip("\"'")
    return d


# --- the specs that rely on it ----------------------------------------------------------

def _specs():
    return sorted((REPO / "examples" / "tau2_airline").rglob("capevolve*.yaml"))


def test_the_tau2_specs_exist_and_all_declare_a_seal():
    specs = _specs()
    assert specs, "no tau2_airline specs found"
    for p in specs:
        d = _spec(p)
        assert d.get("protected_paths"), f"{p.name} declares no seal"


def test_the_direct_specs_seal_the_policy_and_the_proxy_spec_seals_its_substrate():
    """Different arms protect different things, and each is the part that would void the
    measurement: the policy is the benchmark's exam, the primitives are the bridge that makes
    rollouts comparable."""
    for p in _specs():
        d = _spec(p)
        sealed = d["protected_paths"]
        if d.get("intervention") == "blackbox":
            assert "primitive_tools/*" in sealed and "my_skill/SKILL.md" in sealed, p
        else:
            assert "policy/*" in sealed, p


def test_no_tau2_spec_still_declares_the_system_prompt_capability():
    """The policy is sealed precisely because it is NOT the capability; declaring
    `system-prompt` alongside the seal would be self-contradictory."""
    for p in _specs():
        caps = _spec(p).get("capabilities") or []
        assert "system-prompt" not in caps, p


def test_an_agent_mode_spec_declaring_a_seal_will_now_be_warned_about():
    """Three tau2 specs are agent-mode AND declare a seal. That combination is exactly the
    silent-drop case, so it must be the warned case — this test ties the specs to the fix."""
    agent_specs = [p for p in _specs()
                   if _spec(p).get("orchestration_mode") == "agent"]
    if not agent_specs:
        pytest.skip("no agent-mode spec in this example any more")
    for p in agent_specs:
        d = _spec(p)
        assert d.get("protected_paths"), p
        assert d.get("algorithm_skill") not in cli.PROTECTED_PATHS_ALGORITHMS, (
            f"{p.name} is agent mode; if its algorithm now supports the seal, update the tuple")


def test_the_flat_reader_agrees_with_pyyaml():
    """The reader above replaced PyYAML because `core` has no runtime deps. Where PyYAML IS
    installed, prove the substitution did not change what these tests read."""
    yaml = pytest.importorskip("yaml", reason="core has no runtime deps; CI runs without PyYAML")
    keys = ("protected_paths", "intervention", "capabilities",
            "orchestration_mode", "algorithm_skill")
    for p in _specs():
        real = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        mine = _spec(p)
        for k in keys:
            assert mine.get(k) == real.get(k), f"{p.name}:{k} — {mine.get(k)!r} != {real.get(k)!r}"
