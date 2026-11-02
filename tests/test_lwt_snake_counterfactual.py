"""Real LWT policy and game process proof for S40 one-step branches."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RESULT = 'reports/s39-demo/result.json'
CATALOG = 'app/lwt_snake/strategies/strategy-catalog.json'


class CounterfactualTests(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, '-m', 'app.lwt_snake.counterfactual',
                               *map(str, args)], cwd=ROOT, shell=False,
                              capture_output=True, timeout=90)

    def generate(self, path):
        return self.cli('--analyze', RESULT, '--catalog', CATALOG,
                        '--case', 'baseline/4', '--step', 2,
                        '--strategies', 'baseline,bfs,mobility-lookahead', '--output', path)

    def test_same_observation_diverges_and_new_game_rechecks_each_branch(self):
        with tempfile.TemporaryDirectory() as parent:
            first, second = Path(parent)/'one', Path(parent)/'two'
            self.assertEqual(self.generate(first).returncode, 0)
            self.assertEqual(self.generate(second).returncode, 0)
            for relative in ('analysis.json', 'branches/baseline.json',
                             'branches/bfs.json', 'branches/mobility-lookahead.json'):
                self.assertEqual((first/relative).read_bytes(), (second/relative).read_bytes())
            data = json.loads((first/'analysis.json').read_text(encoding='utf-8'))
            self.assertEqual(data['game_transaction'], 3)
            self.assertEqual([row['response'].split('|')[3] for row in data['candidates']],
                             ['R', 'D', 'D'])
            self.assertEqual(self.cli('--verify', first, '--catalog', CATALOG).returncode, 0)
            explained = self.cli('--explain', first, '--catalog', CATALOG)
            self.assertEqual(explained.returncode, 0, explained.stderr)
            self.assertIn(b'same verified observation trace', explained.stdout)

    def test_tampering_and_old_schema_are_rejected(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent)/'one'
            self.assertEqual(self.generate(root).returncode, 0)
            file = root/'analysis.json'
            original = file.read_bytes()
            data = json.loads(original)
            for field, value in [('step', 3), ('result_sha256', '0'*64),
                                 ('catalog_sha256', '0'*64), ('game_transaction', 2)]:
                changed = dict(data, **{field: value})
                file.write_text(json.dumps(changed), encoding='utf-8')
                rejected = self.cli('--verify', root, '--catalog', CATALOG)
                self.assertNotEqual(rejected.returncode, 0, (field, rejected.stdout))
            file.write_bytes(original)
            branch = root/'branches/bfs.json'
            branch.write_bytes(branch.read_bytes() + b' ')
            self.assertNotEqual(self.cli('--verify', root, '--catalog', CATALOG).returncode, 0)
            file.write_bytes(b'{"schema_version":1,"schema_version":1}')
            self.assertIn(b'duplicate JSON key', self.cli('--verify', root, '--catalog', CATALOG).stderr)
            denied = self.cli('--analyze', 'reports/s38-demo/result.json', '--catalog', CATALOG,
                              '--case', 'baseline/4', '--step', 1, '--strategies', 'baseline',
                              '--output', Path(parent)/'old')
            self.assertNotEqual(denied.returncode, 0)


if __name__ == '__main__':
    unittest.main()
