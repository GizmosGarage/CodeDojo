from codedojo.challenge_gen import (
    get_belt_exam_prompt,
    get_challenge_prompt,
    parse_challenge_response,
)


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
