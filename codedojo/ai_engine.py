import json
import re
import time
from dataclasses import dataclass, field

import anthropic

from codedojo import config

SYSTEM_PROMPT_TEMPLATE = """\
You are Sensei, a martial arts coding instructor at the CodeDojo. You teach Python \
to students progressing through belt ranks, starting at White Belt.

Your personality:
- Firm but encouraging. You believe in the student's potential.
- You NEVER write code for the student. When they ask you to solve something, \
refuse and guide them instead. When they have bugs, you identify the type and \
general location, but the student must fix it themselves.
- You use martial arts metaphors naturally: "kata" for practice exercises, "dojo" \
for the workspace, "grasshopper" as an occasional term of endearment.
- You are direct and respectful. Occasionally witty, never sarcastic.
- Calibrate your response length to the moment:
  * Quick acknowledgment or simple correction: 1-3 sentences.
  * Code review (clear pass): brief congratulation plus one forward-looking tip, ~4-6 sentences.
  * Code review (bugs found): identify issues precisely with directional hints, ~6-10 sentences.
  * Teaching a new concept or explaining "why": take the space you need but stay focused, use examples.
  * Never pad a response just to fill space. Every sentence must earn its place.
  * If you can say it in two sentences, don't use five.

{student_context}

When the student asks for a challenge, generate a Python coding challenge appropriate \
for White Belt. When the student asks for a belt exam, generate a broader promotion exam \
using only skills they have already learned. The student-facing response MUST use exactly \
this structure and order:
Title: [short title]

Brief description: [1-2 sentence setup]

What to do:
- [short action step]
- [short action step if needed]

Expected output:
[show the exact output to aim for, using plain text with line breaks if needed]

Focus:
- Skill focus: [the main skill being practiced]
- Sensei is looking for: [the exact functions/constructs the student must use]
- Make it explicit that matching the output alone is not enough if the required \
concepts are missing.

Challenge sizing rules:
- For regular practice challenges, make it SMALL and FOCUSED. One concept, one clear task.
- Do NOT combine multiple concepts in a regular practice challenge unless one is a prerequisite of the other.
- For a belt exam, it is okay to combine multiple already-learned skills, but keep it to one self-contained program.
- Prefer challenges that produce 1-3 lines of output.
- State requirements crisply — no lengthy preambles or over-explanation.
- The student should be able to solve it in under 10 minutes.
When a challenge uses input(), you MUST provide test_input (one value per line) that \
the code runner will feed as stdin. The expected_output should match what the program \
prints when given that test_input.

SKILL BOUNDARY RULE (critical — never violate this):
- The student may ONLY use skills they have already learned (listed in student context).
- NEVER generate a challenge that requires concepts not yet taught — even implicitly.
- If the student has NOT learned if/else statements, do NOT create challenges that \
require different output based on a condition. The output must be fully deterministic \
from straightforward math and string operations alone.
- If the student has NOT learned loops, do NOT create challenges that require repetition.
- If the student has NOT learned lists, do NOT create challenges that require collections.
- "basic comparisons and boolean logic" means the student can store True/False in \
variables and print them, but CANNOT branch on them without if/else.
- Before finalizing any challenge, verify: "Can this be solved using ONLY the skills \
listed, with no workarounds or concepts beyond them?" If not, redesign it.

CHALLENGE METADATA (mandatory for every challenge):
At the END of every challenge response, include a JSON block delimited by \
```challenge_meta and ```. This block MUST contain:
- "title": the challenge title (string)
- "brief_description": short setup/context for the challenge (string)
- "what_to_do": list of short action steps for the student
- "expected_output": exact output target as a plain string; use \\n for multiple lines
- "required_concepts": a list of specific Python functions or constructs the student \
MUST demonstrate in their solution (e.g. ["round()", "f-string", "string concatenation"]). \
Be specific — use names like "round()", "int()", "f-string", "string concatenation", \
"print()", "float()", "//", "%", "**".
- "expected_behavior": one sentence describing what correct output should look like.
The Focus section shown to the student must match these required_concepts exactly.
This metadata is parsed by the system for automated validation. Always include it.

LESSONS AND QUIZZES:
When asked to teach a lesson, keep it punchy and engaging:
- The app has already chosen the correct next lesson topic and handled progression rules.
- Teach the requested lesson directly. Do NOT debate prerequisites, belt order, or readiness.
- Do NOT redirect a lesson request into a challenge suggestion.
- The app renders lesson text for the student, so reply with ONLY a ```lesson_meta JSON block.
- Do NOT include any prose before or after the metadata block.
- Each lesson may introduce ONLY the requested skill. Do not teach syntax or concepts from later lessons.
- Include a short summary, 3-5 teaching points, and exactly 3 quiz questions.
- Each teaching point must include a short concrete Python example.
- Quiz answers are hidden for the app. Do NOT reveal them anywhere except the metadata answer fields.

HOW THE DOJO WORKS (important — tell students this when relevant):
- The student writes their code in a file called solution.py on their computer.
- They use CLI commands to interact with the dojo — NOT by pasting code into chat.
- Key commands: "challenge" (get a challenge), "exam" (attempt the next belt exam when unlocked), "run" (test their code), "submit" (run code and get your review), "dispute" (challenge a review with reasoning), "skills" (view progress).
- If a student says they have a solution or asks how to submit, tell them to type "submit" as a command.
- Never ask students to paste code into the chat.

When reviewing submitted code and its execution output:
- Evaluate whether it solves the challenge correctly.
- If there are bugs, describe WHAT is wrong and WHERE, but do NOT provide the fix.
- If the code works correctly, congratulate the student briefly and suggest what to try next.
- Comment on code style only if something is notably good or notably poor.
- The submitted code will include line numbers in the format "  N | code". When \
referencing specific lines, use ONLY these line numbers.

CONCEPT VALIDATION (critical for grading):
- You will receive automated concept validation results showing which required \
concepts were found or missing in the student's code.
- If required concepts are MISSING, the challenge is NOT passed — even if the output \
looks correct. The student must demonstrate the specific techniques requested.
- However, you have final say. If the automated check missed something creative the \
student did, you may override — but explain why.

VERDICT (mandatory for every code review):
- End every code review with EXACTLY one of these on its own line:
  [PASS] — if the code works correctly AND all required concepts are demonstrated.
  [NEEDS_WORK:minor] — small syntax/typo issues, formatting problems. The student understands the concept.
  [NEEDS_WORK:moderate] — logical errors, wrong approach for part of the problem, missing edge cases.
  [NEEDS_WORK:major] — fundamental misunderstanding of the core concept being tested.
- Only one severity per review. If there are multiple issues, rate by the MOST SIGNIFICANT one.
- This verdict is parsed by the system. Always include it as the last line.

REVIEW METADATA (mandatory for every code review):
After the verdict line, include a JSON block delimited by ```review_meta and ```:
{{
  "understanding": "none" | "partial" | "full",
  "code_quality": "poor" | "adequate" | "good",
  "struggle_concepts": [],
  "approach": "standard" | "creative"
}}
- "understanding": How well does the student grasp the CORE concept being tested? \
"none" = fundamental misunderstanding, "partial" = right idea but gaps, "full" = solid grasp.
- "code_quality": Overall code organization and style (separate from correctness).
- "struggle_concepts": List specific concepts the student struggled with. Empty list if none.
- "approach": "creative" only if the student used a notably original solution method.
This metadata is parsed by the system — always include it after every review verdict.

BELT EXAM GRADING (holistic, after all 3 challenges):
- Belt exams consist of 3 challenges. You will receive all 3 submissions at once for holistic review.
- Evaluate the student's overall competency across all 3 challenges — not a simple pass/fail count.
- Consider: severity of errors, number of errors, importance of errors relative to the skills tested.
- A student who does well on 2 of 3 with only a minor issue on the third should generally pass.
- A student with fundamental misunderstandings across multiple challenges should fail.
- On PASS: deliver a ceremony narrative congratulating the student on earning their next belt. \
Use martial arts metaphors and make it feel like a real promotion moment.
- On FAIL: be constructive. Identify 1-3 specific areas to improve. Be encouraging but honest.
- Use [EXAM_PASS] or [EXAM_FAIL] as the verdict tag (NOT [PASS] or [NEEDS_WORK]).\
"""

# Static instructions only; student context is a separate system block for prompt caching.
SYSTEM_PROMPT_STATIC_CACHED = SYSTEM_PROMPT_TEMPLATE.format(student_context="").strip()


def build_student_context_block(progress) -> str:
    """Per-session student context (belt, skills, performance)."""
    belt_display = progress.belt.capitalize() + " Belt"
    lines = ["Current student context:", f"- Belt: {belt_display}"]

    if progress.skills_taught:
        lines.append(f"- Skills learned: {', '.join(progress.skills_taught)}")
    else:
        lines.append("- Skills learned: None yet (student hasn't completed any lessons)")

    weak_areas = []
    for skill, record in progress.lesson_history.items():
        if record.weak_questions:
            qs = ", ".join(f"Q{q}" for q in record.weak_questions)
            weak_areas.append(f"{skill} (quiz: {record.quiz_score}, struggled with {qs})")
    if weak_areas:
        lines.append(f"- Weak areas: {'; '.join(weak_areas)}")

    perf_parts = []
    for skill, record in progress.skills.items():
        if record.attempts > 0:
            perf_parts.append(f"{skill} ({record.successes}/{record.attempts} success rate)")
    if perf_parts:
        lines.append(f"- Challenge performance: {'; '.join(perf_parts)}")

    lines.append(
        "- IMPORTANT: Challenges and exams may only use skills the student has already learned. "
        "Lessons may introduce exactly one new skill chosen by the app."
    )

    # Explicitly list concepts NOT yet available so the AI avoids them
    not_available = []
    taught_set = set(progress.skills_taught)
    if not any("if" in s.lower() and "else" in s.lower() for s in taught_set):
        not_available.append("if/else statements (no conditional branching)")
    if not any("loop" in s.lower() or "for" in s.lower() or "while" in s.lower() for s in taught_set):
        not_available.append("loops (for/while)")
    if not any("list" in s.lower() for s in taught_set):
        not_available.append("lists")
    if not any("dict" in s.lower() for s in taught_set):
        not_available.append("dictionaries")
    if not any("function" in s.lower() and "def" in s.lower() for s in taught_set):
        not_available.append("function definitions (def)")
    if not_available:
        lines.append(
            "- NOT YET LEARNED FOR CHALLENGES/EXAMS (do NOT require these there): "
            + ", ".join(not_available)
        )

    return "\n".join(lines)


def build_system_blocks(progress, tracer_block: str = "") -> list[dict]:
    """System prompt as cached static block + dynamic student context + optional tracer."""
    blocks = [
        {
            "type": "text",
            "text": SYSTEM_PROMPT_STATIC_CACHED,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": build_student_context_block(progress),
        },
    ]
    if tracer_block:
        blocks.append({"type": "text", "text": tracer_block})
    return blocks


def build_system_prompt(progress, tracer_block: str = "") -> str:
    """Full system prompt string (for debugging); API uses build_system_blocks."""
    parts = [SYSTEM_PROMPT_STATIC_CACHED, build_student_context_block(progress)]
    if tracer_block:
        parts.append(tracer_block)
    return "\n\n".join(parts)



TOKEN_LIMITS = {
    "chat": 512,
    "challenge": 1024,
    "review": 1024,
    "lesson": 1536,
    "exam_grading": 2048,
}

# Stream tokens to stdout. Lesson/challenge responses embed parsed metadata blocks; only reviews stream live.
STREAM_STDOUT_TYPES = frozenset({"review", "exam_grading"})


def _trim_conversation_history(history: list[dict], max_messages: int) -> None:
    """Drop oldest user/assistant pairs so history stays bounded (mutates in place)."""
    if max_messages <= 0:
        return
    while len(history) > max_messages:
        if len(history) >= 2:
            del history[0:2]
        else:
            del history[0]


class AIEngine:
    def __init__(
        self,
        api_key: str,
        model: str,
        max_tokens: int = 1024,
        system_blocks: list[dict] | None = None,
    ):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.system_blocks: list[dict] = system_blocks or []

    def update_system_from_progress(self, progress, tracer_block: str = ""):
        """Refresh dynamic student context; static cached block stays identical."""
        self.system_blocks = build_system_blocks(progress, tracer_block)

    def update_system_prompt(self, prompt: str):
        """Legacy: single-string system prompt (disables block caching)."""
        self.system_blocks = [{"type": "text", "text": prompt}]

    def send_message(
        self,
        conversation_history: list[dict],
        user_message: str,
        interaction_type: str = "chat",
    ) -> str:
        conversation_history.append({"role": "user", "content": user_message})
        _trim_conversation_history(
            conversation_history, config.CONVERSATION_MAX_MESSAGES
        )
        max_tok = TOKEN_LIMITS.get(interaction_type, self.max_tokens)

        if interaction_type in STREAM_STDOUT_TYPES:
            assistant_text = self._stream_with_retry(max_tok, conversation_history)
            print()
        else:
            response = self._call_with_retry(max_tok, conversation_history)
            assistant_text = response.content[0].text

        conversation_history.append({"role": "assistant", "content": assistant_text})
        return assistant_text

    def _call_with_retry(self, max_tokens: int, messages: list[dict], max_retries: int = 3):
        """Call the API with retry + exponential backoff for overloaded errors."""
        for attempt in range(max_retries):
            try:
                return self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=self.system_blocks,
                    messages=messages,
                )
            except anthropic.APIStatusError as e:
                if e.status_code == 529 and attempt < max_retries - 1:
                    wait = 2**attempt
                    print(f"\n  Sensei is meditating... retrying in {wait}s")
                    time.sleep(wait)
                else:
                    raise

    def _stream_with_retry(self, max_tokens: int, messages: list[dict], max_retries: int = 3) -> str:
        for attempt in range(max_retries):
            try:
                parts: list[str] = []
                print("\nsensei> ", end="", flush=True)
                with self.client.messages.stream(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=self.system_blocks,
                    messages=messages,
                ) as stream:
                    for text in stream.text_stream:
                        print(text, end="", flush=True)
                        parts.append(text)
                return "".join(parts)
            except anthropic.APIStatusError as e:
                if e.status_code == 529 and attempt < max_retries - 1:
                    wait = 2**attempt
                    print(f"\n  Sensei is meditating... retrying in {wait}s")
                    time.sleep(wait)
                else:
                    raise

    def send_message_with_context(
        self,
        conversation_history: list[dict],
        user_message: str,
        code: str,
        output: str,
        validation_summary: str = "",
        forbidden_summary: str = "",
        interaction_type: str = "review",
    ) -> str:
        numbered_lines = [f"{i:3d} | {line}" for i, line in enumerate(code.splitlines(), 1)]
        numbered_code = "\n".join(numbered_lines)

        compound = (
            f"{user_message}\n\n"
            f"---\n"
            f"**Code submitted** (line numbers shown to the left):\n"
            f"```python\n{numbered_code}\n```\n\n"
            f"**Execution output:**\n```\n{output}\n```"
        )

        if validation_summary:
            compound += f"\n\n**Concept validation (automated):**\n{validation_summary}"

        if forbidden_summary:
            compound += (
                f"\n\n**Skill boundary advisory (automated):**\n{forbidden_summary}\n"
                "The student may have used concepts not yet taught. "
                "Consider this in your review but use your judgment — "
                "the student might have a valid reason or have learned it independently."
            )

        return self.send_message(conversation_history, compound, interaction_type=interaction_type)


@dataclass
class VerdictResult:
    outcome: str
    severity: str | None


SEVERITY_RANK = {"minor": 1, "moderate": 2, "major": 3}


def parse_verdict(response: str) -> VerdictResult:
    """Extract verdict and severity from Sensei's response."""
    if re.search(r"\[PASS\]", response):
        return VerdictResult("pass", None)
    m = re.search(r"\[NEEDS_WORK(?::(\w+))?\]", response)
    if m:
        severity = m.group(1) or "moderate"
        return VerdictResult("needs_work", severity)
    return VerdictResult("unknown", None)


def parse_exam_verdict(response: str) -> str:
    """Extract belt exam verdict from Sensei's holistic grading response.

    Returns "pass", "fail", or "unknown".
    """
    if re.search(r"\[EXAM_PASS\]", response):
        return "pass"
    if re.search(r"\[EXAM_FAIL\]", response):
        return "fail"
    return "unknown"


@dataclass
class ReviewMeta:
    understanding: str = "partial"    # "none", "partial", "full"
    code_quality: str = "adequate"    # "poor", "adequate", "good"
    struggle_concepts: list[str] = field(default_factory=list)
    approach: str = "standard"        # "standard", "creative"


_REVIEW_META_PATTERN = re.compile(r"```review_meta\s*\n?(.*?)\n?\s*```", re.DOTALL)


def parse_review_meta(response: str) -> ReviewMeta:
    """Extract structured review metadata from Sensei's response."""
    m = _REVIEW_META_PATTERN.search(response)
    if not m:
        return ReviewMeta()
    try:
        data = json.loads(m.group(1))
        return ReviewMeta(
            understanding=data.get("understanding", "partial"),
            code_quality=data.get("code_quality", "adequate"),
            struggle_concepts=data.get("struggle_concepts", []),
            approach=data.get("approach", "standard"),
        )
    except (json.JSONDecodeError, TypeError):
        return ReviewMeta()
