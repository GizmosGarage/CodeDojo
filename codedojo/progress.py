import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class SkillRecord:
    attempts: int = 0
    successes: int = 0
    last_practiced: str | None = None  # ISO timestamp


@dataclass
class LessonRecord:
    quiz_score: str = ""  # e.g. "2/3"
    weak_questions: list[int] = field(default_factory=list)  # 1-indexed


class Progress:
    def __init__(self):
        self.xp: int = 0
        self.belt: str = "white"
        self.completed_challenges: list[str] = []  # challenge_ids
        self.skills: dict[str, SkillRecord] = {}
        self.skills_taught: list[str] = []
        self.lesson_history: dict[str, LessonRecord] = {}

    def record_lesson(self, skill: str, score: int, total: int, wrong_questions: list[int]):
        """Record that a lesson was taught and quiz results."""
        if skill not in self.skills_taught:
            self.skills_taught.append(skill)
        if skill not in self.skills:
            self.skills[skill] = SkillRecord()
        self.lesson_history[skill] = LessonRecord(
            quiz_score=f"{score}/{total}",
            weak_questions=wrong_questions,
        )

    def get_untaught_skills(self, belt_skills: list[str]) -> list[str]:
        """Return skills from the belt that haven't been taught yet."""
        taught = set(self.skills_taught)
        return [s for s in belt_skills if s not in taught]

    def record_attempt(self, skill: str, challenge_id: str, passed: bool):
        """Record a challenge attempt and award XP if passed."""
        if skill not in self.skills:
            self.skills[skill] = SkillRecord()

        record = self.skills[skill]
        record.attempts += 1
        record.last_practiced = datetime.now(timezone.utc).isoformat()

        if passed and challenge_id not in self.completed_challenges:
            record.successes += 1
            self.completed_challenges.append(challenge_id)
            # XP: 50 first attempt, 30 second, 20 third+
            attempts_on_this = record.attempts - (record.successes - 1)
            if attempts_on_this <= 1:
                self.add_xp(50)
            elif attempts_on_this == 2:
                self.add_xp(30)
            else:
                self.add_xp(20)

    def add_xp(self, amount: int):
        self.xp += amount
        self._check_belt_promotion()

    def _check_belt_promotion(self):
        # Future: check if XP threshold reached for next belt
        pass

    def get_proficiency(self, skill: str) -> float:
        """Return success ratio for a skill (0.0 to 1.0)."""
        record = self.skills.get(skill)
        if not record or record.attempts == 0:
            return 0.0
        return record.successes / record.attempts

    def summary_line(self) -> str:
        """Return banner-friendly status line."""
        belt_display = self.belt.capitalize() + " Belt"
        return f"Belt: {belt_display} | XP: {self.xp}"

    def skills_display(self) -> str:
        """Return ASCII progress bars for learned skills (lessons + challenge practice)."""
        names_ordered: list[str] = list(self.skills_taught)
        for name in self.skills:
            if name not in names_ordered:
                names_ordered.append(name)

        if not names_ordered:
            return "  No skills yet. Type 'lesson' to start learning!"

        lines = ["  === Your Skills ==="]
        max_name = max(len(name) for name in names_ordered)

        def challenge_sort_key(name: str) -> tuple[int, int]:
            rec = self.skills.get(name) or SkillRecord()
            return (rec.successes, rec.attempts)

        practiced = [n for n in names_ordered if (self.skills.get(n) or SkillRecord()).attempts > 0]
        lesson_only = [n for n in names_ordered if (self.skills.get(n) or SkillRecord()).attempts == 0]
        practiced.sort(key=challenge_sort_key, reverse=True)
        display_order = practiced + lesson_only

        for name in display_order:
            record = self.skills.get(name) or SkillRecord()
            padded_name = name.ljust(max_name)

            if record.attempts == 0:
                lesson = self.lesson_history.get(name)
                quiz = lesson.quiz_score if lesson else "—"
                bar = "-" * 10
                lines.append(
                    f"  {padded_name}  [{bar}] {'Learned':10s} (lesson {quiz} · try 'challenge')"
                )
                continue

            ratio = record.successes / record.attempts
            if ratio >= 0.8:
                tier = "Mastered"
            elif ratio >= 0.5:
                tier = "Practiced"
            else:
                tier = "Learning"

            filled = round(ratio * 10)
            bar = "#" * filled + "-" * (10 - filled)

            lines.append(f"  {padded_name}  [{bar}] {tier:10s} ({record.successes}/{record.attempts})")

        return "\n".join(lines)

    def save(self, path: Path):
        """Save progress to JSON file."""
        data = {
            "xp": self.xp,
            "belt": self.belt,
            "completed_challenges": self.completed_challenges,
            "skills": {
                name: asdict(record)
                for name, record in self.skills.items()
            },
            "skills_taught": self.skills_taught,
            "lesson_history": {
                name: asdict(record)
                for name, record in self.lesson_history.items()
            },
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self, path: Path):
        """Load progress from JSON file. Silently no-ops if file doesn't exist."""
        if not path.exists():
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.xp = data.get("xp", 0)
            self.belt = data.get("belt", "white")
            self.completed_challenges = data.get("completed_challenges", [])
            for name, record_data in data.get("skills", {}).items():
                self.skills[name] = SkillRecord(**record_data)
            self.skills_taught = data.get("skills_taught", [])
            for name, record_data in data.get("lesson_history", {}).items():
                self.lesson_history[name] = LessonRecord(**record_data)
            # Migration: seed skills_taught from practiced skills if empty
            if not self.skills_taught and self.skills:
                self.skills_taught = list(self.skills.keys())
            for skill in self.skills_taught:
                if skill not in self.skills:
                    self.skills[skill] = SkillRecord()
        except (json.JSONDecodeError, KeyError, TypeError):
            pass  # Corrupted file — start fresh
