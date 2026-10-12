# h4 T1 vs G2: all arms, all clean trials

e1, e2 = George's Oct-04 suite drop. e3 = Oct-06 drop (all five services seeded).
Trials lost to harness errors or to an agent that did not finish are excluded from
every arm; `⚠n/5` marks a task short of five clean trials.

**g2_e3** (added 2026-10-11) is the first G2 (global, shared-bundle) arm run against
the h4 held-out set — optimizer candidate `cand_0006` from `v4_g_e1`
(`artifacts/v4/v4_g_e1/rejected/cand_0006` — highest raw val reward of any candidate
in that run, though not the one hill-climb's gate accepted), same Oct-06 drop as e3,
run via `scripts/parsec/h4/` on CCC (one task per dedicated node, five concurrent).
This resolves two items from [`handoff-t1-vs-g2.md`](handoff-t1-vs-g2.md)'s Open
Questions: G2 is now audited for every §1 failure mode (0 dead trials across 150;
`audit_absence_traps.py` found exactly one hit, noted below), and all 30 tasks are
covered, including icinga (`h4_g2_e1`'s own gap).

| task | George | e1 | e2 | e3 | **g2_e3** |
|---|--:|---|---|---|---|
| 061-capacity-manager-unused-cost-owner-lookup | 0.650 | **0.416** `[0.39 0.39 0.52 0.39 0.39]` | **0.555** `[0.69 0.52 0.52 0.52 0.52]` | **0.546** `[0.65 0.52 0.39 0.52 0.65]` | **0.572** `[0.52 0.52 0.65 0.52 0.65]` |
| 062-provisioning-job-trace | 0.650 | **0.790** `[1.00 0.65 0.65 1.00 0.65]` | **0.720** `[0.65 1.00 0.65 0.65 0.65]` | **0.607** `[0.43 0.65 0.65 0.65 0.65]` | **0.508** `[1.00 0.33 0.43 0.39 0.39]` |
| 063-babylon-namespace-missing-for-account | 0.300 | **0.300** `[0.30 0.30 0.30 0.30 0.30]` | **0.300** `[0.30 0.30 0.30 0.30 0.30]` | **0.300** `[0.15 0.30 0.30 0.30 0.45]` | **0.300** `[0.30 0.30 0.30 0.30 0.30]` |
| 064-reservation-release-active-job-check | 0.325 | **0.455** `[0.43 0.54 0.43 0.54 0.33]` | **0.433** `[0.43 0.43 0.43 0.43 0.43]` | **0.413** `[0.43 0.33 0.33 0.43 0.54]` | **0.413** `[0.54 0.43 0.33 0.43 0.33]` |
| cloud-055-azure-subscription-not-found | 1.000 | **1.000** `[1.00 1.00 1.00 1.00 1.00]` | **1.000** `[1.00 1.00 1.00 1.00 1.00]` | **0.720** `[0.65 0.65 0.65 0.65 1.00]` | **1.000** `[1.00 1.00 1.00 1.00 1.00]` |
| cloud-056-gcp-delete-in-progress-not-requested | 0.767 | **0.767** `[0.77 0.77 0.77 0.77 0.77]` | **0.767** `[0.77 0.77 0.77 0.77 0.77]` | **0.767** `[0.77 0.77 0.77 0.77 0.77]` | **0.673** `[0.77 0.53 0.77 0.77 0.53]` |
| cloud-057-cloudtrail-select-only-refusal | 0.467 | **0.420** `[0.47 0.47 0.47 0.23 0.47]` | **0.467** `[0.47 0.47 0.47 0.47 0.47]` | **0.467** `[0.47 0.47 0.47 0.47 0.47]` | **0.420** `[0.47 0.23 0.47 0.47 0.47]` |
| cloud-058-malformed-account-id | 0.700 | **0.700** `[0.70 0.70 0.70 0.70 0.70]` | **0.607** `[0.47 0.70 0.47 0.70 0.70]` | **0.700** `[0.70 0.70 0.70 0.70 0.70]` | **0.700** `[0.70 0.70 0.70 0.70 0.70]` |
| cloud-059-blank-owner-email-fallback | 0.700 | **0.670** `[0.82 0.35 0.53 0.82 0.82]` | **0.635** `[0.35 0.82 0.82 0.35 0.82]` | **0.575** `[0.35 0.35 0.35 0.82 1.00]` | **0.515** `[0.53 0.82 0.35 0.35 0.53]` |
| cloud-060-marketplace-usd-not-enriched | 0.350 | **0.350** `[0.35 0.35 0.35 0.35 0.35]` | **0.315** `[0.35 0.35 0.35 0.17 0.35]` | **0.350** `[0.35 0.35 0.35 0.35 0.35]` | **0.350** `[0.35 0.35 0.35 0.35 0.35]` |
| cost-050-org-wide-aggregate-doubling | 0.825 | **0.615** `[0.47 0.65 0.47 0.82 0.65]` | **0.545** `[0.47 0.47 0.47 0.65 0.65]` | 0.606 `[0.47 0.65 0.65 0.65]` ⚠4/5 | **0.755** `[0.82 0.82 0.82 0.65 0.65]` ⚑1 |
| cost-051-gcp-net-of-credits | 1.000 | **0.813** `[0.77 1.00 0.77 0.77 0.77]` | **0.753** `[0.77 0.47 0.77 0.77 1.00]` | **0.767** `[0.77 0.77 0.77 0.77 0.77]` | **0.613** `[0.53 0.23 0.53 0.77 1.00]` |
| cost-052-azure-empty-cache-no-filter | 0.467 | **0.420** `[0.47 0.47 0.47 0.23 0.47]` | **0.467** `[0.47 0.47 0.47 0.47 0.47]` | 0.408 `[0.23 0.47 0.47 0.47]` ⚠4/5 | **0.280** `[0.47 0.47 0.00 0.47 0.00]` |
| cost-053-capacity-dropped-reservations | 1.000 | **0.755** `[0.65 0.82 0.82 0.65 0.82]` | **0.825** `[1.00 0.82 0.65 0.82 0.82]` | **0.825** `[0.82 0.82 0.65 1.00 0.82]` | **0.685** `[0.65 0.65 0.65 0.65 0.82]` |
| cost-054-monitor-no-dashboard-link | 0.700 | **0.513** `[0.47 0.70 0.47 0.47 0.47]` | **0.420** `[0.23 0.47 0.47 0.23 0.70]` | **0.620** `[0.70 0.47 0.70 0.70 0.53]` | **0.153** `[0.00 0.00 0.00 0.00 0.77]` |
| icinga-045-hosts-search-filter | 1.000 | **0.475** `[0.47 0.47 0.47 0.47 0.47]` | **0.475** `[0.47 0.47 0.47 0.47 0.47]` | **1.000** `[1.00 1.00 1.00 1.00 1.00]` | **0.475** `[0.47 0.47 0.47 0.47 0.47]` |
| icinga-046-services-search-cross-host | 0.700 | **0.700** `[0.70 0.70 0.70 0.70 0.70]` | **0.700** `[0.70 0.70 0.70 0.70 0.70]` | **0.583** `[0.70 0.70 0.12 0.70 0.70]` | **0.583** `[0.70 0.70 0.70 0.70 0.12]` |
| icinga-047-downtime-similar-host-names | 1.000 | **0.550** `[0.44 0.62 0.62 0.62 0.44]` | **0.812** `[0.81 0.81 0.81 0.81 0.81]` | **0.550** `[0.62 0.62 0.62 0.44 0.44]` | **0.887** `[0.44 1.00 1.00 1.00 1.00]` |
| icinga-048-comment-service-vs-host-scope | 1.000 | **0.700** `[0.75 0.50 0.75 0.75 0.75]` | **0.650** `[0.75 0.75 0.75 0.50 0.50]` | 0.500 `[0.50 0.50 0.50 0.50]` ⚠4/5 | **1.000** `[1.00 1.00 1.00 1.00 1.00]` |
| icinga-049-downtime-already-expired | 0.850 | **0.617** `[0.62 0.62 0.62 0.62 0.62]` | **0.617** `[0.62 0.62 0.62 0.62 0.62]` | 0.617 `[0.62 0.62 0.62]` ⚠3/5 | **0.617** `[0.62 0.62 0.62 0.62 0.62]` |
| platform-035-aap2-cross-controller-job-search | 1.000 | **1.000** `[1.00 1.00 1.00 1.00 1.00]` | **1.000** `[1.00 1.00 1.00 1.00 1.00]` | **1.000** `[1.00 1.00 1.00 1.00 1.00]` | **0.600** `[0.50 1.00 0.50 0.50 0.50]` |
| platform-036-secret-redacted-not-absent | 1.000 | **0.150** `[0.15 0.15 0.15 0.15 0.15]` | **0.430** `[0.50 0.50 0.50 0.15 0.50]` | **0.320** `[0.15 1.00 0.15 0.15 0.15]` | **0.660** `[0.15 1.00 1.00 1.00 0.15]` |
| platform-037-ocpv-healthy-vm-degraded-machineset | 1.000 | **0.767** `[0.77 0.77 0.77 0.77 0.77]` | **0.813** `[0.77 0.77 0.77 1.00 0.77]` | **0.860** `[1.00 0.77 0.77 1.00 0.77]` | **0.720** `[0.53 0.77 0.77 0.77 0.77]` |
| platform-038-anarchy-subject-guid-cross-cluster | 1.000 | **1.000** `[1.00 1.00 1.00 1.00 1.00]` | **1.000** `[1.00 1.00 1.00 1.00 1.00]` | **1.000** `[1.00 1.00 1.00 1.00 1.00]` | **0.740** `[0.45 1.00 0.25 1.00 1.00]` |
| platform-039-catalog-miss-pr-fallback | 1.000 | **0.650** `[0.65 0.65 0.65 0.65 0.65]` | **0.475** `[0.47 0.47 0.47 0.47 0.47]` | **0.475** `[0.47 0.47 0.47 0.47 0.47]` | **0.860** `[1.00 1.00 0.65 0.65 1.00]` |
| platform-040-workshop-cross-cluster-name-search | 1.000 | **0.965** `[1.00 1.00 1.00 0.82 1.00]` | **0.930** `[1.00 0.82 0.82 1.00 1.00]` | **1.000** `[1.00 1.00 1.00 1.00 1.00]` | **0.235** `[0.17 0.00 0.00 1.00 0.00]` |
| platform-041-resource-pool-unfiltered-list | 1.000 | **1.000** `[1.00 1.00 1.00 1.00 1.00]` | **1.000** `[1.00 1.00 1.00 1.00 1.00]` | **1.000** `[1.00 1.00 1.00 1.00 1.00]` | **0.825** `[0.82 1.00 0.30 1.00 1.00]` |
| platform-042-deployment-via-resource-claim | 1.000 | **0.875** `[0.88 0.88 0.88 0.88 0.88]` | **0.900** `[0.88 0.88 1.00 0.88 0.88]` | **0.875** `[0.88 0.88 0.88 0.88 0.88]` | **0.550** `[0.25 0.88 0.38 1.00 0.25]` |
| platform-043-multiworkshop-asset-failure | 1.000 | 1.000 `[1.00 1.00 1.00 1.00]` ⚠4/5 | 1.000 `[1.00 1.00 1.00 1.00]` ⚠4/5 | **1.000** `[1.00 1.00 1.00 1.00 1.00]` | **0.700** `[1.00 0.25 1.00 1.00 0.25]` |
| platform-044-search-catalog-env-type | 1.000 | **0.965** `[0.82 1.00 1.00 1.00 1.00]` | **1.000** `[1.00 1.00 1.00 1.00 1.00]` | **0.755** `[0.82 0.82 0.30 1.00 0.82]` | **0.615** `[1.00 0.30 0.47 0.30 1.00]` |
| **MEAN (30 tasks)** | **0.8150** | **0.6799** | **0.6870** | **0.6735** | **0.6002** |

⚑1 = one trial on this task lost a `third-account-absent` absence-trap assertion to
simulator fabrication (`audit_absence_traps.py`), same failure class as §1c of the
handoff — the mean is a slight overestimate until re-run.

**g2_e3 reads differently from e1/e2/e3**: it is lower on mean (0.600 vs e3's 0.674),
but the five tasks every other arm scores a stable, deterministic 1.000 on
(`cloud-056`, `platform-035/038/041/043` — the handoff's own control set) are no
longer stable under g2_e3: every one of them is now bimodal or spread, landing on
1.0 some trials and 0.25–0.5 others. See
[`handoff-t1-vs-g2.md`](handoff-t1-vs-g2.md)'s dated addendum for the full reading,
including which deltas look like genuine improvements (`icinga-048`, `platform-039`)
versus the control-task reliability regression.
