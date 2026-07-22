from cap_evolve import target_profile as tp


def test_blank_is_agnostic():
    p = tp.resolve("")
    assert p.is_agnostic
    assert p.tier == "" and p.brief == "" and p.suggested_num_trials == 0
    assert tp.reader_block(p) == ""


def test_tier_keyword_passthrough():
    p = tp.resolve("weak")
    assert p.tier == "weak"
    assert "explicit" in p.brief.lower()
    assert p.suggested_num_trials == tp.TIERS["weak"]["suggested_num_trials"]
    assert p.resolution_note == ""


def test_known_model_maps_to_tier():
    p = tp.resolve("gpt-oss-120b")
    assert p.tier == "mid"
    assert p.model == "gpt-oss-120b"


def test_known_model_case_insensitive():
    assert tp.resolve("GPT-OSS-120B").tier == "mid"


def test_unknown_model_defaults_to_strong_with_note():
    p = tp.resolve("some-local-llm-7b")
    assert p.tier == "strong"
    assert "unknown model id" in p.resolution_note.lower()
    assert not p.is_agnostic


def test_profile_file_overrides_brief(tmp_path):
    f = tmp_path / "brief.md"
    f.write_text("Custom reader: assume it forgets tool schemas.", encoding="utf-8")
    p = tp.resolve("mid", target_profile_file=str(f))
    assert p.brief == "Custom reader: assume it forgets tool schemas."
    assert p.tier == "mid"  # tier still resolved; only the brief text is overridden


def test_profile_file_resolved_project_relative(tmp_path):
    (tmp_path / "brief.md").write_text("Project brief.", encoding="utf-8")
    p = tp.resolve("mid", target_profile_file="brief.md", project_dir=str(tmp_path))
    assert p.brief == "Project brief."


def test_reader_block_names_model_and_tier():
    block = tp.reader_block(tp.resolve("gpt-oss-120b"))
    assert "gpt-oss-120b" in block and "mid" in block
    assert "THE READER" in block
