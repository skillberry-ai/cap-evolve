"""The entitlement check must compare WIRE model ids, not the CI-facing provider aliases.

WHAT BROKE

#536 renamed the dispatch ids to `ibm-ete-int/…`, `ibm-ete/…`, `ibm-rits/…` and added
`resolve_provider.sh` to rewrite each alias into the id the provider actually answers to. The
completion probe uses that rewrite. The **entitlement check does not** — `ci_setup.sh` passes
`PF_AGENT` / `PF_OPTIMIZER` (the aliases) straight into `check_models.py`, which compares them
against the gateway's `GET /models` list. That list uses wire ids, so every `ibm-ete*` model
mismatches and preflight aborts:

    ##[group]Entitlement check — ibm-ete-int
    ##[error] optimizer model 'ibm-ete-int/aws/claude-opus-5' is NOT served by this gateway
    ##[error] (prefix mismatch). the gateway spells it 'aws/claude-opus-5'?

Run 36300445911 died there. The default optimizer is `ibm-ete-int/claude-opus-4-8`, so a
dispatch with no inputs at all fails the same way — every benchmark run with a gateway agent or
optimizer was blocked, which is every combination except an all-RITS one.

THE FIX AND WHY IT IS A SEPARATE FUNCTION

`resolve_provider` couples the rewrite to a secrets check (`: "${IBM_…:?}"`), so it cannot be
called just to learn a wire id. `wire_model` does the rewrite ALONE — no secrets, no side
effects — and `resolve_provider` delegates to it, so the two can never disagree about what goes
on the wire. That single-source property is what the parity test below pins.
"""

import json
import re
import subprocess
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
LIB = REPO / "ci" / "benchmarks" / "lib"
RESOLVE = LIB / "resolve_provider.sh"
CI_SETUP = LIB / "ci_setup.sh"
CHECK_MODELS = LIB / "check_models.py"

# (dispatch alias, id the provider actually answers to)
CASES = [
    ("ibm-ete-int/aws/claude-opus-5", "aws/claude-opus-5"),
    ("ibm-ete-int/claude-opus-4-8", "claude-opus-4-8"),
    ("ibm-ete/aws/gpt-oss-120b", "aws/gpt-oss-120b"),
    # RITS keeps a `rits/` wire prefix: lite-rits's own hook only fires when it is present.
    ("ibm-rits/google/gemma-4-31B-it", "rits/google/gemma-4-31B-it"),
]


def _sh(script: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", "-c", script], capture_output=True, text=True,
                          env={"PATH": "/usr/bin:/bin", **(env or {})})


# --- the pure rewrite ----------------------------------------------------------------------


@pytest.mark.parametrize("alias,wire", CASES)
def test_wire_model_rewrites_the_alias(alias, wire):
    p = _sh(f'. {RESOLVE}\nwire_model "{alias}"\n')
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip() == wire


@pytest.mark.parametrize("alias,wire", CASES)
def test_wire_model_needs_no_secrets(alias, wire):
    """It must be callable purely to learn a wire id. `resolve_provider` aborts without the
    provider's credentials, which is why the entitlement path cannot use it."""
    p = _sh(f'. {RESOLVE}\nwire_model "{alias}"\n')  # env deliberately has no IBM_* vars
    assert p.returncode == 0, f"wire_model required credentials: {p.stderr}"
    assert p.stdout.strip() == wire


def test_wire_model_rejects_an_unprefixed_id():
    p = _sh(f'. {RESOLVE}\nwire_model "aws/claude-opus-5"\n')
    assert p.returncode != 0, "an id with no provider prefix must be refused, not passed through"


@pytest.mark.parametrize("alias,wire", CASES)
def test_resolve_provider_agrees_with_wire_model(alias, wire):
    """Single source of truth: if these ever disagree, the probe and the entitlement check are
    testing different models again."""
    env = {f"IBM_{p}_API_{k}": "x" for p in ("ETE_INT", "ETE", "RITS") for k in ("BASE", "KEY")}
    p = _sh(f'. {RESOLVE}\nresolve_provider "{alias}"\nprintf "%s" "$RESOLVED_MODEL"\n', env)
    assert p.returncode == 0, p.stderr
    assert p.stdout.strip() == wire


# --- the regression: what the entitlement check is actually asked to verify -----------------


def _require_specs(agent: str, optimizer: str) -> list[str]:
    """Run ci_setup's real `check_listed` for each gateway-routed role, capturing the
    `--require ROLE=MODEL` spec it hands to check_models.py.

    `check_listed` is lifted verbatim out of ci_setup.sh. `curl` is stubbed to answer the
    /models call with 200, and CAPEVOLVE_PY is a stub that records its `--require` value
    instead of running the real checker. RITS candidates are not passed to check_listed by
    select_provider at all; see test_rits_is_still_never_entitlement_listed.
    """
    src = CI_SETUP.read_text(encoding="utf-8")
    m = re.search(r"^  check_listed\(\) \{.*?^  \}$", src, re.S | re.M)
    assert m, "check_listed() not found in ci_setup.sh"
    script = textwrap.dedent(f"""
        set -uo pipefail
        . {RESOLVE}
        IBM_ETE_INT_API_BASE=x; IBM_ETE_INT_API_KEY=x
        IBM_ETE_API_BASE=x;     IBM_ETE_API_KEY=x
        IBM_RITS_API_BASE=x;    IBM_RITS_API_KEY=x
        LIB_DIR=/nonexistent
        curl() {{ printf 200; }}
        fakepy() {{ echo "$4" >&3; }}
        CAPEVOLVE_PY=fakepy
    """) + m.group(0) + textwrap.dedent(f"""
        for pair in "agent {agent}" "optimizer {optimizer}"; do
          set -- $pair
          p="$(provider_of "$2")"
          [ "$p" = ibm-rits ] && continue
          check_listed "$1" "$p" "$2" 1 >/dev/null
        done 3>&1
    """)
    p = _sh(script)
    assert p.returncode == 0, f"assembly failed: {p.stderr}"
    return [l for l in p.stdout.splitlines() if "=" in l]


def test_the_entitlement_check_receives_wire_ids_not_aliases():
    """The bug, directly: the gateway's /models list uses wire ids, so an alias always misses."""
    specs = _require_specs("ibm-ete-int/aws/gpt-oss-120b", "ibm-ete-int/aws/claude-opus-5")
    assert "optimizer=aws/claude-opus-5" in specs, (
        f"entitlement check is still asked to verify a prefixed alias: {specs}"
    )
    assert "agent=aws/gpt-oss-120b" in specs, specs
    assert not [s for s in specs if "ibm-ete" in s], f"an alias leaked through: {specs}"


def test_the_default_dispatch_would_pass_its_own_entitlement_check():
    """The default optimizer is a plain catalog name; every provider it can fall back to is
    checked with that provider's wire id, never with the CI alias."""
    src = CI_SETUP.read_text(encoding="utf-8")
    default = re.search(r'PF_OPTIMIZER="\$\{OPTIMIZER_MODEL:-([^}"]+)\}"', src).group(1)
    cands = _sh(f'. {RESOLVE}\ncatalog_candidates "{default}"\n')
    assert cands.returncode == 0, f"default {default!r} is not in model_catalog.txt: {cands.stderr}"
    candidates = cands.stdout.split()
    assert candidates and all(c.startswith("ibm-") for c in candidates), candidates
    for c in candidates:
        specs = _require_specs("ibm-ete-int/aws/gpt-oss-120b", c)
        assert not [s for s in specs if s.startswith("optimizer=ibm-")], (
            f"the default optimizer is still checked as an alias: {specs}"
        )


def test_a_wire_id_actually_satisfies_check_models(tmp_path):
    """End to end against the real checker: the wire id is what the gateway list contains."""
    models = tmp_path / "models.json"
    models.write_text(json.dumps({"data": [{"id": "aws/claude-opus-5"}, {"id": "aws/gpt-oss-120b"}]}),
                      encoding="utf-8")
    ok = subprocess.run(["python3", str(CHECK_MODELS), str(models),
                         "--require", "optimizer=aws/claude-opus-5"], capture_output=True, text=True)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    bad = subprocess.run(["python3", str(CHECK_MODELS), str(models),
                          "--require", "optimizer=ibm-ete-int/aws/claude-opus-5"],
                         capture_output=True, text=True)
    assert bad.returncode != 0, "the alias should NOT satisfy the gateway list — that is the bug"


def test_rits_is_still_never_entitlement_listed():
    """lite-rits's /v1/models is empty by design; listing it would abort every RITS run."""
    src = CI_SETUP.read_text(encoding="utf-8")
    # select_provider only calls check_listed for a non-RITS candidate, and check_listed itself
    # returns early for any provider that is not an ete gateway.
    assert re.search(r'\[ "\$provider" != "ibm-rits" \][^\n]*\\\n\s*&& ! check_listed', src), (
        "select_provider no longer skips the entitlement listing for RITS"
    )
    body = re.search(r"^  check_listed\(\) \{.*?^  \}$", src, re.S | re.M).group(0)
    assert re.search(r"\*\)\s*return 0\s*;;", body), "check_listed no longer returns early for RITS"


def test_shell_libs_stay_valid():
    for p in (RESOLVE, CI_SETUP):
        assert subprocess.run(["bash", "-n", str(p)]).returncode == 0
