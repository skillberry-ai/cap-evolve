# "All" experiment — recipes

Two cap-evolve project configs, both starting from the same `seed_capability`
(the four office-doc skills: docx, pdf, pptx, xlsx). Sourced from `intake_skillbench_c1`'s
`.capevolve/project/`.

- **`capevolve.all87.yaml`** + `split_ids.all87.json` — the literal all-87-task
  pass-rate-parity sweep, train==val across all 87 SkillsBench tasks. Budget scaled ~13x
  over the original 10-task run ($8000 max). **Both attempts to run this
  (`run_all87_iter7_v1`, `run_all87_iter7_v2`) were killed by CCC infrastructure errors
  (task-image build failures, agent-install rc=127, timeouts) before any candidate was
  accepted — `state.json` shows `best_id: "seed"` for both.** There is no optimized
  artifact for this recipe, only the seed (see `../../artifacts/all/seed/`).

- **`capevolve.runnable.yaml`** + `split_ids.runnable.json` — a derived recipe that
  filters to the 43 of 87 tasks that actually ran cleanly in the killed `all87_iter7_v2`
  seed pass (build + install + verifier succeed). Same seed capability, same optimizer/gate
  settings, budget scaled down accordingly ($1500 max). This is the recipe that actually
  produced an accepted candidate: `run_runnable_iter7_v1_KILLED_iter4_optimizer_hung_2h`
  reached `cand_0002` (3 accepted iterations) before being killed by a hung optimizer call
  on iteration 4. This is the best artifact under `../../artifacts/all/best-runnable-subset/`.

To rerun either: copy the yaml + split_ids file into a fresh `.capevolve/project/`
alongside a `seed_capability/` (see `../../artifacts/all/seed/`), point
`runner_repo_path` at a local `vendor/skillsbench` checkout, and run
`cap-evolve run capevolve.<name>.yaml`.
