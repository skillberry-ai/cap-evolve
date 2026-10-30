# v6 audits

Read-only audits of the Global run (`v6_g2_e1`) and its sealed-test comparison. Each script reads
recorded trials only and reruns nothing. Paths default to the CCC worktrees the runs used; override
them with `V6_G2_RUN`, `V6_G2_SEALED`, `V6_TREE` and `V6_REPO` (see `_common.py`).

| Script | Question | Written up in `parsec-history` |
|---|---|---|
| `control_batch_audit.py` | What was the anomalously low Seed-control batch (0.401), did it decide cand_0002's acceptance, and did the cand_0002 gain reproduce? | `results/v6/v6_t4_e1/AUDITS.md` §1 |
| `platform131_audit.py` | Why did `platform-131` fall from 0.985 to 0.590 under cand_0005, and how much of that is the verifier's contract? | §2 |
| `test_infra_audit.py` | Are the sealed-test results affected by simulator or infrastructure failures? | §3 |
| `optimizer_token_mix.py` | Why does a token total not compare effort across arms? | `RESULTS_FOR_PAPER.md` Table 2 notes |

The write-ups state what is recorded and what is inference. The scripts print the numbers they quote.
