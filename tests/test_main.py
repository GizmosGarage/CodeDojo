from codedojo.challenge_model import ChallengeSpec
from codedojo.challenge_gen import WHITE_BELT_SKILLS
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
