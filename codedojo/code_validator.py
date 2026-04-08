"""AST-based concept detection for student code.

Deterministic checks — no AI involved. Used as advisory evidence
for Sensei's pass/fail decision.
"""

import ast
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    all_passed: bool
    found: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """Format as a string for Sensei."""
        lines = []
        if self.found:
            lines.append(f"- Found: {', '.join(self.found)}")
        if self.missing:
            lines.append(f"- Missing: {', '.join(self.missing)}")
        if self.unknown:
            lines.append(f"- Could not verify: {', '.join(self.unknown)}")
        return "\n".join(lines) if lines else "- No concept requirements for this challenge."


def _is_string_expr(node: ast.expr) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return True
    if isinstance(node, ast.JoinedStr):
        return True
    return False


def _collect_concept_hits(tree: ast.Module) -> set[str]:
    """Single walk: record which registered concepts appear in the AST."""
    call_names: set[str] = set()
    has_joined_str = False
    has_string_concat = False
    has_floordiv = False
    has_mod = False
    has_pow = False
    has_compare = False
    has_bool_logic = False
    has_assign = False
    has_if_else = False
    has_while_loop = False
    has_for_loop = False
    has_list = False
    has_dict = False
    has_function_def = False
    has_import = False
    has_string_method = False

    _STRING_METHODS = {"upper", "lower", "strip", "replace"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                call_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                if node.func.attr in _STRING_METHODS:
                    has_string_method = True
        elif isinstance(node, ast.JoinedStr):
            has_joined_str = True
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            if _is_string_expr(node.left) or _is_string_expr(node.right):
                has_string_concat = True
        elif isinstance(node, ast.BinOp):
            if isinstance(node.op, ast.FloorDiv):
                has_floordiv = True
            elif isinstance(node.op, ast.Mod):
                has_mod = True
            elif isinstance(node.op, ast.Pow):
                has_pow = True
        elif isinstance(node, ast.Compare):
            has_compare = True
        elif isinstance(node, ast.BoolOp):
            has_bool_logic = True
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            has_bool_logic = True
        elif isinstance(node, (ast.Assign, ast.AugAssign)):
            has_assign = True
        elif isinstance(node, ast.If):
            has_if_else = True
        elif isinstance(node, ast.While):
            has_while_loop = True
        elif isinstance(node, ast.For):
            has_for_loop = True
        elif isinstance(node, ast.List):
            has_list = True
        elif isinstance(node, ast.Dict):
            has_dict = True
        elif isinstance(node, ast.FunctionDef):
            has_function_def = True
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            has_import = True

    hits: set[str] = set()
    builtins_map = {
        "round": "round()",
        "print": "print()",
        "input": "input()",
        "len": "len()",
        "int": "int()",
        "float": "float()",
        "str": "str()",
        "type": "type()",
        "abs": "abs()",
        "max": "max()",
        "min": "min()",
    }
    for name, label in builtins_map.items():
        if name in call_names:
            hits.add(label)
    if has_joined_str:
        hits.add("f-string")
    if has_string_concat:
        hits.add("string concatenation")
    if has_floordiv:
        hits.add("//")
    if has_mod:
        hits.add("%")
    if has_pow:
        hits.add("**")
    if has_compare:
        hits.add("comparison")
    if has_bool_logic:
        hits.add("boolean logic")
    if has_assign:
        hits.add("variable assignment")
    if has_if_else:
        hits.add("if/else")
    if has_while_loop:
        hits.add("while loop")
    if has_for_loop:
        hits.add("for loop")
    if has_list:
        hits.add("list")
    if has_dict:
        hits.add("dict")
    if has_function_def:
        hits.add("function def")
    if has_import:
        hits.add("import")
    if has_string_method:
        hits.add("string method")
    return hits


# Concepts we can verify via _collect_concept_hits (extend both together).
KNOWN_CONCEPTS = frozenset(
    {
        "round()",
        "print()",
        "input()",
        "len()",
        "int()",
        "float()",
        "str()",
        "type()",
        "abs()",
        "max()",
        "min()",
        "f-string",
        "string concatenation",
        "//",
        "%",
        "**",
        "comparison",
        "boolean logic",
        "variable assignment",
        "if/else",
        "while loop",
        "for loop",
        "list",
        "dict",
        "function def",
        "import",
        "string method",
    }
)


def validate_concepts(code: str, required_concepts: list[str]) -> ValidationResult:
    """Validate that student code uses the required concepts.

    Returns ValidationResult with advisory information for Sensei.
    If required_concepts is empty, returns all_passed=True.
    """
    if not required_concepts:
        return ValidationResult(all_passed=True)

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return ValidationResult(
            all_passed=False,
            missing=required_concepts,
        )

    hits = _collect_concept_hits(tree)
    found = []
    missing = []
    unknown = []

    for concept in required_concepts:
        if concept not in KNOWN_CONCEPTS:
            unknown.append(concept)
        elif concept in hits:
            found.append(concept)
        else:
            missing.append(concept)

    all_passed = len(missing) == 0
    return ValidationResult(
        all_passed=all_passed,
        found=found,
        missing=missing,
        unknown=unknown,
    )


# --- Forbidden concept detection (advisory) ---

# White belt fundamentals — always allowed regardless of skills_taught.
BASELINE_ALLOWED: frozenset[str] = frozenset(
    {
        "variable assignment",
        "print()",
        "f-string",
        "string concatenation",
        "//",
        "%",
        "**",
        "comparison",
        "boolean logic",
        "round()",
        "abs()",
        "max()",
        "min()",
        "type()",
        "float()",
        "int()",
        "str()",
    }
)

# Maps each curriculum skill to the additional AST concepts it unlocks.
SKILL_UNLOCKED_CONCEPTS: dict[str, set[str]] = {
    "if/else conditional statements": {"if/else"},
    "elif chains": {"if/else"},
    "input() and type conversion": {"input()", "int()", "float()", "str()"},
    "while loops": {"while loop"},
    "for loops and range()": {"for loop"},
    "basic string methods (.upper(), .lower(), .strip(), .replace())": {"string method"},
    "len() function": {"len()"},
}


@dataclass
class ForbiddenConceptResult:
    found_forbidden: list[str] = field(default_factory=list)

    def summary(self) -> str:
        if not self.found_forbidden:
            return ""
        return (
            "- Concepts used that haven't been taught yet: "
            + ", ".join(self.found_forbidden)
        )


def detect_forbidden_concepts(
    code: str,
    taught_skills: list[str],
) -> ForbiddenConceptResult:
    """Detect AST concepts in code that the student hasn't been taught yet.

    Advisory only — does not block submission.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return ForbiddenConceptResult()

    hits = _collect_concept_hits(tree)

    # Build the set of allowed concepts from baseline + taught skills
    allowed = set(BASELINE_ALLOWED)
    for skill in taught_skills:
        allowed.update(SKILL_UNLOCKED_CONCEPTS.get(skill, set()))

    # Only flag concepts we can actually detect (in KNOWN_CONCEPTS)
    forbidden = sorted(hits & KNOWN_CONCEPTS - allowed)
    return ForbiddenConceptResult(found_forbidden=forbidden)
