# Contributing to CodeDojo

Thanks for your interest in contributing to CodeDojo.

## Getting Started

1. Fork the repository and clone your fork.
2. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and add your Anthropic API key.

## Development Workflow

1. Create a branch for your work:

```bash
git checkout -b your-feature-name
```

2. Make your changes.
3. Run the test suite:

```bash
pytest
```

4. Commit your changes with a clear message describing what and why.
5. Open a pull request against `main`.

## Guidelines

- **Run tests before submitting.** All existing tests must pass.
- **Keep changes focused.** One feature or fix per PR.
- **Follow existing patterns.** The codebase has consistent conventions for how modules interact, how prompts are structured, and how tests are organized. Match them.
- **Don't commit learner data.** Files like `progress.json`, `session_log.jsonl`, and `knowledge_model.pt` are gitignored for a reason.
- **Don't commit API keys.** Use `.env` for secrets. Never commit `.env`.

## Adding a New Belt

If you're contributing curriculum content:

1. Add skill definitions to `codedojo/data/skill_tree.json`.
2. Add skill-to-concept mappings in `code_validator.py` (`SKILL_UNLOCKED_CONCEPTS`).
3. Add the belt's skill list in `challenge_gen.py`.
4. Write tests for any new boundary rules or parsing logic.

## Reporting Issues

Open an issue on GitHub with:

- What you expected to happen
- What actually happened
- Steps to reproduce
- Your Python version and OS
