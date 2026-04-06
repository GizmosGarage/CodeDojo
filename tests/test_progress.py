from datetime import datetime, timedelta, timezone
import json

from codedojo.challenge_gen import WHITE_BELT_SKILLS
from codedojo.progress import Progress


def test_skill_progress_label_uses_compact_challenge_counts():
    progress = Progress()
    progress.record_lesson("variables and assignment", 3, 3, [])
    progress.record_attempt("variables and assignment", "abc12345", passed=True)
    progress.record_attempt("variables and assignment", "def67890", passed=False)

    assert progress.skill_progress_label("variables and assignment") == "Practiced (1/2)"


def test_skill_progress_label_for_lesson_only_skill():
    progress = Progress()
    progress.record_lesson("print() function", 2, 3, [1])

    assert progress.skill_progress_label("print() function") == "Learned (lesson 2/3)"


def test_omit_failed_attempt_removes_overturned_review_from_progress():
    progress = Progress()
    progress.record_lesson("basic data types (int, float, str, bool)", 3, 3, [])
    progress.record_attempt("basic data types (int, float, str, bool)", "abc12345", passed=False)

    progress.omit_failed_attempt("basic data types (int, float, str, bool)")
    progress.record_attempt("basic data types (int, float, str, bool)", "abc12345", passed=True)

    record = progress.skills["basic data types (int, float, str, bool)"]
    assert record.attempts == 1
    assert record.successes == 1
    assert progress.xp == 50


def test_find_similar_challenge_matches_saved_history():
    progress = Progress()
    progress.record_generated_challenge(
        skill="simple math calculations",
        challenge_id="abc12345",
        title="Coin Counter",
        expected_behavior="Print the total value of three coins in dollars.",
        required_concepts=["float()", "print()", "+"],
    )

    similar = progress.find_similar_challenge(
        skill="simple math calculations",
        title="Coin Counter",
        expected_behavior="Print the total value of three coins in dollars.",
        required_concepts=["float()", "print()", "+"],
    )

    assert similar is not None
    assert similar.challenge_id == "abc12345"


def test_legacy_concept_only_history_does_not_block_new_challenge(tmp_path):
    log_path = tmp_path / "session_log.jsonl"
    log_entry = {
        "timestamp": "2026-04-03T12:00:00+00:00",
        "event": "challenge_generated",
        "challenge_id": "log12345",
        "skill": "basic data types (int, float, str, bool)",
        "requirements": ["int", "float", "str", "bool", "type()", "print()"],
    }
    log_path.write_text(json.dumps(log_entry) + "\n", encoding="utf-8")

    progress = Progress()
    progress.import_challenge_history_from_log(log_path)

    similar = progress.find_similar_challenge(
        skill="basic data types (int, float, str, bool)",
        title="Fresh Title",
        expected_behavior="A different sounding description.",
        required_concepts=["int", "float", "str", "bool", "type()", "print()"],
    )

    assert similar is None


def test_import_challenge_history_from_log_still_backfills_entries(tmp_path):
    log_path = tmp_path / "session_log.jsonl"
    log_entry = {
        "timestamp": "2026-04-03T12:00:00+00:00",
        "event": "challenge_generated",
        "challenge_id": "log12345",
        "skill": "basic data types (int, float, str, bool)",
        "requirements": ["int", "float", "str", "bool", "type()", "print()"],
    }
    log_path.write_text(json.dumps(log_entry) + "\n", encoding="utf-8")

    progress = Progress()
    progress.import_challenge_history_from_log(log_path)

    recent = progress.get_recent_challenge_descriptors("basic data types (int, float, str, bool)")

    assert len(recent) == 1
    assert recent[0]["required_concepts"] == ["int", "float", "str", "bool", "type()", "print()"]


def test_save_and_load_preserve_challenge_history(tmp_path):
    progress = Progress()
    progress.record_lesson("print() function", 3, 3, [])
    progress.record_generated_challenge(
        skill="print() function",
        challenge_id="save1234",
        title="Banner Blast",
        expected_behavior="Print a short event banner.",
        required_concepts=["print()", "sep parameter"],
    )

    path = tmp_path / "progress.json"
    progress.save(path)

    loaded = Progress()
    loaded.load(path)

    recent = loaded.get_recent_challenge_descriptors("print() function")
    assert recent[0]["title"] == "Banner Blast"
    assert recent[0]["required_concepts"] == ["print()", "sep parameter"]


def test_belt_exam_unlock_and_daily_limit():
    progress = Progress()
    test_now = datetime(2026, 4, 6, 9, 0, tzinfo=timezone(timedelta(hours=-4)))

    assert not progress.has_unlocked_belt_exam(WHITE_BELT_SKILLS)

    for skill in WHITE_BELT_SKILLS:
        progress.record_lesson(skill, 3, 3, [])

    assert progress.has_unlocked_belt_exam(WHITE_BELT_SKILLS)
    assert progress.belt_exam_attempts_remaining(3, now=test_now) == 3

    progress.record_belt_exam_attempt(now=test_now)
    progress.record_belt_exam_attempt(now=test_now)
    progress.record_belt_exam_attempt(now=test_now)

    assert progress.belt_exam_attempts_today(now=test_now) == 3
    assert progress.belt_exam_attempts_remaining(3, now=test_now) == 0
    assert not progress.can_start_belt_exam(WHITE_BELT_SKILLS, 3, now=test_now)

    tomorrow = test_now + timedelta(days=1)
    assert progress.belt_exam_attempts_today(now=tomorrow) == 0
    assert progress.belt_exam_attempts_remaining(3, now=tomorrow) == 3


def test_save_and_load_preserve_belt_exam_attempts(tmp_path):
    progress = Progress()
    test_now = datetime(2026, 4, 6, 9, 0, tzinfo=timezone(timedelta(hours=-4)))
    progress.record_belt_exam_attempt(now=test_now)

    path = tmp_path / "progress.json"
    progress.save(path)

    loaded = Progress()
    loaded.load(path)

    assert loaded.belt_exam_attempts_today(now=test_now) == 1
