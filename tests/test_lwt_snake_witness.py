"""S41 real LWT witness search, bounded absence and proof tampering."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from app.lwt_snake import witness

ROOT = Path(__file__).resolve().parents[1]
RESULT = 'reports/s39-demo/result.json'
CATALOG = 'app/lwt_snake/strategies/strategy-catalog.json'


class WitnessTests(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, '-m', 'app.lwt_snake.witness', *map(str, args)],
                              cwd=ROOT, shell=False, capture_output=True, timeout=125)

    def create(self, output, budget=32):
        return self.cli('--result', RESULT, '--catalog', CATALOG, '--reference', 'baseline',
                        '--challengers', 'mobility-lookahead,bfs', '--max-observations', budget,
                        '--output', output)

    def test_fixed_witness_and_bounded_absence_are_reverified(self):
        found = self.cli('--verify', 'reports/s41-found', '--catalog', CATALOG)
        self.assertEqual(found.returncode, 0, found.stderr)
        self.assertIn(b'found=true scanned=2/32 case=baseline/4 step=2 challenger=bfs', found.stdout)
        absent = self.cli('--verify', 'reports/s41-none', '--catalog', CATALOG)
        self.assertEqual(absent.returncode, 0, absent.stderr)
        self.assertIn(b'found=false scanned=1/1', absent.stdout)
        rejected = self.cli('--verify', 'reports/s41-tampered', '--catalog', CATALOG)
        self.assertEqual(rejected.returncode, 3, rejected.stdout)
        self.assertIn(b'agent feedback evidence mismatch', rejected.stderr)

    def test_repeat_generation_is_byte_identical_and_rejects_bad_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder)/'a', Path(folder)/'b'
            first = self.create(a, budget=1)
            second = self.create(b, budget=1)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual({p.name:p.read_bytes() for p in a.iterdir()},
                             {p.name:p.read_bytes() for p in b.iterdir()})
            self.assertEqual(self.create(Path(folder)/'bad', budget=0).returncode, 2)
            self.assertEqual(self.cli('--result', RESULT, '--catalog', CATALOG,
                                      '--reference', 'baseline', '--challengers', 'baseline',
                                      '--output', Path(folder)/'invalid').returncode, 2)
            self.assertEqual(self.create(a, budget=1).returncode, 2)
            self.assertEqual(self.cli('--verify', a).returncode, 2)
            data = json.loads((a/'witness.json').read_text(encoding='utf-8'))
            data['found'] = True
            (a/'witness.json').write_text(json.dumps(data), encoding='utf-8')
            self.assertEqual(self.cli('--verify', a, '--catalog', CATALOG).returncode, 3)

    def test_total_deadline_reclaims_real_child(self):
        argv = ['witness', '--verify', 'reports/s41-found', '--catalog', CATALOG]
        with patch.object(witness, 'DEADLINE', .01), patch.object(sys, 'argv', argv):
            self.assertEqual(witness.supervised_main(), 3)

    def test_no_completed_reference_is_an_error_not_no_witness(self):
        data = json.loads((ROOT/RESULT).read_text(encoding='utf-8'))
        for row in data['cases']:
            if row['strategy_id'] == 'baseline':
                row['stop_reason'] = 'failed'
        with patch.object(witness.arena, 'verify', return_value=data):
            with self.assertRaisesRegex(witness.WitnessError, 'no completed'):
                witness.search(ROOT/RESULT, ROOT/CATALOG, 'baseline', ['bfs'], 1)

    def test_no_witness_cannot_contain_branch_analysis(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name in ('witness.json', 'agent-feedback.json', 'report.md'):
                (root/name).write_bytes((ROOT/'reports/s41-none'/name).read_bytes())
            (root/'analysis').mkdir()
            self.assertEqual(self.cli('--verify', root, '--catalog', CATALOG).returncode, 3)

    def test_output_creation_and_write_errors_are_usage_errors(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            blocked_parent = root/'file'
            blocked_parent.write_text('not a directory', encoding='utf-8')
            with patch.object(witness, 'search', return_value=({'found': False}, None, None)):
                with self.assertRaisesRegex(witness.WitnessUsageError, 'cannot create'):
                    witness.create(None, None, 'baseline', ['bfs'], 1, blocked_parent/'out')
                with patch.object(witness.arena, 'atomic_json', side_effect=PermissionError()):
                    with self.assertRaisesRegex(witness.WitnessUsageError, 'cannot write'):
                        witness.create(None, None, 'baseline', ['bfs'], 1, root/'out')


if __name__ == '__main__':
    unittest.main()
