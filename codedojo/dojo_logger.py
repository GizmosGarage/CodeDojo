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

    def log_challenge(self, challenge_id: str, skill: str, requirements: list[str]):
        self._write(
            "challenge_generated",
            challenge_id=challenge_id,
            skill=skill,
            requirements=requirements,
        )

    def log_submission(
        self,
        challenge_id: str,
        code_snippet: str,
        output: str,
        validation: dict | None,
        verdict: str,
    ):
        self._write(
            "submission",
            challenge_id=challenge_id,
            code_snippet=code_snippet[:500],
            output=output[:300],
            validation=validation,
            verdict=verdict,
        )

    def log_error(self, error_type: str, context: str):
        self._write("error", error_type=error_type, context=context)
