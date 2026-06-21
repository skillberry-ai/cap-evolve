# generic optimizer

The escape hatch: drive ANY shell-invokable agent. Set `CAPEVOLVE_OPTIMIZER_CMD`
to your agent's non-interactive edit command, with `{workdir}` and `{prompt}`
placeholders (the runner also offers `{prompt_text}`).

```bash
export CAPEVOLVE_OPTIMIZER_CMD='my-agent edit --dir {workdir} --instructions {prompt}'
```

- **Install / auth:** whatever your agent CLI needs.
- If your agent has a CLI, it plugs in here without a code change.
