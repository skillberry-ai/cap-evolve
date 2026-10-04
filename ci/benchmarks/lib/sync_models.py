#!/usr/bin/env python3
"""Sync the benchmark model pickers to what the gateway key can actually serve.

  sync_models.py --models PREFIX=PATH [--models PREFIX=PATH ...] [--check|--write] [--repo <root>]

Each ``PATH`` is the raw body of a ``GET <that provider's base>/models`` call, repeatable
once per polled gateway (e.g. ``--models ibm-ete-int=/tmp/a.json --models ibm-ete=/tmp/b.json``).

WHY THIS EXISTS
---------------
The ``agent_model`` / ``optimizer_model`` pickers in .github/workflows/benchmarks.yml are a
STATIC list, and the gateway's per-key entitlements are not. When they drift, every LLM call
dies with ``team not allowed to access model`` and the suite reports a clean-looking 0.000 —
that is run 31124146014, which burned 11 minutes and $2.56 before anything noticed. At the
time, 15 of the 30 agent options were unusable, including the workflow's own default.

Rotating the gateway key changes the served set wholesale, so the lists have to be regenerated
rather than hand-patched. Measured on 2026-08-09: the outgoing key served 34 models, the
incoming one 23, with 14 present only in the old key.

WHAT IT TOUCHES
---------------
1. .github/workflows/benchmarks.yml — the ``options:`` blocks of both pickers. Rewritten to
   exactly the served set, sorted case-insensitively for a stable, reviewable diff.
2. Defaults (``default:`` on each picker, and the ``AGENT_MODEL`` / ``OPTIMIZER_MODEL``
   fallbacks in run_suite.sh) are CHECKED, never silently rewritten — see below.
3. ci/benchmarks/*/<tier>/tasks.json ``agent`` pins are checked and reported. They are
   advisory (run_suite.sh warns on mismatch; the env value is authoritative), so a stale pin
   is noise, not breakage.

HOW AN UNSERVED DEFAULT IS HANDLED
----------------------------------
Which model a benchmark defaults to IS the measurement, so this tool never picks one for you.

When a default is no longer served, the default is KEPT and carried into the options list even
though the gateway cannot serve it. Two reasons:

  * a `default:` absent from its own `options:` is an INVALID workflow — actionlint rejects it
    and the dispatch dialog cannot honour it — so the value has to appear in both places;
  * keeping it makes an unset dispatch FAIL LOUDLY instead of silently running something else.
    ci_setup.sh's entitlement preflight rejects the run in seconds, before any spend, naming the
    models the key can serve. Dropping the default and letting GitHub fall back to the first
    option would silently substitute a different model — a changed measurement disguised as
    list maintenance, which is far worse than a clear failure.

That is a deliberate policy choice: the model stays visible and broken until it is re-entitled
on the key. Pass --agent-default / --optimizer-default to move to a served model instead; that
updates the picker default and run_suite.sh's matching fallback together.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

WORKFLOW = Path(".github/workflows/benchmarks.yml")
RUN_SUITE = Path("ci/benchmarks/lib/run_suite.sh")
CATALOG = Path("ci/benchmarks/model_catalog.txt")
PICKERS = ("agent_model", "optimizer_model")
PROVIDERS = ("ibm-rits", "ibm-ete-int", "ibm-ete")

EXIT_OK, EXIT_DRIFT, EXIT_DECISION = 0, 1, 2


def _prefix(model_id: str) -> str:
    """The CI provider tag a served/option model id carries, e.g. 'ibm-ete-int'."""
    return model_id.split("/", 1)[0]


def _is_plain(model_id: str) -> bool:
    """A plain catalog name ("claude-opus-5") rather than a provider-pinned CI id."""
    return _prefix(model_id) not in PROVIDERS


def parse_catalog(text: str) -> tuple[list[str], list[tuple[str, list[str]]], list[str]]:
    """(provider order, [(plain name, [ci ids])] in file order, errors) for model_catalog.txt.

    The same format resolve_provider.sh reads with `while read`: one `order ...` line, then one
    `model <name> <id> ...` line per model; `#` lines and blank lines are ignored.
    """
    order: list[str] = []
    models: list[tuple[str, list[str]]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for n, raw in enumerate(text.splitlines(), 1):
        parts = raw.split()
        if not parts or parts[0].startswith("#"):
            continue
        if parts[0] == "order":
            order = parts[1:]
            unknown = [p for p in order if p not in PROVIDERS]
            if unknown or sorted(order) != sorted(PROVIDERS):
                errors.append(f"line {n}: order must list each of {', '.join(PROVIDERS)} once, got {' '.join(order)}")
        elif parts[0] == "model":
            if len(parts) < 3:
                errors.append(f"line {n}: a model line needs a name and at least one CI id")
                continue
            name, ids = parts[1], parts[2:]
            if not _is_plain(name) or "/" in name:
                errors.append(f"line {n}: plain name {name!r} must not contain '/' or a provider prefix")
            if name in seen:
                errors.append(f"line {n}: {name!r} is listed twice")
            seen.add(name)
            providers = [_prefix(i) for i in ids]
            for i, p in zip(ids, providers):
                if p not in PROVIDERS:
                    errors.append(f"line {n}: {name}: {i!r} has no provider prefix")
            if len(set(providers)) != len(providers):
                errors.append(f"line {n}: {name}: more than one id for the same provider")
            models.append((name, ids))
        else:
            errors.append(f"line {n}: unknown line kind {parts[0]!r}")
    if not order:
        errors.append("no `order` line")
    return order, models, errors


def read_catalog(repo: Path) -> tuple[list[str], list[tuple[str, list[str]]], list[str]] | None:
    """parse_catalog() of the repo's catalog, or None when the repo has no catalog file."""
    path = repo / CATALOG
    if not path.exists():
        return None
    return parse_catalog(path.read_text(encoding="utf-8"))


def _bare_id(model_id: str) -> str:
    """The pre-rename shape a tasks.json pin uses: rits/<vendor>/<model> for ibm-rits ids
    (resolve_provider.sh only strips the 'ibm-' part for RITS), the bare suffix otherwise."""
    prefix, _, rest = model_id.partition("/")
    return f"rits/{rest}" if prefix == "ibm-rits" else rest


def served_ids(body: str) -> list[str]:
    """Model ids from an OpenAI-shaped /models body, tolerant of shape drift."""
    payload = json.loads(body)
    rows = payload.get("data", []) if isinstance(payload, dict) else payload
    out = []
    for row in rows if isinstance(rows, list) else []:
        mid = row if isinstance(row, str) else (row or {}).get("id")
        if isinstance(mid, str) and mid:
            out.append(mid)
    # Case-insensitive sort: the gateway mixes `Azure/` and `azure/`, and a stable order keeps
    # the generated diff reviewable instead of churning.
    return sorted(set(out), key=lambda s: (s.lower(), s))


def _picker_span(text: str, picker: str) -> tuple[int, int, str]:
    """Byte span of one picker's ``options:`` list, plus its indent.

    Anchors on the picker name, then its `options:` key, then consumes the contiguous run of
    `- "…"` items. Deliberately narrow: it must not wander into the next input's block.
    """
    m = re.search(rf"^(\s*){re.escape(picker)}:\s*$", text, re.M)
    if not m:
        raise ValueError(f"picker {picker!r} not found in the workflow")
    opt = re.search(r"^(\s*)options:\s*$", text[m.end():], re.M)
    if not opt:
        raise ValueError(f"no options: block under {picker!r}")
    start = m.end() + opt.end() + 1  # first char after "options:\n"
    indent = opt.group(1) + "  "
    pos = start
    item = re.compile(rf"^{re.escape(indent)}- \"[^\"]*\"\s*$")
    for line in text[start:].splitlines(keepends=True):
        if not item.match(line.rstrip("\n") + ""):
            break
        pos += len(line)
    if pos == start:
        raise ValueError(f"{picker!r} options block is empty or unrecognised")
    return start, pos, indent


def current_options(text: str, picker: str) -> list[str]:
    s, e, _ = _picker_span(text, picker)
    return re.findall(r'- "([^"]*)"', text[s:e])


def current_default(text: str, picker: str) -> str | None:
    m = re.search(rf"^\s*{re.escape(picker)}:\s*$", text, re.M)
    if not m:
        return None
    d = re.search(r'^\s*default:\s*"([^"]*)"\s*$', text[m.end():], re.M)
    return d.group(1) if d else None


def rewrite_default(text: str, picker: str, model: str) -> str:
    """Replace one picker's ``default:`` value, leaving every other input alone."""
    m = re.search(rf"^\s*{re.escape(picker)}:\s*$", text, re.M)
    if not m:
        raise ValueError(f"picker {picker!r} not found")
    d = re.compile(r'^(\s*default:\s*)"[^"]*"(\s*)$', re.M)
    tail = text[m.end():]
    mo = d.search(tail)
    if not mo:
        raise ValueError(f"no default: under {picker!r}")
    new_tail = tail[:mo.start()] + f'{mo.group(1)}"{model}"{mo.group(2)}' + tail[mo.end():]
    return text[:m.end()] + new_tail


def rewrite_run_suite_default(text: str, var: str, model: str) -> str:
    """Point run_suite.sh's ${VAR:-fallback} at ``model``."""
    return re.sub(rf'^{var}="\$\{{{var}:-[^}}]*\}}"', f'{var}="${{{var}:-{model}}}"', text, count=1, flags=re.M)


def rewrite_options(text: str, picker: str, models: list[str]) -> str:
    s, e, indent = _picker_span(text, picker)
    block = "".join(f'{indent}- "{m}"\n' for m in models)
    return text[:s] + block + text[e:]


def run_suite_defaults(text: str) -> dict[str, str]:
    out = {}
    for var in ("AGENT_MODEL", "OPTIMIZER_MODEL"):
        m = re.search(rf'^{var}="\$\{{{var}:-([^}}]*)\}}"', text, re.M)
        if m:
            out[var] = m.group(1)
    return out


def task_pins(repo: Path) -> dict[str, set[str]]:
    """{'<bench>/<tier>': {pinned agent models}} across every tasks.json."""
    pins: dict[str, set[str]] = {}
    # */*/ for a flat bench, */*/*/ for a nested one (tau2_custom/<arm>/<tier>/).
    for f in sorted([*(repo / "ci" / "benchmarks").glob("*/*/tasks.json"),
                     *(repo / "ci" / "benchmarks").glob("*/*/*/tasks.json")]):
        try:
            rows = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        agents = {a for r in rows if isinstance(r, dict)
                  for a in [r.get("agent")] if isinstance(a, str) and a}
        if agents:
            pins[f"{f.parent.parent.name}/{f.parent.name}"] = agents
    return pins


def sync(repo: Path, models: list[str], polled_prefixes: set[str], write: bool,
         agent_default: str | None = None, optimizer_default: str | None = None) -> tuple[int, list[str]]:
    """Returns (exit_code, report lines)."""
    rep: list[str] = []
    if not models:
        return EXIT_DECISION, ["::error:: gateway returned no models — refusing to blank the pickers"]

    wf_path = repo / WORKFLOW
    text = wf_path.read_text(encoding="utf-8")
    rs_path = repo / RUN_SUITE
    rs_text = rs_path.read_text(encoding="utf-8") if rs_path.exists() else ""
    rep.append(f"gateway serves {len(models)} model(s)")

    # ---- the catalog of plain names. Never edited here: only a person can confirm that two ids
    # are the same model. This only reports catalog ids a polled gateway no longer serves.
    catalog = read_catalog(repo)
    catalog_names: list[str] = []
    if catalog is not None:
        _, cat_models, cat_errors = catalog
        if cat_errors:
            return EXIT_DECISION, rep + [f"::error:: {CATALOG}: {e}" for e in cat_errors]
        catalog_names = [name for name, _ in cat_models]
        served = set(models)
        for name, ids in cat_models:
            gone = [i for i in ids if _prefix(i) in polled_prefixes and i not in served]
            for i in gone:
                rep.append(f"  ::warning:: {CATALOG}: {name} -> {i} is NOT served by this key; fix or remove it by hand")
            if gone and len(gone) == len(ids):
                rep.append(f"  ::warning:: {CATALOG}: {name} has no served provider left")

    # ---- defaults FIRST. A default outside its own options is an invalid workflow, so if we
    # cannot end up with a valid file we must not write the options either.
    wanted = {"agent_model": agent_default, "optimizer_model": optimizer_default}
    rs_var = {"agent_model": "AGENT_MODEL", "optimizer_model": "OPTIMIZER_MODEL"}
    blockers: list[str] = []
    keep: dict[str, str] = {}   # picker -> unserved default retained to keep the workflow valid
    for picker, override in wanted.items():
        cur = current_default(text, picker)
        if override:
            if override not in models and override not in catalog_names:
                blockers.append(f"::error:: requested {picker} default {override!r} is not served by this key"
                                f" and is not a plain name in {CATALOG}")
                continue
            if override != cur:
                text = rewrite_default(text, picker, override)
                rs_text = rewrite_run_suite_default(rs_text, rs_var[picker], override)
                rep.append(f"  {picker}: default {cur!r} -> {override!r} (and {rs_var[picker]} fallback)")
        elif cur and _is_plain(cur) and catalog is not None and cur not in catalog_names:
            blockers.append(f"::error:: {picker} default {cur!r} is a plain name that {CATALOG} does not list;"
                            f" add it there or pass --{picker.replace('_model','')}-default")
        elif cur and _prefix(cur) in polled_prefixes and cur not in models:
            # Retained on purpose — see "HOW AN UNSERVED DEFAULT IS HANDLED" above. It must stay
            # in `options` too or the workflow is invalid. Scoped to defaults whose own prefix was
            # actually polled this run — a default under a prefix we didn't poll (e.g. ibm-rits,
            # never entitlement-listed) isn't "unserved," it's simply out of scope for this call.
            keep[picker] = cur
            rep.append(
                f"  ::warning:: {picker} unserved default {cur!r} is NOT served by this key. Kept anyway, so an"
                f" unset dispatch fails LOUDLY at the entitlement preflight (seconds, no spend)"
                f" rather than silently running a different model. Choose a served model in the"
                f" dispatch dialog, or pass --{picker.replace('_model','')}-default to change it.")
    if blockers:
        rep.extend(blockers)
        rep.append("  candidate served defaults: " + ", ".join(models[:8]) + (" …" if len(models) > 8 else ""))
        return EXIT_DECISION, rep

    # Options are per-picker: the served set, plus any current option under a prefix this run
    # never polled (e.g. ibm-rits — hand-curated, never entitlement-listed), plus THAT picker's
    # own retained default if it is unserved. Retaining the default globally would offer an
    # unusable model in the other picker too.
    # Plain catalog names come FIRST, in the catalog's own order (it is grouped by vendor), so the
    # dispatch dialog leads with the names that get provider fallback. With no catalog file, any
    # plain options already present are kept as they are.
    def opts_for(picker: str) -> list[str]:
        extra = keep.get(picker)
        current = current_options(text, picker)
        plain = catalog_names if catalog is not None else [o for o in current if _is_plain(o)]
        unpolled_kept = {o for o in current if not _is_plain(o) and _prefix(o) not in polled_prefixes}
        pinned = sorted(unpolled_kept | set(models) | ({extra} if extra and not _is_plain(extra) else set()),
                        key=lambda s: (s.lower(), s))
        return list(plain) + pinned

    changed = rs_text != (rs_path.read_text(encoding="utf-8") if rs_path.exists() else "")
    for picker in PICKERS:
        want = opts_for(picker)
        cur = current_options(text, picker)
        if cur == want:
            rep.append(f"  {picker}: {len(cur)} option(s), already in sync")
            continue
        added, removed = sorted(set(want) - set(cur)), sorted(set(cur) - set(want))
        rep.append(f"  {picker}: {len(cur)} -> {len(want)} option(s)")
        for m in removed:
            rep.append(f"    - {m}   (no longer served)")
        for m in added:
            rep.append(f"    + {m}   (newly served)")
        text = rewrite_options(text, picker, want)
        changed = True

    # Advisory: task pins only produce a warning at run time. Pins are written in the
    # pre-rename bare/rits-prefixed shape; served models always carry a CI prefix now, so
    # compare against each served id's bare form rather than the prefixed id itself.
    served_bare = {_bare_id(m) for m in models}
    for tier, agents in task_pins(repo).items():
        bad = sorted(a for a in agents if a not in served_bare)
        if bad:
            rep.append(f"  ::warning:: tasks.json {tier} pins unserved agent(s): {', '.join(bad)}")

    if changed and write:
        wf_path.write_text(text, encoding="utf-8")
        rep.append(f"WROTE {WORKFLOW}")
        if rs_path.exists():
            rs_path.write_text(rs_text, encoding="utf-8")
    elif changed:
        rep.append(f"DRIFT in {WORKFLOW} (use --write to apply)")

    if changed and not write:
        return EXIT_DRIFT, rep
    return EXIT_OK, rep


def validate(workflow_text: str, run_suite_text: str,
             catalog_text: str | None = None) -> tuple[bool, list[str]]:
    """Assert every picker default is among its own options — no repo or gateway needed.

    With ``catalog_text`` (model_catalog.txt), also assert the catalog parses and that every
    plain-name option is a catalog name: a plain name the catalog does not list would pass the
    dispatch dialog and then fail at the preflight.

    A ``default:`` outside its ``options:`` is an INVALID workflow: actionlint rejects it and
    the dispatch dialog cannot honour it. Kept here rather than inline in the workflow so the
    check is unit-tested and runs identically on a runner without actionlint installed.

    ``run_suite_text`` is accepted for parity with this module's other text-based helpers (see
    ``run_suite_defaults()``) but not cross-checked here — the workflow's own default/options
    pair is the only invariant this validates.
    """
    del run_suite_text
    rep, bad = [], False
    names: set[str] | None = None
    if catalog_text is not None:
        _, cat_models, cat_errors = parse_catalog(catalog_text)
        for e in cat_errors:
            rep.append(f"::error:: {CATALOG}: {e}")
        bad = bool(cat_errors)
        names = {name for name, _ in cat_models}
    for picker in PICKERS:
        opts, dflt = current_options(workflow_text, picker), current_default(workflow_text, picker)
        if dflt not in opts:
            rep.append(f"::error:: {picker} default {dflt!r} is not among its own {len(opts)} options")
            bad = True
        else:
            rep.append(f"  {picker}: {len(opts)} options, default {dflt!r} OK")
        if names is not None:
            for o in opts:
                if _is_plain(o) and o not in names:
                    rep.append(f"::error:: {picker} option {o!r} is a plain name that {CATALOG} does not list")
                    bad = True
    return not bad, rep


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", action="append", default=[], metavar="PREFIX=PATH",
                    help="PREFIX=PATH to a /models response body, repeatable, one per gateway"
                         " provider (not needed with --validate)")
    ap.add_argument("--repo", default=".", help="repository root")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="report drift, write nothing (default)")
    g.add_argument("--write", action="store_true", help="apply the update")
    ap.add_argument("--agent-default", help="set the agent_model default (must be served)")
    ap.add_argument("--optimizer-default", help="set the optimizer_model default (must be served)")
    ap.add_argument("--validate", action="store_true",
                    help="only check that each picker default is among its own options")
    a = ap.parse_args(argv)

    if a.validate:
        wf_text = (Path(a.repo) / WORKFLOW).read_text(encoding="utf-8")
        rs_path = Path(a.repo) / RUN_SUITE
        rs_text = rs_path.read_text(encoding="utf-8") if rs_path.exists() else ""
        cat_path = Path(a.repo) / CATALOG
        cat_text = cat_path.read_text(encoding="utf-8") if cat_path.exists() else None
        ok, report = validate(wf_text, rs_text, cat_text)
        for line in report:
            print(line)
        return EXIT_OK if ok else EXIT_DECISION
    if not a.models:
        print("::error:: --models is required unless --validate is given")
        return EXIT_DECISION

    models: list[str] = []
    polled_prefixes: set[str] = set()
    for spec in a.models:
        prefix, sep, path = spec.partition("=")
        if not sep or not prefix or not path:
            print(f"::error:: --models must be PREFIX=PATH, got {spec!r}")
            return EXIT_DECISION
        try:
            served = served_ids(Path(path).read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"::error:: cannot parse {path}: {exc}")
            return EXIT_DECISION
        polled_prefixes.add(prefix)
        models.extend(f"{prefix}/{m}" for m in served)

    code, report = sync(Path(a.repo), models, polled_prefixes, write=a.write,
                        agent_default=a.agent_default, optimizer_default=a.optimizer_default)
    for line in report:
        print(line)
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
