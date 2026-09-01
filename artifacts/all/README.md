# "All" experiment — artifacts

- **`seed/`** — the starting `seed_capability` (docx/pdf/pptx/xlsx skills) shared by both
  `capevolve.all87.yaml` and `capevolve.runnable.yaml`. This is also the final state of
  the pure all-87-task recipe, since neither of its two run attempts got past baseline.

- **`best-runnable-subset/`** — `cand_0002` from `run_runnable_iter7_v1_KILLED_iter4_optimizer_hung_2h`,
  the best accepted candidate under the 43-task runnable-subset recipe (see
  `../../recipes/all/README.md`). Adds `docx/scripts/fill_template.py`, `INSTRUCTIONS.md`,
  and `PROCESS.md` on top of the seed, plus in-place edits to the existing skill files.
  `__pycache__/` excluded (evidence it executed, not part of the artifact).
