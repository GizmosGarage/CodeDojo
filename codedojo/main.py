import uuid

from codedojo import config
from codedojo.ai_engine import (
    AIEngine,
    STREAM_STDOUT_TYPES,
    build_system_blocks,
    parse_exam_verdict,
    parse_verdict,
    SEVERITY_RANK,
)
from codedojo.belt_exam import (
    BeltExamState,
    ExamChallengeRecord,
    clear_belt_exam,
    load_belt_exam,
    save_belt_exam,
)
from codedojo.challenge_gen import (
    all_skills_up_to_belt,
    build_exam_final_grading_prompt,
    get_belt_exam_prompt,
    get_challenge_prompt,
    get_lesson_prompt,
    NoNewSkillsError,
    parse_challenge_response,
    parse_quiz_answers,
    skills_for_belt,
    strip_quiz_meta,
)
from codedojo.code_runner import run_code
from codedojo.code_validator import validate_concepts
from codedojo.dojo_logger import DojoLogger
from codedojo.knowledge_tracer import KnowledgeTracer
from codedojo.progress import Progress
from codedojo.session import ReviewState, Session
from codedojo.session_persist import (
    save_interrupted_challenge,
    clear_interrupted_challenge,
)

def get_banner(progress: Progress) -> str:
    return f"""\
=======================================
  CODEDOJO - Python Training System
  {progress.summary_line()}
=======================================
  Commands:
    lesson     - Learn a new Python topic
    challenge  - Practice a skill you've learned
    exam       - Attempt your next belt exam
    skills     - View your skill progress
    help       - Show all commands
    quit       - Exit the dojo
=======================================
  Type anything else to talk to Sensei.
======================================="""


HELP_TEXT = """\
  lesson     - Learn a new Python topic (teach + quiz)
  challenge  - Practice a skill you've learned (coding challenge)
  exam       - Attempt your next belt exam once all lessons are unlocked
  quiz a b c - Answer the quiz (e.g. 'quiz a b c')
  submit     - Submit solution.py for Sensei review
  dispute    - Challenge a failed review with your reasoning
  run        - Run solution.py and see output (no review)
  leave      - Save current challenge and step away
  resume     - Resume a saved challenge
  skills     - View your skill progress
  clear      - Reset conversation history
  help       - Show this message
  quit       - Exit the dojo"""

CHALLENGE_GENERATION_MAX_ATTEMPTS = 4


def print_sensei(text: str):
    print(f"\nsensei> {text}")


def print_output(result):
    if result.stdout:
        print(f"\n--- Output ---\n{result.stdout.rstrip()}")
    if result.stderr:
        print(f"\n--- Error ---\n{result.stderr.rstrip()}")
    if result.timed_out:
        print("\n(Code execution timed out)")
    if not result.stdout and not result.stderr and not result.timed_out:
        print("\n(No output)")


def clear_review_state(session: Session) -> None:
    session.awaiting_dispute_reason = False
    session.last_review = None


def belt_name(progress: Progress) -> str:
    return progress.belt.capitalize() + " Belt"


def current_activity_name(session: Session) -> str:
    if session.current_challenge_kind == "belt_exam":
        return "belt exam"
    return "challenge"


def print_belt_exam_unlock_message(progress: Progress) -> None:
    remaining = progress.belt_exam_attempts_remaining(config.BELT_EXAM_DAILY_LIMIT)
    print(f"\n  You've unlocked the {belt_name(progress)} exam.")
    if remaining > 0:
        print(
            f"  Type 'exam' when you want to try it. "
            f"You have {remaining} of {config.BELT_EXAM_DAILY_LIMIT} attempts left today."
        )
    else:
        print(
            f"  You've used all {config.BELT_EXAM_DAILY_LIMIT} exam attempts for today. "
            "Come back tomorrow to try again."
        )
    print("  You can also keep practicing with 'challenge'.")


def offer_interrupted_activity(
    session: Session,
    interrupted: dict,
    requested_action: str,
) -> None:
    spec = interrupted["challenge"]
    stored_kind = interrupted.get("challenge_kind", "practice")
    label = "belt exam" if stored_kind == "belt_exam" else "challenge"
    print(f'\n  You have an unfinished {label}: "{spec.title}" ({spec.skill})')
    print("  Type 'resume' to continue or 'new' for a fresh start.")
    session.pending_resume = {
        **interrupted,
        "requested_action": requested_action,
    }


def finish_passed_activity(progress: Progress, session: Session):
    is_belt_exam = session.current_challenge_kind == "belt_exam"
    if not is_belt_exam:
        print(f"\n  +XP! {progress.summary_line()}")
    session.current_challenge = None
    session.current_challenge_kind = None
    session.challenge_active = False
    session.attempt_count = 0
    session.worst_severity = None
    session.phase = "idle"
    session.current_skill = None
    clear_review_state(session)
    clear_interrupted_challenge(config.INTERRUPTED_CHALLENGE_FILE)
    session.invalidate_interrupted_snapshot()
    if is_belt_exam:
        print(f"\n  {belt_name(progress)} exam passed!")
        print("  Type 'challenge' to keep practicing.")
    else:
        print("\n  Ready for another challenge? (yes/no)")


def build_dispute_prompt(previous_review: str, student_reasoning: str) -> str:
    return (
        "Sensei, the student disputes your most recent review and wants you to reconsider it carefully.\n\n"
        f"Student rebuttal:\n{student_reasoning.strip()}\n\n"
        "Your previous review was:\n"
        f"{previous_review}\n\n"
        "Re-evaluate the same submitted code and output. Address the student's reasoning directly.\n"
        "If your previous judgment was too strict or mistaken, correct yourself clearly, acknowledge the mistake, "
        "and pass the student.\n"
        "If the student is still missing the target, explain why briefly and keep the verdict as needs work.\n"
        "End with the same required verdict tag format."
    )


def handle_lesson(engine: AIEngine, session: Session, logger: DojoLogger, progress: Progress):
    """Start a lesson on a new (untaught) skill."""
    untaught = progress.get_untaught_skills(skills_for_belt(progress.belt))
    if not untaught:
        print_belt_exam_unlock_message(progress)
        return

    try:
        prompt, skill = get_lesson_prompt(available_skills=untaught)
    except NoNewSkillsError:
        print_belt_exam_unlock_message(progress)
        return

    session.current_skill = skill
    print(f"\nSensei is preparing a lesson on: {skill}...")
    try:
        response = engine.send_message(
            session.conversation_history, prompt, interaction_type="lesson"
        )
        session.quiz_answers = parse_quiz_answers(response)
        display_text = strip_quiz_meta(response)
        session.phase = "quiz"
        print_sensei(display_text)
        print("\n  Answer the quiz: quiz [your answers]  (e.g. 'quiz a b c')")
    except Exception as e:
        logger.log_error("lesson_error", str(e))
        print(f"\nError communicating with Sensei: {e}")


def handle_quiz(
    engine: AIEngine, session: Session, logger: DojoLogger, progress: Progress,
    user_answers: list[str], tracer: KnowledgeTracer | None = None,
):
    """Check quiz answers and record the lesson."""
    correct = session.quiz_answers or []
    total = len(correct)
    score = 0
    wrong_questions = []

    if not total:
        print("\n  No quiz to check.")
    else:
        score = sum(
            1 for u, c in zip(user_answers, correct) if u.lower() == c.lower()
        )
        wrong_questions = [
            i + 1
            for i, (u, c) in enumerate(zip(user_answers, correct))
            if u.lower() != c.lower()
        ]
        if score == total:
            print(f"\n  Perfect! {score}/{total} correct.")
        else:
            print(f"\n  {score}/{total} correct.")
            wrong_strs = [str(q) for q in wrong_questions]
            clarify_prompt = (
                f"I got question(s) {', '.join(wrong_strs)} wrong on the quiz. "
                "Briefly explain the correct answers."
            )
            try:
                resp = engine.send_message(
                    session.conversation_history, clarify_prompt, interaction_type="chat"
                )
                print_sensei(resp)
            except Exception as e:
                logger.log_error("quiz_clarify_error", str(e))

    # Record lesson and refresh Sensei's context
    skill = session.current_skill or "unknown"
    progress.record_lesson(skill, score, total, wrong_questions)
    progress.save(config.PROGRESS_FILE)
    tracer_block = tracer.format_block(progress) if tracer else ""
    engine.update_system_from_progress(progress, tracer_block)

    print(f"\n  Lesson complete! You've learned '{skill}'.")
    if progress.has_unlocked_belt_exam(skills_for_belt(progress.belt)):
        print_belt_exam_unlock_message(progress)
    else:
        print("  Type 'challenge' to practice, or 'lesson' for another topic.")
    session.phase = "idle"
    session.current_skill = None
    session.quiz_answers = []


def show_skill_menu(progress: Progress):
    """Display numbered list of learned skills for challenge selection."""
    print("\n  Choose a skill to practice:")
    max_name = max(len(skill) for skill in progress.skills_taught)
    for i, skill in enumerate(progress.skills_taught, 1):
        label = progress.skill_progress_label(skill)
        print(f"    {i}. {skill.ljust(max_name)}  {label}")
    print("\n  Type a number to select, or 'back' to cancel.")


def start_challenge_selection(progress: Progress, session: Session) -> None:
    """Route the user into fresh challenge selection when skills are available."""
    if not progress.skills_taught:
        print("\n  You haven't learned any skills yet. Type 'lesson' to start!")
        session.phase = "idle"
        return

    show_skill_menu(progress)
    session.phase = "choosing_skill"


def handle_challenge_generate(
    engine: AIEngine,
    session: Session,
    logger: DojoLogger,
    progress: Progress,
    skill: str,
):
    """Generate and start a coding challenge for the given skill."""
    print("\nRequesting challenge from Sensei...")
    try:
        recent_challenges = progress.get_recent_challenge_descriptors(skill, limit=5)
        duplicate_warning = None

        for attempt in range(1, CHALLENGE_GENERATION_MAX_ATTEMPTS + 1):
            prompt, chosen_skill = get_challenge_prompt(
                skill=skill,
                recent_challenges=recent_challenges,
                duplicate_warning=duplicate_warning,
            )
            temp_history = list(session.conversation_history)
            response = engine.send_message(temp_history, prompt, interaction_type="challenge")
            spec = parse_challenge_response(response, chosen_skill)

            similar = progress.find_similar_challenge(
                skill=spec.skill,
                title=spec.title,
                expected_behavior=spec.expected_behavior,
                required_concepts=spec.required_concepts,
            )
            if similar:
                duplicate_warning = {
                    "title": similar.title,
                    "expected_behavior": similar.expected_behavior,
                    "required_concepts": list(similar.required_concepts),
                }
                if attempt < CHALLENGE_GENERATION_MAX_ATTEMPTS:
                    print("  Sensei repeated a familiar kata. Asking for a fresher challenge...")
                    continue

                logger.log_error(
                    "challenge_repeat_error",
                    (
                        f"skill={skill}; generated_title={spec.title}; "
                        f"prior_title={similar.title}; prior_behavior={similar.expected_behavior}"
                    ),
                )
                print(
                    "\n  Sensei kept circling back to an old challenge. "
                    "Try 'challenge' again or choose another skill."
                )
                return

            session.conversation_history = temp_history
            session.current_challenge = spec
            session.current_challenge_kind = "practice"
            session.challenge_active = True
            session.attempt_count = 0
            session.worst_severity = None
            session.phase = "challenge"
            session.current_skill = spec.skill
            clear_review_state(session)
            progress.record_generated_challenge(
                skill=spec.skill,
                challenge_id=spec.challenge_id,
                title=spec.title,
                expected_behavior=spec.expected_behavior,
                required_concepts=spec.required_concepts,
            )
            progress.save(config.PROGRESS_FILE)
            logger.log_challenge(
                challenge_id=spec.challenge_id,
                skill=spec.skill,
                title=spec.title,
                expected_behavior=spec.expected_behavior,
                requirements=spec.required_concepts,
            )
            print_sensei(spec.narrative)
            return
    except Exception as e:
        logger.log_error("challenge_error", str(e))
        print(f"\nError communicating with Sensei: {e}")


def _generate_next_exam_challenge(
    engine: AIEngine,
    session: Session,
    logger: DojoLogger,
    progress: Progress,
    exam_state: BeltExamState,
) -> bool:
    """Generate the next exam challenge and add it to the exam state.

    Returns True on success, False on failure.
    """
    challenge_number = len(exam_state.challenges) + 1
    total = config.BELT_EXAM_CHALLENGES_PER_EXAM
    exam_label = f"{belt_name(progress)} Exam"

    # Build prior exam challenge summaries for variety
    prior_exam_challenges = [
        {
            "title": rec.challenge_spec.title,
            "expected_behavior": rec.challenge_spec.expected_behavior,
            "required_concepts": list(rec.challenge_spec.required_concepts),
        }
        for rec in exam_state.challenges
    ]

    recent_challenges = progress.get_recent_challenge_descriptors(exam_label, limit=3)
    duplicate_warning = None

    for attempt in range(1, CHALLENGE_GENERATION_MAX_ATTEMPTS + 1):
        prompt, chosen_skill = get_belt_exam_prompt(
            belt_name(progress),
            all_skills_up_to_belt(progress.belt),
            challenge_number=challenge_number,
            total_challenges=total,
            prior_exam_challenges=prior_exam_challenges,
            recent_challenges=recent_challenges,
            duplicate_warning=duplicate_warning,
        )
        temp_history = list(session.conversation_history)
        response = engine.send_message(temp_history, prompt, interaction_type="challenge")
        spec = parse_challenge_response(response, chosen_skill)

        similar = progress.find_similar_challenge(
            skill=spec.skill,
            title=spec.title,
            expected_behavior=spec.expected_behavior,
            required_concepts=spec.required_concepts,
        )
        if similar:
            duplicate_warning = {
                "title": similar.title,
                "expected_behavior": similar.expected_behavior,
                "required_concepts": list(similar.required_concepts),
            }
            if attempt < CHALLENGE_GENERATION_MAX_ATTEMPTS:
                print("  Sensei repeated a familiar exam format. Asking for a fresher test...")
                continue

            logger.log_error(
                "belt_exam_repeat_error",
                (
                    f"belt={progress.belt}; generated_title={spec.title}; "
                    f"prior_title={similar.title}; prior_behavior={similar.expected_behavior}"
                ),
            )
            print(
                "\n  Sensei kept circling back to an old belt exam challenge. "
                "Try 'exam' again later."
            )
            return False

        session.conversation_history = temp_history
        exam_state.challenges.append(ExamChallengeRecord(challenge_spec=spec))
        exam_state.current_index = len(exam_state.challenges) - 1

        # Set session state so submit works
        session.current_challenge = spec
        session.current_challenge_kind = "belt_exam"
        session.challenge_active = True
        session.attempt_count = 0
        session.worst_severity = None
        session.phase = "challenge"
        session.current_skill = spec.skill
        clear_review_state(session)

        progress.record_generated_challenge(
            skill=spec.skill,
            challenge_id=spec.challenge_id,
            title=spec.title,
            expected_behavior=spec.expected_behavior,
            required_concepts=spec.required_concepts,
        )
        progress.save(config.PROGRESS_FILE)
        logger.log_challenge(
            challenge_id=spec.challenge_id,
            skill=spec.skill,
            title=spec.title,
            expected_behavior=spec.expected_behavior,
            requirements=spec.required_concepts,
        )
        save_belt_exam(config.BELT_EXAM_FILE, exam_state)
        return True

    return False


def handle_belt_exam_generate(
    engine: AIEngine,
    session: Session,
    logger: DojoLogger,
    progress: Progress,
    tracer: KnowledgeTracer | None = None,
):
    """Generate and start a user-initiated belt exam, or resume one in progress."""
    # Check for an in-progress exam on disk
    exam_state = session.belt_exam_state or load_belt_exam(config.BELT_EXAM_FILE)
    if exam_state:
        session.belt_exam_state = exam_state
        _resume_belt_exam(engine, session, logger, progress, exam_state, tracer)
        return

    untaught = progress.get_untaught_skills(skills_for_belt(progress.belt))
    if untaught:
        print(f"\n  The {belt_name(progress)} exam unlocks once all lessons are unlocked.")
        print(f"  Remaining lessons: {', '.join(untaught)}")
        return

    attempts_left = progress.belt_exam_attempts_remaining(config.BELT_EXAM_DAILY_LIMIT)
    if attempts_left <= 0:
        print(
            f"\n  You've used all {config.BELT_EXAM_DAILY_LIMIT} "
            f"{belt_name(progress)} exam attempts for today."
        )
        print("  Come back tomorrow, or keep practicing with 'challenge'.")
        return

    # Create a new exam
    exam_state = BeltExamState.new(
        exam_id=uuid.uuid4().hex[:8],
        belt=progress.belt,
    )
    session.belt_exam_state = exam_state
    logger.log_exam_start(exam_state.exam_id, exam_state.belt)

    total = config.BELT_EXAM_CHALLENGES_PER_EXAM
    print(f"\nSensei is preparing your {belt_name(progress)} exam ({total} challenges)...")

    try:
        if _generate_next_exam_challenge(engine, session, logger, progress, exam_state):
            print(f"\n  Belt exam challenge 1 of {total}:")
            print_sensei(exam_state.current_challenge.challenge_spec.narrative)
        else:
            session.belt_exam_state = None
            clear_belt_exam(config.BELT_EXAM_FILE)
    except Exception as e:
        logger.log_error("belt_exam_error", str(e))
        print(f"\nError communicating with Sensei: {e}")
        session.belt_exam_state = None
        clear_belt_exam(config.BELT_EXAM_FILE)


def _resume_belt_exam(
    engine: AIEngine,
    session: Session,
    logger: DojoLogger,
    progress: Progress,
    exam_state: BeltExamState,
    tracer: KnowledgeTracer | None = None,
):
    """Resume an in-progress belt exam."""
    total = config.BELT_EXAM_CHALLENGES_PER_EXAM
    submitted = exam_state.challenges_submitted
    current = exam_state.current_challenge

    if exam_state.all_submitted:
        # All submitted but not yet graded (e.g., crashed during grading)
        print("\n  All exam challenges were already submitted. Sending to Sensei for grading...")
        handle_exam_final_grading(engine, session, logger, progress, tracer)
        return

    if current and current.submitted:
        # Current challenge submitted, need to generate next one
        print(f"\n  Resuming your {belt_name(progress)} exam. "
              f"Challenges submitted: {submitted}/{total}.")
        print("  Generating your next exam challenge...")
        try:
            if _generate_next_exam_challenge(engine, session, logger, progress, exam_state):
                idx = len(exam_state.challenges)
                print(f"\n  Belt exam challenge {idx} of {total}:")
                print_sensei(exam_state.current_challenge.challenge_spec.narrative)
        except Exception as e:
            logger.log_error("belt_exam_error", str(e))
            print(f"\nError communicating with Sensei: {e}")
    elif current:
        # Current challenge not yet submitted — re-display it
        idx = exam_state.current_index + 1
        print(f"\n  Resuming your {belt_name(progress)} exam. "
              f"You're on challenge {idx} of {total}.")
        session.current_challenge = current.challenge_spec
        session.current_challenge_kind = "belt_exam"
        session.challenge_active = True
        session.phase = "challenge"
        session.current_skill = current.challenge_spec.skill
        clear_review_state(session)
        print_sensei(current.challenge_spec.narrative)
    else:
        # No challenges generated yet (shouldn't normally happen)
        print(f"\n  Resuming your {belt_name(progress)} exam...")
        try:
            if _generate_next_exam_challenge(engine, session, logger, progress, exam_state):
                print(f"\n  Belt exam challenge 1 of {total}:")
                print_sensei(exam_state.current_challenge.challenge_spec.narrative)
        except Exception as e:
            logger.log_error("belt_exam_error", str(e))
            print(f"\nError communicating with Sensei: {e}")


def handle_exam_final_grading(
    engine: AIEngine,
    session: Session,
    logger: DojoLogger,
    progress: Progress,
    tracer: KnowledgeTracer | None = None,
):
    """Send all 3 exam submissions to Sensei for holistic grading."""
    exam_state = session.belt_exam_state
    if not exam_state:
        return

    exam_state.phase = "grading"
    save_belt_exam(config.BELT_EXAM_FILE, exam_state)

    prompt = build_exam_final_grading_prompt(
        belt_name(progress),
        exam_state.challenges,
        all_skills_up_to_belt(progress.belt),
    )

    print("\n  All challenges submitted. Sensei is reviewing your exam...")
    try:
        response = engine.send_message(
            session.conversation_history,
            prompt,
            interaction_type="exam_grading",
        )
        print()  # newline after streamed response

        verdict = parse_exam_verdict(response)
        belt_before = progress.belt

        if verdict == "pass":
            new_belt = progress.promote_belt()
            progress.save(config.PROGRESS_FILE)
            tracer_block = tracer.format_block(progress) if tracer else ""
            engine.update_system_from_progress(progress, tracer_block)
            logger.log_exam_result(
                exam_state.exam_id, "pass", belt_before, new_belt
            )
            print(f"\n  You've been promoted to {new_belt.capitalize()} Belt!")
            print(f"  {progress.summary_line()}")
        elif verdict == "fail":
            progress.record_belt_exam_attempt()
            progress.save(config.PROGRESS_FILE)
            remaining = progress.belt_exam_attempts_remaining(config.BELT_EXAM_DAILY_LIMIT)
            logger.log_exam_result(
                exam_state.exam_id, "fail", belt_before, belt_before
            )
            print(
                f"\n  Exam attempts remaining today: {remaining}/"
                f"{config.BELT_EXAM_DAILY_LIMIT}"
            )
            if remaining > 0:
                print("  Type 'exam' to try again, or 'challenge' to keep practicing.")
            else:
                print("  Come back tomorrow, or keep practicing with 'challenge'.")
        else:
            # Unknown verdict — don't consume attempt
            logger.log_error(
                "belt_exam_verdict_error",
                f"exam_id={exam_state.exam_id}; could not parse verdict",
            )
            print("\n  Sensei's response was unclear. Try 'exam' to reattempt grading.")

        # Clean up exam state
        exam_state.phase = "completed"
        session.belt_exam_state = None
        session.current_challenge = None
        session.current_challenge_kind = None
        session.challenge_active = False
        session.attempt_count = 0
        session.worst_severity = None
        session.phase = "idle"
        session.current_skill = None
        clear_review_state(session)
        clear_belt_exam(config.BELT_EXAM_FILE)

    except Exception as e:
        logger.log_error("belt_exam_grading_error", str(e))
        print(f"\nError communicating with Sensei: {e}")
        print("  Your exam progress is saved. Type 'exam' to retry grading.")


def handle_run():
    path = config.SOLUTION_FILE
    if not path.exists():
        print(f"\nNo solution file found at: {path}")
        print("Write your code there first, then try again.")
        return
    result = run_code(path, timeout=config.TIMEOUT_SECONDS)
    print_output(result)


def _read_and_run_solution() -> tuple[str, str, str, dict | None] | None:
    """Read solution.py, run it, and return (code, output, validation_summary, validation_dict).

    Returns None if the file doesn't exist.
    """
    path = config.SOLUTION_FILE
    if not path.exists():
        print(f"\nNo solution file found at: {path}")
        print("Write your code there first, then try again.")
        return None

    code = path.read_text(encoding="utf-8")
    result = run_code(path, timeout=config.TIMEOUT_SECONDS)

    output_text = ""
    if result.stdout:
        output_text += result.stdout
    if result.stderr:
        output_text += ("\n" if output_text else "") + result.stderr
    if result.timed_out:
        output_text += ("\n" if output_text else "") + "(timed out)"
    if not output_text:
        output_text = "(no output)"

    return code, output_text


def handle_submit(
    engine: AIEngine, session: Session, logger: DojoLogger, progress: Progress,
    tracer: KnowledgeTracer | None = None,
):
    # Belt exam submit path — no Sensei review, just record and advance
    if session.current_challenge_kind == "belt_exam" and session.belt_exam_state:
        _handle_exam_submit(engine, session, logger, progress, tracer)
        return

    result = _read_and_run_solution()
    if result is None:
        return
    code, output_text = result

    clear_review_state(session)

    # Run concept validation if we have structured challenge data
    validation_summary = ""
    validation_dict = None
    if session.current_challenge and session.current_challenge.required_concepts:
        val_result = validate_concepts(code, session.current_challenge.required_concepts)
        validation_summary = val_result.summary()
        validation_dict = {
            "all_passed": val_result.all_passed,
            "found": val_result.found,
            "missing": val_result.missing,
            "unknown": val_result.unknown,
        }

    print("\nSending to Sensei for review...")
    try:
        prior_attempt_count = session.attempt_count
        prior_worst_severity = session.worst_severity
        challenge_kind = session.current_challenge_kind or "practice"
        response = engine.send_message_with_context(
            session.conversation_history,
            "Sensei, I'm submitting my solution. Please review it.",
            code,
            output_text,
            validation_summary=validation_summary,
        )

        # Parse verdict and update progress
        verdict = parse_verdict(response)
        challenge_id = session.current_challenge.challenge_id if session.current_challenge else "none"
        skill = session.current_challenge.skill if session.current_challenge else "unknown"
        session.attempt_count += 1

        passed = verdict.outcome == "pass"
        if verdict.outcome != "unknown":
            if challenge_kind == "practice":
                progress.record_attempt(skill, challenge_id, passed)

                if tracer:
                    tracer.train_step(skill, passed, progress)

                # Track worst severity across attempts for this challenge
                if verdict.severity:
                    prev_rank = SEVERITY_RANK.get(session.worst_severity, 0)
                    new_rank = SEVERITY_RANK.get(verdict.severity, 0)
                    if new_rank > prev_rank:
                        session.worst_severity = verdict.severity

                # Bonus XP for clean learning path (only minor mistakes or none)
                if passed and session.worst_severity in ("minor", None):
                    progress.add_xp(10)

                progress.save(config.PROGRESS_FILE)
                tracer_block = tracer.format_block(progress) if tracer else ""
                engine.update_system_from_progress(progress, tracer_block)

        logger.log_submission(
            challenge_id=challenge_id,
            code_snippet=code,
            output=output_text,
            validation=validation_dict,
            verdict=verdict.outcome,
        )
        if "review" not in STREAM_STDOUT_TYPES:
            print_sensei(response)

        if not passed and verdict.outcome == "needs_work":
            session.awaiting_dispute_reason = False
            session.last_review = ReviewState(
                challenge_id=challenge_id,
                skill=skill,
                code=code,
                output_text=output_text,
                validation_summary=validation_summary,
                validation_dict=validation_dict,
                response=response,
                verdict_outcome=verdict.outcome,
                verdict_severity=verdict.severity,
                prior_attempt_count=prior_attempt_count,
                prior_worst_severity=prior_worst_severity,
                challenge_kind=challenge_kind,
            )
            print("\n  If Sensei misread your solution, type: dispute [your reasoning]")
        elif passed:
            clear_review_state(session)

        if passed:
            finish_passed_activity(progress, session)
    except Exception as e:
        logger.log_error("submit_error", str(e))
        print(f"\nError communicating with Sensei: {e}")


def _handle_exam_submit(
    engine: AIEngine,
    session: Session,
    logger: DojoLogger,
    progress: Progress,
    tracer: KnowledgeTracer | None = None,
):
    """Handle a submit during a belt exam — store result, no Sensei review."""
    exam_state = session.belt_exam_state
    result = _read_and_run_solution()
    if result is None:
        return
    code, output_text = result

    current_rec = exam_state.current_challenge
    if not current_rec:
        print("  No active exam challenge.")
        return

    # Run concept validation
    validation_summary = ""
    validation_dict = None
    spec = current_rec.challenge_spec
    if spec.required_concepts:
        val_result = validate_concepts(code, spec.required_concepts)
        validation_summary = val_result.summary()
        validation_dict = {
            "all_passed": val_result.all_passed,
            "found": val_result.found,
            "missing": val_result.missing,
            "unknown": val_result.unknown,
        }

    # Store submission in exam state
    current_rec.code = code
    current_rec.output = output_text
    current_rec.validation_summary = validation_summary
    current_rec.validation_dict = validation_dict
    current_rec.submitted = True

    logger.log_exam_challenge_submit(
        exam_state.exam_id,
        exam_state.current_index,
        spec.challenge_id,
    )
    save_belt_exam(config.BELT_EXAM_FILE, exam_state)

    total = config.BELT_EXAM_CHALLENGES_PER_EXAM

    if exam_state.all_submitted:
        # All 3 submitted — trigger final grading
        handle_exam_final_grading(engine, session, logger, progress, tracer)
    else:
        # Generate next challenge
        next_num = len(exam_state.challenges) + 1
        print(f"\n  Submitted. Generating challenge {next_num} of {total}...")
        try:
            if _generate_next_exam_challenge(engine, session, logger, progress, exam_state):
                print(f"\n  Belt exam challenge {next_num} of {total}:")
                print_sensei(exam_state.current_challenge.challenge_spec.narrative)
            else:
                print("  Failed to generate the next exam challenge. Type 'exam' to retry.")
        except Exception as e:
            logger.log_error("belt_exam_error", str(e))
            print(f"\nError communicating with Sensei: {e}")
            print("  Your exam progress is saved. Type 'exam' to continue.")


def handle_dispute(
    engine: AIEngine,
    session: Session,
    logger: DojoLogger,
    progress: Progress,
    reasoning: str,
    tracer: KnowledgeTracer | None = None,
):
    review = session.last_review
    if not session.challenge_active or not review or not review.disputable:
        print("  There is no failed challenge review to dispute right now.")
        session.awaiting_dispute_reason = False
        return

    if not reasoning.strip():
        print("  Tell Sensei why you think the review should be reconsidered.")
        return

    print("\nSensei is reconsidering your rebuttal...")
    try:
        response = engine.send_message_with_context(
            session.conversation_history,
            build_dispute_prompt(review.response, reasoning),
            review.code,
            review.output_text,
            validation_summary=review.validation_summary,
            interaction_type="review",
        )
        verdict = parse_verdict(response)

        review.response = response
        review.verdict_outcome = verdict.outcome
        review.verdict_severity = verdict.severity
        session.awaiting_dispute_reason = False

        logger.log_dispute(
            challenge_id=review.challenge_id,
            reasoning=reasoning,
            verdict=verdict.outcome,
            overturned=verdict.outcome == "pass",
        )

        if "review" not in STREAM_STDOUT_TYPES:
            print_sensei(response)

        if verdict.outcome == "pass":
            session.attempt_count = review.prior_attempt_count
            session.worst_severity = review.prior_worst_severity

            if review.challenge_kind == "practice":
                progress.omit_failed_attempt(review.skill)
                progress.record_attempt(review.skill, review.challenge_id, True)

                if tracer:
                    tracer.train_step(review.skill, True, progress)

                if session.worst_severity in ("minor", None):
                    progress.add_xp(10)
                progress.save(config.PROGRESS_FILE)
                tracer_block = tracer.format_block(progress) if tracer else ""
                engine.update_system_from_progress(progress, tracer_block)

            finish_passed_activity(progress, session)
            return

        if verdict.outcome == "needs_work":
            print("\n  Sensei is holding the line. Update your code, or dispute again with clearer reasoning.")
        else:
            print("\n  Sensei's reply was unclear. You can try disputing again or resubmit after changes.")
    except Exception as e:
        logger.log_error("dispute_error", str(e))
        print(f"\nError communicating with Sensei: {e}")


def handle_chat(engine: AIEngine, session: Session, user_input: str):
    try:
        response = engine.send_message(session.conversation_history, user_input, interaction_type="chat")
        print_sensei(response)
    except Exception as e:
        print(f"\nError communicating with Sensei: {e}")



def main():
    config.validate_config()

    progress = Progress()
    progress.load(config.PROGRESS_FILE)
    known_history_before = sum(len(entries) for entries in progress.challenge_history.values())
    progress.import_challenge_history_from_log(config.LOG_FILE)
    known_history_after = sum(len(entries) for entries in progress.challenge_history.values())
    if known_history_after != known_history_before:
        progress.save(config.PROGRESS_FILE)

    tracer = KnowledgeTracer(config.LOG_FILE, config.KNOWLEDGE_MODEL_FILE)
    tracer.initialize(progress)
    tracer_block = tracer.format_block(progress)

    engine = AIEngine(
        api_key=config.ANTHROPIC_API_KEY,
        model=config.MODEL,
        max_tokens=config.MAX_TOKENS,
        system_blocks=build_system_blocks(progress, tracer_block),
    )
    session = Session()
    logger = DojoLogger(config.LOG_FILE)
    logger.log_session_start()

    print(get_banner(progress))

    try:
        while True:
            try:
                user_input = input("\nyou> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nSayonara, grasshopper.")
                break

            if not user_input:
                continue

            command = user_input.lower()

            if session.awaiting_dispute_reason:
                if command == "back":
                    session.awaiting_dispute_reason = False
                    print("  Dispute cancelled.")
                    continue
                if command not in ("help", "quit", "exit", "q"):
                    handle_dispute(engine, session, logger, progress, user_input, tracer)
                    continue

            # Handle skill selection phase first
            if session.phase == "choosing_skill":
                if command == "back":
                    session.phase = "idle"
                    print("  Cancelled.")
                    continue
                try:
                    idx = int(command) - 1
                    if 0 <= idx < len(progress.skills_taught):
                        chosen_skill = progress.skills_taught[idx]
                        session.phase = "idle"
                        handle_challenge_generate(
                            engine,
                            session,
                            logger,
                            progress,
                            skill=chosen_skill,
                        )
                    else:
                        print(f"  Pick a number between 1 and {len(progress.skills_taught)}, or 'back'.")
                except ValueError:
                    print("  Pick a number from the list, or type 'back' to cancel.")
                continue

            if command in ("quit", "exit", "q"):
                print("Sayonara, grasshopper. Train well.")
                break
            elif command == "help":
                print(HELP_TEXT)
            elif command == "lesson":
                if session.phase == "quiz":
                    print("  Complete the quiz first. Answer with: quiz a b c")
                elif session.phase == "challenge" and session.challenge_active:
                    print(
                        f"  You have an active {current_activity_name(session)}. "
                        "Use 'submit' or 'leave' first."
                    )
                else:
                    handle_lesson(engine, session, logger, progress)
            elif command in ("challenge", "challenges"):
                if session.phase == "quiz":
                    print("  Complete the quiz first. Answer with: quiz a b c")
                elif session.phase == "challenge" and session.challenge_active:
                    print(
                        f"  You already have an active {current_activity_name(session)}. "
                        "Use 'submit' or 'leave'."
                    )
                else:
                    interrupted = session.get_interrupted_snapshot(
                        config.INTERRUPTED_CHALLENGE_FILE
                    )
                    if interrupted:
                        offer_interrupted_activity(session, interrupted, requested_action="challenge")
                    else:
                        start_challenge_selection(progress, session)
            elif command == "exam":
                if session.phase == "quiz":
                    print("  Complete the quiz first. Answer with: quiz a b c")
                elif session.phase == "challenge" and session.challenge_active:
                    print(
                        f"  You already have an active {current_activity_name(session)}. "
                        "Use 'submit' or 'leave'."
                    )
                else:
                    handle_belt_exam_generate(engine, session, logger, progress, tracer)
            elif command == "resume":
                if session.pending_resume:
                    data = session.pending_resume
                    session.current_challenge = data["challenge"]
                    session.current_challenge_kind = data.get("challenge_kind", "practice")
                    session.attempt_count = data["attempt_count"]
                    session.phase = data.get("phase", "challenge")
                    session.current_skill = data.get("skill")
                    session.challenge_active = True
                    clear_interrupted_challenge(config.INTERRUPTED_CHALLENGE_FILE)
                    session.invalidate_interrupted_snapshot()
                    session.pending_resume = None
                    clear_review_state(session)
                    print_sensei(f"Welcome back! Here's where we left off:\n\n{session.current_challenge.narrative}")
                else:
                    print("  Nothing to resume.")
            elif command == "new":
                if not session.pending_resume:
                    print(
                        "  No unfinished challenge is waiting. "
                        "Type 'challenge' or 'exam' to start something new."
                    )
                    continue

                requested_action = session.pending_resume.get("requested_action", "challenge")
                clear_interrupted_challenge(config.INTERRUPTED_CHALLENGE_FILE)
                session.invalidate_interrupted_snapshot()
                session.pending_resume = None
                session.current_challenge = None
                session.current_challenge_kind = None
                session.challenge_active = False
                session.attempt_count = 0
                session.worst_severity = None
                session.phase = "idle"
                session.current_skill = None
                clear_review_state(session)
                if requested_action == "exam":
                    handle_belt_exam_generate(engine, session, logger, progress, tracer)
                else:
                    start_challenge_selection(progress, session)
            elif command == "leave":
                if session.belt_exam_state:
                    # Save belt exam state to disk and clear session
                    save_belt_exam(config.BELT_EXAM_FILE, session.belt_exam_state)
                    session.belt_exam_state = None
                    session.current_challenge = None
                    session.current_challenge_kind = None
                    session.challenge_active = False
                    session.attempt_count = 0
                    session.worst_severity = None
                    session.phase = "idle"
                    session.current_skill = None
                    clear_review_state(session)
                    print("\n  Exam progress saved. Type 'exam' to resume.")
                elif session.challenge_active or session.phase not in ("idle",):
                    if session.current_challenge:
                        save_interrupted_challenge(
                            config.INTERRUPTED_CHALLENGE_FILE,
                            session.current_challenge,
                            session.attempt_count,
                            session.phase,
                            session.current_skill,
                            challenge_kind=session.current_challenge_kind,
                        )
                        session.invalidate_interrupted_snapshot()
                    session.current_challenge = None
                    session.current_challenge_kind = None
                    session.challenge_active = False
                    session.attempt_count = 0
                    session.worst_severity = None
                    session.phase = "idle"
                    session.current_skill = None
                    clear_review_state(session)
                    print("\n  Progress saved. You can resume it later with 'resume'.")
                else:
                    print("  No active challenge or exam to leave.")
            elif command.startswith("quiz "):
                if session.phase != "quiz":
                    print("  No quiz active right now.")
                else:
                    answers = command.split()[1:]
                    handle_quiz(engine, session, logger, progress, answers, tracer)
            elif command == "run":
                handle_run()
            elif command == "submit":
                handle_submit(engine, session, logger, progress, tracer)
            elif command in ("dispute", "rebuke"):
                if session.current_challenge_kind == "belt_exam":
                    print("  Disputes are not available during belt exams.")
                elif not session.challenge_active or not session.last_review or not session.last_review.disputable:
                    print("  There is no failed challenge review to dispute right now.")
                else:
                    session.awaiting_dispute_reason = True
                    print("  Tell Sensei why you think the review was wrong, or type 'back' to cancel.")
            elif command.startswith("dispute ") or command.startswith("rebuke "):
                if session.current_challenge_kind == "belt_exam":
                    print("  Disputes are not available during belt exams.")
                else:
                    _, _, reasoning = user_input.partition(" ")
                    handle_dispute(engine, session, logger, progress, reasoning, tracer)
            elif command == "skills":
                print(f"\n{progress.skills_display()}")
            elif command in ("yes", "y") and not session.challenge_active:
                start_challenge_selection(progress, session)
            elif command in ("no", "n") and not session.challenge_active:
                print("\n  Take a breather, grasshopper. Type 'lesson', 'challenge', or 'exam' when you're ready.")
            elif command == "clear":
                session.clear()
                print("Conversation cleared. Fresh start, grasshopper.")
            else:
                handle_chat(engine, session, user_input)
    finally:
        # Save belt exam state if the user quit mid-exam
        if session.belt_exam_state:
            save_belt_exam(config.BELT_EXAM_FILE, session.belt_exam_state)
        tracer.save()
        logger.log_session_end()
        logger.close()


if __name__ == "__main__":
    main()
