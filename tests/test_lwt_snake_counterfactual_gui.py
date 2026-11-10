"""Real Tk widgets and event loop for the read-only S40 experiment viewer."""
import threading
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from app.lwt_snake.counterfactual_ui import CounterfactualWindow
from app.lwt_snake.replay import ROOT


class CounterfactualTkTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f'Tk display unavailable: {error}')
        self.root.withdraw()

    def tearDown(self):
        try:
            if self.root.winfo_exists():
                self.root.destroy()
        except tk.TclError:
            pass

    def until(self, predicate, seconds=25):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.root.update()
            if predicate():
                return
            time.sleep(.01)
        self.fail('Tk worker did not settle within bounded event loop')

    def test_real_verify_button_shows_lwt_response_and_step_switch(self):
        ui = CounterfactualWindow(self.root)
        self.until(lambda: not ui.busy)
        self.assertIn('双层原局', ui.status.get())
        self.assertIn('LWA1|000002|MOVE|D|FOOD', ui.text.get('1.0', 'end'))
        ui.prev.invoke()
        self.assertIn('旧结果已清除', ui.text.get('1.0', 'end'))
        ui.verify_button.invoke()
        self.until(lambda: not ui.busy)
        self.assertIn('LWA1|000001|MOVE|R|FOOD', ui.text.get('1.0', 'end'))
        ui.close()

    def test_late_worker_cannot_replace_new_selection_or_destroyed_window(self):
        started = threading.Event()
        release = threading.Event()
        def controlled(_folder, _cancel):
            started.set()
            release.wait(5)
            return [], 0, 'stale', ''
        ui = CounterfactualWindow(self.root, runner=controlled)
        self.until(started.is_set)
        ui.prev.invoke()
        self.assertIn('旧结果已清除', ui.text.get('1.0', 'end'))
        release.set()
        self.until(lambda: not ui.busy)
        self.assertNotIn('stale', ui.text.get('1.0', 'end'))
        ui.close()

    def test_load_real_s41_witness_with_button_and_reverify(self):
        ui = CounterfactualWindow(self.root)
        self.until(lambda: not ui.busy)
        with patch('app.lwt_snake.counterfactual_ui.filedialog.askdirectory',
                   return_value=str(ROOT / 'reports/s41-found')):
            ui.load_button.invoke()
        self.assertIn('旧结果已清除', ui.text.get('1.0', 'end'))
        ui.verify_button.invoke()
        # S49: verifying reports/s41-found replays 32 steps and spawns one LWT
        # process per branch; measured 50-60 s on this machine, so the old 45 s
        # bound failed roughly two runs out of three. This bound is a hang
        # detector, not a performance assertion.
        self.until(lambda: not ui.busy, seconds=120)
        shown = ui.text.get('1.0', 'end')
        self.assertIn('扫描 2/32', shown)
        self.assertIn('LWA1|000002|MOVE|D|FOOD', shown)
        ui.close()


if __name__ == '__main__':
    unittest.main()
