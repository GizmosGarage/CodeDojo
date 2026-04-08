<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/anthropic-claude-6B4FBB?style=for-the-badge&logo=anthropic&logoColor=white" alt="Claude API">
  <img src="https://img.shields.io/badge/pytorch-2.0+-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white" alt="PyTorch">
  <img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="MIT License">
</p>

<h1 align="center">CodeDojo</h1>

<p align="center">
  <strong>An AI-powered Python training system that learns how you learn.</strong>
</p>

<p align="center">
  CodeDojo pairs you with Sensei — a Claude-powered coding instructor who teaches lessons,<br>
  generates challenges, reviews your solutions, and adapts to your skill level over time<br>
  using a PyTorch knowledge-tracing model trained on your own practice history.
</p>

---

## How It Works

```
 You write code          Sensei reviews it           The dojo adapts
┌──────────────┐      ┌───────────────────┐      ┌──────────────────┐
│  solution.py │ ──── │  AST validation   │ ──── │  PyTorch model   │
│  (your code) │      │  + Claude review  │      │  tracks mastery  │
└──────────────┘      └───────────────────┘      └──────────────────┘
                              │                          │
                              ▼                          ▼
                      ┌───────────────────┐      ┌──────────────────┐
                      │  Pass / feedback  │      │  Future lessons  │
                      │  with hints       │      │  tuned to you    │
                      └───────────────────┘      └──────────────────┘
```

1. **Learn** — Sensei teaches a concept with examples and a quiz.
2. **Practice** — You get a focused coding challenge for a skill you've learned.
3. **Submit** — Your code is executed, validated for required concepts, and reviewed by Sensei.
4. **Adapt** — A GRU neural network tracks your mastery, velocity, and weak spots, then feeds that assessment back into Sensei's context so future interactions are calibrated to you.
5. **Advance** — Pass belt exams to unlock new skills and progress through the curriculum.

Every learner trains their own local model from their own practice history. No data leaves your machine.

---

## Features

| Feature | Description |
|---------|-------------|
| **Structured Lessons** | Guided lessons with teaching points, code examples, and 3-question quizzes |
| **AI-Generated Challenges** | Unique practice problems tied to your learned skills, with duplicate detection |
| **Concept Validation** | AST-based checking ensures you actually use the required constructs, not just match output |
| **Adaptive Knowledge Tracing** | PyTorch GRU model predicts mastery per skill and injects guidance into Sensei's prompt |
| **Belt Progression** | Martial arts ranking system — White Belt through Yellow Belt (and growing) |
| **Belt Exams** | Multi-challenge exams that combine skills for holistic assessment |
| **Code Review** | Sensei identifies bugs by type and location but never writes code for you |
| **Dispute System** | Challenge a review if you think Sensei got it wrong |
| **Session Persistence** | Save and resume interrupted challenges and exams |
| **Skill Boundary Enforcement** | Challenges and lessons never require concepts you haven't been taught yet |

---

## Quick Start

### Prerequisites

- Python 3.10+
- An [Anthropic API key](https://console.anthropic.com/)

### Installation

```bash
git clone https://github.com/GizmosGarage/CodeDojo.git
cd CodeDojo
python -m venv .venv
```

Activate the virtual environment:

```bash
# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

> **Note:** If PyTorch needs a platform-specific install, use the [official installer](https://pytorch.org/get-started/locally/).

### Configuration

```bash
cp .env.example .env
```

Edit `.env` and add your API key:

```
ANTHROPIC_API_KEY=your-api-key-here
```

### Launch

```bash
python -m codedojo
```

---

## Commands

| Command | Description |
|---------|-------------|
| `lesson` | Learn the next skill in the curriculum |
| `challenge` | Get a practice challenge for a skill you've learned |
| `exam` | Attempt the next belt exam (when unlocked) |
| `quiz a b c` | Submit answers to a lesson quiz |
| `run` | Execute `solution.py` and see the output |
| `submit` | Execute `solution.py` and send it to Sensei for review |
| `dispute [reason]` | Ask Sensei to reconsider a failed review |
| `skills` | View your current belt, XP, and skill progress |
| `resume` | Restore a saved challenge or exam |
| `leave` | Save current challenge or exam and exit it |
| `clear` | Clear conversation history |
| `help` | Show available commands |
| `quit` | Exit the dojo |

---

## Architecture

```
codedojo/
├── main.py                 # Interactive REPL and command dispatcher
├── ai_engine.py            # Claude API integration and Sensei personality
├── challenge_gen.py         # Challenge and lesson prompt generation
├── challenge_model.py       # ChallengeSpec dataclass
├── lesson_model.py          # LessonSpec, QuizQuestion, LessonPoint dataclasses
├── code_runner.py           # Sandboxed Python execution with stdin support
├── code_validator.py        # AST-based concept detection (deterministic)
├── knowledge_tracer.py      # PyTorch GRU model for adaptive mastery prediction
├── progress.py              # Student progress, XP, belt tracking
├── session.py               # In-memory session state
├── session_persist.py       # Save/restore interrupted work
├── belt_exam.py             # Belt exam state and persistence
├── dojo_logger.py           # Event logging to JSONL
├── config.py                # Environment and constants
├── curriculum.py            # Skill tree loader
└── data/
    └── skill_tree.json      # Belt and skill definitions

tests/                       # Pytest suite (8 test modules)
```

### Key Design Decisions

- **Deterministic validation first, AI review second.** The AST validator checks for required concepts before Sensei ever sees the submission. This prevents "output matching" — where a student hardcodes the answer without using the required techniques.

- **Skill boundary enforcement at every layer.** The prompt generator, lesson system, and challenge generator all enforce that content stays within what the student has been taught. This is checked both in the AI prompt and deterministically in code.

- **Local-only learning profile.** All progress, session logs, and the trained PyTorch model stay on the user's machine. Each learner builds their own adaptive model from their own history.

- **GRU over MLP for knowledge tracing.** The knowledge tracer uses a GRU (Gated Recurrent Unit) to model temporal patterns in learning — not just "how many times did you pass" but "what's your trajectory over time."

---

## Curriculum

CodeDojo uses a belt-based progression system inspired by martial arts.

### White Belt — Python Fundamentals
Variables and assignment, basic data types, arithmetic operators, `print()`, string concatenation and f-strings, basic comparisons and boolean logic, simple math calculations.

### Yellow Belt — Control Flow and I/O
`if`/`else` conditional statements, `elif` chains, `input()` and type conversion, `while` loops, `for` loops and `range()`, string methods, `len()`.

*More belts are in active development.*

---

## How the Adaptive Model Works

```
Session Log (.jsonl)          Feature Extraction           GRU Model
┌─────────────────┐         ┌─────────────────┐        ┌──────────────┐
│ challenge_gen    │         │ success rate     │        │              │
│ submission       │  ────── │ streaks          │ ────── │  P(pass)     │
│ dispute          │         │ recency          │        │  velocity    │
│ exam results     │         │ severity history │        │  difficulty  │
│ quiz scores      │         │ concept gaps     │        │              │
└─────────────────┘         └─────────────────┘        └──────────────┘
                                                              │
                                                              ▼
                                                     ┌──────────────────┐
                                                     │ Injected into    │
                                                     │ Sensei's system  │
                                                     │ prompt as        │
                                                     │ qualitative      │
                                                     │ guidance         │
                                                     └──────────────────┘
```

The knowledge tracer reads the session log, extracts per-skill event histories, and feeds them through a GRU neural network. The output — mastery level, learning velocity, and recommended difficulty — is translated into natural language hints that become part of Sensei's context for the next interaction.

The model checkpoint is saved locally as `knowledge_model.pt` and updates as you practice.

---

## Development

### Running Tests

```bash
pytest
```

The test suite covers the REPL, challenge generation, lesson parsing, code execution, AST validation, knowledge tracing, progress tracking, and session persistence.

### Project Dependencies

| Package | Purpose |
|---------|---------|
| `anthropic` | Claude API client for Sensei |
| `python-dotenv` | Environment variable loading |
| `torch` | PyTorch for the knowledge tracing model |
| `pytest` | Test framework |

---

## Roadmap

- [ ] Green Belt curriculum (functions, lists, dictionaries)
- [ ] Blue Belt curriculum (file I/O, error handling, classes)
- [ ] Streamlit web interface
- [ ] Challenge history analytics and progress visualization
- [ ] Multi-session learning curves
- [ ] Export/import learner profiles

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
