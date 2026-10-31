import unittest
from app.lwt_snake.clock import GameClock

class ClockTests(unittest.TestCase):
    def test_turns_busy_and_slow_completion_keep_one_due_intent(self):
        clock = GameClock(.25)
        clock.start(0)
        for now in (.05, .1, .2): clock.start(now)
        self.assertEqual(clock.deadline, .25)
        self.assertTrue(clock.due(.3))
        self.assertTrue(clock.due(8))  # Busy never discards the deadline.
        clock.completed(8)
        self.assertFalse(clock.due(8.1))
        self.assertEqual(clock.deadline, 8.25)
        clock.stop()
        self.assertFalse(clock.due(99))
        clock.start(100)
        self.assertEqual(clock.deadline, 100.25)
