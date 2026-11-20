"""Planned-evaluation summarizer. Every run below is a SYNTHETIC fixture, not a measurement."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import summarize_evaluation_run as summ


def fixture(policy='equal', ttft=0.5, hot_ttft=None, n_per_tenant=10, budget=1000, quotas=None,
            rate=None, trace='synthetic-trace'):
    """Two tenants, warm-up 0-10 s, measured 10-30 s, requests evenly spaced."""
    tenants = ['t0', 't1']
    requests, rid = [], 0
    for tenant in tenants:
        for i in range(n_per_tenant):
            submitted = 10 + 20.0 * i / n_per_tenant
            first = ttft if tenant == 't1' or hot_ttft is None else hot_ttft
            requests.append({'request_id': str(rid), 'tenant': tenant, 'submitted_at_s': submitted,
                             'first_token_at_s': submitted + first, 'finished_at_s': submitted + first + 3.1,
                             'prompt_tokens': 4160, 'output_tokens': 32, 'status': 'ok'})
            rid += 1
    requests.append({'request_id': 'warm', 'tenant': 't0', 'submitted_at_s': 2.0, 'first_token_at_s': 9.0,
                     'finished_at_s': 9.5, 'prompt_tokens': 4160, 'output_tokens': 32, 'status': 'ok'})
    return {'manifest': {'run_id': 'synthetic-%s' % policy, 'policy': policy, 'seed': 11,
                         'trace_sha256': trace, 'tenants': tenants, 'budget_bytes': budget,
                         'warmup_end_s': 10, 'measured_end_s': 30, 'shift_at_s': None,
                         'target_rate_rps': rate if rate is not None else 2 * n_per_tenant / 20.0},
            'requests': requests,
            'observations': [{'tenant_id': t, 'window_end_s': 15.0, 'eligible_input_tokens': 4096,
                              'retained_bytes': 0, 'retrieved_tokens': 0, 'errors': 0} for t in tenants],
            'quota_updates': [{'update_id': 'u1', 'applied_at_s': 10.0, 'status': 'accepted',
                               'quotas': quotas or {'t0': 500, 't1': 500}}]}


class StatsTests(unittest.TestCase):
    def test_percentile_type7(self):
        self.assertEqual(summ.percentile([1, 2, 3, 4], 0.5), 2.5)
        self.assertAlmostEqual(summ.percentile(list(range(1, 101)), 0.95), 95.05)
        self.assertIsNone(summ.percentile([], 0.5))

    def test_warmup_excluded_and_phases_split(self):
        report = summ.summarize(fixture())
        t0 = report['per_tenant']['t0']
        self.assertEqual(t0['measured']['submitted'], 10)  # warm-up request excluded
        self.assertEqual(t0['phase1']['submitted'] + t0['phase2']['submitted'], 10)
        self.assertAlmostEqual(t0['measured']['median_ttft_s'], 0.5)
        self.assertAlmostEqual(t0['measured']['median_tpot_s'], 0.1)  # 3.1 s / 31 tokens
        self.assertEqual(report['automatic_gates'], 'passed')

    def test_p95_withheld_below_100_samples(self):
        small = summ.summarize(fixture())['per_tenant']['t0']['measured']
        self.assertIsNone(small['p95_ttft_s'])
        self.assertIn('insufficient', small['p95_note'])
        large = summ.summarize(fixture(n_per_tenant=100))['per_tenant']['t0']['measured']
        self.assertIsNotNone(large['p95_ttft_s'])

    def test_failed_requests_counted_not_timed(self):
        data = fixture()
        data['requests'][0].update(status='timeout', first_token_at_s=None)
        stats = summ.summarize(data)['per_tenant']['t0']['measured']
        self.assertEqual((stats['completed'], stats['failed']), (9, 1))


class GateTests(unittest.TestCase):
    def test_quota_sum_over_budget_needs_review(self):
        report = summ.summarize(fixture(quotas={'t0': 700, 't1': 700}))
        self.assertEqual(report['automatic_gates'], 'Needs review')

    def test_realized_rate_outside_tolerance_needs_review(self):
        self.assertEqual(summ.summarize(fixture(rate=5.0))['automatic_gates'], 'Needs review')

    def test_non_integer_observation_needs_review(self):
        data = fixture()
        data['observations'][0]['retained_bytes'] = 1.5
        self.assertEqual(summ.summarize(data)['automatic_gates'], 'Needs review')


class HarmTests(unittest.TestCase):
    def test_harm_ratio_is_worst_tenant_ratio(self):
        equal = summ.summarize(fixture())
        adaptive = summ.summarize(fixture(policy='adaptive', hot_ttft=0.25, ttft=0.75))
        harm = summ.harm_ratio(adaptive, equal)['measured']
        self.assertEqual(harm['worst_tenant'], 't1')
        self.assertAlmostEqual(harm['harm_ratio'], 1.5)

    def test_harm_ratio_refuses_different_traces(self):
        with self.assertRaises(ValueError):
            summ.harm_ratio(summ.summarize(fixture(trace='a')), summ.summarize(fixture(trace='b')))


class CommandTests(unittest.TestCase):
    def write(self, root, name, data):
        run = Path(root) / name
        run.mkdir()
        (run / 'manifest.json').write_text(json.dumps(data['manifest']))
        for key in ('requests', 'observations', 'quota_updates'):
            (run / (key + '.jsonl')).write_text(''.join(json.dumps(r) + '\n' for r in data[key]))
        return run

    def test_cli_with_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            equal = self.write(tmp, 'equal', fixture())
            adaptive = self.write(tmp, 'adaptive', fixture(policy='adaptive', hot_ttft=0.25, ttft=0.75))
            out = subprocess.run([sys.executable, str(SCRIPTS / 'summarize_evaluation_run.py'), str(adaptive),
                                  '--baseline', str(equal)], stdout=subprocess.PIPE, universal_newlines=True)
            self.assertEqual(out.returncode, 0)
            self.assertAlmostEqual(json.loads(out.stdout)['versus_equal']['measured']['harm_ratio'], 1.5)


if __name__ == '__main__':
    unittest.main()
