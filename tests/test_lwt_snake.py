"""Public CLI rules, independent oracle, and real-process bridge boundaries."""
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from app.lwt_snake.bridge import BridgeFailure, GAME_SOURCE, LwtSnakeBridge
from app.lwt_snake.protocol import CommandRejected, ProtocolError, parse_response
from app.snake_game_core import Direction, SnakeGame

ROOT = Path(__file__).resolve().parents[1]


class ParkMiller:
    def __init__(self, seed): self.state = seed
    def randrange(self, stop):
        self.state = self.state * 48271 % 2147483647
        return self.state % stop


class LwtSnakeRuleTests(unittest.TestCase):
    def bridge(self, **kwargs):
        bridge = LwtSnakeBridge(repository_root=ROOT, **kwargs)
        self.addCleanup(bridge.close)
        return bridge, bridge.start()

    def test_public_cli_golden_win_and_eof(self):
        commands = (ROOT / 'app/lwt_snake/demo.commands').read_bytes()
        expected = (ROOT / 'app/lwt_snake/demo.expected').read_bytes()
        result = subprocess.run([sys.executable, '-u', '-m', 'lwt', 'app/lwt_snake/game.lwt'], cwd=ROOT, input=commands, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.replace(b'\r\n', b'\n'), expected.replace(b'\r\n', b'\n'))
        self.assertEqual(result.stderr, b'')
        rules = subprocess.run([sys.executable, '-u', '-m', 'lwt', str(GAME_SOURCE)], cwd=ROOT, input=(ROOT/'app/lwt_snake/rules.commands').read_bytes(), capture_output=True, timeout=10)
        self.assertEqual((rules.returncode, rules.stderr), (0, b''))
        self.assertEqual(rules.stdout.replace(b'\r\n', b'\n'), (ROOT/'app/lwt_snake/rules.expected').read_bytes().replace(b'\r\n', b'\n'))
        empty = subprocess.run([sys.executable, '-u', '-m', 'lwt', str(GAME_SOURCE)], cwd=ROOT, input=b'', capture_output=True, timeout=10)
        self.assertEqual((empty.returncode, empty.stdout, empty.stderr), (0, b'', b''))

    def test_growth_vacating_tail_and_reset_are_lwt_owned(self):
        bridge, original = self.bridge(width=4, height=2, seed=4)
        self.assertEqual(original.food, (3, 1))
        bridge.request('START')
        grown = bridge.request('TICK')
        self.assertEqual((grown.score, len(grown.snake)), (10, 4))
        for direction in ('U', 'L', 'D'):
            bridge.request('TURN', direction)
            before = grown
            grown = bridge.request('TICK')
        self.assertEqual(grown.snake[0], before.snake[-1])
        self.assertEqual(grown.phase, 'RUNNING')
        reset = bridge.request('RESET')
        self.assertEqual((reset.snake, reset.food, reset.score, reset.phase), (original.snake, original.food, 0, 'READY'))

    def test_turn_queue_reversal_self_collision_pause_and_wall(self):
        bridge, initial = self.bridge(width=8, height=5)
        bridge.request('START')
        with self.assertRaises(CommandRejected) as rejected: bridge.request('TURN', 'L')
        self.assertEqual(rejected.exception.code, 'BAD_TURN')
        bridge.request('TURN', 'U')
        with self.assertRaises(CommandRejected): bridge.request('TURN', 'D')
        bridge.request('TURN', 'L')
        hit = bridge.request('TICK')
        self.assertEqual((hit.phase, hit.snake), ('GAME_OVER', initial.snake))
        bridge.request('RESET'); bridge.request('START')
        bridge.request('TURN', 'U')
        paused = bridge.request('PAUSE')
        self.assertEqual(paused.direction, 'R')
        self.assertEqual(bridge.request('TICK').snake, paused.snake)
        bridge.request('RESUME')
        for _ in range(5): last = bridge.request('TICK')
        self.assertEqual(last.phase, 'GAME_OVER')

    def test_malformed_cli_commands_do_not_corrupt_state_or_sequence(self):
        lines = ['garbage', 'WRONG|000001|INIT|4|1|0000000001', 'LWS1|000002|INIT|4|1|0000000001', 'LWS1|000001|WHAT|-|-|-', 'LWS1|000002|INIT|4|1|0000000001', 'LWS1|000003|TICK|-|-|-']
        result = subprocess.run([sys.executable, '-u', '-m', 'lwt', str(GAME_SOURCE)], cwd=ROOT, input=('\n'.join(lines)+'\n').encode(), capture_output=True, timeout=10)
        out = result.stdout.decode().splitlines()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([line.rsplit('|',1)[-1] for line in out[:4]], ['BAD_FIELD_COUNT', 'BAD_VERSION', 'BAD_SEQUENCE', 'BAD_COMMAND'])
        self.assertIn('|STATE|READY|', out[-1])

    def test_independent_python_oracle_fixed_action_trajectories(self):
        directions = {'U': Direction.UP, 'R': Direction.RIGHT, 'D': Direction.DOWN, 'L': Direction.LEFT}
        chooser = random.Random(3401)
        for seed in (1, 4, 14, 39):
            with self.subTest(seed=seed):
                bridge, initial = self.bridge(width=8, height=5, seed=seed)
                oracle = SnakeGame(8, 5, rng=ParkMiller(seed))
                self.assertEqual(initial.food, oracle.food)
                bridge.request('START'); oracle.start()
                for _ in range(60):
                    # One accepted TURN per TICK maps faithfully to the reference core.
                    direction = chooser.choice(tuple(directions))
                    accepted = oracle.set_direction(directions[direction])
                    if accepted: bridge.request('TURN', direction)
                    oracle.step()
                    state = bridge.request('TICK')
                    self.assertEqual((state.snake, state.food, state.score, state.phase.lower()), (tuple(oracle.snake), oracle.food, oracle.score, oracle.status.value))
                    if state.phase != 'RUNNING': break

    def test_long_lived_process_and_unicode_source_path(self):
        with tempfile.TemporaryDirectory(prefix='lwt snake 雪 ') as folder:
            source = Path(folder) / '规则 game.lwt'
            source.write_bytes(GAME_SOURCE.read_bytes())
            bridge, _ = self.bridge(source_path=source)
            pid = bridge.pid
            bridge.request('START')
            for _ in range(100): bridge.request('TICK')
            self.assertEqual(bridge.pid, pid)
            bridge.close()
            self.assertEqual(bridge.returncode, 0)


class BridgeFaultTests(unittest.TestCase):
    def fault(self, script, timeout=0.5):
        def factory(**kwargs):
            kwargs['args'] = [sys.executable, '-u', '-c', script]
            return subprocess.Popen(**kwargs)
        bridge = LwtSnakeBridge(repository_root=ROOT, process_factory=factory, timeout=timeout)
        self.addCleanup(bridge.close)
        return bridge

    def test_invalid_bytes_overlong_partial_duplicate_and_extra_output(self):
        valid = b'LWS1|000001|STATE|READY|0|R|0|0|3|12,9;11,9;10,9\n'
        scripts = ["import sys; sys.stdout.buffer.write(b'\\xff\\n'); sys.stdout.flush()", "print('x'*5000)", "import sys; sys.stdout.write('partial'); sys.stdout.flush()", f"import sys; sys.stdout.buffer.write({valid!r}+{valid!r}); sys.stdout.flush()", f"import sys; sys.stdout.buffer.write({valid.replace(b'000001', b'000002')!r}); sys.stdout.flush()"]
        for script in scripts:
            with self.subTest(script=script[:60]):
                bridge = self.fault(script)
                with self.assertRaises(BridgeFailure):
                    bridge.start()
                    bridge.request('START')
                bridge.close()
                self.assertIsNotNone(bridge.returncode)

    def test_timeout_and_stderr_flood_are_drained_and_reaped(self):
        for script in ("import time; time.sleep(30)", "import sys; sys.stderr.write('diagnostic'*20000); sys.stderr.flush(); sys.exit(7)"):
            bridge = self.fault(script)
            with self.assertRaises(BridgeFailure): bridge.start()
            self.assertIsNotNone(bridge.returncode)
            self.assertFalse(bridge._stdout_thread.is_alive())
            self.assertFalse(bridge._stderr_thread.is_alive())

    def test_start_failure_and_parser_rejects_inconsistent_frames(self):
        bridge = LwtSnakeBridge(repository_root=ROOT, python_executable=str(ROOT/'missing-python'))
        with self.assertRaises(BridgeFailure): bridge.start()
        valid = b'LWS1|000001|STATE|READY|0|R|0|0|3|4,2;3,2;2,2'
        for frame in (valid+b'|extra', valid.replace(b'4,2', b'24,2'), valid.replace(b'2,2', b'3,2'), valid.replace(b'|3|',b'|4|'), valid.replace(b'|0|R|',b'|1|R|'), valid.replace(b'|0|0|',b'|-|-|')):
            with self.subTest(frame=frame), self.assertRaises(ProtocolError): parse_response(frame, expected_sequence=1, width=24, height=18)


if __name__ == '__main__': unittest.main()
