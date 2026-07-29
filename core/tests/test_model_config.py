"""Provider-scoped credential resolution + `auto` probing (issue #134).

Security-critical tests, in order of importance:
  * a fake credential value NEVER appears in any output/artifact/exception text;
  * a provider-scoped credential is NEVER sent to another provider's endpoint;
  * precedence is CLI > project > user > built-in;
  * `auto` picks the usable provider; nothing-resolves gives an actionable error;
  * existing single-provider specs behave exactly as before (back-compat guard).
"""

from __future__ import annotations

import io
import json
import contextlib
import subprocess
import sys
from pathlib import Path

import pytest

from cap_evolve import model_config as mc

FAKE = "sk-FAKETOKEN0123456789abcdefFAKE"      # must never be echoed anywhere


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """No inherited real credentials, and no user config, unless a test adds one."""
    for row in mc.PROVIDERS.values():
        for name in row["env"]:
            monkeypatch.delenv(name, raising=False)
        if row["base_url_env"]:
            monkeypatch.delenv(row["base_url_env"], raising=False)
    monkeypatch.setenv("CAPEVOLVE_CONFIG", "/nonexistent/capevolve-config.yaml")


# ---------------------------------------------------------------------------
# 1. Provider scoping: never cross the boundary
# ---------------------------------------------------------------------------

def test_provider_b_selected_with_only_provider_a_key_errors(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE)
    with pytest.raises(mc.CredentialError) as ei:
        mc.resolve(project={"provider": "openai"})
    msg = str(ei.value)
    assert FAKE not in msg
    assert "OPENAI_API_KEY" in msg                 # says what to set
    assert "anthropic" in msg                      # and that the other one won't be reused
    assert "never reused" in msg


def test_explicit_cross_provider_credential_env_is_refused(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE)
    with pytest.raises(mc.CredentialError) as ei:
        mc.resolve(cli={"provider": "openai", "credential_env": "ANTHROPIC_API_KEY"})
    assert "belongs to provider 'anthropic'" in str(ei.value)
    assert FAKE not in str(ei.value)


def test_scoped_lookup_only_reads_own_row(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", FAKE)
    assert mc._scoped_credential_env("openai") == "OPENAI_API_KEY"
    assert mc._scoped_credential_env("anthropic") == ""      # blind to another row's var


def test_probe_never_sends_credential_to_another_providers_endpoint(monkeypatch):
    """The wrong-endpoint guarantee, asserted at the wire level.

    Only ANTHROPIC_API_KEY is set. We capture every urlopen the probe attempts and
    assert: the anthropic probe sends the token to an anthropic URL only, and the
    openai/gemini probes make NO request at all (no credential of their own).
    """
    sent: list[tuple[str, dict]] = []

    class _Resp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=None):
        sent.append((req.full_url, dict(req.headers)))
        return _Resp()

    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    ok, _ = mc.probe("anthropic")
    assert ok
    assert len(sent) == 1
    url, headers = sent[0]
    assert url.startswith("https://api.anthropic.com")
    assert FAKE in json.dumps(headers)          # it went out, to its OWN endpoint

    for other in ("openai", "gemini", "rits", "watsonx"):
        ok, why = mc.probe(other)
        assert ok is False
        assert "no %s credential" % other in why
    assert len(sent) == 1, "a probe made a request without its own credential"
    # And no request ever reached a non-anthropic host with the anthropic token.
    for url, headers in sent:
        assert "api.anthropic.com" in url or FAKE not in json.dumps(headers)


def test_auto_probe_does_not_leak_credential_across_candidates(monkeypatch):
    """`auto` + probe with only an OpenAI key: openai's URL is the only one touched."""
    hosts: list[str] = []

    class _Resp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, timeout=None):
        hosts.append(req.full_url)
        assert FAKE in json.dumps(dict(req.headers))
        assert "api.openai.com" in req.full_url, "token sent to a foreign host!"
        return _Resp()

    monkeypatch.setenv("OPENAI_API_KEY", FAKE)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    res = mc.resolve(project={"provider": "auto"}, probe_fn=mc.probe)
    assert res.provider == "openai"
    assert all("api.openai.com" in h for h in hosts)


# ---------------------------------------------------------------------------
# 2. No-leak: the fake token appears nowhere
# ---------------------------------------------------------------------------

def _all_text(res: mc.Resolved) -> str:
    return " ".join([repr(res), str(res), json.dumps(res.to_dict()), mc.describe(res)])


def test_resolved_object_carries_no_credential_value(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE)
    res = mc.resolve(project={"provider": "anthropic"})
    assert res.credential_env == "ANTHROPIC_API_KEY"
    assert res.credential_present is True
    assert FAKE not in _all_text(res)


def test_probe_failure_reason_is_scrubbed(monkeypatch):
    """A library exception echoing a credential-bearing URL must not leak it."""
    import urllib.error

    def boom(req, timeout=None):
        raise urllib.error.URLError(
            f"failed connecting to https://x.invalid/v1/models?api_key={FAKE}")

    monkeypatch.setenv("GEMINI_API_KEY", FAKE)
    monkeypatch.setattr("urllib.request.urlopen", boom)
    ok, why = mc.probe("gemini")
    assert ok is False
    assert FAKE not in why
    assert "redacted" in why


def test_cli_run_transcript_never_prints_credential(monkeypatch, tmp_path):
    """Whole `cap-evolve run` provider step: stdout+stderr contain no token."""
    spec = tmp_path / "capevolve.yaml"
    spec.write_text("capabilities: [system-prompt]\nprovider: openai\n"
                    "optimizer_skill: mock\nalgorithm_skill: hill-climb\n", encoding="utf-8")
    env = dict(**{k: v for k, v in __import__("os").environ.items()})
    env.update({"ANTHROPIC_API_KEY": FAKE, "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
                "CAPEVOLVE_CONFIG": "/nonexistent/capevolve-config.yaml"})
    env.pop("OPENAI_API_KEY", None)
    proc = subprocess.run(
        [sys.executable, "-m", "cap_evolve.cli", "run", "--spec", str(spec),
         "--project", str(tmp_path)],
        capture_output=True, text=True, env=env, cwd=str(tmp_path))
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 1                       # failed on the cross-provider case
    assert "OPENAI_API_KEY" in combined               # actionable
    assert FAKE not in combined                       # and leak-free
    assert "FAKETOKEN" not in combined                # not even a fragment


def test_no_leak_on_the_nothing_resolves_path(capsys):
    with pytest.raises(mc.CredentialError) as ei:
        mc.resolve(project={"provider": "auto"})
    out = capsys.readouterr()
    assert FAKE not in (str(ei.value) + out.out + out.err)


# ---------------------------------------------------------------------------
# 3. Precedence
# ---------------------------------------------------------------------------

def test_precedence_cli_over_project_over_user(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE)
    monkeypatch.setenv("OPENAI_API_KEY", FAKE)
    monkeypatch.setenv("GEMINI_API_KEY", FAKE)
    user = {"provider": "gemini"}
    project = {"provider": "openai"}
    cli = {"provider": "anthropic"}

    assert mc.resolve(user=user).provider == "gemini"
    assert mc.resolve(project=project, user=user).provider == "openai"
    got = mc.resolve(cli=cli, project=project, user=user)
    assert got.provider == "anthropic"
    assert got.sources["provider"] == "CLI flag"


def test_empty_layer_does_not_shadow_lower_layer(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", FAKE)
    res = mc.resolve(cli={"provider": ""}, project={"provider": ""},
                     user={"provider": "openai"})
    assert res.provider == "openai"
    assert res.sources["provider"] == "user config"


def test_user_config_file_is_read(monkeypatch, tmp_path):
    cfg = tmp_path / "config.yaml"
    cfg.write_text("provider: openai\n", encoding="utf-8")
    monkeypatch.setenv("CAPEVOLVE_CONFIG", str(cfg))
    monkeypatch.setenv("OPENAI_API_KEY", FAKE)
    assert mc.resolve().provider == "openai"


def test_base_url_precedence(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", FAKE)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://gw.example/v1")
    assert mc.resolve(project={"provider": "openai"}).base_url == "https://gw.example/v1"
    res = mc.resolve(cli={"base_url": "https://cli.example/v1"}, project={"provider": "openai"})
    assert res.base_url == "https://cli.example/v1"
    monkeypatch.delenv("OPENAI_BASE_URL")
    assert mc.resolve(project={"provider": "openai"}).base_url == "https://api.openai.com/v1"


def test_precedence_documented_in_module_and_docs():
    assert mc.PRECEDENCE == ("CLI flag", "project capevolve.yaml", "user config",
                             "built-in default")
    doc = Path(__file__).resolve().parents[2] / "docs" / "INSTALL.md"
    assert "CLI flag > project" in doc.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 4. auto + failure messages
# ---------------------------------------------------------------------------

def test_auto_picks_the_provider_that_has_a_credential(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", FAKE)
    res = mc.resolve(project={"provider": "auto"})
    assert res.provider == "gemini"
    assert "GEMINI_API_KEY is set" in res.reason
    assert FAKE not in res.reason


def test_auto_prefers_the_documented_order(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", FAKE)
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE)
    assert mc.resolve(project={"provider": "auto"}).provider == "anthropic"


def test_auto_skips_a_candidate_whose_probe_fails(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE)
    monkeypatch.setenv("OPENAI_API_KEY", FAKE)
    res = mc.resolve(project={"provider": "auto"},
                     probe_fn=lambda p, u: (p == "openai", "mocked"))
    assert res.provider == "openai"
    assert "Skipped: anthropic (probe failed" in res.reason


def test_auto_skips_provider_needing_a_base_url_it_lacks(monkeypatch):
    monkeypatch.setenv("RITS_API_KEY", FAKE)          # no RITS_API_URL
    with pytest.raises(mc.CredentialError) as ei:
        mc.resolve(project={"provider": "auto"})
    assert "RITS_API_URL unset" in str(ei.value)
    monkeypatch.setenv("RITS_API_URL", "https://rits.example")
    assert mc.resolve(project={"provider": "auto"}).provider == "rits"


def test_nothing_resolves_is_actionable():
    with pytest.raises(mc.CredentialError) as ei:
        mc.resolve(project={"provider": "auto"})
    msg = str(ei.value)
    assert "ANTHROPIC_API_KEY" in msg and "OPENAI_API_KEY" in msg
    assert "CLI flag > project capevolve.yaml > user config > built-in default" in msg


def test_unknown_provider_errors_clearly():
    with pytest.raises(mc.CredentialError) as ei:
        mc.resolve(cli={"provider": "nope"})
    assert "unknown provider 'nope'" in str(ei.value)
    assert "auto" in str(ei.value)


def test_probe_refuses_unknown_provider_before_any_request(monkeypatch):
    def never(*a, **k):
        raise AssertionError("made a request for an unknown provider")
    monkeypatch.setattr("urllib.request.urlopen", never)
    assert mc.probe("nope") == (False, "unknown provider 'nope'")


# ---------------------------------------------------------------------------
# 5. Back-compat: existing single-provider specs unchanged
# ---------------------------------------------------------------------------

def test_existing_spec_without_provider_key_infers_from_optimizer(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE)
    res = mc.resolve(project={"optimizer_skill": "claude-code"})
    assert res.provider == "anthropic"
    assert "from optimizer_skill" in res.sources["provider"]


def test_mock_optimizer_needs_no_credential():
    res = mc.resolve(project={"optimizer_skill": "mock"})
    assert res.provider == "mock"
    assert res.credential_present is False           # and it did not raise


def test_legacy_spec_with_no_provider_and_no_creds_does_not_break():
    """A spec that never mentions a provider must not start failing (regression guard)."""
    res = mc.resolve(project={"optimizer_skill": "hill-climb-ish-unknown"},
                     require_credential=False)
    assert res.provider == ""                        # unresolved, but no exception


def test_toy_calc_style_run_still_resolves(monkeypatch, tmp_path):
    """The zero-API example's spec shape: optimizer_skill: mock, no provider key."""
    spec = tmp_path / "capevolve.yaml"
    spec.write_text("capabilities: [system-prompt]\noptimizer_skill: mock\n", encoding="utf-8")
    from cap_evolve.specfile import read_yaml
    res = mc.resolve(project=read_yaml(spec.read_text()), require_credential=False)
    assert res.provider == "mock" and res.credential_present is False


def test_describe_is_a_single_secret_free_line(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", FAKE)
    line = mc.describe(mc.resolve(project={"provider": "anthropic"}))
    assert "\n" not in line
    assert "ANTHROPIC_API_KEY (present)" in line
    assert FAKE not in line
