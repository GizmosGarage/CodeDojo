from dataclasses import dataclass
from pathlib import Path

from codedojo.belt_exam import BeltExamState
from codedojo.challenge_model import ChallengeSpec
from codedojo.session_persist import load_interrupted_challenge


@dataclass
class ReviewState:
    challenge_id: str = ""
    skill: str = ""
    challenge_kind: str = "practice"
    code: str = ""
    output_text: str = ""
    validation_summary: str = ""
    validation_dict: dict | None = None
    response: str = ""
    verdict_outcome: str = "unknown"
    verdict_severity: str | None = None
    prior_attempt_count: int = 0
    prior_worst_severity: str | None = None

    @property
    def disputable(self) -> bool:
        return self.verdict_outcome == "needs_work"


class Session:
    def __init__(self):
        self.conversation_history: list[dict] = []
        self.current_challenge: ChallengeSpec | None = None
        self.current_challenge_kind: str | None = None
        self.challenge_active: bool = False
        self.attempt_count: int = 0
        self.worst_severity: str | None = None
        self.phase: str = "idle"  # "idle" | "quiz" | "challenge" | "choosing_skill"
        self.current_skill: str | None = None
        self.quiz_answers: list[str] = []
        self.pending_resume: dict | None = None
        self.awaiting_dispute_reason: bool = False
        self.last_review: ReviewState | None = None
        self.belt_exam_state: BeltExamState | None = None
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
        self.current_challenge_kind = None
        self.challenge_active = False
        self.attempt_count = 0
        self.worst_severity = None
        self.phase = "idle"
        self.current_skill = None
        self.quiz_answers = []
        self.pending_resume = None
        self.awaiting_dispute_reason = False
        self.last_review = None
        self.belt_exam_state = None
