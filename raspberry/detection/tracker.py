import time


class DetectionTracker:
    def __init__(self, consecutive_frames: int, cooldown_seconds: float):
        self.consecutive_frames = consecutive_frames
        self.cooldown_seconds = cooldown_seconds
        self.streak = 0
        self.cooldown_until = 0.0

    def in_cooldown(self) -> bool:
        return time.monotonic() < self.cooldown_until

    def observe(self, has_object: bool) -> bool:
        if self.in_cooldown():
            return False
        if not has_object:
            self.streak = 0
            return False
        self.streak += 1
        if self.streak >= self.consecutive_frames:
            self.streak = 0
            self.cooldown_until = time.monotonic() + self.cooldown_seconds
            return True
        return False
