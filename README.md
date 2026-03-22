# 🥋 CodeDojo

**Sharpen Your Python Blade.**

CodeDojo is an AI-powered CLI training tool that acts as your personal coding sensei. It evaluates your skills, tracks your progress, and adaptively trains you through quizzes, coding challenges, and code reviews — all with the personality of a strict but wise martial arts master.

## Features

- **Skill Assessment** — Initial evaluation places you at the right rank
- **Belt Ranking System** — Progress from White Belt ⬜ to Black Belt ⬛ with XP
- **Adaptive Training** — Sensei recommends what to practice based on your weaknesses
- **Live Coding Challenges** — Write real code, tested against real test cases
- **Multiple Choice Quizzes** — Test your Python knowledge across the skill tree
- **Code Review** — Submit any code and get detailed sensei feedback
- **Skill Tree** — 40+ skills across 10 branches, from fundamentals to design patterns
- **Progress Tracking** — Streaks, accuracy stats, session history, all stored locally
- **Mr. Miyagi Personality** — Strict but wise, never gives away answers

## Quick Start

### Prerequisites

- Python 3.10+
- An Anthropic API key

### Installation

```bash
# Clone or download the project
cd codedojo

# Install dependencies
pip install -r requirements.txt

# Set your API key
export ANTHROPIC_API_KEY="your-api-key-here"

# Run the dojo
python -m codedojo
```

Or install as a CLI tool:

```bash
pip install -e .
codedojo
```

### First Run

1. Sensei greets you and asks your name
2. You take an 8-question skill assessment
3. Based on your score, you're placed at an appropriate belt rank
4. Relevant skills are unlocked in your skill tree
5. Training begins!

## How It Works

### Session Flow

```
Launch → Sensei Greeting → Choose Activity:
├── 🥋 Train (Sensei Recommends) → Pick session length → Quiz + Challenge
├── 🌳 Choose from Skill Tree → Pick branch → Pick skill → Train
├── 📝 Submit Code for Review → Paste code → Get feedback
├── 📊 View Progress → Stats, skill tree, XP bar
├── 💬 Talk to Sensei → Free conversation
└── 🚪 Leave the Dojo → Session summary + farewell
```

### Belt Ranks

| Belt | Icon | XP Required |
|------|------|-------------|
| White Belt | ⬜ | 0 |
| Yellow Belt | 🟡 | 100 |
| Orange Belt | 🟠 | 300 |
| Green Belt | 🟢 | 600 |
| Blue Belt | 🔵 | 1,000 |
| Purple Belt | 🟣 | 1,500 |
| Brown Belt | 🟤 | 2,200 |
| Black Belt | ⬛ | 3,000 |

### Skill Tree Branches

- 🌱 **Fundamentals** — Variables, control flow, functions, strings, file I/O
- 🏗️ **Data Structures** — Lists, dicts, sets, comprehensions, collections
- ⚔️ **Algorithms** — Searching, sorting, recursion, dynamic programming, Big-O
- 🏛️ **OOP** — Classes, inheritance, dunder methods, properties, SOLID
- 🌀 **Functional** — Lambdas, decorators, generators, closures
- 🛡️ **Error Handling** — Exceptions, custom exceptions, context managers
- 🧪 **Testing** — Unit tests, pytest, mocking, TDD
- ⚡ **Async & Concurrency** — Threading, asyncio, multiprocessing
- 🎯 **Design Patterns** — Creational, structural, behavioral

### XP Rewards

| Activity | XP |
|----------|-----|
| Quiz correct answer | +10 |
| Quiz wrong answer | +2 |
| Challenge passed | +30 |
| Challenge partial | +15 |
| Code review | +10-30 |
| Daily streak bonus | +5/day (max 50) |

## Data Storage

All progress is stored locally in `~/.codedojo/dojo.db` (SQLite). No cloud, no accounts, fully portable.

To reset your progress:
```bash
rm -rf ~/.codedojo
```

## Architecture

```
codedojo/
├── __init__.py          # Package init
├── __main__.py          # Entry point
├── cli.py               # Main CLI loop & session management
├── sensei.py            # Claude API integration & personality
├── storage.py           # SQLite persistence layer
├── models.py            # Data models
├── config.py            # Constants, belts, skill tree definition
├── display.py           # Rich terminal UI
├── ranking.py           # Belt/XP progression system
├── skill_tree.py        # Skill tree logic & recommendations
├── challenges.py        # Code execution engine
└── assessment.py        # Initial skill assessment
```

## License

MIT
