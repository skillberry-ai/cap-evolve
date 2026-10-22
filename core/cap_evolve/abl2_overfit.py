"""A2b (abl2_scope=policy): tools byte-identical + anti-overfit lint on policy/policy.md.

The forbidden set (reservation ids, user ids, emails, customer names, flight numbers, payment ids, and
city+date pairs that co-occur with a reservation/user id) is mined ONCE from the SEED's train rollouts
(``<run_dir>/rollouts/val/*__seed__t*.json``), lazily at the first check, and cached in the run dir
(``abl2_forbidden.json``). Anything that also appears in the fixed benchmark policy
(``reference/benchmark_policy.md``) is generic and never forbidden.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

CACHE = "abl2_forbidden.json"
_RES = re.compile(r"\b(?=[A-Z0-9]{6}\b)(?=[A-Z]*\d)(?=\d*[A-Z])[A-Z0-9]{6}\b")      # letters+digits mix
_RES_CTX = re.compile(r"(?i:reservation(?:_id)?|booking|confirmation)[^A-Za-z0-9\n]{0,24}((?=[A-Z0-9]*\d)[A-Z0-9]{6})\b")
_RES_KEY = re.compile(r'"reservation_id"\s*:\s*"([A-Z0-9]{6})"')
_USER = re.compile(r"\b[a-z]+_[a-z]+_\d{2,}\b")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_FLIGHT = re.compile(r"\bHAT\d{3}\b")
_PAY = re.compile(r"\b(?:credit_card|gift_card|certificate|paypal_account|payment)_\d{3,}\b")
_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_IATA = re.compile(r"\b[A-Z]{3}\b")
_SELFNAME = re.compile(r"(?:I'm|I am|my name is|name is|this is)\s+([A-Z][a-z]+ [A-Z][a-z]+)")
_TASK = re.compile(r"\btask(?:[ _-]?id)?[ _#:=-]*\(?(\d+)\b", re.I)
_AIRPORTS = {"ATL", "DFW", "DEN", "ORD", "LAX", "CLT", "MCO", "LAS", "PHX", "MIA", "SEA", "SFO", "EWR", "JFK",
             "BOS", "IAH", "MSP", "DTW", "PHL", "LGA"}


def _files(src) -> list:
    if isinstance(src, (str, Path)):
        p = Path(src)
        if p.is_dir():
            return sorted(p.glob("*__seed__t*.json"))
        return [p]
    return [Path(x) for x in src]


def _texts(d) -> list:
    """Message-level texts of one rollout: user-sim messages, tool outputs, assistant tool-call args."""
    out = []
    for m in (d.get("rollout") or {}).get("trace") or []:
        if not isinstance(m, dict):
            continue
        parts = []
        if isinstance(m.get("content"), str):
            parts.append(m["content"])
        for tc in m.get("tool_calls") or []:
            parts.append(json.dumps(tc.get("arguments", {})))
        if parts:
            out.append("\n".join(parts))
    return out


def _walk_names(obj, acc):
    if isinstance(obj, dict):
        fn, ln = obj.get("first_name"), obj.get("last_name")
        if isinstance(fn, str) and isinstance(ln, str) and fn and ln:
            acc.add(f"{fn} {ln}")
        for v in obj.values():
            _walk_names(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _walk_names(v, acc)


def build_forbidden(src, benchmark_policy_text: str = "") -> dict:
    ids, users, emails, names, flights, pays = set(), set(), set(), set(), set(), set()
    pairs, task_ids = set(), set()
    for f in _files(src):
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        tid = (d.get("rollout") or {}).get("task_id") or (d.get("score") or {}).get("task_id")
        if tid is not None:
            task_ids.add(str(tid))
        for t in _texts(d):
            ids.update(_RES.findall(t))
            ids.update(_RES_CTX.findall(t))
            ids.update(_RES_KEY.findall(t))
            u = set(_USER.findall(t))
            users.update(u)
            emails.update(_EMAIL.findall(t))
            flights.update(_FLIGHT.findall(t))
            pays.update(_PAY.findall(t))
            names.update(_SELFNAME.findall(t))
            try:
                _walk_names(json.loads(t), names)
            except ValueError:
                for m in re.finditer(r"\{[^{}]*\"first_name\"[^{}]*\}", t):
                    try:
                        _walk_names(json.loads(m.group(0)), names)
                    except ValueError:
                        pass
            if u or _RES_CTX.search(t) or _RES.search(t):         # city+date only next to a reservation/user id
                dates = set(_DATE.findall(t))
                cities = {c for c in _IATA.findall(t) if c in _AIRPORTS}
                pairs.update((c, dt) for c in cities for dt in dates)
        for u in users:                                            # name implied by a user id
            parts = u.split("_")
            names.add(" ".join(p.capitalize() for p in parts[:-1]))
    bench = benchmark_policy_text or ""
    low = bench.lower()
    keep = lambda s: s.lower() not in low                          # noqa: E731 generic = in benchmark policy
    names = {n for n in names if keep(n)}
    return {
        "reservation_ids": sorted(x for x in ids if x not in bench and not x.startswith("HAT")),
        "user_ids": sorted(x for x in users if keep(x)),
        "emails": sorted(x for x in emails if keep(x)),
        "names": sorted(names),
        "flight_numbers": sorted(x for x in flights if x not in bench),
        "payment_ids": sorted(x for x in pays if keep(x)),
        "city_dates": sorted([c, dt] for c, dt in pairs if dt not in bench),
        "task_ids": sorted(task_ids),
    }


def policy_findings(policy_text: str, forbidden: dict, task_ids=None) -> list[str]:
    text = policy_text or ""
    out = []
    for key, label, flags in (("reservation_ids", "reservation id", 0), ("user_ids", "user id", re.I),
                              ("emails", "email", re.I), ("names", "customer name", re.I),
                              ("flight_numbers", "flight number", 0), ("payment_ids", "payment id", re.I)):
        for v in forbidden.get(key, []):
            if re.search(r"(?<![A-Za-z0-9_])" + re.escape(v) + r"(?![A-Za-z0-9_])", text, flags):
                out.append(f"{label} {v!r} (from train traces)")
    for c, dt in forbidden.get("city_dates", []):
        for ln in text.splitlines():
            if re.search(r"\b" + re.escape(c) + r"\b", ln) and dt in ln:
                out.append(f"city+date {c} {dt} (from train traces)")
                break
    ids = {str(t) for t in (task_ids if task_ids is not None else forbidden.get("task_ids", []))}
    for m in _TASK.finditer(text):
        if not ids or m.group(1) in ids:
            out.append(f"task id reference {m.group(0).strip()!r}")
    return out


def _forbidden_for_run(run_dir, parent_dir) -> dict:
    root = Path(run_dir if isinstance(run_dir, (str, Path)) else run_dir.root)
    cache = root / CACHE
    if cache.is_file():
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except ValueError:
            pass
    bench = ""
    for base in (Path(parent_dir), root.parent / "project" / "seed_capability"):
        b = base / "reference" / "benchmark_policy.md"
        if b.is_file():
            bench = b.read_text(encoding="utf-8", errors="replace")
            break
    forb = build_forbidden(root / "rollouts" / "val", bench)
    cache.write_text(json.dumps(forb, indent=1), encoding="utf-8")
    return forb


def policy_scope_violation(parent_dir, cand_dir, run_dir=None):
    """(lint, detail) or None. 'surface' when tools/ (or anything else) changed, 'overfit' for the lint."""
    from .abl_surface import surface_violation
    v = surface_violation("P", parent_dir, cand_dir)
    if v:
        return ("surface", v)
    p = Path(cand_dir) / "policy" / "policy.md"
    if not p.is_file() or run_dir is None:
        return None
    forb = _forbidden_for_run(run_dir, parent_dir)
    pol = p.read_text(encoding="utf-8", errors="replace")
    old = Path(parent_dir) / "policy" / "policy.md"
    prev = set(policy_findings(old.read_text(encoding="utf-8", errors="replace"), forb)) if old.is_file() else set()
    f = [x for x in policy_findings(pol, forb) if x not in prev]
    return ("overfit", "; ".join(f[:8]) + (f" (+{len(f) - 8} more)" if len(f) > 8 else "")) if f else None
