# Consuming-LLM Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user declare the runtime/consuming LLM (by model id or capability tier) so the optimizer prompt and capability guidance adapt their proposed edits to that reader — distinct from the edit-proposing `optimizer_model`.

**Architecture:** A new zero-dependency core module (`target_profile.py`) holds built-in capability tiers (each with a prose "reader brief") and a name→tier lookup, and resolves a declaration to a `TargetProfile`. The run loop injects the resolved brief into a new `{{TARGET_READER}}` slot in the optimizer-instructions template, threaded `capevolve.yaml` → `cli.py` → `hill-climb/run.py` → `harness.hill_climb_loop` → `harness._focus_instructions`, mirroring the existing `--instructions-file` path exactly. The four capability skills gain tier-conditional guidance. `cap-evolve check` warns (non-blocking) on a detected runner-model mismatch. The honesty core (gate/splits/seal) is untouched.

**Tech Stack:** Python 3.10+ (stdlib only — no new runtime deps), pytest, the existing cap-evolve skill/markdown library.

**Spec:** `docs/superpowers/specs/2026-07-20-consuming-llm-profile-design.md`

## Global Constraints

- **Zero runtime dependencies.** Core code is stdlib-only. Do NOT add a YAML dependency. (This is why built-in tier briefs live in a Python module, not a parsed YAML file — see Task 1, resolving the spec's flagged YAML-reader risk.)
- **Python 3.10+** syntax is allowed (`str | None`, `match` optional).
- **Backward compatibility is mandatory.** Every new field defaults to blank/agnostic. With `target_model` unset, the rendered optimizer prompt contains NO reader block and NO leftover `{{TARGET_READER}}` token; gate, splits, reports behave exactly as before.
- **Two distinct roles must stay visibly distinct** in any user-facing copy: `optimizer_model` = the model that PROPOSES edits; `target_model` = the model that CONSUMES the capabilities at runtime. Never conflate them.
- **Tier vocabulary is fixed:** `frontier`, `strong`, `mid`, `weak`. Default tier for an unknown model id is `strong`.
- Run tests from the repo root with the venv active: `source .venv/bin/activate`.

---

### Task 1: Core `target_profile` resolver

**Files:**
- Create: `core/cap_evolve/target_profile.py`
- Test: `core/tests/test_target_profile.py`

**Interfaces:**
- Consumes: nothing (stdlib only).
- Produces:
  - `TIERS: dict[str, dict]` — keys `frontier|strong|mid|weak`; each `{"brief": str, "suggested_num_trials": int, "notes": str}`.
  - `MODEL_MAP: dict[str, str]` — lowercased model id → tier.
  - `DEFAULT_TIER = "strong"`.
  - `@dataclass TargetProfile(model: str, tier: str, brief: str, suggested_num_trials: int, notes: str, resolution_note: str)` with property `is_agnostic -> bool` (True iff `tier == ""`).
  - `resolve(target_model: str = "", target_profile_file: str | Path | None = None, project_dir: str | Path | None = None) -> TargetProfile`.
  - `reader_block(profile: TargetProfile) -> str` — the `{{TARGET_READER}}` text; returns `""` when agnostic.

- [ ] **Step 1: Write the failing test**

```python
# core/tests/test_target_profile.py
from pathlib import Path
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest core/tests/test_target_profile.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cap_evolve.target_profile'`.

- [ ] **Step 3: Write minimal implementation**

```python
# core/cap_evolve/target_profile.py
"""Consuming-LLM capability profiles.

Distinct from ``optimizer_model`` (the model that PROPOSES edits): the *consuming*
model is the one the agent under test reads these capabilities with at runtime. A
declaration is either a tier keyword (frontier|strong|mid|weak) or a concrete model id
resolved to a tier via ``MODEL_MAP``. The resolved brief steers the optimizer prompt and
the capability guidance to optimize FOR that reader.

Zero-dependency by design: the built-in tiers live here as Python data (no YAML parse),
and a project may override a tier's brief with a raw-text file (``target_profile_file``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

DEFAULT_TIER = "strong"

TIERS: dict[str, dict] = {
    "frontier": {
        "brief": (
            "The reader is a top-tier model: strong long-context reasoning, reliable "
            "instruction-following, and a tendency to OVER-comply. Prefer concise policy "
            "that explains the WHY over piling on ALL-CAPS MUSTs; soften brittle "
            "imperatives; trust multi-step reasoning; keep few-shot examples minimal. "
            "Over-constraining HURTS this reader."
        ),
        "suggested_num_trials": 1,
        "notes": "e.g. claude-opus, gpt-4-class, gemini-2.5-pro-class",
    },
    "strong": {
        "brief": (
            "The reader is a capable general model, but less robust than frontier on long "
            "or ambiguous context. Keep instructions clear and reasonably explicit; add a "
            "worked example for tricky formats; prefer code enforcement for behavioral "
            "rules over trusting inference."
        ),
        "suggested_num_trials": 3,
        "notes": "default when a named model is unknown",
    },
    "mid": {
        "brief": (
            "The reader is a mid-capability model (e.g. ~100B open weights). Be EXPLICIT: "
            "imperative step-by-step rules, at least one worked few-shot example per "
            "non-trivial behavior, short decision chains, and literal argument/slot-filling "
            "docs on every tool parameter. Lean HARD on deterministic tool-code "
            "enforcement — a behavioral rule it 'knows' but skips must be enforced in code, "
            "not restated in prose."
        ),
        "suggested_num_trials": 5,
        "notes": "e.g. gpt-oss-120b",
    },
    "weak": {
        "brief": (
            "The reader is a smaller/weaker model. Assume it will miss anything not made "
            "mechanical. Maximize explicitness and examples; minimize unaided reasoning; "
            "move as much correctness as possible into tool code/guards and rigid output "
            "contracts; keep each instruction short and single-purpose. Prose is the "
            "weakest lever here."
        ),
        "suggested_num_trials": 5,
        "notes": "e.g. gpt-oss-20b, small local models",
    },
}

# Known model id (lowercased) -> tier. Extensible; unknown ids fall back to DEFAULT_TIER.
MODEL_MAP: dict[str, str] = {
    "claude-opus-4-6": "frontier",
    "claude-opus-4-8": "frontier",
    "claude-sonnet-5": "strong",
    "claude-haiku-4-5": "mid",
    "gpt-4o": "frontier",
    "gpt-oss-120b": "mid",
    "gpt-oss-20b": "weak",
}


@dataclass
class TargetProfile:
    model: str = ""
    tier: str = ""
    brief: str = ""
    suggested_num_trials: int = 0
    notes: str = ""
    resolution_note: str = ""

    @property
    def is_agnostic(self) -> bool:
        return not self.tier


def resolve(target_model: str = "",
            target_profile_file: str | Path | None = None,
            project_dir: str | Path | None = None) -> TargetProfile:
    decl = (target_model or "").strip()
    if not decl:
        return TargetProfile()  # agnostic

    key = decl.lower()
    note = ""
    if key in TIERS:
        tier = key
    elif key in MODEL_MAP:
        tier = MODEL_MAP[key]
    else:
        tier = DEFAULT_TIER
        note = (f"unknown model id '{decl}'; defaulting to tier '{DEFAULT_TIER}' — "
                "set a tier keyword (frontier|strong|mid|weak) explicitly to override")

    spec = TIERS[tier]
    brief = spec["brief"]
    if target_profile_file:
        fp = Path(target_profile_file)
        if not fp.is_absolute() and project_dir is not None:
            cand = Path(project_dir) / fp
            if cand.exists():
                fp = cand
        try:
            if fp.exists():
                brief = fp.read_text(encoding="utf-8").strip()
        except OSError:
            pass  # unreadable override → keep the tier's built-in brief

    return TargetProfile(model=decl, tier=tier, brief=brief,
                         suggested_num_trials=int(spec["suggested_num_trials"]),
                         notes=str(spec["notes"]), resolution_note=note)


def reader_block(profile: TargetProfile) -> str:
    """Render the ``{{TARGET_READER}}`` block. Empty string when agnostic."""
    if profile.is_agnostic:
        return ""
    return (
        "## THE READER (who consumes what you edit)\n"
        f"At runtime these capabilities are read by `{profile.model}` — capability tier: "
        f"**{profile.tier}**. {profile.brief}\n"
        "Optimize your edits for THIS reader's capability level, not for your own. When "
        "the reader is weaker than you, prefer explicit rules, worked examples, and "
        "code enforcement over terse prose you would personally infer.\n"
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest core/tests/test_target_profile.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add core/cap_evolve/target_profile.py core/tests/test_target_profile.py
git commit -m "feat(core): target_profile resolver for the consuming LLM

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Render `{{TARGET_READER}}` in the optimizer prompt

**Files:**
- Modify: `templates/project/optimizer/INSTRUCTIONS.md` (add the slot near the top)
- Modify: `core/cap_evolve/harness.py` — `_focus_instructions` (add `target_reader` param + repl entry; ~lines 1674–1730)
- Test: `core/tests/test_target_reader_render.py`

**Interfaces:**
- Consumes: `target_profile.reader_block` (Task 1).
- Produces: `_focus_instructions(..., target_reader: str = "")` — new keyword-only-safe trailing param; adds `"{{TARGET_READER}}": target_reader` to the `repl` dict.

- [ ] **Step 1: Add the slot to the template**

In `templates/project/optimizer/INSTRUCTIONS.md`, immediately after the H1 title line
`# Optimize the capability — ship several REAL, SAFE, VERIFIED fixes this iteration`,
insert a blank line then the token on its own line:

```
{{TARGET_READER}}
```

(It sits above `{{FOCUS_SUMMARY}}`. When agnostic it renders to `""`, leaving the existing structure intact.)

- [ ] **Step 2: Write the failing test**

```python
# core/tests/test_target_reader_render.py
from cap_evolve import harness
from cap_evolve.loop import SplitResult
from cap_evolve import target_profile as tp


def _val():
    return SplitResult(split="val", reward=0.0, stderr=0.0,
                       per_task=[{"task_id": "t1", "reward": 0.0}])


def test_reader_block_injected_when_declared():
    reader = tp.reader_block(tp.resolve("gpt-oss-120b"))
    out = harness._focus_instructions(_val(), None, "all", capabilities=["system-prompt"],
                                      target_reader=reader)
    assert "THE READER" in out and "gpt-oss-120b" in out


def test_no_reader_block_and_no_token_when_agnostic():
    out = harness._focus_instructions(_val(), None, "all", capabilities=["system-prompt"],
                                      target_reader="")
    assert "THE READER" not in out
    assert "{{TARGET_READER}}" not in out  # token must be substituted away
```

Note: `SplitResult` is a dataclass with a required `split: str` first field (verified in `core/cap_evolve/loop.py`); there is no `n` field. The helper above matches.

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest core/tests/test_target_reader_render.py -v`
Expected: FAIL — `test_no_reader_block_and_no_token_when_agnostic` fails because the template's `{{TARGET_READER}}` token is left unsubstituted (or `_focus_instructions` rejects the new kwarg).

- [ ] **Step 4: Implement**

In `core/cap_evolve/harness.py`, add the trailing parameter to `_focus_instructions`:

```python
def _focus_instructions(current_val: SplitResult, focus_ids, label: str,
                        capabilities=None, algorithm: str = "hill-climb",
                        instructions_file=None, bench_repo: str | None = None,
                        optimizer_name: str | None = None,
                        seed_empty: bool | None = None,
                        target_reader: str = "") -> str:
```

Add the entry to the `repl` dict (alongside `{{EMPTY_SEED}}`):

```python
    repl = {
        "{{FOCUS_SUMMARY}}": focus_summary,
        "{{FAILURES}}": failures,
        "{{PASSING}}": passing,
        "{{CAP_BRIEF}}": cap,
        "{{ALGO_BRIEF}}": algo,
        "{{BENCH_REPO}}": bench,
        "{{PARALLEL_NOTE}}": parallel_note,
        "{{EMPTY_SEED}}": empty_note,
        "{{TARGET_READER}}": target_reader,
    }
```

In the fallback branch (`# Fallback (template unreadable):` ~line 1735), prepend the
reader block so the fallback prompt also carries it. Find the `parts = [` list and insert
`target_reader,` as the second element (after the H1 string, before `focus_summary`):

```python
    parts = [
        "# Optimize the capability — analyze this step's trajectories in ./trajectories/, "
        "then fix MANY root causes in this ONE candidate and STOP.",
        target_reader,
        focus_summary, "",
        empty_note,
        ...
```

(`target_reader` is `""` when agnostic, so the fallback is unchanged in that case.)

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest core/tests/test_target_reader_render.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add templates/project/optimizer/INSTRUCTIONS.md core/cap_evolve/harness.py core/tests/test_target_reader_render.py
git commit -m "feat(harness): inject {{TARGET_READER}} into the optimizer prompt

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Thread `target_model` end-to-end (config → CLI → hill-climb → loop)

**Files:**
- Modify: `core/cap_evolve/harness.py` — `hill_climb_loop` (add params + resolve + pass `target_reader`; signature at ~line 1767, call site at ~line 1821)
- Modify: `skills/algorithms/hill-climb/scripts/run.py` (argparse + forward to `hill_climb_loop`; ~lines 40–98)
- Modify: `core/cap_evolve/cli.py` (append flags to `alg_cmd`, hill-climb branch; ~lines 305–320)
- Test: `core/tests/test_target_reader_wiring.py`

**Interfaces:**
- Consumes: `target_profile.resolve` + `target_profile.reader_block` (Task 1); `_focus_instructions(..., target_reader=...)` (Task 2).
- Produces: `harness.hill_climb_loop(..., target_model: str = "", target_profile_file: str | None = None)`. NOTE (verified): `hill_climb_loop` **already** has a `project_dir: Path | None = None` keyword param (and `capability_sources`); reuse `project_dir` for resolution — do NOT add a new one. It is a keyword-only function (`*` after `adapter`), so append the two new params anywhere after `project_dir`.

- [ ] **Step 1: Write the failing test (loop-level resolution)**

```python
# core/tests/test_target_reader_wiring.py
import inspect
from cap_evolve import harness


def test_hill_climb_loop_accepts_target_params():
    sig = inspect.signature(harness.hill_climb_loop)
    assert "target_model" in sig.parameters
    assert "target_profile_file" in sig.parameters
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest core/tests/test_target_reader_wiring.py -v`
Expected: FAIL — `assert 'target_model' in sig.parameters`.

- [ ] **Step 3: Implement `hill_climb_loop` changes**

Add the two params to the `hill_climb_loop` signature (after the existing `project_dir: Path | None = None`):

```python
    target_model: str = "",
    target_profile_file: str | None = None,
```

At the top of the loop body (before the iteration loop that calls `_focus_instructions`), resolve once, reusing the existing `project_dir` param:

```python
    from . import target_profile as _tp
    _profile = _tp.resolve(target_model, target_profile_file, project_dir=project_dir)
    _target_reader = _tp.reader_block(_profile)
```

Pass it into the call at ~line 1821:

```python
        instructions = _focus_instructions(current_val, focus_ids, label,
                                            capabilities=capabilities, algorithm=algorithm,
                                            instructions_file=instructions_file,
                                            bench_repo=bench_repo, optimizer_name=optimizer_name,
                                            seed_empty=seed_empty,
                                            target_reader=_target_reader)
```

(Match the existing kwargs already present at that call; only `target_reader=_target_reader` is new.)

- [ ] **Step 4: Implement `hill-climb/scripts/run.py` changes**

Add argparse flags (after `--capability-sources`, ~line 70):

```python
    p.add_argument("--target-model", default="",
                   help="consuming/runtime model id or tier keyword (frontier|strong|mid|weak)")
    p.add_argument("--target-profile-file", default=None,
                   help="optional project-local brief overriding the tier's built-in brief")
```

Forward to the loop in the `harness.hill_climb_loop(...)` call (~line 91):

```python
        target_model=args.target_model,
        target_profile_file=args.target_profile_file,
```

- [ ] **Step 5: Implement `cli.py` changes**

In the `if algorithm_name == "hill-climb":` block that appends `--instructions-file` etc. (~line 305), append after the capability-sources handling:

```python
        if spec.get("target_model"):
            alg_cmd += ["--target-model", str(spec["target_model"])]
        tpf = spec.get("target_profile_file")
        if tpf:
            tpf_p = Path(str(tpf))
            if not tpf_p.is_absolute() and not tpf_p.exists():
                tpf_p = Path(project) / str(tpf)
            alg_cmd += ["--target-profile-file", str(tpf_p)]
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest core/tests/test_target_reader_wiring.py core/tests/test_target_reader_render.py -v`
Expected: PASS.

Also run a syntax/import smoke check on the edited skill script:
Run: `python -c "import ast; ast.parse(open('skills/algorithms/hill-climb/scripts/run.py').read())"`
Expected: no output (parses).

- [ ] **Step 7: Commit**

```bash
git add core/cap_evolve/harness.py core/cap_evolve/cli.py skills/algorithms/hill-climb/scripts/run.py core/tests/test_target_reader_wiring.py
git commit -m "feat: thread target_model config → CLI → hill-climb → loop

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Record + display the consuming model (run metadata, report, dashboard)

**Files:**
- Modify: `core/cap_evolve/cli.py` — add `target_model` to the `--plan-only` config dump (~line 220) so `estimate`/`--plan-only` surfaces it.
- Modify: `skills/algorithms/hill-climb/scripts/run.py` — after opening the run dir, log a `target_profile` event so it lands in run metadata.
- Modify: `core/cap_evolve/dashboard.py` — surface the consuming model + tier in the run header/KPI metadata (near where `optimizer_model` / gate mode are shown).
- Modify: `skills/phases/report/SKILL.md` — instruct the report to print the consuming model + tier next to the optimizer model.
- Test: `core/tests/test_target_profile_metadata.py`

**Interfaces:**
- Consumes: `target_profile.resolve` (Task 1); the run dir's event log (`run_dir.log_event`, already used across the codebase).
- Produces: a `target_profile` event `{model, tier, suggested_num_trials, resolution_note}` in the run's event stream.

- [ ] **Step 1: Write the failing test**

```python
# core/tests/test_target_profile_metadata.py
from cap_evolve import target_profile as tp


def test_metadata_payload_shape():
    p = tp.resolve("gpt-oss-120b")
    payload = {"model": p.model, "tier": p.tier,
               "suggested_num_trials": p.suggested_num_trials,
               "resolution_note": p.resolution_note}
    assert payload == {"model": "gpt-oss-120b", "tier": "mid",
                       "suggested_num_trials": 5, "resolution_note": ""}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest core/tests/test_target_profile_metadata.py -v`
Expected: PASS already? No — this test only exercises Task 1 code, so it passes immediately. That is acceptable here: this task is mostly metadata plumbing/UI whose behavior is verified by the payload-shape contract above plus manual dashboard inspection. Treat Steps 3–5 as the deliverable and this test as the contract guard.

- [ ] **Step 3: Log the profile event in `hill-climb/scripts/run.py`**

After `run_dir` is opened and before the loop starts, add:

```python
    from cap_evolve import target_profile as _tp
    _p = _tp.resolve(args.target_model, args.target_profile_file, project_dir=args.project)
    if not _p.is_agnostic:
        run_dir.log_event("target_profile", model=_p.model, tier=_p.tier,
                          suggested_num_trials=_p.suggested_num_trials,
                          resolution_note=_p.resolution_note)
```

(Reuse the `run_dir` variable already established in the script. If the script resolves the profile in Task 3 already, reuse that object instead of re-resolving.)

- [ ] **Step 4: Add `target_model` to the `--plan-only` dump in `cli.py`**

In the `print(json.dumps({...}))` for `args.plan_only` (~line 217), add a key:

```python
                          "target_model": spec.get("target_model", ""),
```

- [ ] **Step 5: Surface in dashboard + report**

In `core/cap_evolve/dashboard.py`, in the reducer/renderer that reads the event stream for run metadata, read the `target_profile` event (if present) and render a line/badge in the run header: `consuming model: <model> (tier <tier>)` next to the optimizer model. Follow the existing pattern used for `optimizer_model` in that file (locate it via `grep -n "optimizer_model\|gate_mode" core/cap_evolve/dashboard.py`). If no such metadata panel exists for optimizer_model, add a single small line in the KPI header area; keep it hidden when the event is absent (agnostic run) — matching the file's stated "hide the panel rather than crashing" convention.

In `skills/phases/report/SKILL.md`, add one sentence to the summary section: the report must print the declared consuming model + tier (from the `target_profile` event) alongside the optimizer model, so the two LLM roles are visibly distinct. If the event is absent, print nothing (agnostic).

- [ ] **Step 6: Run test + smoke checks**

Run: `python -m pytest core/tests/test_target_profile_metadata.py core/tests/test_dashboard.py -v`
Expected: PASS (existing dashboard tests stay green; if a dashboard test snapshots header HTML, update the snapshot to include the new hidden-when-absent line).

- [ ] **Step 7: Commit**

```bash
git add core/cap_evolve/cli.py core/cap_evolve/dashboard.py skills/algorithms/hill-climb/scripts/run.py skills/phases/report/SKILL.md core/tests/test_target_profile_metadata.py
git commit -m "feat: record + display the consuming model (metadata, report, dashboard)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: `cap-evolve check` warns on runner-model mismatch

**Files:**
- Modify: `core/cap_evolve/adapter.py` — add optional non-abstract `runner_model(self) -> str | None` (returns `None`), mirroring `trajectories`/`live` optional hooks (~lines 113–158).
- Modify: `core/cap_evolve/check.py` — in `run_check`, best-effort read `capevolve.yaml`'s `target_model`, call `adapter.runner_model()`, and append a `notes` warning when the two resolve to different tiers.
- Test: `core/tests/test_check_runner_mismatch.py`

**Interfaces:**
- Consumes: `target_profile.resolve` (Task 1); `specfile.read_yaml` (existing); `CheckReport.notes` (existing list field).
- Produces: `CapabilityAdapter.runner_model() -> str | None` (default `None`); a warning string appended to `CheckReport.notes` on mismatch.

- [ ] **Step 1: Write the failing test**

```python
# core/tests/test_check_runner_mismatch.py
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
```

Note: the stub adapter above returns `None` from `tasks`/`score`; if `run_check`'s determinism probes choke on that, point the test project at an existing minimal fixture adapter instead (see `core/tests/` for one) and only override `runner_model`/`target_model`. The mismatch check must run regardless of probe outcomes (append it before returning, guarded by its own try/except).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest core/tests/test_check_runner_mismatch.py -v`
Expected: FAIL — `runner_model` attribute missing / no note appended.

- [ ] **Step 3: Add the adapter hook**

In `core/cap_evolve/adapter.py`, in the `CapabilityAdapter` class near the other optional hooks:

```python
    def runner_model(self) -> str | None:
        """Optional: the model id the runner drives at runtime (the CONSUMING model).

        Override to enable cap-evolve check's consuming-vs-declared mismatch warning.
        Returns None by default (no cross-check; the declaration is trusted).
        """
        return None
```

- [ ] **Step 4: Add the mismatch check to `run_check`**

In `core/cap_evolve/check.py`, near the end of `run_check` (before the final `rep.ok = ...`), add a self-contained best-effort block:

```python
    # Best-effort: warn (do not block) if the declared consuming model resolves to a
    # different capability tier than the runner actually drives. Trust the declaration
    # when either side is absent.
    try:
        from . import target_profile as _tp
        from .specfile import read_yaml as _read_yaml
        cfg_path = Path(project_dir) / "capevolve.yaml"
        declared = ""
        if cfg_path.exists():
            declared = str((_read_yaml(cfg_path.read_text(encoding="utf-8")) or {}).get("target_model", "") or "")
        actual = None
        try:
            actual = adapter.runner_model()
        except Exception:  # noqa: BLE001 — optional hook
            actual = None
        if declared and actual:
            dt = _tp.resolve(declared).tier
            at = _tp.resolve(str(actual)).tier
            if dt != at:
                rep.notes.append(
                    f"consuming-model mismatch: optimizing FOR '{declared}' (tier {dt}) "
                    f"but the runner drives '{actual}' (tier {at}) — edits are tuned for a "
                    "different reader than eval measures. Set target_model to the runner's "
                    "model, or confirm this is intended.")
    except Exception:  # noqa: BLE001 — mismatch check is best-effort, never blocks
        pass
```

Confirm `Path` is imported at the top of `check.py` (it is — used by `load_adapter`).

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest core/tests/test_check_runner_mismatch.py -v`
Expected: PASS (3 passed). The warning appends to `notes` and `rep.ok` is unaffected (non-blocking).

- [ ] **Step 6: Commit**

```bash
git add core/cap_evolve/adapter.py core/cap_evolve/check.py core/tests/test_check_runner_mismatch.py
git commit -m "feat(check): warn (non-blocking) on consuming-model tier mismatch

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Config template + intake docs

**Files:**
- Modify: `templates/project/capevolve.yaml` (add the two fields with comments)
- Modify: `.capevolve/project/capevolve.yaml` (mirror the new fields, kept blank)
- Modify: `skills/phases/intake/inputs/INPUTS.md` (add `target_model` under RECOMMENDED)
- Modify: `skills/phases/intake/SKILL.md` (mention writing it into `capevolve.yaml`)

No automated test — verified by content review + the tolerant reader parsing the new fields (existing config-load tests already exercise `read_yaml`).

- [ ] **Step 1: Add fields to `templates/project/capevolve.yaml`**

After the `--- who proposes edits ---` block (right after `optimizer_usd_per_iter`), insert:

```yaml
# --- consuming (runtime) LLM the capabilities are optimized FOR --------------
# The model the AGENT UNDER TEST reads these capabilities with at runtime — DISTINCT
# from optimizer_model (which PROPOSES edits). May be a concrete model id (resolved to a
# capability tier via the built-in profile registry) OR a tier keyword directly:
# frontier | strong | mid | weak. Empty = profile-agnostic (today's behavior).
target_model: ""
# Optional project-local brief (raw text/markdown) that OVERRIDES the resolved tier's
# built-in brief. Resolved project-relative. Leave empty to use the built-in brief.
target_profile_file: ""
```

- [ ] **Step 2: Mirror blank fields in `.capevolve/project/capevolve.yaml`**

Add the same two lines (`target_model: ""` / `target_profile_file: ""`) with a one-line comment, in the corresponding section, so the live project's config documents the option.

- [ ] **Step 3: Add to intake `INPUTS.md`**

Under `## RECOMMENDED`, add a new bullet:

```markdown
- **target_model** (default `""` = profile-agnostic): the runtime/consuming LLM the
  agent reads these capabilities with — DISTINCT from the optimizer model that proposes
  edits. Give a concrete model id (e.g. `gpt-oss-120b`) or a capability tier
  (`frontier | strong | mid | weak`). cap-evolve steers the optimizer prompt and
  capability guidance to optimize FOR this reader (a weaker reader gets more explicit
  rules, worked examples, and code enforcement; a frontier reader gets leaner prose).
  ASK the user which model the agent runs at runtime; if unknown, leave blank and note
  it in `PROJECT.md`. Optionally set `target_profile_file` to override the built-in brief.
```

- [ ] **Step 4: Add to intake `SKILL.md`**

Find where the skill lists the `capevolve.yaml` fields it writes (grep `optimizer_model` in `skills/phases/intake/SKILL.md`) and add `target_model` (and optional `target_profile_file`) to that list with a one-line description mirroring INPUTS.md.

- [ ] **Step 5: Verify config parses**

Run:
```bash
python -c "from cap_evolve.specfile import read_yaml; d=read_yaml(open('templates/project/capevolve.yaml').read()); print('target_model' in d, repr(d.get('target_model')))"
```
Expected: `True ''`

- [ ] **Step 6: Commit**

```bash
git add templates/project/capevolve.yaml .capevolve/project/capevolve.yaml skills/phases/intake/inputs/INPUTS.md skills/phases/intake/SKILL.md
git commit -m "feat(config,intake): add target_model / target_profile_file inputs

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Tier-conditional capability guidance (the knowledge work)

**Files:**
- Modify: `skills/capabilities/system-prompt/references/concepts.md`
- Modify: `skills/capabilities/tools/SKILL.md` (or its `references/` — put the section where the skill keeps its guidance)
- Modify: `skills/capabilities/mcp-tool/SKILL.md`
- Modify: `skills/capabilities/skill-package/SKILL.md`

No automated test — this is documentation the optimizer reads. Verified by content review + a markdown-lint/section-present check (Step 5).

- [ ] **Step 1: system-prompt — make the reader-capability advice tier-conditional**

In `skills/capabilities/system-prompt/references/concepts.md`, add a new section titled `## Adapting to the reader's capability tier` (place it right after `## How agents consume it`). Content:

```markdown
## Adapting to the reader's capability tier
The right edit depends on WHO reads this prompt at runtime (see the `THE READER` block
in your instructions). The advice elsewhere in this file — "soften MUSTs", "explain the
why", "newer models over-comply" — is a **frontier/strong-reader** tactic. Flip it for
weaker readers:

- **frontier / strong reader:** lean, reasoning-first prose; explain the WHY; minimal
  few-shot; soften brittle imperatives — over-constraining hurts.
- **mid / weak reader:** be EXPLICIT. Prefer imperative step-by-step rules; include at
  least one worked few-shot example per non-trivial behavior; keep decision chains short;
  make the output contract rigid and literal; and push behavioral rules into tool CODE
  (see the tools capability) rather than prose the reader will skip.

When no reader is declared (`target_model` empty), default to the frontier/strong advice
above — but say so in PROCESS.md so a later run can set the tier.
```

- [ ] **Step 2: tools — tier note on enforcement + slot-filling docs**

In the tools capability skill, add a short `## Adapting to the reader's capability tier` section:

```markdown
## Adapting to the reader's capability tier
For a **mid/weak** reader, push harder on this skill's already-preferred code enforcement
(in-body guards, composite atomic-write tools) — a weak reader skips prose rules but a
guard fires regardless — and write **literal, example-bearing per-parameter slot-filling
docs** on every tool (name the exact format, units, and one concrete valid value). For a
**frontier** reader, terser parameter docs and fewer worked examples suffice; spend the
budget on removing confusable/redundant tools instead. See the `THE READER` block.
```

- [ ] **Step 3: mcp-tool — tier note on re-description + exposed set**

In `skills/capabilities/mcp-tool/SKILL.md`, add near the `## How agents consume MCP tools` section a short paragraph:

```markdown
### Adapting to the reader's capability tier
A **mid/weak** reader needs more literal, example-bearing parameter descriptions and a
**tighter exposed set** (hide more confusable tools so the few it needs stand out). A
**frontier** reader tolerates a larger set and terser descriptions. Re-description is the
main lever either way; scale its explicitness to the reader (see the `THE READER` block).
```

- [ ] **Step 4: skill-package — tier note on body density**

In `skills/capabilities/skill-package/SKILL.md`, add a short section:

```markdown
### Adapting to the reader's capability tier
Scale SKILL.md body density to the reader: a **mid/weak** reader needs more worked steps,
explicit ordering, and examples (less inference); a **frontier** reader follows a compact,
principle-first body. Keep progressive-disclosure structure either way. See `THE READER`.
```

- [ ] **Step 5: Verify sections present**

Run:
```bash
for f in skills/capabilities/system-prompt/references/concepts.md skills/capabilities/tools/SKILL.md skills/capabilities/mcp-tool/SKILL.md skills/capabilities/skill-package/SKILL.md; do
  grep -q "reader's capability tier" "$f" && echo "OK $f" || echo "MISSING $f"
done
```
Expected: four `OK` lines.

- [ ] **Step 6: Commit**

```bash
git add skills/capabilities/system-prompt/references/concepts.md skills/capabilities/tools/SKILL.md skills/capabilities/mcp-tool/SKILL.md skills/capabilities/skill-package/SKILL.md
git commit -m "docs(capabilities): tier-conditional guidance for the consuming reader

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: Example opt-in + CHANGELOG + full suite

**Files:**
- Modify: `examples/tau2_airline/capevolve.yaml` (set `target_model: gpt-oss-120b`)
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Opt the flagship example in**

In `examples/tau2_airline/capevolve.yaml`, add under the optimizer block:

```yaml
# The tau2 airline runner (agent + user sim) is openai/gpt-oss-120b via RITS — a mid-tier
# reader. Optimize the policy + tools FOR that reader.
target_model: gpt-oss-120b
```

- [ ] **Step 2: CHANGELOG entry**

Add to `CHANGELOG.md` under the unreleased/next section:

```markdown
### Added
- **Consuming-LLM profiles.** Declare the runtime/consuming model via `target_model`
  (a model id or a tier: `frontier|strong|mid|weak`) in `capevolve.yaml`. The optimizer
  prompt and capability guidance now adapt their proposed edits to that reader — distinct
  from `optimizer_model` (which proposes edits). `cap-evolve check` warns (non-blocking)
  when the declared consuming model's tier differs from the runner's actual model. Blank
  `target_model` preserves prior behavior. Optional `target_profile_file` overrides a
  tier's built-in brief.
```

- [ ] **Step 3: Run the full core test suite**

Run: `python -m pytest core/tests/ -q`
Expected: all pass (new tests + existing suites green — no honesty-core behavior changed).

- [ ] **Step 4: Run the toy example end-to-end (regression smoke)**

Run: `bash examples/toy_calc/run.sh`
Expected: unchanged result — `baseline_val 0.0 -> test_reward 1.0` (agnostic run: no reader block, behavior identical).

- [ ] **Step 5: Commit**

```bash
git add examples/tau2_airline/capevolve.yaml CHANGELOG.md
git commit -m "feat(examples,docs): opt tau2 into gpt-oss-120b profile + CHANGELOG

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Data model (registry tiers + model_map + two config fields + resolution rule) → Tasks 1, 6. *(Registry realized as a Python module per the Global Constraint / spec's flagged YAML risk — briefs are Python data, not parsed YAML; project override is raw text.)*
- Pipeline flow (load → resolve → inject `{{TARGET_READER}}` → record) → Tasks 2, 3, 4.
- Capability-skill tier guidance (all four) → Task 7.
- Intake / report / dashboard / honesty warning → Tasks 4, 5, 6.
- Testing (resolver, backward-compat, check-warning, existing suites green) → Tasks 1, 2, 5, 8.
- Backward compatibility (blank = unchanged) → Tasks 2 (no-token test), 8 (toy_calc smoke).
- Example rollout → Task 8.

**Placeholder scan:** No `TBD`/`TODO`/"handle edge cases". Every code step shows the code; every doc step shows the prose to insert. Two notes flag runtime-verification points (SplitResult kwargs in Task 2; stub-adapter probe behavior in Task 5) with explicit fallback instructions — these are verification guards, not placeholders.

**Type consistency:** `resolve()` / `reader_block()` / `TargetProfile` / `TIERS` / `MODEL_MAP` / `DEFAULT_TIER` names are identical across Tasks 1–5. `_focus_instructions(..., target_reader="")` (Task 2) matches the call site kwarg in Task 3. `hill_climb_loop(..., target_model="", target_profile_file=None)` (Task 3) matches the argparse forwarding in `run.py` (Task 3) and the CLI flags `--target-model`/`--target-profile-file` (Task 3). `CheckReport.notes` (Task 5) matches the existing field. The `target_profile` event payload keys (Task 4) match the `TargetProfile` attributes (Task 1).

## Known follow-ups (out of scope, YAGNI)
- `gepa` and `skillopt` algorithms render agnostic (their `_focus_instructions` calls omit `target_reader`, defaulting to `""`). Extending them to thread `target_model` is a later task if those algorithms need reader-awareness.
- `cap-evolve check`'s mismatch warning only fires when the adapter implements the optional `runner_model()` hook; adapters that don't are trusted (by design — "warn, don't block").
