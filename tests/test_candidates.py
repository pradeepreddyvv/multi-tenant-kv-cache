import unittest
from policy.candidates import Candidate
from scripts.live_common import build_trace

class CandidatesTest(unittest.TestCase):
    def test_budget_granularity_and_idle_hold(self):
        for name in ('slow','reuse','v3'):
            c=Candidate(name,'ABCD',128*2**30,2**30)
            self.assertIsNone(c.decide(31))
            for window in range(1,25):
                for n in range(24): c.arrival('ABCD'[n%4] if n<8 else 'A',n%4)
                q=c.decide(window*31)
                if q:
                    self.assertEqual(sum(q.values()),128*2**30)
                    self.assertTrue(all(v%2**30==0 for v in q.values()))
                    self.assertTrue(all(v>=0 for v in q.values()))
    def test_reuse_resists_one_use_scanner(self):
        slow=Candidate('slow','ABCD',128,1);reuse=Candidate('reuse','ABCD',128,1)
        for window in range(1,30):
            for c in (slow,reuse):
                for n in range(30):c.arrival('D',window*100+n)
                for t in 'ABC':
                    for n in range(10):c.arrival(t,n%4)
                c.decide(window*31)
        self.assertGreater(slow.quotas['D'],reuse.quotas['D'])
    def test_scan_unique_prefixes_and_trace_identity(self):
        a=build_trace(91,100,.5,50,pool=2,scenario='scan')
        self.assertEqual(a,build_trace(91,100,.5,50,pool=2,scenario='scan'))
        d=[r for r in a if r['tenant']=='D']
        self.assertEqual(len(d),len({r['variant'] for r in d}))
        self.assertTrue(all(len(r['prompt'])==4160 for r in a))
    def test_burst_times_ordered_and_bounded(self):
        r=build_trace(92,100,2,50,pool=2,scenario='burst')
        times=[x['scheduled_at_s'] for x in r]
        self.assertEqual(times,sorted(times));self.assertTrue(all(0<=t<100 for t in times))

if __name__=='__main__':unittest.main()
