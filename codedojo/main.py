from codedojo import config
from codedojo.ai_engine import (
    AIEngine,
    STREAM_STDOUT_TYPES,
    build_system_blocks,
    parse_verdict,
    SEVERITY_RANK,
)
from codedojo.challenge_gen import (
    get_challenge_prompt,
    get_lesson_prompt,
    NoNewSkillsError,
    parse_challenge_response,
    parse_quiz_answers,
    strip_quiz_meta,
    WHITE_BELT_SKILLS,
)
from codedojo.code_runner import run_code
from codedojo.code_validator import validate_concepts
from codedojo.dojo_logger import DojoLogger
from codedojo.progress import Progress
from codedojo.session import Session
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
    submit     - Submit solution.py for Sensei review
    run        - Run solution.py (see output)
    leave      - Save challenge and step away
    skills     - View your skill progress
    help       - Show commands
    quit       - Exit the dojo
=======================================
  Type anything else to talk to Sensei.
======================================="""


HELP_TEXT = """\
  lesson     - Learn a new Python topic (teach + quiz)
  challenge  - Practice a skill you've learned (coding challenge)
  quiz a b c - Answer the quiz (e.g. 'quiz a b c')
  submit     - Submit solution.py for Sensei review
  run        - Run solution.py and see output (no review)
  leave      - Save current challenge and step away
  resume     - Resume a saved challenge
  skills     - View your skill progress
  clear      - Reset conversation history
  help       - Show this message
  quit       - Exit the dojo"""


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


def handle_lesson(engine: AIEngine, session: Session, logger: DojoLogger, progress: Progress):
    """Start a lesson on a new (untaught) skill."""
    untaught = progress.get_untaught_skills(WHITE_BELT_SKILLS)
    if not untaught:
        print("\n  You've covered all White Belt topics! Practice with 'challenge'.")
        return

    try:
        prompt, skill = get_lesson_prompt(available_skills=untaught)
    except NoNewSkillsError:
        print("\n  You've covered all White Belt topics! Practice with 'challenge'.")
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
    user_answers: list[str],
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
    engine.update_system_from_progress(progress)

    print(f"\n  Lesson complete! You've learned '{skill}'.")
    print("  Type 'challenge' to practice, or 'lesson' for another topic.")
    session.phase = "idle"
    session.current_skill = None
    session.quiz_answers = []


def show_skill_menu(progress: Progress):
    """Display numbered list of learned skills for challenge selection."""
    print("\n  Choose a skill to practice:")
    for i, skill in enumerate(progress.skills_taught, 1):
        print(f"    {i}. {skill}")
    print("\n  Type a number to select, or 'back' to cancel.")


def handle_challenge_generate(
    engine: AIEngine, session: Session, logger: DojoLogger, skill: str,
):
    """Generate and start a coding challenge for the given skill."""
    prompt, chosen_skill = get_challenge_prompt(skill=skill)
    print("\nRequesting challenge from Sensei...")
    try:
        response = engine.send_message(session.conversation_history, prompt, interaction_type="challenge")
        spec = parse_challenge_response(response, chosen_skill)
        session.current_challenge = spec
        session.challenge_active = True
        session.attempt_count = 0
        session.worst_severity = None
        session.phase = "challenge"
        logger.log_challenge(
            challenge_id=spec.challenge_id,
            skill=spec.skill,
            requirements=spec.required_concepts,
        )
        print_sensei(spec.narrative)
    except Exception as e:
        logger.log_error("challenge_error", str(e))
        print(f"\nError communicating with Sensei: {e}")


def handle_run():
    path = config.SOLUTION_FILE
    if not path.exists():
        print(f"\nNo solution file found at: {path}")
        print("Write your code there first, then try again.")
        return
    result = run_code(path, timeout=config.TIMEOUT_SECONDS)
    print_output(result)


def handle_submit(engine: AIEngine, session: Session, logger: DojoLogger, progress: Progress):
    path = config.SOLUTION_FILE
    if not path.exists():
        print(f"\nNo solution file found at: {path}")
        print("Write your code there first, then try again.")
        return

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
            progress.record_attempt(skill, challenge_id, passed)

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

        logger.log_submission(
            challenge_id=challenge_id,
            code_snippet=code,
            output=output_text,
            validation=validation_dict,
            verdict=verdict.outcome,
        )
        if "review" not in STREAM_STDOUT_TYPES:
            print_sensei(response)

        if passed:
            print(f"\n  +XP! {progress.summary_line()}")
            session.challenge_active = False
            session.phase = "idle"
            clear_interrupted_challenge(config.INTERRUPTED_CHALLENGE_FILE)
            session.invalidate_interrupted_snapshot()
            print("\n  Ready for another challenge? (yes/no)")
    except Exception as e:
        logger.log_error("submit_error", str(e))
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

    engine = AIEngine(
        api_key=config.ANTHROPIC_API_KEY,
        model=config.MODEL,
        max_tokens=config.MAX_TOKENS,
        system_blocks=build_system_blocks(progress),
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
                        handle_challenge_generate(engine, session, logger, skill=chosen_skill)
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
                    print("  You have an active challenge. Use 'submit' or 'leave' first.")
                else:
                    handle_lesson(engine, session, logger, progress)
            elif command == "challenge":
                if session.phase == "quiz":
                    print("  Complete the quiz first. Answer with: quiz a b c")
                elif session.phase == "challenge" and session.challenge_active:
                    print("  You already have an active challenge. Use 'submit' or 'leave'.")
                else:
                    # Check for an interrupted challenge
                    interrupted = session.get_interrupted_snapshot(
                        config.INTERRUPTED_CHALLENGE_FILE
                    )
                    if interrupted:
                        spec = interrupted["challenge"]
                        print(f'\n  You have an unfinished challenge: "{spec.title}" ({spec.skill})')
                        print("  Type 'resume' to continue or 'new' for a fresh start.")
                        session.pending_resume = interrupted
                    elif not progress.skills_taught:
                        print("\n  You haven't learned any skills yet. Type 'lesson' to start!")
                    else:
                        show_skill_menu(progress)
                        session.phase = "choosing_skill"
            elif command == "resume":
                if session.pending_resume:
                    data = session.pending_resume
                    session.current_challenge = data["challenge"]
                    session.attempt_count = data["attempt_count"]
                    session.phase = data.get("phase", "challenge")
                    session.current_skill = data.get("skill")
                    session.challenge_active = True
                    clear_interrupted_challenge(config.INTERRUPTED_CHALLENGE_FILE)
                    session.invalidate_interrupted_snapshot()
                    session.pending_resume = None
                    print_sensei(f"Welcome back! Here's where we left off:\n\n{session.current_challenge.narrative}")
                else:
                    print("  Nothing to resume.")
            elif command == "new":
                if session.pending_resume:
                    clear_interrupted_challenge(config.INTERRUPTED_CHALLENGE_FILE)
                    session.invalidate_interrupted_snapshot()
                    session.pending_resume = None
                handle_lesson(engine, session, logger, progress)
            elif command == "leave":
                if session.challenge_active or session.phase not in ("idle",):
                    if session.current_challenge:
                        save_interrupted_challenge(
                            config.INTERRUPTED_CHALLENGE_FILE,
                            session.current_challenge,
                            session.attempt_count,
                            session.phase,
                            session.current_skill,
                        )
                        session.invalidate_interrupted_snapshot()
                    session.current_challenge = None
                    session.challenge_active = False
                    session.phase = "idle"
                    session.current_skill = None
                    print("\n  Challenge saved. You can resume it later with 'challenge'.")
                else:
                    print("  No active challenge to leave.")
            elif command.startswith("quiz "):
                if session.phase != "quiz":
                    print("  No quiz active right now.")
                else:
                    answers = command.split()[1:]
                    handle_quiz(engine, session, logger, progress, answers)
            elif command == "run":
                handle_run()
            elif command == "submit":
                handle_submit(engine, session, logger, progress)
            elif command == "skills":
                print(f"\n{progress.skills_display()}")
            elif command in ("yes", "y") and not session.challenge_active:
                show_skill_menu(progress) if progress.skills_taught else print("\n  Type 'lesson' to start learning!")
                if progress.skills_taught:
                    session.phase = "choosing_skill"
            elif command in ("no", "n") and not session.challenge_active:
                print("\n  Take a breather, grasshopper. Type 'lesson' or 'challenge' when you're ready.")
            elif command == "clear":
                session.clear()
                print("Conversation cleared. Fresh start, grasshopper.")
            else:
                handle_chat(engine, session, user_input)
    finally:
        logger.log_session_end()
        logger.close()


if __name__ == "__main__":
    main()
