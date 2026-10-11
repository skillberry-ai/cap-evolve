# E05 injected faults (zero LLM)

Scripts that feed the SpreadsheetBench scorer/adapter, the tau2 adapter and the harness deliberately broken inputs and
record what is detected. Output: `experiments/summaries/E05_injected_faults.json`.

* `e05_sb_harness.py` (SpreadsheetBench + harness; needs openpyxl, cap-evolve-core on `PYTHONPATH`; `REPO=<checkout>`)
* `e05_tau2_faults.py`, `e05_pregate.py`, `e05_pregate_strict.py`, `e05_tau2_gold_env.py` (tau2 @ `8ebb7499`, python 3.12 venv with tau2 + litellm; the gateway points at a dead port, nothing is called)
* `assemble_e05.py` merges the JSON each script prints (`E05JSON...`) into the summary
* `manifest.py` is the integrity-manifest prototype (write/verify sha256 trees)

Paths in the scripts name the machine they were run on (`/home/dev/projects2/campaign-scratch/bench`); adjust `BENCH`/`REPO`.
