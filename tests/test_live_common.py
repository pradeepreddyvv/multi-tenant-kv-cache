import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from live_common import build_trace, trace_hash, window_observations


class LiveEvidenceTests(unittest.TestCase):
    def test_trace_deterministic_and_tenant_specific(self):
        rows=build_trace(11, 60, 3, 30)
        self.assertEqual(trace_hash(rows),trace_hash(build_trace(11,60,3,30)))
        self.assertNotEqual(trace_hash(rows),trace_hash(build_trace(12,60,3,30)))
        self.assertTrue(all(len(r['prompt'])==4160 for r in rows))
        prefixes={}
        for r in rows:
            key=(r['tenant'],r['variant'])
            prefixes.setdefault(key,r['prompt'][:4096])
            self.assertEqual(prefixes[key],r['prompt'][:4096])
        self.assertEqual(len({tuple(v) for v in prefixes.values()}),len(prefixes))

    def test_missing_attribution_rejects_window(self):
        record=dict(tenant='A',request_id='r1',prompt_tokens=4160,status='ok')
        rows=window_observations([record],'',{},5)
        self.assertEqual(rows[0]['errors'],1)
        self.assertEqual(rows[0]['eligible_input_tokens'],0)

    def test_actual_retrieval_and_idle_tenants(self):
        record=dict(tenant='A',request_id='r1',prompt_tokens=4160,status='ok')
        log=('Reqid: r1, Total tokens 4160, Inference Engine computed tokens: 0, LMCache hit tokens: 4096\n'
             '[req_id=r1] Retrieved 4096 out of 4160 required tokens\n')
        rows=window_observations([record],log,{'A':224*2**20},5)
        self.assertEqual(len(rows),4)
        self.assertEqual(rows[0]['retrieved_tokens'],4096)
        self.assertEqual(rows[0]['eligible_input_tokens'],4096)
        self.assertEqual(rows[1]['errors'],0)
        self.assertEqual(rows[1]['eligible_input_tokens'],0)

    def test_large_model_sizes_are_validated(self):
        record=dict(tenant='A',request_id='r1',prompt_tokens=4160,status='ok')
        log=('Reqid: r1, Total tokens 4160, Inference Engine computed tokens: 0, LMCache hit tokens: 4096\n'
             '[req_id=r1] Retrieved 4096 out of 4160 required tokens (from 4160 total tokens). size: 1.0000 gb\n')
        self.assertEqual(window_observations([record],log,{},5,256*1024)[0]['errors'],0)
        self.assertEqual(window_observations([record],log,{},5)[0]['errors'],1)

    def test_error_not_counted_as_demand_or_success(self):
        rows=window_observations([dict(tenant='B',status='error')],'',{},5)
        self.assertEqual(rows[1]['errors'],1)


if __name__=='__main__': unittest.main()
