#!/usr/bin/env python3
"""Extract public function names from a Python file.

Vendored from skillberry-benchmarks/tau2/scripts/extract_functions.py so this
example's setup.sh registers exactly the same primitive tool set as the
benchmark's ``import-primitive-tools`` Makefile target.

Functions whose name starts with '_' are EXCLUDED. That is the mechanism that
keeps ``_make_api_call`` from ever becoming a store tool.
"""
import ast
import sys

if len(sys.argv) != 2:
    print("Usage: extract_functions.py <python_file>", file=sys.stderr)
    sys.exit(1)

try:
    with open(sys.argv[1], "r") as f:
        tree = ast.parse(f.read())

    funcs = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
    ]

    print(" ".join(funcs))
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
