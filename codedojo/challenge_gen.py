import json
import random
import re
import uuid

from codedojo.challenge_model import ChallengeSpec

_QUIZ_ANSWERS_PATTERN = re.compile(r"```quiz_answers\s*\n?(.*?)\n?\s*```", re.DOTALL)
_STRIP_QUIZ_META_PATTERN = re.compile(r"```quiz_answers\s*\n?.*?\n?\s*```", re.DOTALL)
_CHALLENGE_META_PATTERN = re.compile(r"```challenge_meta\s*\n?(.*?)\n?\s*```", re.DOTALL)


class NoNewSkillsError(Exception):
    """Raised when all skills in the belt have been taught."""
    pass

WHITE_BELT_SKILLS = [
    "variables and assignment",
    "basic data types (int, float, str, bool)",
    "arithmetic operators (+, -, *, /, //, %, **)",
    "print() function",
    "string concatenation and f-strings",
    "basic comparisons and boolean logic",
    "simple math calculations",
]


def get_lesson_prompt(
    skill: str | None = None,
    available_skills: list[str] | None = None,
) -> tuple[str, str]:
    """Return (prompt_for_sensei, chosen_skill) for a lesson + quiz."""
    if skill:
        chosen = skill
    elif available_skills is not None:
        if not available_skills:
            raise NoNewSkillsError("All skills in this belt have been taught.")
        chosen = random.choice(available_skills)
    else:
        chosen = random.choice(WHITE_BELT_SKILLS)
    prompt = (
        f"Sensei, please teach me a quick lesson about: {chosen}\n\n"
        "Keep it brief and focused — 3-5 key points maximum. "
        "Use a short concrete example for each point. "
        "At the end, include a multiple-choice quiz with exactly 3 questions "
        "to check understanding.\n\n"
        "Format the quiz as:\n\n"
        "QUIZ:\n"
        "1. [Question]\n"
        "   a) [option]\n   b) [option]\n   c) [option]\n\n"
        "2. [Question]\n"
        "   a) [option]\n   b) [option]\n   c) [option]\n\n"
        "3. [Question]\n"
        "   a) [option]\n   b) [option]\n   c) [option]\n\n"
        "After the quiz questions, include a JSON block delimited by "
        "```quiz_answers and ``` containing:\n"
        '- "answers": list of correct letters, e.g. ["b", "a", "c"]\n'
        "Place this block at the very END of your response."
    )
    return prompt, chosen


def parse_quiz_answers(response: str) -> list[str]:
    """Extract correct quiz answers from the quiz_answers JSON block."""
    match = _QUIZ_ANSWERS_PATTERN.search(response)
    if match:
        try:
            meta = json.loads(match.group(1).strip())
            return meta.get("answers", [])
        except json.JSONDecodeError:
            pass
    return []


def strip_quiz_meta(response: str) -> str:
    """Remove the quiz_answers JSON block from display text."""
    return _STRIP_QUIZ_META_PATTERN.sub("", response).rstrip()


def get_challenge_prompt(skill: str | None = None) -> tuple[str, str]:
    """Return (prompt_for_sensei, chosen_skill)."""
    chosen = skill if skill else random.choice(WHITE_BELT_SKILLS)
    prompt = (
        f"Sensei, please give me a coding challenge focused on: {chosen}\n\n"
        "IMPORTANT: You MUST include a JSON metadata block in your response, "
        "delimited by ```challenge_meta and ```. The block must contain:\n"
        '- "title": short challenge title\n'
        '- "required_concepts": list of specific Python functions or constructs '
        "the student MUST use (e.g. [\"round()\", \"f-string\", \"float()\"])\n"
        '- "expected_behavior": one sentence describing what correct output looks like\n\n'
        "Place this block at the END of your response. Then write the challenge "
        "narrative for the student above it."
    )
    return prompt, chosen


def parse_challenge_response(raw_response: str, skill: str) -> ChallengeSpec:
    """Extract structured metadata from Sensei's challenge response.

    Falls back gracefully if the JSON block is missing or malformed.
    """
    challenge_id = uuid.uuid4().hex[:8]

    match = _CHALLENGE_META_PATTERN.search(raw_response)

    if match:
        try:
            meta = json.loads(match.group(1).strip())
            # Strip the JSON block from the narrative shown to student
            narrative = raw_response[: match.start()].rstrip()
            return ChallengeSpec(
                challenge_id=challenge_id,
                skill=skill,
                title=meta.get("title", "Untitled"),
                required_concepts=meta.get("required_concepts", []),
                expected_behavior=meta.get("expected_behavior", ""),
                narrative=narrative,
            )
        except (json.JSONDecodeError, AttributeError):
            pass  # Fall through to fallback

    # Fallback: no structured metadata, app still works
    return ChallengeSpec(
        challenge_id=challenge_id,
        skill=skill,
        title="Untitled",
        required_concepts=[],
        expected_behavior="",
        narrative=raw_response,
    )
