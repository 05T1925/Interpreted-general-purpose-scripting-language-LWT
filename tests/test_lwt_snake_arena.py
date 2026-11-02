"""Real LWT strategy matches, independent replay verification and adversarial files."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from app.lwt_snake import arena
from app.lwt_snake.strategy import StrategyBridge
from app.lwt_snake.bridge import LwtSnakeBridge

ROOT=Path(__file__).resolve().parents[1]


class ArenaTests(unittest.TestCase):
    def cli(self,*args):
        return subprocess.run([sys.executable,'-m','app.lwt_snake.arena',*map(str,args)],
                              cwd=ROOT,capture_output=True,timeout=70)

    def test_review_counterexamples_rejected(self):
        """A game replay cannot establish who chose its commands; zero cases prove nothing."""
        fixed=json.loads((ROOT/'reports/s37-demo/result.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory(prefix='s38 counterexample ') as folder:
            target=Path(folder)
            original=fixed['cases'][0]
            self.assertEqual((original['strategy_id'],original['seed'],original['score']),('baseline',4,10))
            row=dict(original)
            row.update(strategy_id='bfs',strategy_sha256=fixed['strategies']['bfs']['sha256'],
                       replay_path='replays/bfs-4.json')
            (target/'replays').mkdir()
            shutil.copyfile(ROOT/'reports/s37-demo'/original['replay_path'],target/row['replay_path'])
            forged=dict(fixed,seeds=[4],strategies={'bfs':fixed['strategies']['bfs']},cases=[row],
                        summary=arena.summary([row]))
            result=target/'result.json'
            result.write_text(json.dumps(forged),encoding='utf-8')
            rejected=self.cli('--verify',result)
            self.assertEqual(rejected.returncode,3)
            self.assertIn(b'game replay only; strategy decisions unverified',rejected.stderr)
            downgraded=self.cli('--game-only','--verify',result)
            self.assertEqual(downgraded.returncode,0,downgraded.stderr)
            self.assertIn(b'game replay only; strategy decisions unverified',downgraded.stdout)

    def test_empty_inventory_rejected(self):
        fixed=json.loads((ROOT/'reports/s37-demo/result.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory(prefix='s38 empty ') as folder:
            result=Path(folder)/'result.json'
            result.write_text(json.dumps(dict(fixed,seeds=[],strategies={},cases=[],summary={})),encoding='utf-8')
            self.assertEqual(self.cli('--game-only','--verify',result).returncode,3)

    def test_v2_policy_tampering_and_explanation(self):
        with tempfile.TemporaryDirectory(prefix='s38 proof 雪 ') as folder:
            root=Path(folder);original=root/'original'
            made=self.cli('--strategies','baseline','--seeds','4','--max-ticks','12','--output',original)
            self.assertEqual(made.returncode,0,made.stderr)
            clean=self.cli('--verify',original/'result.json')
            self.assertEqual(clean.returncode,0,clean.stderr)
            self.assertIn(b'game and policy decisions',clean.stdout)
            data=json.loads((original/'result.json').read_text(encoding='utf-8'))
            row=data['cases'][0]
            self.assertEqual((row['score'],row['ticks'],row['game_verified'],row['policy_verified']),(10,12,True,True))
            for field,expected in [('response_direction',b'response'),('response_reason',b'response'),
                                   ('sequence',b'sequence'),('count',b'extra game transaction'),
                                   ('transaction',b'game_transaction'),('request',b'query-before-TURN')]:
                with self.subTest(field=field):
                    copy=root/field;shutil.copytree(original,copy)
                    result_file=copy/'result.json';changed=json.loads(result_file.read_text(encoding='utf-8'))
                    item=changed['cases'][0]
                    decision_file=copy/item['decision_path']
                    evidence=json.loads(decision_file.read_text(encoding='utf-8'))
                    decisions=evidence['decisions']
                    if field=='response_direction':
                        parts=decisions[0]['response'].split('|');parts[3]='U';decisions[0]['response']='|'.join(parts)
                    elif field=='response_reason':
                        parts=decisions[0]['response'].split('|');parts[4]='FOOD';decisions[0]['response']='|'.join(parts)
                    elif field=='sequence':decisions[0]['sequence']=2
                    elif field=='count':decisions.pop()
                    elif field=='transaction':decisions[0]['game_transaction']=3
                    else:decisions[0]['request']=decisions[1]['request']
                    decision_file.write_text(json.dumps(evidence),encoding='utf-8')
                    item['decision_sha256']=hashlib.sha256(decision_file.read_bytes()).hexdigest()
                    result_file.write_text(json.dumps(changed),encoding='utf-8')
                    rejected=self.cli('--verify',result_file)
                    self.assertEqual(rejected.returncode,3,(field,rejected.stdout,rejected.stderr))
                    self.assertIn(expected,rejected.stderr)
                    self.assertIn(b'baseline/4',rejected.stderr)
            # Rebinding the same LWS1 commands to BFS, with every ordinary SHA updated,
            # must fail when the fresh LWT BFS process answers the first divergent step.
            copy=root/'relabel';shutil.copytree(original,copy)
            result_file=copy/'result.json';changed=json.loads(result_file.read_text(encoding='utf-8'))
            item=changed['cases'][0]
            bfs=arena.STRATEGIES['bfs'];digest=arena.digest_file(bfs)
            changed['strategies']={'bfs':{'path':str(bfs.relative_to(ROOT)).replace('\\','/'),'sha256':digest,'protocol':'LWA1'}}
            item['strategy_id']='bfs';item['strategy_sha256']=digest
            for kind in ('replay','decision'):
                old=copy/item[kind+'_path'];new=old.with_name('bfs-4.json');old.rename(new)
                item[kind+'_path']=f'{kind}s/bfs-4.json' if kind=='decision' else 'replays/bfs-4.json'
            decision_file=copy/item['decision_path'];evidence=json.loads(decision_file.read_text(encoding='utf-8'))
            evidence['strategy_id']='bfs';evidence['strategy_sha256']=digest
            decision_file.write_text(json.dumps(evidence),encoding='utf-8')
            item['decision_sha256']=hashlib.sha256(decision_file.read_bytes()).hexdigest()
            changed['summary']=arena.summary([item])
            result_file.write_text(json.dumps(changed),encoding='utf-8')
            rejected=self.cli('--verify',result_file)
            self.assertEqual(rejected.returncode,3,rejected.stdout)
            self.assertIn(b'bfs/4: decision',rejected.stderr)
            # A limit cannot be relabelled TRAPPED by appending a made-up NONE.
            copy=root/'false-trapped';shutil.copytree(original,copy)
            result_file=copy/'result.json';changed=json.loads(result_file.read_text(encoding='utf-8'))
            item=changed['cases'][0];decision_file=copy/item['decision_path']
            evidence=json.loads(decision_file.read_text(encoding='utf-8'))
            replay=arena.load(copy/item['replay_path'])
            last=arena.reconstruct(replay).states[-1]
            sequence=len(evidence['decisions'])+1
            evidence['decisions'].append({'sequence':sequence,'game_transaction':len(replay.transactions),
                                          'request':arena.encode_snapshot(last,sequence)[:-1].decode('ascii'),
                                          'response':f'LWA1|{sequence:06d}|NONE|-|TRAPPED'})
            decision_file.write_text(json.dumps(evidence),encoding='utf-8')
            item['decision_sha256']=hashlib.sha256(decision_file.read_bytes()).hexdigest()
            item['stop_reason']='trapped';changed['summary']=arena.summary([item])
            result_file.write_text(json.dumps(changed),encoding='utf-8')
            rejected=self.cli('--verify',result_file)
            self.assertEqual(rejected.returncode,3,rejected.stdout)
            self.assertIn(b'baseline/4: decision',rejected.stderr)
            for step in (1,2,3):
                explained=self.cli('--explain',original/'result.json','--case','baseline/4','--step',step)
                self.assertEqual(explained.returncode,0,explained.stderr)
                self.assertIn(b'LWT_advice=LWA1|',explained.stdout)
                self.assertIn(b'before_tx=',explained.stdout)
            turn_and_food=self.cli('--explain',ROOT/'reports/s38-demo/result.json','--case','bfs/4','--step','3')
            self.assertEqual(turn_and_food.returncode,0,turn_and_food.stderr)
            self.assertIn(b'|MOVE|L|FOOD commands=TURN,TICK',turn_and_food.stdout)
            self.assertIn(b'score=20 delta=10',turn_and_food.stdout)
            self.assertEqual(self.cli('--explain',result_file,'--case','bfs/4','--step','1').returncode,3)

    def test_result_inventory_rejects_noncanonical_json(self):
        fixed=json.loads((ROOT/'reports/s37-demo/result.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as folder:
            result=Path(folder)/'result.json'
            bad=[dict(fixed,seeds=[]),dict(fixed,board={'width':24,'height':19}),
                 dict(fixed,seeds=[True]),dict(fixed,max_ticks=True),
                 dict(fixed,cases=[]),dict(fixed,strategies={}),
                 dict(fixed,seeds=[4,4])]
            for value in bad:
                with self.subTest(value=str(value)[:80]):
                    result.write_text(json.dumps(value),encoding='utf-8')
                    self.assertEqual(self.cli('--game-only','--verify',result).returncode,3)
            for raw in (b'{"schema_version":1,"schema_version":1}',b'{"x":NaN}',b'{"x":999999999999999999999}'):
                with self.subTest(raw=raw):
                    result.write_bytes(raw)
                    self.assertEqual(self.cli('--game-only','--verify',result).returncode,3)

    def test_even_number_of_scores_keeps_finite_median(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'two-seeds'
            self.assertEqual(self.cli('--strategies','baseline','--seeds','4,7',
                                      '--max-ticks','12','--workers','2','--output',output).returncode,0)
            data=json.loads((output/'result.json').read_text(encoding='utf-8'))
            self.assertEqual(data['summary']['baseline']['score_median'],5.0)
            checked=self.cli('--verify',output/'result.json')
            self.assertEqual(checked.returncode,0,checked.stderr)

    def test_terminal_game_rejects_extra_policy_consultation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);original=root/'won'
            made=self.cli('--strategies','baseline','--seeds','4','--width','4','--height','2',
                          '--max-ticks','40','--output',original)
            self.assertEqual(made.returncode,0,made.stderr)
            result_file=original/'result.json'
            data=json.loads(result_file.read_text(encoding='utf-8'))
            self.assertEqual(data['cases'][0]['stop_reason'],'won')
            self.assertEqual(self.cli('--verify',result_file).returncode,0)
            copy=root/'extra';shutil.copytree(original,copy)
            forged=copy/'result.json';data=json.loads(forged.read_text(encoding='utf-8'))
            row=data['cases'][0];decision_file=copy/row['decision_path']
            evidence=json.loads(decision_file.read_text(encoding='utf-8'))
            last=dict(evidence['decisions'][-1]);last['sequence']+=1
            evidence['decisions'].append(last)
            decision_file.write_text(json.dumps(evidence),encoding='utf-8')
            row['decision_sha256']=hashlib.sha256(decision_file.read_bytes()).hexdigest()
            forged.write_text(json.dumps(data),encoding='utf-8')
            rejected=self.cli('--verify',forged)
            self.assertEqual(rejected.returncode,3,rejected.stdout)
            self.assertIn(b'baseline/4: decision',rejected.stderr)

    def test_baseline_public_lwa1_protocol_and_distinct_choice(self):
        from tests.test_lwt_snake_strategy import frame
        inputs=[frame(),frame(2,height=2,direction='L',food=(3,1),body=((1,0),(1,1),(0,1),(0,0))),
                frame(3,height=3,direction='U',food=(3,2),body=((0,0),(1,0),(1,1),(0,1),(0,2))),
                frame(4,height=2,direction='U',food=(3,1),body=((2,1),(1,1),(0,1))),
                b'LWA2|000005|4|1|R|3|0|3|2,0;1,0;0,0',
                frame(5)]
        p=subprocess.run([sys.executable,'-u','-m','lwt','app/lwt_snake/strategy_baseline.lwt'],
                         cwd=ROOT,input=b'\n'.join(inputs)+b'\n',capture_output=True,timeout=10)
        self.assertEqual((p.returncode,p.stderr),(0,b''))
        self.assertEqual(p.stdout.splitlines(),[
            b'LWA1|000001|MOVE|R|SPACE',b'LWA1|000002|MOVE|L|SPACE',
            b'LWA1|000003|NONE|-|TRAPPED',b'LWA1|000004|MOVE|U|SPACE',
            b'LWA1|ERR|000005|BAD_FRAME',b'LWA1|000005|MOVE|R|SPACE'])
        self.assertEqual(self.cli('--strategies','../evil','--output','any').returncode,2)

    def test_six_real_matches_are_worker_invariant_and_reverified(self):
        with tempfile.TemporaryDirectory(prefix='arena workers 雪 ') as folder:
            outputs=[];evidence_bytes=[]
            for workers in (1,2,4):
                directory=Path(folder)/str(workers)
                result=self.cli('--seeds','4,7,11','--max-ticks','12','--workers',workers,'--output',directory)
                self.assertEqual(result.returncode,0,result.stderr)
                verify=self.cli('--verify',directory/'result.json')
                self.assertEqual(verify.returncode,0,verify.stderr)
                self.assertIn(b'Verified 6 matches: game and policy decisions.',verify.stdout)
                data=(directory/'result.json').read_bytes()
                outputs.append(data)
                evidence_bytes.append({str(file.relative_to(directory)):file.read_bytes()
                                       for file in directory.rglob('*.json')})
                parsed=json.loads(data)
                self.assertEqual(len(parsed['cases']),6)
                self.assertTrue(all(case['game_verified'] and case['policy_verified'] for case in parsed['cases']))
                for case in parsed['cases']:
                    self.assertEqual(case['ticks'],12)
                    self.assertEqual(case['stop_reason'],'limit')
            self.assertEqual(outputs[0],outputs[1])
            self.assertEqual(outputs[1],outputs[2])
            self.assertEqual(evidence_bytes[0],evidence_bytes[1])
            self.assertEqual(evidence_bytes[1],evidence_bytes[2])

    def test_tampering_is_located_by_case_and_field_or_transaction(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'original'
            self.assertEqual(self.cli('--seeds','4,7,11','--max-ticks','5','--output',source).returncode,0)
            for target,expected in [('score',b'score/phase'),('seed',b'seed'),
                                    ('strategy',b'strategy source digest'),('game',b'game digest'),
                                    ('missing',b'missing replay'),('transaction',b'transaction')]:
                with self.subTest(target=target):
                    copy=root/target;shutil.copytree(source,copy)
                    path=copy/'result.json';data=json.loads(path.read_text(encoding='utf-8'))
                    row=data['cases'][3]  # bfs/4
                    replay=copy/row['replay_path']
                    if target=='score':row['score']+=10
                    elif target=='seed':row['seed']=12
                    elif target=='strategy':data['strategies']['bfs']['sha256']='0'*64
                    elif target=='game':row['game_sha256']='0'*64
                    elif target=='missing':replay.unlink()
                    else:
                        record=json.loads(replay.read_text(encoding='utf-8'))
                        fields=record['transactions'][2]['response'].split('|')
                        fields[4]=str(int(fields[4])+10)
                        record['transactions'][2]['response']='|'.join(fields)
                        replay.write_text(json.dumps(record),encoding='utf-8')
                        row['replay_sha256']=hashlib.sha256(replay.read_bytes()).hexdigest()
                    path.write_text(json.dumps(data),encoding='utf-8')
                    result=self.cli('--verify',path)
                    self.assertEqual(result.returncode,3,result.stdout)
                    self.assertIn(expected,result.stderr)
                    if target!='strategy':self.assertIn(b'bfs/4',result.stderr)

    def test_faults_keep_verified_prefix_and_release_children(self):
        scripts=["import sys;sys.stdin.buffer.readline();sys.stdout.write('BAD\\n');sys.stdout.flush();sys.stderr.write('x'*20000)",
                 'import sys,time;sys.stdin.buffer.readline();time.sleep(5)',
                 'import sys;sys.stdin.buffer.readline();sys.stderr.write("bad");sys.exit(7)']
        for script in scripts:
            with self.subTest(script=script[:35]),tempfile.TemporaryDirectory() as folder:
                output=Path(folder);(output/'replays').mkdir()
                def factory(**options):
                    options['args']=[sys.executable,'-u','-c',script]
                    return subprocess.Popen(**options)
                def strategy_factory(**options):
                    options['process_factory']=factory;options['timeout']=.2
                    return StrategyBridge(**options)
                case=arena.run_case('baseline',4,8,5,5,output,strategy_factory=strategy_factory)
                self.assertEqual(case['stop_reason'],'failed')
                self.assertEqual(case['ticks'],0)
                self.assertTrue(case['game_verified'])
                self.assertFalse(case['policy_verified'])
                self.assertEqual(len(arena.load(output/case['replay_path']).transactions),2)
                self.assertIsNotNone(case['error_category'])
                result={'schema_version':2,'protocol_version':'LWS1','board':{'width':8,'height':5},
                        'seeds':[4],'max_ticks':5,
                        'strategies':{'baseline':{'path':'app/lwt_snake/strategy_baseline.lwt',
                                                'sha256':arena.digest_file(arena.STRATEGIES['baseline']),
                                                'protocol':'LWA1'}},
                        'cases':[case],'summary':arena.summary([case])}
                arena.atomic_json(output/'result.json',result)
                checked=arena.verify(output/'result.json')
                self.assertEqual((checked['cases'][0]['game_verified'],checked['cases'][0]['policy_verified']),(True,False))
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder);(output/'replays').mkdir()
            cancel=threading.Event();cancel.set()
            case=arena.run_case('baseline',4,8,5,5,output,cancel=cancel)
            self.assertEqual(case['stop_reason'],'failed')
            self.assertIsNone(case['replay_path'])
            def broken_game_factory(**options):
                def process_factory(**launch):
                    launch['args']=[sys.executable,'-u','-c',
                                    'import sys;sys.stdin.readline();print("not-a-frame",flush=True);sys.exit(7)']
                    return subprocess.Popen(**launch)
                options['process_factory']=process_factory
                return LwtSnakeBridge(**options)
            broken=arena.run_case('baseline',4,8,5,5,output,game_factory=broken_game_factory)
            self.assertEqual((broken['stop_reason'],broken['game_verified'],broken['replay_path']),
                             ('failed',False,None))
            self.assertIsNotNone(broken['error_category'])
            result['cases']=[broken];result['summary']=arena.summary([broken])
            arena.atomic_json(output/'result.json',result)
            self.assertFalse(arena.verify(output/'result.json')['cases'][0]['game_verified'])
            with patch.object(arena,'save',side_effect=OSError('disk full')):
                with self.assertRaisesRegex(OSError,'disk full'):
                    arena.run_case('baseline',4,8,5,1,output)


if __name__=='__main__':unittest.main()
