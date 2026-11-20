"""Figure-data extraction checks. All fixtures below are SYNTHETIC, not measurements."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import plot_historical_evidence as plot

MIB = 2 ** 20


def scale_fixture():
    rows = [{'label': 'before_population', 'elapsed_seconds': 0, 'chunks': 0, 'tensor_bytes': 0}]
    for n in (100, 200):
        rows.append({'label': 'after_%d' % n, 'elapsed_seconds': n, 'chunks': n,
                     'tensor_bytes': n * 14 * MIB})
    rows.append({'label': 'after_retention_probes', 'elapsed_seconds': 201, 'chunks': 200,
                 'tensor_bytes': 200 * 14 * MIB})
    return {'job': 'synthetic', 'occupancy': rows, 'completed': {'cache_capacity_GiB': 8},
            'cache_full_warning_count': 0, 'max_sampled_cgroup_highwater_GiB': 1.0}


def timeline_fixture(peer_c=42 * MIB):
    def sample(t, a, limit_a):
        return {'time': t, 'bytes': {'A': a, 'B': 42 * MIB, 'C': peer_c, 'D': 42 * MIB},
                'limits': {'A': limit_a, 'B': 42 * MIB, 'C': 42 * MIB, 'D': 42 * MIB}}
    return [{'started_at': 100.0, 'errors': [], 'evicted_chunks': {'A': 3},
             'events': [{'tenant': 'A', 'limit_bytes': 0, 'applied_at': 101.0},
                        {'tenant': 'A', 'limit_bytes': 126 * MIB, 'applied_at': 103.0}],
             'samples': [sample(100.0, 42 * MIB, 42 * MIB), sample(101.5, 0, 0),
                         sample(102.5, 0, 0), sample(104.0, 126 * MIB, 126 * MIB)]}]


def tenant_fixture(salt_first_misses=1):
    def group(mode, rep, miss, hit):
        return {'mode': mode, 'repetition': rep, 'requests': 16, 'lookup_misses': miss,
                'actual_retrieves_768': hit}
    return {'groups': [group('cache_salt', 0, salt_first_misses, 16 - salt_first_misses),
                       group('cache_salt', 1, 0, 16), group('lmcache_tag', 0, 16, 0),
                       group('lmcache_tag', 1, 0, 16)]}


class ExtractionTests(unittest.TestCase):
    def test_scale_points_skip_probe_snapshot_and_convert_to_gib(self):
        points = plot.scale_points(scale_fixture())
        self.assertEqual([n for n, _ in points], [0, 100, 200])
        self.assertAlmostEqual(points[-1][1], 200 * 14 / 1024)

    def test_quota_series_relative_time_and_mib(self):
        rows, events = plot.quota_series(timeline_fixture())
        self.assertEqual([r['seconds'] for r in rows], [0.0, 1.5, 2.5, 4.0])
        self.assertEqual([r['a_MiB'] for r in rows], [42, 0, 0, 126])
        self.assertEqual([e['seconds'] for e in events], [1.0, 3.0])

    def test_quota_series_refuses_to_merge_differing_peers(self):
        with self.assertRaises(ValueError):
            plot.quota_series(timeline_fixture(peer_c=0))

    def test_overlap_spans_mark_where_a_equals_peers(self):
        rows, _ = plot.quota_series(timeline_fixture())
        # A equals the peers (42 MiB) only from the first sample to the second.
        self.assertEqual(plot.overlap_spans(rows), [(0.0, 1.5, 42.0)])

    def test_tenant_runs_must_agree(self):
        self.assertEqual(plot.tenant_outcomes(tenant_fixture(), tenant_fixture())[0]['misses'], 1)
        with self.assertRaises(ValueError):
            plot.tenant_outcomes(tenant_fixture(1), tenant_fixture(2))


class CommandTests(unittest.TestCase):
    def test_writes_parseable_svgs_without_touching_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            evidence, out = Path(tmp) / 'evidence', Path(tmp) / 'out'
            evidence.mkdir()
            files = {'gpu-scale-occupancy.json': scale_fixture(),
                     'gpu-primary-quota-timeline.json': timeline_fixture(),
                     'gpu-primary-quota-analysis.json': {'requests': 8, 'low_quota_A_requests': 1,
                                                         'low_quota_A_lookup_misses': 1},
                     'gpu-tenants-first-summary.json': tenant_fixture(),
                     'gpu-tenants-repeat-summary.json': tenant_fixture()}
            for name, value in files.items():
                (evidence / name).write_text(json.dumps(value))
            before = {p.name: p.read_bytes() for p in evidence.iterdir()}
            subprocess.check_output([sys.executable, str(SCRIPTS / 'plot_historical_evidence.py'),
                                     str(evidence), str(out)])
            self.assertEqual(before, {p.name: p.read_bytes() for p in evidence.iterdir()})
            svgs = sorted(out.glob('*.svg'))
            self.assertEqual(len(svgs), 3)
            for svg in svgs:
                ET.parse(str(svg))  # well-formed XML
            self.assertIn('fig-scale-retained.svg', json.loads((out / 'figure-data.json').read_text()))

    def test_refuses_to_write_into_evidence_dir_or_below_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            for out in (tmp, str(Path(tmp) / 'figures')):
                result = subprocess.run([sys.executable, str(SCRIPTS / 'plot_historical_evidence.py'),
                                         tmp, out], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                self.assertNotEqual(result.returncode, 0)
            self.assertFalse((Path(tmp) / 'figures').exists())


if __name__ == '__main__':
    unittest.main()
