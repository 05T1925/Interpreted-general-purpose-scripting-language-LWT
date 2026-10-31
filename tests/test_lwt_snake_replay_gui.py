"""Real widgets, worker boundaries and real LWT replay/handoff processes."""
from pathlib import Path
import gc
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
try:
    import tkinter as tk
except ImportError:
    tk = None
from app.lwt_snake import replay as r
from tests.test_lwt_snake_replay import record


class ReplayTkTests(unittest.TestCase):
    def setUp(self):
        gc.collect()
        if tk is None: self.skipTest('Tkinter unavailable')
        try:
            self.root=tk.Tk(); self.root.withdraw()
        except tk.TclError as error:self.skipTest(f'Tk display unavailable: {error}')
        from app.lwt_snake.ui import LwtSnakeApp
        self.app=LwtSnakeApp(self.root,tick_ms=10000)
        self.folder=tempfile.TemporaryDirectory(prefix='对局 GUI ')
        self.path=Path(self.folder.name)/'parent 雪.json'
        self.pump(lambda:self.app.snapshot is not None and not self.app.busy)

    def tearDown(self):
        if not self.app.closing:self.app.close()
        self.app.worker.join(7)
        self.assertFalse(self.app.worker.is_alive())
        if self.app.worker.bridge.pid:self.assertIsNotNone(self.app.worker.bridge.returncode)
        self.folder.cleanup()
        self.app=None
        self.root=None
        gc.collect()

    def pump(self,condition,timeout=12):
        until=time.monotonic()+timeout
        while time.monotonic()<until:
            self.root.update()
            if condition():return
            threading.Event().wait(.002)
        self.fail(f'Tk timeout: mode={self.app.mode} busy={self.app.busy} status={self.app.status_var.get()}')

    def dialog_save(self,path):
        with patch('app.lwt_snake.ui.filedialog.asksaveasfilename',autospec=True,return_value=str(path)):
            self.app.save_button.invoke()
        self.pump(lambda:not self.app.busy and self.app.pending_save is None)

    def dialog_load(self,path):
        with patch('app.lwt_snake.ui.filedialog.askopenfilename',autospec=True,return_value=str(path)):
            self.app.load_button.invoke()

    def test_real_save_verify_step_play_takeover_branch_and_return_live(self):
        app=self.app
        app.start_button.invoke();self.pump(lambda:not app.busy)
        app.send('TURN','U');self.pump(lambda:not app.busy)
        app.pause_button.invoke();self.pump(lambda:not app.busy)
        self.dialog_save(self.path)
        original=self.path.read_bytes(); parent=r.load(self.path)
        old=app.worker
        self.dialog_load(self.path)
        self.pump(lambda:app.mode=='replay')
        self.assertTrue(old.finished.is_set());self.assertEqual(old.bridge.returncode,0)
        self.assertEqual(len(app.verified.states),len(parent.transactions))
        app.next_button.invoke();self.assertEqual(app.replay_index,1)
        app.previous_button.invoke();self.assertEqual(app.replay_index,0)
        app.speed.set('快');app.play_button.invoke()
        self.assertIsNotNone(app.play_id)
        app.play_button.invoke();self.assertIsNone(app.play_id)
        while app.replay_index<2:app.next_button.invoke()
        self.assertIn('TURN',app.position_var.get())
        app.take_button.invoke();self.pump(lambda:app.mode=='live' and not app.busy)
        self.assertEqual(app.snapshot.direction,'U')
        self.assertEqual(app.worker.recorder.snapshot().origin.prefix_count,3)
        app.pause_button.invoke();self.pump(lambda:not app.busy)
        child=Path(self.folder.name)/'branch.json'
        self.dialog_save(child)
        self.assertEqual(self.path.read_bytes(),original)
        self.assertEqual(r.load(child).transactions[:3],parent.transactions[:3])
        self.assertEqual(len(r.load(child).transactions),4)
        r.reconstruct(r.load(child))
        old=app.worker;app.live_button.invoke()
        self.pump(lambda:app.mode=='live' and not app.busy)
        self.assertEqual(app.snapshot.phase,'READY')
        self.assertTrue(old.finished.is_set());self.assertEqual(old.bridge.returncode,0)

    def test_file_error_cancel_save_and_failure_recovery(self):
        app=self.app
        before=app.worker.recorder.snapshot()
        with patch('app.lwt_snake.ui.filedialog.asksaveasfilename',autospec=True,return_value=''):
            app.save_button.invoke()
        self.assertEqual(app.worker.recorder.snapshot(),before)
        self.dialog_save(Path(self.folder.name))
        self.assertIn('错误',app.status_var.get())
        self.dialog_save(self.path)
        self.assertTrue(self.path.exists())
        bad=Path(self.folder.name)/'bad.json';bad.write_bytes(b'{}')
        self.dialog_load(bad);self.pump(lambda:app.mode=='idle')
        self.assertTrue(app.failed)
        app.live_button.invoke();self.pump(lambda:app.mode=='live' and not app.busy)
        self.assertEqual(app.snapshot.phase,'READY')

    def test_cancel_inflight_verification_second_load_and_close(self):
        app=self.app
        long=record([('TICK',())]*450)
        r.save(self.path,long)
        self.dialog_load(self.path)
        self.pump(lambda:app.mode=='loading' and app.next_worker is None and app.worker.replay_path==self.path and app.worker.bridge.pid is not None)
        old=app.worker
        app.cancel_button.invoke();self.pump(lambda:app.mode=='idle')
        self.assertTrue(old.finished.is_set());self.assertIsNotNone(old.bridge.returncode)
        self.assertIsNone(app.verified)
        short=Path(self.folder.name)/'short.json';r.save(short,record([]))
        self.dialog_load(self.path)
        self.pump(lambda:app.mode=='loading' and app.next_worker is None and app.worker.replay_path==self.path and app.worker.bridge.pid is not None)
        previous=app.worker
        self.dialog_load(short);self.pump(lambda:app.mode=='replay')
        self.assertTrue(previous.finished.is_set());self.assertIsNotNone(previous.bridge.returncode)
        self.assertEqual(len(app.verified.states),1)
        self.dialog_load(self.path)
        self.pump(lambda:app.mode=='loading' and app.next_worker is None and app.worker.replay_path==self.path and app.worker.bridge.pid is not None)
        app.close()


if __name__=='__main__':unittest.main()
