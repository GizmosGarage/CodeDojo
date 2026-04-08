"""Tests for code_runner stdin support."""

import textwrap
from pathlib import Path

from codedojo.code_runner import run_code


def test_run_code_with_stdin(tmp_path: Path):
    script = tmp_path / "greet.py"
    script.write_text(textwrap.dedent("""\
        name = input("Name: ")
        print(f"Hello, {name}!")
    """))
    result = run_code(script, stdin_input="Alice\n")
    assert result.returncode == 0
    assert "Hello, Alice!" in result.stdout
    assert not result.timed_out


def test_run_code_without_stdin_gets_eof_error(tmp_path: Path):
    script = tmp_path / "blocking.py"
    script.write_text("x = input()\n")
    result = run_code(script, timeout=2, stdin_input=None)
    assert result.returncode != 0
    assert "EOFError" in result.stderr


def test_run_code_multiple_inputs(tmp_path: Path):
    script = tmp_path / "two_inputs.py"
    script.write_text(textwrap.dedent("""\
        a = input()
        b = input()
        print(int(a) + int(b))
    """))
    result = run_code(script, stdin_input="3\n7\n")
    assert result.returncode == 0
    assert "10" in result.stdout
