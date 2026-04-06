import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from codedojo.challenge_model import ChallengeSpec


@dataclass
class ExamChallengeRecord:
    challenge_spec: ChallengeSpec
    code: str | None = None
    output: str | None = None
    validation_summary: str = ""
    validation_dict: dict | None = None
    submitted: bool = False


@dataclass
class BeltExamState:
    exam_id: str
    belt: str
    challenges: list[ExamChallengeRecord] = field(default_factory=list)
    current_index: int = 0
    phase: str = "in_progress"  # "in_progress" | "grading" | "completed"
    created_at: str = ""

    @staticmethod
    def new(exam_id: str, belt: str) -> "BeltExamState":
        return BeltExamState(
            exam_id=exam_id,
            belt=belt,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    @property
    def challenges_submitted(self) -> int:
        return sum(1 for c in self.challenges if c.submitted)

    @property
    def all_submitted(self) -> bool:
        return len(self.challenges) >= 3 and all(c.submitted for c in self.challenges)

    @property
    def current_challenge(self) -> ExamChallengeRecord | None:
        if 0 <= self.current_index < len(self.challenges):
            return self.challenges[self.current_index]
        return None


def save_belt_exam(path: Path, state: BeltExamState) -> None:
    data = {
        "exam_id": state.exam_id,
        "belt": state.belt,
        "current_index": state.current_index,
        "phase": state.phase,
        "created_at": state.created_at,
        "challenges": [
            {
                "challenge_spec": asdict(rec.challenge_spec),
                "code": rec.code,
                "output": rec.output,
                "validation_summary": rec.validation_summary,
                "validation_dict": rec.validation_dict,
                "submitted": rec.submitted,
            }
            for rec in state.challenges
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_belt_exam(path: Path) -> BeltExamState | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        challenges = []
        for rec_data in data.get("challenges", []):
            spec = ChallengeSpec(**rec_data["challenge_spec"])
            challenges.append(
                ExamChallengeRecord(
                    challenge_spec=spec,
                    code=rec_data.get("code"),
                    output=rec_data.get("output"),
                    validation_summary=rec_data.get("validation_summary", ""),
                    validation_dict=rec_data.get("validation_dict"),
                    submitted=rec_data.get("submitted", False),
                )
            )
        return BeltExamState(
            exam_id=data["exam_id"],
            belt=data["belt"],
            challenges=challenges,
            current_index=data.get("current_index", 0),
            phase=data.get("phase", "in_progress"),
            created_at=data.get("created_at", ""),
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def clear_belt_exam(path: Path) -> None:
    if path.exists():
        path.unlink()
