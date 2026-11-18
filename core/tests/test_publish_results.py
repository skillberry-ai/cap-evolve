"""Each benchmark leg publishes its own results to skillberry-runs (`publish_results.sh`).

WHY THIS EXISTS

Until 2026-11-18 a bench job uploaded an artifact and a GitHub-hosted `aggregate` job turned it
into a dashboard record and the run's "Open UI" data. After IBM's network change the
self-hosted runners still reach github.com (each connection ~8 s slower), but the artifact
service's CreateArtifact call times out (runs 44284485344, 44305019470), so nothing was
published. The bench job now publishes with plain git, which those runs showed still works.

WHAT THIS PINS (against local bare repos standing in for skillberry-runs/dashboard and tau)

1. A leg's run folder (ci_runs/<run_id>__<slug>/, run_folder.py) and its Open UI data
   (ci_ui/<run_id>__<slug>/, masked) land in <bench repo> in one commit; its record at
   dashboard/records/<run_id>__<slug>.json with has_ui true and report_url -> the folder's
   README page; all committed by skillberry-bot. A repo with "site": false links GitHub instead.
2. A bench with no repo in sections.json still gets its record (has_ui false, no report_url) and
   a warning.
3. Republishing the same leg is a no-op, not a failure or a duplicate commit.
4. Legs publishing at the same moment all land (push races retry on a fresh clone).
5. Only the run's own ci_ui/<name> is checked out, never the repo's whole ci_ui/ (GBs).
6. No runmeta.json (the job stopped early) -> nothing published, exit 0; no token -> exit 1.
7. The workflow: the bench job runs the publisher with the results token, before the (now
   optional) artifact upload, and the `aggregate` job is gone.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "ci" / "benchmarks" / "lib" / "publish_results.sh"
WORKFLOW = REPO / ".github" / "workflows" / "benchmarks.yml"
RUN_ID = "999000111"

pytestmark = pytest.mark.skipif(not shutil.which("git"), reason="needs git")

SECTIONS = [
    {"repo": "tau", "title": "tau2", "benches": ["tau2", "tau2_sierra"]},
    {"repo": "spreadsheetbench", "title": "SpreadsheetBench"},
    {"repo": "skillsbench", "title": "SkillsBench"},
    {"repo": "rfe", "title": "RFE Creator", "benches": ["rfe-creator"], "site": False},
]

# Minimal stand-ins for the dashboard's scripts (the real ones live in skillberry-runs/dashboard):
# mask_secrets rewrites tool-call ids, check_records requires the keys a record must have.
MASK = r'''
import re, sys
from pathlib import Path
for d in sys.argv[1:]:
    for p in Path(d).rglob("*"):
        if p.is_file():
            t = p.read_text()
            n = re.sub(r"toolu_bdrk_[A-Za-z0-9]{16,}", "toolu_masked_x", t)
            if n != t: p.write_text(n)
'''
CHECK = r'''
import json, sys
for f in sys.argv[1:]:
    r = json.load(open(f))
    missing = [k for k in ("run_id", "bench", "tier", "schema", "has_ui") if k not in r]
    if missing: sys.exit(f"{f}: missing {missing}")
print("ok")
'''


def _git(*args, cwd=None):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def _bare(remotes: Path, name: str, files: dict[str, str]) -> None:
    seed = remotes.parent / f"seed_{name}"
    for rel, txt in files.items():
        p = seed / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(txt)
    _git("init", "-q", "-b", "main", cwd=seed)
    _git("add", "-A", cwd=seed)
    _git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "seed", cwd=seed)
    _git("clone", "-q", "--bare", str(seed), str(remotes / f"{name}.git"))
    _git(f"--git-dir={remotes / f'{name}.git'}", "config", "uploadpack.allowFilter", "true")


def _reject_pushes(bare: Path) -> None:
    """Make `bare` refuse every push. Via the repo's own core.hooksPath, because a global one
    (IBM's "Block Secrets" scanner sets it on developer machines) would hide hooks/pre-receive."""
    hooks = bare / "reject-hooks"
    hooks.mkdir()
    (hooks / "pre-receive").write_text("#!/bin/sh\necho rejected by test >&2\nexit 1\n")
    (hooks / "pre-receive").chmod(0o755)
    _git(f"--git-dir={bare}", "config", "core.hooksPath", str(hooks))


@pytest.fixture
def org(tmp_path):
    remotes = tmp_path / "remotes"
    remotes.mkdir()
    _bare(remotes, "dashboard", {
        "sections.json": json.dumps(SECTIONS),
        "scripts/mask_secrets.py": MASK,
        "scripts/check_records.py": CHECK,
        "records/.keep": "",
    })
    # an existing run's data, which a publish must never check out
    _bare(remotes, "tau", {"README.md": "tau\n", "ci_ui/111__smoke-tau2/big.json": "{}",
                           "ci_runs/111__smoke-tau2/README.md": "old\n"})
    _bare(remotes, "skillsbench", {"README.md": "sb\n"})
    _bare(remotes, "rfe", {"README.md": "rfe\n"})
    return remotes


def _leg(tmp_path: Path, bench: str, tier: str = "canary", ui: bool = True) -> Path:
    out = tmp_path / f"out_{tier}_{bench}"
    out.mkdir()
    (out / "runmeta.json").write_text(json.dumps({
        "run_id": int(RUN_ID), "bench": bench, "tier": tier, "conclusion": "success",
        "date": "2026-11-18T13:00:00Z",
    }))
    (out / "metrics.jsonl").write_text(json.dumps({"task": "8", "reward_baseline": 0.0, "reward_opt": 1.0}) + "\n")
    (out / "steps.jsonl").write_text(json.dumps({"iter": 0, "eval_usd": 0.1}) + "\n")
    (out / "report.md").write_text("## Canary suite\n| task | base | opt |\n")
    opt = out / "optimized"
    (opt / "optimized_capability" / "__pycache__").mkdir(parents=True)
    (opt / "capability.diff").write_text("--- a/policy.md\n+++ b/policy.md\n+be careful\n")
    (opt / "optimized_capability" / "policy.md").write_text("be careful\n")
    (opt / "optimized_capability" / "__pycache__" / "x.pyc").write_bytes(b"\0")
    if ui:
        (out / "ui" / "data").mkdir(parents=True)
        (out / "ui" / "data" / "runs.json").write_text('[{"tool": "toolu_bdrk_01ABCDEFGHIJKLMNOPQRSTUV"}]')
    # the project work dir run_suite.sh leaves next to it (<out>_proj)
    proj = Path(f"{out}_proj") / ".capevolve"
    (proj / "project" / "inputs").mkdir(parents=True)
    (proj / "project" / "capevolve.yaml").write_text("algorithm: hill-climb\n")
    (proj / "project" / "inputs" / "split_ids.json").write_text('{"train": ["8"], "val": ["8"], "test": ["8"]}')
    (proj / "run_suite").mkdir()
    (proj / "run_suite" / "final.json").write_text(json.dumps({
        "test": {"reward": 1.0}, "test_baseline": {"reward": 0.0}, "test_delta": 1.0,
        "best_id": "cand_0001", "train_equals_val": True}))
    return out


def _publish(tmp_path, remotes, out, slug, **env_extra):
    rt = tmp_path / "runner_temp"
    rt.mkdir(exist_ok=True)
    env = {**os.environ, "RESULTS_REMOTE_BASE": f"file://{remotes}", "RUNNER_TEMP": str(rt),
           "PY": sys.executable, "GIT_CONFIG_NOSYSTEM": "1", **env_extra}
    return subprocess.run(["bash", str(SCRIPT), str(out), RUN_ID, slug],
                          capture_output=True, text=True, env=env, timeout=120)


def _show(remotes, repo, path):
    return _git(f"--git-dir={remotes / f'{repo}.git'}", "show", f"main:{path}")


def _log(remotes, repo):
    return _git(f"--git-dir={remotes / f'{repo}.git'}", "log", "--format=%an <%ae>|%s", "main").splitlines()


def _ls(remotes, repo, path):
    return _git(f"--git-dir={remotes / f'{repo}.git'}", "ls-tree", "-r", "--name-only", "main", path).split()


def test_leg_publishes_its_run_folder_and_masked_ui_data_then_its_record(tmp_path, org):
    r = _publish(tmp_path, org, _leg(tmp_path, "tau2"), "canary-tau2")
    assert r.returncode == 0, r.stdout + r.stderr
    name = f"{RUN_ID}__canary-tau2"
    ui = _show(org, "tau", f"ci_ui/{name}/runs.json")
    assert "toolu_masked_" in ui and "toolu_bdrk_" not in ui
    folder = sorted(f[len(f"ci_runs/{name}/"):] for f in _ls(org, "tau", f"ci_runs/{name}"))
    assert folder == ["README.md", "capability.diff", "final.json", "metrics.jsonl",
                      "optimized_capability/policy.md", "recipe/capevolve.yaml", "recipe/split_ids.json",
                      "report.md", "runmeta.json", "steps.jsonl"], folder
    readme = _show(org, "tau", f"ci_runs/{name}/README.md")
    assert readme.startswith(f"# canary / tau2 — run {RUN_ID}")
    assert "Pipeline check only" in readme and "No held-out split" in readme
    assert "**Sealed test:** 0.000 → 1.000" in readme
    assert f"/tau/ci_ui/{name}" in readme.replace("%2F", "/")      # its Open UI link
    rec = json.loads(_show(org, "dashboard", f"records/{name}.json"))
    assert rec["has_ui"] is True and rec["bench"] == "tau2" and rec["suite"]["reward_opt"] == 1.0
    assert rec["report_url"] == f"https://skillberry-runs.github.io/dashboard/tau/ci_runs/{name}/README.html"
    bot = "skillberry-bot <281869455+skillberry-bot@users.noreply.github.com>"
    assert _log(org, "tau")[0] == f"{bot}|run {RUN_ID} (canary-tau2): ci_runs/ folder and Open UI data"
    assert len(_log(org, "tau")) == 2, "the run folder and its Open UI data are ONE commit"
    assert _log(org, "dashboard")[0].startswith(bot + "|records:")
    # the temp work dir (clones) is removed
    assert not list((tmp_path / "runner_temp").iterdir())


def test_bench_without_a_repo_gets_its_record_but_no_ui(tmp_path, org):
    r = _publish(tmp_path, org, _leg(tmp_path, "madeupbench"), "canary-madeupbench")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "has no repo" in r.stdout
    rec = json.loads(_show(org, "dashboard", f"records/{RUN_ID}__canary-madeupbench.json"))
    assert rec["has_ui"] is False and "report_url" not in rec


def test_a_repo_without_section_pages_links_the_folder_on_github(tmp_path, org):
    r = _publish(tmp_path, org, _leg(tmp_path, "rfe-creator"), "smoke-rfe-creator")
    assert r.returncode == 0, r.stdout + r.stderr
    rec = json.loads(_show(org, "dashboard", f"records/{RUN_ID}__smoke-rfe-creator.json"))
    assert rec["report_url"] == f"https://github.com/skillberry-runs/rfe/tree/main/ci_runs/{RUN_ID}__smoke-rfe-creator"


def test_skillsbench_never_publishes_the_licensed_skill_content(tmp_path, org):
    out = _leg(tmp_path, "skillsbench")
    (out / "optimized" / "capability.diff").unlink()          # run_suite.sh writes a diffstat instead
    (out / "optimized" / "capability.diffstat.txt").write_text(" docx/SKILL.md | 2 +-\n")
    r = _publish(tmp_path, org, out, "canary-skillsbench")
    assert r.returncode == 0, r.stdout + r.stderr
    files = _ls(org, "skillsbench", "ci_runs")
    assert any(f.endswith("capability.diffstat.txt") for f in files)
    assert not any("optimized_capability" in f or f.endswith("capability.diff") for f in files), files


def test_republishing_a_leg_is_a_no_op(tmp_path, org):
    out = _leg(tmp_path, "tau2")
    assert _publish(tmp_path, org, out, "canary-tau2").returncode == 0
    before = (_log(org, "tau"), _log(org, "dashboard"))
    r = _publish(tmp_path, org, out, "canary-tau2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (_log(org, "tau"), _log(org, "dashboard")) == before


def test_legs_publishing_at_once_all_land(tmp_path, org):
    legs = [(_leg(tmp_path, b, tier=t), f"{t}-{b}") for t in ("canary", "smoke") for b in ("tau2", "tau2_sierra")]
    with ThreadPoolExecutor(len(legs)) as ex:
        results = list(ex.map(lambda leg: _publish(tmp_path, org, *leg), legs))
    for r in results:
        assert r.returncode == 0, r.stdout + r.stderr
    recs = _git(f"--git-dir={org / 'dashboard.git'}", "ls-tree", "--name-only", "main", "records/").split()
    assert sorted(f"records/{RUN_ID}__{s}.json" for _, s in legs) == sorted(x for x in recs if RUN_ID in x)
    ui = _git(f"--git-dir={org / 'tau.git'}", "ls-tree", "--name-only", "main", "ci_ui/").split()
    assert all(f"ci_ui/{RUN_ID}__{s}" in ui for _, s in legs)


def test_only_the_runs_own_ci_ui_folder_is_checked_out(tmp_path, org):
    """Stop right after the clone (fail the push) and look at what the clone checked out."""
    _reject_pushes(org / "tau.git")
    rt = tmp_path / "runner_temp"
    script = tmp_path / "keep.sh"   # same script, but keep the work dir for inspection
    script.write_text(SCRIPT.read_text().replace("trap 'rm -rf \"$work\"' EXIT", ":"))
    rt.mkdir()
    env = {**os.environ, "RESULTS_REMOTE_BASE": f"file://{org}", "RUNNER_TEMP": str(rt),
           "PY": sys.executable, "ATTEMPTS": "1", "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["bash", str(script), str(_leg(tmp_path, "tau2")), RUN_ID, "canary-tau2"],
                   capture_output=True, text=True, env=env, timeout=120)
    (work,) = list(rt.iterdir())
    clone = work / "r_tau"
    assert (clone / "ci_ui" / f"{RUN_ID}__canary-tau2" / "runs.json").exists()
    assert not (clone / "ci_ui" / "111__smoke-tau2").exists(), "the repo's other runs were checked out"
    assert not (clone / "ci_runs" / "111__smoke-tau2").exists(), "the repo's other runs were checked out"


def test_ui_push_failure_still_publishes_the_record_without_ui_and_fails(tmp_path, org):
    _reject_pushes(org / "tau.git")
    r = _publish(tmp_path, org, _leg(tmp_path, "tau2"), "canary-tau2", ATTEMPTS="1")
    assert r.returncode == 1
    rec = json.loads(_show(org, "dashboard", f"records/{RUN_ID}__canary-tau2.json"))
    assert rec["has_ui"] is False and "report_url" not in rec


def test_no_runmeta_publishes_nothing(tmp_path, org):
    out = tmp_path / "empty"
    out.mkdir()
    r = _publish(tmp_path, org, out, "canary-tau2")
    assert r.returncode == 0 and "nothing to publish" in r.stdout
    assert len(_log(org, "dashboard")) == 1


def test_missing_token_fails_loudly(tmp_path, org):
    env = {k: v for k, v in os.environ.items() if k != "GH_TOKEN"}
    rt = tmp_path / "rt"
    rt.mkdir()
    r = subprocess.run(["bash", str(SCRIPT), str(_leg(tmp_path, "tau2")), RUN_ID, "canary-tau2"],
                       capture_output=True, text=True, env={**env, "RUNNER_TEMP": str(rt)}, timeout=60)
    assert r.returncode == 1 and "SKILLBERRY_RUNS_RESULTS_TOKEN is not set" in r.stdout


def test_the_token_is_never_part_of_a_clone_url():
    """Clones are anonymous (the repos are public), so the token never lands in a .git/config
    on the persistent self-hosted runner; only the push command line carries it."""
    src = SCRIPT.read_text()
    clone_fn = src[src.index("clone_url()"):src.index("push_url()")]
    assert "GH_TOKEN" not in clone_fn


def _steps(src: str) -> dict[str, str]:
    """name -> text of each `- name:` step (text-level, like the other workflow tests: PyYAML
    is not a test dependency)."""
    parts = re.split(r"\n(?=      - (?:name|uses): )", src)
    out = {}
    for p in parts[1:]:
        m = re.match(r"      - name: (.+)", p)
        if m:
            out[m.group(1).strip()] = p
    return out


def test_workflow_publishes_from_the_bench_job_and_has_no_aggregate_job():
    src = WORKFLOW.read_text()
    jobs = re.findall(r"^  ([a-z_-]+):\s*$", src[src.index("\njobs:"):], re.M)
    assert jobs == ["plan", "bench"], jobs
    steps = _steps(src)
    names = list(steps)
    pub = steps["Publish results to skillberry-runs"]
    assert "publish_results.sh" in pub
    assert "GH_TOKEN: ${{ secrets.SKILLBERRY_RUNS_RESULTS_TOKEN }}" in pub
    assert "if: always()" in pub and "timeout-minutes:" in pub
    up = "Upload artifacts (metrics + optimized capabilities)"
    assert names.index("Write run metadata") < names.index("Publish results to skillberry-runs") < names.index(up)
    assert "continue-on-error: true" in steps[up]
    # the results token is given to the publish step only
    assert src.count("SKILLBERRY_RUNS_RESULTS_TOKEN") == pub.count("SKILLBERRY_RUNS_RESULTS_TOKEN")
