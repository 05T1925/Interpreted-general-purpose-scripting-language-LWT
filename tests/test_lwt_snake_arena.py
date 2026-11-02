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
            outputs=[]
            for workers in (1,2,4):
                directory=Path(folder)/str(workers)
                result=self.cli('--seeds','4,7,11','--max-ticks','12','--workers',workers,'--output',directory)
                self.assertEqual(result.returncode,0,result.stderr)
                verify=self.cli('--verify',directory/'result.json')
                self.assertEqual(verify.returncode,0,verify.stderr)
                self.assertIn(b'Verified 6 matches.',verify.stdout)
                data=(directory/'result.json').read_bytes()
                outputs.append(data)
                parsed=json.loads(data)
                self.assertEqual(len(parsed['cases']),6)
                self.assertTrue(all(case['verified'] for case in parsed['cases']))
                for case in parsed['cases']:
                    self.assertEqual(case['ticks'],12)
                    self.assertEqual(case['stop_reason'],'limit')
            self.assertEqual(outputs[0],outputs[1])
            self.assertEqual(outputs[1],outputs[2])

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
                self.assertTrue(case['verified'])
                self.assertEqual(len(arena.load(output/case['replay_path']).transactions),2)
                self.assertIsNotNone(case['error_category'])
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
            self.assertEqual((broken['stop_reason'],broken['verified'],broken['replay_path']),
                             ('failed',False,None))
            self.assertIsNotNone(broken['error_category'])
            with patch.object(arena,'save',side_effect=OSError('disk full')):
                with self.assertRaisesRegex(OSError,'disk full'):
                    arena.run_case('baseline',4,8,5,1,output)


if __name__=='__main__':unittest.main()
