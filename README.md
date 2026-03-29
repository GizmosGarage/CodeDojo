# CodeDojo

CodeDojo is a Python CLI training app that acts like a coding sensei. It teaches small Python lessons, generates focused practice challenges, runs your `solution.py`, and reviews your work with AI feedback while tracking progress locally.

## What Changed From The Old Repo

This repository now tracks the newer Python-first CodeDojo implementation from the current local project. The earlier Electron desktop app and its legacy Python modules have been removed in favor of the newer CLI workflow in `codedojo/`.

## Features

- Guided lessons on foundational Python topics
- Three-question quizzes after each lesson
- AI-generated practice challenges tied to learned skills
- Local code execution through `solution.py`
- Automated concept validation before AI review
- Local progress, challenge, and session tracking
- Resume support for interrupted challenges

## Requirements

- Python 3.10+
- An Anthropic API key

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the repository root:

```env
ANTHROPIC_API_KEY=your-api-key-here
```

Then run the dojo:

```bash
python -m codedojo
```

## Basic Commands

- `lesson` starts a new lesson and quiz
- `challenge` generates a challenge for a learned skill
- `quiz a b c` submits quiz answers
- `run` executes `solution.py`
- `submit` sends `solution.py` for review
- `skills` shows your current progress
- `leave` saves an in-progress challenge
- `resume` restores a saved challenge
- `clear` clears the current conversation history
- `quit` exits the dojo

## Project Layout

```text
codedojo/
  ai_engine.py
  challenge_gen.py
  challenge_model.py
  code_runner.py
  code_validator.py
  config.py
  curriculum.py
  dojo_logger.py
  main.py
  progress.py
  session.py
  session_persist.py
  data/
    skill_tree.json
```

## Notes

- `solution.py` is intentionally ignored because it is your practice file.
- Progress and session logs are stored locally under `codedojo/data/` and are not committed.
- The app currently targets a CLI workflow instead of the older desktop UI.
