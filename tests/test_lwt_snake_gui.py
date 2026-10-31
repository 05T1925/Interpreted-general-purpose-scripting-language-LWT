"""Real Tk controls/events with real background LWT subprocesses."""
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
try:
    import tkinter as tk
except ImportError:
    tk = None

from app.lwt_snake.bridge import GAME_SOURCE


class LwtSnakeTkTests(unittest.TestCase):
    def setUp(self):
        if tk is None: self.skipTest('Tkinter unavailable')
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except tk.TclError as error: self.skipTest(f'Tk display unavailable: {error}')
        from app.lwt_snake.ui import LwtSnakeApp
        self.app_class = LwtSnakeApp
        self.app = None

    def tearDown(self):
        if self.app:
            if not self.app.closing: self.app.close()
            self.app.worker.join(timeout=6)
            self.assertFalse(self.app.worker.is_alive())
            self.assertIsNotNone(self.app.worker.bridge.returncode)
        else: self.root.destroy()

    def pump(self, predicate, timeout=10):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            self.root.update()
            if predicate(): return
            threading.Event().wait(0.002)
        self.fail('Tk event-loop condition timed out')

    def test_real_buttons_keys_focus_reset_and_close(self):
        self.app = app = self.app_class(self.root, tick_ms=10000)
        self.pump(lambda: app.snapshot is not None and not app.busy)
        self.assertEqual(app.snapshot.phase, 'READY')
        self.root.deiconify(); self.root.update()
        app.start_button.invoke()
        self.pump(lambda: not app.busy)
        self.assertEqual(app.snapshot.phase, 'RUNNING')
        app.pause_button.focus_force()
        self.root.update()
        app.pause_button.event_generate('<KeyPress>', keysym='Up', when='now')
        self.pump(lambda: not app.busy and app.snapshot.direction == 'U')
        app.pause_button.invoke()
        self.pump(lambda: not app.busy)
        self.assertEqual(app.snapshot.phase, 'PAUSED')
        self.assertIsNone(app.tick_id)
        app.start_button.invoke()
        self.pump(lambda: not app.busy)
        other = tk.Toplevel(self.root)
        # Mapping must complete before Windows accepts focus_force on a new window.
        self.pump(lambda: bool(other.winfo_ismapped()))
        other.focus_force()
        self.pump(lambda: self.root.focus_displayof() is not None and self.root.focus_displayof().winfo_toplevel() is other)
        self.assertIs(self.root.focus_displayof().winfo_toplevel(), other)
        self.root.event_generate('<FocusOut>', when='now')
        self.pump(lambda: not app.busy and app.snapshot.phase == 'PAUSED')
        other.destroy()
        app.reset_button.invoke()
        self.pump(lambda: not app.busy)
        self.assertEqual((app.snapshot.phase, app.snapshot.score), ('READY', 0))
        app.close()
        self.assertIsNone(app.poll_id)
        self.assertIsNone(app.tick_id)

    def test_continuous_turn_responses_cannot_starve_real_lwt_ticks(self):
        self.app = app = self.app_class(self.root, tick_ms=250)
        self.pump(lambda: app.snapshot is not None and not app.busy)
        self.root.deiconify();self.root.update();app.canvas.focus_force();self.root.update()
        for key in ('Right','Left'):
            app.reset_button.invoke();self.pump(lambda:not app.busy)
            app.start_button.invoke();self.pump(lambda:not app.busy)
            original = app.snapshot.snake[0]
            start_count=len(app.worker.recorder.snapshot().transactions)
            until = time.monotonic() + 1.15
            next_turn = 0.0
            while time.monotonic() < until:
                self.root.update()
                if not app.busy and time.monotonic() >= next_turn:
                    app.canvas.event_generate('<KeyPress>',keysym=key,when='now')
                    next_turn = time.monotonic() + 0.04
                threading.Event().wait(0.002)
            self.pump(lambda: not app.busy)
            transactions=app.worker.recorder.snapshot().transactions[start_count:]
            self.assertGreater(sum('|TURN|' in tx.request for tx in transactions),5)
            if key=='Left':self.assertGreater(sum('|ERR|' in tx.response for tx in transactions),5)
            self.assertNotEqual(app.snapshot.snake[0], original)

    def test_tick_timer_and_reset_discard_old_reply(self):
        self.app = app = self.app_class(self.root, tick_ms=20)
        self.pump(lambda: app.snapshot is not None and not app.busy)
        app.start_button.invoke()
        self.pump(lambda: app.snapshot.sequence >= 5)
        self.assertEqual(app.worker.commands.maxsize, 1)
        app.reset_button.invoke()
        self.pump(lambda: not app.busy and app.snapshot.phase == 'READY')
        sequence = app.snapshot.sequence
        self.root.update()
        self.assertEqual(app.snapshot.sequence, sequence)
        self.assertIsNone(app.tick_id)

    def test_due_tick_waits_for_busy_turn_without_catchup_burst(self):
        self.app = app = self.app_class(self.root, tick_ms=250)
        self.pump(lambda:app.snapshot is not None and not app.busy)
        app.start_button.invoke();self.pump(lambda:not app.busy)
        completed=threading.Event();release=threading.Event()
        original=app.worker.bridge.request
        def blocked(command,*args):
            result=original(command,*args)
            if command=='TURN':
                completed.set()
                if not release.wait(4):raise TimeoutError('controlled release missing')
            return result
        try:
            with patch.object(app.worker.bridge,'request',side_effect=blocked):
                app.send('TURN','U');self.pump(completed.is_set)
                elapsed=[];self.root.after(400,lambda:elapsed.append(True));self.pump(lambda:bool(elapsed))
                self.assertTrue(app.busy)
                self.assertTrue(app.clock.due(time.monotonic()))
                self.assertEqual(sum('|TICK|' in t.request for t in app.worker.recorder.snapshot().transactions),0)
                release.set()
                self.pump(lambda:not app.busy and sum('|TICK|' in t.request for t in app.worker.recorder.snapshot().transactions)==1)
                app.pause_button.invoke();self.pump(lambda:not app.busy)
                self.assertIsNone(app.clock.deadline)
        finally:release.set()

    def test_engine_failure_and_real_retry_with_unicode_source(self):
        with tempfile.TemporaryDirectory(prefix='GUI 雪 ') as folder:
            source = Path(folder)/'规则 game.lwt'
            source.write_text('fail("controlled engine failure");', encoding='utf-8')
            self.app = app = self.app_class(self.root, source=source)
            self.pump(lambda: app.failed and app.worker.finished.is_set())
            self.assertIn('引擎错误', app.status_var.get())
            source.write_bytes(GAME_SOURCE.read_bytes())
            app.retry_button.invoke()
            self.pump(lambda: app.snapshot is not None and not app.busy)
            self.assertEqual(app.snapshot.phase, 'READY')

    def test_space_wasd_r_and_close_during_request(self):
        self.app = app = self.app_class(self.root, tick_ms=10000)
        self.pump(lambda: app.snapshot is not None and not app.busy)
        self.root.deiconify(); self.root.update(); app.canvas.focus_force(); self.root.update()
        app.canvas.event_generate('<KeyPress>', keysym='space', when='now')
        self.pump(lambda: not app.busy and app.snapshot.phase == 'RUNNING')
        for key, direction in [('w','U'),('a','L'),('s','D'),('d','R')]:
            app.canvas.event_generate('<KeyPress>', keysym=key, when='now')
            self.pump(lambda: not app.busy and app.snapshot.direction == direction)
        app.canvas.event_generate('<KeyPress>', keysym='space', when='now')
        self.pump(lambda: not app.busy and app.snapshot.phase == 'PAUSED')
        app.canvas.event_generate('<KeyPress>', keysym='r', when='now')
        self.pump(lambda: not app.busy and app.snapshot.phase == 'READY')
        app.start_button.invoke()
        self.assertTrue(app.busy)
        app.close()


if __name__ == '__main__': unittest.main()
