import json
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from analyze_live import summarize


class LiveSummaryTests(unittest.TestCase):
    def fixture(self, root):
        manifest=dict(status='completed',policy='equal',seed=1,trace_sha256='synthetic',
            tenants=['A','B','C','D'],warmup_end_s=1,shift_at_s=5,measured_end_s=10,budget_bytes=100)
        (root/'manifest.json').write_text(json.dumps(manifest))
        row=dict(request_id='r1',tenant='A',status='ok',prompt_tokens=4160,output_tokens=32,
            scheduled_at_s=2,submitted_at_s=2,first_token_at_s=2.2,finished_at_s=2.6,text='synthetic')
        (root/'requests.jsonl').write_text(json.dumps(row)+'\n')
        (root/'trace.json').write_text(json.dumps([row]))
        manifest['trace_sha256']=hashlib.sha256(json.dumps([row],separators=(',', ':')).encode()).hexdigest()
        (root/'manifest.json').write_text(json.dumps(manifest))
        (root/'run.log').write_text('Reqid: r1, Total tokens 4160, Inference Engine computed tokens: 0, LMCache hit tokens: 0\n')
        (root/'occupancy.jsonl').write_text(json.dumps(dict(retained_bytes={'A':0}))+'\n')
        (root/'quota_updates.jsonl').write_text(json.dumps(dict(status='initialized',quotas=dict(A=25,B=25,C=25,D=25)))+'\n')

    def test_small_samples_withhold_p95_and_compute_ttft(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root);r=summarize(root)
            self.assertTrue(r['valid'])
            self.assertIsNone(r['phase_tenant']['before_shift']['A']['p95_ttft_s'])
            self.assertAlmostEqual(r['phase_tenant']['before_shift']['A']['median_ttft_s'],.2)

    def test_missing_logs_fail_instead_of_zero_hits(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root);(root/'run.log').write_text('')
            self.assertFalse(summarize(root)['valid'])

    def test_changed_trace_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            trace=json.loads((root/'trace.json').read_text());trace[0]['tenant']='B'
            (root/'trace.json').write_text(json.dumps(trace))
            result=summarize(root)
            self.assertFalse(result['valid'])
            self.assertIn('trace hash does not match manifest',result['problems'])

    def test_same_count_wrong_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            row=json.loads((root/'requests.jsonl').read_text());row['request_id']='other'
            (root/'requests.jsonl').write_text(json.dumps(row)+'\n')
            self.assertIn('request IDs do not match trace',summarize(root)['problems'])

    def test_missing_quota_log_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root);(root/'quota_updates.jsonl').unlink()
            self.assertIn('no quota initialization evidence',summarize(root)['problems'])

    def test_same_budget_wrong_membership_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);self.fixture(root)
            (root/'quota_updates.jsonl').write_text(json.dumps(dict(status='initialized',quotas={'unknown':100}))+'\n')
            self.assertIn('quota membership mismatch',summarize(root)['problems'])


if __name__=='__main__':unittest.main()
