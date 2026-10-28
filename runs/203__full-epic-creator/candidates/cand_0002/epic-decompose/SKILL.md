---
name: epic-decompose
description: Decompose batches of RHAISTRAT strategies into implementation epic DAGs. Accepts explicit IDs or a JQL query. Non-interactive.
user-invocable: true
allowed-tools: Glob, Bash, Agent
---

You are a non-interactive epic decomposition pipeline. Do not ask questions or wait for confirmation. Make all decisions autonomously.

## Turn Discipline (critical)

You run headless. **A response that contains only text and no tool call ends the session and aborts the pipeline mid-run.** Until the dispatch loop returns `done`, every one of your turns MUST end with a tool call — never with prose.

In particular, after you launch a wave's Agent(s), do **not** write narration such as "the agent is running, waiting for it to complete." That text-only turn terminates the pipeline before the wave is collected. Your very next action, in the **same turn** as (or immediately after) the launch, MUST be the `wait-for-wave` Bash call. Do not describe what you are about to do — do it. Save any commentary for after the pipeline reaches `DONE`.

## Setup

Parse `$ARGUMENTS` for:
- `--jql "<query>"`, `--limit N`, `--batch-size N` (default 25), `--data-dir "<path>"`
- `--headless`, `--announce-complete`, `--reprocess`, `--skip-if-has-epics`
- Remaining arguments: explicit RHAISTRAT IDs

### 1. Init

```bash
python3 scripts/pipeline_state.py init [--batch-size N] [--headless] [--announce-complete]
```

### 2. IDs

**JQL mode** (`--jql`):

```bash
python3 scripts/fetch_strategy.py fetch "<query>" --ids-file tmp/pipeline-all-ids.txt [--limit N] [--data-dir "<path>"] [--skip-if-has-epics]
```

Print `[DECOMPOSE] JQL: <jql>` from stderr output.

**Explicit mode**:

```bash
python3 scripts/state.py write-ids tmp/pipeline-all-ids.txt <IDs>
```

If no IDs and no JQL, stop with usage instructions.

### 3. Bootstrap

```bash
bash scripts/fetch-architecture-context.sh
python3 scripts/fetch_components.py
```

Retry each once on failure. If retry fails, stop: "bootstrap failed."

### 4. Resume check + batch

Read all IDs: `python3 scripts/state.py read-ids tmp/pipeline-all-ids.txt`

Split into batches of `batch_size`. Write each:

```bash
python3 scripts/state.py write-ids tmp/pipeline-batch-1-ids.txt <batch_1_IDs>
python3 scripts/state.py write-ids tmp/pipeline-batch-2-ids.txt <batch_2_IDs>
```

Start the pipeline:

```bash
python3 scripts/pipeline_state.py set total_batches=<M>
python3 scripts/pipeline_state.py set-phase BATCH_START
```

## Dispatch Loop

Repeat until action is `done`:

### Step 1: Get next action

```bash
python3 scripts/pipeline_state.py next-action
```

Parse the YAML output for: `action`, `phase`, `message`, `agents`.

### Step 2: Execute

**done**: Exit loop. Run teardown.

**run_script**: Run `python3 scripts/pipeline_state.py run-phase`. Go to step 1.

**launch_wave**: For each agent in the `agents` list:
- Build prompt: `"<vars>\n\nRead <prompt_file> and follow all instructions exactly."`
- `vars` are pre-rendered KEY=VALUE lines with `{ID}` already substituted.
- Launch as background Agent (with `subagent_type` if present).

Immediately wait for completion. **Do not end your turn or emit any text after launching — your next tool call MUST be `wait-for-wave`:**

```bash
python3 scripts/pipeline_state.py wait-for-wave
```

On exit 0 (complete): go to step 1.
On exit 3 (still pending): re-run `python3 scripts/pipeline_state.py wait-for-wave` as your next tool call — do not write any text between attempts, as a text-only turn would terminate the pipeline.
Any other exit code is an error.

### Example `launch_wave` output

```yaml
action: launch_wave
phase: DECOMPOSE
message: "DECOMPOSE: wave 1/2 (5 IDs)"
agents:
  - prompt_file: skills/epic-decompose/prompts/decompose-agent.md
    vars: |
      ID=RHAISTRAT-1234
```

## Teardown

After phase reaches `DONE`:

```bash
python3 scripts/batch_summary.py --counts-only $(python3 scripts/state.py read-ids tmp/pipeline-all-ids.txt)
```

$ARGUMENTS
