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

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            call_names.add(node.func.id)
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
