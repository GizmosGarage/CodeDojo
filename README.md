# CodeDojo

CodeDojo is a Python CLI training app that acts like a coding sensei. It teaches focused Python lessons, turns them into practice challenges, runs your `solution.py`, reviews submissions with AI feedback, and tracks progress locally as you move through belt levels.

## Project Evolution

This repository intentionally keeps the same project lineage instead of starting over from scratch.

- The earliest version of CodeDojo in this repo was a desktop-oriented prototype.
- The next major version rebuilt the project as a Python-first CLI dojo.
- The current version extends that CLI foundation with belt exams, adaptive knowledge tracing, stronger persistence, richer review flows, and automated tests.

That means the git history shows how CodeDojo evolved, while the current working tree reflects the latest training system.

## Current Features

- Guided lessons on foundational Python topics
- Three-question quizzes after each lesson
- AI-generated challenges tied to learned skills
- Duplicate-aware challenge generation to avoid stale repeats
- Belt exam progression once a belt's lessons are unlocked
- Local code execution through `solution.py`
- Concept validation before AI review
- Review dispute flow when Sensei gets a submission wrong
- Resume support for interrupted challenges and in-progress exams
- Local progress, challenge history, session logs, and knowledge-tracing state
- Pytest coverage for core CLI and progress behavior

## Requirements

- Python 3.10+
- An Anthropic API key

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the repository root. You can use `.env.example` as the starting point:

```env
ANTHROPIC_API_KEY=your-api-key-here
```

Then run the dojo:

```bash
python -m codedojo
```

Run the tests with:

```bash
pytest
```

## Basic Commands

- `lesson` starts a new lesson and quiz
- `challenge` lets you choose a learned skill and generates a practice challenge
- `exam` starts or resumes the next belt exam when unlocked
- `quiz a b c` submits quiz answers
- `run` executes `solution.py`
- `submit` sends `solution.py` for review
- `dispute [reason]` asks Sensei to reconsider a failed review
- `skills` shows your current progress
- `leave` saves an in-progress challenge or exam
- `resume` restores a saved challenge
- `clear` clears the current conversation history
- `quit` exits the dojo

## Project Layout

```text
codedojo/
  ai_engine.py
  belt_exam.py
  challenge_gen.py
  challenge_model.py
  code_runner.py
  code_validator.py
  config.py
  curriculum.py
  dojo_logger.py
  knowledge_tracer.py
  main.py
  progress.py
  session.py
  session_persist.py
  data/
    skill_tree.json
tests/
  ...
```

## Repository Notes

- `solution.py` is intentionally ignored because it is your practice file.
- Generated learner state under `codedojo/data/` stays local and is not committed.
- `codedojo/data/skill_tree.json` is committed because it is part of the curriculum definition.
- The knowledge tracer creates `knowledge_model.pt` locally as you build up session history.
