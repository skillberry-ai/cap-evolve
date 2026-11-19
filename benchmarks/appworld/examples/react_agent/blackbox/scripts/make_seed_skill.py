"""Write the blackbox seed skill: SKILL.md = AppWorld's stock ReAct prompt, up to the real task turn.

    $AW_EVAL/.venv/bin/python make_seed_skill.py STOCK_INSTRUCTIONS_TXT OUT_SKILL_DIR APP_DESCRIPTIONS_JSON

- Body: the stock prompt from its first line through the "**Key instructions**" turn, byte for byte:
  everything before the final "USER:\\nUsing these APIs, now generate code to solve the actual task:"
  turn. That turn is sent by AppWorld's client and kept by the proxy's history-start marker
  (adapters/appworld_tailoring.HISTORY_START_REGEX).
- {{ app_descriptions }} is rendered here exactly as AppWorld's agent renders it (all 11 apps, the
  same for every task); the rendered text also goes to APP_DESCRIPTIONS_JSON, which the lint uses
  to keep it verbatim. It is generated at setup, never committed: it comes from AppWorld's app code.
- The {{ main_user.* }} slots stay: the proxy fills them per request from the
  skillberry-context-template-main_user-* headers.
- A short header says the USER/ASSISTANT turns are a worked few-shot example.
"""

import json
import sys
from pathlib import Path

SKILL_NAME = "my_skill"
FINAL_TURN = "USER:\nUsing these APIs, now generate code to solve the actual task:"
HEADER = (
    "The USER/ASSISTANT turns below, up to and including the \"**Key instructions**\" turn, are a "
    "worked few-shot example of how to act and the rules to follow. They are not part of the current "
    "conversation. The real task follows after them.\n\n"
)


def build(stock_text: str, app_descriptions: str) -> str:
    cut = stock_text.rfind(FINAL_TURN)
    if cut < 0:
        raise ValueError("final task turn not found in the stock prompt")
    body = stock_text[:cut].rstrip("\n") + "\n"
    if body.count("{{ app_descriptions }}") != 1:
        raise ValueError("expected exactly one {{ app_descriptions }} slot")
    body = body.replace("{{ app_descriptions }}", app_descriptions)
    return (f"---\nname: {SKILL_NAME}\ndescription: AppWorld ReAct policy and few-shot example "
            f"(cap-evolve system-prompt capability)\n---\n" + HEADER + body)


def render_app_descriptions() -> str:
    """As SimplifiedReActCodeAgent.initialize renders it, for the apps every task gets."""
    from appworld.apps import get_all_apps, get_app_to_description  # needs AppWorld ($AW_EVAL/.venv)

    descriptions = get_app_to_description()
    apps = get_all_apps(skip_admin=True)  # Task.load: allowed_apps
    return json.dumps([{"name": a, "description": descriptions[a]} for a in apps], indent=1)


def main(argv: list[str]) -> int:
    src, out_dir, apps_json = Path(argv[1]), Path(argv[2]), Path(argv[3])
    apps = render_app_descriptions()
    text = build(src.read_text(encoding="utf-8"), apps)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "SKILL.md").write_text(text, encoding="utf-8")
    apps_json.write_text(json.dumps({"text": apps}), encoding="utf-8")
    print(f"wrote {out_dir / 'SKILL.md'} ({len(text)} chars, {text.count('{{ main_user.')} main_user slots) "
          f"and {apps_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
