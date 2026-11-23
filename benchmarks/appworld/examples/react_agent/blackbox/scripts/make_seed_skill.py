"""The blackbox seed: build the committed seed, and render it into a project at setup.

    $AW_EVAL/.venv/bin/python make_seed_skill.py SEED_DIR OUT_SEED_DIR APP_DESCRIPTIONS_JSON
        render the committed seed (../seed_capability) into the project: copy it, filling
        {{ app_descriptions }} in my_skill/SKILL.md (what scripts/setup_project.sh runs)
    python make_seed_skill.py --build STOCK_INSTRUCTIONS_TXT SEED_DIR
        (re)write the committed seed from AppWorld's stock prompt (the direct seed's
        ../../seed_capability/policy/instructions.txt is that prompt, byte for byte)

The committed seed, ``seed_capability/``, is what every candidate looks like:
- ``my_skill/SKILL.md`` (the store skill, the system prompt). Its body is the stock prompt from its first
  line through the "**Key instructions**" turn, byte for byte: everything before the final
  "USER:\\nUsing these APIs, now generate code to solve the actual task:" turn. That turn is sent by
  AppWorld's client and kept by the proxy's history-start marker
  (adapters/appworld_tailoring.HISTORY_START_REGEX). A short header says the USER/ASSISTANT turns are a
  worked few-shot example.
- {{ app_descriptions }} stays a placeholder there, as in the direct seed: the rendered app list comes
  from AppWorld's installed app code and is never committed. At setup it is rendered exactly as
  AppWorld's agent renders it (all 11 apps, the same for every task); the rendered text also goes to
  APP_DESCRIPTIONS_JSON, which the lint uses to keep it verbatim. The proxy cannot fill it per request
  (multi-line JSON does not fit in a header).
- The {{ main_user.* }} slots stay in both: the proxy fills them per request from the
  skillberry-context-template-main_user-* headers.
- ``tools/helpers.py`` (a docstring only) and ``tools/api_notes.json`` ({}), the direct seed's own files:
  they load nothing, so the seed deploys no REPL loader and keeps the stock agent's behaviour.
"""

import json
import shutil
import sys
from pathlib import Path

SKILL_NAME = "my_skill"
FINAL_TURN = "USER:\nUsing these APIs, now generate code to solve the actual task:"
APP_SLOT = "{{ app_descriptions }}"
HEADER = (
    "The USER/ASSISTANT turns below, up to and including the \"**Key instructions**\" turn, are a "
    "worked few-shot example of how to act and the rules to follow. They are not part of the current "
    "conversation. The real task follows after them.\n\n"
)


FRONTMATTER = (
    "---\n"
    f"name: {SKILL_NAME}\n"
    "description: AppWorld ReAct policy and few-shot example (cap-evolve system-prompt capability)\n"
    "---\n"
)


def build(stock_text: str, app_descriptions: str = APP_SLOT) -> str:
    """SKILL.md from the stock prompt; the default keeps the app list a placeholder (the committed seed)."""
    # Everything before the client's final task turn: the demo and the key instructions.
    cut = stock_text.rfind(FINAL_TURN)
    if cut < 0:
        raise ValueError("final task turn not found in the stock prompt")
    body = stock_text[:cut].rstrip("\n") + "\n"

    if body.count(APP_SLOT) != 1:
        raise ValueError("expected exactly one {{ app_descriptions }} slot")
    body = body.replace(APP_SLOT, app_descriptions)

    return FRONTMATTER + HEADER + body


def render(skill_text: str, app_descriptions: str) -> str:
    """Fill the one app-list placeholder of the committed SKILL.md."""
    if skill_text.count(APP_SLOT) != 1:
        raise ValueError("the committed SKILL.md must hold exactly one {{ app_descriptions }} slot")
    return skill_text.replace(APP_SLOT, app_descriptions)


SEED_HELPERS = (
    '"""Helper functions defined in the AppWorld REPL before step 1 (capability: tools).\n'
    "\n"
    "Empty in the seed. See optimizer/INSTRUCTIONS.md for the rules a helper must follow.\n"
    '"""\n'
)


def write_tools(seed: Path) -> None:
    """The seed's tools capability, as in the direct seed: no helpers, no API notes."""
    tools = seed / "tools"
    tools.mkdir(parents=True, exist_ok=True)
    (tools / "helpers.py").write_text(SEED_HELPERS, encoding="utf-8")
    (tools / "api_notes.json").write_text("{}\n", encoding="utf-8")


def render_app_descriptions() -> str:
    """As SimplifiedReActCodeAgent.initialize renders it, for the apps every task gets."""
    from appworld.apps import get_all_apps, get_app_to_description  # needs AppWorld ($AW_EVAL/.venv)

    descriptions = get_app_to_description()
    apps = get_all_apps(skip_admin=True)  # Task.load: allowed_apps
    return json.dumps([{"name": a, "description": descriptions[a]} for a in apps], indent=1)


def build_committed_seed(stock: Path, seed: Path) -> None:
    """--build: (re)write the committed seed from AppWorld's stock prompt."""
    (seed / SKILL_NAME).mkdir(parents=True, exist_ok=True)
    (seed / SKILL_NAME / "SKILL.md").write_text(build(stock.read_text(encoding="utf-8")), encoding="utf-8")
    write_tools(seed)
    print(f"wrote the committed seed {seed}")


def render_into_project(seed: Path, out_dir: Path, apps_json: Path) -> None:
    """Copy the committed seed into the project, with AppWorld's app list filled into SKILL.md."""
    apps = render_app_descriptions()

    # A fresh copy of the whole seed folder (my_skill/SKILL.md and tools/) ...
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(seed, out_dir, ignore=shutil.ignore_patterns("__pycache__"))

    # ... with the one placeholder rendered in its SKILL.md.
    text = render((seed / SKILL_NAME / "SKILL.md").read_text(encoding="utf-8"), apps)
    (out_dir / SKILL_NAME / "SKILL.md").write_text(text, encoding="utf-8")

    # The rendered list also goes to its own file: the lint keeps it verbatim in SKILL.md.
    apps_json.write_text(json.dumps({"text": apps}), encoding="utf-8")

    slots = text.count("{{ main_user.")
    print(f"wrote {out_dir} from {seed} ({len(text)} chars, {slots} main_user slots, "
          f"app list rendered) and {apps_json}")


def main(argv: list[str]) -> int:
    if len(argv) > 1 and argv[1] == "--build":
        build_committed_seed(Path(argv[2]), Path(argv[3]))
        return 0
    render_into_project(Path(argv[1]), Path(argv[2]), Path(argv[3]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
