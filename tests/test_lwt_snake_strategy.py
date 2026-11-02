"""Public CLI decisions and bounded protocol/child lifecycle regressions."""
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import queue
from dataclasses import replace
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'app/lwt_snake/strategy.lwt'
from app.lwt_snake.bridge import LwtSnakeBridge, BridgeFailure
from app.lwt_snake.protocol import GameSnapshot, ProtocolError
from app.lwt_snake.strategy import StrategyBridge, StrategyWorker, encode_snapshot, parse_advice
from app.lwt_snake import replay as r

STATE=GameSnapshot(2,'RUNNING',0,'R',(3,0),((2,0),(1,0),(0,0)),4,1)


def frame(sequence=1, width=4, height=1, direction='R', food=(3,0),
          body=((2,0),(1,0),(0,0))):
    return (f'LWA1|{sequence:06d}|{width}|{height}|{direction}|{food[0]}|{food[1]}|{len(body)}|'
            + ';'.join(f'{x},{y}' for x,y in body)).encode('ascii')


class StrategyCliTests(unittest.TestCase):
    def run_frames(self, frames):
        result = subprocess.run([sys.executable,'-u','-m','lwt',str(SOURCE)],
                                cwd=ROOT,input=b'\n'.join(frames)+b'\n',
                                capture_output=True,timeout=20,shell=False)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(result.stderr,b'')
        return result.stdout.split(b'\n')[:-1]

    def test_deterministic_food_tie_wall_tail_pending_and_trapped(self):
        cases = [
            (frame(),b'MOVE|R|FOOD'),
            (frame(width=5,height=3,food=(3,0),body=((2,1),(1,1),(0,1))),b'MOVE|U|FOOD'),
            (frame(height=2,food=(0,0),body=((3,1),(2,1),(1,1))),b'MOVE|U|FOOD'),
            (frame(height=2,direction='L',food=(3,1),body=((1,0),(1,1),(0,1),(0,0))),b'MOVE|L|SPACE'),
            (frame(height=2,direction='U',food=(3,1),body=((2,1),(1,1),(0,1))),b'MOVE|R|FOOD'),
            (frame(height=3,direction='U',food=(3,2),body=((0,0),(1,0),(1,1),(0,1),(0,2))),b'NONE|-|TRAPPED'),
        ]
        for request,expected in cases:
            with self.subTest(request=request):
                second=request.replace(b'000001',b'000002',1)
                self.assertEqual(self.run_frames([request,second]),
                                 [b'LWA1|000001|'+expected,b'LWA1|000002|'+expected])

    def test_bad_frames_do_not_consume_sequence_and_eof_is_quiet(self):
        good=frame()
        bad=[good.replace(b'LWA1',b'LWA2'),good.replace(b'000001',b'000003'),
             good+b'|extra',good.replace(b'|R|',b'|\xc3\xa9|'),b'x'*4097,
             frame(food=(0,0)),good.replace(b'|3|2,0',b'|4|2,0')]
        lines=self.run_frames(bad+[good])
        self.assertEqual([line.split(b'|')[-1] for line in lines[:-1]],
                         [b'BAD_FRAME',b'BAD_SEQUENCE',b'BAD_FRAME',b'BAD_FRAME',b'BAD_FRAME',b'BAD_SNAPSHOT',b'BAD_SNAPSHOT'])
        self.assertEqual(lines[-1],b'LWA1|000001|MOVE|R|FOOD')
        result=subprocess.run([sys.executable,'-u','-m','lwt',str(SOURCE)],cwd=ROOT,
                              input=b'',capture_output=True,timeout=5)
        self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'',b''))

    def test_space_tie_unreachable_food_and_largest_board(self):
        # Tail square seals the head from food on the predicted static grid.
        requests=[frame(height=2,direction='L',food=(3,1),body=((1,0),(1,1),(0,1),(0,0))),
                  frame(sequence=2,width=24,height=18,food=(13,8),body=((12,9),(11,9),(10,9)))]
        self.assertEqual(self.run_frames(requests),[b'LWA1|000001|MOVE|L|SPACE',b'LWA1|000002|MOVE|U|FOOD'])
        # A one-cell-wide loop leaves only the vacating tail; food on tail is
        # rejected, rather than pretending that a growing tail would leave.
        self.assertEqual(self.run_frames([frame(height=2,direction='L',food=(0,0),
                                               body=((1,0),(1,1),(0,1),(0,0)))]),
                         [b'LWA1|ERR|000001|BAD_SNAPSHOT'])
        # U and R each reach four cells; a body barrier isolates the food.
        # Fixed U,R,D,L order resolves the SPACE tie as U.
        self.assertEqual(self.run_frames([frame(height=3,direction='U',food=(0,1),
                  body=((2,1),(2,2),(1,2),(1,1),(1,0),(0,0)))]),
                  [b'LWA1|000001|MOVE|U|SPACE'])
        dense=tuple((x,y) for y in range(18) for x in (range(24) if y%2==0 else range(23,-1,-1)))
        self.assertEqual(self.run_frames([frame(width=24,height=18,direction='U',food=dense[-1],body=dense[:-1])]),
                         [b'LWA1|000001|NONE|-|TRAPPED'])

    def test_invalid_utf8_is_real_input_diagnostic(self):
        result=subprocess.run([sys.executable,'-u','-m','lwt',str(SOURCE)],cwd=ROOT,
                              input=b'\xff\n',capture_output=True,timeout=5)
        self.assertEqual(result.returncode,3)
        self.assertIn(b'RuntimeError',result.stderr)
        self.assertEqual(result.stdout,b'')


class StrategyBridgeTests(unittest.TestCase):
    def fault(self,script,timeout=.3):
        def factory(**options):
            options['args']=[sys.executable,'-u','-c',script]
            return subprocess.Popen(**options)
        bridge=StrategyBridge(repository_root=ROOT,process_factory=factory,timeout=timeout)
        self.addCleanup(bridge.close)
        bridge.start()
        return bridge

    def test_malformed_timeout_extra_output_and_stderr_are_reaped(self):
        valid=b'LWA1|000001|MOVE|R|FOOD\n'
        outputs=[b'wrong\n',valid.replace(b'000001',b'000002'),b'\xff\n',b'x'*130,
                 b'partial',valid+valid,valid.replace(b'|R|',b'|L|')]
        scripts=[f'import sys,time;sys.stdin.buffer.readline();sys.stdout.buffer.write({data!r});sys.stdout.flush();time.sleep(10)' for data in outputs]
        scripts+=['import time;time.sleep(10)',
                  "import sys;sys.stdin.readline();sys.stderr.write('failure'*20000);sys.stderr.flush();sys.exit(7)"]
        for script in scripts:
            with self.subTest(script=script[:90]):
                bridge=self.fault(script)
                # Extra stdout may race the first completed response, but must
                # be rejected before another request or normal EOF cleanup.
                with self.assertRaises(BridgeFailure):
                    bridge.query(STATE);bridge.query(STATE);bridge.close()
                bridge.close()
                self.assertIsNotNone(bridge.returncode)
                self.assertFalse(bridge._stdout_thread.is_alive())
                self.assertFalse(bridge._stderr_thread.is_alive())
                self.assertLessEqual(len(bridge._stderr_tail),8192)

    def test_cancel_start_failure_retry_and_unicode_path(self):
        bridge=self.fault('import time;time.sleep(10)',timeout=5)
        replies=queue.Queue();cancel=threading.Event()
        def query():
            try:bridge.query(STATE,cancel)
            except BridgeFailure as error:replies.put(str(error))
        worker=threading.Thread(target=query);worker.start();cancel.set()
        worker.join(4)
        self.assertFalse(worker.is_alive());self.assertIn('cancelled',replies.get_nowait())
        self.assertIsNotNone(bridge.returncode);bridge.close()
        missing=StrategyBridge(repository_root=ROOT,python_executable=str(ROOT/'absent-python'))
        with self.assertRaises(BridgeFailure):missing.start()
        missing.close()
        with tempfile.TemporaryDirectory(prefix='策略 雪 ') as folder:
            source=Path(folder)/'strategy 副本.lwt';source.write_bytes(SOURCE.read_bytes())
            retry=StrategyBridge(repository_root=ROOT,source_path=source)
            retry.start()
            try:
                pid=retry.pid
                for _ in range(3):self.assertEqual(retry.query(STATE).direction,'R')
                self.assertEqual(retry.pid,pid)
            finally:retry.close()
            self.assertEqual(retry.returncode,0)

    def test_snapshot_and_reason_validation_does_not_choose_a_fallback(self):
        for state in (replace(STATE,phase='PAUSED'),replace(STATE,food=(0,0)),replace(STATE,width=25)):
            with self.assertRaises(ProtocolError):encode_snapshot(state,1)
        for output in (b'LWA1|000001|NONE|U|TRAPPED',b'LWA1|000001|MOVE|U|TRAPPED',
                       b'LWA1|000001|MOVE|L|FOOD',b'LWA1|ERR|000001|BAD_SNAPSHOT'):
            with self.assertRaises(ProtocolError):parse_advice(output,1,STATE)

    def test_auto_record_fresh_cli_verification_and_prefix_branch(self):
        # Query a real queued TURN before TICK: DIR is effective, not inferred
        # from old body geometry. The returned R must be accepted and grow.
        pending=LwtSnakeBridge(repository_root=ROOT,width=4,height=2,seed=4)
        chooser=StrategyBridge(repository_root=ROOT)
        pending.start();chooser.start()
        try:
            pending.request('START');queued=pending.request('TURN','U')
            advice=chooser.query(queued)
            self.assertEqual(advice.direction,'R')
            pending.request('TURN',advice.direction)
            grown=pending.request('TICK')
            self.assertEqual((grown.score,len(grown.snake),grown.phase),(10,4,'RUNNING'))
        finally:chooser.close();pending.close()
        recorder=r.Recorder(8,5,4)
        game=LwtSnakeBridge(repository_root=ROOT,width=8,height=5,seed=4,on_transaction=recorder.append)
        strategy=StrategyBridge(repository_root=ROOT)
        game.start();strategy.start()
        try:
            state=game.request('START');pid=strategy.pid
            for _ in range(18):
                advice=strategy.query(state)
                self.assertIsNotNone(advice.direction)
                if advice.direction!=state.direction:state=game.request('TURN',advice.direction)
                state=game.request('TICK')
                self.assertEqual(state.phase,'RUNNING')
                self.assertEqual(strategy.pid,pid)
            parent=recorder.snapshot()
        finally:strategy.close();game.close()
        self.assertIsNotNone(game.returncode);self.assertIsNotNone(strategy.returncode)
        with tempfile.TemporaryDirectory(prefix='自动局 ') as folder:
            path=Path(folder)/'parent.json';r.save(path,parent)
            result=subprocess.run([sys.executable,'-m','app.lwt_snake.replay','--verify',str(path)],
                                  cwd=ROOT,capture_output=True,timeout=15)
            self.assertEqual((result.returncode,result.stdout,result.stderr),
                             (0,f'Verified {len(parent.transactions)} transactions.\n'.encode(),b''))
            # INIT + START is RUNNING; rebuild hidden RNG/pending turn through
            # real commands, then explicitly choose a different manual suffix.
            branch=r.reconstruct(parent,prefix=2,keep=True)
            try:
                branch.bridge.request('TURN','D');branch.bridge.request('TICK')
                child=branch.recorder.snapshot()
            finally:branch.bridge.close()
            self.assertEqual(child.transactions[:2],parent.transactions[:2])
            self.assertNotEqual(child.transactions[2:],parent.transactions[2:len(child.transactions)])
            r.reconstruct(child);r.reconstruct(parent)


if __name__=='__main__':unittest.main()
