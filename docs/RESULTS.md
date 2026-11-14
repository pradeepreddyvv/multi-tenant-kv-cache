# Historical feasibility evidence

Measurements below came from the original November 10, 2026 Sol runs, before this repository cleanup. Raw evidence remains in the team's preserved research archive. These are component tests, not final research benchmarks.

| Diagnostic | Measured outcome |
|---|---|
| Occupied-cache scale | 600 unique 4096-token prompts; 127.99609375 GiB retained KV; about 145.19 GiB job memory high-water under a 192 GiB limit |
| Retention under pressure | Oldest two probes missed; newest two retrieved 4096 tokens each; 270 allocator-full warnings preserved |
| Tagged tenant identity | 16 first requests missed and 16 repeats retrieved 768 tokens; two fresh-process runs reproduced the identity behavior |
| cache_salt alone | One initial miss followed by cross-identity external hits on the legacy connector |
| Manual primary quota | 184 requests; A retained 42 MiB, then zero, then 126 MiB; B/C/D each retained 42 MiB |
| Quota correctness | All 15 A requests wholly inside the settled low-quota interval missed; both changes overlapped inference batches; no hook errors |

The quota run's request count is time-bounded and may differ on a rerun. A zero-quota tenant losing its data establishes control correctness; it does not establish that adaptive allocation improves latency or fairness.

CPU-only feasibility was also investigated separately but is outside this Option 1 starter repository. Do not treat this repository as a CPU-only runner.
