"""Legacy spreadsheetbench unit tests build tiny fake datasets whose answer files sit inside DATA_DIR and
score them directly. Since #782 the adapter refuses that layout unless it is explicitly allowed, so default
the opt-out for the whole test session. test_spreadsheetbench_gold_isolation.py scrubs these variables and
tests the real defaults."""
import os

os.environ.setdefault("SPREADSHEETBENCH_AGENT_VIEW", "0")
os.environ.setdefault("SPREADSHEETBENCH_ALLOW_GOLD_IN_MOUNT", "1")
