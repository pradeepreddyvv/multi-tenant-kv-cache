# Interpretation boundaries

- Scale, tenant separation and quota control were separate tests. No combined 128 GiB / 16-tenant / dynamic-quota claim is supported.
- The quota hook is a custom bounded diagnostic: four tenants, a 30-second maximum enforcer lifetime and 100 ms enforcement cadence. It is not stock LMCache quota support or an adaptive controller.
- The tested legacy GPU connector did not isolate external entries with cache_salt alone. Explicit LMCache tenant tags did. This observation is version/connector-specific and is not a general security guarantee.
- Requests are offline vLLM engine calls. Tenant count is not concurrency. The tenant probe is sequential; the quota workload batches four requests. No streaming TTFT or two-second SLO was measured here.
- Log parsing expects the tested logger's request-ID format and 768-token hits. Missing/incompatible logs are not evidence of success. Inspect raw logs with derived outputs.
- Configured capacity, cumulative store traffic and retained bytes differ. Only the locked cache-object snapshots establish retained payload. Job cgroup memory includes additional overhead.
- The scale run reported allocator-full warnings at pressure. These were recorded even though retention and serving completed.
- The GPU image emitted a nonfatal Prometheus metadata warning. Conclusions used request-matched logs and locked byte counts; label attribution needs repair before a final benchmark.
- The resource monitor currently targets cgroup v1 on Linux. A different cgroup layout must not silently be treated as a valid memory measurement.
- Workloads are diagnostic synthetic prompts/token sequences, not a representative application benchmark. Output consistency is not a quality or accuracy claim.
- The cleaned wrapper/model-revision changes have been checked locally; no new GPU end-to-end run was performed while preparing this repository.

Outstanding research includes general sustained enforcement, adaptive policy design, fair baselines, traffic shifts, repeated measurements, controller overhead, and larger-memory/multi-node tests.
