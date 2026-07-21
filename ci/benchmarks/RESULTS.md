# Benchmark suite — baseline metrics (2× measurement)

Agent `aws/gpt-oss-120b` · optimizer Claude Code `claude-opus-4-8` · 1 iteration · baselines frozen & reused (baseline agent never re-run in CI). Measured twice on skillberry-1 (self-hosted, IBM VPC). All tasks are **hard** (baseline reward 0; no natural 0→1 flip exists at this budget — see README). Latency is wall-time and host-dependent; cost/tokens are host-independent (tau2/skillsbench runners report 0).

| bench | task | reward base→opt | latency base (s) | latency opt r1/r2 (s) | runner cost base→opt | optimizer $ r1/r2 |
|---|---|:--:|---|---|---|---|
| skillsbench | `exceltable-in-ppt` | 0.00→0.00/0.00 | 433.48 | 194.18/161.57 | $0.0000→$0.0000 | $0.0000/$0.0000 |
| skillsbench | `offer-letter-generator` | 0.00→1.00/0.00 | 157.97 | 125.48/126.12 | $0.0000→$0.0000 | $0.0000/$0.0000 |
| swebench | `pallets__flask-4992` | 0.00→0.00/0.00 | 138.18 | 109.46/104.89 | $0.0004→$0.0007 | $0.0000/$0.0000 |
| swebench | `scikit-learn__scikit-learn-10297` | 0.00→0.00/0.00 | 157.56 | 95.06/93.26 | $0.0005→$0.0007 | $0.0000/$0.0000 |
| tau2 | `35` | 0.00→0.00/0.00 | 110.98 | 3.37/18.60 | $0.0000→$0.0000 | $0.0000/$0.0000 |
| tau2 | `37` | 0.00→0.00/0.00 | 34.65 | 26.13/2.44 | $0.0000→$0.0000 | $0.0000/$0.0000 |

`reward base→opt` = frozen baseline reward → optimized test reward (run1/run2). A stable `0→0/0` is the expected hard-task signal; the CI gates on non-regression.
