---
name: nlp-research-repo-package-installment
version: "1.0"
description: Align the Python version and repo-declared dependencies (environment.yml / requirements.txt) and build a REPRODUCIBLE venv before installing packages for NLP research-code reproduction. Use when reproducing an NLP research repo whose results (e.g. a saved loss/metric) must be re-runnable by a downstream reproducer or grader.
---

# NLP Research Repo Package Installment

When reproducing an NLP research repo, **align the environment to the repo's declared dependencies first, and build the venv where a downstream reproducer expects it, with `pip` inside it.** Most reproduction failures are not the math — they are environment setup: wrong Python version, a venv the reproducer can't find, or a venv that has no `pip`.

## Fastest path: run the bundled setup script (do not hand-roll it)

```
bash /skills/nlp-research-repo-package-installment/scripts/setup_repro_env.sh /root/<repo>
```

It reads the repo's `environment.yml`, then deterministically: installs `uv`; creates a **pip-seeded** venv at the conventional path for the declared Python (Python 3.10 → `/opt/py310`); guarantees the `pip` module is importable (exits non-zero if not); symlinks `python`/`pip` to it; and installs the declared versions of the core libraries (torch family from the CPU wheel index, plus transformers/trl/accelerate/datasets/peft/numpy and the packages trl imports at load time such as `rich`/`wandb`). After it finishes, run the repo's unit test with that interpreter and log the environment (see steps 4–5).

## What to do (in order — this is also what the script does)

1. **Read the repo dependency files.** Prefer `environment.yml` / `environment.yaml` (usually pins **Python** + deps); else `requirements.txt`. Note the **exact declared versions** of Python and the heavy libs (`torch`/`torchvision`/`torchaudio`).

2. **Create the venv at the CONVENTIONAL path for the declared Python, WITH pip.**
- A downstream reproducer re-runs your code with `<venv>/bin/python -m pip …` and `-m pytest …`, and it looks for that interpreter at the path derived from the declared Python major.minor: **Python 3.10 → `/opt/py310`**, 3.11 → `/opt/py311`, etc. Build the venv **exactly there** — not at `/opt/venv`, `/opt/py310_simpo`, or any other name — or the reproducer won't find it and will fall back to a fresh, often-unresolvable install and fail.
- `uv venv` **without `--seed`** (and `uv pip install`) do **not** put the `pip` module inside the venv. Your own installs still work, but the reproducer's `python -m pip` then dies with **"No module named pip"**. Always seed pip and verify it:
```
export PATH="/root/.local/bin:$PATH"
uv python install <VERSION_FROM_environment.yml>            # e.g. 3.10.14
uv venv --seed --python <VERSION_FROM_environment.yml> /opt/py310   # --seed installs pip
/opt/py310/bin/python -m ensurepip --upgrade               # belt-and-suspenders
/opt/py310/bin/python -m pip --version                     # MUST succeed before continuing
```
- Use that interpreter (`/opt/py310/bin/python`) for **every** install and run.

3. **Install the declared versions.** Install from the repo's dependency files at the **declared** versions; do not silently substitute `torch`/`torchvision`/`torchaudio`. For CPU wheels use the matching index explicitly (a `+cpu`/`+cuXXX` build is not on default PyPI):
```
/opt/py310/bin/python -m pip install torch==<DECLARED> torchvision==<DECLARED> torchaudio==<DECLARED> \
    --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple
```
Then install the remaining declared deps and do a quick import smoke test of the module you must reproduce.

4. **Run the repo's unit test with THIS interpreter** to produce the required output (e.g. the saved loss), so the recorded environment is the one that generated the result:
```
cd /root/<repo> && PYTHONPATH=/root/<repo> /opt/py310/bin/python <repo>/unit_test/<the_test>.py
```

5. **Log the environment for reproduction.** Write the requested file (often `/root/python_info.txt`) with the **same** interpreter:
```
{ /opt/py310/bin/python -VV; echo; /opt/py310/bin/python -m pip freeze; } > /root/python_info.txt
```
`python -VV` from the 3.10 venv records the Python version a reproducer checks for; `pip freeze` (needs pip in the venv, per step 2) records the exact packages.
