"""Replay files must be justified by fresh public LWT executions."""
from dataclasses import replace
import json
import queue
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from app.lwt_snake.bridge import GAME_SOURCE, LwtSnakeBridge
from app.lwt_snake.protocol import CommandRejected
from app.lwt_snake import replay as r

ROOT = Path(__file__).resolve().parents[1]


def record(commands, width=4, height=2, seed=4):
    recorder = r.Recorder(width,height,seed)
    bridge = LwtSnakeBridge(repository_root=ROOT,width=width,height=height,seed=seed,on_transaction=recorder.append)
    bridge.start()
    try:
        for command,args in commands:
            try: bridge.request(command,*args)
            except CommandRejected: pass
    finally: bridge.close()
    return recorder.snapshot()


class ReplayTests(unittest.TestCase):
    def test_worker_records_completed_reply_even_when_display_is_superseded(self):
        from app.lwt_snake.session import EngineWorker
        replies=queue.Queue(maxsize=16);worker=EngineWorker(ROOT,replies,1)
        worker.start();replies.get(timeout=5)
        worker.submit(1,'START');replies.get(timeout=5)
        completed=threading.Event();release=threading.Event()
        original=worker.bridge.request
        def controlled(command,*args):
            result=original(command,*args)
            if command=='TURN':
                completed.set()
                if not release.wait(5):raise TimeoutError('test release missing')
            return result
        try:
            with patch.object(worker.bridge,'request',side_effect=controlled):
                worker.submit(2,'TURN','U');self.assertTrue(completed.wait(5))
                worker.submit(3,'RESET',replace=True);release.set()
                old=replies.get(timeout=5);new=replies.get(timeout=5)
                self.assertEqual((old.request_id,new.request_id),(2,3))
                with tempfile.TemporaryDirectory() as folder:
                    path=Path(folder)/'all.json';worker.submit(4,'SAVE',path)
                    reply=replies.get(timeout=5)
                    self.assertEqual([t.request.split('|')[2] for t in reply.record.transactions],['INIT','START','TURN','RESET'])
                    r.reconstruct(r.load(path))
        finally:
            release.set();worker.stop();worker.join(7)
            self.assertFalse(worker.is_alive());self.assertEqual(worker.bridge.returncode,0)

    def test_real_record_verify_rules_rejections_reset_and_win(self):
        commands=[]
        for line in (ROOT/'app/lwt_snake/rules.commands').read_text().splitlines()[1:]:
            fields=line.split('|'); cmd=fields[2]
            if cmd in {'WHAT','QUIT'}: continue
            commands.append((cmd,(fields[3],) if cmd=='TURN' else ()))
        replay=record(commands)
        self.assertTrue(any('|ERR|' in tx.response for tx in replay.transactions))
        verified=r.reconstruct(replay)
        self.assertEqual(len(verified.states),len(replay.transactions))
        self.assertEqual(verified.states[-1].phase,'GAME_OVER')
        rejected_index=next(i for i,tx in enumerate(replay.transactions,1) if '|ERR|' in tx.response)
        resumed=r.reconstruct(replay,prefix=rejected_index,keep=True)
        try:
            state=resumed.bridge.request('TICK')
            self.assertEqual(state.sequence,rejected_index+1)
            r.reconstruct(resumed.recorder.snapshot())
        finally:resumed.bridge.close()
        paused=record([('START',()),('TURN',('U',)),('PAUSE',()),('RESUME',()),('TICK',())],8,5,1)
        states=r.reconstruct(paused).states
        self.assertEqual((states[2].direction,states[3].direction,states[-1].snake[0]),('U','R',(5,2)))
        win=record([('START',()),('TICK',())],4,1,1)
        self.assertEqual(r.reconstruct(win).states[-1].phase,'WON')
        with self.assertRaisesRegex(r.VerificationError,'terminal'):r.reconstruct(win,keep=True)

    def test_pending_turn_rng_prefix_takeover_and_independent_branch(self):
        recorder=r.Recorder(4,2,4)
        original=LwtSnakeBridge(repository_root=ROOT,width=4,height=2,seed=4,on_transaction=recorder.append)
        original.start(); rebuilt=None
        try:
            for cmd,args in [('START',()),('TICK',()),('TURN',('U',)),('TICK',()),('TURN',('L',)),('TICK',()),('TICK',()),('TICK',()),('TURN',('D',))]: original.request(cmd,*args)
            parent=recorder.snapshot()
            self.assertEqual(r.reconstruct(parent).states[-1].score,20)
            result=r.reconstruct(parent,keep=True)
            rebuilt=result.bridge
            for cmd,args in [('TICK',()),('PAUSE',()),('RESUME',())]:
                a=original.request(cmd,*args); b=rebuilt.request(cmd,*args)
                self.assertEqual(a,b)
                self.assertEqual(original.last_response,rebuilt.last_response)
            child=result.recorder.snapshot()
            self.assertEqual(child.transactions[:len(parent.transactions)],parent.transactions)
            self.assertEqual(child.origin.prefix_count,len(parent.transactions))
            self.assertEqual(len(parent.transactions),10)
            r.reconstruct(child)
            alternate=r.reconstruct(parent,keep=True)
            try:
                alternate.bridge.request('TURN','R'); alternate.bridge.request('TICK')
                branch=alternate.recorder.snapshot()
                r.reconstruct(branch)
                self.assertNotEqual(branch.transactions[-1].response,child.transactions[-1].response)
            finally: alternate.bridge.close()
        finally:
            original.close()
            if rebuilt: rebuilt.close()

    def test_file_contract_duplicates_bounds_types_and_atomic_failure(self):
        replay=record([])
        with tempfile.TemporaryDirectory(prefix='回放 雪 ') as folder:
            path=Path(folder)/'对局 file.json'
            r.save(path,replay); before=path.read_bytes()
            self.assertEqual(r.load(path),replay)
            with patch('app.lwt_snake.replay.os.replace',autospec=True,side_effect=PermissionError('controlled denied')):
                with self.assertRaises(OSError): r.save(path,replay)
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(list(Path(folder).iterdir()),[path])
            bad=[b'',b'{',b'{"a":1,"a":2}',b'{"x":NaN}',b'\xff',b'{"x":123456789012}']
            for raw in bad:
                path.write_bytes(raw)
                with self.subTest(raw=raw),self.assertRaises(r.ReplayError): r.load(path)
            for key,value in [('schema_version',True),('protocol_version','LWS2'),('interruption',False),('origin',{'parent_sha256':'0'*64,'prefix_count':True})]:
                data=r.document(replay);data[key]=value
                with self.subTest(key=key),self.assertRaises(r.ReplayError): r.decode_document(data)
            data=r.document(replay);data['source_path']='evil.lwt'
            with self.assertRaises(r.ReplayError):r.decode_document(data)
            path.write_bytes(before)
            with patch('app.lwt_snake.replay.MAX_FILE_BYTES',10):
                with self.assertRaises(r.ReplayError):r.load(path)
            with path.open('wb') as stream:stream.truncate(r.MAX_FILE_BYTES+1)
            with self.assertRaises(r.ReplayError):r.load(path)

    def test_hash_normalization_and_real_divergence_not_self_report(self):
        self.assertEqual(r.source_digest(b'a\nb\n'),r.source_digest(b'\xef\xbb\xbfa\r\nb\r'))
        self.assertNotEqual(r.source_digest(b'\xef\xbb\xbf\xef\xbb\xbfa'),r.source_digest(b'a'))
        parent=record([('START',()),('TICK',())])
        data=r.document(parent);data['transactions'][2]['response']=data['transactions'][2]['response'].replace('|10|R|','|20|R|')
        altered=r.decode_document(data)
        with self.assertRaisesRegex(r.VerificationError,'transaction 3.*field'):
            r.reconstruct(altered)
        data=r.document(parent); data['settings']['seed']=9; data['transactions'][0]['request']=data['transactions'][0]['request'].replace('0000000004','0000000009')
        with self.assertRaises(r.VerificationError):r.reconstruct(r.decode_document(data))
        data=r.document(parent);del data['transactions'][1]
        with self.assertRaises(r.ReplayError):r.decode_document(data)
        data=r.document(parent);data['transactions'][1]['request']='LWS1|000002|TICK|-|-|-'
        with self.assertRaises(r.VerificationError):r.reconstruct(r.decode_document(data))

    def test_cancel_total_deadline_and_recording_limit(self):
        replay=record([('START',()),('TICK',())])
        owned=[]
        class Tracked(LwtSnakeBridge):
            def __init__(self,**kwargs):super().__init__(**kwargs);owned.append(self)
        cancel=threading.Event();cancel.set()
        with patch('app.lwt_snake.replay.LwtSnakeBridge',Tracked):
            with self.assertRaisesRegex(r.VerificationError,'cancel'):r.reconstruct(replay,cancel=cancel)
            with self.assertRaises(r.VerificationError):r.reconstruct(replay,total_timeout=.00001)
            with self.assertRaisesRegex(r.VerificationError,'deadline'):
                r.reconstruct(replay,total_timeout=.15,progress=lambda n,total:threading.Event().wait(.25))
            def interrupt(n,total):raise KeyboardInterrupt()
            with self.assertRaisesRegex(r.VerificationError,'cancel'):r.reconstruct(replay,progress=interrupt)
            self.assertTrue(any(bridge.pid is not None for bridge in owned))
        for bridge in owned:
            self.assertTrue(bridge._closed)
            if bridge.pid:self.assertIsNotNone(bridge.returncode)
        with patch('app.lwt_snake.replay.MAX_TRANSACTIONS',2):
            recorder=r.Recorder();recorder.append('a','b');recorder.append('c','d');recorder.append('e','f')
            self.assertEqual(len(recorder.snapshot().transactions),2)
            self.assertIn('第 2 条',recorder.snapshot().interruption)

    def test_cli_success_contract_and_divergence_exit_codes(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'game.json'; replay=record([])
            r.save(path,replay)
            command=[sys.executable,'-m','app.lwt_snake.replay','--verify',str(path)]
            result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=15)
            self.assertEqual((result.returncode,result.stdout,result.stderr),(0,b'Verified 1 transactions.\n',b''))
            data=r.document(replay);data['transactions'][0]['response']=data['transactions'][0]['response'].replace('|0|R|','|10|R|')
            path.write_text(json.dumps(data),encoding='utf-8')
            result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=15)
            self.assertEqual(result.returncode,3);self.assertIn(b'transaction 1',result.stderr)
            path.write_bytes(b'{}')
            result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=15)
            self.assertEqual(result.returncode,2)


if __name__=='__main__':unittest.main()
