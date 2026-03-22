"""Main CLI loop for CodeDojo."""

import uuid
from datetime import datetime

from rich.console import Console

from .config import BELTS, SESSION_LENGTHS, SKILL_TREE, XP_QUIZ_CORRECT, XP_QUIZ_WRONG, XP_CHALLENGE_PASS, XP_CHALLENGE_PARTIAL, XP_CHALLENGE_FAIL, XP_CODE_REVIEW
from .display import (
    console, clear_screen, show_banner, show_status_bar, show_xp_bar,
    sensei_says, show_menu, ask_text, ask_confirm, show_skill_tree,
    show_progress_report, show_code_block, show_quiz_question,
    show_challenge_intro, show_result, show_xp_gain,
    get_multiline_input, get_belt, get_next_belt,
)
from .models import UserProfile, SkillProgress, SessionRecord
from .storage import DojoStorage
from .sensei import Sensei
from .ranking import award_xp, award_skill_xp, calculate_streak_bonus
from .skill_tree import (
    get_skill_info, get_recommended_skills, get_unlocked_skills,
    get_branch_options, get_skill_options_in_branch, check_and_unlock_new_skills,
)
from .challenges import run_challenge, format_test_results
from .assessment import run_assessment


class DojoSession:
    """Manages a single dojo training session."""

    def __init__(self):
        self.storage = DojoStorage()
        self.sensei = Sensei()
        self.session_id = str(uuid.uuid4())[:8]
        self.xp_earned = 0
        self.challenges_done = 0
        self.quizzes_done = 0
        self.reviews_done = 0
        self.skills_practiced = set()
        self.was_promoted = False
        self.start_time = datetime.now()

    def run(self):
        """Main entry point."""
        try:
            clear_screen()
            show_banner()

            user = self.storage.get_user()

            if not user:
                user = self._onboarding()
            else:
                user = self._returning_user(user)

            self.user = user
            self._main_loop()

        except KeyboardInterrupt:
            console.print("\n")
            self._exit_dojo()
        except Exception as e:
            console.print(f"\n  [bold red]An error occurred: {e}[/]")
            console.print("  [dim]Your progress has been saved.[/]")
        finally:
            self.storage.close()

    # ── Onboarding ─────────────────────────────────────────────────

    def _onboarding(self) -> UserProfile:
        sensei_says(
            "A new face enters the dojo. Tell me your name, student."
        )
        name = ask_text("Your name")
        if not name.strip():
            name = "Student"

        user = self.storage.create_user(name)

        sensei_says(
            f"Welcome, {name}. I am Sensei. "
            "This dojo will test you, challenge you, and forge you into a sharper coder. "
            "But first, I must see what you already know."
        )

        if ask_confirm("Ready for the skill assessment?"):
            starting_xp = run_assessment(user, self.sensei, self.storage)
            user.total_xp = starting_xp
        else:
            sensei_says("Very well. We will start from the beginning. There is no shortcut.")
            from .skill_tree import unlock_initial_skills
            unlock_initial_skills(self.storage)
            starting_xp = 0

        user = self.storage.update_streak(user)
        self.storage.update_user(user)

        return user

    def _returning_user(self, user: UserProfile) -> UserProfile:
        user = self.storage.update_streak(user)
        self.storage.update_user(user)

        # Calculate days away
        days_away = 0
        if user.last_session_date:
            last = datetime.fromisoformat(user.last_session_date).date()
            days_away = (datetime.now().date() - last).days

        # Get weak/strong areas
        weak = self.storage.get_weakest_skills(1)
        strong = self.storage.get_strongest_skills(1)
        weak_area = get_skill_info(weak[0].skill_id)["name"] if weak else "unknown"
        strong_area = get_skill_info(strong[0].skill_id)["name"] if strong else "unknown"

        belt = get_belt(user.total_xp)

        try:
            greeting = self.sensei.greet(
                name=user.name, belt_name=belt["name"], belt_icon=belt["icon"],
                xp=user.total_xp, days_away=days_away, streak=user.current_streak,
                weak_area=weak_area, strong_area=strong_area,
            )
            sensei_says(greeting)
        except Exception:
            sensei_says(f"Welcome back, {user.name}. Let us continue your training.")

        show_status_bar(user)
        show_xp_bar(user)

        # Check for new unlockable skills
        newly_unlocked = check_and_unlock_new_skills(self.storage)
        if newly_unlocked:
            for sid in newly_unlocked:
                info = get_skill_info(sid)
                if info:
                    console.print(f"  [bold green]🔓 New skill unlocked: {info['name']}[/]")

        return user

    # ── Main Loop ──────────────────────────────────────────────────

    def _main_loop(self):
        while True:
            console.print()
            choice = show_menu([
                ("train",    "🥋 Train (Sensei recommends)"),
                ("choose",   "🌳 Choose from Skill Tree"),
                ("review",   "📝 Submit Code for Review"),
                ("progress", "📊 View Progress"),
                ("chat",     "💬 Talk to Sensei"),
                ("exit",     "🚪 Leave the Dojo"),
            ], prompt="What will you do")

            if choice == "train":
                self._sensei_training()
            elif choice == "choose":
                self._choose_training()
            elif choice == "review":
                self._code_review()
            elif choice == "progress":
                self._show_progress()
            elif choice == "chat":
                self._chat_with_sensei()
            elif choice == "exit":
                self._exit_dojo()
                break

    # ── Sensei-Guided Training ─────────────────────────────────────

    def _sensei_training(self):
        # Pick session length
        length = show_menu([
            ("quick",     "⚡ Quick Drill (5 min)"),
            ("medium",    "🥋 Training Session (15 min)"),
            ("deep",      "🏔️  Deep Practice (30 min)"),
            ("endurance", "🔥 Endurance Round (60 min)"),
        ], prompt="Session length")

        session_cfg = SESSION_LENGTHS[length]
        recommended = get_recommended_skills(self.storage, limit=3)

        if not recommended:
            sensei_says("You have no unlocked skills yet. Let us start with the basics.")
            recommended = ["fundamentals.variables_types"]

        # Show recommendations
        console.print()
        sensei_says("I recommend we focus on these areas today:")
        for i, sid in enumerate(recommended, 1):
            info = get_skill_info(sid)
            if info:
                console.print(f"    {i}. {info['branch_icon']} {info['name']} — {', '.join(info['topics'][:3])}")

        console.print()
        if not ask_confirm("Accept sensei's recommendation?"):
            self._choose_training()
            return

        # Run the training session
        skill_id = recommended[0]
        self._run_training_on_skill(skill_id, session_cfg)

        # Additional skills if time allows
        for sid in recommended[1:]:
            if self.quizzes_done >= session_cfg["quizzes"] and self.challenges_done >= session_cfg["challenges"]:
                break
            console.print()
            if ask_confirm(f"Continue training? Next: {get_skill_info(sid)['name']}"):
                self._run_training_on_skill(sid, session_cfg)
            else:
                break

    def _run_training_on_skill(self, skill_id: str, session_cfg: dict):
        """Run a mix of quizzes and challenges for a skill."""
        info = get_skill_info(skill_id)
        if not info:
            console.print("  [red]Skill not found.[/]")
            return

        skill = self.storage.get_skill(skill_id) or SkillProgress(skill_id=skill_id, level=1)
        difficulty = self._get_difficulty(skill)

        console.print(f"\n  [bold]{info['branch_icon']} Training: {info['name']}[/] [{difficulty}]")
        console.print(f"  [dim]Topics: {', '.join(info['topics'])}[/]\n")

        # Quiz round
        quizzes_to_do = min(session_cfg.get("quizzes", 2), max(1, session_cfg["quizzes"] - self.quizzes_done))
        if quizzes_to_do > 0:
            self._run_quiz(skill_id, info, difficulty, count=quizzes_to_do)

        # Challenge round
        challenges_to_do = min(session_cfg.get("challenges", 1), max(1, session_cfg["challenges"] - self.challenges_done))
        if challenges_to_do > 0:
            for _ in range(challenges_to_do):
                if not self._run_coding_challenge(skill_id, info, difficulty):
                    break  # Student chose to skip

        self.skills_practiced.add(skill_id)

    def _get_difficulty(self, skill: SkillProgress) -> str:
        if skill.level <= 1:
            return "beginner"
        elif skill.level <= 2:
            return "intermediate"
        else:
            return "advanced"

    # ── Quiz Mode ──────────────────────────────────────────────────

    def _run_quiz(self, skill_id: str, info: dict, difficulty: str, count: int = 1):
        sensei_says("Let us test your knowledge first.", typing_effect=False)
        console.print("  [dim]Generating quiz...[/]")

        try:
            questions = self.sensei.generate_quiz(
                skill_id=skill_id,
                skill_name=info["name"],
                topics=info["topics"],
                difficulty=difficulty,
                count=count,
            )
        except Exception as e:
            console.print(f"  [red]Could not generate quiz: {e}[/]")
            return

        skill = self.storage.get_skill(skill_id) or SkillProgress(skill_id=skill_id, level=1)

        for q in questions:
            answer = show_quiz_question(q.question, q.options)
            correct = answer == q.correct_index

            if correct:
                show_result(True, "Correct!")
                xp = XP_QUIZ_CORRECT
                award_xp(self.user, xp, "Quiz — correct answer", self.storage)
                award_skill_xp(skill, xp, True, self.storage)
                self.xp_earned += xp
                self.user.quizzes_correct += 1
            else:
                show_result(False, f"The answer was: {q.options[q.correct_index]}")
                xp = XP_QUIZ_WRONG
                award_xp(self.user, xp, "Quiz — participation", self.storage)
                award_skill_xp(skill, xp, False, self.storage)
                self.xp_earned += xp

            # Show explanation
            console.print(f"\n  [dim italic]Sensei: {q.explanation}[/]")

            self.user.quizzes_attempted += 1
            self.quizzes_done += 1
            self.storage.update_user(self.user)

    # ── Coding Challenge Mode ──────────────────────────────────────

    def _run_coding_challenge(self, skill_id: str, info: dict, difficulty: str) -> bool:
        """Run a single coding challenge. Returns False if student skips."""
        sensei_says("Now, show me what you can do with code.", typing_effect=False)
        console.print("  [dim]Generating challenge...[/]")

        try:
            challenge = self.sensei.generate_challenge(
                skill_id=skill_id,
                skill_name=info["name"],
                topics=info["topics"],
                difficulty=difficulty,
            )
        except Exception as e:
            console.print(f"  [red]Could not generate challenge: {e}[/]")
            return True

        show_challenge_intro(challenge.title, challenge.description, difficulty, challenge.starter_code)

        hints_used = 0
        attempts = 0
        max_attempts = 3

        while attempts < max_attempts:
            console.print()
            action = show_menu([
                ("code",  "✍️  Write my solution"),
                ("hint",  f"💡 Get a hint ({hints_used}/{len(challenge.hints)} used)"),
                ("skip",  "⏭️  Skip this challenge"),
            ], prompt="Action")

            if action == "skip":
                sensei_says("Retreat is not defeat — if you return stronger.")
                return True

            if action == "hint":
                if hints_used < len(challenge.hints):
                    console.print(f"\n  [yellow]💡 Hint: {challenge.hints[hints_used]}[/]")
                    hints_used += 1
                else:
                    console.print("  [dim]No more hints available.[/]")
                continue

            # Get code from student
            student_code = get_multiline_input()
            if not student_code.strip():
                console.print("  [dim]Empty submission. Try again.[/]")
                continue

            attempts += 1

            # Run tests
            console.print("\n  [dim]Running tests...[/]")
            results = run_challenge(challenge, student_code)
            passed = sum(1 for r in results if r["passed"])
            total = len(results)
            all_passed = passed == total

            # Show results
            console.print(format_test_results(results))
            console.print(f"\n  [bold]Result: {passed}/{total} tests passed[/]")

            # Get sensei evaluation
            try:
                feedback = self.sensei.evaluate_solution(
                    challenge.title, student_code, results, all_passed
                )
                sensei_says(feedback, typing_effect=False)
            except Exception:
                pass

            # Award XP
            skill = self.storage.get_skill(skill_id) or SkillProgress(skill_id=skill_id, level=1)
            self.user.challenges_attempted += 1

            if all_passed:
                xp = XP_CHALLENGE_PASS - (hints_used * 5)  # Penalty for hints
                xp = max(xp, XP_CHALLENGE_PARTIAL)
                award_xp(self.user, xp, f"Challenge passed — {challenge.title}", self.storage)
                award_skill_xp(skill, xp, True, self.storage)
                self.xp_earned += xp
                self.user.challenges_passed += 1
                self.challenges_done += 1
                self.storage.update_user(self.user)
                return True
            elif passed > 0:
                xp = XP_CHALLENGE_PARTIAL
                award_xp(self.user, xp, f"Partial solve — {passed}/{total} tests", self.storage)
                award_skill_xp(skill, xp, False, self.storage)
                self.xp_earned += xp
            else:
                xp = XP_CHALLENGE_FAIL
                award_xp(self.user, xp, "Challenge attempted", self.storage)
                award_skill_xp(skill, xp, False, self.storage)
                self.xp_earned += xp

            self.storage.update_user(self.user)

            if attempts < max_attempts:
                if not ask_confirm("Try again?"):
                    break
            else:
                sensei_says("Three attempts. Reflect on what went wrong. We will revisit this.")

        self.challenges_done += 1
        return True

    # ── Code Review Mode ───────────────────────────────────────────

    def _code_review(self):
        sensei_says("Show me your code. I will tell you the truth — even if it stings.")

        context = ask_text("What does this code do? (brief description)", default="general Python code")
        console.print()
        student_code = get_multiline_input("Paste your code (type 'END' on a new line to finish):")

        if not student_code.strip():
            sensei_says("You show me nothing? There is nothing to review.")
            return

        console.print("\n  [dim]Sensei is reviewing your code...[/]")

        try:
            review = self.sensei.review_code(student_code, context)
        except Exception as e:
            console.print(f"  [red]Review failed: {e}[/]")
            return

        # Display review
        console.print()
        console.print(f"  [bold]Score: {review.score}/10[/]")
        console.print()

        if review.strengths:
            console.print("  [bold green]Strengths:[/]")
            for s in review.strengths:
                console.print(f"    ✅ {s}")

        if review.improvements:
            console.print()
            console.print("  [bold yellow]Improvements:[/]")
            for imp in review.improvements:
                console.print(f"    🔸 {imp}")

        console.print()
        sensei_says(review.sensei_feedback, typing_effect=False)

        # Award XP
        xp = review.xp_earned
        award_xp(self.user, xp, "Code review completed", self.storage)
        self.xp_earned += xp
        self.reviews_done += 1
        self.user.reviews_completed += 1
        self.storage.update_user(self.user)

    # ── Choose from Skill Tree ─────────────────────────────────────

    def _choose_training(self):
        show_skill_tree(self.storage.get_all_skills())

        branches = get_branch_options()
        console.print()
        branch_id = show_menu(branches, prompt="Choose a branch")

        skills = get_skill_options_in_branch(branch_id, self.storage)
        if not skills:
            sensei_says("No skills are unlocked in that branch yet. Patience.")
            return

        skill_id = show_menu(skills, prompt="Choose a skill to train")

        session_cfg = SESSION_LENGTHS["medium"]  # Default medium for manual choice
        self._run_training_on_skill(skill_id, session_cfg)

    # ── Progress ───────────────────────────────────────────────────

    def _show_progress(self):
        all_skills = self.storage.get_all_skills()
        show_progress_report(self.user, all_skills)
        show_skill_tree(all_skills)

    # ── Chat ───────────────────────────────────────────────────────

    def _chat_with_sensei(self):
        sensei_says("Speak, student. What is on your mind?")

        while True:
            msg = ask_text("You (or 'back' to return)")
            if msg.lower() in ("back", "exit", "quit", "q"):
                break

            belt = get_belt(self.user.total_xp)
            context = (
                f"Student: {self.user.name}, Rank: {belt['name']}, "
                f"XP: {self.user.total_xp}, Sessions: {self.user.sessions_completed}"
            )

            try:
                response = self.sensei.chat(msg, context)
                sensei_says(response)
            except Exception as e:
                console.print(f"  [red]Sensei is meditating... (error: {e})[/]")

    # ── Exit ───────────────────────────────────────────────────────

    def _exit_dojo(self):
        # Streak bonus
        streak_bonus = calculate_streak_bonus(self.user)
        if streak_bonus > 0:
            award_xp(self.user, streak_bonus, f"Streak bonus ({self.user.current_streak} days)", self.storage)
            self.xp_earned += streak_bonus

        # Save session record
        duration = int((datetime.now() - self.start_time).total_seconds() / 60)
        self.user.sessions_completed += 1
        self.storage.update_user(self.user)

        session_record = SessionRecord(
            session_id=self.session_id,
            date=datetime.now().isoformat(),
            duration_minutes=duration,
            xp_earned=self.xp_earned,
            challenges_completed=self.challenges_done,
            quizzes_completed=self.quizzes_done,
            reviews_completed=self.reviews_done,
            skills_practiced=",".join(self.skills_practiced),
        )
        self.storage.save_session(session_record)

        # Farewell
        activities = []
        if self.quizzes_done:
            activities.append(f"{self.quizzes_done} quiz(zes)")
        if self.challenges_done:
            activities.append(f"{self.challenges_done} challenge(s)")
        if self.reviews_done:
            activities.append(f"{self.reviews_done} review(s)")

        belt = get_belt(self.user.total_xp)

        if self.xp_earned > 0:
            try:
                farewell = self.sensei.farewell(
                    name=self.user.name,
                    xp_earned=self.xp_earned,
                    activities=", ".join(activities) or "reflection",
                    belt_name=belt["name"],
                    belt_icon=belt["icon"],
                    was_promoted=self.was_promoted,
                )
                sensei_says(farewell)
            except Exception:
                sensei_says("Until next time, student. The dojo will be here.")
        else:
            sensei_says("You leave without training? The blade grows dull. Return soon.")

        console.print(f"  [dim]Session: {duration} min | +{self.xp_earned} XP | {belt['icon']} {belt['name']}[/]")
        console.print()


def main():
    """Entry point for CodeDojo."""
    session = DojoSession()
    session.run()
