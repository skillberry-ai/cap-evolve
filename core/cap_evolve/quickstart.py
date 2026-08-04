"""``cap-evolve quickstart`` — the zero-question fast path to a runnable project.

``intake`` is the guided INTERVIEW: an agent-driven phase skill that mines your working
dir, asks what capability to optimize, and leaves a *stub* adapter for you to implement
before the ``implement-and-check`` gate will let a run start. ``quickstart`` is the
opposite trade: it asks nothing (or one question), picks a **free or local** preset, and
writes a project that is ALREADY green under ``cap-evolve check`` — so the very next
command is ``cap-evolve run`` and you see a sealed test number without a paywall.

They do not overlap in code: quickstart never invokes intake, and a quickstart project
is a normal project intake could have produced. Use quickstart to see the pipeline work;
use intake when you have your own capability and benchmark.

Presets (``PRESETS``) — a dict, deliberately not a plugin framework:

===========  ========  ===============================  =========================
preset       cost      target runner                    needs
===========  ========  ===============================  =========================
``mock``     $0        deterministic stand-in, offline  nothing at all
``local``    $0        OpenAI-compatible local server   a server on 127.0.0.1
``free``     $0        Gemini free tier (OpenAI-compat) ``GEMINI_API_KEY``
===========  ========  ===============================  =========================

Non-interactive contract: ``--yes``, ``--preset``, a non-TTY stdin, or a non-TTY stderr
all mean "use defaults and never read stdin". Piping into quickstart cannot hang.
The TTY decision is #215's ``eventstream.capability`` ladder, not a local ``isatty``.

Secrets: quickstart resolves a credential's env var **NAME** (via ``model_config``) and
reports PRESENCE only — never a value, a prefix, or a length. Nothing it writes contains
a credential: the scaffolded adapter reads ``os.environ[<NAME>]`` at run time. A base URL
carrying ``user:token@`` userinfo is stripped before it is stored, and a non-default base
URL is reported as ``<custom>`` (``dashboard.safe_url``), because an internal gateway
hostname is itself sensitive.

Stdout is exactly ONE JSON object (#217). Every human-facing line goes to stderr.
Stdlib only, zero new runtime deps.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .dashboard import redact
from .splits import make_splits

def safe_url(url: str) -> str:
    """Public default verbatim, anything else ``<custom>``.

    Our OWN preset endpoints are checked first, so they always print verbatim. #190's
    rule does not know this table and masked both non-mock presets' shipped defaults as
    ``<custom>`` — hiding the value quickstart itself just chose, which reads as a bug
    and protects nothing (they are a documented public API and an explicit loopback).

    Everything else delegates to ``dashboard.safe_url`` — #190 moved this rule there so
    every consumer inherits one definition. The local fallback (an allowlist, so
    deliberately stricter than a heuristic) exists only until that PR lands: a real
    internal gateway URL already leaked into a public PR in this epic.
    """
    if not url:
        return ""
    if url in _PUBLIC_DEFAULTS:
        return url
    from . import dashboard
    fn = getattr(dashboard, "safe_url", None)
    return fn(url) if fn is not None else "<custom>"


#: The preset table. ``provider``/``credential`` are resolved through ``model_config``
#: when it is available, so cross-provider credential reuse stays impossible.
#: ponytail: a dict. A preset is one row; #124's cheap-real-run preset is one more row.
PRESETS: dict[str, dict] = {
    "mock": {
        "summary": "fully offline, $0, no credential — a deterministic stand-in agent",
        "provider": "mock",
        "runner": "mock",
        "base_url": "",
        "model": "",
        "optimizer": "mock",
        "needs": "nothing",
    },
    "local": {
        "summary": "$0 — a local OpenAI-compatible server (Ollama, llama.cpp, vLLM)",
        "provider": "openai",
        "runner": "openai-compatible",
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "qwen2.5:3b",
        "optimizer": "mock",
        "needs": "a local server answering at the base URL, with the model pulled "
                 "(`ollama serve` + `ollama pull qwen2.5:3b`)",
    },
    "free": {
        "summary": "$0 on the free tier — Gemini via its OpenAI-compatible endpoint",
        "provider": "gemini",
        "runner": "openai-compatible",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-2.0-flash",
        "optimizer": "mock",
        "needs": "GEMINI_API_KEY (or GOOGLE_API_KEY) exported",
    },
}

DEFAULT_PRESET = "mock"

#: Base URLs safe to print verbatim: the endpoints the presets themselves ship (a
#: documented public API, or an explicit loopback address). Any other endpoint is
#: somebody's infrastructure — see :func:`safe_url`.
_PUBLIC_DEFAULTS = frozenset(r["base_url"] for r in PRESETS.values() if r["base_url"])

#: 16 tasks, not 8. #195 refuses a val split below ``MIN_VAL_TASKS``, and the default
#: 0.5/0.25/0.25 ratios over 8 tasks land val on exactly the floor — one rounding change
#: away from a hard-failing scaffold. 16 gives val=4, comfortably clear of it.
_N_TASKS = 16


def _tasks() -> list[dict]:
    """The seed task set: exact-answer arithmetic, generated (no data file to ship)."""
    out = []
    for i in range(_N_TASKS):
        a, b = 3 + i, 2 + (i * 3) % 7
        op = "+-*"[i % 3]
        expr = f"{a} {op} {b}"
        out.append({"id": f"q{i + 1:02d}", "input": expr,
                    "target": str(eval(expr, {"__builtins__": {}}, {}))})  # noqa: S307
    return out


# The scaffolded adapter. ONE template for both runner modes: ``_RUNNER`` is substituted
# at write time, so there is no second near-identical file to keep in sync. The seed
# prompt is deliberately vague, so a real (or stand-in) agent rambles instead of
# answering — that is the headroom the optimizer closes by making the prompt explicit.
_ADAPTER = '''"""Quickstart adapter — written by `cap-evolve quickstart` (preset: {preset}).

The capability under optimization is ``seed_capability/prompt.txt``. The seed prompt is
vague on purpose, so the agent answers in prose and scores 0; an optimizer that makes
the output contract explicit raises the score. That is the whole pipeline, provable.

NO CREDENTIAL IS STORED HERE. ``_CRED_ENV`` is the NAME of an environment variable; the
value is read from the process environment at run time and never written to disk.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from cap_evolve import CapabilityAdapter, Rollout, Score, Task

_HERE = Path(__file__).resolve().parent
_RUNNER = {runner!r}
_BASE_URL = {base_url!r}
_MODEL = {model!r}
_CRED_ENV = {cred_env!r}          # an env var NAME, never a value
_CRED_NAMES = {cred_names!r}      # the provider's candidate NAMES, in precedence order


def _credential() -> str | None:
    """Resolve the credential at RUN time, from names fixed at scaffold time.

    Scaffolding before you export the key used to bake ``_CRED_ENV = ''``, so the
    adapter then sent no Authorization header at all — a 401 indistinguishable from a
    dead endpoint, and exporting the key afterwards did nothing until you re-scaffolded
    with --force. The NAMES are provider-scoped and fixed here (so no cross-provider
    reuse is possible); only the lookup moves to run time.
    """
    for name in ((_CRED_ENV,) if _CRED_ENV else ()) + _CRED_NAMES:
        val = os.environ.get(name)
        if val:
            return val
    return None


def _safe_eval(expr: str) -> int:
    if not set(expr) <= set("0123456789 +-*"):
        raise ValueError("unsafe expr")
    return int(eval(expr, {{"__builtins__": {{}}}}, {{}}))  # noqa: S307


def _chat(prompt: str, question: str, *, seed: int) -> str:
    """One OpenAI-compatible chat completion, stdlib urllib only."""
    import urllib.request

    body = json.dumps({{
        "model": _MODEL,
        "messages": [{{"role": "system", "content": prompt}},
                     {{"role": "user", "content": question}}],
        "temperature": 0, "seed": seed,
    }}).encode()
    req = urllib.request.Request(_BASE_URL.rstrip("/") + "/chat/completions",
                                data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    cred = _credential()
    if cred:
        req.add_header("Authorization", f"Bearer {{cred}}")
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
    return (data["choices"][0]["message"]["content"] or "").strip()


class Adapter(CapabilityAdapter):

    def tasks(self, split: str) -> list[Task]:
        rows = [json.loads(ln) for ln in
                (_HERE / "tasks.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
        return [Task(id=r["id"], input=r["input"], target=r["target"]) for r in rows]

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        prompt = (Path(ctx) / "prompt.txt").read_text(encoding="utf-8")
        expr = str(task.input)
        if _RUNNER == "mock":
            # Offline stand-in: it computes correctly only once the prompt tells it to
            # output just the number. Deterministic, zero-cost, no network.
            if "ONLY" in prompt.upper():
                try:
                    out = str(_safe_eval(expr))
                except Exception as e:  # noqa: BLE001
                    out = f"error: {{e}}"
            else:
                out = f"Well, {{expr}} works out to something around there."
            return Rollout(task_id=task.id, output=out, trace=f"runner=mock explicit={{'ONLY' in prompt.upper()}}")
        try:
            out = _chat(prompt, expr, seed=seed)
        except Exception as e:  # noqa: BLE001 — a dead endpoint is a scored failure, not a crash
            return Rollout(task_id=task.id, output="", trace=f"runner error: {{type(e).__name__}}")
        return Rollout(task_id=task.id, output=out, trace=f"runner={{_RUNNER}}")

    def score(self, task: Task, rollout: Rollout) -> Score:
        got, want = (rollout.output or "").strip(), str(task.target).strip()
        ok = got == want
        fb = "correct" if ok else (
            f"expected exactly '{{want}}' but got '{{got[:120]}}' — the prompt does not "
            "require the answer to be the bare number and nothing else")
        return Score(task_id=task.id, reward=1.0 if ok else 0.0, feedback=fb,
                     trial_rewards=[1.0 if ok else 0.0])

    def apply(self, candidate_dir: Path, edits: dict | None = None) -> None:
        return None
'''

_SEED_PROMPT = "You are a helpful assistant. Answer the user as best you can.\n"

# The mock optimizer's scripted edit: make the output contract explicit. This is what
# turns baseline 0.0 into a sealed 1.0 without any model call.
_MOCK_SCRIPT = {
    "edits": [{"file": "prompt.txt", "op": "ensure_contains",
               "text": "\nCompute the expression exactly and output ONLY the resulting "
                       "number — no words, no units, no explanation."}],
}


def _optional(name: str):
    """Import a sibling module that may not exist on this branch yet, else ``None``.

    ``doctor`` (#121), ``model_config`` (#190) and ``eventstream`` (#215) land in
    parallel PRs. quickstart USES each when present rather than reimplementing health
    checks / credential resolution / TTY sniffing, and degrades to a documented
    fallback when it is merged first. ponytail: three one-line lookups, no shim layer.
    """
    try:
        import importlib
        return importlib.import_module(f".{name}", __package__)
    except Exception:  # noqa: BLE001
        return None


def interactive() -> bool:
    """May we ask a question? False whenever stdin or stderr is not a real terminal.

    Uses #215's capability ladder so "can I talk to a human" is decided in exactly one
    place in the repo. ``pipe``/``none`` are the non-TTY rungs; ``plain``/``dumb`` are
    real terminals that merely refuse colour, so they still get the prompt.
    """
    es = _optional("eventstream")
    if es is not None:
        return (es.capability(sys.stdin) not in ("pipe", "none")
                and es.capability(sys.stderr) not in ("pipe", "none"))
    try:  # fallback only while #215 is unmerged
        return bool(sys.stdin.isatty() and sys.stderr.isatty())
    except Exception:  # noqa: BLE001
        return False


def _ask_preset(default: str = DEFAULT_PRESET) -> str:
    """One question, on stderr, with a default. Only ever called when interactive()."""
    print("cap-evolve quickstart — pick a preset (all free):", file=sys.stderr)
    for name, row in PRESETS.items():
        mark = " (default)" if name == default else ""
        print(f"  {name:<6} {row['summary']}{mark}\n         needs: {row['needs']}",
              file=sys.stderr)
    print(f"preset [{default}]: ", end="", file=sys.stderr, flush=True)
    try:
        answer = (sys.stdin.readline() or "").strip()
    except Exception:  # noqa: BLE001 — stdin vanished mid-prompt
        return default
    return answer if answer in PRESETS else default


#: Provider-scoped credential env var NAMES, in precedence order. One table, used both
#: for the ``model_config``-absent fallback and for the scaffolded adapter's run-time
#: lookup — so a preset can never resolve another provider's credential.
_CRED_NAMES: dict[str, tuple[str, ...]] = {
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
    "openai": ("OPENAI_API_KEY",),
}


def _resolve_provider(row: dict, base_url: str) -> dict:
    """Secret-free provider report: which env var NAME holds the credential, if any.

    Delegates to ``model_config`` (#190) so provider-scoping and the precedence order
    are not re-implemented here. Reports PRESENCE only.
    """
    mc = _optional("model_config")
    provider = row["provider"]
    if provider == "mock":
        return {"provider": "mock", "credential_env": "", "credential_present": False,
                "base_url": "", "reason": "offline preset — no credential, no endpoint"}
    if mc is None:  # fallback while #190 is unmerged: name-only lookup, still no values
        found = next((n for n in _CRED_NAMES.get(provider, ()) if os.environ.get(n)), "")
        return {"provider": provider, "credential_env": found,
                "credential_present": bool(found), "base_url": safe_url(base_url),
                "reason": "model_config unavailable — env-name lookup only"}
    try:
        res = mc.resolve(cli={"provider": provider, "base_url": base_url},
                         require_credential=False)
        return res.to_dict()
    except Exception as e:  # noqa: BLE001 — message names env VARS, never values
        return {"provider": provider, "credential_env": "", "credential_present": False,
                "base_url": safe_url(base_url), "reason": redact(str(e))[:400]}


def _patch_spec(text: str, values: dict[str, object]) -> str:
    """Set top-level ``key: value`` lines in the template spec, in place.

    Patching the shipped ``templates/project/capevolve.yaml`` rather than authoring a
    fresh one is what keeps quickstart honest about #197: the template deliberately
    OMITS ``protected_paths`` (an empty list is a hard error), and every future spec
    key/comment arrives for free. Keys absent from the template are appended.
    """
    remaining = dict(values)
    out = []
    for line in text.splitlines():
        stripped = line.lstrip()
        key = stripped.split(":", 1)[0].strip() if ":" in stripped else ""
        if key in remaining and not stripped.startswith("#") and line == stripped:
            val = remaining.pop(key)
            out.append(f"{key}: {json.dumps(val) if isinstance(val, str) else val}")
        else:
            out.append(line)
    for key, val in remaining.items():
        out.append(f"{key}: {json.dumps(val) if isinstance(val, str) else val}")
    return "\n".join(out) + "\n"


def _template_spec() -> str:
    """``templates/project/capevolve.yaml`` from the repo, else a minimal equivalent."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "templates" / "project" / "capevolve.yaml"
        if cand.is_file():
            return cand.read_text(encoding="utf-8")
    # Installed-wheel fallback: the same keys, still WITHOUT protected_paths (#197).
    return ("capabilities: [system-prompt]\ncapability_path: seed_capability\n"
            "actions: [edit]\noptimizer_skill: mock\noptimizer_model: \"\"\n"
            "algorithm_skill: hill-climb\nalgorithm_focus: all\n"
            "orchestration_mode: deterministic\ndataset_source: tasks.jsonl\n"
            "split_seed: 0\nsplit_train: 0.5\nsplit_val: 0.25\nsplit_test: 0.25\n"
            "num_trials: 1\ngate_mode: paired\ngate_k_se: 1.0\n"
            "max_iterations: 3\nstall: 2\nstore: git\n")


def _val_tasks(n: int) -> int:
    """How many val tasks the scaffolded spec will actually produce.

    Asks ``splits.make_splits`` rather than recomputing ``round(n * 0.25)``: a second
    copy of the split arithmetic is a number that can silently disagree with the one
    the run uses, which is exactly the class of defect this PR is fixing elsewhere.
    """
    ids = [f"q{i + 1:02d}" for i in range(n)]
    return len(make_splits(ids, seed=0, ratios=(0.5, 0.25, 0.25)).val)


def scaffold(dest: Path, preset: str, *, model: str = "", base_url: str = "",
             force: bool = False) -> dict:
    """Write a ready-to-run project under ``dest``. Returns a secret-free record."""
    if preset not in PRESETS:
        raise ValueError(f"unknown preset {preset!r}; pick one of: {', '.join(PRESETS)}")
    row = PRESETS[preset]
    dest = Path(dest)
    project = dest / ".capevolve" / "project"
    if project.exists() and not force:
        raise FileExistsError(f"{project} already exists — pass --force to overwrite")
    if project.exists() and not project.is_dir():
        # `--force` on a plain file used to surface a bare `[Errno 20] Not a directory`
        # from deep inside mkdir. Say what is wrong and what to do instead.
        raise ValueError(f"{project} exists but is a file, not a directory — "
                         f"--force overwrites a project, not a file; remove it first")
    # The mock edit script lives OUTSIDE `.capevolve/project`, so the guard above never
    # saw it: an existing (possibly hand-edited) one was replaced without a word.
    mock_script = dest / ".capevolve" / "mock_script.json"
    if mock_script.exists() and not force:
        raise FileExistsError(f"{mock_script} already exists — pass --force to overwrite")

    # Userinfo (https://user:token@host/) is a credential. Strip it at the single point
    # of resolution so it can never be written to a file, printed, or reported (#190).
    url = base_url or row["base_url"]
    mc = _optional("model_config")
    # COUPLING NOTE (#190): `strip_url_userinfo` is DEFINED in `dashboard`; it resolves as
    # `mc.strip_url_userinfo` only because #190 does `from .dashboard import ...` at
    # model_config.py:51, i.e. we depend on its import list, not its public API. If #190
    # ever switches to `from . import dashboard` + `dashboard.strip_url_userinfo(...)`,
    # getattr fails and the manual `elif` below silently takes over. Hence `getattr`
    # rather than a bare attribute access, so the degradation is a documented branch.
    strip = getattr(mc, "strip_url_userinfo", None) if mc is not None else None
    if strip is not None and url:
        url = strip(url)
    elif url and "@" in url.split("//", 1)[-1].split("/", 1)[0]:
        scheme, _, rest = url.partition("//")
        url = scheme + "//" + rest.split("@", 1)[1]

    provider = _resolve_provider(row, url)
    cred_env = provider.get("credential_env") or ""

    (project / "adapters").mkdir(parents=True, exist_ok=True)
    (project / "adapters" / "adapter.py").write_text(
        _ADAPTER.format(preset=preset, runner=row["runner"], base_url=url,
                        model=model or row["model"], cred_env=cred_env,
                        cred_names=_CRED_NAMES.get(row["provider"], ())), encoding="utf-8")
    (project / "adapters" / "tasks.jsonl").write_text(
        "".join(json.dumps(t) + "\n" for t in _tasks()), encoding="utf-8")
    (project / "capevolve.yaml").write_text(_patch_spec(_template_spec(), {
        "optimizer_skill": row["optimizer"],
        "capability_path": "seed_capability",
        "dataset_source": "adapter",
        "max_iterations": 3,
        "stall": 2,
    }), encoding="utf-8")
    (dest / "seed_capability").mkdir(parents=True, exist_ok=True)
    (dest / "seed_capability" / "prompt.txt").write_text(_SEED_PROMPT, encoding="utf-8")
    mock_script.write_text(json.dumps(_MOCK_SCRIPT, indent=2) + "\n", encoding="utf-8")

    created = sorted(str(p.relative_to(dest)) for p in
                     (*project.rglob("*"), dest / "seed_capability" / "prompt.txt",
                      mock_script) if p.is_file())
    return {"preset": preset, "dir": str(dest.resolve()), "created": created,
            "provider": provider, "model": model or row["model"],
            "base_url": safe_url(url) if url else "",
            "val_tasks": _val_tasks(_N_TASKS), "tasks": _N_TASKS}


def _health(dest: Path) -> dict | None:
    """``doctor``'s report for the scaffolded dir, or ``None`` if #121 isn't merged."""
    doc = _optional("doctor")
    if doc is None:
        return None
    rep = doc.run_doctor(dest)
    if not rep.ok:  # human-facing detail on stderr; stdout stays one JSON object
        print(doc.format_report(rep), file=sys.stderr)
    return {"ok": rep.ok, "failed": [c.name for c in rep.checks if c.status == doc.FAIL]}


def _next_steps(dest: Path, preset: str) -> list[str]:
    # Absolute paths: `--dir .` used to render `cd .` and a relative script path, which
    # is only correct if you never leave the shell you ran quickstart in.
    dest = Path(dest).resolve()
    row = PRESETS[preset]
    env = [f"export CAPEVOLVE_MOCK_SCRIPT={dest / '.capevolve' / 'mock_script.json'}"]
    if preset != "mock":
        env.append(f"# target runner needs: {row['needs']}")
    return [*env, f"cd {dest}", "cap-evolve check .capevolve/project", "cap-evolve run"]


def _main(argv: list[str]) -> int:
    import argparse

    p = argparse.ArgumentParser(
        prog="cap-evolve quickstart",
        description="Scaffold a ready-to-run project from a free/local preset.",
        epilog="examples:\n"
               "  cap-evolve quickstart                      # one question (or defaults)\n"
               "  cap-evolve quickstart --yes                # zero questions, mock preset\n"
               "  cap-evolve quickstart --preset local       # local OpenAI-compatible server\n"
               "  cap-evolve quickstart --preset free --dir ./demo\n"
               "presets: " + " | ".join(f"{k} ({v['summary']})" for k, v in PRESETS.items()),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dir", default=".", help="where to scaffold (default: .)")
    p.add_argument("--preset", choices=sorted(PRESETS), default=None,
                   help=f"skip the question (default: {DEFAULT_PRESET})")
    p.add_argument("--yes", "-y", action="store_true",
                   help="never prompt; accept every default")
    p.add_argument("--model", default="", help="override the preset's target model")
    p.add_argument("--base-url", default="",
                   help="override the preset's endpoint (URL userinfo is stripped)")
    p.add_argument("--force", action="store_true", help="overwrite an existing project")
    p.add_argument("--no-doctor", action="store_true", help="skip the health check")
    args = p.parse_args(argv)

    # Non-interactive contract: an explicit --preset, --yes, or a non-TTY stdin/stderr
    # all mean "defaults, never read stdin". So `echo x | cap-evolve quickstart` and a
    # CI invocation both return immediately instead of blocking on a prompt.
    preset = args.preset or (_ask_preset() if not args.yes and interactive()
                             else DEFAULT_PRESET)

    # `mock` has no endpoint and no model, so --model/--base-url were silently dropped.
    # Refuse instead: a flag that is accepted and ignored is the same defect family as
    # an optimizer that proposes nothing and still exits 0. The message names the fix.
    dead = [f for f, v in (("--model", args.model), ("--base-url", args.base_url)) if v]
    if preset == "mock" and dead:
        print(json.dumps({"ok": False, "error":
              f"{' and '.join(dead)} has no effect with preset 'mock' (offline stand-in, "
              f"no endpoint and no model). Use --preset local or --preset free, or drop "
              f"the flag."}))
        return 1

    try:
        rec = scaffold(Path(args.dir), preset, model=args.model,
                       base_url=args.base_url, force=args.force)
    except (ValueError, FileExistsError, OSError) as e:
        print(json.dumps({"ok": False, "error": redact(str(e))}))
        return 1

    # A doctor failure does NOT change the exit code, deliberately: quickstart's contract
    # is "the project was scaffolded", which succeeded. Health is advisory about the
    # environment (#121 owns that), reported in `health` and printed to stderr, and
    # `check`/`run` are the gates that must actually refuse. Exiting non-zero here would
    # make a scaffold that is on disk and check-green look like a failed command.
    if not args.no_doctor:
        health = _health(Path(args.dir))
        if health is not None:
            rec["health"] = health
    rec["next"] = _next_steps(Path(args.dir), preset)
    rec["ok"] = True

    # Defense in depth: everything goes through redact(). But redact() masks any value
    # under a key that merely *looks* secret, and "credential_env"/"credential_present"
    # do — so the provider block came out as `credential_env: «redacted»`, hiding the one
    # thing the user needs (WHICH var to export) with no security gain. `credential_env`
    # is an env var NAME and `credential_present` a bool, secret-free by construction in
    # model_config; #121's doctor solves this identically, by rendering names AFTER
    # redaction. Re-stamp exactly those two fields, nothing else.
    out = redact(rec)
    for key in ("credential_env", "credential_present"):
        if key in rec.get("provider", {}):
            out["provider"][key] = rec["provider"][key]

    # Human summary → stderr. Stdout is exactly one JSON object (#217).
    print(f"quickstart: preset {preset} scaffolded in {rec['dir']}\n"
          f"  {rec['tasks']} tasks ({rec['val_tasks']} val) · optimizer "
          f"{PRESETS[preset]['optimizer']} · {PRESETS[preset]['summary']}\n"
          "next:\n" + "\n".join(f"  {s}" for s in rec["next"]), file=sys.stderr)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
