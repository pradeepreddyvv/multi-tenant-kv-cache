import sys
import threading
import time
import unittest
from collections import OrderedDict
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from tenant_quota import TenantQuotaAdapter

class Key:
    def __init__(self, tenant): self.tags = [('tenant', tenant)]

class Object:
    def __init__(self, size, pinned=False):
        self.size, self.can_evict = size, not pinned
    def get_size(self): return self.size

class Backend:
    def __init__(self):
        self.cpu_lock = threading.RLock()
        self.hot_cache = OrderedDict()
        self.cache_policy = Mock()
        self.fail_remove = False
    def add(self, tenant, size, pinned=False):
        key = Key(tenant)
        self.hot_cache[key] = Object(size, pinned)
        return key
    def remove(self, key, force=False):
        assert force is False
        if self.fail_remove: return False
        del self.hot_cache[key]
        return True

class QuotaTests(unittest.TestCase):
    def setUp(self):
        self.b = Backend()
        self.q = TenantQuotaAdapter(self.b, {'A': 20, 'B': 20}, 60, history_size=3)
    def test_shared_mode_observes_without_quota_eviction(self):
        q = TenantQuotaAdapter(self.b, {'A': 20, 'B': 20}, 60, enforce=False)
        self.b.add('A', 40)
        snapshot = q.sweep()
        self.assertEqual(snapshot['retained_bytes']['A'], 40)
        self.assertEqual(snapshot['evicted_bytes_quota']['A'], 0)
        self.b.cache_policy.update_on_force_evict.assert_not_called()

    def test_shrink_grow_and_peer(self):
        self.b.add('A', 10); self.b.add('A', 10); self.b.add('B', 20)
        ack = self.q.update({'A': 0, 'B': 20})
        s = self.q.sweep()
        self.assertEqual(ack['status'], 'accepted')
        self.assertEqual(s['retained_bytes'], {'A': 0, 'B': 20})
        self.assertEqual(s['evicted_bytes_quota'], {'A': 20, 'B': 0})
        self.q.update({'A': 30, 'B': 20})
        self.b.add('A', 30)
        self.assertEqual(self.q.sweep()['status'], 'compliant')
    def test_pinned_object_defers_then_evicts(self):
        key = self.b.add('A', 30, pinned=True)
        self.assertEqual(self.q.sweep()['status'], 'deferred')
        self.b.hot_cache[key].can_evict = True
        self.assertEqual(self.q.sweep()['retained_bytes']['A'], 0)
    def test_failed_remove_does_not_claim_eviction(self):
        self.b.add('A', 30); self.b.fail_remove = True
        s = self.q.sweep()
        self.assertEqual(s['excess_bytes']['A'], 10)
        self.assertEqual(s['evicted_bytes_quota']['A'], 0)
        self.b.cache_policy.update_on_force_evict.assert_not_called()
    def test_invalid_updates_are_atomic(self):
        for limits in ({'A': -1, 'B': 20}, {'A': True, 'B': 20}, {'A': 41, 'B': 20}, {'A': 0}, {'A': 1.5, 'B': 20}):
            with self.assertRaises(ValueError): self.q.update(limits)
            self.assertEqual(self.q.snapshot()['quota_bytes'], {'A': 20, 'B': 20})
            self.assertEqual(self.q.snapshot()['update_id'], 0)
    def test_unknown_tenant_reported_not_removed(self):
        self.b.add('unknown', 10)
        s = self.q.sweep()
        self.assertEqual(s['unmanaged_bytes'], {'unknown': 10})
        self.assertEqual(s['status'], 'deferred')
    def test_history_bounded_and_returned_data_isolated(self):
        for _ in range(10): self.q.sweep()
        s = self.q.snapshot()
        self.assertEqual(len(s['history']), 3)
        s['quota_bytes']['A'] = -1
        self.assertEqual(self.q.snapshot()['quota_bytes']['A'], 20)
    def test_lifecycle(self):
        self.q.start()
        with self.assertRaises(RuntimeError): self.q.start()
        s = self.q.stop()
        self.assertFalse(s['running']); self.assertTrue(s['closed'])
        self.assertIsNone(s['error'])
        self.q.stop()
        with self.assertRaises(RuntimeError): self.q.update({'A': 1, 'B': 1})
    def test_worker_error_visible(self):
        self.b.add('A', 30)
        self.b.remove = Mock(side_effect=RuntimeError('backend failure'))
        self.q.start()
        deadline = time.monotonic() + 2
        while self.q.snapshot()['error'] is None and time.monotonic() < deadline:
            time.sleep(.01)
        self.assertIn('backend failure', self.q.stop()['error'])
    def test_policy_error_acknowledgement(self):
        self.assertEqual(self.q.apply_quotas({'A': -1, 'B': 20})['status'], 'error')
        self.assertEqual(self.q.snapshot()['update_id'], 0)

    def test_bad_configuration(self):
        for interval in (0, -1, float('nan'), float('inf'), True):
            with self.assertRaises(ValueError): TenantQuotaAdapter(self.b, {'A': 1}, 2, interval_s=interval)

if __name__ == '__main__': unittest.main()
