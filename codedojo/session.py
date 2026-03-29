from pathlib import Path

from codedojo.challenge_model import ChallengeSpec
from codedojo.session_persist import load_interrupted_challenge


class Session:
    def __init__(self):
        self.conversation_history: list[dict] = []
        self.current_challenge: ChallengeSpec | None = None
        self.challenge_active: bool = False
        self.attempt_count: int = 0
        self.worst_severity: str | None = None
        self.phase: str = "idle"  # "idle" | "quiz" | "challenge" | "choosing_skill"
        self.current_skill: str | None = None
        self.quiz_answers: list[str] = []
        self.pending_resume: dict | None = None
        self._interrupted_snapshot_stale: bool = True
        self._cached_interrupted: dict | None = None

    def get_interrupted_snapshot(self, path: Path) -> dict | None:
        if self._interrupted_snapshot_stale:
            self._cached_interrupted = load_interrupted_challenge(path)
            self._interrupted_snapshot_stale = False
        return self._cached_interrupted

    def invalidate_interrupted_snapshot(self) -> None:
        self._interrupted_snapshot_stale = True

    def clear(self):
        self.conversation_history.clear()
        self.current_challenge = None
        self.challenge_active = False
        self.attempt_count = 0
        self.worst_severity = None
        self.phase = "idle"
        self.current_skill = None
        self.quiz_answers = []
        self.pending_resume = None
