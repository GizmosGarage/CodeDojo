from codedojo.challenge_gen import (
    find_challenge_boundary_violations,
    find_lesson_boundary_violations,
    get_belt_exam_prompt,
    get_challenge_prompt,
    get_lesson_prompt,
    parse_lesson_response,
    parse_challenge_response,
)
from codedojo.challenge_model import ChallengeSpec


def test_get_challenge_prompt_includes_recent_history():
    prompt, skill = get_challenge_prompt(
        skill="print() function",
        recent_challenges=[
            {
                "title": "Banner Blast",
                "expected_behavior": "Print a two-line tournament banner.",
                "required_concepts": ["print()", "end parameter"],
            }
        ],
        duplicate_warning={
            "title": "Banner Blast",
            "expected_behavior": "Print a two-line tournament banner.",
            "required_concepts": ["print()", "end parameter"],
        },
    )

    assert skill == "print() function"
    assert "Previously used challenge patterns:" in prompt
    assert 'title="Banner Blast"' in prompt
    assert "Your last attempt was still too similar" in prompt
    assert "Brief description:" in prompt
    assert "What to do:" in prompt
    assert "Expected output:" in prompt
    assert "Focus:" in prompt
    assert '"what_to_do": list of short student action steps' in prompt


def test_get_belt_exam_prompt_mentions_manual_exam_flow():
    prompt, skill = get_belt_exam_prompt(
        "White Belt",
        [
            "variables and assignment",
            "print() function",
            "string concatenation and f-strings",
        ],
    )

    assert skill == "White Belt Exam"
    assert "The student chose to attempt this belt exam now." in prompt
    assert "combines 2 to 3 of those skills" in prompt
    assert "Skill focus: White Belt exam" in prompt
    assert '"required_concepts": list of specific Python functions or constructs' in prompt


def test_get_lesson_prompt_uses_first_available_skill_in_curriculum_order():
    prompt, skill = get_lesson_prompt(
        available_skills=[
            "if/else conditional statements",
            "elif chains",
            "input() and type conversion",
        ]
    )

    assert skill == "if/else conditional statements"
    assert "lesson about: if/else conditional statements" in prompt


def test_get_lesson_prompt_tells_sensei_not_to_gatekeep_lesson_requests():
    prompt, skill = get_lesson_prompt(skill="if/else conditional statements")

    assert skill == "if/else conditional statements"
    assert "Curriculum selection and prerequisite checks have already been handled by the app." in prompt
    assert "Do not question whether the student is ready" in prompt
    assert "do not redirect them to a different topic or a challenge instead" in prompt
    assert "```lesson_meta" in prompt
    assert "Quiz answers are hidden for the app" in prompt
    assert "Future topics to avoid for now: elif chains" in prompt


def test_parse_lesson_response_extracts_hidden_answers_and_renders_quiz_without_them():
    response = """```lesson_meta
{
  "title": "Conditional Logic with if/else Statements",
  "summary": "Use if and else to make your program choose between different paths.",
  "points": [
    {
      "title": "Basic if statement",
      "explanation": "An if block runs only when its condition is True.",
      "example": "temperature = 75\\nif temperature > 70:\\n    print(\\"Warm\\")"
    },
    {
      "title": "Use else for the fallback path",
      "explanation": "Else runs when the if condition is False.",
      "example": "age = 16\\nif age >= 18:\\n    print(\\"Adult\\")\\nelse:\\n    print(\\"Minor\\")"
    },
    {
      "title": "Use comparison operators in conditions",
      "explanation": "Conditions often compare values with operators like > or ==.",
      "example": "score = 85\\nif score > 80:\\n    print(\\"Nice work\\")\\nelse:\\n    print(\\"Keep practicing\\")"
    }
  ],
  "quiz": [
    {
      "question": "What prints when number is 15?",
      "code": "number = 15\\nif number > 10:\\n    print(\\"Big\\")\\nelse:\\n    print(\\"Small\\")",
      "options": ["Big", "Small", "Nothing"],
      "answer": "a"
    },
    {
      "question": "What happens when an if condition is False and there is no else?",
      "code": "",
      "options": ["Python crashes", "Python shows an error", "The block is skipped"],
      "answer": "c"
    },
    {
      "question": "Which operator checks whether a value equals 5?",
      "code": "",
      "options": ["=", "==", "!="],
      "answer": "b"
    }
  ]
}
```"""

    spec = parse_lesson_response(response, "if/else conditional statements")

    assert spec is not None
    assert spec.skill == "if/else conditional statements"
    assert spec.quiz_answers == ["a", "c", "b"]
    assert "QUIZ:" in spec.narrative
    assert "A) Big" in spec.narrative
    assert '"answer": "a"' not in spec.narrative
    assert "lesson_meta" not in spec.narrative


def test_find_lesson_boundary_violations_flags_future_topics():
    response = """```lesson_meta
{
  "title": "Conditional Logic with if/else Statements",
  "summary": "Use if, elif, and else to make your program choose between different paths.",
  "points": [
    {
      "title": "Basic if statement",
      "explanation": "An if block runs only when its condition is True.",
      "example": "temperature = 75\\nif temperature > 70:\\n    print(\\"Warm\\")"
    },
    {
      "title": "Use else for the fallback path",
      "explanation": "Else runs when the if condition is False.",
      "example": "age = 16\\nif age >= 18:\\n    print(\\"Adult\\")\\nelse:\\n    print(\\"Minor\\")"
    },
    {
      "title": "Add elif for another check",
      "explanation": "Elif lets you test another condition after if.",
      "example": "score = 85\\nif score >= 90:\\n    print(\\"A\\")\\nelif score >= 80:\\n    print(\\"B\\")\\nelse:\\n    print(\\"C\\")"
    }
  ],
  "quiz": [
    {
      "question": "What prints when number is 15?",
      "code": "number = 15\\nif number > 10:\\n    print(\\"Big\\")\\nelse:\\n    print(\\"Small\\")",
      "options": ["Big", "Small", "Nothing"],
      "answer": "a"
    },
    {
      "question": "What happens when an if condition is False and there is no else?",
      "code": "",
      "options": ["Python crashes", "Python shows an error", "The block is skipped"],
      "answer": "c"
    },
    {
      "question": "Which operator checks whether a value equals 5?",
      "code": "",
      "options": ["=", "==", "!="],
      "answer": "b"
    }
  ]
}
```"""

    spec = parse_lesson_response(response, "if/else conditional statements")

    assert spec is not None
    assert find_lesson_boundary_violations(spec) == ["elif chains"]


def test_parse_lesson_response_returns_none_for_incomplete_metadata():
    response = """```lesson_meta
{
  "title": "Broken lesson"
}
```"""

    assert parse_lesson_response(response, "if/else conditional statements") is None


def test_parse_challenge_response_extracts_metadata():
    response = """Title: Type Parade

Brief description: Practice displaying values with their Python types.

What to do:
- Create one integer, one float, one string, and one boolean.
- Print each value with its type on its own line.

Expected output:
The output should show each value followed by its Python type.

Focus:
- Skill focus: basic data types (int, float, str, bool)
- Sensei is looking for: type(), print()

```challenge_meta
{
  "title": "Type Parade",
  "brief_description": "Practice displaying values with their Python types.",
  "what_to_do": [
    "Create one integer, one float, one string, and one boolean.",
    "Print each value with its type on its own line."
  ],
  "expected_output": "42 <class 'int'>\\n3.14 <class 'float'>\\nhello <class 'str'>\\nTrue <class 'bool'>",
  "required_concepts": ["type()", "print()"],
  "expected_behavior": "Print each value followed by its Python type."
}
```"""

    spec = parse_challenge_response(response, "basic data types (int, float, str, bool)")

    assert spec.skill == "basic data types (int, float, str, bool)"
    assert spec.title == "Type Parade"
    assert spec.brief_description == "Practice displaying values with their Python types."
    assert spec.what_to_do == [
        "Create one integer, one float, one string, and one boolean.",
        "Print each value with its type on its own line.",
    ]
    assert spec.expected_output == (
        "42 <class 'int'>\n3.14 <class 'float'>\nhello <class 'str'>\nTrue <class 'bool'>"
    )
    assert spec.required_concepts == ["type()", "print()"]
    assert spec.expected_behavior == "Print each value followed by its Python type."
    assert "challenge_meta" not in spec.narrative
    assert spec.narrative.startswith("Title: Type Parade")
    assert "\n\nBrief description: Practice displaying values with their Python types." in spec.narrative
    assert "\n\nWhat to do:\n- Create one integer, one float, one string, and one boolean." in spec.narrative
    assert "\n\nExpected output:\n42 <class 'int'>" in spec.narrative
    assert "\n\nFocus:\n- Skill focus: basic data types (int, float, str, bool)" in spec.narrative
    assert "- Sensei is looking for: type(), print()" in spec.narrative
    assert "not only on matching the output" in spec.narrative


def test_parse_challenge_response_falls_back_without_metadata():
    response = "Write a program that prints your dojo motto."

    spec = parse_challenge_response(response, "print() function")

    assert spec.title == "Untitled"
    assert spec.required_concepts == []
    assert spec.expected_behavior == ""
    assert spec.narrative == response


# --- Challenge boundary violation tests ---


def _make_challenge(**kwargs) -> ChallengeSpec:
    defaults = {
        "challenge_id": "test1234",
        "skill": "print() function",
        "title": "Test",
        "narrative": "",
    }
    defaults.update(kwargs)
    return ChallengeSpec(**defaults)


WHITE_BELT_SKILLS = [
    "variables and assignment",
    "basic data types (int, float, str, bool)",
    "arithmetic operators (+, -, *, /, //, %, **)",
    "print() function",
    "string concatenation and f-strings",
    "basic comparisons and boolean logic",
    "simple math calculations",
]


def test_challenge_boundary_flags_while_loop_for_white_belt():
    spec = _make_challenge(
        narrative="Use a while loop to count from 1 to 10.",
    )
    violations = find_challenge_boundary_violations(spec, WHITE_BELT_SKILLS)
    assert "while loops" in violations


def test_challenge_boundary_flags_if_else_for_white_belt():
    spec = _make_challenge(
        narrative="Check if the number is even.",
        what_to_do=["Use if/else to decide what to print."],
    )
    violations = find_challenge_boundary_violations(spec, WHITE_BELT_SKILLS)
    assert "if/else conditional statements" in violations


def test_challenge_boundary_passes_when_skill_is_taught():
    taught = WHITE_BELT_SKILLS + ["while loops"]
    spec = _make_challenge(
        narrative="Use a while loop to count from 1 to 10.",
    )
    violations = find_challenge_boundary_violations(spec, taught)
    assert "while loops" not in violations


def test_challenge_boundary_no_violations_for_clean_challenge():
    spec = _make_challenge(
        narrative="Print the result of 2 + 3 using an f-string.",
    )
    violations = find_challenge_boundary_violations(spec, WHITE_BELT_SKILLS)
    assert violations == []


def test_challenge_boundary_multiple_violations():
    spec = _make_challenge(
        narrative="Use a for loop and if/else to process a list of items.",
    )
    violations = find_challenge_boundary_violations(spec, WHITE_BELT_SKILLS)
    assert len(violations) >= 2
    assert "if/else conditional statements" in violations
    assert "for loops and range()" in violations
