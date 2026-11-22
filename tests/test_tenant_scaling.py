import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from live_common import build_trace, tenant_ids, trace_hash, window_observations
from policy.allocation import equal_allocation, fixed_unequal_allocation


class TenantScalingTests(unittest.TestCase):
    def test_all_tenants_appear_with_short_chunk_aligned_prefixes(self):
        for count in (4, 8, 16):
            ids = tenant_ids(count)
            rows = build_trace(11, 120, 10, 60, prefix_tokens=256, pool=2, tenants=ids)
            self.assertEqual(set(ids), {r['tenant'] for r in rows})
            self.assertTrue(all(len(r['prompt']) == 320 for r in rows))
            self.assertEqual(trace_hash(rows), trace_hash(build_trace(
                11, 120, 10, 60, prefix_tokens=256, pool=2, tenants=ids)))
            for quotas in (equal_allocation(ids, 2**30),
                           fixed_unequal_allocation({t: 3 if t == ids[0] else 1 for t in ids}, 2**30)):
                self.assertEqual(sum(quotas.values()), 2**30)
                self.assertEqual(set(quotas), set(ids))

    def test_idle_and_error_windows_preserve_all_identities(self):
        for count in (8, 16):
            ids = tenant_ids(count)
            rows = window_observations([dict(tenant=ids[-1], status='error')], '', {}, 5, tenants=ids)
            self.assertEqual(len(rows), count)
            self.assertEqual(rows[-1]['errors'], 1)
            self.assertTrue(all(r['eligible_input_tokens'] == 0 for r in rows))

    def test_default_trace_remains_four_tenants(self):
        self.assertEqual(trace_hash(build_trace(11, 30, 2, 15)),
                         trace_hash(build_trace(11, 30, 2, 15, tenants=tenant_ids(4))))

    def test_invalid_membership_fails(self):
        with self.assertRaises(ValueError): tenant_ids(5)
        with self.assertRaises(ValueError): build_trace(11, 30, 2, 15, tenants=('A', 'A'))
