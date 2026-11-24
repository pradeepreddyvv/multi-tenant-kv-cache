# Research questions in the current presentation

| Question | Evidence-supported answer | Slides |
|---|---|---|
| Can we keep a large cache while serving requests? | Yes in the tested setup: measured peak 128 GiB retained KV, 614 validated requests. | 7 |
| Does changing cache shares shorten the wait? | Not consistently. Original adaptive lost across three seeds. Cautious adaptive improved median TTFT 19.9% in one newer seed but worsened p95. | 8–11 |
| Can overall gains hide slower applications? | Yes. In the newer run, application C’s median TTFT increased about 3.3% despite the aggregate median improvement. | 11 |

Explain each as question → controlled experiment → observation → interpretation → limitation. Occupancy and eviction patterns support a churn hypothesis; they do not isolate causality. Candidate improvements need held-out replication.

The baseline is equal fixed CPU-cache shares, 32 GiB each for four tenants. Fixed priority and unpartitioned shared caching are additional references. Our algorithms run on reused vLLM/LMCache infrastructure; they are not reproductions of all cited papers.

For beginners, prioritize understanding cache hits/misses, prefill versus decode, tenant quotas, eviction/refill costs, TTFT, p95 and per-tenant tradeoffs. A narrower mechanism study that the team can explain is preferable to an unsupported claim of a full FairCache improvement. For an untested configuration, say so explicitly rather than extrapolate.
