# VHS tape for the cap-evolve demo GIF.  Render from the repo root:  vhs docs/demo.tape
# Requires https://github.com/charmbracelet/vhs (+ ttyd + ffmpeg). Produces docs/demo.gif.

Output docs/demo.gif

Set Shell bash
Set Width 1180
Set Height 640
Set FontSize 18
Set Padding 22
Set Theme "Catppuccin Frappe"

# --- hidden setup: env + a throwaway toy project (not shown in the GIF) ---
Hide
Type "export PYTHONPATH=$PWD/core CAPEVOLVE_SKILLS_DIR=$PWD/skills" Enter
Type "export CAPEVOLVE_TOY_DATA=$PWD/examples/toy_calc CAPEVOLVE_MOCK_SCRIPT=$PWD/examples/toy_calc/mock_script.json" Enter
Type "export REPO=$PWD" Enter
Type "rm -rf .demo && mkdir -p .demo && cd .demo" Enter
Type "python3 $REPO/skills/phases/intake/scripts/run.py --base .capevolve --templates $REPO/templates/project >/dev/null" Enter
Type "cp $REPO/examples/toy_calc/adapter.py .capevolve/project/adapters/adapter.py" Enter
Type "cp -R $REPO/examples/toy_calc/capability seed_capability" Enter
Type "clear" Enter
Show

# --- shown demo ---
Type "# cap-evolve - optimize a prompt, prove the gain (zero-API toy)"
Enter
Sleep 900ms
Type "python3 -m cap_evolve.cli check .capevolve/project"
Enter
Sleep 2400ms
Type "python3 -m cap_evolve.cli run --spec .capevolve/project/capevolve.yaml --project .capevolve/project --run-ts demo"
Enter
Sleep 4500ms
Type "# baseline_val 0.0 -> test 1.0, gate-accepted, test sealed; dashboard written"
Enter
Sleep 1400ms
Type "ls .capevolve/run_demo/dashboard.html"
Enter
Sleep 1800ms
