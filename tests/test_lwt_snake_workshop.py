"""Trusted local strategy catalog, real LWT CLI and v3 proof regression."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

from app.lwt_snake import arena, catalog
from app.lwt_snake.strategy import StrategyBridge

ROOT = Path(__file__).resolve().parents[1]
CATALOG = Path('app/lwt_snake/strategies/strategy-catalog.json')
CUSTOM = 'mobility-lookahead'


class WorkshopTests(unittest.TestCase):
    def cli(self, *args, timeout=90):
        return subprocess.run([sys.executable, '-m', 'app.lwt_snake.arena', *map(str, args)],
                              cwd=ROOT, shell=False, capture_output=True, timeout=timeout)

    def trusted_file(self, suffix, raw):
        path = catalog.TRUSTED_DIR / f'test-{uuid.uuid4().hex} 雪{suffix}'
        path.write_bytes(raw)
        self.addCleanup(lambda: path.unlink(missing_ok=True))
        return path

    def manifest(self, source=None, *, name='temporary', overrides=None):
        source = source or self.trusted_file('.lwt',
            (ROOT/'app/lwt_snake/strategy_baseline.lwt').read_bytes())
        item = {'id':name, 'path':source.name,
                'sha256':arena.digest_file(source), 'protocol':'LWA1'}
        if overrides:item.update(overrides)
        path = self.trusted_file('.json', json.dumps({'schema_version':1,'strategies':[item]}).encode())
        return path,source

    def test_checked_in_agent_strategy_passes_real_public_smoke(self):
        checked=self.cli('--check-strategy',CUSTOM,'--catalog',CATALOG)
        self.assertEqual(checked.returncode,0,checked.stderr)
        self.assertIn(b'static and LWA1 smoke check passed',checked.stdout)
        self.assertIn(b'frame 3: NONE/TRAPPED',checked.stdout)
        self.assertEqual(self.cli('--check-strategy',CUSTOM).returncode,2)
        self.assertEqual(self.cli('--check-strategy','', '--catalog',CATALOG).returncode,2)

    def test_catalog_rejects_untrusted_paths_ids_bytes_and_import_ast(self):
        path,source=self.manifest()
        self.assertEqual(len(catalog.load_catalog(path).entries),1)
        bad_items=[{'path':'../evil.lwt'},{'path':str(source)},{'path':'sub/evil.lwt'},
                   {'id':'baseline'},{'id':'Bad Name'},{'sha256':'0'*64},{'protocol':'LWA2'}]
        original=json.loads(path.read_text(encoding='utf-8'))
        for alteration in bad_items:
            with self.subTest(alteration=alteration):
                changed=json.loads(json.dumps(original))
                changed['strategies'][0].update(alteration)
                path.write_text(json.dumps(changed),encoding='utf-8')
                with self.assertRaises(catalog.CatalogError):catalog.load_catalog(path)
        path.write_text(json.dumps(original),encoding='utf-8')
        original['strategies'].append(dict(original['strategies'][0]))
        path.write_text(json.dumps(original),encoding='utf-8')
        with self.assertRaisesRegex(catalog.CatalogError,'duplicate'):catalog.load_catalog(path)
        path.write_bytes(b'{"schema_version":1,"schema_version":1,"strategies":[]}')
        with self.assertRaisesRegex(catalog.CatalogError,'duplicate'):catalog.load_catalog(path)
        path.write_bytes(b'\xff')
        with self.assertRaises(catalog.CatalogError):catalog.load_catalog(path)
        path.write_bytes(b' '*(catalog.MAX_CATALOG_BYTES+1))
        with self.assertRaisesRegex(catalog.CatalogError,'64 KiB'):catalog.load_catalog(path)
        source.write_bytes(b'import "lib.lwt" as lib;\n')
        path.write_text(json.dumps({'schema_version':1,'strategies':[{'id':'temporary',
            'path':source.name,'sha256':arena.digest_file(source),'protocol':'LWA1'}]}),encoding='utf-8')
        with self.assertRaisesRegex(catalog.CatalogError,'import'):catalog.load_catalog(path)
        source.write_bytes(b'emit "import"; # import in a comment is harmless\n')
        item=json.loads(path.read_text(encoding='utf-8'))
        item['strategies'][0]['sha256']=arena.digest_file(source)
        path.write_text(json.dumps(item),encoding='utf-8')
        self.assertEqual(len(catalog.load_catalog(path).entries),1)
        source.write_bytes(b'\xff')
        with self.assertRaises(catalog.CatalogError):catalog.load_catalog(path)
        source.write_bytes(b' '* (catalog.MAX_SOURCE_BYTES+1))
        with self.assertRaisesRegex(catalog.CatalogError,'64 KiB'):catalog.load_catalog(path)
        outside=ROOT/'README.md'
        link=catalog.TRUSTED_DIR/f'test-{uuid.uuid4().hex}.lwt'
        try:
            link.symlink_to(outside)
        except OSError:
            # Some Windows accounts cannot create links. Still exercise the
            # explicit symlink rejection branch; Linux CI takes the real path.
            with patch.object(Path, 'is_symlink', autospec=True, return_value=True):
                with self.assertRaisesRegex(catalog.CatalogError, 'regular file'):
                    catalog._source(source, '0'*64)
        else:
            self.addCleanup(lambda:link.unlink(missing_ok=True))
            with self.assertRaises(catalog.CatalogError):catalog._source(link,'0'*64)

    def test_three_strategies_three_seeds_workers_are_byte_identical(self):
        with tempfile.TemporaryDirectory(prefix='s39 workers 雪 ') as folder:
            outputs=[]
            for workers in (1,2,4):
                directory=Path(folder)/str(workers)
                made=self.cli('--catalog',CATALOG,'--strategies','baseline,bfs,mobility-lookahead',
                              '--seeds','4,7,11','--max-ticks','6','--workers',workers,'--output',directory)
                self.assertEqual(made.returncode,0,made.stderr)
                verified=self.cli('--verify',directory/'result.json','--catalog',CATALOG)
                self.assertEqual(verified.returncode,0,verified.stderr)
                data=json.loads((directory/'result.json').read_text(encoding='utf-8'))
                self.assertEqual(data['schema_version'],3)
                self.assertEqual(len(data['cases']),9)
                self.assertTrue(all(row['game_verified'] and row['policy_verified'] for row in data['cases']))
                outputs.append({str(file.relative_to(directory)):file.read_bytes()
                                for file in directory.rglob('*.json')})
            self.assertEqual(outputs[0],outputs[1])
            self.assertEqual(outputs[1],outputs[2])
            explained=self.cli('--explain',Path(folder)/'1/result.json','--catalog',CATALOG,
                               '--case','mobility-lookahead/4','--step','1')
            self.assertEqual(explained.returncode,0,explained.stderr)
            self.assertIn(b'LWT_advice=LWA1|',explained.stdout)

    def test_v3_requires_catalog_and_detects_source_and_identity_changes(self):
        with tempfile.TemporaryDirectory(prefix='s39 tamper ') as folder:
            root=Path(folder)
            manifest,source=self.manifest(name='temporary')
            output=root/'one'
            made=self.cli('--catalog',manifest,'--strategies','temporary','--seeds','4',
                          '--max-ticks','3','--output',output)
            self.assertEqual(made.returncode,0,made.stderr)
            result=output/'result.json'
            self.assertEqual(self.cli('--verify',result,'--catalog',manifest).returncode,0)
            self.assertEqual(self.cli('--verify',result).returncode,3)
            legacy_only=self.cli('--game-only','--verify',result,'--catalog',manifest)
            self.assertEqual(legacy_only.returncode,3)
            self.assertIn(b'only for legacy v1',legacy_only.stderr)
            other=self.trusted_file('.json',manifest.read_bytes())
            self.assertEqual(self.cli('--verify',result,'--catalog',other).returncode,3)
            changed=json.loads(result.read_text(encoding='utf-8'))
            changed['catalog']['sha256']='0'*64
            forged=root/'forged.json';forged.write_text(json.dumps(changed),encoding='utf-8')
            self.assertEqual(self.cli('--verify',forged,'--catalog',manifest).returncode,3)
            source.write_bytes(source.read_bytes()+b'\n# changed after run\n')
            rejected=self.cli('--verify',result,'--catalog',manifest)
            self.assertEqual(rejected.returncode,3,rejected.stdout)
            self.assertIn(b'source digest mismatch',rejected.stderr)

    def test_relabelled_custom_game_cannot_claim_builtin_policy(self):
        fixed=ROOT/'reports/s39-demo'
        source=json.loads((fixed/'result.json').read_text(encoding='utf-8'))
        original=next(row for row in source['cases'] if row['strategy_id']==CUSTOM and row['seed']==4)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'replays').mkdir();(root/'decisions').mkdir()
            row=dict(original)
            row['strategy_id']='baseline'
            row['strategy_sha256']=source['strategies']['baseline']['sha256']
            row['replay_path']='replays/baseline-4.json'
            row['decision_path']='decisions/baseline-4.json'
            shutil.copyfile(fixed/original['replay_path'],root/row['replay_path'])
            evidence=json.loads((fixed/original['decision_path']).read_text(encoding='utf-8'))
            evidence['strategy_id']='baseline'
            evidence['strategy_sha256']=row['strategy_sha256']
            target=root/row['decision_path'];target.write_text(json.dumps(evidence),encoding='utf-8')
            row['decision_sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
            forged=dict(source,seeds=[4],strategies={'baseline':source['strategies']['baseline']},
                        cases=[row],summary=arena.summary([row]))
            result=root/'result.json';result.write_text(json.dumps(forged),encoding='utf-8')
            rejected=self.cli('--verify',result,'--catalog',CATALOG)
            self.assertEqual(rejected.returncode,3,rejected.stdout)
            self.assertIn(b'baseline/4: decision 1',rejected.stderr)
            self.assertIn(b'response/direction/reason mismatch',rejected.stderr)

    def test_runtime_source_change_fails_match_with_verified_game_prefix(self):
        manifest,source=self.manifest(name='temporary')
        loaded=catalog.load_catalog(manifest)
        entry=loaded.entries['temporary']
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder);(directory/'replays').mkdir()
            class ChangingBridge(StrategyBridge):
                def query(self,state,cancel=None):
                    answer=super().query(state,cancel)
                    source.write_bytes(source.read_bytes()+b'\n# changed during query\n')
                    return answer
            case=arena.run_case('temporary',4,8,5,3,directory,strategy_path=source,
                                expected_digest=entry.sha256,catalog=loaded,
                                strategy_factory=ChangingBridge)
            self.assertEqual(case['stop_reason'],'failed')
            self.assertEqual(case['error_category'],'CatalogError')
            self.assertTrue(case['game_verified'])
            self.assertFalse(case['policy_verified'])
            self.assertEqual(case['ticks'],0)
            self.assertIsNotNone(case['replay_path'])


if __name__=='__main__':
    unittest.main()
