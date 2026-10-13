#!/usr/bin/env python3
"""Structural consistency self-check for epic decompositions.

Usage:
    python3 check_decomposition.py <STRATEGY_ID> [--epic-dir artifacts/epic-tasks]
    python3 check_decomposition.py --self-check

Checks (structural invariants only — no semantic judgment, so a finding is
always a real inconsistency the downstream review rubric scores as critical):

  mermaid-frontmatter   Every dependency edge in the decomposition summary's
                        Mermaid DAG has a matching entry in the dependent
                        epic's frontmatter `dependencies`, and every
                        frontmatter dependency of a main-plan epic appears as
                        an edge in the diagram (both directions).
  dangling-dependency   An epic's `dependencies` references an epic_id that
                        has no file on disk.
  main-plan-branch-dep  A main-plan epic lists a `-BRANCH-<letter>-` epic in
                        its `dependencies` (branch epics are never created as
                        issues; depending on one dangles).
  dependency-cycle      The frontmatter dependency graph has a cycle.

Each finding names the file, the defect, and the exact fix. Exit 0 with
"OK: ..." when there are no findings; exit 1 with FINDING lines otherwise.
Exit 2 on usage/parse trouble BEFORE any artifacts were read (callers treat
non-zero-with-no-FINDING-lines as "check unavailable" and proceed).
"""
import glob
import os
import re
import sys

MERMAID_BLOCK = re.compile(r"```mermaid\b(.*?)```", re.S)
EDGE_LINE = re.compile(r"^\s*([A-Za-z0-9_-]+)(?:\[[^\]]*\]|\(\w+\)|\{[^}]*\})?\s*"
                       r"(-->|-\.->|==>)\s*"
                       r"([A-Za-z0-9_-]+)", re.M)
BRANCH_INFIX = re.compile(r"-BRANCH-[A-Z]-")
EPIC_FILE = re.compile(r"^(?P<id>.+?-E\d{3})\.md$")


def parse_frontmatter(text):
    """Return (dict, body). Values are raw strings; lists stay raw text."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm = {}
    current_key = None
    for line in parts[1].splitlines():
        if not line.strip() or line.strip().startswith("#"):
            current_key = None
            continue
        m = re.match(r"^([A-Za-z0-9_.]+):\s*(.*)$", line)
        if m and not line.startswith(" "):
            fm[m.group(1)] = m.group(2).strip()
            current_key = m.group(1)
        elif line.strip().startswith("- ") and current_key:
            fm[current_key] = (fm.get(current_key, "") + "\n" + line.strip()[2:]).strip()
    return fm, parts[2]


def parse_dependencies(raw):
    """Parse a frontmatter dependencies value: inline list, block list,
    comma-separated string, or quoted string. Returns list of ids."""
    if raw is None:
        return []
    ids = []
    for piece in re.split(r"[,\n]+", raw):
        piece = piece.strip()
        if piece.startswith("- "):
            piece = piece[2:]
        piece = piece.strip("\"'[]{} ")
        if piece:
            ids.append(piece)
    return ids


def mermaid_edges(summary_text):
    """Return the set of (dependency, dependent) short-id edges from all
    mermaid blocks. Node tokens may be short (E001) or full ids."""
    edges = set()
    for block in MERMAID_BLOCK.findall(summary_text):
        for line in block.splitlines():
            line = line.strip()
            if not line or line.startswith(("classDef", "style", "subgraph",
                                            "end", "click", "%%")):
                continue
            for m in EDGE_LINE.finditer(line):
                edges.add((m.group(1), m.group(3)))
    return edges


def normalize(node, strat_id):
    """Map a mermaid node token to a full epic id when possible."""
    if node.startswith(strat_id + "-"):
        return node
    if re.fullmatch(r"E\d{3}", node):
        return f"{strat_id}-{node}"
    return node


def load_epics(epic_dir, strat_id):
    """Return (main_plan, branch): dicts epic_id -> {'file', 'deps'}."""
    main_plan, branch = {}, {}
    pattern = os.path.join(epic_dir, f"{strat_id}-*E[0-9][0-9][0-9].md")
    for path in sorted(glob.glob(pattern)):
        name = os.path.basename(path)
        if name.endswith("-ai-signals.md"):
            continue
        m = EPIC_FILE.match(name)
        if not m:
            continue
        epic_id = m.group("id")
        fm, _ = parse_frontmatter(open(path, encoding="utf-8", errors="replace").read())
        entry = {"file": name, "deps": parse_dependencies(fm.get("dependencies"))}
        if BRANCH_INFIX.search(epic_id):
            branch[epic_id] = entry
        else:
            main_plan[epic_id] = entry
    return main_plan, branch


def check(strat_id, epic_dir):
    """Return a list of finding strings."""
    findings = []
    summary_path = os.path.join(epic_dir, f"{strat_id}-decomposition.md")
    if not os.path.isdir(epic_dir) or not os.path.exists(summary_path):
        return None  # nothing to check yet (triaged/incomplete) — not an error
    summary_text = open(summary_path, encoding="utf-8", errors="replace").read()
    main_plan, branch = load_epics(epic_dir, strat_id)
    all_ids = set(main_plan) | set(branch)

    # dangling dependencies + main-plan->branch deps
    for epic_id, entry in sorted(list(main_plan.items()) + list(branch.items())):
        for dep in entry["deps"]:
            if dep.endswith("-ai-signals"):
                continue
            if BRANCH_INFIX.search(dep) and epic_id in main_plan:
                findings.append(
                    f"FINDING main-plan-branch-dep: {entry['file']} lists branch epic "
                    f"{dep} in dependencies — branch epics are never created as issues. "
                    f"Fix: depend on the gating Investigation epic instead, or move this "
                    f"work into that branch.")
            elif dep not in all_ids:
                findings.append(
                    f"FINDING dangling-dependency: {entry['file']} depends on {dep}, "
                    f"which has no epic file. Fix: remove the dependency or create the "
                    f"epic file.")

    # mermaid <-> frontmatter (main-plan only; branch conventions differ)
    has_mermaid = bool(MERMAID_BLOCK.search(summary_text))
    if has_mermaid and main_plan:
        diagram = {(normalize(a, strat_id), normalize(b, strat_id))
                   for a, b in mermaid_edges(summary_text)}
        fm_edges = set()
        for epic_id, entry in main_plan.items():
            for dep in entry["deps"]:
                fm_edges.add((dep, epic_id))
        # restrict comparison to edges between main-plan epics
        diag_main = {(a, b) for a, b in diagram
                     if a in main_plan and b in main_plan}
        for dep, epic_id in sorted(fm_edges - diag_main):
            findings.append(
                f"FINDING mermaid-frontmatter: {main_plan[epic_id]['file']} declares a "
                f"dependency on {dep}, but the summary's Mermaid DAG has no "
                f"{dep.split('-')[-1]} --> {epic_id.split('-')[-1]} arrow. "
                f"Fix: add the arrow to the Mermaid diagram.")
        for dep, epic_id in sorted(diag_main - fm_edges):
            findings.append(
                f"FINDING mermaid-frontmatter: the summary's Mermaid DAG draws "
                f"{dep.split('-')[-1]} --> {epic_id.split('-')[-1]}, but "
                f"{main_plan[epic_id]['file']} does not list {dep} in its frontmatter "
                f"dependencies. Fix: add {dep} to that epic's dependencies (or remove "
                f"the arrow if it is not a real dependency).")

    # cycles over all epics
    graph = {eid: [d for d in e["deps"] if d in all_ids]
             for eid, e in list(main_plan.items()) + list(branch.items())}
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {eid: WHITE for eid in graph}

    def visit(node, stack):
        color[node] = GRAY
        for nxt in graph.get(node, []):
            if color.get(nxt) == GRAY:
                findings.append(
                    f"FINDING dependency-cycle: "
                    f"{' -> '.join(stack + [node, nxt])}. "
                    f"Fix: remove the least-justified edge in the cycle.")
            elif color.get(nxt) == WHITE:
                visit(nxt, stack + [node])
        color[node] = BLACK

    for eid in sorted(graph):
        if color[eid] == WHITE:
            visit(eid, [])
    return findings


def run(strat_id, epic_dir):
    try:
        findings = check(strat_id, epic_dir)
    except Exception as exc:  # fail-open: never block the pipeline
        print(f"consistency check unavailable: {exc}")
        return 0
    if findings is None:
        print("OK: no decomposition artifacts to check yet")
        return 0
    if not findings:
        n = len(glob.glob(os.path.join(epic_dir, f"{strat_id}-*E[0-9][0-9][0-9].md"))) \
            - len(glob.glob(os.path.join(epic_dir, f"{strat_id}-*E[0-9][0-9][0-9]-ai-signals.md")))
        print(f"OK: no structural findings ({n} epics checked)")
        return 0
    for f in findings:
        print(f)
    return 1


def self_check():
    import tempfile
    ok = [0]

    def case(name, files, expect_findings):
        with tempfile.TemporaryDirectory() as td:
            ed = os.path.join(td, "artifacts", "epic-tasks")
            os.makedirs(ed)
            for fname, content in files.items():
                open(os.path.join(ed, fname), "w").write(content)
            got = check("STRAT-1", ed) or []
            matched = (len(got) > 0) == expect_findings
            ok[0] += matched
            print(f"  {'PASS' if matched else 'FAIL'} {name}: {len(got)} finding(s)"
                  f"{'' if matched else ' (expected findings=' + str(expect_findings) + ')'}")

    def epic(eid, deps):
        if deps:
            depstr = "dependencies:\n" + "\n".join(f"- {d}" for d in deps)
        else:
            depstr = "dependencies: []"
        return f"---\nepic_id: {eid}\n{depstr}\n---\n# {eid}\n"

    summary_dag = ("---\nparent_strat: STRAT-1\n---\n# S\n```mermaid\ngraph TD\n"
                   "E001[\"a\"] --> E002[\"b\"]\nE002 --> E003[\"c\"]\n```\n")
    case("consistent dag", {
        "STRAT-1-decomposition.md": summary_dag,
        "STRAT-1-E001.md": epic("STRAT-1-E001", []),
        "STRAT-1-E002.md": epic("STRAT-1-E002", ["STRAT-1-E001"]),
        "STRAT-1-E003.md": epic("STRAT-1-E003", ["STRAT-1-E002"]),
    }, False)
    case("frontmatter dep missing from diagram", {
        "STRAT-1-decomposition.md": summary_dag,
        "STRAT-1-E001.md": epic("STRAT-1-E001", []),
        "STRAT-1-E002.md": epic("STRAT-1-E002", ["STRAT-1-E001"]),
        "STRAT-1-E003.md": epic("STRAT-1-E003", ["STRAT-1-E001", "STRAT-1-E002"]),
    }, True)
    case("diagram edge missing from frontmatter", {
        "STRAT-1-decomposition.md": ("---\n---\n```mermaid\ngraph TD\n"
                                     "E001 --> E002\nE002 --> E003\nE001 --> E003\n```\n"),
        "STRAT-1-E001.md": epic("STRAT-1-E001", []),
        "STRAT-1-E002.md": epic("STRAT-1-E002", ["STRAT-1-E001"]),
        "STRAT-1-E003.md": epic("STRAT-1-E003", ["STRAT-1-E002"]),
    }, True)
    case("dangling dependency", {
        "STRAT-1-decomposition.md": summary_dag,
        "STRAT-1-E001.md": epic("STRAT-1-E001", []),
        "STRAT-1-E002.md": epic("STRAT-1-E002", ["STRAT-1-E001"]),
        "STRAT-1-E003.md": epic("STRAT-1-E003", ["STRAT-1-E009"]),
    }, True)
    case("dependency cycle", {
        "STRAT-1-decomposition.md": ("---\n---\n```mermaid\ngraph TD\n"
                                     "E001 --> E002\nE002 --> E001\n```\n"),
        "STRAT-1-E001.md": epic("STRAT-1-E001", ["STRAT-1-E002"]),
        "STRAT-1-E002.md": epic("STRAT-1-E002", ["STRAT-1-E001"]),
    }, True)
    case("branch epics excluded from diagram comparison", {
        "STRAT-1-decomposition.md": summary_dag,
        "STRAT-1-E001.md": epic("STRAT-1-E001", []),
        "STRAT-1-E002.md": epic("STRAT-1-E002", ["STRAT-1-E001"]),
        "STRAT-1-E003.md": epic("STRAT-1-E003", ["STRAT-1-E002"]),
        "STRAT-1-BRANCH-A-E004.md": epic("STRAT-1-BRANCH-A-E004",
                                         ["STRAT-1-E003"]),
        "STRAT-1-BRANCH-A-E005.md": epic("STRAT-1-BRANCH-A-E005",
                                         ["STRAT-1-BRANCH-A-E004"]),
    }, False)
    case("main-plan epic depending on branch epic", {
        "STRAT-1-decomposition.md": summary_dag,
        "STRAT-1-E001.md": epic("STRAT-1-E001", []),
        "STRAT-1-E002.md": epic("STRAT-1-E002", ["STRAT-1-E001"]),
        "STRAT-1-E003.md": epic("STRAT-1-E003", ["STRAT-1-BRANCH-A-E004"]),
        "STRAT-1-BRANCH-A-E004.md": epic("STRAT-1-BRANCH-A-E004", []),
    }, True)
    case("no mermaid (triaged single epic) is not a finding", {
        "STRAT-1-decomposition.md": "---\ntriage: below-threshold\n---\n# S\n",
        "STRAT-1-E001.md": epic("STRAT-1-E001", []),
    }, False)
    case("comma-string dependencies parse", {
        "STRAT-1-decomposition.md": summary_dag,
        "STRAT-1-E001.md": epic("STRAT-1-E001", []),
        "STRAT-1-E002.md": ("---\nepic_id: STRAT-1-E002\n"
                            "dependencies: \"STRAT-1-E001\"\n---\n"),
        "STRAT-1-E003.md": ("---\nepic_id: STRAT-1-E003\n"
                            "dependencies: [STRAT-1-E002]\n---\n"),
    }, False)
    print(f"self-check: {ok[0]}/9 cases pass")
    return 0 if ok[0] == 9 else 1


def main(argv):
    if "--self-check" in argv:
        return self_check()
    args = [a for a in argv[1:] if not a.startswith("--")]
    epic_dir = "artifacts/epic-tasks"
    for i, a in enumerate(argv):
        if a == "--epic-dir" and i + 1 < len(argv):
            epic_dir = argv[i + 1]
    if len(args) < 1:
        print(__doc__)
        return 2
    return run(args[0], epic_dir)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
