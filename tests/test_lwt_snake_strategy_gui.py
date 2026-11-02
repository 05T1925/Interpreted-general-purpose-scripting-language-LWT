"""Real Tk controls, real strategy/game children, synthetic events (not manual QA)."""
from pathlib import Path
import gc
import queue
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
try:
    import tkinter as tk
except ImportError:
    tk=None
from app.lwt_snake.strategy import StrategyReply, Advice, StrategyWorker, StrategyBridge
from app.lwt_snake import replay as r


class StrategyTkTests(unittest.TestCase):
    def setUp(self):
        gc.collect()
        if tk is None:self.skipTest('Tkinter unavailable')
        try:self.root=tk.Tk();self.root.withdraw()
        except tk.TclError as error:self.skipTest(f'Tk display unavailable: {error}')
        from app.lwt_snake.ui import LwtSnakeApp
        self.app=LwtSnakeApp(self.root,tick_ms=10000)
        self.owners=[]
        self.pump(lambda:not self.app.busy)
        self.app.start_button.invoke();self.pump(lambda:not self.app.busy)

    def tearDown(self):
        if not self.app.closing:self.app.close()
        self.app.worker.join(7)
        self.assertFalse(self.app.worker.is_alive())
        owners=self.owners+[self.app.strategy_worker]
        for owner in owners:
            if owner:
                owner.stop();owner.join(7)
                self.assertFalse(owner.is_alive())
                if owner.bridge.pid:self.assertIsNotNone(owner.bridge.returncode)
        self.app=None;self.root=None;gc.collect()

    def pump(self,condition,timeout=12):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            self.root.update()
            if condition():return
            threading.Event().wait(.002)
        self.fail(f'Tk timeout: {self.app.strategy_var.get()} / {self.app.status_var.get()}')

    def ticks(self):
        return sum('|TICK|' in t.request for t in self.app.worker.recorder.snapshot().transactions)

    def enable(self,steps=2):
        self.app.tick_ms=40
        before=self.ticks()
        self.app.auto_button.invoke()
        self.pump(lambda:self.ticks()>=before+steps)
        self.assertTrue(self.app.auto)
        self.assertIsNone(self.app.tick_id)
        self.assertIsNone(self.app.clock.deadline)
        return self.app.strategy_worker

    def test_hint_is_readonly_auto_serial_events_and_manual_takeover(self):
        app=self.app
        before=app.worker.recorder.snapshot()
        app.hint_button.invoke();self.pump(lambda:app.advice is not None)
        self.assertEqual(app.worker.recorder.snapshot(),before)
        self.assertIn('FOOD',app.strategy_var.get())
        old=app.strategy_worker;self.owners.append(old)
        app.hint_button.invoke();self.pump(lambda:old.finished.is_set())
        worker=self.enable(5)
        pid=worker.bridge.pid
        self.pump(lambda:not app.busy)
        self.assertEqual(worker.bridge.pid,pid)
        self.assertLessEqual(worker.commands.qsize(),1)
        commands=[t.request.split('|')[2] for t in app.worker.recorder.snapshot().transactions]
        self.assertIn('TURN',commands)
        # Every automatic TURN is followed by a TICK; there is no manual timer.
        for i,command in enumerate(commands[:-1]):
            if command=='TURN':self.assertEqual(commands[i+1],'TICK')
        self.root.deiconify();self.root.update();app.pause_button.focus_force();self.root.update()
        app.pause_button.event_generate('<KeyPress>',keysym='Up',when='now')
        self.pump(lambda:not app.auto and not app.busy)
        self.assertFalse(app.strategy_busy)
        self.pump(lambda:worker.finished.is_set())
        self.assertIsNotNone(worker.bridge.returncode)

    def test_pause_reset_focus_replay_takeover_and_close_cancel_old_strategy(self):
        app=self.app
        first=self.enable();self.owners.append(first)
        self.pump(lambda:not app.busy)
        app.pause_button.invoke();self.pump(lambda:not app.busy and app.snapshot.phase=='PAUSED')
        self.assertFalse(app.auto);self.pump(lambda:first.finished.is_set())
        app.start_button.invoke();self.pump(lambda:not app.busy)
        second=self.enable();self.owners.append(second)
        app.reset_button.invoke();self.pump(lambda:not app.busy and app.snapshot.phase=='READY')
        self.assertFalse(app.auto);self.pump(lambda:second.finished.is_set())
        app.start_button.invoke();self.pump(lambda:not app.busy)
        self.root.deiconify();self.root.update();app.start_button.focus_force();self.root.update()
        third=self.enable();self.owners.append(third)
        other=tk.Toplevel(self.root)
        self.pump(lambda:bool(other.winfo_ismapped()));other.focus_force()
        self.pump(lambda:not app.busy and app.snapshot.phase=='PAUSED')
        self.assertFalse(app.auto);self.pump(lambda:third.finished.is_set());other.destroy()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'auto.json';r.save(path,app.worker.recorder.snapshot())
            app.load_path(path);self.pump(lambda:app.mode=='replay')
            self.assertFalse(app.auto)
            app.next_button.invoke()  # START prefix
            app.take_button.invoke();self.pump(lambda:app.mode=='live' and not app.busy)
            self.assertFalse(app.auto)
            self.assertEqual(app.snapshot.phase,'RUNNING')
            fourth=self.enable(1);self.owners.append(fourth)
            app.close()
            fourth.join(7)
            self.assertFalse(fourth.is_alive())
            self.assertIsNone(app.auto_id)

    def test_stale_response_failure_recovery_and_auto_save_verification(self):
        app=self.app
        # Controlled failure only replaces the child, never the Tk controls.
        def failing_worker(root,replies,generation):
            def factory(**options):return StrategyBridge(**options,python_executable=str(root/'absent-python'))
            return StrategyWorker(root,replies,generation,factory=factory)
        with patch('app.lwt_snake.ui.StrategyWorker',side_effect=failing_worker,autospec=True):
            app.auto_button.invoke()
            self.pump(lambda:app.strategy_hold)
        old=app.strategy_worker;self.owners.append(old)
        self.assertFalse(app.auto)
        self.assertIsNone(app.tick_id)
        self.assertIn('停止',app.strategy_var.get())
        self.assertEqual(self.ticks(),0)
        self.pump(lambda:old.finished.is_set())
        worker=self.enable(4);self.owners.append(worker)
        with tempfile.TemporaryDirectory(prefix='自动 GUI ') as folder:
            path=Path(folder)/'replay 雪.json'
            with patch('app.lwt_snake.ui.filedialog.asksaveasfilename',autospec=True,return_value=str(path)):
                app.save_button.invoke()
            self.pump(lambda:not app.busy and app.pending_save is None and path.exists())
            self.assertFalse(app.auto)
            self.assertEqual(app.snapshot.phase,'PAUSED')
            self.pump(lambda:worker.finished.is_set())
            state=app.snapshot;epoch=app.strategy_generation
            app.strategy_replies.put_nowait(StrategyReply(epoch-1,state,Advice('U','FOOD')))
            self.root.update();app.poll_strategy()
            self.assertIsNone(app.advice)
            app.load_path(path);self.pump(lambda:app.mode=='replay')
            self.assertGreaterEqual(len(app.verified.states),6)
            self.assertFalse(app.auto)

    def test_cancel_computed_but_undisplayed_hint_reset_and_mode_switches(self):
        app=self.app
        computed=threading.Event();release=threading.Event()
        original=StrategyBridge.query
        def delayed(bridge,state,cancel=None):
            result=original(bridge,state,cancel)
            computed.set()
            if not release.wait(5):raise RuntimeError('missing test release')
            return result
        with patch.object(StrategyBridge,'query',autospec=True,side_effect=delayed):
            try:
                app.hint_button.invoke();self.pump(computed.is_set)
                old=app.strategy_worker;self.owners.append(old)
                app.reset_button.invoke()
                self.pump(lambda:not app.busy and app.snapshot.phase=='READY')
                self.assertIsNone(app.advice)
            finally:release.set()
            self.pump(lambda:old.finished.is_set())
        app.start_button.invoke();self.pump(lambda:not app.busy)
        for _ in range(3):
            worker=self.enable(1);self.owners.append(worker)
            app.auto_button.invoke()
            self.pump(lambda:not app.busy and worker.finished.is_set())
            count=self.ticks()
            self.assertFalse(app.auto)
            self.assertIsNone(app.auto_id)
            done=threading.Event();self.root.after(180,done.set)
            self.pump(done.is_set)
            self.assertEqual(self.ticks(),count)  # manual deadline is 10 seconds


if __name__=='__main__':unittest.main()
