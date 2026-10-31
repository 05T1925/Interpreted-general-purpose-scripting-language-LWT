"""A single bounded movement deadline, independent of input responses."""
class GameClock:
    def __init__(self, period):
        self.period = period
        self.deadline = None
    def start(self, now):
        if self.deadline is None:
            self.deadline = now + self.period
    def stop(self):
        self.deadline = None
    def due(self, now):
        return self.deadline is not None and now >= self.deadline
    def completed(self, now):
        # Drop elapsed intervals: never replay a backlog after a slow response.
        self.deadline = now + self.period
