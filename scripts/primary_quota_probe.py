"""Bounded, pinned-version feasibility hook; not a production quota manager.

Only runs in the isolated diagnostic worker. Uses existing eviction eligibility,
the backend lock and reference-counted removal. No installed package is edited.
"""
import threading
import time

from cache_occupancy_probe import CacheProbeExtension


class PrimaryQuotaProbeExtension(CacheProbeExtension):
    def dis_ml_start_quota_probe(self, plan):
        from lmcache.v1.cache_engine import LMCacheEngineBuilder

        if hasattr(self, '_dis_ml_quota_thread'):
            raise RuntimeError('Diagnostic already started')
        engines = list(LMCacheEngineBuilder._instances.values())
        if len(engines) != 1:
            raise RuntimeError('Expected one isolated LMCache engine')
        backend = engines[0].storage_manager.storage_backends['LocalCPUBackend']
        state = {'started_at': time.time(), 'limits': dict(plan['initial_limits']),
                 'events': [], 'samples': [], 'evicted_chunks': {}, 'errors': []}
        self._dis_ml_quota_state = state
        self._dis_ml_quota_stop = threading.Event()
        self._dis_ml_quota_lock = threading.Lock()

        def run():
            pending = sorted(plan['changes'], key=lambda c: c['after_seconds'])
            deadline = time.monotonic() + 30
            start = time.monotonic()
            try:
                while not self._dis_ml_quota_stop.is_set() and time.monotonic() < deadline:
                    with self._dis_ml_quota_lock:
                        while pending and time.monotonic() - start >= pending[0]['after_seconds']:
                            event = dict(pending.pop(0), applied_at=time.time())
                            state['limits'][event['tenant']] = event['limit_bytes']
                            state['events'].append(event)
                        with backend.cpu_lock:
                            totals = {}
                            for key, obj in backend.hot_cache.items():
                                tenant = dict(key.tags or ()).get('tenant', '<untagged>')
                                totals[tenant] = totals.get(tenant, 0) + obj.get_size()
                            # OrderedDict iteration follows the installed LRU order.
                            for key, obj in list(backend.hot_cache.items()):
                                tenant = dict(key.tags or ()).get('tenant', '<untagged>')
                                limit = state['limits'].get(tenant)
                                if limit is None or totals[tenant] <= limit or not obj.can_evict:
                                    continue
                                size = obj.get_size()
                                if backend.remove(key, force=False):
                                    backend.cache_policy.update_on_force_evict(key)
                                    totals[tenant] -= size
                                    state['evicted_chunks'][tenant] = state['evicted_chunks'].get(tenant, 0) + 1
                            state['samples'].append({'time': time.time(), 'bytes': totals,
                                                     'limits': dict(state['limits'])})
                    self._dis_ml_quota_stop.wait(0.1)
            except Exception as exc:
                with self._dis_ml_quota_lock:
                    state['errors'].append(repr(exc))

        self._dis_ml_quota_thread = threading.Thread(target=run, daemon=True)
        self._dis_ml_quota_thread.start()
        return {'started_at': state['started_at']}

    def dis_ml_stop_quota_probe(self):
        self._dis_ml_quota_stop.set()
        self._dis_ml_quota_thread.join(timeout=3)
        if self._dis_ml_quota_thread.is_alive():
            raise RuntimeError('Quota probe did not stop')
        with self._dis_ml_quota_lock:
            return self._dis_ml_quota_state
