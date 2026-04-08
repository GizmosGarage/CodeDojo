import json
import re
from dataclasses import asdict, dataclass, field
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


@dataclass
class ChallengeHistoryRecord:
    challenge_id: str = ""
    title: str = ""
    expected_behavior: str = ""
    required_concepts: list[str] = field(default_factory=list)
    generated_at: str | None = None  # ISO timestamp


class Progress:
    def __init__(self):
        self.xp: int = 0
        self.belt: str = "white"
        self.completed_challenges: list[str] = []  # challenge_ids
        self.skills: dict[str, SkillRecord] = {}
        self.skills_taught: list[str] = []
        self.lesson_history: dict[str, LessonRecord] = {}
        self.challenge_history: dict[str, list[ChallengeHistoryRecord]] = {}
        self.belt_exam_attempts: dict[str, int] = {}

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

    def has_unlocked_belt_exam(self, belt_skills: list[str]) -> bool:
        """Return whether the current belt exam is unlocked."""
        return not self.get_untaught_skills(belt_skills)

    @staticmethod
    def _local_day_key(now: datetime | None = None) -> str:
        current = now or datetime.now().astimezone()
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc).astimezone()
        else:
            current = current.astimezone()
        return current.date().isoformat()

    def belt_exam_attempts_today(self, now: datetime | None = None) -> int:
        """Return the number of belt exam attempts used today."""
        return self.belt_exam_attempts.get(self._local_day_key(now), 0)

    def belt_exam_attempts_remaining(
        self,
        daily_limit: int,
        now: datetime | None = None,
    ) -> int:
        """Return the number of belt exam attempts still available today."""
        return max(0, daily_limit - self.belt_exam_attempts_today(now))

    def can_start_belt_exam(
        self,
        belt_skills: list[str],
        daily_limit: int,
        now: datetime | None = None,
    ) -> bool:
        """Return whether the student can start the belt exam right now."""
        return (
            self.has_unlocked_belt_exam(belt_skills)
            and self.belt_exam_attempts_remaining(daily_limit, now) > 0
        )

    def record_belt_exam_attempt(self, now: datetime | None = None) -> int:
        """Consume one belt exam attempt for the current day."""
        day_key = self._local_day_key(now)
        next_count = self.belt_exam_attempts.get(day_key, 0) + 1
        self.belt_exam_attempts[day_key] = next_count
        return next_count

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

    def omit_failed_attempt(self, skill: str) -> None:
        """Remove one recorded failed attempt when Sensei overturns a review."""
        record = self.skills.get(skill)
        if not record or record.attempts <= record.successes:
            return
        record.attempts -= 1
        if record.attempts == 0:
            record.last_practiced = None

    def add_xp(self, amount: int):
        self.xp += amount
        self._check_belt_promotion()

    BELT_ORDER = ["white", "yellow", "orange", "green", "blue", "purple", "brown", "black"]

    def _check_belt_promotion(self):
        # Belt promotion is handled explicitly via promote_belt() after passing an exam.
        pass

    def promote_belt(self) -> str:
        """Promote to the next belt. Returns the new belt name."""
        try:
            idx = self.BELT_ORDER.index(self.belt)
            if idx < len(self.BELT_ORDER) - 1:
                self.belt = self.BELT_ORDER[idx + 1]
        except ValueError:
            pass
        return self.belt

    def get_proficiency(self, skill: str) -> float:
        """Return success ratio for a skill (0.0 to 1.0)."""
        record = self.skills.get(skill)
        if not record or record.attempts == 0:
            return 0.0
        return record.successes / record.attempts

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join(re.findall(r"[a-z0-9]+", (text or "").casefold()))

    @classmethod
    def _text_tokens(cls, text: str) -> set[str]:
        return {token for token in cls._normalize_text(text).split() if len(token) >= 3}

    @classmethod
    def _normalize_concepts(cls, concepts: list[str]) -> set[str]:
        normalized: set[str] = set()
        for concept in concepts:
            cleaned = cls._normalize_text(concept)
            if cleaned:
                normalized.add(cleaned)
        return normalized

    @staticmethod
    def _jaccard_similarity(left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        return len(left & right) / len(left | right)

    @staticmethod
    def _challenge_tier(record: SkillRecord) -> str:
        ratio = record.successes / record.attempts
        if ratio >= 0.8:
            return "Mastered"
        if ratio >= 0.5:
            return "Practiced"
        return "Learning"

    def skill_progress_label(self, skill: str) -> str:
        """Compact skill status text for menus and summaries."""
        record = self.skills.get(skill) or SkillRecord()
        if record.attempts == 0:
            lesson = self.lesson_history.get(skill)
            quiz = lesson.quiz_score if lesson and lesson.quiz_score else "--"
            return f"Learned (lesson {quiz})"
        tier = self._challenge_tier(record)
        return f"{tier} ({record.successes}/{record.attempts})"

    def record_generated_challenge(
        self,
        skill: str,
        challenge_id: str,
        title: str,
        expected_behavior: str,
        required_concepts: list[str],
        generated_at: str | None = None,
    ) -> None:
        """Persist generated challenge details so future prompts can avoid repeats."""
        history = self.challenge_history.setdefault(skill, [])
        if any(entry.challenge_id == challenge_id for entry in history):
            return
        history.append(
            ChallengeHistoryRecord(
                challenge_id=challenge_id,
                title=title,
                expected_behavior=expected_behavior,
                required_concepts=list(required_concepts),
                generated_at=generated_at or datetime.now(timezone.utc).isoformat(),
            )
        )

    def get_recent_challenge_descriptors(self, skill: str, limit: int = 5) -> list[dict]:
        """Return recent challenge details for prompt conditioning."""
        history = self.challenge_history.get(skill, [])
        recent = history[-limit:]
        return [
            {
                "title": entry.title,
                "expected_behavior": entry.expected_behavior,
                "required_concepts": list(entry.required_concepts),
            }
            for entry in reversed(recent)
        ]

    def find_similar_challenge(
        self,
        skill: str,
        title: str,
        expected_behavior: str,
        required_concepts: list[str],
    ) -> ChallengeHistoryRecord | None:
        """Find a prior challenge that is too similar to safely reuse."""
        title_normalized = self._normalize_text(title)
        behavior_normalized = self._normalize_text(expected_behavior)
        title_tokens = self._text_tokens(title)
        combined_tokens = self._text_tokens(f"{title} {expected_behavior}")
        concept_set = self._normalize_concepts(required_concepts)

        for entry in reversed(self.challenge_history.get(skill, [])):
            entry_title_normalized = self._normalize_text(entry.title)
            entry_behavior_normalized = self._normalize_text(entry.expected_behavior)
            entry_title_tokens = self._text_tokens(entry.title)
            entry_combined_tokens = self._text_tokens(f"{entry.title} {entry.expected_behavior}")
            entry_concepts = self._normalize_concepts(entry.required_concepts)

            if title_normalized and entry_title_normalized and title_normalized == entry_title_normalized:
                return entry
            if behavior_normalized and entry_behavior_normalized and behavior_normalized == entry_behavior_normalized:
                return entry

            title_similarity = self._jaccard_similarity(title_tokens, entry_title_tokens)
            combined_similarity = self._jaccard_similarity(combined_tokens, entry_combined_tokens)

            if combined_similarity >= 0.82:
                return entry

            if concept_set and concept_set == entry_concepts:
                if not (entry.title or entry.expected_behavior):
                    continue
                if len(concept_set) >= 3 and combined_similarity >= 0.55:
                    return entry
                if title_similarity >= 0.8:
                    return entry

        return None

    def import_challenge_history_from_log(self, path: Path) -> None:
        """Backfill stored challenge history from the session log when available."""
        if not path.exists():
            return

        known_ids = {
            entry.challenge_id
            for entries in self.challenge_history.values()
            for entry in entries
            if entry.challenge_id
        }

        try:
            with open(path, "r", encoding="utf-8") as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if data.get("event") != "challenge_generated":
                        continue

                    challenge_id = data.get("challenge_id", "")
                    skill = data.get("skill")
                    if not skill or (challenge_id and challenge_id in known_ids):
                        continue

                    self.record_generated_challenge(
                        skill=skill,
                        challenge_id=challenge_id,
                        title=data.get("title", ""),
                        expected_behavior=data.get("expected_behavior", ""),
                        required_concepts=data.get("requirements", []),
                        generated_at=data.get("timestamp"),
                    )
                    if challenge_id:
                        known_ids.add(challenge_id)
        except OSError:
            return

    def summary_line(self) -> str:
        """Return banner-friendly status line."""
        belt_display = self.belt.capitalize() + " Belt"
        return f"Belt: {belt_display} | XP: {self.xp}"

    @classmethod
    def _group_skill_names_by_belt(cls, names: list[str]) -> list[tuple[str, list[str]]]:
        """Group known skill names under their curriculum belt headers."""
        from codedojo.challenge_gen import BELT_SKILL_MAP

        remaining = set(names)
        groups: list[tuple[str, list[str]]] = []

        for belt in cls.BELT_ORDER:
            belt_skills = [skill for skill in BELT_SKILL_MAP.get(belt, []) if skill in remaining]
            if belt_skills:
                groups.append((f"{belt.capitalize()} Belt", belt_skills))
                remaining.difference_update(belt_skills)

        extras = [skill for skill in names if skill in remaining]
        if extras:
            groups.append(("Other Skills", extras))

        return groups

    def grouped_skills_taught(self) -> list[tuple[str, list[str]]]:
        """Return learned skills grouped under curriculum belt headers."""
        return self._group_skill_names_by_belt(list(self.skills_taught))

    def ordered_skills_taught(self) -> list[str]:
        """Return learned skills flattened in grouped curriculum order."""
        ordered: list[str] = []
        for _, skills in self.grouped_skills_taught():
            ordered.extend(skills)
        return ordered

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

        grouped_names = self._group_skill_names_by_belt(names_ordered)

        for belt_label, belt_skills in grouped_names:
            lines.append("")
            lines.append(f"  {belt_label}:")
            for name in belt_skills:
                record = self.skills.get(name) or SkillRecord()
                padded_name = name.ljust(max_name)

                if record.attempts == 0:
                    lesson = self.lesson_history.get(name)
                    quiz = lesson.quiz_score if lesson and lesson.quiz_score else "--"
                    bar = "-" * 10
                    lines.append(
                        f"    {padded_name}  [{bar}] {'Learned':10s} (lesson {quiz} - try 'challenge')"
                    )
                    continue

                ratio = record.successes / record.attempts
                tier = self._challenge_tier(record)
                filled = round(ratio * 10)
                bar = "#" * filled + "-" * (10 - filled)

                lines.append(
                    f"    {padded_name}  [{bar}] {tier:10s} ({record.successes}/{record.attempts})"
                )

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
            "challenge_history": {
                skill: [asdict(entry) for entry in entries]
                for skill, entries in self.challenge_history.items()
            },
            "belt_exam_attempts": self.belt_exam_attempts,
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
            for skill, entries in data.get("challenge_history", {}).items():
                self.challenge_history[skill] = [
                    ChallengeHistoryRecord(**entry)
                    for entry in entries
                ]
            self.belt_exam_attempts = {}
            for day, count in data.get("belt_exam_attempts", {}).items():
                day_key = str(day).strip()
                if not day_key:
                    continue
                try:
                    self.belt_exam_attempts[day_key] = int(count)
                except (TypeError, ValueError):
                    continue
            # Migration: seed skills_taught from practiced skills if empty
            if not self.skills_taught and self.skills:
                self.skills_taught = list(self.skills.keys())
            for skill in self.skills_taught:
                if skill not in self.skills:
                    self.skills[skill] = SkillRecord()
        except (json.JSONDecodeError, KeyError, TypeError):
            pass  # Corrupted file -- start fresh
