import json
from datetime import datetime, timezone
from pathlib import Path


class DojoLogger:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = open(self.log_path, "a", encoding="utf-8")

    def _write(self, event: str, **fields):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **fields,
        }
        self._fp.write(json.dumps(entry) + "\n")

    def flush(self):
        if self._fp:
            self._fp.flush()

    def close(self):
        if self._fp:
            self._fp.flush()
            self._fp.close()
            self._fp = None

    def log_session_start(self):
        self._write("session_start")

    def log_session_end(self):
        self._write("session_end")
        self.flush()

    def log_challenge(
        self,
        challenge_id: str,
        skill: str,
        title: str,
        expected_behavior: str,
        requirements: list[str],
    ):
        self._write(
            "challenge_generated",
            challenge_id=challenge_id,
            skill=skill,
            title=title,
            expected_behavior=expected_behavior,
            requirements=requirements,
        )

    def log_submission(
        self,
        challenge_id: str,
        code_snippet: str,
        output: str,
        validation: dict | None,
        verdict: str,
        *,
        severity: str | None = None,
        attempt_number: int = 0,
        forbidden_concepts: list[str] | None = None,
        timed_out: bool = False,
        code_lines: int = 0,
        missing_concepts: list[str] | None = None,
        understanding: str | None = None,
        code_quality: str | None = None,
        struggle_concepts: list[str] | None = None,
        approach: str | None = None,
    ):
        self._write(
            "submission",
            challenge_id=challenge_id,
            code_snippet=code_snippet[:500],
            output=output[:300],
            validation=validation,
            verdict=verdict,
            severity=severity,
            attempt_number=attempt_number,
            forbidden_concepts=forbidden_concepts or [],
            timed_out=timed_out,
            code_lines=code_lines,
            missing_concepts=missing_concepts or [],
            understanding=understanding,
            code_quality=code_quality,
            struggle_concepts=struggle_concepts or [],
            approach=approach,
        )

    def log_dispute(
        self,
        challenge_id: str,
        reasoning: str,
        verdict: str,
        overturned: bool,
    ):
        self._write(
            "submission_dispute",
            challenge_id=challenge_id,
            reasoning=reasoning[:300],
            verdict=verdict,
            overturned=overturned,
        )

    def log_exam_start(self, exam_id: str, belt: str):
        self._write("exam_start", exam_id=exam_id, belt=belt)

    def log_exam_challenge_submit(
        self, exam_id: str, challenge_index: int, challenge_id: str
    ):
        self._write(
            "exam_challenge_submit",
            exam_id=exam_id,
            challenge_index=challenge_index,
            challenge_id=challenge_id,
        )

    def log_exam_result(
        self, exam_id: str, verdict: str, belt_before: str, belt_after: str
    ):
        self._write(
            "exam_result",
            exam_id=exam_id,
            verdict=verdict,
            belt_before=belt_before,
            belt_after=belt_after,
        )

    def log_error(self, error_type: str, context: str):
        self._write("error", error_type=error_type, context=context)
