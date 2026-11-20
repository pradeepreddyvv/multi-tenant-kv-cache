"""Attribution-checker behavior. All logs and records below are SYNTHETIC, not measurements."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import check_request_attribution as check

MIB = 2 ** 20


def lookup(rid, hits, total=906, computed=0):
    return ('LMCache INFO: Reqid: %s-abcd1234, Total tokens %d, Inference Engine computed tokens: %d, '
            'LMCache hit tokens: %d, need to load: %d' % (rid, total, computed, hits, hits))


def retrieve(rid, tokens, size=None):
    size = tokens * 56 * 1024 / 2 ** 30 if size is None else size
    return ('LMCache INFO: [req_id=%s-abcd1234] Retrieved %d out of %d required tokens '
            '(from %d total tokens). size: %.4f gb' % (rid, tokens, tokens, tokens, size))


def record(rid, tenant='t0', prompt=906, text='synthetic'):
    return {'request_id': rid, 'tenant': tenant, 'prompt_tokens': prompt, 'output_tokens': 8, 'text': text}


class ClassifyTests(unittest.TestCase):
    def classify(self, rec, lines):
        lookups, retrieves = check.parse_log('\n'.join(lines))
        return check.classify(rec, lookups, retrieves)

    def test_hit_and_miss(self):
        self.assertEqual(self.classify(record('0'), [lookup('0', 768), retrieve('0', 768)]), ('hit', []))
        self.assertEqual(self.classify(record('0'), [lookup('0', 0)]), ('miss', []))

    def test_missing_evidence_is_never_a_hit(self):
        self.assertEqual(self.classify(record('0'), [])[0], 'unattributed')
        self.assertEqual(self.classify(record('0'), [lookup('0', 768)])[0], 'unattributed')

    def test_nonzero_engine_computed_is_flagged_not_skipped(self):
        outcome, why = self.classify(record('0'), [lookup('0', 0, computed=256)])
        self.assertEqual(outcome, 'unattributed')
        self.assertTrue(any('native cache' in p for p in why))

    def test_join_mismatch_and_impossible_retrieval_flagged(self):
        self.assertEqual(self.classify(record('0'), [lookup('0', 0, total=500)])[0], 'unattributed')
        self.assertEqual(self.classify(record('0'), [lookup('0', 1024), retrieve('0', 1024)])[0],
                         'unattributed')  # 906-token prompt has only 768 eligible tokens
        self.assertEqual(self.classify(record('0'), [lookup('0', 768), retrieve('0', 768, size=0.5)])[0],
                         'unattributed')

    def test_snapshot_bytes_must_be_whole_chunks(self):
        self.assertEqual(check.snapshot_problems('s', {'A': {'chunks': 3, 'tensor_bytes': 42 * MIB}}), [])
        self.assertTrue(check.snapshot_problems('s', {'A': {'chunks': 3, 'tensor_bytes': 40 * MIB}}))


class CommandTests(unittest.TestCase):
    def run_dir(self, tmp, records, lines):
        run = Path(tmp) / 'synthetic-run'
        run.mkdir()
        (run / 'requests.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in records))
        (run / 'run.log').write_text('\n'.join(lines) + '\n')
        return run

    def invoke(self, run):
        return subprocess.run([sys.executable, str(SCRIPTS / 'check_request_attribution.py'), str(run)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

    def test_valid_run_exits_zero_and_leaves_run_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self.run_dir(tmp, [record('0'), record('1')],
                               [lookup('0', 0), lookup('1', 768), retrieve('1', 768)])
            before = {p.name: p.read_bytes() for p in run.iterdir()}
            result = self.invoke(run)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('Valid', result.stdout)
            self.assertEqual(before, {p.name: p.read_bytes() for p in run.iterdir()})

    def test_orphan_log_line_or_failed_text_needs_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = self.run_dir(tmp, [record('0')], [lookup('0', 0), lookup('9', 0)])
            self.assertEqual(self.invoke(run).returncode, 2)
        with tempfile.TemporaryDirectory() as tmp:
            run = self.run_dir(tmp, [record('0', text='')], [lookup('0', 0)])
            report = check.check_run(run)
            self.assertEqual(report['failed_requests'], 1)


if __name__ == '__main__':
    unittest.main()
