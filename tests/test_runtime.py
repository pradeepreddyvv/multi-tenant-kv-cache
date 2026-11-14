"""Protect evidence against accidental overwrite without requiring model imports."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from runtime import output_directory


class OutputDirectoryTests(unittest.TestCase):
    def test_existing_experiment_is_rejected_and_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            for artifact in ['requests.jsonl', 'batches.jsonl', 'completed.json',
                             'occupancy.json', 'occupancy.jsonl', 'quota-state.json']:
                file = out / artifact
                file.write_text('existing evidence')
                with patch.dict(os.environ, {'DIS_ML_RESULT_DIR': str(out)}):
                    with self.assertRaises(RuntimeError):
                        output_directory()
                self.assertEqual(file.read_text(), 'existing evidence')
                file.unlink()

    def test_launcher_metadata_does_not_block_new_workload(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / 'launch.json').write_text('{}')
            (out / 'memory.jsonl').touch()
            (out / 'run.log').touch()
            with patch.dict(os.environ, {'DIS_ML_RESULT_DIR': str(out)}):
                self.assertEqual(output_directory(), out)


if __name__ == '__main__':
    unittest.main()
