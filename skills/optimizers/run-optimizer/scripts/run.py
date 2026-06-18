"""run-optimizer — the single runner for every shell-invokable edit proposer.

The optimize loop calls this with ``--name <optimizer> --workdir <candidate copy>
--prompt <INSTRUCTIONS.md>``. This script reads ``optimizers/registry.yaml``,
resolves the named row, builds the command from its ``command_template`` (with
``{workdir}`` / ``{prompt}`` / ``{prompt_text}`` / ``{model}`` placeholders), and
runs it with cwd = the workdir so the agent edits files in place. One runner +
one YAML row per optimizer replaces the eight near-identical wrapper skills.

Backward-compat: a spec that still names an old optimizer skill (``claude-code``,
``ibm-bob``, ``mock``, …) resolves to the registry row of the same name, so old
specs keep working unchanged.

The ``mock`` row is fully offline: it runs the colocated ``_mock_apply.py`` (a
deterministic JSON-driven editor), so zero-API e2e tests never touch a network.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from cap_evolve.specfile import read_yaml

# Old per-CLI skill names that callers may still pass; they map 1:1 to a row.
_LEGACY_ALIASES = {
    "claude-code", "codex", "gemini-cli", "ibm-bob", "openclaw",
    "opencode", "generic", "mock",
}


def _registry_path() -> Path:
    """``optimizers/registry.yaml`` — sibling of the ``run-optimizer`` skill dir."""
    env = os.environ.get("CAPEVOLVE_OPTIMIZER_REGISTRY")
    if env and Path(env).exists():
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        cand = parent / "registry.yaml"
        if cand.exists() and parent.name == "optimizers":
            return cand
        cand = parent / "optimizers" / "registry.yaml"
        if cand.exists():
            return cand
    raise FileNotFoundError("optimizers/registry.yaml not found (set CAPEVOLVE_OPTIMIZER_REGISTRY)")


def load_registry() -> dict:
    return read_yaml(_registry_path().read_text(encoding="utf-8"))


def _self_dir() -> str:
    return str(Path(__file__).resolve().parent)


def _resolve_env_keys(row: dict) -> dict:
    """Resolve auth env vars; for ibm-bob also read the nearest .env (legacy behavior).

    Returns ``{present: [keys set], env: {overrides}}``. Never prints values.
    """
    keys = [k.strip() for k in str(row.get("env_keys", "")).split(",") if k.strip()]
    present, overrides = [], {}
    for k in keys:
        if os.environ.get(k):
            present.append(k)
    # ibm-bob: BOBSHELL_API_KEY <- BOB_API_KEY or the nearest .env up the tree.
    if "BOBSHELL_API_KEY" in keys and not os.environ.get("BOBSHELL_API_KEY"):
        val = os.environ.get("BOB_API_KEY") or _read_dotenv_key(("BOBSHELL_API_KEY", "BOB_API_KEY"))
        if val:
            overrides["BOBSHELL_API_KEY"] = val
            present.append("BOBSHELL_API_KEY(.env)")
    return {"present": present, "env": overrides}


def _read_dotenv_key(names: tuple[str, ...]) -> str | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        env = parent / ".env"
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    name, val = line.split("=", 1)
                    if name.strip() in names:
                        return val.strip().strip('"').strip("'")
            break
    return None


def _coerce_float(x) -> float | None:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_cost(stdout: str) -> dict:
    """Best-effort extraction of cost from a headless optimizer's JSON output.

    Coding-agent CLIs emit structured results with slightly different shapes; we
    look for the common keys without committing to one vendor:

      * Claude Code (`--output-format json`): top-level ``total_cost_usd`` and
        ``usage`` (input/output tokens); per-model cost under ``modelUsage``.
      * Codex (`--json`): a stream of JSON lines; the final/`result`-like object
        may carry ``total_cost_usd`` or ``usage``.
      * Gemini (`--output-format json``): ``total_cost_usd`` / ``usage`` if present.

    Returns ``{usd: float|None, tokens: int|None, raw: <parsed-or-None>}``. Never
    raises: a CLI that printed prose (no JSON) yields ``{usd: None, ...}`` and the
    caller falls back to the prose-fed path unchanged.
    """
    out = {"usd": None, "tokens": None, "raw": None}
    if not stdout or not stdout.strip():
        return out

    # Try whole-string JSON first, then last-nonempty-line (JSONL streams like codex).
    objs: list = []
    text = stdout.strip()
    try:
        objs.append(json.loads(text))
    except Exception:
        for line in reversed(text.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                objs.append(json.loads(line))
                break
            except Exception:
                continue
    if not objs:
        return out

    def _scan(obj) -> None:
        """Walk dicts/lists pulling the first cost/token signal we recognize."""
        if isinstance(obj, dict):
            for key in ("total_cost_usd", "cost_usd", "totalCostUsd"):
                if out["usd"] is None and key in obj:
                    out["usd"] = _coerce_float(obj[key])
            usage = obj.get("usage") or obj.get("token_usage") or {}
            if isinstance(usage, dict) and out["tokens"] is None:
                tot = usage.get("total_tokens")
                if tot is None:
                    inp = usage.get("input_tokens") or usage.get("prompt_tokens")
                    o = usage.get("output_tokens") or usage.get("completion_tokens")
                    if inp is not None or o is not None:
                        tot = (int(inp or 0) + int(o or 0))
                if tot is not None:
                    try:
                        out["tokens"] = int(tot)
                    except (TypeError, ValueError):
                        pass
            for v in obj.values():
                if out["usd"] is None or out["tokens"] is None:
                    _scan(v)
        elif isinstance(obj, list):
            for v in obj:
                if out["usd"] is None or out["tokens"] is None:
                    _scan(v)

    for o in objs:
        _scan(o)
        out["raw"] = o
    return out


def build_command(template: str, *, workdir: str, prompt: str, prompt_text: str,
                  model: str | None, self_dir: str) -> list[str]:
    """Expand the template into argv.

    ``{model}`` drops itself and an immediately-preceding bare flag token
    (``-m`` / ``--model``) when no model is set, so the same template works with
    or without a model. ``${VAR}`` expands from the environment first (so the
    ``generic`` / ``openclaw`` escape-hatch rows pull their command from env).
    """
    expanded = os.path.expandvars(template)
    tokens = shlex.split(expanded)
    out: list[str] = []
    subs = {"workdir": workdir, "prompt": prompt, "prompt_text": prompt_text,
            "self_dir": self_dir, "model": model or ""}
    for tok in tokens:
        # model-group drop: a flag token whose only job is to precede {model}
        if tok in ("-m", "--model", "-model") and not model:
            # peek: drop only if the next token IS the {model} placeholder
            continue
        if tok == "{model}" and not model:
            continue
        new = tok
        for k, v in subs.items():
            new = new.replace("{" + k + "}", v)
        out.append(new)
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="run-optimizer")
    p.add_argument("--name", default=os.environ.get("CAPEVOLVE_OPTIMIZER", "mock"),
                   help="optimizer name resolved via optimizers/registry.yaml")
    p.add_argument("--workdir", help="candidate working copy to edit in place")
    p.add_argument("--prompt", help="path to INSTRUCTIONS.md")
    p.add_argument("--model", default=os.environ.get("CAPEVOLVE_OPTIMIZER_MODEL") or None)
    p.add_argument("--json", action="store_true",
                   default=os.environ.get("CAPEVOLVE_OPTIMIZER_JSON") == "1",
                   help="append the registry row's json_flag and parse total_cost_usd "
                        "from the CLI's structured output (best-effort; off by default)")
    p.add_argument("--json-schema", default=os.environ.get("CAPEVOLVE_OPTIMIZER_JSON_SCHEMA"),
                   help="for Claude Code: a JSON Schema string passed as --json-schema so "
                        "the result carries .structured_output (only added when --json and "
                        "the row's json_flag contains --output-format)")
    p.add_argument("--budget", type=int, default=None,
                   help="per-iteration cap rendered into the registry row's budget_flag "
                        "(e.g. claude-code → --max-turns N); ignored if the row has none")
    p.add_argument("--list", action="store_true", help="list known optimizers and exit")
    args = p.parse_args(argv)

    registry = load_registry()
    if args.list:
        print(json.dumps({"optimizers": sorted(registry)}, indent=2))
        return 0
    if not args.workdir or not args.prompt:
        p.error("--workdir and --prompt are required (unless --list)")

    name = args.name
    row = registry.get(name)
    if row is None:
        # back-compat: an unknown legacy alias still maps by exact name; otherwise error.
        print(json.dumps({"optimizer": name, "error":
              f"no registry row for {name!r}; known: {sorted(registry)}"}))
        return 2

    # Resolve to an absolute path: the command runs with cwd=workdir, so a relative
    # {workdir} would be re-interpreted against that cwd (nesting the path). Making
    # it absolute keeps file edits landing in the candidate dir, not a subdir of it.
    workdir = str(Path(args.workdir).resolve())
    prompt_path = Path(args.prompt).resolve()
    prompt_text = prompt_path.read_text(encoding="utf-8") if prompt_path.exists() else ""

    cmd = build_command(str(row.get("command_template", "")), workdir=workdir,
                        prompt=str(prompt_path), prompt_text=prompt_text,
                        model=args.model, self_dir=_self_dir())

    # Optional headless structured output: append the row's json_flag so the CLI
    # emits machine-readable cost. Off by default — the prose-fed path is untouched,
    # and a row with an empty json_flag (mock/generic/opencode/openclaw/ibm-bob)
    # silently stays prose-fed even with --json.
    want_json = bool(args.json)
    json_flag = str(row.get("json_flag", "")).strip()
    if want_json and json_flag and str(row.get("offline", "")).lower() != "true":
        cmd += shlex.split(os.path.expandvars(json_flag))
        # Claude Code: pair --output-format json with --json-schema for .structured_output.
        if args.json_schema and "--output-format" in json_flag:
            cmd += ["--json-schema", args.json_schema]

    # Per-iteration budget cap: render {budget} into the row's budget_flag (e.g.
    # claude-code → "--max-turns N"). Skipped when --budget is unset, the row has no
    # budget_flag, or the row is offline (mock).
    budget_flag = str(row.get("budget_flag", "")).strip()
    if args.budget is not None and budget_flag and str(row.get("offline", "")).lower() != "true":
        cmd += shlex.split(budget_flag.replace("{budget}", str(int(args.budget))))

    if not cmd:
        print(json.dumps({"optimizer": name, "error":
              "empty command — for generic/openclaw set the *_CMD env var"}))
        return 2

    # CLI present? (mock's helper is a python script we ship, always present.)
    exe = cmd[0]
    if str(row.get("offline", "")).lower() != "true" and shutil.which(exe) is None:
        print(json.dumps({"optimizer": name, "cli_present": False, "error":
              f"`{exe}` not on PATH. Install: {row.get('install_url') or 'see references'}. "
              f"Auth: {row.get('auth_notes')}"}))
        return 2

    auth = _resolve_env_keys(row)
    env = dict(os.environ)
    env.update(auth["env"])

    proc = subprocess.run(cmd, cwd=workdir, capture_output=True, text=True, env=env)
    result = {"optimizer": name, "cli_present": True, "returncode": proc.returncode,
              "auth_present": auth["present"],
              "stdout_tail": proc.stdout[-800:], "stderr_tail": proc.stderr[-500:]}
    # Best-effort cost capture: only when --json requested AND the row had a json_flag.
    # The prose-fed path (no --json, or empty json_flag) never reaches here, so the
    # offline/mock and generic flows are unchanged.
    if want_json and json_flag:
        cost = parse_cost(proc.stdout)
        result["cost"] = {"total_cost_usd": cost["usd"], "tokens": cost["tokens"]}
        if cost["usd"] is None:
            # Headless output wasn't parseable — say so; the loop falls back to no-cost.
            result["cost"]["note"] = ("no total_cost_usd in optimizer output; "
                                      "loop continues without a cost figure")
    print(json.dumps(result))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
