import ast

from codedojo.code_validator import (
    _collect_concept_hits,
    detect_forbidden_concepts,
    validate_concepts,
)


# --- Extended AST detection tests ---


def test_detect_if_else():
    code = "x = 5\nif x > 3:\n    print('big')\nelse:\n    print('small')"
    tree = ast.parse(code)
    hits = _collect_concept_hits(tree)
    assert "if/else" in hits


def test_detect_while_loop():
    code = "i = 0\nwhile i < 5:\n    print(i)\n    i += 1"
    tree = ast.parse(code)
    hits = _collect_concept_hits(tree)
    assert "while loop" in hits


def test_detect_for_loop():
    code = "for i in range(5):\n    print(i)"
    tree = ast.parse(code)
    hits = _collect_concept_hits(tree)
    assert "for loop" in hits


def test_detect_list():
    code = "nums = [1, 2, 3]"
    tree = ast.parse(code)
    hits = _collect_concept_hits(tree)
    assert "list" in hits


def test_detect_dict():
    code = "data = {'a': 1, 'b': 2}"
    tree = ast.parse(code)
    hits = _collect_concept_hits(tree)
    assert "dict" in hits


def test_detect_function_def():
    code = "def greet(name):\n    print(f'Hello {name}')"
    tree = ast.parse(code)
    hits = _collect_concept_hits(tree)
    assert "function def" in hits


def test_detect_import():
    code = "import math"
    tree = ast.parse(code)
    hits = _collect_concept_hits(tree)
    assert "import" in hits


def test_detect_import_from():
    code = "from math import sqrt"
    tree = ast.parse(code)
    hits = _collect_concept_hits(tree)
    assert "import" in hits


def test_detect_string_method():
    code = "name = 'hello'\nprint(name.upper())"
    tree = ast.parse(code)
    hits = _collect_concept_hits(tree)
    assert "string method" in hits


def test_no_false_positive_for_simple_code():
    code = "x = 42\nprint(f'The answer is {x}')"
    tree = ast.parse(code)
    hits = _collect_concept_hits(tree)
    assert "if/else" not in hits
    assert "while loop" not in hits
    assert "for loop" not in hits
    assert "list" not in hits
    assert "dict" not in hits
    assert "function def" not in hits
    assert "import" not in hits


# --- Forbidden concept detection tests ---

WHITE_BELT_SKILLS = [
    "variables and assignment",
    "basic data types (int, float, str, bool)",
    "arithmetic operators (+, -, *, /, //, %, **)",
    "print() function",
    "string concatenation and f-strings",
    "basic comparisons and boolean logic",
    "simple math calculations",
]


def test_forbidden_flags_if_else_for_white_belt():
    code = "x = 5\nif x > 3:\n    print('big')"
    result = detect_forbidden_concepts(code, WHITE_BELT_SKILLS)
    assert "if/else" in result.found_forbidden


def test_forbidden_flags_while_for_white_belt():
    code = "i = 0\nwhile i < 5:\n    i += 1"
    result = detect_forbidden_concepts(code, WHITE_BELT_SKILLS)
    assert "while loop" in result.found_forbidden


def test_forbidden_allows_if_else_for_yellow_belt():
    taught = WHITE_BELT_SKILLS + ["if/else conditional statements"]
    code = "x = 5\nif x > 3:\n    print('big')"
    result = detect_forbidden_concepts(code, taught)
    assert "if/else" not in result.found_forbidden


def test_forbidden_allows_loops_when_taught():
    taught = WHITE_BELT_SKILLS + ["for loops and range()"]
    code = "for i in range(5):\n    print(i)"
    result = detect_forbidden_concepts(code, taught)
    assert "for loop" not in result.found_forbidden


def test_forbidden_clean_white_belt_code():
    code = "name = 'Ethan'\nage = 25\nprint(f'{name} is {age} years old')"
    result = detect_forbidden_concepts(code, WHITE_BELT_SKILLS)
    assert result.found_forbidden == []


def test_forbidden_summary_empty_when_clean():
    code = "x = 42\nprint(x)"
    result = detect_forbidden_concepts(code, WHITE_BELT_SKILLS)
    assert result.summary() == ""


def test_forbidden_summary_nonempty_when_violations():
    code = "for i in range(3):\n    print(i)"
    result = detect_forbidden_concepts(code, WHITE_BELT_SKILLS)
    assert "for loop" in result.summary()


def test_forbidden_handles_syntax_error():
    code = "def broken(:\n    pass"
    result = detect_forbidden_concepts(code, WHITE_BELT_SKILLS)
    assert result.found_forbidden == []
