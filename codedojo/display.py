"""Rich terminal display for CodeDojo."""

import time
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.progress import Progress, BarColumn, TextColumn
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.prompt import Prompt, IntPrompt, Confirm
from rich import box

from .config import BELTS, SKILL_TREE
from .models import UserProfile, SkillProgress, SKILL_LEVEL_NAMES

console = Console()


def clear_screen():
    console.clear()


def show_banner():
    banner = Text()
    banner.append("╔══════════════════════════════════════════════════════╗\n", style="bold red")
    banner.append("║", style="bold red")
    banner.append("              🥋  C O D E   D O J O  🥋              ", style="bold bright_white")
    banner.append("║\n", style="bold red")
    banner.append("║", style="bold red")
    banner.append("           Sharpen Your Python Blade                  ", style="italic dim")
    banner.append("║\n", style="bold red")
    banner.append("╚══════════════════════════════════════════════════════╝", style="bold red")
    console.print(banner)
    console.print()


def show_status_bar(user: UserProfile):
    """Display current rank, XP, and streak."""
    belt = get_belt(user.total_xp)
    next_belt = get_next_belt(user.total_xp)

    status = Table(show_header=False, box=box.SIMPLE_HEAVY, expand=True, padding=(0, 1))
    status.add_column(ratio=1)
    status.add_column(ratio=1)
    status.add_column(ratio=1)

    # Belt info
    belt_text = f"{belt['icon']} {belt['name']}"

    # XP progress
    if next_belt:
        xp_into_belt = user.total_xp - belt["xp_required"]
        xp_for_belt = next_belt["xp_required"] - belt["xp_required"]
        xp_text = f"XP: {user.total_xp} ({xp_into_belt}/{xp_for_belt} to {next_belt['name']})"
    else:
        xp_text = f"XP: {user.total_xp} (MAX RANK)"

    # Streak
    streak_text = f"🔥 Streak: {user.current_streak} day{'s' if user.current_streak != 1 else ''}"

    status.add_row(belt_text, xp_text, streak_text)
    console.print(Panel(status, border_style="dim"))


def show_xp_bar(user: UserProfile):
    """Show a visual XP progress bar toward next belt."""
    belt = get_belt(user.total_xp)
    next_belt = get_next_belt(user.total_xp)

    if not next_belt:
        console.print(f"  [bold bright_white]⬛ BLACK BELT — You have reached the summit.[/]")
        return

    xp_into = user.total_xp - belt["xp_required"]
    xp_needed = next_belt["xp_required"] - belt["xp_required"]
    pct = min(xp_into / xp_needed, 1.0) if xp_needed > 0 else 1.0
    filled = int(pct * 30)
    empty = 30 - filled

    bar = f"  {belt['icon']} [{'█' * filled}{'░' * empty}] {next_belt['icon']}  {xp_into}/{xp_needed} XP"
    console.print(bar, style=f"bold {belt['color']}")


def sensei_says(text: str, typing_effect: bool = True):
    """Display sensei dialogue with optional typing effect."""
    console.print()
    if typing_effect:
        console.print("  [bold red]Sensei:[/] ", end="")
        for char in text:
            console.print(char, end="", highlight=False)
            time.sleep(0.015)
        console.print()
    else:
        console.print(f"  [bold red]Sensei:[/] {text}")
    console.print()


def show_menu(options: list[tuple[str, str]], prompt: str = "Your choice") -> str:
    """Display a numbered menu and return the selected key."""
    console.print()
    for i, (key, label) in enumerate(options, 1):
        console.print(f"  [bold cyan][{i}][/] {label}")
    console.print()

    while True:
        try:
            choice = IntPrompt.ask(f"  {prompt}", console=console)
            if 1 <= choice <= len(options):
                return options[choice - 1][0]
            console.print("  [red]Invalid choice. Try again.[/]")
        except (ValueError, KeyboardInterrupt):
            console.print("  [red]Invalid input.[/]")


def ask_text(prompt: str, default: str = "") -> str:
    return Prompt.ask(f"  {prompt}", default=default, console=console)


def ask_confirm(prompt: str) -> bool:
    return Confirm.ask(f"  {prompt}", console=console)


def show_skill_tree(skills: list[SkillProgress]):
    """Display the full skill tree with progress."""
    skill_map = {s.skill_id: s for s in skills}

    console.print()
    console.print("[bold underline]🌳 Skill Tree[/]")
    console.print()

    for branch_id, branch in SKILL_TREE.items():
        console.print(f"  {branch['icon']} [bold]{branch['name']}[/] — [dim]{branch['description']}[/]")

        for skill_id, skill_def in branch["skills"].items():
            full_id = f"{branch_id}.{skill_id}"
            progress = skill_map.get(full_id)

            if progress and progress.level > 0:
                level_name = SKILL_LEVEL_NAMES.get(progress.level, "?")
                pct = f"{progress.correct_rate:.0%}" if progress.times_practiced > 0 else "—"
                style = "green" if progress.level >= 3 else "yellow" if progress.level >= 2 else "white"
                marker = "●" if progress.level >= 4 else "◐" if progress.level >= 2 else "○"
                console.print(
                    f"    {marker} [{style}]{skill_def['name']}[/] "
                    f"[dim]Lv.{progress.level} {level_name} | {progress.xp} XP | Accuracy: {pct}[/]"
                )
            else:
                console.print(f"    ◌ [dim]{skill_def['name']} (locked)[/]")

        console.print()


def show_progress_report(user: UserProfile, skills: list[SkillProgress]):
    """Detailed progress report."""
    console.print()
    console.print(Panel("[bold]📊 Progress Report[/]", border_style="cyan"))

    # Stats table
    table = Table(show_header=False, box=box.ROUNDED, border_style="dim", padding=(0, 2))
    table.add_column("Stat", style="bold")
    table.add_column("Value", justify="right")

    belt = get_belt(user.total_xp)
    table.add_row("Rank", f"{belt['icon']} {belt['name']}")
    table.add_row("Total XP", str(user.total_xp))
    table.add_row("Sessions", str(user.sessions_completed))
    table.add_row("Current Streak", f"🔥 {user.current_streak} days")
    table.add_row("Longest Streak", f"{user.longest_streak} days")

    if user.challenges_attempted > 0:
        pass_rate = user.challenges_passed / user.challenges_attempted
        table.add_row("Challenges", f"{user.challenges_passed}/{user.challenges_attempted} ({pass_rate:.0%})")
    else:
        table.add_row("Challenges", "0")

    if user.quizzes_attempted > 0:
        quiz_rate = user.quizzes_correct / user.quizzes_attempted
        table.add_row("Quizzes", f"{user.quizzes_correct}/{user.quizzes_attempted} ({quiz_rate:.0%})")
    else:
        table.add_row("Quizzes", "0")

    table.add_row("Code Reviews", str(user.reviews_completed))

    unlocked = sum(1 for s in skills if s.level >= 1)
    mastered = sum(1 for s in skills if s.level >= 4)
    total = sum(len(b["skills"]) for b in SKILL_TREE.values())
    table.add_row("Skills Unlocked", f"{unlocked}/{total}")
    table.add_row("Skills Mastered", f"{mastered}/{total}")

    console.print(table)
    show_xp_bar(user)
    console.print()


def show_code_block(code: str, language: str = "python", title: str = ""):
    """Display syntax-highlighted code."""
    syntax = Syntax(code, language, theme="monokai", line_numbers=True)
    if title:
        console.print(Panel(syntax, title=title, border_style="cyan"))
    else:
        console.print(syntax)


def show_quiz_question(question: str, options: list[str]) -> int:
    """Display quiz and return selected option index (0-based)."""
    console.print()
    console.print(Panel(question, title="[bold]❓ Quiz[/]", border_style="yellow"))
    console.print()
    for i, opt in enumerate(options, 1):
        console.print(f"  [bold cyan][{i}][/] {opt}")
    console.print()

    while True:
        try:
            choice = IntPrompt.ask("  Your answer", console=console)
            if 1 <= choice <= len(options):
                return choice - 1
            console.print("  [red]Pick a number from the list.[/]")
        except (ValueError, KeyboardInterrupt):
            console.print("  [red]Invalid input.[/]")


def show_challenge_intro(title: str, description: str, difficulty: str, starter_code: str):
    """Display a coding challenge."""
    diff_colors = {"beginner": "green", "intermediate": "yellow", "advanced": "red"}
    color = diff_colors.get(difficulty, "white")

    console.print()
    console.print(Panel(
        f"[{color}]Difficulty: {difficulty.upper()}[/]\n\n{description}",
        title=f"[bold]⚔️ {title}[/]",
        border_style="red",
    ))

    if starter_code.strip():
        console.print()
        console.print("[dim]Starter code:[/]")
        show_code_block(starter_code)


def show_result(passed: bool, message: str):
    if passed:
        console.print(f"\n  [bold green]✅ PASS[/] — {message}")
    else:
        console.print(f"\n  [bold red]❌ FAIL[/] — {message}")


def show_xp_gain(amount: int, reason: str):
    console.print(f"  [bold yellow]⭐ +{amount} XP[/] — {reason}")


def show_belt_promotion(old_belt: dict, new_belt: dict):
    """Epic belt promotion display."""
    console.print()
    console.print(Panel(
        f"[bold]You have been promoted!\n\n"
        f"{old_belt['icon']} {old_belt['name']}  →  {new_belt['icon']} {new_belt['name']}[/]",
        title="[bold yellow]🎉 BELT PROMOTION 🎉[/]",
        border_style="bold yellow",
    ))
    console.print()


def get_multiline_input(prompt: str = "Enter your code (type 'END' on a new line to finish):") -> str:
    """Get multi-line code input from user."""
    console.print(f"\n  [dim]{prompt}[/]")
    console.print("  [dim]───────────────────────────────────[/]")
    lines = []
    while True:
        try:
            line = input("  ")
            if line.strip().upper() == "END":
                break
            lines.append(line)
        except EOFError:
            break
    return "\n".join(lines)


# ── Helpers ────────────────────────────────────────────────────────

def get_belt(xp: int = 0, belt_rank: int = 0) -> dict:
    """Get current belt by rank (exam-based). XP param kept for backward compat."""
    if belt_rank < len(BELTS):
        return BELTS[belt_rank]
    return BELTS[-1]


def get_next_belt(xp: int = 0, belt_rank: int = 0) -> Optional[dict]:
    """Get next belt to achieve, or None if at max."""
    next_rank = belt_rank + 1
    if next_rank < len(BELTS):
        return BELTS[next_rank]
    return None
