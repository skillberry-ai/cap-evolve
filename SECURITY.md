# Security Policy

## Supported versions
AgentCapTune is at `0.x` (beta). Fixes land on the latest commit of the default branch.

## Reporting a vulnerability
Please report security issues privately (do **not** open a public issue): open a
[GitHub security advisory](https://docs.github.com/en/code-security/security-advisories)
on the repository, or email the maintainers. Include a description, reproduction
steps, and impact. We aim to acknowledge within a few days.

## Scope notes
- AgentCapTune runs external agent CLIs (the optimizers) and executes user-provided
  adapter code and a target benchmark. Run optimizations in an environment you
  trust; the `claude-code`/`codex`/`gemini-cli` optimizers use auto-approve flags
  on a throwaway candidate copy by design.
- `capabilities/tools` and `tau2_runtime` `exec()` user/optimizer-authored tool
  code. Treat candidate code as untrusted; the run dir is the blast radius.
