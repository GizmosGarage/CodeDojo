"""Data models for CodeDojo."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class UserProfile:
    name: str
    created_at: str = ""
    total_xp: int = 0
    level: int = 1
    belt_rank: int = 0  # 0=White, 1=Yellow, ..., 7=Black (earned via exams)
    current_streak: int = 0
    longest_streak: int = 0
    last_session_date: Optional[str] = None
    sessions_completed: int = 0
    challenges_passed: int = 0
    challenges_attempted: int = 0
    quizzes_correct: int = 0
    quizzes_attempted: int = 0
    reviews_completed: int = 0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class SkillProgress:
    skill_id: str          # e.g. "fundamentals.variables_types"
    xp: int = 0
    level: int = 0         # 0=locked, 1=beginner, 2=intermediate, 3=advanced, 4=mastered
    times_practiced: int = 0
    last_practiced: Optional[str] = None
    correct_rate: float = 0.0  # rolling accuracy


@dataclass
class SessionRecord:
    session_id: str
    date: str
    duration_minutes: int = 0
    xp_earned: int = 0
    challenges_completed: int = 0
    quizzes_completed: int = 0
    reviews_completed: int = 0
    skills_practiced: str = ""  # comma-separated skill IDs


@dataclass
class QuizQuestion:
    question: str
    options: list[str]
    correct_index: int
    explanation: str
    skill_id: str
    difficulty: str  # "beginner", "intermediate", "advanced"


@dataclass
class CodingChallenge:
    title: str
    description: str
    skill_id: str
    difficulty: str
    starter_code: str
    test_cases: list[dict]  # [{"input": ..., "expected": ..., "description": ...}]
    hints: list[str]
    solution_approach: str  # brief description, not full solution


@dataclass
class CodeReviewResult:
    score: int             # 1-10
    strengths: list[str]
    improvements: list[str]
    sensei_feedback: str
    xp_earned: int


@dataclass
class BeltExamRecord:
    exam_id: str
    belt_target: int       # which belt rank this exam is for (1=Yellow, ..., 7=Black)
    date: str
    passed: bool
    score: int             # rounds passed out of total
    total_rounds: int
    feedback: str = ""     # sensei feedback on weak areas


# Skill level thresholds
SKILL_LEVEL_NAMES = {
    0: "Locked",
    1: "Novice",
    2: "Apprentice",
    3: "Journeyman",
    4: "Master",
}

SKILL_LEVEL_XP = {
    1: 0,     # Unlocked
    2: 50,
    3: 150,
    4: 300,
}
