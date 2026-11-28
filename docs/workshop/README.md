# Held-out cache policy results
Prepared by Akshith Reddy Ganta for Team 11, November 30 workshop.
Seeds 811, 823, and 839 contributed 637, 650, and 605 successful requests per policy, including warmup. TTFT is time from submission to first token. Reuse is retrieved tokens divided by eligible prefix tokens.

## Three held-out traces put all policies under pressure

- **Design.** Equal quotas, cautious adaptive (v3), and shared cache each replayed the same trace within a seed.
- **System.** Qwen2.5-32B-Instruct on an A100 80 GB GPU, with a 128 GiB CPU KV cache and four tenants.
- **Workload.** 64 reusable prefixes per tenant, 4,096 tokens per prefix. Demand shifted from A to B at 900 seconds.
- **Measurement.** After a 600-second warmup, we measured 300 seconds on either side of the shift. All nine runs reached 128 GiB.

## Equal quotas beat v3 after the shift on all three traces

| Seed | Phase | Equal | Adaptive v3 | Shared |
|---|---|---:|---:|---:|
| 811 | before shift | 1240 | 1196 | 1156 |
| 823 | before shift | 1267 | 1149 | 793 |
| 839 | before shift | 1243 | 1154 | 1153 |
| 811 | after shift | 892 | 1159 | 1159 |
| 823 | after shift | 1275 | 1277 | 1270 |
| 839 | after shift | 1154 | 1159 | 1155 |

## The new busiest tenant waited for its quota to grow

- **Tenant B.** Compared with equal quotas, B received its first token 6 ms sooner on seed 811 and 36 ms and 33 ms later on seeds 823 and 839.
- **Timing.** B’s quota first exceeded A’s 264, 177, and 235 seconds into the 300-second post-shift window.
- **Tenant D.** Under v3, D waited an extra 970, 448, and 682 ms at the median after the shift, respectively.
- **Interpretation.** V3 reduced quota-driven evicted bytes by 11–17% on every seed. Lower eviction volume alone did not predict shorter waits.

## What the experiment establishes

- **Before the shift.** V3 improved overall median latency and cache reuse over equal quotas on all three seeds. Shared cache had the lowest pre-shift median on all three.
- **After the shift.** Equal quotas had higher reuse and lower median latency than v3 on each trace. The largest median difference was 267 ms on seed 811.
- **Correctness boundary.** Seven selected prompts matched in sequential tests, including forced eviction and refill. Concurrent warm-cache runs sometimes produced different tokens.
- **Next experiment.** Test whether a faster response to a shift helps B without slowing other tenants. Evaluate output consistency separately before making serving-quality claims.

See pressure-results.csv for all phase and tenant measurements. Per-tenant p95 is withheld below 100 requests. Raw evidence stays outside Git.
