"""Dependency-free guard on the pandas/pyarrow SIGSEGV fix.

`test_spreadsheetbench_pandas_backend.py` proves the fix *behaves* correctly, but it needs
pandas and openpyxl — and `core[dev]` installs only pytest, so in CI it skips entirely. A
guard that never runs where changes land is not a guard. These checks are pure AST/source
inspection: they run everywhere and fail if someone removes the fix or reintroduces the
crashing pattern.

Background: run 30634898569 died with SIGSEGV in `ArrowStringArray._from_sequence`, reached
from `_spreadsheet_preview` inside the rollout thread pool. pandas 3.x makes `str` columns
pyarrow-backed by default; the fix pins `mode.string_storage = "python"` once per process.
"""

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ADAPTER = REPO / "templates" / "adapters" / "spreadsheetbench" / "adapter.py"


def _tree():
    return ast.parse(ADAPTER.read_text(encoding="utf-8"))


def _func(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"{name}() not found in {ADAPTER}")


def test_adapter_pins_the_python_string_backend():
    """The one line that keeps pyarrow out of the read_excel path."""
    assigns = [
        n for n in ast.walk(_tree())
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Attribute) and t.attr == "string_storage" for t in n.targets)
    ]
    assert assigns, (
        "no `...string_storage = ...` assignment: pandas 3.x will build ArrowStringArray "
        "columns again and the rollout pool can segfault (run 30634898569)"
    )
    values = {n.value.value for n in assigns if isinstance(n.value, ast.Constant)}
    assert values == {"python"}, f'expected string_storage set to "python", found {values}'


def test_preview_gets_pandas_through_the_configuring_helper():
    """A bare `import pandas as pd` inside the preview bypasses the fix — that is the regression."""
    preview = _func(_tree(), "_spreadsheet_preview")
    imports = [n for n in ast.walk(preview) if isinstance(n, (ast.Import, ast.ImportFrom))]
    imported = []
    for node in imports:
        if isinstance(node, ast.Import):
            imported += [a.name for a in node.names]
        elif node.module:
            imported.append(node.module)
    assert not any(m and m.split(".")[0] == "pandas" for m in imported), (
        "_spreadsheet_preview imports pandas directly, bypassing the helper that pins the "
        "non-Arrow string backend"
    )
    calls = [n.func.id for n in ast.walk(preview)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
    assert "_pandas" in calls, "_spreadsheet_preview must obtain pandas via _pandas()"


def test_no_per_call_option_context():
    """option_context restores on exit; in a thread pool that races the other workers."""
    calls = [
        n for n in ast.walk(_tree())
        if isinstance(n, ast.Call)
        and ((isinstance(n.func, ast.Attribute) and n.func.attr == "option_context")
             or (isinstance(n.func, ast.Name) and n.func.id == "option_context"))
    ]
    assert not calls, (
        f"pd.option_context called at line {calls[0].lineno if calls else '?'}: it mutates a "
        "process-global option and restores it on exit, so one thread can restore the Arrow "
        "backend while another is mid-read"
    )


def test_every_pandas_entry_point_goes_through_the_helper():
    """Any future pandas user in this adapter must route through _pandas(), not import it."""
    tree = _tree()
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name == "_pandas":
            continue  # the helper itself is the single sanctioned import site
        for inner in ast.walk(node):
            if isinstance(inner, ast.Import) and any(
                a.name.split(".")[0] == "pandas" for a in inner.names
            ):
                offenders.append(f"{node.name}:{inner.lineno}")
            elif isinstance(inner, ast.ImportFrom) and inner.module and \
                    inner.module.split(".")[0] == "pandas":
                offenders.append(f"{node.name}:{inner.lineno}")
    assert not offenders, (
        f"pandas imported outside _pandas() at {offenders} — those call sites skip the "
        "string-backend fix"
    )
