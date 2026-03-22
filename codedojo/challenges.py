"""Challenge execution engine — runs student code safely against test cases."""

import subprocess
import sys
import tempfile
import os
import json
from pathlib import Path
from typing import Optional

from .models import CodingChallenge


def run_challenge(challenge: CodingChallenge, student_code: str) -> list[dict]:
    """Run student code against test cases and return results.

    Returns list of {"description": str, "passed": bool, "error": str | None}
    """
    results = []

    for i, tc in enumerate(challenge.test_cases):
        result = _run_single_test(student_code, tc, challenge)
        results.append(result)

    return results


def _run_single_test(student_code: str, test_case: dict, challenge: CodingChallenge) -> dict:
    """Run a single test case in a subprocess for safety."""
    description = test_case.get("description", f"Test case")

    # Build test script
    # We extract the function name from the starter code or challenge
    func_name = _extract_function_name(challenge.starter_code)
    if not func_name:
        func_name = "solution"

    test_input = test_case["input"]
    expected = test_case["expected"]

    test_script = f"""
import json
import sys

# Student's code
{student_code}

# Run test
try:
    args = {test_input}
    if not isinstance(args, tuple):
        args = (args,)
    result = {func_name}(*args)

    # Compare
    expected = {expected}
    if result == expected:
        print(json.dumps({{"passed": True}}))
    else:
        print(json.dumps({{"passed": False, "error": f"Expected {{expected!r}}, got {{result!r}}"}}))
except Exception as e:
    print(json.dumps({{"passed": False, "error": f"{{type(e).__name__}}: {{e}}"}}))
"""

    try:
        # Run in subprocess with timeout
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(test_script)
            f.flush()
            temp_path = f.name

        proc = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            text=True,
            timeout=10,
        )

        os.unlink(temp_path)

        if proc.returncode != 0:
            error = proc.stderr.strip().split("\n")[-1] if proc.stderr else "Unknown error"
            return {"description": description, "passed": False, "error": error}

        output = proc.stdout.strip()
        if output:
            data = json.loads(output)
            return {
                "description": description,
                "passed": data.get("passed", False),
                "error": data.get("error"),
            }
        else:
            return {"description": description, "passed": False, "error": "No output from test"}

    except subprocess.TimeoutExpired:
        try:
            os.unlink(temp_path)
        except:
            pass
        return {"description": description, "passed": False, "error": "Time limit exceeded (10s)"}
    except json.JSONDecodeError:
        return {"description": description, "passed": False, "error": "Invalid test output"}
    except Exception as e:
        return {"description": description, "passed": False, "error": str(e)}


def _extract_function_name(starter_code: str) -> Optional[str]:
    """Extract function name from starter code."""
    for line in starter_code.split("\n"):
        line = line.strip()
        if line.startswith("def "):
            name = line[4:].split("(")[0].strip()
            return name
    return None


def format_test_results(results: list[dict]) -> str:
    """Format test results for display."""
    lines = []
    for r in results:
        if r["passed"]:
            lines.append(f"  ✅ {r['description']}")
        else:
            lines.append(f"  ❌ {r['description']}")
            if r.get("error"):
                lines.append(f"     → {r['error']}")
    return "\n".join(lines)
