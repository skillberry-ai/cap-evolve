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

``verify`` is not a manifest parser. It runs the real ``cap-evolve check`` gate AND
a real zero-API smoke through the adapter (every val task, twice, comparing
rollouts and rewards), AND the honest-split floor, AND the protected-paths
resolution — then stamps ``verified.json`` with the reward it actually measured.
A benchmark whose ``score`` is stubbed, whose ``run_target`` is non-deterministic,
whose dataset is too small for an honest gate, or whose dataset file is missing
cannot pass it.

Pure stdlib (json + hashlib + importlib), like the rest of ``core``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .adapter import IMPLEMENT_MARKER, CapabilityAdapter
from .specfile import read_yaml
from .splits import make_splits
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
from . import splits as _splits  # noqa: E402

MIN_VAL_TASKS = getattr(_splits, "MIN_VAL_TASKS", 2)

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
}


class BenchmarkError(RuntimeError):
    """A benchmark manifest is invalid, or its benchmark does not verify."""


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
    return m


def _load_target_module(manifest: dict):
    """Import the manifest's target module (the one function that is real code)."""
    mod_path = Path(manifest["root"]) / str(manifest["target_module"])
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
    return mod


# ---------------------------------------------------------------------------
# scoring (the declarative half)
# ---------------------------------------------------------------------------


def _num(s: str):
    m = re.search(r"-?\d+(?:\.\d+)?", str(s).replace(",", ""))
    return float(m.group()) if m else None


def match(output: str, target: str, mode: str) -> bool:
    """Does ``output`` satisfy ``target`` under ``mode``? (the built-in predicates)"""
    out, tgt = (output or "").strip(), (target or "").strip()
    if mode == "contains":
        return tgt.lower() in out.lower()
    if mode == "regex":
        return re.search(tgt, out) is not None
    if mode == "numeric":
        a, b = _num(out), _num(tgt)
        return a is not None and b is not None and abs(a - b) < 1e-9
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
        if self._tasks is not None:
            return list(self._tasks)
        m = self.manifest
        path = self.root / str(m["tasks_file"])
        if not path.is_file():
            raise BenchmarkError(
                f"dataset file missing: {path} (declared as tasks_file="
                f"{m['tasks_file']!r} in {self.root / MANIFEST_NAME}). Create it — one "
                'JSON object per line, e.g. {"id": "t1", "input": "...", '
                '"target": "..."} — or point tasks_file at the real dataset.')
        out: list[Task] = []
        seen: set[str] = set()
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
            out.append(Task(id=tid, input=d.get(m["input_field"]),
                            target=d.get(m["target_field"]),
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
        if callable(custom):  # a custom scorer always wins over the declared mode
            return custom(task, rollout)
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
    prot = m["protected_paths"] or default_protected(m)
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
    (proj / "adapters" / "adapter.py").write_text(
        "from cap_evolve.zoo import ManifestAdapter\n\n\n"
        "class Adapter(ManifestAdapter):\n"
        f'    """{m["name"]} — everything is declared in ../{MANIFEST_NAME}."""\n\n'
        "    manifest_path = __file__\n",
        encoding="utf-8")
    (proj / "capevolve.yaml").write_text(spec_from_manifest(m), encoding="utf-8")
    return {"name": m["name"], "dir": str(dest), "project": str(proj),
            "manifest": str(proj / MANIFEST_NAME), "files": sorted(
                str(p.relative_to(dest)) for p in dest.rglob("*") if p.is_file())}


def _manifest_text(name: str, description: str) -> str:
    return f"""# cap-evolve benchmark manifest — the DECLARATIVE half of a benchmark.
# The only code is target.py's run(task, ctx, *, seed=0). Flat keys only, so the
# zero-dependency spec reader can parse it.
name: {name}
description: {description or "TODO one line: what capability this benchmark measures"}

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
        stamp = bench / STAMP_NAME
        st = {}
        if stamp.is_file():
            try:
                st = json.loads(stamp.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                st = {"error": "unreadable verified.json"}
        out.append({"name": m["name"], "dir": str(bench),
                    "description": m["description"], "scoring": m["scoring"],
                    "metric_direction": m["metric_direction"],
                    "verified": bool(st.get("ok")),
                    "verified_at": st.get("at"), "smoke_val_reward": st.get("val_reward"),
                    "n_tasks": st.get("n_tasks")})
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
      4. seeded split + the honest-gate floor (``MIN_VAL_TASKS`` val, >=1 test);
      5. a REAL zero-API smoke: every val task through ``live`` → ``run_target`` →
         ``score``, TWICE, comparing rollout fingerprints and rewards — this is what
         catches a non-deterministic ``run_target``, which ``check`` never runs;
      6. protected-paths resolution: the grader, the dataset and the manifest must
         all be covered by what the spec declares.

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
        sf = proj / str(m["split_ids_file"])
        if not sf.is_file():
            rep.problems.append(f"split_ids_file {sf} does not exist")
            return rep
        sd = json.loads(sf.read_text(encoding="utf-8"))
        sp = type("S", (), {"train": sd.get("train", []), "val": sd.get("val", []),
                            "test": sd.get("test", [])})()
    else:
        sp = make_splits([t.id for t in tasks], seed=int(m["split_seed"]),
                         ratios=(float(m["split_train"]), float(m["split_val"]),
                                 float(m["split_test"])))
    rep.splits = {"train": len(sp.train), "val": len(sp.val), "test": len(sp.test)}
    rep.steps.append(f"splits computed: {rep.splits}")
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
    if rewards and all(r == rewards[0] for r in rewards) and rewards[0] == 1.0:
        rep.notes.append(
            "the seed capability already scores 1.0 on every smoke task — there is no "
            "headroom to optimize; consider harder tasks.")

    # 6. protected paths — declared, and actually covering the grader
    declared = m["protected_paths"] or default_protected(m)
    try:
        from . import protect  # available once #142 lands
        files = protect.resolve_protected(proj)
        rep.protected = sorted(files)
    except ImportError:  # pragma: no cover — pre-#142 checkout
        rep.notes.append("protect module absent (pre-#142); manifest declaration checked only")
    must = {MANIFEST_NAME, str(m["target_module"]), str(m["tasks_file"]), "adapters"}
    missing = sorted(x for x in must if not any(
        d == x or d.startswith(x.rstrip("/") + "/") for d in declared))
    if missing:
        rep.problems.append(
            f"protected_paths does not cover {missing} — the grader / dataset / "
            "manifest would be optimizer-writable, so a candidate could 'improve' by "
            f"rewriting them. Add them in {proj / MANIFEST_NAME}.")
    else:
        rep.steps.append(f"protected paths declared + resolved: {declared}")

    rep.ok = not rep.problems
    return rep


def stamp(bench_dir: Path, rep: VerifyReport) -> Path:
    """Persist the verification EVIDENCE (measured reward + hashes), not a claim."""
    bench_dir = Path(bench_dir)
    import datetime
    payload = {
        "ok": rep.ok,
        "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "cap_evolve": __import__("cap_evolve").__version__,
        "val_reward": rep.val_reward, "n_tasks": rep.n_tasks, "splits": rep.splits,
        "steps": rep.steps, "problems": rep.problems,
        "dataset_sha256": _file_sha(
            bench_dir / PROJECT_SUBDIR
            / str(load_manifest(bench_dir / PROJECT_SUBDIR)["tasks_file"])),
    }
    p = bench_dir / STAMP_NAME
    p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return p


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
