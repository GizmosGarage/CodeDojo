import json
from dataclasses import asdict
from pathlib import Path

from codedojo.challenge_model import ChallengeSpec


def save_interrupted_challenge(
    path: Path,
    spec: ChallengeSpec,
    attempt_count: int,
    phase: str,
    skill: str | None,
) -> None:
    data = {
        "challenge": asdict(spec),
        "attempt_count": attempt_count,
        "phase": phase,
        "skill": skill,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_interrupted_challenge(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["challenge"] = ChallengeSpec(**data["challenge"])
        return data
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def clear_interrupted_challenge(path: Path) -> None:
    if path.exists():
        path.unlink()
