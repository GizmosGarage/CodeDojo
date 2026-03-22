"""SQLite persistence layer for CodeDojo."""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .config import DATA_DIR_NAME, DB_NAME
from .models import UserProfile, SkillProgress, SessionRecord, BeltExamRecord


class DojoStorage:
    """Manages all persistent state for CodeDojo."""

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or Path.home() / DATA_DIR_NAME
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / DB_NAME
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._init_tables()
        self._migrate()

    def _init_tables(self):
        cur = self._conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                total_xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 1,
                belt_rank INTEGER DEFAULT 0,
                current_streak INTEGER DEFAULT 0,
                longest_streak INTEGER DEFAULT 0,
                last_session_date TEXT,
                sessions_completed INTEGER DEFAULT 0,
                challenges_passed INTEGER DEFAULT 0,
                challenges_attempted INTEGER DEFAULT 0,
                quizzes_correct INTEGER DEFAULT 0,
                quizzes_attempted INTEGER DEFAULT 0,
                reviews_completed INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS skill_progress (
                skill_id TEXT PRIMARY KEY,
                xp INTEGER DEFAULT 0,
                level INTEGER DEFAULT 0,
                times_practiced INTEGER DEFAULT 0,
                last_practiced TEXT,
                correct_rate REAL DEFAULT 0.0
            );

            CREATE TABLE IF NOT EXISTS session_history (
                session_id TEXT PRIMARY KEY,
                date TEXT NOT NULL,
                duration_minutes INTEGER DEFAULT 0,
                xp_earned INTEGER DEFAULT 0,
                challenges_completed INTEGER DEFAULT 0,
                quizzes_completed INTEGER DEFAULT 0,
                reviews_completed INTEGER DEFAULT 0,
                skills_practiced TEXT DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS conversation_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS belt_exams (
                exam_id TEXT PRIMARY KEY,
                belt_target INTEGER NOT NULL,
                date TEXT NOT NULL,
                passed INTEGER DEFAULT 0,
                score INTEGER DEFAULT 0,
                total_rounds INTEGER DEFAULT 0,
                feedback TEXT DEFAULT ''
            );
        """)
        self._conn.commit()

    def _migrate(self):
        """Add new columns to existing databases."""
        cur = self._conn.cursor()
        # Check if level column exists
        columns = [row[1] for row in cur.execute("PRAGMA table_info(user_profile)").fetchall()]
        if "level" not in columns:
            cur.execute("ALTER TABLE user_profile ADD COLUMN level INTEGER DEFAULT 1")
        if "belt_rank" not in columns:
            cur.execute("ALTER TABLE user_profile ADD COLUMN belt_rank INTEGER DEFAULT 0")
        self._conn.commit()

    # ── User Profile ───────────────────────────────────────────────

    def get_user(self) -> Optional[UserProfile]:
        row = self._conn.execute("SELECT * FROM user_profile WHERE id = 1").fetchone()
        if not row:
            return None
        keys = row.keys()
        data = {k: row[k] for k in keys if k != "id"}
        # Handle missing columns gracefully
        if "level" not in data:
            data["level"] = 1
        if "belt_rank" not in data:
            data["belt_rank"] = 0
        return UserProfile(**data)

    def create_user(self, name: str) -> UserProfile:
        user = UserProfile(name=name)
        self._conn.execute(
            """INSERT INTO user_profile (id, name, created_at, total_xp, level, belt_rank,
               current_streak, longest_streak, last_session_date, sessions_completed,
               challenges_passed, challenges_attempted, quizzes_correct, quizzes_attempted,
               reviews_completed)
               VALUES (1, ?, ?, 0, 1, 0, 0, 0, NULL, 0, 0, 0, 0, 0, 0)""",
            (user.name, user.created_at),
        )
        self._conn.commit()
        return user

    def update_user(self, user: UserProfile):
        self._conn.execute(
            """UPDATE user_profile SET
               name=?, total_xp=?, level=?, belt_rank=?, current_streak=?, longest_streak=?,
               last_session_date=?, sessions_completed=?, challenges_passed=?,
               challenges_attempted=?, quizzes_correct=?, quizzes_attempted=?,
               reviews_completed=?
               WHERE id = 1""",
            (
                user.name, user.total_xp, user.level, user.belt_rank,
                user.current_streak, user.longest_streak,
                user.last_session_date, user.sessions_completed, user.challenges_passed,
                user.challenges_attempted, user.quizzes_correct, user.quizzes_attempted,
                user.reviews_completed,
            ),
        )
        self._conn.commit()

    def update_streak(self, user: UserProfile) -> UserProfile:
        """Update streak based on last session date."""
        today = datetime.now().date()
        if user.last_session_date:
            last = datetime.fromisoformat(user.last_session_date).date()
            delta = (today - last).days
            if delta == 0:
                pass  # Same day, streak unchanged
            elif delta == 1:
                user.current_streak += 1
            else:
                user.current_streak = 1  # Streak broken
        else:
            user.current_streak = 1  # First session

        user.longest_streak = max(user.longest_streak, user.current_streak)
        user.last_session_date = today.isoformat()
        return user

    # ── Skill Progress ─────────────────────────────────────────────

    def get_skill(self, skill_id: str) -> Optional[SkillProgress]:
        row = self._conn.execute(
            "SELECT * FROM skill_progress WHERE skill_id = ?", (skill_id,)
        ).fetchone()
        if not row:
            return None
        return SkillProgress(**{k: row[k] for k in row.keys()})

    def get_all_skills(self) -> list[SkillProgress]:
        rows = self._conn.execute("SELECT * FROM skill_progress").fetchall()
        return [SkillProgress(**{k: r[k] for k in r.keys()}) for r in rows]

    def upsert_skill(self, skill: SkillProgress):
        self._conn.execute(
            """INSERT INTO skill_progress (skill_id, xp, level, times_practiced, last_practiced, correct_rate)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(skill_id) DO UPDATE SET
               xp=excluded.xp, level=excluded.level, times_practiced=excluded.times_practiced,
               last_practiced=excluded.last_practiced, correct_rate=excluded.correct_rate""",
            (skill.skill_id, skill.xp, skill.level, skill.times_practiced,
             skill.last_practiced, skill.correct_rate),
        )
        self._conn.commit()

    def unlock_skill(self, skill_id: str):
        existing = self.get_skill(skill_id)
        if not existing:
            skill = SkillProgress(skill_id=skill_id, level=1)
            self.upsert_skill(skill)

    # ── Belt Exams ────────────────────────────────────────────────

    def save_belt_exam(self, exam: BeltExamRecord):
        self._conn.execute(
            """INSERT INTO belt_exams (exam_id, belt_target, date, passed, score, total_rounds, feedback)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (exam.exam_id, exam.belt_target, exam.date, int(exam.passed),
             exam.score, exam.total_rounds, exam.feedback),
        )
        self._conn.commit()

    def get_belt_exam_history(self, belt_target: Optional[int] = None) -> list[BeltExamRecord]:
        if belt_target is not None:
            rows = self._conn.execute(
                "SELECT * FROM belt_exams WHERE belt_target = ? ORDER BY date DESC", (belt_target,)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM belt_exams ORDER BY date DESC"
            ).fetchall()
        return [
            BeltExamRecord(
                exam_id=r["exam_id"],
                belt_target=r["belt_target"],
                date=r["date"],
                passed=bool(r["passed"]),
                score=r["score"],
                total_rounds=r["total_rounds"],
                feedback=r["feedback"],
            )
            for r in rows
        ]

    def get_last_failed_exam(self, belt_target: int) -> Optional[BeltExamRecord]:
        """Get the most recent failed exam for a belt target."""
        rows = self._conn.execute(
            "SELECT * FROM belt_exams WHERE belt_target = ? AND passed = 0 ORDER BY date DESC LIMIT 1",
            (belt_target,)
        ).fetchall()
        if not rows:
            return None
        r = rows[0]
        return BeltExamRecord(
            exam_id=r["exam_id"], belt_target=r["belt_target"], date=r["date"],
            passed=bool(r["passed"]), score=r["score"], total_rounds=r["total_rounds"],
            feedback=r["feedback"],
        )

    def count_sessions_since(self, since_date: str) -> int:
        """Count training sessions completed since a given date."""
        rows = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM session_history WHERE date >= ?", (since_date,)
        ).fetchone()
        return rows["cnt"] if rows else 0

    # ── Sessions ───────────────────────────────────────────────────

    def save_session(self, session: SessionRecord):
        self._conn.execute(
            """INSERT INTO session_history
               (session_id, date, duration_minutes, xp_earned, challenges_completed,
                quizzes_completed, reviews_completed, skills_practiced)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session.session_id, session.date, session.duration_minutes,
                session.xp_earned, session.challenges_completed,
                session.quizzes_completed, session.reviews_completed,
                session.skills_practiced,
            ),
        )
        self._conn.commit()

    def get_recent_sessions(self, limit: int = 10) -> list[SessionRecord]:
        rows = self._conn.execute(
            "SELECT * FROM session_history ORDER BY date DESC LIMIT ?", (limit,)
        ).fetchall()
        return [SessionRecord(**{k: r[k] for k in r.keys()}) for r in rows]

    # ── Conversation Log ───────────────────────────────────────────

    def log_message(self, session_id: str, role: str, content: str):
        self._conn.execute(
            "INSERT INTO conversation_log (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, datetime.now().isoformat()),
        )
        self._conn.commit()

    def get_session_log(self, session_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT role, content FROM conversation_log WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    # ── Utility ────────────────────────────────────────────────────

    def get_weakest_skills(self, limit: int = 3) -> list[SkillProgress]:
        """Get unlocked skills with lowest XP/accuracy."""
        rows = self._conn.execute(
            """SELECT * FROM skill_progress WHERE level >= 1
               ORDER BY correct_rate ASC, xp ASC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [SkillProgress(**{k: r[k] for k in r.keys()}) for r in rows]

    def get_strongest_skills(self, limit: int = 3) -> list[SkillProgress]:
        rows = self._conn.execute(
            """SELECT * FROM skill_progress WHERE level >= 1
               ORDER BY xp DESC, correct_rate DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [SkillProgress(**{k: r[k] for k in r.keys()}) for r in rows]

    def get_skills_needing_review(self, days: int = 7) -> list[SkillProgress]:
        """Skills not practiced in N days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        rows = self._conn.execute(
            """SELECT * FROM skill_progress WHERE level >= 1
               AND (last_practiced IS NULL OR last_practiced < ?)
               ORDER BY last_practiced ASC""",
            (cutoff,),
        ).fetchall()
        return [SkillProgress(**{k: r[k] for k in r.keys()}) for r in rows]

    def close(self):
        self._conn.close()
