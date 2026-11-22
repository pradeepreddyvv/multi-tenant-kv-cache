import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from compare_live import compare


class PairedComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.runs=[]
        for name in ('equal','fixed','adaptive'):
            run=Path(self.tmp.name)/name;run.mkdir()
            (run/'manifest.json').write_text(json.dumps(dict(policy=name,seed=11,model='model',trace_sha256='same')))
            self.runs.append(run)

    @staticmethod
    def result(run):
        stats=dict(valid=10,median_ttft_s=1 if run.name=='adaptive' else 2,reuse_fraction=.5)
        return dict(valid=True,phase_tenant={p:{'ALL':stats} for p in ('before_shift','after_shift')})

    def test_paired_direction_and_incomplete_set(self):
        with patch('compare_live.summarize',side_effect=self.result):
            report=compare(self.runs)
            self.assertEqual(report['pairs'][0]['median_ttft_change_fraction'],-.5)
            with self.assertRaisesRegex(ValueError,'Each seed requires'):compare(self.runs[:-1])

    def test_rejects_unlike_models_or_invalid_evidence(self):
        path=self.runs[-1]/'manifest.json';m=json.loads(path.read_text());m['model']='other';path.write_text(json.dumps(m))
        with patch('compare_live.summarize',side_effect=self.result):
            with self.assertRaisesRegex(ValueError,'mismatch'):compare(self.runs)
        with patch('compare_live.summarize',return_value={'valid':False}):
            with self.assertRaisesRegex(ValueError,'invalid evidence'):compare(self.runs)


if __name__=='__main__':unittest.main()
