# Changelog

All notable changes to CodeDojo are documented here.

## [0.3.0] - 2026-04-08

### Added
- **Structured lesson system** with `LessonSpec`, `QuizQuestion`, and `LessonPoint` dataclasses (`lesson_model.py`)
- **Lesson prompt generation** in `challenge_gen.py` with curriculum-order skill selection
- **Lesson boundary violation detection** to prevent Sensei from teaching future topics prematurely
- **Challenge boundary violation detection** to catch skill-scope creep in generated challenges
- **stdin support** in `code_runner.py` — challenges using `input()` now work with `test_input` fed as stdin
- **Structured lesson metadata parsing** in `ai_engine.py` — `lesson_meta` JSON blocks
- **Full lesson/quiz flow** in the REPL — `lesson` command, `quiz` answer submission, lesson-aware progression
- **`test_input` field** on `ChallengeSpec` for challenges that use `input()`
- New test modules: `test_ai_engine.py`, `test_code_runner.py`, `test_code_validator.py`

### Changed
- **Knowledge tracer upgraded from MLP to GRU** — richer temporal mastery prediction using chronological skill event histories (512 to 981 lines)
- **Code validator expanded** — broader AST-based concept detection with `SKILL_UNLOCKED_CONCEPTS` mapping and `BASELINE_ALLOWED` concepts (172 to 299 lines)
- **Challenge generation expanded** — lesson prompts, boundary checks, duplicate-aware generation (466 to 737 lines)
- **Test coverage massively expanded** — `test_knowledge_tracer` (135 to 990 lines), `test_challenge_gen` (115 to 331 lines)

## [0.2.0] - 2026-04-06

### Added
- PyTorch knowledge tracer with MLP model for adaptive mastery prediction
- Belt exam system with multi-challenge holistic grading
- Dispute flow for challenging failed reviews
- Session persistence for interrupted challenges and exams
- Event logging to JSONL for training the knowledge model
- Prompt caching with static/dynamic system prompt blocks
- Duplicate-aware challenge generation using recent history
- Concept validation with AST-based detection before AI review

### Changed
- Rebuilt as a Python CLI application (replaced earlier prototype)
- System prompt dynamically built from student progress
- Challenge generation enforces skill boundary rules

## [0.1.0] - 2026-03-26

### Added
- Initial CodeDojo prototype
- Basic REPL with challenge and submit commands
- Claude integration for code review
- Simple progress tracking with XP and belt levels
