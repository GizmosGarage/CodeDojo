import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RunResult:
    stdout: str
    stderr: str
    returncode: int
    timed_out: bool


def run_code(file_path: Path, timeout: int = 10) -> RunResult:
    if not file_path.exists():
        return RunResult(
            stdout="",
            stderr=f"File not found: {file_path}",
            returncode=1,
            timed_out=False,
        )

    if file_path.suffix != ".py":
        return RunResult(
            stdout="",
            stderr=f"Not a Python file: {file_path}",
            returncode=1,
            timed_out=False,
        )

    try:
        result = subprocess.run(
            [sys.executable, str(file_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(file_path.parent),
        )
        return RunResult(
            stdout=result.stdout,
            stderr=result.stderr,
            returncode=result.returncode,
            timed_out=False,
        )
    except subprocess.TimeoutExpired:
        return RunResult(
            stdout="",
            stderr=f"Code timed out after {timeout} seconds.",
            returncode=1,
            timed_out=True,
        )
