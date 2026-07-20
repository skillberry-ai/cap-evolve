from pathlib import Path
from cap_evolve import check


def _write_project(tmp_path, target_model, runner_model):
    proj = tmp_path / ".capevolve" / "project"
    (proj / "adapters").mkdir(parents=True)
    (proj / "capevolve.yaml").write_text(
        f"capabilities: [system-prompt]\ntarget_model: {target_model}\n", encoding="utf-8")
    (proj / "adapters" / "adapter.py").write_text(
        "from cap_evolve.adapter import CapabilityAdapter\n"
        "class Adapter(CapabilityAdapter):\n"
        "    def tasks(self, split): return []\n"
        "    def run_target(self, task, ctx, *, seed=0): return None\n"
        "    def score(self, task, rollout): return None\n"
        f"    def runner_model(self): return {runner_model!r}\n",
        encoding="utf-8")
    return proj


def test_mismatch_adds_note(tmp_path):
    proj = _write_project(tmp_path, "frontier", "gpt-oss-20b")  # frontier vs weak
    rep = check.run_check(proj)
    assert any("consum" in n.lower() or "runner" in n.lower() for n in rep.notes)


def test_match_no_note(tmp_path):
    proj = _write_project(tmp_path, "gpt-oss-120b", "gpt-oss-120b")  # both mid
    rep = check.run_check(proj)
    assert not any("runner" in n.lower() and "tier" in n.lower() for n in rep.notes)


def test_no_declaration_no_note(tmp_path):
    proj = _write_project(tmp_path, "", "gpt-oss-20b")  # agnostic → no cross-check
    rep = check.run_check(proj)
    assert not any("runner" in n.lower() and "tier" in n.lower() for n in rep.notes)
