"""The benchmark zoo — a declarative manifest, a scaffolder, and a real verifier.

Onboarding a benchmark used to mean hand-writing a whole ``CapabilityAdapter``
subclass plus a ~100-line ``capevolve.yaml``. Comparing the two *generic* bundled
templates (``templates/adapters/jsonl_litellm`` vs ``huggingface_litellm``) shows
what actually repeats: the module preamble, the JSONL→``Task`` loop, the
error-rollout branch of ``score``, the match-mode helper, the ``Score(...)``
construction, and nearly the entire spec file. What does NOT repeat is exactly one
thing — **how you run the target agent** — plus, occasionally, a bespoke match
predicate.

So this module makes the repeating half declarative and leaves the other half as
code, deliberately:

  * ``benchmark.yaml`` declares dataset wiring, the match mode, split policy,
    metric direction and protected paths.
  * ``target.py`` defines ONE function, ``run(task, ctx, *, seed=0)``, returning
    the agent's output. Optionally ``score(task, rollout)`` when
    ``scoring: custom`` — a real predicate is real logic and a config language
    that reimplemented it would be worse than the Python it replaced.

``ManifestAdapter`` then IS the adapter: ``tasks()`` and ``score()`` come from the
manifest, ``run_target()`` delegates to ``target.run``. The project's
``adapters/adapter.py`` is a 3-line subclass, so the whole adapter contract is
satisfied without the user seeing it.

``verify`` is not a manifest parser, and it does not stop at "it ran". It runs the
real ``cap-evolve check`` gate AND a real zero-API smoke through the adapter (every
val task, twice, comparing rollouts and rewards), then **draws conclusions from the
results**: a benchmark whose seed capability already scores 1.0 has no headroom and
FAILS, and a ``score()`` that returns the same reward for a deliberately wrong
output FAILS the degenerate-scorer probe. It also requires genuinely disjoint
splits with a non-empty train, containment of every declared path inside the
project dir, and that the paths the *runtime guard actually resolves* — not the
ones the manifest claims — cover the grader, dataset and declaration. Then it
stamps ``verified.json`` with the reward it measured plus hashes of the dataset,
grader and manifest, which ``index()`` re-checks so a forged or stale stamp reads
as unverified.

Scope note on the determinism check: the two smoke passes run back-to-back in one
process, so it catches a sampler without a seed, not drift on a coarser clock (a
``run()`` keyed on ``int(time.time()) % 2`` looks identical inside one second). It
is a necessary condition, not a proof of reproducibility.

Pure stdlib (json + hashlib + importlib), like the rest of ``core``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import splits as _splits
from .adapter import IMPLEMENT_MARKER, CapabilityAdapter
from .specfile import read_yaml
from .splits import Splits, make_splits
from .types import Rollout, Score, Task

MANIFEST_NAME = "benchmark.yaml"
STAMP_NAME = "verified.json"

#: A zoo entry is ``<bench>/project/`` — the manifest, the target module, the dataset
#: and the generated ``adapters/adapter.py`` all live in ONE dir, which is also the
#: cap-evolve project dir. That is not cosmetic: #142's tamper guard can only hash
#: paths *under* the project dir, so a grader parked at the benchmark root would be
#: declared-but-unprotected (its own ``protected_paths_unmatched`` event). Keeping the
#: manifest + scorer + task data inside the project dir makes the guard cover them by
#: construction. ``<bench>/`` itself stays the run base, so run dirs land in
#: ``<bench>/run_<ts>/`` rather than polluting the zoo root.
PROJECT_SUBDIR = "project"

#: Minimum val tasks for the acceptance gate to mean anything. #113 puts the same
#: floor inside ``gate.decide`` itself; read it from ``splits`` when that has landed
#: so the two can never disagree, and fall back to the same literal when it has not.
MIN_VAL_TASKS = getattr(_splits, "MIN_VAL_TASKS", 2)

#: Manifest keys whose value is a path INSIDE the benchmark's project dir. Each one
#: is fed to ``root / value`` — and ``target_module`` is then *imported*, so an
#: unchecked value is arbitrary code execution during ``verify`` (a reviewer's
#: ``target_module: ../../pwned.py`` ran code outside the project dir and still
#: verified clean). These are validated by ``_contained`` at manifest-load time,
#: before anything is read or imported.
_PATH_FIELDS = ("tasks_file", "target_module", "capability_path", "split_ids_file")

SCORING_MODES = ("exact", "contains", "regex", "numeric", "custom")

#: Every field a manifest may declare, with its default. Anything else is a typo
#: and a hard error — a silently-ignored key in an honesty-critical config is how
#: "I declared it" and "it applied" drift apart.
_FIELDS: dict = {
    "name": "",
    "description": "",
    "tasks_file": "tasks.jsonl",
    "id_field": "id",
    "input_field": "input",
    "target_field": "target",
    "scoring": "exact",
    "metric_direction": "higher",
    "capability_path": "seed_capability",
    "target_module": "target.py",
    "split_seed": 0,
    "split_train": 0.5,
    "split_val": 0.25,
    "split_test": 0.25,
    "split_ids_file": "",
    "protected_paths": [],
    "num_trials": 1,
    "verified": False,
    #: Loud, explicit opt-out of the headroom requirement, for a reference benchmark
    #: that is genuinely saturated at baseline (a regression fixture, not an
    #: optimization target). Named for what it costs, not for what it disables: a
    #: benchmark with no headroom cannot demonstrate improvement, which is the one
    #: thing `baseline` exists to confirm, so it must be a deliberate declaration.
    "allow_saturated_baseline": False,
}


class BenchmarkError(RuntimeError):
    """A benchmark manifest is invalid, or its benchmark does not verify."""


def _contained(root: Path, value: str, key: str) -> Path:
    """``root / value``, proven to stay inside ``root``. An ALLOWLIST, not a denylist.

    Two conditions, both required: the declared value must be a *plain relative
    path* (no absolute path, no drive, no ``..`` component, no leading ``~``), and
    the resolved parent must still be inside the resolved ``root``. The second
    condition is what a string check cannot give you — it catches a symlinked
    subdirectory pointing out of the tree, which every ``..``-denylist in this repo
    has missed (six times in this batch).

    Same shape as the guard PR #210 added at ``gepa.py``: resolve, then compare
    parents. Denylisting substrings is not attempted, deliberately.
    """
    raw = str(value)
    p = Path(raw)
    if p.is_absolute() or p.drive or raw.startswith("~") or ".." in p.parts:
        raise BenchmarkError(
            f"{key}={raw!r} must be a plain relative path inside the benchmark's "
            f"project dir ({root}). Absolute paths, `~` and `..` are refused: "
            f"{key} is read (and for target_module, IMPORTED) by verify, so a value "
            "escaping the project dir would execute code and load data that #142's "
            "tamper guard structurally cannot hash — the guard only covers paths "
            "under the project dir.")
    target = (root / p).resolve()
    parent = target.parent if not target.is_dir() else target
    try:
        inside = parent.is_relative_to(root.resolve())
    except AttributeError:  # pragma: no cover — py<3.9
        inside = str(parent).startswith(str(root.resolve()))
    if not inside:
        raise BenchmarkError(
            f"{key}={raw!r} resolves to {target}, whose parent is OUTSIDE the "
            f"benchmark's project dir ({root.resolve()}) — most likely through a "
            "symlinked directory. Refused: see above.")
    return root / p


# ---------------------------------------------------------------------------
# manifest
# ---------------------------------------------------------------------------


def find_manifest(start: Path) -> Path:
    """The nearest ``benchmark.yaml`` at or above ``start``.

    Lets the scaffolded ``adapters/adapter.py`` be a bare subclass: the manifest
    lives one dir up (the project dir), which is also where the dataset, the target
    module and the seed capability live.
    """
    p = Path(start).resolve()
    for cand in (p, *p.parents) if p.is_dir() else (p.parent, *p.parents):
        m = cand / MANIFEST_NAME
        if m.is_file():
            return m
    raise BenchmarkError(
        f"no {MANIFEST_NAME} found at or above {start} — a manifest benchmark needs "
        f"one. Run `cap-evolve benchmark add <name>` to scaffold it."
    )


def load_manifest(path: Path) -> dict:
    """Read + validate a ``benchmark.yaml``. Raises ``BenchmarkError`` on anything off."""
    path = Path(path)
    if path.is_dir():
        path = path / MANIFEST_NAME
    if not path.is_file():
        raise BenchmarkError(f"missing manifest: {path}")
    try:
        raw = read_yaml(path.read_text(encoding="utf-8")) or {}
    except Exception as e:  # noqa: BLE001
        raise BenchmarkError(f"{path} did not parse as YAML: {e}") from e
    if not isinstance(raw, dict):
        raise BenchmarkError(f"{path} must be a YAML mapping, got {type(raw).__name__}")

    unknown = sorted(set(raw) - set(_FIELDS))
    if unknown:
        raise BenchmarkError(
            f"{path}: unknown manifest key(s) {unknown}. Known keys: "
            f"{sorted(_FIELDS)}. A misspelled key would be silently ignored, so this "
            "is a hard error."
        )
    m = {**_FIELDS, **raw}
    m["root"] = str(path.parent.resolve())
    if not str(m["name"]).strip():
        m["name"] = path.parent.name
    # `name` is interpolated into a generated Python docstring and a module name, so a
    # multi-line value would emit broken code rather than a broken config.
    if "\n" in str(m["name"]) or "\r" in str(m["name"]):
        raise BenchmarkError(
            f"{path}: name must be a single line (it is interpolated into the "
            "generated adapter shim's docstring and module name).")
    if str(m["scoring"]).lower() not in SCORING_MODES:
        raise BenchmarkError(
            f"{path}: scoring={m['scoring']!r} is not one of {list(SCORING_MODES)}. "
            "Use `custom` and define score(task, rollout) in the target module for a "
            "bespoke predicate."
        )
    m["scoring"] = str(m["scoring"]).lower()
    if str(m["metric_direction"]).lower() not in ("higher", "lower"):
        raise BenchmarkError(
            f"{path}: metric_direction must be 'higher' or 'lower', got "
            f"{m['metric_direction']!r}")
    m["metric_direction"] = str(m["metric_direction"]).lower()
    pp = m["protected_paths"]
    if isinstance(pp, str):
        pp = [pp]
    if not isinstance(pp, (list, tuple)):
        raise BenchmarkError(
            f"{path}: protected_paths must be a YAML list (got "
            f"{type(pp).__name__}). Write it as `protected_paths: [adapters, "
            "tasks.jsonl]`.")
    m["protected_paths"] = [str(x) for x in pp if str(x).strip()]
    # Containment, at the ONE point every caller routes through. Doing it here rather
    # than at each use site means `tasks()`, `_load_target_module`, `verify` and the
    # generated spec all inherit it — there is no second path to `root / value`.
    root = Path(m["root"])
    for key in _PATH_FIELDS:
        if str(m[key]).strip():
            _contained(root, str(m[key]), key)
    return m


def _load_target_module(manifest: dict):
    """Import the manifest's target module (the one function that is real code)."""
    mod_path = _contained(Path(manifest["root"]), str(manifest["target_module"]),
                          "target_module")
    if not mod_path.is_file():
        raise BenchmarkError(
            f"target_module {mod_path} does not exist — it must define "
            "run(task, ctx, *, seed=0). Scaffold one with `cap-evolve benchmark add`.")
    spec = importlib.util.spec_from_file_location(
        f"capevolve_bench_{manifest['name']}_target", mod_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    if not callable(getattr(mod, "run", None)):
        raise BenchmarkError(f"{mod_path} must define a callable run(task, ctx, *, seed=0)")
    # A `score()` that is not declared is a manifest that LIES about how the benchmark
    # is graded — and `benchmark list` then reports the declared mode next to a
    # verified badge for a benchmark scored by arbitrary code. Same reasoning as the
    # unknown-key hard error, one level deeper: declaration must match behaviour.
    if manifest["scoring"] != "custom" and callable(getattr(mod, "score", None)):
        raise BenchmarkError(
            f"{mod_path} defines score(task, rollout) but {MANIFEST_NAME} declares "
            f"scoring: {manifest['scoring']!r}. A code scorer silently overriding the "
            "declared mode makes the manifest — and `benchmark list` — report a "
            "grading mode that is not the one in effect. Either set `scoring: custom` "
            "to declare it, or delete score() and let the declared mode grade.")
    return mod


# ---------------------------------------------------------------------------
# scoring (the declarative half)
# ---------------------------------------------------------------------------


def _num(s: str):
    """The first number in ``s``, scientific notation included, or None."""
    m = re.search(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", str(s).replace(",", ""))
    return float(m.group()) if m else None


def match(output: str, target: str, mode: str) -> bool:
    """Does ``output`` satisfy ``target`` under ``mode``? (the built-in predicates)

    Exact semantics, because a scorer that surprises its author produces silent 0.0
    rows:

    * ``exact`` — case-insensitive equality of the stripped strings.
    * ``contains`` — the stripped target appears anywhere in the output,
      case-insensitively. An empty target is rejected in ``tasks()`` (it would match
      everything).
    * ``regex`` — ``re.search``, so the target is an UNANCHORED pattern: target ``7``
      credits ``17`` and ``0.7``. Anchor it yourself (``^7$``) when you mean exactly.
      Every target is ``re.compile``-validated at dataset load.
    * ``numeric`` — the FIRST number found in each side, compared with
      ``math.isclose(rel_tol=1e-9, abs_tol=1e-12)``: relative tolerance so large
      magnitudes are not spuriously unequal (a fixed ``abs(a-b) < 1e-9`` called
      ``1e9`` vs ``1e9 + 2e-7`` different, which is one float step), and a small
      absolute floor so values near zero still compare. ``_num`` accepts scientific
      notation and strips thousands separators; ``"in 2024 the answer is 7"`` yields
      ``2024``, not ``7``, so put the answer first or use ``regex``.
    """
    out, tgt = (output or "").strip(), (target or "").strip()
    if mode == "contains":
        return tgt.lower() in out.lower()
    if mode == "regex":
        return re.search(tgt, out) is not None
    if mode == "numeric":
        a, b = _num(out), _num(tgt)
        return (a is not None and b is not None
                and math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12))
    return out.lower() == tgt.lower()  # exact


# ---------------------------------------------------------------------------
# the adapter
# ---------------------------------------------------------------------------


class ManifestAdapter(CapabilityAdapter):
    """A full ``CapabilityAdapter`` driven by ``benchmark.yaml`` + ``target.run``.

    Subclass it with an empty body in ``adapters/adapter.py``; the manifest is found
    by walking up from that subclass's own file.
    """

    manifest_path: str | None = None  # override to point elsewhere

    def __init__(self, manifest: Path | str | None = None):
        start = manifest or self.manifest_path
        if start is None:
            try:
                start = Path(inspect.getfile(type(self)))
            except (TypeError, OSError):  # defined in a REPL/exec — fall back to cwd
                start = Path.cwd()
        self.manifest = load_manifest(find_manifest(Path(start)))
        self.root = Path(self.manifest["root"])
        self._target = _load_target_module(self.manifest)
        self._tasks: list[Task] | None = None

    # --- declarative: where tasks come from --------------------------------

    def tasks(self, split: str) -> list[Task]:
        """The tasks for ``split`` — HONOURED, not ignored.

        It used to return the full list for every split, so ``tasks("test")`` handed
        out the sealed test set to any caller who trusted the base contract. The
        manifest already declares the seed, ratios and any pinned id file, so the same
        partition ``verify`` and the run dir use is derivable here. ``harness`` still
        asks for ``"all"`` and filters by the frozen ids, so nothing re-splits mid-run.
        """
        allt = self._all_tasks()
        if str(split).lower() in ("all", ""):
            return allt
        sp = self._splits([t.id for t in allt])
        ids = set(sp.ids(str(split).lower()))
        return [t for t in allt if t.id in ids]

    def _splits(self, ids: list[str]) -> Splits:
        """The manifest's declared partition: pinned ids when given, else seed+ratios."""
        m = self.manifest
        if str(m["split_ids_file"]).strip():
            sf = _contained(self.root, str(m["split_ids_file"]), "split_ids_file")
            sd = json.loads(sf.read_text(encoding="utf-8"))
            return Splits(train=[str(x) for x in sd.get("train", [])],
                          val=[str(x) for x in sd.get("val", [])],
                          test=[str(x) for x in sd.get("test", [])],
                          seed=int(m["split_seed"]))
        return make_splits(ids, seed=int(m["split_seed"]),
                           ratios=(float(m["split_train"]), float(m["split_val"]),
                                   float(m["split_test"])))

    def _all_tasks(self) -> list[Task]:
        if self._tasks is not None:
            return list(self._tasks)
        m = self.manifest
        path = _contained(self.root, str(m["tasks_file"]), "tasks_file")
        if not path.is_file():
            raise BenchmarkError(
                f"dataset file missing: {path} (declared as tasks_file="
                f"{m['tasks_file']!r} in {self.root / MANIFEST_NAME}). Create it — one "
                'JSON object per line, e.g. {"id": "t1", "input": "...", '
                '"target": "..."} — or point tasks_file at the real dataset.')
        out: list[Task] = []
        seen: set[str] = set()
        by_content: dict = {}
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception as e:  # noqa: BLE001
                raise BenchmarkError(f"{path}:{lineno} is not valid JSON: {e}") from e
            tid = str(d.get(m["id_field"], "") or f"t{lineno}")
            if tid in seen:
                raise BenchmarkError(
                    f"{path}:{lineno} duplicate task id {tid!r} — ids key the splits, "
                    "so duplicates would silently drop tasks and leak across splits.")
            seen.add(tid)
            # CONTENT duplicates, not just id duplicates. Fresh ids on identical
            # (input, target) rows split cleanly and pass every honesty check, but a
            # val task that is byte-identical to a train task is memorization dressed
            # as generalization — the id-level guard below could not see it, so the
            # reviewer's duplicate-every-row attack verified clean.
            key = (json.dumps(d.get(m["input_field"]), sort_keys=True, default=str),
                   json.dumps(d.get(m["target_field"]), sort_keys=True, default=str))
            if key in by_content:
                raise BenchmarkError(
                    f"{path}:{lineno} task {tid!r} is a CONTENT duplicate of "
                    f"{by_content[key]!r}: identical input and target under a different "
                    "id. Distinct ids make it split cleanly, so the same task can land "
                    "in train and val — the gate then rewards memorization, and the "
                    "sealed test number measures recall of a seen row. De-duplicate the "
                    "dataset.")
            by_content[key] = tid
            tgt = d.get(m["target_field"])
            # An absent/empty target is a FREE POINT under `contains` (`"" in
            # anything` is True) and a match-everything pattern under `regex`. A
            # dataset row missing its answer must be an error, not a gift.
            if m["scoring"] != "custom" and not str(tgt if tgt is not None else "").strip():
                raise BenchmarkError(
                    f"{path}:{lineno} has no {m['target_field']!r} value (got {tgt!r}), "
                    f"but scoring is {m['scoring']!r} — an empty target scores 1.0 for "
                    "free under `contains`/`regex`, silently inflating the benchmark. "
                    "Give the row a target, or use `scoring: custom` if the answer is "
                    "not a single field.")
            if m["scoring"] == "regex":
                try:
                    re.compile(str(tgt))
                except re.error as e:
                    raise BenchmarkError(
                        f"{path}:{lineno} target {str(tgt)!r} is not a valid regex "
                        f"({e}) — under `scoring: regex` the target IS the pattern. "
                        "Validated at load so it fails as a dataset error rather than "
                        "mid-eval inside score().") from e
            out.append(Task(id=tid, input=d.get(m["input_field"]),
                            target=tgt,
                            metadata={k: v for k, v in d.items()
                                      if k not in (m["id_field"], m["input_field"],
                                                   m["target_field"])}))
        if not out:
            raise BenchmarkError(f"{path} contains no tasks")
        self._tasks = out
        return list(out)

    # --- code: how the target runs -----------------------------------------

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        res = self._target.run(task, ctx, seed=seed)
        if isinstance(res, Rollout):
            return res
        if isinstance(res, dict):
            return Rollout(task_id=task.id, **{k: v for k, v in res.items()
                                               if k != "task_id"})
        return Rollout(task_id=task.id, output=res, trace=res)

    # --- declarative (or custom code): scoring ------------------------------

    def score(self, task: Task, rollout: Rollout) -> Score:
        custom = getattr(self._target, "score", None)
        if self.manifest["scoring"] == "custom":
            if not callable(custom):
                raise BenchmarkError(
                    f"{self.manifest['target_module']} declares scoring: custom but "
                    "defines no score(task, rollout).")
            return custom(task, rollout)
        # No `if callable(custom)` fallthrough: an undeclared score() is refused at
        # module load (_load_target_module), so reaching here means the declared mode
        # IS the effective mode. `benchmark list`'s `scoring` column is now honest.
        if rollout.error:
            return Score(task_id=task.id, reward=0.0, trial_rewards=[0.0],
                         feedback=f"Rollout failed ({rollout.error}); infrastructure "
                                  "noise, not a capability defect — do not optimize "
                                  "against it.")
        mode = self.manifest["scoring"]
        ok = match(str(rollout.output or ""), str(task.target), mode)
        got = str(rollout.output or "").strip().replace("\n", " ")[:200]
        fb = ("correct" if ok else
              f"output did not satisfy the expected answer under '{mode}' scoring; "
              f"the agent produced {got!r}. Guide it toward the required "
              "answer format/content — never hard-code answers.")
        return Score(task_id=task.id, reward=1.0 if ok else 0.0, feedback=fb,
                     trial_rewards=[1.0 if ok else 0.0])

    # The seed capability is read straight out of ``ctx`` (the candidate dir) by
    # ``target.run``, so making a candidate live needs no global side effect.
    def apply(self, candidate_dir, edits: dict | None = None) -> None:
        self.materialize(candidate_dir, edits)


# ---------------------------------------------------------------------------
# spec generation — the other half of the boilerplate
# ---------------------------------------------------------------------------


def spec_from_manifest(manifest: dict) -> str:
    """Render the ``capevolve.yaml`` a manifest implies (so nobody authors one)."""
    m = manifest
    # The UNION, not the manifest's list: #197's protected_paths replaces its defaults
    # wholesale, so emitting only the declared four silently switched off the answer-key
    # globs. verify now asserts against this same generated file, which is what the
    # runtime guard actually reads.
    prot = effective_protected(m)
    return f"""# GENERATED from {MANIFEST_NAME} by `cap-evolve benchmark add` — edit the
# manifest and re-run `cap-evolve benchmark add --refresh`, not this file.
capabilities: [system-prompt]
capability_path: {m['capability_path']}
actions: [edit]
optimizer_skill: mock
optimizer_model: ""
algorithm_skill: hill-climb
algorithm_focus: all
dataset_source: adapter
split_seed: {m['split_seed']}
split_train: {m['split_train']}
split_val: {m['split_val']}
split_test: {m['split_test']}
split_ids_file: "{m['split_ids_file']}"
num_trials: {m['num_trials']}
metric_directions: [{m['metric_direction']}]
gate_mode: paired
gate_k_se: 1.0
max_iterations: 5
stall: 2
store: copy
# Declared by the manifest; #142's tamper guard hashes exactly these at baseline
# and re-hashes them after every optimizer step.
protected_paths: [{', '.join(prot)}]
"""


def default_protected(manifest: dict) -> list[str]:
    """The paths a manifest benchmark must protect: grader + dataset + declaration."""
    out = ["adapters", MANIFEST_NAME, str(manifest["target_module"]),
           str(manifest["tasks_file"])]
    if str(manifest["split_ids_file"]).strip():
        out.append(str(manifest["split_ids_file"]))
    return out


def effective_protected(manifest: dict) -> list[str]:
    """What the generated spec must declare: the manifest's list UNIONED with the
    layout defaults — #197's globs plus this benchmark's grader/dataset/declaration.

    ADDITIVE, deliberately. #197's ``protected_paths`` *replaces* its defaults
    wholesale, so a manifest that declared its four known paths silently switched off
    the ``*gold*`` answer-key globs — a reviewer added ``helpers.py``, ``scorer2.py``
    and ``answers_gold.json``, tampered with all three, and nothing noticed. Union is
    the only default that fails safe: declaring one more path can never *un*protect
    something. A benchmark that genuinely needs a default off edits the generated
    spec, which is now a supported override (see ``add``).
    """
    return list(dict.fromkeys([*manifest["protected_paths"],
                               *default_protected(manifest),
                               *_protect_default_globs()]))


def _protect_default_globs() -> tuple:
    """#197's default globs when ``protect`` is importable, else its literal set.

    Duplicated-with-fallback rather than imported-hard so this module still works on a
    pre-#142 checkout (the branch merges in either order). ``protect`` wins when
    present, so the two can never drift once merged.
    """
    try:
        from . import protect
        return tuple(protect._DEFAULT_GLOBS)
    except (ImportError, AttributeError):  # pragma: no cover — pre-#142 checkout
        return ("adapters", "capevolve.yaml",
                "*gold*.json", "*gold*.jsonl", "*gold*.yaml", "*gold*.yml",
                "*gold*.csv", "*gold*.txt",
                "**/*gold*.json", "**/*gold*.jsonl", "**/*gold*.yaml",
                "**/*gold*.yml", "**/*gold*.csv", "**/*gold*.txt")


#: Data suffixes that could hold an answer key. Used by the under-declaration sweep,
#: which flags any *code* or *gold-ish data* file in the project dir that the runtime
#: guard would not hash — the four names ``verify`` used to hardcode covered only the
#: two committed examples, so anything a third author added was neither protected nor
#: flagged.
_GOLDISH_SUFFIXES = (".json", ".jsonl", ".yaml", ".yml", ".csv", ".tsv", ".txt")
_GOLDISH_HINTS = ("gold", "answer", "label", "solution", "truth", "key", "expected")


def resolve_declared(project_dir: Path) -> set:
    """``{project-relative path}`` the tamper guard will hash, read from the GENERATED
    ``capevolve.yaml`` — the artifact the runtime guard reads.

    Delegates to ``protect.resolve_protected`` when #142 has landed. The fallback is a
    deliberately small re-implementation (dirs expand to their subtree, globs via
    ``Path.glob``) so ``verify``'s protected-paths and under-declaration steps are not
    silently skipped on a pre-#142 checkout — the two branches merge in either order,
    and a guard that quietly does nothing is the exact failure this review found.
    """
    pdir = Path(project_dir).resolve()
    try:
        from . import protect
        return set(protect.resolve_protected(pdir))
    except ImportError:  # pragma: no cover — pre-#142 checkout
        pass
    cfg = pdir / "capevolve.yaml"
    declared: list = []
    if cfg.is_file():
        d = (read_yaml(cfg.read_text(encoding="utf-8")) or {}).get("protected_paths")
        if isinstance(d, str):
            d = [d]
        declared = [str(x) for x in d if str(x).strip()] if isinstance(d, (list, tuple)) else []
    out: set = set()

    def _add(p: Path) -> None:
        if not p.is_file() or "__pycache__" in p.parts:
            return
        try:
            rel = p.relative_to(pdir)
        except ValueError:
            return
        out.add(str(rel).replace("\\", "/"))

    for pat in declared:
        direct = pdir / str(pat).lstrip("/")
        if direct.is_dir():
            for c in direct.rglob("*"):
                _add(c)
        elif direct.is_file():
            _add(direct)
        else:
            for hit in pdir.glob(str(pat).lstrip("/")):
                if hit.is_dir():
                    for c in hit.rglob("*"):
                        _add(c)
                else:
                    _add(hit)
    return out


def under_declared(project_dir: Path, manifest: dict, protected: set) -> list[str]:
    """Files inside the project dir that the runtime guard will NOT hash but should.

    Everything the optimizer must not rewrite is code or ground truth. So: every
    ``.py`` in the project dir (a helper the grader imports is as much the grader as
    ``adapter.py``), plus every data file whose name suggests an answer key. The seed
    capability dir is excluded — it is the target, the one thing that MUST be
    writable — and so are run dirs and caches.

    Returns project-relative paths, sorted. Detection, not silent protection: an
    author who genuinely wants a file writable declares it, rather than finding out
    from a tampered run.
    """
    pdir = Path(project_dir).resolve()
    cap = (pdir / str(manifest["capability_path"])).resolve()
    out = []
    for p in sorted(pdir.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(pdir)
        parts = rel.parts
        if any(x in (".git", "__pycache__", ".pytest_cache", ".mypy_cache",
                     ".ruff_cache") or x.startswith("run_") for x in parts):
            continue
        try:
            if p.resolve().is_relative_to(cap):
                continue  # the seed capability IS the target
        except (AttributeError, OSError, ValueError):  # pragma: no cover
            pass
        name = rel.name.lower()
        goldish = (p.suffix.lower() in _GOLDISH_SUFFIXES
                   and any(h in name for h in _GOLDISH_HINTS))
        if not (p.suffix == ".py" or goldish):
            continue
        if str(rel).replace("\\", "/") not in protected:
            out.append(str(rel).replace("\\", "/"))
    return out


# ---------------------------------------------------------------------------
# add (scaffold)
# ---------------------------------------------------------------------------

_TARGET_STUB = '''"""The ONE piece of a benchmark that is real code, not config.

``run(task, ctx, *, seed=0)`` runs the agent under test and returns its output.
``ctx`` is the live candidate dir — read the artifact being optimized out of it
(here: ``prompt.txt``). Return a str, or a dict of ``Rollout`` fields
(``output``/``trace``/``cost_usd``/``tokens``/``error``/``metadata``).

Everything else — dataset wiring, splits, scoring mode, metric direction,
protected paths — is declared in ``{manifest}``.

If your runner is STOCHASTIC you MUST forward ``seed`` to it, or pass^k and the
significance gate degenerate. Optionally define ``score(task, rollout) -> Score``
for a bespoke predicate (set ``scoring: custom``).
"""

from __future__ import annotations

from pathlib import Path


def run(task, ctx, *, seed: int = 0):
    # TODO replace this placeholder runner with a real one (an LLM call, a
    # benchmark harness invocation, a subprocess). The placeholder echoes the
    # task input when the candidate prompt asks it to, so the scaffold is a
    # complete, runnable, verifiable benchmark from the first minute.
    prompt = (Path(ctx) / "prompt.txt").read_text(encoding="utf-8")
    if "[ECHO]" in prompt:
        return str(task.input)
    return f"I am not sure about {{task.input}}."
'''

_PROMPT_STUB = ("You are a helpful assistant. Answer the user's question.\n")

_README = """# Benchmark: {name}

{description}

Declared in [`project/{manifest}`](project/{manifest}); the only code is
[`project/{target}`](project/{target}) — one function, `run(task, ctx, *, seed=0)`.

Everything under `project/` is the cap-evolve project dir, so #142's tamper guard
hashes the manifest, the scorer and the dataset by construction.

```bash
cap-evolve benchmark verify {name}          # check gate + real zero-API smoke eval
cap-evolve run --spec {name}/project/capevolve.yaml --project {name}/project
```
"""


def add(dest: Path, *, name: str = "", description: str = "", from_zoo: str = "",
        n_tasks: int = 8, refresh: bool = False) -> dict:
    """Scaffold a benchmark at ``dest`` (or copy ``from_zoo``), wired end to end.

    Layout: ``dest/project/`` holds the manifest, the one-function target module, the
    dataset, the seed capability AND the generated ``adapters/adapter.py`` +
    ``capevolve.yaml``; ``dest/`` is the run base. Everything the grader depends on
    is therefore inside the project dir, which is the only place #142's tamper guard
    can hash. ``refresh`` regenerates just the derived files from an existing manifest.
    """
    dest = Path(dest)
    name = name or dest.name
    proj = dest / PROJECT_SUBDIR
    if from_zoo:
        import shutil
        src = resolve(from_zoo)
        if dest.exists() and not refresh:
            raise BenchmarkError(f"{dest} already exists")
        shutil.copytree(src, dest, dirs_exist_ok=refresh)
    elif not (proj / MANIFEST_NAME).exists():
        if proj.exists() and any(proj.iterdir()):
            raise BenchmarkError(f"{proj} exists and is not empty")
        proj.mkdir(parents=True, exist_ok=True)
        (proj / MANIFEST_NAME).write_text(_manifest_text(name, description),
                                          encoding="utf-8")
        (proj / "target.py").write_text(
            _TARGET_STUB.format(manifest=MANIFEST_NAME), encoding="utf-8")
        (proj / "tasks.jsonl").write_text("".join(
            json.dumps({"id": f"t{i}", "input": f"question {i}",
                        "target": f"question {i}"}) + "\n"
            for i in range(1, n_tasks + 1)), encoding="utf-8")
        cap = proj / "seed_capability"
        cap.mkdir(exist_ok=True)
        (cap / "prompt.txt").write_text(_PROMPT_STUB, encoding="utf-8")
        (dest / "README.md").write_text(_README.format(
            name=name, description=description or "(describe the benchmark here)",
            manifest=MANIFEST_NAME, target="target.py"), encoding="utf-8")
    elif not refresh:
        raise BenchmarkError(
            f"{proj / MANIFEST_NAME} already exists — pass --refresh to regenerate "
            "the derived project files from it.")

    m = load_manifest(proj)
    (proj / "adapters").mkdir(parents=True, exist_ok=True)
    # The whole adapter: the manifest is found by walking up from this file.
    shim = proj / "adapters" / "adapter.py"
    generated = _shim_text(m)
    kept = []
    # THE OVERRIDE PATH. `--refresh` used to overwrite this file unconditionally, so an
    # author who overrode one generated hook (`trajectories()`, a custom `live()`) lost
    # it silently the next time they edited the manifest — "hand-edit a file the tool
    # overwrites" was the only answer to "I need to override one method". Now a shim
    # whose bytes differ from the generated text is treated as AUTHORED and left alone;
    # `capevolve.yaml` is still re-derived, since it holds no logic to override. The
    # kept files are reported, so a stale hand-edited shim is visible, not silent.
    if shim.is_file() and shim.read_text(encoding="utf-8") != generated:
        kept.append("adapters/adapter.py")
    else:
        shim.write_text(generated, encoding="utf-8")
    (proj / "capevolve.yaml").write_text(spec_from_manifest(m), encoding="utf-8")
    info = {"name": m["name"], "dir": str(dest), "project": str(proj),
            "manifest": str(proj / MANIFEST_NAME), "files": sorted(
                str(p.relative_to(dest)) for p in dest.rglob("*") if p.is_file())}
    if kept:
        info["kept_hand_edited"] = kept
        info["note"] = (
            f"left {kept} untouched: its content differs from the generated shim, so it "
            "is treated as an authored override. Delete it and re-run --refresh to go "
            "back to the generated version.")
    return info


def _shim_text(manifest: dict) -> str:
    """The generated ``adapters/adapter.py``. Compared byte-wise by ``--refresh`` to
    tell an untouched shim from an authored override."""
    return ("from cap_evolve.zoo import ManifestAdapter\n\n\n"
            "class Adapter(ManifestAdapter):\n"
            f'    """{manifest["name"]} — everything is declared in '
            f'../{MANIFEST_NAME}."""\n\n'
            "    manifest_path = __file__\n")


def _yaml_scalar(value: str) -> str:
    """One YAML scalar, quoted so it cannot become extra keys.

    ``json.dumps`` emits a double-quoted string with ``\\n``/``"``/``\\`` escaped, and
    YAML's double-quoted style is a superset of JSON string syntax — so a JSON string
    IS a valid single-line YAML scalar. That is the whole fix for a ``--description``
    containing a newline, which previously redefined manifest keys below it. Free via
    stdlib; a dumper dependency would buy nothing.
    """
    return json.dumps(str(value))


def _manifest_text(name: str, description: str) -> str:
    return f"""# cap-evolve benchmark manifest — the DECLARATIVE half of a benchmark.
# The only code is target.py's run(task, ctx, *, seed=0). Flat keys only, so the
# zero-dependency spec reader can parse it.
name: {_yaml_scalar(name)}
description: {_yaml_scalar(description or "TODO one line: what capability this benchmark measures")}

# --- dataset ---------------------------------------------------------------
tasks_file: tasks.jsonl        # one JSON object per line
id_field: id
input_field: input
target_field: target

# --- scoring ---------------------------------------------------------------
scoring: exact                 # exact | contains | regex | numeric | custom
metric_direction: higher       # higher | lower

# --- what is optimized -----------------------------------------------------
capability_path: seed_capability
target_module: target.py

# --- splits (seeded once; test is sealed) ----------------------------------
split_seed: 0
split_train: 0.5
split_val: 0.25
split_test: 0.25
split_ids_file: ""             # pin an official split instead of ratios
num_trials: 1                  # raise if the runner is stochastic

# --- protected paths (#142 tamper guard hashes exactly these) --------------
protected_paths: [adapters, {MANIFEST_NAME}, target.py, tasks.jsonl]

verified: false                # `cap-evolve benchmark verify` flips this
"""


# ---------------------------------------------------------------------------
# the zoo index
# ---------------------------------------------------------------------------


def zoo_dir() -> Path:
    """The bundled ``benchmarks/`` library (env override for a private zoo)."""
    import os
    env = os.environ.get("CAPEVOLVE_BENCHMARKS_DIR")
    if env and Path(env).is_dir():
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        d = parent / "benchmarks"
        if d.is_dir():
            return d
    return Path("benchmarks")


def index() -> list[dict]:
    """Every benchmark in the zoo, with its verified status (read from DISK).

    The stamp is read from ``verified.json``, not from the manifest's ``verified:``
    flag — a committed flag is a claim, the stamp is evidence, and the stamp carries
    the reward that was actually measured.
    """
    out = []
    d = zoo_dir()
    if not d.is_dir():
        return out
    for mpath in sorted(d.glob(f"*/{PROJECT_SUBDIR}/{MANIFEST_NAME}")):
        try:
            m = load_manifest(mpath)
        except BenchmarkError as e:
            out.append({"name": mpath.parent.parent.name, "error": str(e)})
            continue
        bench = mpath.parent.parent
        # The stamp is only evidence if it is a real verify result AND still matches the
        # files on disk. `stamp_state` re-hashes; a forged or stale stamp reads as
        # unverified with the reason visible in `stale_reason`.
        state = stamp_state(bench, m)
        st = state.get("stamp") or {}
        row = {"name": m["name"], "dir": str(bench),
               "description": m["description"],
               # The EFFECTIVE grading mode. `scoring: exact` with a code scorer is now
               # refused at load, so the declared mode is the one in effect — but say so
               # explicitly rather than making the reader infer it.
               "scoring": m["scoring"],
               "metric_direction": m["metric_direction"],
               "verified": state["verified"],
               "verified_at": st.get("at"), "smoke_val_reward": st.get("val_reward"),
               "n_tasks": st.get("n_tasks")}
        if not state["verified"] and state["why"]:
            row["stale"] = bool(state["stale"])
            row["stale_reason"] = state["why"]
        if bool(m["allow_saturated_baseline"]):
            row["allow_saturated_baseline"] = True
        out.append(row)
    return out


def resolve(name_or_path: str) -> Path:
    """A benchmark dir from a zoo name or a filesystem path."""
    for cand in (Path(name_or_path), zoo_dir() / name_or_path):
        if (cand / PROJECT_SUBDIR / MANIFEST_NAME).is_file():
            return cand
        if (cand / MANIFEST_NAME).is_file():   # given the project dir directly
            return cand.parent
    raise BenchmarkError(
        f"no benchmark {name_or_path!r}: no {PROJECT_SUBDIR}/{MANIFEST_NAME} under "
        f"{Path(name_or_path).resolve()} or {zoo_dir() / name_or_path}. Zoo entries: "
        f"{[b['name'] for b in index()]}")


# ---------------------------------------------------------------------------
# verify — the part that must actually verify
# ---------------------------------------------------------------------------


@dataclass
class VerifyReport:
    name: str = ""
    ok: bool = False
    steps: list = field(default_factory=list)   # what was EXECUTED, in order
    problems: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    val_reward: float | None = None
    n_tasks: int | None = None
    splits: dict = field(default_factory=dict)
    protected: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"name": self.name, "ok": self.ok, "steps": self.steps,
                "problems": self.problems, "notes": self.notes,
                "val_reward": self.val_reward, "n_tasks": self.n_tasks,
                "splits": self.splits, "protected": self.protected}


#: The deliberately-wrong output handed to ``score()`` by the degenerate-scorer probe.
#: Chosen to satisfy no plausible target under any built-in mode, and to be obvious in
#: a failure message.
_WRONG_SENTINEL = "__CAPEVOLVE_DELIBERATELY_WRONG__"


def _rollout_fingerprint(r: Rollout) -> str:
    """Hash of everything about a rollout that a deterministic runner must repeat.

    ``cost_usd``/``tokens`` are excluded: a real metered runner reports them with
    float jitter, and they are not the thing being verified.
    """
    d = r.to_dict()
    d.pop("cost_usd", None)
    d.pop("tokens", None)
    return hashlib.sha256(json.dumps(d, sort_keys=True, default=str)
                          .encode("utf-8")).hexdigest()[:16]


def verify(bench_dir: Path, *, smoke_tasks: int = 0) -> VerifyReport:
    """Prove a benchmark works: check gate + REAL smoke eval + honest splits.

    Executes, in order:
      1. manifest parse + field validation;
      2. dataset load through the real adapter (missing/duplicate/empty → fail);
      3. ``cap_evolve.check.run_check`` on the generated project (stubs, task
         stability, scorer determinism, materialize);
      4. seeded (or pinned) split + the honesty floor: ``MIN_VAL_TASKS`` val, a
         non-empty sealed test, a non-empty train, and genuine disjointness — all
         asserted on the REALIZED split, so ``train == val == test`` fails;
      5. a REAL zero-API smoke: every val task through ``live`` → ``run_target`` →
         ``score``, TWICE, comparing rollout fingerprints and rewards — this is what
         catches a non-deterministic ``run_target``, which ``check`` never runs;
      5a. HEADROOM: a seed capability that already scores 1.0 everywhere fails,
         unless the manifest declares ``allow_saturated_baseline: true``;
      5b. the DEGENERATE-SCORER probe: a deliberately wrong output must score
         differently from the real rollout on at least one task;
      6. protected paths, checked against what ``protect.resolve_protected`` actually
         resolves from the generated spec (the artifact the runtime guard reads),
         plus a sweep for any ``.py`` / answer-key-ish file the guard would miss.

    ``smoke_tasks`` caps step 5 (0 = the whole val split).
    """
    rep = VerifyReport()
    bench_dir = Path(bench_dir)
    proj = bench_dir / PROJECT_SUBDIR

    # 1. manifest
    try:
        m = load_manifest(proj)
    except BenchmarkError as e:
        rep.problems.append(str(e))
        return rep
    rep.name = m["name"]
    rep.steps.append("manifest parsed + validated")

    if not (proj / "adapters" / "adapter.py").is_file():
        rep.problems.append(
            f"no generated project at {proj} — run `cap-evolve benchmark add "
            f"{bench_dir} --refresh` to regenerate the adapter shim + capevolve.yaml "
            "from the manifest.")
        return rep

    # 2. dataset, through the real adapter
    from .check import load_adapter
    try:
        adapter = load_adapter(proj)
        tasks = adapter.tasks("all")
    except Exception as e:  # noqa: BLE001
        rep.problems.append(f"dataset/adapter load failed: {e}")
        return rep
    rep.n_tasks = len(tasks)
    rep.steps.append(f"dataset loaded through the adapter: {len(tasks)} task(s)")

    # 3. the real check gate
    from .check import run_check
    creport = run_check(proj)
    rep.steps.append("cap-evolve check executed on the generated project")
    if not creport.ok:
        rep.problems.extend(f"cap-evolve check: {p}" for p in creport.problems)
    rep.notes.extend(f"check: {n}" for n in creport.notes)

    # 4. honest splits — a benchmark must not be able to ship without them
    if str(m["split_ids_file"]).strip():
        sf = _contained(proj, str(m["split_ids_file"]), "split_ids_file")
        if not sf.is_file():
            rep.problems.append(f"split_ids_file {sf} does not exist")
            return rep
        sd = json.loads(sf.read_text(encoding="utf-8"))
        # A real ``Splits``, not a throwaway ``type("S", (), ...)``: the dataclass is
        # what every other honesty check in the repo consumes, so the seal semantics
        # and the id types are the same ones ``harness.ensure_splits`` sees.
        sp = Splits(train=[str(x) for x in sd.get("train", [])],
                    val=[str(x) for x in sd.get("val", [])],
                    test=[str(x) for x in sd.get("test", [])],
                    seed=int(m["split_seed"]))
    else:
        sp = make_splits([t.id for t in tasks], seed=int(m["split_seed"]),
                         ratios=(float(m["split_train"]), float(m["split_val"]),
                                 float(m["split_test"])))
    rep.splits = {"train": len(sp.train), "val": len(sp.val), "test": len(sp.test)}
    rep.steps.append(f"splits computed: {rep.splits}")

    # Disjointness + a non-empty train, asserted on the REALIZED split (not on the
    # declared ratios): whatever produced `sp` — pinned ids or ratios — is what the
    # run will use. #99 found the repo's own headline tau^2 number came from a
    # train==val==test==50 run, so "the sealed number is a fit metric" is not a
    # hypothetical failure mode; it already happened once here.
    tr, va, te = set(sp.train), set(sp.val), set(sp.test)
    leak = sorted(te & (tr | va))
    if leak:
        rep.problems.append(
            f"test split OVERLAPS train/val on {len(leak)} task id(s) (e.g. "
            f"{leak[:5]}) — the 'sealed' number would be measured on data the "
            "optimizer trained against, making it a fit metric, not a held-out "
            "result. train/val/test must be disjoint.")
    tv = sorted(tr & va)
    if tv:
        rep.problems.append(
            f"train and val OVERLAP on {len(tv)} task id(s) (e.g. {tv[:5]}) — the "
            "acceptance gate would score candidates on the very tasks reflection "
            "read, so every accept is measuring memorization.")
    if not tr:
        rep.problems.append(
            "train split is EMPTY — there is nothing for the optimizer to reflect "
            f"over, so no candidate can be proposed from evidence. Raise split_train "
            f"above {m['split_train']} in {proj / MANIFEST_NAME}"
            + (" or add train ids to the split_ids_file."
               if str(m["split_ids_file"]).strip() else "."))
    if len(sp.val) < MIN_VAL_TASKS:
        rep.problems.append(
            f"val split has {len(sp.val)} task(s), below the honest-gate minimum of "
            f"{MIN_VAL_TASKS}: SE(Δ) would have {max(len(sp.val) - 1, 0)} degrees of "
            f"freedom, so every accept/reject is meaningless (the gate itself refuses "
            f"this mid-run). This benchmark has {len(tasks)} task(s) total — add more "
            f"tasks, or raise split_val above {m['split_val']} in "
            f"{proj / MANIFEST_NAME}.")
    if not sp.test:
        rep.problems.append(
            "test split is EMPTY — there is no sealed held-out set, so this benchmark "
            f"cannot produce an honest headline number. Add tasks or raise split_test "
            f"above {m['split_test']}.")
    if rep.problems:
        return rep  # a dishonest split makes the smoke number meaningless

    # 5. a REAL smoke eval through the adapter, twice.
    val_ids = set(sp.val)
    smoke = [t for t in tasks if t.id in val_ids]
    if smoke_tasks:
        smoke = smoke[:smoke_tasks]
    cap = proj / str(m["capability_path"])
    if not cap.is_dir():
        rep.problems.append(
            f"capability_path {cap} is not a directory — the optimizer needs a seed "
            "artifact dir to edit.")
        return rep
    passes: list[dict] = []
    for attempt in (1, 2):
        got: dict = {}
        try:
            with adapter.live(cap) as ctx:
                for t in smoke:
                    r = adapter.run_target(t, ctx, seed=0)
                    s = adapter.score(t, r)
                    got[t.id] = (_rollout_fingerprint(r), round(float(s.reward), 9))
        except NotImplementedError as e:
            rep.problems.append(
                f"smoke eval pass {attempt} hit an unimplemented method ({e}) — "
                f"implement it in {m['target_module']} (run/score) before verifying.")
            return rep
        except Exception as e:  # noqa: BLE001
            rep.problems.append(
                f"smoke eval pass {attempt} raised {type(e).__name__}: {e} — the "
                "benchmark cannot be run, so it cannot be verified.")
            return rep
        passes.append(got)
    rep.steps.append(
        f"REAL smoke eval: {len(smoke)} val task(s) x 2 passes through live() -> "
        "run_target() -> score()")
    drift = sorted(k for k in passes[0] if passes[0][k] != passes[1][k])
    if drift:
        rep.problems.append(
            f"NON-DETERMINISTIC: {len(drift)} task(s) produced a different rollout or "
            f"reward on an identical re-run with seed=0 — e.g. {drift[:3]}: "
            f"{[passes[0][k] for k in drift[:3]]} vs {[passes[1][k] for k in drift[:3]]}. "
            "A benchmark whose rollouts drift at a fixed seed cannot produce a "
            f"reproducible number. Make {m['target_module']}'s run() a function of "
            "(task, candidate, seed) only, and forward `seed` to any sampler.")
    rewards = [v[1] for v in passes[0].values()]
    rep.val_reward = round(sum(rewards) / len(rewards), 6) if rewards else None
    rep.notes.append(f"smoke val reward (seed capability) = {rep.val_reward}")

    # 5a. HEADROOM. verify already had this signal and only *noted* it, so a score()
    # hard-wired to 1.0 and a run() returning task.target both verified clean. A
    # benchmark whose seed capability is already perfect cannot demonstrate an
    # improvement — the one thing `baseline` exists to confirm — so it is a problem.
    if rewards and min(rewards) >= 1.0:
        if bool(m["allow_saturated_baseline"]):
            rep.notes.append(
                "SATURATED BASELINE ALLOWED: the seed capability scores 1.0 on every "
                "smoke task and the manifest declares allow_saturated_baseline: true. "
                "This benchmark has NO headroom and cannot show an improvement; it is "
                "only usable as a regression fixture.")
        else:
            rep.problems.append(
                f"NO HEADROOM: the seed capability already scores {rep.val_reward} on "
                f"all {len(rewards)} smoke val task(s). A benchmark that is perfect at "
                "baseline cannot demonstrate an improvement, so optimizing it is "
                "meaningless — and this is the signature of the two commonest reward "
                "hacks: a score() hard-wired to a constant, and a run() that returns "
                "task.target (or reads the answer key off disk). Make the tasks harder, "
                "weaken the seed capability, or — for a genuinely saturated reference "
                "fixture — declare `allow_saturated_baseline: true` in "
                f"{proj / MANIFEST_NAME}.")

    # 5b. DEGENERATE-SCORER PROBE. Hand `score()` a synthetically CORRECT rollout (the
    # task's own target as the output — that is what "correct" means for every declared
    # mode) and a deliberately WRONG one, and require the two rewards to differ on at
    # least one task.
    #
    # Note the comparison is correct-vs-wrong, NOT wrong-vs-the-seed-rollout: the seed
    # capability is usually already wrong, so comparing against it would score 0.0 both
    # times on a perfectly good benchmark. Correct-vs-wrong is a property of the SCORER
    # alone, so it holds at any baseline — which is what catches a
    # `return Score(reward=1.0)` on a benchmark whose baseline is imperfect, a case the
    # headroom rule (5a) cannot see.
    if smoke:
        probe: dict = {}
        try:
            for t in smoke:
                good = Rollout(task_id=t.id, output=str(t.target),
                               trace="__CAPEVOLVE_PROBE_CORRECT__")
                bad = Rollout(task_id=t.id, output=_WRONG_SENTINEL,
                              trace=_WRONG_SENTINEL)
                probe[t.id] = (round(float(adapter.score(t, good).reward), 9),
                               round(float(adapter.score(t, bad).reward), 9))
        except Exception as e:  # noqa: BLE001
            rep.problems.append(
                f"degenerate-scorer probe raised {type(e).__name__}: {e} — score() must "
                "handle any rollout it is handed (a real run produces wrong answers by "
                "definition), so a scorer that crashes on one cannot grade a run.")
            return rep
        rep.steps.append(
            f"degenerate-scorer probe: {len(smoke)} task(s) scored with a correct vs a "
            "deliberately-wrong output")
        discriminating = sorted(k for k, (g, b) in probe.items() if g != b)
        if not discriminating:
            rep.problems.append(
                "SCORER DOES NOT DISCRIMINATE: a correct output and a deliberately "
                f"wrong one ({_WRONG_SENTINEL!r}) received the SAME reward on every one "
                f"of {len(smoke)} smoke task(s) — e.g. "
                f"{ {k: {'correct': probe[k][0], 'wrong': probe[k][1]} for k in list(probe)[:3]} }"
                ". score() is therefore not a function of the agent's output: it grades "
                "a constant, so every number this benchmark produces is fiction and no "
                f"optimizer can learn from it. Fix score() in {m['target_module']} (or "
                f"the {m['scoring']!r} mode's target field).")
        else:
            rep.notes.append(
                f"scorer discriminates on {len(discriminating)}/{len(smoke)} smoke "
                "task(s) (a correct output outscores a deliberately wrong one)")

    # 6. protected paths — checked against the artifact the RUNTIME GUARD reads.
    #
    # This step used to read the manifest's `protected_paths` while #197's
    # `resolve_protected` reads the GENERATED `capevolve.yaml`. Weakening only the
    # generated spec left verify reporting OK with `rep.protected ==
    # ['adapters/adapter.py']`: the same wrong-artifact bug as #189 (a guard reading a
    # committed manifest instead of disk). Now the manifest is only the *source*, and
    # every assertion below is on what `protect` actually resolves.
    try:
        protected = resolve_declared(proj)
    except Exception as e:  # noqa: BLE001 — a guard that cannot resolve is a problem
        rep.problems.append(
            f"resolving the protected set for {proj} raised {type(e).__name__}: {e} — "
            "the runtime tamper guard cannot determine what to hash, so it would refuse "
            "to run. Fix the generated capevolve.yaml's protected_paths.")
        return rep
    rep.protected = sorted(protected)

    # Assert on the RESOLVED set: every file the grader depends on must be one the guard
    # will hash. A string match against a declaration proves nothing.
    must_files = [str(m["target_module"]), str(m["tasks_file"]), MANIFEST_NAME,
                  "adapters/adapter.py"]
    if str(m["split_ids_file"]).strip():
        must_files.append(str(m["split_ids_file"]))
    missing = sorted(x for x in must_files if x not in protected)
    if missing:
        rep.problems.append(
            f"the runtime tamper guard will NOT hash {missing}. What it actually "
            f"resolves from {proj / 'capevolve.yaml'} is {sorted(protected)} — so the "
            "grader / dataset / manifest is optimizer-writable and a candidate could "
            "'improve' by rewriting it. This is checked against the generated spec "
            f"(what the guard reads), not {MANIFEST_NAME} (what it was derived from); "
            f"if they have diverged, re-run `cap-evolve benchmark add {bench_dir} "
            "--refresh`.")

    # 6a. UNDER-DECLARATION SWEEP. The four names above only ever covered the two
    # committed examples: a third author's `helpers.py` / `scorer2.py` /
    # `answers_gold.json` were neither protected nor flagged, and tampering with all
    # three went undetected. Flag every Python module and answer-key-ish data file in
    # the project dir that the guard would not hash.
    stray = under_declared(proj, m, protected)
    if stray:
        rep.problems.append(
            f"UNDER-DECLARED: {len(stray)} file(s) inside {proj} are code or answer-key "
            f"data that the tamper guard will not hash: {stray}. A helper the grader "
            "imports is as much the grader as adapter.py, and an answer key the "
            "optimizer can rewrite is a free 1.0. Add them to protected_paths in "
            f"{proj / MANIFEST_NAME} and re-run `cap-evolve benchmark add {bench_dir} "
            f"--refresh` — or move them under {m['capability_path']}/ if they are "
            "genuinely part of the artifact being optimized.")
    else:
        rep.steps.append(
            "under-declaration sweep: every .py and answer-key-ish file under "
            f"{PROJECT_SUBDIR}/ (outside {m['capability_path']}/) is guard-hashed")
    if not rep.problems:
        rep.steps.append(
            f"protected paths resolved from the generated spec: {rep.protected}")

    rep.ok = not rep.problems
    return rep


#: The files a stamp hashes. The dataset changing invalidates the evidence, but so does
#: the GRADER changing (``target.py``) and the DECLARATION changing (``benchmark.yaml``)
#: — a contributor who verifies then edits the scorer ships a badge certifying code
#: that no longer exists. Keys are stable so ``index()`` can re-check each one.
_STAMPED_KEYS = ("dataset_sha256", "target_sha256", "manifest_sha256")


def stamp_hashes(proj: Path, manifest: dict) -> dict:
    """``{stamp key -> sha256}`` for the dataset, the grader and the declaration."""
    return {
        "dataset_sha256": _file_sha(
            _contained(Path(proj), str(manifest["tasks_file"]), "tasks_file")),
        "target_sha256": _file_sha(
            _contained(Path(proj), str(manifest["target_module"]), "target_module")),
        "manifest_sha256": _file_sha(Path(proj) / MANIFEST_NAME),
    }


def stamp(bench_dir: Path, rep: VerifyReport) -> Path:
    """Persist the verification EVIDENCE (measured reward + hashes), not a claim."""
    bench_dir = Path(bench_dir)
    import datetime
    proj = bench_dir / PROJECT_SUBDIR
    payload = {
        "ok": rep.ok,
        "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "cap_evolve": __import__("cap_evolve").__version__,
        "val_reward": rep.val_reward, "n_tasks": rep.n_tasks, "splits": rep.splits,
        "steps": rep.steps, "problems": rep.problems,
        **stamp_hashes(proj, load_manifest(proj)),
    }
    p = bench_dir / STAMP_NAME
    p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return p


def stamp_state(bench_dir: Path, manifest: dict) -> dict:
    """Is ``verified.json`` real, current evidence? ``{"verified", "stale", "why"}``.

    Three ways a badge is refused:

      * ``ok`` is false, or the fields verify actually writes are absent — a
        hand-written ``{"ok": true}`` has no ``steps``, so it is not a verify result;
      * a recorded hash does not match the file on disk — a stale stamp certifying a
        dataset or grader that has since been edited;
      * the stamp does not parse.

    Previously ``index()`` read only ``st["ok"]``, so "a committed flag is a claim, the
    stamp is evidence" was false as implemented: the stamp was a differently-located
    claim. The hashes were written and never compared.
    """
    bench_dir = Path(bench_dir)
    p = bench_dir / STAMP_NAME
    if not p.is_file():
        return {"verified": False, "stale": False, "why": "no verified.json"}
    try:
        st = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        return {"verified": False, "stale": True, "why": f"unreadable verified.json: {e}",
                "stamp": {}}
    if not isinstance(st, dict):
        return {"verified": False, "stale": True,
                "why": "verified.json is not a JSON object", "stamp": {}}
    if not st.get("ok"):
        return {"verified": False, "stale": False, "why": "stamp records ok: false",
                "stamp": st}
    # Require the fields we rely on. A stamp without `steps` was not produced by
    # `verify` — it was typed. This is the cheap half of un-forging the badge.
    missing = [k for k in ("steps", "val_reward", "splits", "n_tasks", *_STAMPED_KEYS)
               if k not in st]
    if missing:
        return {"verified": False, "stale": True, "stamp": st,
                "why": f"verified.json is missing {missing} — `cap-evolve benchmark "
                       "verify` always writes these, so this stamp was hand-written, "
                       "not measured. Re-run verify."}
    if not st.get("steps"):
        return {"verified": False, "stale": True, "stamp": st,
                "why": "verified.json records no executed steps, so nothing was "
                       "actually verified. Re-run verify."}
    try:
        actual = stamp_hashes(bench_dir / PROJECT_SUBDIR, manifest)
    except BenchmarkError as e:
        return {"verified": False, "stale": True, "stamp": st,
                "why": f"cannot re-hash the stamped files: {e}"}
    drifted = {k: {"stamped": st.get(k), "actual": actual[k]}
               for k in _STAMPED_KEYS if st.get(k) != actual[k]}
    if drifted:
        return {"verified": False, "stale": True, "stamp": st, "drifted": drifted,
                "why": f"STALE STAMP: {sorted(drifted)} changed since verification "
                       f"({ {k: (str(v['stamped'])[:12], str(v['actual'])[:12]) for k, v in drifted.items()} }). "
                       "The badge certifies a dataset/grader/manifest that no longer "
                       "exists on disk. Re-run `cap-evolve benchmark verify`."}
    return {"verified": True, "stale": False, "why": "", "stamp": st}


def _file_sha(p: Path) -> str | None:
    p = Path(p)
    if not p.is_file():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _selfcheck() -> None:
    """ponytail self-check for the declarative predicates (``python -m cap_evolve.zoo``).

    A module, not a script: ``zoo.py`` uses relative imports, so ``python zoo.py``
    cannot work — this runs as ``python -m cap_evolve.zoo``.
    """
    assert match("Paris", "paris", "exact") and not match("Paris, FR", "paris", "exact")
    assert match("The capital is Paris.", "Paris", "contains")
    assert match("answer: 42", r"\d+", "regex") and not match("none", r"\d+", "regex")
    assert match("the answer is 1,024 units", "1024", "numeric")
    assert not match("no number", "7", "numeric")
    assert IMPLEMENT_MARKER  # imported for the stub contract
    print("zoo predicate self-check: OK")


if __name__ == "__main__":
    _selfcheck()
