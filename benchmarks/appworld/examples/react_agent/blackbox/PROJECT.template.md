# AppWorld blackbox: the system prompt, delivered by the Skillberry Store + Proxy-Agent

Example: benchmarks/appworld/examples/react_agent/blackbox/README.md (repo @REPO@). Resolved inputs:
- capability: system-prompt + tools = the seed folder: my_skill/SKILL.md (the store skill) and
  tools/helpers.py + tools/api_notes.json (run in the trial's REPL before step 1 by the episode
  worker, as in the direct approach; empty in the seed). capability_path: seed_capability (committed). SKILL.md seed: AppWorld's stock ReAct
  prompt @ 42b5bcf up to the real task turn, app list rendered, main_user slots rendered per request
  by the proxy)
- target: AppWorld's stock SimplifiedReActCodeAgent and stock prompt; LLM calls go to the proxy
  (openai/ibm/skillberry-local), which calls SPA_MODEL_NAME derived from AW_MODEL_NAME / AW_MODEL_URL / AW_KEY_*
- optimizer: claude-code, @OPT_MODEL@; instructions: @INSTRUCTIONS@
- data: adapter tasks(); split_ids.json train = val = official train ∪ dev (147), test = []
- stack: store + proxy at the pinned commits in the shared vendor/ (or $SPA_VENDOR_DIR)
