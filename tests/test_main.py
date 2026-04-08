from codedojo.challenge_model import ChallengeSpec
from codedojo.challenge_gen import WHITE_BELT_SKILLS, YELLOW_BELT_SKILLS
from codedojo.progress import Progress
from codedojo.session import Session
from codedojo.main import build_dispute_prompt
import codedojo.main as main_module


def test_build_dispute_prompt_includes_reasoning_and_previous_review():
    prompt = build_dispute_prompt(
        "You did not demonstrate the data types clearly.\n[NEEDS_WORK:minor]",
        "I created one int, one float, one str, and one bool and printed each with labels.",
    )

    assert "Student rebuttal:" in prompt
    assert "I created one int" in prompt
    assert "Your previous review was:" in prompt
    assert "[NEEDS_WORK:minor]" in prompt
    assert "correct yourself clearly" in prompt


def test_new_from_interrupted_challenge_starts_challenge_selection(monkeypatch, capsys):
    class DummyEngine:
        def __init__(self, *args, **kwargs):
            pass

    class DummyLogger:
        def log_session_start(self):
            pass

        def log_session_end(self):
            pass

        def close(self):
            pass

    def seed_progress(self, path):
        self.skills_taught = list(WHITE_BELT_SKILLS)

    interrupted = {
        "challenge": ChallengeSpec(
            challenge_id="abc12345",
            skill="variables and assignment",
            title="Inventory Manager",
            required_concepts=["variable assignment", "print()"],
            expected_behavior="Print the updated inventory values.",
            narrative="Resume this inventory kata.",
        ),
        "attempt_count": 1,
        "phase": "challenge",
        "skill": "variables and assignment",
    }

    inputs = iter(["challenge", "new", "back", "quit"])

    monkeypatch.setattr(main_module.config, "validate_config", lambda: None)
    monkeypatch.setattr(main_module, "AIEngine", DummyEngine)
    monkeypatch.setattr(main_module, "DojoLogger", lambda path: DummyLogger())
    monkeypatch.setattr(main_module.Progress, "load", seed_progress)
    monkeypatch.setattr(
        main_module.Progress,
        "import_challenge_history_from_log",
        lambda self, path: None,
    )
    monkeypatch.setattr(main_module, "clear_interrupted_challenge", lambda path: None)
    monkeypatch.setattr(
        main_module.Session,
        "get_interrupted_snapshot",
        lambda self, path: interrupted,
    )
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    main_module.main()
    output = capsys.readouterr().out

    assert 'You have an unfinished challenge: "Inventory Manager" (variables and assignment)' in output
    assert "Choose a skill to practice:" in output
    assert "You've covered all White Belt topics! Practice with 'challenge'." not in output


def test_exam_requires_all_lessons_to_be_unlocked(monkeypatch, capsys):
    class DummyEngine:
        def __init__(self, *args, **kwargs):
            pass

    class DummyLogger:
        def log_session_start(self):
            pass

        def log_session_end(self):
            pass

        def close(self):
            pass

    def seed_progress(self, path):
        self.skills_taught = list(WHITE_BELT_SKILLS[:-1])

    inputs = iter(["exam", "quit"])

    monkeypatch.setattr(main_module.config, "validate_config", lambda: None)
    monkeypatch.setattr(main_module, "AIEngine", DummyEngine)
    monkeypatch.setattr(main_module, "DojoLogger", lambda path: DummyLogger())
    monkeypatch.setattr(main_module.Progress, "load", seed_progress)
    monkeypatch.setattr(
        main_module.Progress,
        "import_challenge_history_from_log",
        lambda self, path: None,
    )
    monkeypatch.setattr(
        main_module.Session,
        "get_interrupted_snapshot",
        lambda self, path: None,
    )
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    main_module.main()
    output = capsys.readouterr().out

    assert "exam unlocks once all lessons are unlocked" in output
    assert "Remaining lessons:" in output


def test_challenge_menu_groups_skills_by_belt(monkeypatch, capsys):
    class DummyEngine:
        def __init__(self, *args, **kwargs):
            pass

    class DummyLogger:
        def log_session_start(self):
            pass

        def log_session_end(self):
            pass

        def close(self):
            pass

    def seed_progress(self, path):
        self.skills_taught = list(WHITE_BELT_SKILLS) + [YELLOW_BELT_SKILLS[0]]

    inputs = iter(["challenge", "back", "quit"])

    monkeypatch.setattr(main_module.config, "validate_config", lambda: None)
    monkeypatch.setattr(main_module, "AIEngine", DummyEngine)
    monkeypatch.setattr(main_module, "DojoLogger", lambda path: DummyLogger())
    monkeypatch.setattr(main_module.Progress, "load", seed_progress)
    monkeypatch.setattr(
        main_module.Progress,
        "import_challenge_history_from_log",
        lambda self, path: None,
    )
    monkeypatch.setattr(
        main_module.Session,
        "get_interrupted_snapshot",
        lambda self, path: None,
    )
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    main_module.main()
    output = capsys.readouterr().out

    white_header = output.index("  White Belt:")
    yellow_header = output.index("  Yellow Belt:")
    white_skill = output.index(f"1. {WHITE_BELT_SKILLS[0]}")
    yellow_skill = output.index(f"8. {YELLOW_BELT_SKILLS[0]}")

    assert "Choose a skill to practice:" in output
    assert white_header < white_skill < yellow_header < yellow_skill


def test_challenge_menu_selection_uses_grouped_skill_order(monkeypatch):
    class DummyEngine:
        def __init__(self, *args, **kwargs):
            pass

    class DummyLogger:
        def log_session_start(self):
            pass

        def log_session_end(self):
            pass

        def close(self):
            pass

    def seed_progress(self, path):
        self.skills_taught = [YELLOW_BELT_SKILLS[0], WHITE_BELT_SKILLS[0], WHITE_BELT_SKILLS[1]]

    chosen = {}

    def fake_handle_challenge_generate(engine, session, logger, progress, skill):
        chosen["skill"] = skill
        print(f"SELECTED:{skill}")

    inputs = iter(["challenge", "3", "quit"])

    monkeypatch.setattr(main_module.config, "validate_config", lambda: None)
    monkeypatch.setattr(main_module, "AIEngine", DummyEngine)
    monkeypatch.setattr(main_module, "DojoLogger", lambda path: DummyLogger())
    monkeypatch.setattr(main_module.Progress, "load", seed_progress)
    monkeypatch.setattr(
        main_module.Progress,
        "import_challenge_history_from_log",
        lambda self, path: None,
    )
    monkeypatch.setattr(
        main_module.Session,
        "get_interrupted_snapshot",
        lambda self, path: None,
    )
    monkeypatch.setattr(main_module, "handle_challenge_generate", fake_handle_challenge_generate)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    main_module.main()

    assert chosen["skill"] == YELLOW_BELT_SKILLS[0]


def test_handle_lesson_retries_malformed_response_and_keeps_answers_hidden(capsys):
    class DummyEngine:
        def __init__(self):
            self.calls = 0

        def send_message(self, conversation_history, user_message, interaction_type="chat"):
            self.calls += 1
            conversation_history.append({"role": "user", "content": user_message})
            if self.calls == 1:
                response = """```lesson_meta
{
  "title": "Broken lesson",
  "summary": "This response is cut off"
"""
            else:
                response = """```lesson_meta
{
  "title": "Conditional Logic with if/else Statements",
  "summary": "Use if and else to make your program choose between paths.",
  "points": [
    {
      "title": "Basic if",
      "explanation": "An if block runs when its condition is True.",
      "example": "temperature = 75\\nif temperature > 70:\\n    print(\\"Warm\\")"
    },
    {
      "title": "Else fallback",
      "explanation": "Else runs when the if condition is False.",
      "example": "age = 16\\nif age >= 18:\\n    print(\\"Adult\\")\\nelse:\\n    print(\\"Minor\\")"
    },
    {
      "title": "Compare values inside conditions",
      "explanation": "Conditions often compare numbers or strings before choosing a branch.",
      "example": "score = 85\\nif score > 80:\\n    print(\\"Nice work\\")\\nelse:\\n    print(\\"Keep practicing\\")"
    }
  ],
  "quiz": [
    {
      "question": "What prints when number is 15?",
      "code": "number = 15\\nif number > 10:\\n    print(\\"Big\\")\\nelse:\\n    print(\\"Small\\")",
      "options": ["Big", "Small", "Nothing"],
      "answer": "a"
    },
    {
      "question": "What happens if an if condition is False with no else?",
      "code": "",
      "options": ["Crash", "Error", "The block is skipped"],
      "answer": "c"
    },
    {
      "question": "Which operator checks equality?",
      "code": "",
      "options": ["=", "==", "!="],
      "answer": "b"
    }
  ]
}
```"""
            conversation_history.append({"role": "assistant", "content": response})
            return response

    class DummyLogger:
        def __init__(self):
            self.errors = []

        def log_error(self, error_type, context):
            self.errors.append((error_type, context))

    engine = DummyEngine()
    logger = DummyLogger()
    session = Session()
    progress = Progress()
    progress.belt = "yellow"
    progress.skills_taught = list(WHITE_BELT_SKILLS)

    main_module.handle_lesson(engine, session, logger, progress)
    output = capsys.readouterr().out

    assert engine.calls == 2
    assert session.phase == "quiz"
    assert session.quiz_answers == ["a", "c", "b"]
    assert len(session.conversation_history) == 2
    assert "lesson_meta" not in output
    assert '"answer": "a"' not in output
    assert "Answer the quiz: quiz [your answers]" in output
    assert not logger.errors


def test_handle_lesson_retries_when_future_lesson_topic_leaks(capsys):
    class DummyEngine:
        def __init__(self):
            self.calls = 0

        def send_message(self, conversation_history, user_message, interaction_type="chat"):
            self.calls += 1
            conversation_history.append({"role": "user", "content": user_message})
            if self.calls == 1:
                response = """```lesson_meta
{
  "title": "Conditional Logic with if/else Statements",
  "summary": "Use if, elif, and else to make your program choose between paths.",
  "points": [
    {
      "title": "Basic if",
      "explanation": "An if block runs when its condition is True.",
      "example": "temperature = 75\\nif temperature > 70:\\n    print(\\"Warm\\")"
    },
    {
      "title": "Else fallback",
      "explanation": "Else runs when the if condition is False.",
      "example": "age = 16\\nif age >= 18:\\n    print(\\"Adult\\")\\nelse:\\n    print(\\"Minor\\")"
    },
    {
      "title": "Elif chain",
      "explanation": "Elif checks another condition after if.",
      "example": "score = 85\\nif score >= 90:\\n    print(\\"A\\")\\nelif score >= 80:\\n    print(\\"B\\")\\nelse:\\n    print(\\"C\\")"
    }
  ],
  "quiz": [
    {
      "question": "What prints when number is 15?",
      "code": "number = 15\\nif number > 10:\\n    print(\\"Big\\")\\nelse:\\n    print(\\"Small\\")",
      "options": ["Big", "Small", "Nothing"],
      "answer": "a"
    },
    {
      "question": "What happens if an if condition is False with no else?",
      "code": "",
      "options": ["Crash", "Error", "The block is skipped"],
      "answer": "c"
    },
    {
      "question": "Which operator checks equality?",
      "code": "",
      "options": ["=", "==", "!="],
      "answer": "b"
    }
  ]
}
```"""
            else:
                response = """```lesson_meta
{
  "title": "Conditional Logic with if/else Statements",
  "summary": "Use if and else to make your program choose between paths.",
  "points": [
    {
      "title": "Basic if",
      "explanation": "An if block runs when its condition is True.",
      "example": "temperature = 75\\nif temperature > 70:\\n    print(\\"Warm\\")"
    },
    {
      "title": "Else fallback",
      "explanation": "Else runs when the if condition is False.",
      "example": "age = 16\\nif age >= 18:\\n    print(\\"Adult\\")\\nelse:\\n    print(\\"Minor\\")"
    },
    {
      "title": "Compare values inside conditions",
      "explanation": "Conditions often compare numbers or strings before choosing a branch.",
      "example": "score = 85\\nif score > 80:\\n    print(\\"Nice work\\")\\nelse:\\n    print(\\"Keep practicing\\")"
    }
  ],
  "quiz": [
    {
      "question": "What prints when number is 15?",
      "code": "number = 15\\nif number > 10:\\n    print(\\"Big\\")\\nelse:\\n    print(\\"Small\\")",
      "options": ["Big", "Small", "Nothing"],
      "answer": "a"
    },
    {
      "question": "What happens if an if condition is False with no else?",
      "code": "",
      "options": ["Crash", "Error", "The block is skipped"],
      "answer": "c"
    },
    {
      "question": "Which operator checks equality?",
      "code": "",
      "options": ["=", "==", "!="],
      "answer": "b"
    }
  ]
}
```"""
            conversation_history.append({"role": "assistant", "content": response})
            return response

    class DummyLogger:
        def __init__(self):
            self.errors = []

        def log_error(self, error_type, context):
            self.errors.append((error_type, context))

    engine = DummyEngine()
    logger = DummyLogger()
    session = Session()
    progress = Progress()
    progress.belt = "yellow"
    progress.skills_taught = list(WHITE_BELT_SKILLS)

    main_module.handle_lesson(engine, session, logger, progress)
    output = capsys.readouterr().out

    assert engine.calls == 2
    assert session.phase == "quiz"
    assert "elif" not in output.lower()
    assert session.quiz_answers == ["a", "c", "b"]
    assert not logger.errors
