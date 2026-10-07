"""Headless rules and state for the independent LWT project Snake game."""

from __future__ import annotations

from enum import Enum
import random
from typing import Protocol


Point = tuple[int, int]


class RandomIndexSource(Protocol):
    """Small injectable interface used to choose a free food cell."""

    def randrange(self, stop: int) -> int:
        ...


class Direction(str, Enum):
    UP = "up"
    RIGHT = "right"
    DOWN = "down"
    LEFT = "left"


class GameStatus(str, Enum):
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    GAME_OVER = "game_over"
    WON = "won"


class TickResult(str, Enum):
    INACTIVE = "inactive"
    MOVED = "moved"
    ATE_FOOD = "ate_food"
    WALL_COLLISION = "wall_collision"
    SELF_COLLISION = "self_collision"
    WON = "won"


_DELTAS: dict[Direction, Point] = {
    Direction.UP: (0, -1),
    Direction.RIGHT: (1, 0),
    Direction.DOWN: (0, 1),
    Direction.LEFT: (-1, 0),
}
_OPPOSITE: dict[Direction, Direction] = {
    Direction.UP: Direction.DOWN,
    Direction.RIGHT: Direction.LEFT,
    Direction.DOWN: Direction.UP,
    Direction.LEFT: Direction.RIGHT,
}


class SnakeGame:
    """Deterministic, display-independent Snake state machine.

    A move into the current tail cell is legal when the snake is not growing,
    because the tail leaves during that same tick. Food selection is uniform
    over the row-major list of currently empty cells.
    """

    def __init__(
        self,
        width: int = 24,
        height: int = 18,
        *,
        rng: RandomIndexSource | None = None,
    ) -> None:
        if width < 4 or height < 1:
            raise ValueError("the board must be at least 4 cells wide and 1 cell high")
        self.width = width
        self.height = height
        self._rng = rng if rng is not None else random.Random()
        self.restart()

    def restart(self) -> None:
        """Reset the board to the ready state with score zero."""
        y = self.height // 2
        head_x = self.width // 2
        self.snake: list[Point] = [(head_x, y), (head_x - 1, y), (head_x - 2, y)]
        self.direction = Direction.RIGHT
        self.score = 0
        self.status = GameStatus.READY
        self.food: Point | None = None
        self._place_food()

    def start(self) -> bool:
        """Start a new ready game. Paused games must use ``resume``."""
        if self.status is not GameStatus.READY:
            return False
        self.status = GameStatus.RUNNING
        return True

    def pause(self) -> bool:
        if self.status is not GameStatus.RUNNING:
            return False
        self.status = GameStatus.PAUSED
        return True

    def resume(self) -> bool:
        if self.status is not GameStatus.PAUSED:
            return False
        self.status = GameStatus.RUNNING
        return True

    def on_focus_lost(self) -> bool:
        """Pause after the window loses focus; the UI asks the model to resume."""
        return self.pause()

    def set_direction(self, direction: Direction | str) -> bool:
        """Set the next travel direction, rejecting a direct reversal."""
        try:
            selected = direction if isinstance(direction, Direction) else Direction(direction)
        except ValueError:
            return False
        if len(self.snake) > 1 and selected is _OPPOSITE[self.direction]:
            return False
        self.direction = selected
        return True

    def step(self) -> TickResult:
        """Advance one fixed game tick, returning the event for the UI/tests."""
        if self.status is not GameStatus.RUNNING:
            return TickResult.INACTIVE

        dx, dy = _DELTAS[self.direction]
        head_x, head_y = self.snake[0]
        next_head = (head_x + dx, head_y + dy)
        next_x, next_y = next_head
        if not (0 <= next_x < self.width and 0 <= next_y < self.height):
            self.status = GameStatus.GAME_OVER
            return TickResult.WALL_COLLISION

        grows = next_head == self.food
        occupied = self.snake if grows else self.snake[:-1]
        if next_head in occupied:
            self.status = GameStatus.GAME_OVER
            return TickResult.SELF_COLLISION

        self.snake.insert(0, next_head)
        if not grows:
            self.snake.pop()
            return TickResult.MOVED

        self.score += 10
        if not self._place_food():
            self.status = GameStatus.WON
            return TickResult.WON
        return TickResult.ATE_FOOD

    def _place_food(self) -> bool:
        occupied = set(self.snake)
        empty_cells = [
            (x, y)
            for y in range(self.height)
            for x in range(self.width)
            if (x, y) not in occupied
        ]
        if not empty_cells:
            self.food = None
            return False
        self.food = empty_cells[self._rng.randrange(len(empty_cells))]
        return True
