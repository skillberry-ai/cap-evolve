# cap-evolve run report — run_swebench-harnessfix-s1

- Best candidate: `cand_0002`
- Baseline val: 0.5106382978723404 ± 0.07370428968378201
- Best val: 0.5454545454545454 ± 0.07593355178041425
- **Held-out test (optimized skills): 0.53125 ± 0.05119862636932033**  (pass^1=0.531)
- Held-out test (baseline `seed` skills): 0.5773195876288659 ± 0.050417184711756734
- **Test improvement (optimized − baseline): -0.04607**
- Val→test gap: +0.014205 — selection optimism on val; this gap IS the overfitting
- Iterations: 7

Test was scored exactly once on the sealed split, for BOTH the baseline (`seed`) and the optimized skills — the improvement above is on held-out tasks the optimizer never saw.
