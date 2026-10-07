"""Headless behavior tests for the independent Python Snake game."""

from __future__ import annotations

import subprocess
import sys
import unittest

from app.snake_game_core import Direction, GameStatus, SnakeGame, TickResult


class FixedIndex:
    def __init__(self, index: int = 0) -> None:
        self.index = index

    def randrange(self, stop: int) -> int:
        return self.index % stop


class SnakeGameTests(unittest.TestCase):
    def test_initial_state_food_and_inactive_tick(self) -> None:
        game = SnakeGame(width=8, height=5, rng=FixedIndex())
        self.assertEqual(game.status, GameStatus.READY)
        self.assertEqual(len(game.snake), 3)
        self.assertEqual(game.direction, Direction.RIGHT)
        self.assertEqual(game.score, 0)
        self.assertNotIn(game.food, game.snake)
        self.assertEqual(game.step(), TickResult.INACTIVE)

    def test_start_and_legal_movement_keep_length(self) -> None:
        game = SnakeGame(width=8, height=5, rng=FixedIndex())
        self.assertTrue(game.start())
        old_length = len(game.snake)
        old_head = game.snake[0]
        self.assertEqual(game.step(), TickResult.MOVED)
        self.assertEqual(game.snake[0], (old_head[0] + 1, old_head[1]))
        self.assertEqual(len(game.snake), old_length)

    def test_direct_reversal_is_rejected(self) -> None:
        game = SnakeGame(width=8, height=5, rng=FixedIndex())
        self.assertFalse(game.set_direction(Direction.LEFT))
        self.assertEqual(game.direction, Direction.RIGHT)
        self.assertTrue(game.set_direction(Direction.UP))

    def test_eating_grows_scores_and_relocates_food_off_snake(self) -> None:
        game = SnakeGame(width=8, height=5, rng=FixedIndex())
        old_length = len(game.snake)
        game.food = (game.snake[0][0] + 1, game.snake[0][1])
        game.start()
        self.assertEqual(game.step(), TickResult.ATE_FOOD)
        self.assertEqual(len(game.snake), old_length + 1)
        self.assertEqual(game.score, 10)
        self.assertNotIn(game.food, game.snake)

    def test_wall_collision_ends_game_without_moving(self) -> None:
        game = SnakeGame(width=4, height=2, rng=FixedIndex())
        game.start()
        self.assertEqual(game.step(), TickResult.MOVED)
        before = list(game.snake)
        self.assertEqual(game.step(), TickResult.WALL_COLLISION)
        self.assertEqual(game.status, GameStatus.GAME_OVER)
        self.assertEqual(game.snake, before)

    def test_self_collision_ends_game_without_moving(self) -> None:
        game = SnakeGame(width=6, height=4, rng=FixedIndex())
        game.snake = [(1, 1), (1, 2), (2, 2), (2, 1), (3, 1)]
        game.direction = Direction.RIGHT
        game.food = (5, 3)
        game.start()
        before = list(game.snake)
        self.assertEqual(game.step(), TickResult.SELF_COLLISION)
        self.assertEqual(game.status, GameStatus.GAME_OVER)
        self.assertEqual(game.snake, before)

    def test_entering_the_vacating_tail_cell_is_allowed(self) -> None:
        game = SnakeGame(width=5, height=4, rng=FixedIndex())
        game.snake = [(1, 1), (1, 2), (0, 2), (0, 1)]
        game.direction = Direction.UP
        game.food = (4, 3)
        self.assertTrue(game.set_direction(Direction.LEFT))
        game.start()
        self.assertEqual(game.step(), TickResult.MOVED)
        self.assertEqual(game.snake[0], (0, 1))
        self.assertEqual(len(game.snake), 4)

    def test_pause_resume_and_focus_loss_pause_are_explicit(self) -> None:
        game = SnakeGame(width=8, height=5, rng=FixedIndex())
        self.assertFalse(game.pause())
        game.start()
        self.assertTrue(game.on_focus_lost())
        self.assertEqual(game.status, GameStatus.PAUSED)
        self.assertEqual(game.step(), TickResult.INACTIVE)
        self.assertTrue(game.resume())
        self.assertFalse(game.resume())
        self.assertEqual(game.status, GameStatus.RUNNING)

    def test_restart_restores_initial_state(self) -> None:
        game = SnakeGame(width=8, height=5, rng=FixedIndex())
        original_snake = list(game.snake)
        game.start()
        game.food = (game.snake[0][0] + 1, game.snake[0][1])
        game.step()
        self.assertEqual(game.score, 10)
        game.restart()
        self.assertEqual(game.status, GameStatus.READY)
        self.assertEqual(game.snake, original_snake)
        self.assertEqual(game.direction, Direction.RIGHT)
        self.assertEqual(game.score, 0)
        self.assertNotIn(game.food, game.snake)

    def test_filling_board_is_a_win(self) -> None:
        game = SnakeGame(width=4, height=1, rng=FixedIndex())
        self.assertEqual(game.food, (3, 0))
        game.start()
        self.assertEqual(game.step(), TickResult.WON)
        self.assertEqual(game.status, GameStatus.WON)
        self.assertEqual(game.snake, [(3, 0), (2, 0), (1, 0), (0, 0)])
        self.assertIsNone(game.food)
        self.assertEqual(game.score, 10)

    def test_primary_action_replays_after_game_over_and_starts_immediately(self) -> None:
        game = SnakeGame(width=4, height=2, rng=FixedIndex())
        game.start()
        self.assertEqual(game.step(), TickResult.MOVED)
        self.assertEqual(game.step(), TickResult.WALL_COLLISION)
        self.assertEqual(game.status, GameStatus.GAME_OVER)

        self.assertTrue(game.activate_primary_action())
        self.assertEqual(game.status, GameStatus.RUNNING)
        self.assertEqual(game.score, 0)
        self.assertEqual(len(game.snake), 3)

    def test_primary_action_replays_after_a_win_and_starts_immediately(self) -> None:
        game = SnakeGame(width=4, height=1, rng=FixedIndex())
        game.start()
        self.assertEqual(game.step(), TickResult.WON)
        self.assertEqual(game.status, GameStatus.WON)
        self.assertEqual(game.score, 10)

        self.assertTrue(game.activate_primary_action())
        self.assertEqual(game.status, GameStatus.RUNNING)
        self.assertEqual(game.score, 0)
        self.assertEqual(len(game.snake), 3)

    def test_core_import_does_not_import_tkinter_or_create_a_window(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import app.snake_game_core; "
                "assert 'tkinter' not in sys.modules",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
