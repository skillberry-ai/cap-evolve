"""Build the optimizer's read-only reference dir (public AppWorld docs only, no task data).

    python make_reference.py OUT_DIR

Writes api_index.md (every app and API: method, required/optional parameters, one-line
description, generated from data/api_docs/standard) and react_agent_notes.md (how the agent
under test runs a candidate).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from awpaths import ROOT_OPT  # noqa: E402

NOTES = """# How the agent under test runs a candidate (AppWorld simplified ReAct code agent)

- Model: gpt-oss-120b (reasoning effort medium, temperature 0), 40K-token context window,
  6,000 completion tokens per step, at most 50 steps, prior reasoning is not re-sent.
- `policy/instructions.txt` is a Jinja template rendered with `instruction`, `main_user`
  (first_name, last_name, email, phone_number) and `app_descriptions`, then split into chat
  messages on lines `USER:` / `ASSISTANT:` / `SYSTEM:` followed by a newline. The worked
  demo is a sequence of such messages. The final USER message must end with
  `My name is: … Task: {{ instruction }}`.
- Each step the model answers with text and ONE ```python code block; only the first block
  runs (`ignore_multiple_calls`). The code runs in a persistent IPython REPL that holds
  `apis` (all app APIs: `apis.<app>.<api>(**kwargs)`) and `requester`. The REPL output is
  sent back as `Output:` in a USER message. Older outputs are replaced by
  `[NOT SHOWN FOR BREVITY]` once the history exceeds 60,000 characters.
- The episode ends when the code calls `apis.supervisor.complete_task(...)`, after 50 steps,
  or after 100,000 completion tokens. The evaluator then compares the final app databases
  (and the answer, if one is required) with the task's hidden requirements. Changing state
  the task did not ask for fails the "no collateral damage" checks.
- REPL restrictions: imports outside the AppWorld allowlist fail; in this harness `os`,
  `pathlib`, `io`, `shutil` and `glob` are also blocked; `open`, `subprocess`, `sys`,
  `socket` are blocked. Only the app APIs may be used to read or change app state.
- `tools/helpers.py` is executed once in the REPL before step 1, so its functions are
  callable from the agent's code. The prompt then gets one line listing them. Helpers must
  take `apis` and app/API names as parameters (no hardcoded `apis.<app>.` chains, no app or
  API name string literals) and may import only re, json, math, datetime, itertools,
  collections, functools.
- `tools/api_notes.json` maps `"app"` or `"app.api"` to a note (at most 400 characters).
  `apis.api_docs.show_api_doc(...)` returns the original doc plus a `note` field;
  `show_api_descriptions(app_name=...)` adds `note` to the listed APIs (and appends the app
  note). The original doc text is never changed.
- Lint before you stop: `python lints.py .` (path given in INSTRUCTIONS.md) must print
  `"ok": true`, or the candidate is rejected without being run.
"""


def main(argv: list[str]) -> int:
    out = Path(argv[1])
    out.mkdir(parents=True, exist_ok=True)
    lines = ["# AppWorld API index (generated from the public API docs)", "",
             "Read the full spec of one API in the REPL with "
             "`apis.api_docs.show_api_doc(app_name=..., api_name=...)`.", ""]
    for f in sorted((ROOT_OPT / "data/api_docs/standard").glob("*.json")):
        docs = json.loads(f.read_text())
        lines += [f"## {f.stem} ({len(docs)} APIs)", ""]
        for name, d in docs.items():
            req = [p["name"] for p in d.get("parameters", []) if p.get("required")]
            opt = [p["name"] for p in d.get("parameters", []) if not p.get("required")]
            lines.append(f"- `{name}` {d.get('method', '')} — {d.get('description', '').strip()} "
                         f"required: {', '.join(req) or '-'}; optional: {', '.join(opt) or '-'}")
        lines.append("")
    (out / "api_index.md").write_text("\n".join(lines))
    (out / "react_agent_notes.md").write_text(NOTES)
    print(f"wrote {out}/api_index.md ({len(lines)} lines) and react_agent_notes.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
