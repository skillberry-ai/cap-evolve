# cap-evolve run report — run_SWE-BENCH-VERIFIED-WITH-GLM-UNLIMITED-TURNS

- Best candidate: `cand_0005`
- Baseline val: 0.896 ± 0.02741320614170736
- Best val: 0.976 ± 0.013744206990818044
- **Held-out test (optimized skills): 0.9590163934426229 ± 0.018022930882932674**  (pass^1=0.959)
- Held-out test (baseline `seed` skills): 0.8688524590163934 ± 0.030687422178798808
- **Test improvement (optimized − baseline): +0.090164**
- Val→test gap: +0.016984 — selection optimism on val; this gap IS the overfitting
- Iterations: 10

Test was scored exactly once on the sealed split, for BOTH the baseline (`seed`) and the optimized skills — the improvement above is on held-out tasks the optimizer never saw.
