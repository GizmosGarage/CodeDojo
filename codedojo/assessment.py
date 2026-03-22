"""Initial skill assessment to determine starting rank."""

from .config import BELTS, SKILL_TREE
from .display import (
    console, sensei_says, show_quiz_question, show_result,
    show_belt_promotion, show_xp_gain, get_belt
)
from .models import UserProfile
from .sensei import Sensei
from .storage import DojoStorage
from .skill_tree import unlock_initial_skills


# Skill areas mapped to skill tree IDs for initial unlock boosting
ASSESSMENT_SKILL_MAP = {
    "variables_types": "fundamentals.variables_types",
    "control_flow": "fundamentals.control_flow",
    "functions": "fundamentals.functions",
    "data_structures": "data_structures.lists_tuples",
    "comprehensions": "data_structures.comprehensions",
    "oop": "oop.classes_basics",
    "error_handling": "error_handling.exceptions",
    "decorators_generators": "functional.decorators",
}

# How many correct answers map to starting belt/XP
ASSESSMENT_RESULTS = [
    (0, 2, "White Belt",  0),     # 0-2 correct: White, 0 XP
    (3, 4, "Yellow Belt", 100),   # 3-4 correct: Yellow, 100 XP
    (5, 6, "Orange Belt", 300),   # 5-6 correct: Orange, 300 XP
    (7, 7, "Green Belt",  600),   # 7 correct: Green, 600 XP
    (8, 8, "Blue Belt",   1000),  # 8 correct: Blue, 1000 XP
]


def run_assessment(user: UserProfile, sensei: Sensei, storage: DojoStorage) -> int:
    """Run the initial skill assessment. Returns starting XP."""

    sensei_says(
        "Before we begin your training, I must understand where you stand. "
        "Answer these questions honestly — there is no shame in not knowing. "
        "Only in pretending to know."
    )

    console.print()
    console.print("  [dim]Generating assessment... this may take a moment.[/]")

    try:
        questions = sensei.generate_assessment_questions()
    except Exception as e:
        console.print(f"  [red]Failed to generate assessment: {e}[/]")
        console.print("  [yellow]Starting you at White Belt. We will learn your level as we train.[/]")
        unlock_initial_skills(storage)
        return 0

    if not questions:
        console.print("  [yellow]Assessment could not be generated. Starting at White Belt.[/]")
        unlock_initial_skills(storage)
        return 0

    correct = 0
    total = len(questions)
    skill_results = {}  # skill_area -> bool (correct or not)

    for i, q in enumerate(questions, 1):
        console.print(f"\n  [dim]Question {i}/{total}[/]")

        answer = show_quiz_question(q["question"], q["options"])

        is_correct = answer == q["correct_index"]
        skill_area = q.get("skill_area", "general")
        skill_results[skill_area] = is_correct

        if is_correct:
            correct += 1
            show_result(True, "Correct.")
        else:
            correct_answer = q["options"][q["correct_index"]]
            show_result(False, f"The answer was: {correct_answer}")

    # Determine starting rank
    starting_xp = 0
    belt_name = "White Belt"
    for low, high, name, xp in ASSESSMENT_RESULTS:
        if low <= correct <= high:
            starting_xp = xp
            belt_name = name
            break

    # Show results
    console.print()
    console.print(f"  [bold]Assessment Complete: {correct}/{total} correct[/]")

    belt = get_belt(starting_xp)
    console.print()
    sensei_says(
        f"I see. You will begin your journey as a {belt['icon']} {belt['name']}. "
        f"{'There is much work ahead.' if correct < 5 else 'You have a foundation. Now we build upon it.' if correct < 7 else 'Impressive. But do not let skill breed arrogance.'}"
    )

    # Unlock initial skills
    unlock_initial_skills(storage)

    # Boost skills they demonstrated knowledge in
    for area, was_correct in skill_results.items():
        mapped_skill = None
        for key, skill_id in ASSESSMENT_SKILL_MAP.items():
            if key in area.lower().replace(" ", "_"):
                mapped_skill = skill_id
                break

        if mapped_skill and was_correct:
            skill = storage.get_skill(mapped_skill)
            if skill:
                skill.xp += 25
                skill.correct_rate = 1.0
                skill.times_practiced = 1
                from datetime import datetime
                skill.last_practiced = datetime.now().isoformat()
                storage.upsert_skill(skill)

    return starting_xp
