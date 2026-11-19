# AppWorld blackbox: the system prompt, delivered by the Skillberry Store + Proxy-Agent

Example: benchmarks/appworld/examples/react_agent/blackbox/README.md (repo @REPO@). Resolved inputs:
- capability: system-prompt only = the store skill my_skill/SKILL.md (seed: AppWorld's stock ReAct
  prompt @ 42b5bcf up to the real task turn, app list rendered, main_user slots rendered per request
  by the proxy)
- target: AppWorld's stock SimplifiedReActCodeAgent and stock prompt; LLM calls go to the proxy
  (openai/ibm/skillberry-local), which calls SPA_MODEL_NAME derived from AW_MODEL_NAME / AW_MODEL_URL / AW_KEY_*
- optimizer: claude-code, @OPT_MODEL@; instructions: @INSTRUCTIONS@
- data: adapter tasks(); split_ids.json train = val = official train ∪ dev (147), test = []
- stack: store + proxy at the pinned commits in the shared vendor/ (or $SPA_VENDOR_DIR)
