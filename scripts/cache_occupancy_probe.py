"""Read-only diagnostic for the pinned LMCache 0.4.4 GPU image.

This uses internal fields, so it is diagnostic instrumentation, not a stable
management API. Invoke with vLLM collective_rpc after a completed batch.
"""


def cpu_cache_snapshot(worker):
    from lmcache.v1.cache_engine import LMCacheEngineBuilder

    engines = []
    for name, engine in LMCacheEngineBuilder._instances.items():
        backend = engine.storage_manager.storage_backends.get('LocalCPUBackend')
        if backend is None:
            continue
        totals = {}
        with backend.cpu_lock:
            for key, value in backend.hot_cache.items():
                tags = dict(key.tags or ())
                tenant = tags.get('tenant', '<untagged>')
                row = totals.setdefault(tenant, {'chunks': 0, 'tensor_bytes': 0,
                                                  'physical_bytes': 0})
                row['chunks'] += 1
                row['tensor_bytes'] += value.get_size()
                row['physical_bytes'] += value.get_physical_size()
        engines.append({'engine': name, 'tenants': totals})
    if not engines:
        raise RuntimeError('No worker-local LMCache CPU backend found')
    return engines


class CacheProbeExtension:
    """Named worker method avoids shipping a pickled callable through RPC."""

    def dis_ml_cpu_cache_snapshot(self):
        return cpu_cache_snapshot(self)
