"""Sensei AI — Claude API integration for CodeDojo."""

import json
import os
import re
from pathlib import Path
from typing import Optional

from anthropic import Anthropic
from anthropic import APIStatusError


def _load_env():
    """Load .env file from project root if present."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                k = key.strip()
                if not os.environ.get(k):  # override empty strings too
                    os.environ[k] = value.strip()

_load_env()

from .config import CLAUDE_MODEL, SENSEI_SYSTEM_PROMPT, SENSEI_GREETING_PROMPT, SENSEI_FAREWELL_PROMPT
from .models import QuizQuestion, CodingChallenge, CodeReviewResult


class Sensei:
    """AI-powered coding sensei backed by Claude."""

    def __init__(self):
        self.client = Anthropic()

    def _ask(self, system: str, user_prompt: str, max_tokens: int = 1024) -> str:
        """Send a message to Claude and return the text response."""
        try:
            response = self.client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return response.content[0].text
        except APIStatusError as e:
            if e.status_code == 400 and "credit balance is too low" in str(e):
                raise RuntimeError(
                    "No API credits available. Add credits at: https://console.anthropic.com/settings/billing"
                ) from None
            raise

    def _ask_json(self, system: str, user_prompt: str, max_tokens: int = 2048) -> dict:
        """Send a message expecting JSON response."""
        full_prompt = user_prompt + "\n\nRespond with ONLY valid JSON. No markdown, no backticks, no extra text."
        text = self._ask(system, full_prompt, max_tokens)
        # Strip any markdown fences
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        text = text.strip()
        return json.loads(text)

    # ── Greetings & Farewells ──────────────────────────────────────

    def greet(self, name: str, belt_name: str, belt_icon: str, xp: int,
              days_away: int, streak: int, weak_area: str, strong_area: str) -> str:
        prompt = SENSEI_GREETING_PROMPT.format(
            name=name, belt_name=belt_name, belt_icon=belt_icon, xp=xp,
            days_away=days_away, streak=streak, weak_area=weak_area, strong_area=strong_area,
        )
        return self._ask(SENSEI_SYSTEM_PROMPT, prompt, max_tokens=256)

    def farewell(self, name: str, xp_earned: int, activities: str,
                 belt_name: str, belt_icon: str, was_promoted: bool) -> str:
        promotion_note = "The student was PROMOTED to a new belt this session!" if was_promoted else ""
        prompt = SENSEI_FAREWELL_PROMPT.format(
            name=name, xp_earned=xp_earned, activities=activities,
            belt_name=belt_name, belt_icon=belt_icon, promotion_note=promotion_note,
        )
        return self._ask(SENSEI_SYSTEM_PROMPT, prompt, max_tokens=200)

    # ── Quiz Generation ────────────────────────────────────────────

    def generate_quiz(self, skill_id: str, skill_name: str, topics: list[str],
                      difficulty: str, count: int = 1) -> list[QuizQuestion]:
        prompt = f"""Generate {count} multiple-choice Python quiz question(s).

Skill area: {skill_name}
Topics to cover: {', '.join(topics)}
Difficulty: {difficulty}
Student belt level determines difficulty context.

Return a JSON array of objects, each with:
- "question": the question text (can include code snippets using backticks)
- "options": array of exactly 4 answer strings
- "correct_index": 0-based index of correct answer
- "explanation": brief explanation of why the answer is correct (2-3 sentences, in sensei voice)

Make questions that TEST UNDERSTANDING, not just memorization.
For intermediate/advanced: include code snippets that require reading and reasoning.
Make wrong answers plausible — no obvious throwaways."""

        data = self._ask_json(SENSEI_SYSTEM_PROMPT, prompt)
        questions = data if isinstance(data, list) else [data]

        return [
            QuizQuestion(
                question=q["question"],
                options=q["options"],
                correct_index=q["correct_index"],
                explanation=q["explanation"],
                skill_id=skill_id,
                difficulty=difficulty,
            )
            for q in questions[:count]
        ]

    # ── Coding Challenge Generation ────────────────────────────────

    def generate_challenge(self, skill_id: str, skill_name: str, topics: list[str],
                           difficulty: str) -> CodingChallenge:
        prompt = f"""Generate a Python coding challenge.

Skill area: {skill_name}
Topics: {', '.join(topics)}
Difficulty: {difficulty}

Return a JSON object with:
- "title": short challenge name
- "description": clear problem description (what the function should do, constraints, examples)
- "function_name": the name of the function the student should implement
- "starter_code": starter code with function signature and docstring (student fills in the body)
- "test_cases": array of objects with "input" (as string that can be eval'd), "expected" (expected return value as string), and "description" (what this test checks)
- "hints": array of 2-3 progressive hints (vague first, more specific later)
- "solution_approach": brief description of the right approach (do NOT give full solution code)

Requirements:
- The challenge should be a SINGLE function that takes input and returns output
- Test cases should be runnable: input is a string like "([1,2,3], 5)" that can be unpacked as args
- Include 3-5 test cases, including edge cases
- Difficulty guide: beginner=basic syntax/logic, intermediate=data structures/algorithms, advanced=complex problem-solving"""

        data = self._ask_json(SENSEI_SYSTEM_PROMPT, prompt, max_tokens=2048)

        return CodingChallenge(
            title=data["title"],
            description=data["description"],
            skill_id=skill_id,
            difficulty=difficulty,
            starter_code=data["starter_code"],
            test_cases=data["test_cases"],
            hints=data.get("hints", []),
            solution_approach=data.get("solution_approach", ""),
        )

    # ── Code Review ────────────────────────────────────────────────

    def review_code(self, code: str, context: str = "general Python code") -> CodeReviewResult:
        prompt = f"""Review this Python code as Sensei. The student submitted this for review.
Context: {context}

```python
{code}
```

Return a JSON object with:
- "score": integer 1-10 (be honest but fair)
- "strengths": array of 1-3 things done well
- "improvements": array of 1-3 specific improvements with brief explanation
- "sensei_feedback": 2-3 sentence overall feedback in sensei voice (strict but encouraging)
- "xp_earned": integer 10-30 based on code quality (10=poor, 20=decent, 30=excellent)

Be specific in your feedback. Reference actual lines/patterns in the code.
Do not be artificially generous — a score of 5 is average."""

        data = self._ask_json(SENSEI_SYSTEM_PROMPT, prompt, max_tokens=1024)

        return CodeReviewResult(
            score=data["score"],
            strengths=data["strengths"],
            improvements=data["improvements"],
            sensei_feedback=data["sensei_feedback"],
            xp_earned=data.get("xp_earned", 20),
        )

    # ── Challenge Evaluation ───────────────────────────────────────

    def evaluate_solution(self, challenge_title: str, code: str,
                          test_results: list[dict], all_passed: bool) -> str:
        """Get sensei commentary on a challenge attempt."""
        results_text = "\n".join(
            f"- {r['description']}: {'PASS' if r['passed'] else 'FAIL'}"
            for r in test_results
        )
        prompt = f"""The student attempted the challenge "{challenge_title}".
Test results:
{results_text}

All tests passed: {all_passed}

Their code:
```python
{code}
```

Give brief sensei feedback (2-3 sentences). If they passed, acknowledge it without being excessive.
If they failed, guide them toward the issue WITHOUT giving the answer.
Stay in character as Sensei."""

        return self._ask(SENSEI_SYSTEM_PROMPT, prompt, max_tokens=256)

    # ── Assessment ─────────────────────────────────────────────────

    def generate_assessment_questions(self) -> list[dict]:
        """Generate skill assessment questions covering multiple areas."""
        prompt = """Generate 8 Python assessment questions to evaluate a student's skill level.
Cover these areas in order (one question each + extras on weak spots):
1. Variables & basic types (beginner)
2. Control flow — loops and conditionals (beginner)
3. Functions — arguments, returns (beginner/intermediate)
4. Data structures — lists, dicts (intermediate)
5. List comprehensions (intermediate)
6. OOP — classes (intermediate)
7. Error handling (intermediate/advanced)
8. Decorators or generators (advanced)

Return a JSON array of objects, each with:
- "question": the question (include code snippets where appropriate)
- "options": exactly 4 options
- "correct_index": 0-based index
- "skill_area": which area this tests
- "difficulty": "beginner", "intermediate", or "advanced"

Questions should progressively get harder. Include code-reading questions for intermediate+."""

        data = self._ask_json(SENSEI_SYSTEM_PROMPT, prompt, max_tokens=4096)
        return data if isinstance(data, list) else []

    # ── Belt Exam Generation ──────────────────────────────────────

    def generate_belt_exam_quiz(self, belt_name: str, topics: list[str],
                                 difficulty: str, count: int) -> list[QuizQuestion]:
        """Generate quiz questions for a belt exam — harder than normal training."""
        prompt = f"""Generate {count} multiple-choice Python quiz questions for a BELT EXAM.

This is a {belt_name} promotion exam. The questions must be challenging enough to prove
the student has truly mastered the material, not just memorized it.

Topics to cover: {', '.join(topics)}
Difficulty: {difficulty} (exam-level — harder than normal training)

Return a JSON array of objects, each with:
- "question": the question text (include code snippets where appropriate)
- "options": array of exactly 4 answer strings
- "correct_index": 0-based index of correct answer
- "explanation": brief explanation of why the answer is correct

Requirements:
- Questions must TEST DEEP UNDERSTANDING, not surface knowledge
- Include tricky edge cases and "what does this code output?" questions
- Wrong answers should be very plausible — common misconceptions
- At least half the questions should involve reading/tracing code"""

        data = self._ask_json(SENSEI_SYSTEM_PROMPT, prompt, max_tokens=4096)
        questions = data if isinstance(data, list) else [data]

        return [
            QuizQuestion(
                question=q["question"],
                options=q["options"],
                correct_index=q["correct_index"],
                explanation=q.get("explanation", ""),
                skill_id="belt_exam",
                difficulty=difficulty,
            )
            for q in questions[:count]
        ]

    def generate_belt_exam_boss(self, belt_name: str, topics: list[str],
                                 difficulty: str) -> CodingChallenge:
        """Generate the BOSS challenge for a belt exam — the ultimate test."""
        prompt = f"""Generate a BOSS-LEVEL Python coding challenge for a {belt_name} promotion exam.

This is the FINAL challenge of the exam. It should combine multiple concepts and be
significantly harder than normal training challenges.

Topics this must cover (combine at least 3): {', '.join(topics)}
Difficulty: {difficulty} (boss-level — the hardest challenge for this belt)

Return a JSON object with:
- "title": epic challenge name (make it feel like a boss fight)
- "description": clear but challenging problem description
- "function_name": the name of the function to implement
- "starter_code": starter code with function signature and docstring
- "test_cases": array of 5-7 test cases (more than normal, including tough edge cases)
- "hints": array of 2 hints only (boss challenges should be harder)
- "solution_approach": brief description of the approach

Requirements:
- Must combine multiple concepts from the topics list
- Include edge cases that test deep understanding
- The problem should feel like a culmination of everything learned for this belt"""

        data = self._ask_json(SENSEI_SYSTEM_PROMPT, prompt, max_tokens=3072)

        return CodingChallenge(
            title=data["title"],
            description=data["description"],
            skill_id="belt_exam_boss",
            difficulty=difficulty,
            starter_code=data["starter_code"],
            test_cases=data["test_cases"],
            hints=data.get("hints", []),
            solution_approach=data.get("solution_approach", ""),
        )

    def evaluate_belt_exam(self, belt_name: str, rounds_passed: int,
                            total_rounds: int, weak_areas: list[str]) -> str:
        """Sensei evaluates a belt exam performance and gives feedback."""
        passed = rounds_passed >= total_rounds  # must pass ALL rounds
        pct = (rounds_passed / total_rounds * 100) if total_rounds > 0 else 0

        prompt = f"""The student just completed their {belt_name} promotion exam.

Results: {rounds_passed}/{total_rounds} rounds passed ({pct:.0f}%)
Outcome: {"PASSED — they earned their new belt!" if passed else "FAILED — they must train more."}
Weak areas observed: {', '.join(weak_areas) if weak_areas else 'None — perfect performance'}

Generate sensei feedback (3-4 sentences) that:
{"1. Congratulates them on passing and earning their belt" if passed else "1. Acknowledges their effort but is honest about what needs improvement"}
2. Specifically mentions their weak areas and what to focus on
3. {"Reminds them that earning a belt is just the beginning of true mastery" if passed else "Encourages them to train more in those specific areas before retrying"}
4. Stays in character as Sensei — strict but fair

Respond with ONLY the feedback dialogue."""

        return self._ask(SENSEI_SYSTEM_PROMPT, prompt, max_tokens=400)

    # ── General Conversation ───────────────────────────────────────

    def chat(self, message: str, context: str = "") -> str:
        """General sensei conversation."""
        prompt = message
        if context:
            prompt = f"Context: {context}\n\nStudent says: {message}"
        return self._ask(SENSEI_SYSTEM_PROMPT, prompt, max_tokens=512)
