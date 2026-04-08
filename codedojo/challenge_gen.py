import json
import random
import re
import uuid

from codedojo.challenge_model import ChallengeSpec
from codedojo.lesson_model import LessonPoint, LessonSpec, QuizQuestion

_CHALLENGE_META_PATTERN = re.compile(r"```challenge_meta\s*\n?(.*?)\n?\s*```", re.DOTALL)
_LESSON_META_PATTERN = re.compile(r"```lesson_meta\s*\n?(.*?)\n?\s*```", re.DOTALL)


class NoNewSkillsError(Exception):
    """Raised when all skills in the belt have been taught."""


WHITE_BELT_SKILLS = [
    "variables and assignment",
    "basic data types (int, float, str, bool)",
    "arithmetic operators (+, -, *, /, //, %, **)",
    "print() function",
    "string concatenation and f-strings",
    "basic comparisons and boolean logic",
    "simple math calculations",
]

YELLOW_BELT_SKILLS = [
    "if/else conditional statements",
    "elif chains",
    "input() and type conversion",
    "while loops",
    "for loops and range()",
    "basic string methods (.upper(), .lower(), .strip(), .replace())",
    "len() function",
]

BELT_SKILL_MAP = {
    "white": WHITE_BELT_SKILLS,
    "yellow": YELLOW_BELT_SKILLS,
}

LESSON_FUTURE_SKILL_PATTERNS = {
    "if/else conditional statements": [
        re.compile(r"(?m)^\s*if\s+.+:\s*$", re.IGNORECASE),
        re.compile(r"(?m)^\s*else\s*:\s*$", re.IGNORECASE),
        re.compile(r"\bif/else\b", re.IGNORECASE),
        re.compile(r"\bif statement(?:s)?\b", re.IGNORECASE),
    ],
    "elif chains": [
        re.compile(r"\belif\b", re.IGNORECASE),
    ],
    "input() and type conversion": [
        re.compile(r"\binput\s*\(", re.IGNORECASE),
        re.compile(r"\bint\s*\(", re.IGNORECASE),
        re.compile(r"\bfloat\s*\(", re.IGNORECASE),
        re.compile(r"\bstr\s*\(", re.IGNORECASE),
        re.compile(r"\btype conversion\b", re.IGNORECASE),
    ],
    "while loops": [
        re.compile(r"\bwhile\b", re.IGNORECASE),
    ],
    "for loops and range()": [
        re.compile(r"\brange\s*\(", re.IGNORECASE),
        re.compile(r"(?m)^\s*for\s+\w+\s+in\b", re.IGNORECASE),
        re.compile(r"\bfor loop(?:s)?\b", re.IGNORECASE),
    ],
    "basic string methods (.upper(), .lower(), .strip(), .replace())": [
        re.compile(r"\.upper\s*\(", re.IGNORECASE),
        re.compile(r"\.lower\s*\(", re.IGNORECASE),
        re.compile(r"\.strip\s*\(", re.IGNORECASE),
        re.compile(r"\.replace\s*\(", re.IGNORECASE),
    ],
    "len() function": [
        re.compile(r"\blen\s*\(", re.IGNORECASE),
    ],
}


def skills_for_belt(belt: str) -> list[str]:
    """Return the skill list for the given belt color."""
    return BELT_SKILL_MAP.get(belt, [])


def all_skills_up_to_belt(belt: str) -> list[str]:
    """Return all skills from white belt up to and including the given belt."""
    from codedojo.progress import Progress
    order = Progress.BELT_ORDER
    result: list[str] = []
    for b in order:
        result.extend(BELT_SKILL_MAP.get(b, []))
        if b == belt:
            break
    return result


def all_curriculum_skills() -> list[str]:
    """Return all known curriculum skills in teaching order."""
    from codedojo.progress import Progress

    ordered: list[str] = []
    for belt in Progress.BELT_ORDER:
        ordered.extend(BELT_SKILL_MAP.get(belt, []))
    return ordered


def future_lesson_skills(skill: str) -> list[str]:
    """Return skills that should be taught after the given lesson."""
    ordered = all_curriculum_skills()
    try:
        index = ordered.index(skill)
    except ValueError:
        return []
    return ordered[index + 1:]


def _clean_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _coerce_string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [item.strip() for item in (str(part) for part in value) if item.strip()]
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return []


def format_challenge_narrative(
    *,
    skill: str,
    title: str,
    brief_description: str,
    what_to_do: list[str],
    expected_output: str,
    required_concepts: list[str],
    expected_behavior: str,
) -> str:
    """Render the student-facing challenge in the dojo's fixed format."""
    resolved_title = title or "Untitled"
    resolved_description = (
        brief_description or f"Practice {skill} with one small, focused Python program."
    )
    resolved_steps = what_to_do or [resolved_description]
    resolved_output = expected_output or expected_behavior or "Produce the output described above."

    lines = [
        f"Title: {resolved_title}",
        "",
        f"Brief description: {resolved_description}",
        "",
        "What to do:",
    ]
    lines.extend(f"- {step}" for step in resolved_steps)
    lines.extend(
        [
            "",
            "Expected output:",
            resolved_output,
            "",
            "Focus:",
            f"- Skill focus: {skill}",
        ]
    )

    if required_concepts:
        lines.append(f"- Sensei is looking for: {', '.join(required_concepts)}")
        lines.append(
            "- Your answer is graded on using those specific concepts, not only on matching the output."
        )
    else:
        lines.append("- Sensei is looking for the target skill to be used clearly and intentionally.")

    return "\n".join(lines).rstrip()


def format_lesson_narrative(
    *,
    title: str,
    summary: str,
    points: list[LessonPoint],
    quiz: list[QuizQuestion],
) -> str:
    """Render the student-facing lesson in a fixed format."""
    lines = [
        f"Lesson: {title}",
        "",
        "Summary:",
        summary,
        "",
        "Key points:",
    ]

    for index, point in enumerate(points, 1):
        lines.append(f"{index}. {point.title}")
        lines.append(point.explanation)
        if point.example:
            lines.extend(
                [
                    "Example:",
                    "```python",
                    point.example,
                    "```",
                ]
            )
        lines.append("")

    lines.append("QUIZ:")
    for index, question in enumerate(quiz, 1):
        lines.append(f"{index}. {question.question}")
        if question.code:
            lines.extend(
                [
                    "```python",
                    question.code,
                    "```",
                ]
            )
        option_labels = ("A", "B", "C")
        for label, option in zip(option_labels, question.options):
            lines.append(f"{label}) {option}")
        if index != len(quiz):
            lines.append("")

    return "\n".join(lines).rstrip()


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
        # Lessons should follow the curriculum order, not jump around randomly.
        chosen = available_skills[0]
    else:
        chosen = WHITE_BELT_SKILLS[0]
    future_topics = future_lesson_skills(chosen)
    future_topics_text = ""
    if future_topics:
        future_topics_text = (
            "Do NOT teach, mention, or use any later curriculum topics in this lesson yet. "
            "That includes explanations, examples, and quiz questions.\n"
            f"Future topics to avoid for now: {', '.join(future_topics)}.\n\n"
        )
    prompt = (
        f"Sensei, please prepare the student's next lesson about: {chosen}\n\n"
        "Curriculum selection and prerequisite checks have already been handled by the app. "
        "This topic is the correct next lesson for the student right now.\n\n"
        "Teach exactly this skill. Do not question whether the student is ready, "
        "do not mention missing prerequisites or belt progression, and do not redirect "
        "them to a different topic or a challenge instead.\n\n"
        f"{future_topics_text}"
        "Reply with ONLY a JSON metadata block delimited by ```lesson_meta and ```. "
        "Do not include any prose before or after the block.\n\n"
        "The block must contain:\n"
        '- "title": short lesson title\n'
        '- "summary": 1-2 sentence overview of the skill\n'
        '- "points": list of 3 to 5 objects, each with:\n'
        '  - "title": short point heading\n'
        '  - "explanation": 1-2 short teaching sentences\n'
        '  - "example": short Python example as a plain string; use \\n for multiple lines\n'
        '- "quiz": list of exactly 3 objects, each with:\n'
        '  - "question": question text\n'
        '  - "code": short Python snippet as a plain string; use \\n for multiple lines; use "" if none\n'
        '  - "options": list of exactly 3 answer options in A/B/C order\n'
        '  - "answer": the correct letter as "a", "b", or "c"\n\n'
        "Keep the lesson tight and practical. Every point should teach one idea and show it with code. "
        "Quiz answers are hidden for the app, so do not reveal them anywhere except the answer fields."
    )
    return prompt, chosen


def _lesson_text_for_boundary_checks(lesson: LessonSpec) -> str:
    parts = [lesson.title, lesson.summary]
    for point in lesson.points:
        parts.extend([point.title, point.explanation, point.example])
    for question in lesson.quiz:
        parts.extend([question.question, question.code, *question.options])
    return "\n".join(part for part in parts if part)


def find_lesson_boundary_violations(lesson: LessonSpec) -> list[str]:
    """Return future curriculum topics that leaked into this lesson."""
    text = _lesson_text_for_boundary_checks(lesson)
    violations: list[str] = []

    for future_skill in future_lesson_skills(lesson.skill):
        patterns = LESSON_FUTURE_SKILL_PATTERNS.get(future_skill, [])
        if any(pattern.search(text) for pattern in patterns):
            violations.append(future_skill)

    return violations


def _challenge_text_for_boundary_checks(challenge: ChallengeSpec) -> str:
    """Concatenate all challenge text fields for boundary scanning."""
    parts = [
        challenge.title,
        challenge.brief_description,
        "\n".join(challenge.what_to_do),
        challenge.expected_output,
        challenge.narrative,
    ]
    return "\n".join(part for part in parts if part)


def find_challenge_boundary_violations(
    challenge: ChallengeSpec,
    taught_skills: list[str],
) -> list[str]:
    """Return untaught skills whose patterns appear in the challenge text."""
    text = _challenge_text_for_boundary_checks(challenge)
    all_skills = all_curriculum_skills()
    taught_set = set(taught_skills)
    untaught = [s for s in all_skills if s not in taught_set]

    violations: list[str] = []
    for skill in untaught:
        patterns = LESSON_FUTURE_SKILL_PATTERNS.get(skill, [])
        if any(p.search(text) for p in patterns):
            violations.append(skill)
    return violations


def _coerce_lesson_points(value: object) -> list[LessonPoint]:
    if not isinstance(value, list):
        return []

    points: list[LessonPoint] = []
    for item in value:
        if not isinstance(item, dict):
            return []
        title = _clean_text(item.get("title"))
        explanation = _clean_text(item.get("explanation"))
        example = _clean_text(item.get("example"))
        if not title or not explanation or not example:
            return []
        points.append(LessonPoint(title=title, explanation=explanation, example=example))
    return points


def _coerce_quiz_options(value: object) -> list[str]:
    if isinstance(value, list):
        options = [_clean_text(option) for option in value]
    elif isinstance(value, dict):
        options = [_clean_text(value.get(letter)) for letter in ("a", "b", "c")]
    else:
        return []

    if len(options) != 3 or any(not option for option in options):
        return []
    return options


def _coerce_quiz_questions(value: object) -> list[QuizQuestion]:
    if not isinstance(value, list):
        return []

    quiz: list[QuizQuestion] = []
    for item in value:
        if not isinstance(item, dict):
            return []
        question = _clean_text(item.get("question"))
        code = _clean_text(item.get("code"))
        options = _coerce_quiz_options(item.get("options"))
        answer = _clean_text(item.get("answer")).lower()
        if not question or len(options) != 3 or answer not in {"a", "b", "c"}:
            return []
        quiz.append(
            QuizQuestion(
                question=question,
                code=code,
                options=options,
                answer=answer,
            )
        )
    return quiz


def parse_lesson_response(raw_response: str, skill: str) -> LessonSpec | None:
    """Extract structured lesson metadata and render student-facing lesson text."""
    match = _LESSON_META_PATTERN.search(raw_response)
    if not match:
        return None

    try:
        meta = json.loads(match.group(1).strip())
    except json.JSONDecodeError:
        return None

    title = _clean_text(meta.get("title")) or skill
    summary = _clean_text(meta.get("summary"))
    points = _coerce_lesson_points(meta.get("points"))
    quiz = _coerce_quiz_questions(meta.get("quiz"))

    if not summary or not 3 <= len(points) <= 5 or len(quiz) != 3:
        return None

    narrative = format_lesson_narrative(
        title=title,
        summary=summary,
        points=points,
        quiz=quiz,
    )
    return LessonSpec(
        skill=skill,
        title=title,
        summary=summary,
        points=points,
        quiz=quiz,
        narrative=narrative,
    )


def _format_prior_challenge(challenge: dict) -> str | None:
    parts: list[str] = []
    title = challenge.get("title", "").strip()
    expected_behavior = challenge.get("expected_behavior", "").strip()
    required_concepts = [concept for concept in challenge.get("required_concepts", []) if concept]

    if title:
        parts.append(f'title="{title}"')
    if expected_behavior:
        parts.append(f'behavior="{expected_behavior}"')
    if required_concepts:
        parts.append(f'concepts={", ".join(required_concepts)}')

    if not parts:
        return None
    return f"- {'; '.join(parts)}"


def get_challenge_prompt(
    skill: str | None = None,
    recent_challenges: list[dict] | None = None,
    duplicate_warning: dict | None = None,
    boundary_violations: list[str] | None = None,
) -> tuple[str, str]:
    """Return (prompt_for_sensei, chosen_skill)."""
    chosen = skill if skill else random.choice(WHITE_BELT_SKILLS)

    history_section = ""
    history_lines = [
        "IMPORTANT: Make this challenge genuinely different from any prior challenge for this skill.",
        "Use a new title, a new task framing, and different expected behavior whenever possible.",
    ]

    formatted_recent = [
        formatted
        for formatted in (
            _format_prior_challenge(challenge)
            for challenge in (recent_challenges or [])
        )
        if formatted
    ]
    if formatted_recent:
        history_lines.append("Previously used challenge patterns:")
        history_lines.extend(formatted_recent)

    if duplicate_warning:
        formatted_duplicate = _format_prior_challenge(duplicate_warning)
        if formatted_duplicate:
            history_lines.append("Your last attempt was still too similar to this prior challenge:")
            history_lines.append(formatted_duplicate)
            history_lines.append("Try again with a clearly different idea.")

    if boundary_violations:
        history_lines.append(
            "Your last attempt referenced concepts the student has NOT learned yet. "
            "Do NOT mention or require these topics: "
            + ", ".join(boundary_violations)
            + ". Generate a completely new challenge using ONLY skills the student knows."
        )

    if len(history_lines) > 2:
        history_section = "\n" + "\n".join(history_lines) + "\n\n"

    prompt = (
        f"Sensei, please give me a coding challenge focused on: {chosen}\n\n"
        "CRITICAL: The challenge must be solvable using ONLY the skills listed in the "
        "student context. If the student has not learned if/else, the challenge MUST NOT "
        "require conditional branching — all output must be deterministic from math and "
        "string operations. Do NOT design scenarios where different inputs produce "
        "different outputs (e.g., 'warning vs ticket', 'pass vs fail').\n\n"
        f"{history_section}"
        "Write the student-facing challenge using EXACTLY these sections in this order:\n"
        "Title: [short title]\n"
        "Brief description: [1-2 sentence setup]\n"
        "What to do:\n"
        "- [short action step]\n"
        "- [short action step if needed]\n"
        "Expected output:\n"
        "[show the exact output to aim for, using plain text with line breaks if needed]\n"
        "Focus:\n"
        f"- Skill focus: {chosen}\n"
        "- Sensei is looking for: [the exact functions/constructs that must appear]\n"
        "- Your answer is graded on using those specific concepts, not only on matching the output.\n\n"
        "IMPORTANT: You must include a JSON metadata block in your response, "
        "delimited by ```challenge_meta and ```. The block must contain:\n"
        '- "title": short challenge title\n'
        '- "brief_description": short setup/context for the challenge\n'
        '- "what_to_do": list of short student action steps\n'
        '- "expected_output": exact output target as a plain string; use \\n for multiple lines\n'
        '- "test_input": if the challenge uses input(), provide the stdin values (one per line) '
        'that produce the expected_output. Omit or leave empty if no input() is needed.\n'
        '- "required_concepts": list of specific Python functions or constructs '
        'the student must use (e.g. ["round()", "f-string", "float()"])\n'
        '- "expected_behavior": one sentence describing what correct output looks like\n\n'
        "The Focus section and required_concepts list must match each other. "
        "Be explicit so the student knows exactly what Sensei will grade for.\n"
        "Place this block at the end of your response."
    )
    return prompt, chosen


def get_belt_exam_prompt(
    belt_name: str,
    learned_skills: list[str],
    challenge_number: int = 1,
    total_challenges: int = 3,
    prior_exam_challenges: list[dict] | None = None,
    recent_challenges: list[dict] | None = None,
    duplicate_warning: dict | None = None,
    boundary_violations: list[str] | None = None,
) -> tuple[str, str]:
    """Return (prompt_for_sensei, exam_label) for a user-started belt exam."""
    exam_label = f"{belt_name} Exam"
    skills_text = ", ".join(learned_skills)

    history_section = ""
    history_lines = [
        "IMPORTANT: Make this belt exam challenge genuinely different from any earlier one.",
        "Use a new title, a new scenario, and different expected behavior whenever possible.",
    ]

    # Show prior challenges from this same exam attempt for variety
    if prior_exam_challenges:
        history_lines.append("Challenges already given in this exam (do NOT repeat these):")
        for prior in prior_exam_challenges:
            formatted = _format_prior_challenge(prior)
            if formatted:
                history_lines.append(formatted)

    formatted_recent = [
        formatted
        for formatted in (
            _format_prior_challenge(challenge)
            for challenge in (recent_challenges or [])
        )
        if formatted
    ]
    if formatted_recent:
        history_lines.append("Previously used belt exam patterns:")
        history_lines.extend(formatted_recent)

    if duplicate_warning:
        formatted_duplicate = _format_prior_challenge(duplicate_warning)
        if formatted_duplicate:
            history_lines.append("Your last attempt was still too similar to this earlier belt exam:")
            history_lines.append(formatted_duplicate)
            history_lines.append("Try again with a clearly different exam idea.")

    if boundary_violations:
        history_lines.append(
            "Your last attempt referenced concepts the student has NOT learned yet. "
            "Do NOT mention or require these topics: "
            + ", ".join(boundary_violations)
            + ". Generate a completely new challenge using ONLY skills the student knows."
        )

    if len(history_lines) > 2:
        history_section = "\n" + "\n".join(history_lines) + "\n\n"

    prompt = (
        f"Sensei, please create challenge {challenge_number} of {total_challenges} "
        f"for the {belt_name} promotion exam.\n\n"
        "The student chose to attempt this belt exam now. It is not a random invitation.\n"
        f"The exam may only use skills the student has already learned: {skills_text}.\n"
        "Make it a single moderate-sized Python program that combines 2 to 3 of those skills. "
        "It should feel broader than a normal practice challenge, but still be solvable in one sitting.\n"
        "Each exam challenge should test a different combination of skills.\n\n"
        "CRITICAL: The challenge must be solvable using ONLY the listed skills. "
        "If the student has not learned if/else, the challenge MUST NOT require conditional "
        "branching — no 'if X then Y, otherwise Z' scenarios. All output must be fully "
        "deterministic from straightforward math and string operations. Do NOT design "
        "scenarios that require choosing between different outcomes.\n\n"
        f"{history_section}"
        "Write the student-facing exam challenge using EXACTLY these sections in this order:\n"
        "Title: [short title]\n"
        "Brief description: [1-2 sentence setup]\n"
        "What to do:\n"
        "- [short action step]\n"
        "- [short action step if needed]\n"
        "Expected output:\n"
        "[show the exact output to aim for, using plain text with line breaks if needed]\n"
        "Focus:\n"
        f"- Skill focus: {belt_name} exam (challenge {challenge_number}/{total_challenges})\n"
        "- Sensei is looking for: [3-6 specific Python functions or constructs that must appear]\n"
        "- Your answer is graded on using those specific concepts, not only on matching the output.\n\n"
        "IMPORTANT: You must include a JSON metadata block in your response, "
        "delimited by ```challenge_meta and ```. The block must contain:\n"
        '- "title": short challenge title\n'
        '- "brief_description": short setup/context for the challenge\n'
        '- "what_to_do": list of short student action steps\n'
        '- "expected_output": exact output target as a plain string; use \\n for multiple lines\n'
        '- "test_input": if the challenge uses input(), provide the stdin values (one per line) '
        'that produce the expected_output. Omit or leave empty if no input() is needed.\n'
        '- "required_concepts": list of specific Python functions or constructs '
        'the student must use (e.g. ["round()", "f-string", "float()"])\n'
        '- "expected_behavior": one sentence describing what correct output looks like\n\n'
        "The Focus section and required_concepts list must match each other. "
        "Be explicit so the student knows exactly what Sensei will grade for.\n"
        "Place this block at the end of your response."
    )
    return prompt, exam_label


def build_exam_final_grading_prompt(
    belt_name: str,
    challenges: list,
    learned_skills: list[str],
) -> str:
    """Build the holistic grading prompt for a completed belt exam.

    ``challenges`` is a list of ExamChallengeRecord objects.
    """
    skills_text = ", ".join(learned_skills)
    sections: list[str] = []

    for i, rec in enumerate(challenges, 1):
        spec = rec.challenge_spec
        numbered_lines = [
            f"{ln:3d} | {line}"
            for ln, line in enumerate((rec.code or "").splitlines(), 1)
        ]
        numbered_code = "\n".join(numbered_lines)

        sections.append(
            f"=== Challenge {i}: {spec.title} ===\n"
            f"Skill focus: {spec.skill}\n"
            f"Required concepts: {', '.join(spec.required_concepts)}\n"
            f"Expected behavior: {spec.expected_behavior}\n\n"
            f"Code submitted:\n```python\n{numbered_code}\n```\n\n"
            f"Execution output:\n```\n{rec.output or '(no output)'}\n```\n\n"
            f"Concept validation:\n{rec.validation_summary or 'N/A'}"
        )

    challenges_block = "\n\n".join(sections)

    return (
        f"Sensei, the student has completed all 3 challenges for the {belt_name} promotion exam.\n"
        f"Skills covered by this belt: {skills_text}.\n"
        "Please review all submissions holistically.\n\n"
        f"{challenges_block}\n\n"
        "=== Grading Instructions ===\n"
        "Evaluate all 3 submissions together as a whole exam. Consider:\n"
        "- The severity of any errors across all 3 challenges\n"
        "- The total number of errors\n"
        "- The importance of the errors relative to the skills being tested\n"
        f"- Whether the student demonstrates overall competency in the {belt_name} skills\n\n"
        "This is NOT a simple pass/fail count. A student who nails 2 challenges perfectly "
        "but has a minor issue on the third should pass. A student who has fundamental "
        "misunderstandings across multiple challenges should fail.\n"
        "Note: if a challenge inadvertently required a concept the student hasn't learned "
        "(e.g., if/else when only comparisons were taught), be lenient about workarounds "
        "the student used to handle that gap.\n\n"
        "If the student PASSES:\n"
        "- Deliver a ceremony narrative congratulating them on earning the next belt\n"
        "- Use martial arts metaphors and make it feel like a real promotion moment\n"
        "- Briefly acknowledge what they did well across the exam\n"
        "- End with [EXAM_PASS] on its own line\n\n"
        "If the student FAILS:\n"
        "- Tell them specifically what they need to work on\n"
        "- Identify 1-3 areas where their understanding fell short\n"
        "- Be encouraging but honest\n"
        "- End with [EXAM_FAIL] on its own line"
    )


def parse_challenge_response(raw_response: str, skill: str) -> ChallengeSpec:
    """Extract structured metadata from Sensei's challenge response.

    Falls back gracefully if the JSON block is missing or malformed.
    """
    challenge_id = uuid.uuid4().hex[:8]

    match = _CHALLENGE_META_PATTERN.search(raw_response)

    if match:
        try:
            meta = json.loads(match.group(1).strip())
            title = _clean_text(meta.get("title")) or "Untitled"
            required_concepts = _coerce_string_list(meta.get("required_concepts"))
            expected_behavior = _clean_text(meta.get("expected_behavior"))
            brief_description = _clean_text(meta.get("brief_description"))
            what_to_do = _coerce_string_list(meta.get("what_to_do"))
            expected_output = _clean_text(meta.get("expected_output"))
            test_input = _clean_text(meta.get("test_input"))
            narrative = format_challenge_narrative(
                skill=skill,
                title=title,
                brief_description=brief_description,
                what_to_do=what_to_do,
                expected_output=expected_output,
                required_concepts=required_concepts,
                expected_behavior=expected_behavior,
            )
            return ChallengeSpec(
                challenge_id=challenge_id,
                skill=skill,
                title=title,
                required_concepts=required_concepts,
                expected_behavior=expected_behavior,
                brief_description=brief_description,
                what_to_do=what_to_do,
                expected_output=expected_output,
                test_input=test_input or "",
                narrative=narrative,
            )
        except (json.JSONDecodeError, AttributeError):
            pass

    return ChallengeSpec(
        challenge_id=challenge_id,
        skill=skill,
        title="Untitled",
        required_concepts=[],
        expected_behavior="",
        narrative=raw_response,
    )
