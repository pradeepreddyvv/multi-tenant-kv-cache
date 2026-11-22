"""Soft retention quotas for the pinned LMCache LocalCPUBackend.

This is an eviction adapter, not admission control. Cache writes can temporarily
exceed a quota between sweeps; pinned objects are never forcibly removed.
"""
import copy
import math
import threading
import time
from collections import deque

from cache_occupancy_probe import CacheProbeExtension


class TenantQuotaAdapter:
    def __init__(self, backend, limits, budget_bytes, interval_s=0.1, history_size=600, enforce=True):
        if type(budget_bytes) is not int or budget_bytes <= 0:
            raise ValueError('budget_bytes must be a positive integer')
        if not isinstance(interval_s, (int, float)) or isinstance(interval_s, bool) or not math.isfinite(interval_s) or interval_s <= 0:
            raise ValueError('interval_s must be finite and positive')
        if type(history_size) is not int or history_size < 1:
            raise ValueError('history_size must be a positive integer')
        self.enforce = enforce
        self.backend = backend
        self.budget_bytes = budget_bytes
        self.interval_s = interval_s
        self._validate(limits)
        self.limits = dict(limits)
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None
        self._closed = False
        self._error = None
        self._update_id = 0
        self._applied_at = time.time()
        self._evicted = {t: 0 for t in limits}
        self._history = deque(maxlen=history_size)
        self._latest = None

    def _validate(self, limits):
        if not isinstance(limits, dict) or not limits:
            raise ValueError('limits must be a nonempty tenant-to-byte mapping')
        if any(not isinstance(t, str) or not t.strip() for t in limits):
            raise ValueError('tenant IDs must be nonempty strings')
        if any(type(v) is not int or v < 0 for v in limits.values()):
            raise ValueError('quotas must be nonnegative integer bytes')
        if sum(limits.values()) > self.budget_bytes:
            raise ValueError('quota sum exceeds budget')
        if hasattr(self, 'limits') and set(limits) != set(self.limits):
            raise ValueError('updates must include exactly the registered tenants')

    def update(self, limits):
        """Atomically accept a full allocation. Compliance is observed separately."""
        with self._lock:
            if self._closed or self._error:
                raise RuntimeError('adapter stopped or failed')
            self._validate(limits)
            self.limits = dict(limits)
            self._update_id += 1
            self._applied_at = time.time()
            return {'status': 'accepted', 'update_id': self._update_id,
                    'applied_at_s': self._applied_at, 'quota_bytes': dict(self.limits)}

    @staticmethod
    def _tenant(key):
        return dict(key.tags or ()).get('tenant', '<untagged>')

    def apply_quotas(self, limits):
        """Policy-facing acknowledgement; invalid allocations leave state intact."""
        try:
            return self.update(limits)
        except (ValueError, RuntimeError) as exc:
            return {'status': 'error', 'error': str(exc)}

    def sweep(self):
        with self._lock:
            if self._closed or self._error:
                raise RuntimeError('adapter stopped or failed')
            with self.backend.cpu_lock:
                retained = {t: 0 for t in self.limits}
                for key, obj in self.backend.hot_cache.items():
                    t = self._tenant(key)
                    retained[t] = retained.get(t, 0) + obj.get_size()
                for key, obj in list(self.backend.hot_cache.items()):
                    t = self._tenant(key)
                    if not self.enforce or t not in self.limits or retained[t] <= self.limits[t] or not obj.can_evict:
                        continue
                    size = obj.get_size()
                    if self.backend.remove(key, force=False):
                        self.backend.cache_policy.update_on_force_evict(key)
                        retained[t] -= size
                        self._evicted[t] += size
            excess = {t: max(0, retained[t] - q) for t, q in self.limits.items()}
            unmanaged = {t: b for t, b in retained.items() if t not in self.limits}
            self._latest = {
                'observed_at_s': time.time(), 'update_id': self._update_id,
                'applied_at_s': self._applied_at, 'quota_bytes': dict(self.limits),
                'retained_bytes': retained, 'excess_bytes': excess,
                'unmanaged_bytes': unmanaged, 'evicted_bytes_quota': dict(self._evicted),
                'status': 'deferred' if any(excess.values()) or any(unmanaged.values()) else 'compliant',
            }
            self._history.append(copy.deepcopy(self._latest))
            return copy.deepcopy(self._latest)

    def start(self):
        with self._lock:
            if self._closed or self._error or self._thread is not None:
                raise RuntimeError('adapter cannot be started twice; create a new adapter')
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return {'status': 'started', 'update_id': self._update_id}

    def _run(self):
        try:
            while not self._stop.is_set():
                self.sweep()
                self._stop.wait(self.interval_s)
        except Exception as exc:
            with self._lock:
                self._error = repr(exc)
            self._stop.set()

    def snapshot(self):
        with self._lock:
            return copy.deepcopy({'running': self._thread is not None and self._thread.is_alive(),
                'closed': self._closed, 'error': self._error, 'update_id': self._update_id,
                'quota_bytes': self.limits, 'latest': self._latest, 'history': list(self._history)})

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=3)
            if self._thread.is_alive():
                raise RuntimeError('quota thread did not stop within three seconds')
        with self._lock:
            self._closed = True
        return self.snapshot()


class TenantQuotaExtension(CacheProbeExtension):
    def dis_ml_quota_start(self, config):
        from lmcache.v1.cache_engine import LMCacheEngineBuilder
        previous = getattr(self, '_tenant_quota', None)
        if previous is not None and not previous.snapshot()['closed']:
            raise RuntimeError('stop the existing adapter before restarting')
        engines = list(LMCacheEngineBuilder._instances.values())
        if len(engines) != 1:
            raise RuntimeError('expected one isolated LMCache engine')
        backend = engines[0].storage_manager.storage_backends['LocalCPUBackend']
        self._tenant_quota = TenantQuotaAdapter(backend, **config)
        return self._tenant_quota.start()

    def dis_ml_quota_update(self, limits):
        return self._tenant_quota.apply_quotas(limits)

    def dis_ml_quota_snapshot(self):
        return self._tenant_quota.snapshot()

    def dis_ml_quota_stop(self):
        return self._tenant_quota.stop()
