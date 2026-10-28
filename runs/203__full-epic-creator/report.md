# cap-evolve run report — run_epic-intake-v1

- Best candidate: `cand_0002`
- Baseline val: 0.9181818181818181 ± 0.05296966229802624
- Best val: 0.9924242424242423 ± 0.015075567228888184
- **Held-out test (optimized skills): 0.9 ± 0.048386670078337086**  (pass^1=0.667, pass^2=0.429)
- Held-out test (baseline `seed` skills): 0.7023809523809523 ± 0.13984928719608014
- **Test improvement (optimized − baseline): +0.197619**
- Val→test gap: +0.092424 — selection optimism on val; this gap IS the overfitting
- Iterations: 10
- Optimized for: rits/zai-org/glm-5-3 (tier strong)

Test was scored exactly once on the sealed split, for BOTH the baseline (`seed`) and the optimized skills — the improvement above is on held-out tasks the optimizer never saw.
