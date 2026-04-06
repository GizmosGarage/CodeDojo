# CodeDojo

CodeDojo is a Python CLI training app built around a PyTorch-powered ML Sensei. It teaches Python, gives you coding drills, reviews your solutions with AI feedback, and trains a local knowledge-tracing model over time so the dojo can adapt to how you actually learn.

## Why This Version Matters

This repository intentionally keeps the same project lineage instead of starting over from scratch.

- The earliest version of CodeDojo in this repo was a desktop-oriented prototype.
- The next major version rebuilt the project as a Python-first CLI dojo.
- This newest version is defined by the addition of a PyTorch knowledge tracer that models learner progress and feeds adaptive guidance back into the Sensei workflow.

The git history shows how CodeDojo evolved, and the current working tree reflects the PyTorch ML Sensei version of the project.

## PyTorch ML Sensei

The key architectural change in this version lives in `codedojo/knowledge_tracer.py`.

- It uses PyTorch to run a small MLP that predicts mastery, learning velocity, and recommended difficulty per skill.
- It learns from the student's local lesson results, challenge attempts, practice streaks, and review outcomes.
- It parses `codedojo/data/session_log.jsonl` so the training signal comes from real dojo interactions.
- It saves its evolving checkpoint locally as `codedojo/data/knowledge_model.pt`.
- It turns those predictions into qualitative guidance that gets injected into the Sensei system prompt, making future lessons and reviews more adaptive.

In other words, this version is not just "CodeDojo with more commands." It is the version where CodeDojo starts learning about the learner.

## What Users Get

- Guided lessons on foundational Python topics
- Three-question quizzes after each lesson
- AI-generated challenges tied to learned skills
- Duplicate-aware challenge generation to avoid stale repeats
- Belt exam progression once a belt's lessons are unlocked
- Local code execution through `solution.py`
- Concept validation before AI review
- Review dispute flow when Sensei gets a submission wrong
- Resume support for interrupted challenges and in-progress exams
- Local progress, challenge history, session logs, and PyTorch knowledge-tracing state
- Pytest coverage for core CLI and persistence behavior

## Requirements

- Python 3.10+
- An Anthropic API key

## Install And Run

1. Clone the repository.
2. Create and activate a virtual environment.
3. Install the dependencies, including PyTorch.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

If PyTorch needs a platform-specific install command for your machine, use the official PyTorch install selector: [pytorch.org/get-started/locally](https://pytorch.org/get-started/locally/).

4. Copy `.env.example` to `.env` and add your Anthropic API key.

```env
ANTHROPIC_API_KEY=your-api-key-here
```

5. Start the dojo.

```bash
python -m codedojo
```

6. Begin with `lesson`, then move into `challenge`, `submit`, and eventually `exam` as your belt progresses.

Run the tests with:

```bash
pytest
```

## How The Local Training Loop Works

1. You complete lessons and practice challenges.
2. CodeDojo logs challenge generation, submissions, and dispute outcomes locally.
3. The PyTorch knowledge tracer extracts features like success rate, streaks, quiz performance, practice recency, and belt level.
4. The model updates its local understanding of your mastery and momentum.
5. That assessment is fed back into the Sensei context so the dojo can better tune future interactions.

This means each user can clone the repo, use it on their own machine, and build up their own local training history without needing a shared central learner profile.

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
- Each learner trains their own local Sensei profile from their own activity history.
