"""Belt ranking, level system, and XP for CodeDojo."""

from .config import BELTS, XP_STREAK_BONUS, BELT_EXAM_REQUIREMENTS, get_level_from_xp
from .models import UserProfile, SkillProgress, SKILL_LEVEL_XP
from .display import get_belt, get_next_belt, show_belt_promotion, show_xp_gain


def award_xp(user: UserProfile, amount: int, reason: str, storage) -> dict:
    """Award XP to user, update level, and persist.

    Belts are NO LONGER promoted by XP — only by passing belt exams.
    """
    user.total_xp += amount

    # Update player level (XP-based, steep curve)
    new_level = get_level_from_xp(user.total_xp)
    level_up = new_level > user.level
    user.level = new_level

    show_xp_gain(amount, reason)

    storage.update_user(user)
    return {"xp_added": amount, "level_up": level_up, "new_level": user.level}


def award_skill_xp(skill: SkillProgress, amount: int, correct: bool, storage):
    """Award XP to a specific skill and update level."""
    skill.xp += amount
    skill.times_practiced += 1

    # Update rolling accuracy
    total = skill.times_practiced
    if correct:
        skill.correct_rate = ((skill.correct_rate * (total - 1)) + 1.0) / total
    else:
        skill.correct_rate = (skill.correct_rate * (total - 1)) / total

    # Check level up
    for level, threshold in sorted(SKILL_LEVEL_XP.items(), reverse=True):
        if skill.xp >= threshold:
            if skill.level < level:
                skill.level = level
            break

    from datetime import datetime
    skill.last_practiced = datetime.now().isoformat()
    storage.upsert_skill(skill)


def calculate_streak_bonus(user: UserProfile) -> int:
    """Calculate bonus XP for current streak."""
    return min(user.current_streak * XP_STREAK_BONUS, 50)  # Cap at 50


def get_rank_summary(user: UserProfile) -> str:
    """Get a text summary of current rank (belt is exam-based now)."""
    belt = BELTS[user.belt_rank] if user.belt_rank < len(BELTS) else BELTS[-1]
    next_rank = user.belt_rank + 1
    if next_rank < len(BELTS):
        next_belt = BELTS[next_rank]
        return f"{belt['icon']} {belt['name']} — Pass the {next_belt['name']} exam to advance"
    return f"{belt['icon']} {belt['name']} — Maximum rank achieved"


def check_belt_exam_readiness(user: UserProfile, storage) -> dict:
    """Check if the student is ready for their next belt exam.

    Returns readiness status and details.
    """
    next_rank = user.belt_rank + 1
    if next_rank >= len(BELTS):
        return {"ready": False, "reason": "max_rank", "next_belt": None}

    if next_rank not in BELT_EXAM_REQUIREMENTS:
        return {"ready": False, "reason": "no_exam_defined", "next_belt": None}

    req = BELT_EXAM_REQUIREMENTS[next_rank]
    next_belt = BELTS[next_rank]

    # Check trained skills count
    all_skills = storage.get_all_skills()
    trained_skills = [s for s in all_skills if s.level >= 1]
    trained_count = len(trained_skills)

    # Check average accuracy
    if trained_skills:
        total_practiced = [s for s in trained_skills if s.times_practiced > 0]
        avg_accuracy = (
            sum(s.correct_rate for s in total_practiced) / len(total_practiced)
            if total_practiced else 0.0
        )
    else:
        avg_accuracy = 0.0

    # Check required skills
    skill_map = {s.skill_id: s for s in all_skills}
    required_met = all(
        skill_map.get(sid) and skill_map[sid].level >= 1
        for sid in req.get("required_skills", [])
    )

    # Check mastered skills (for Black Belt)
    mastered_count = sum(1 for s in all_skills if s.level >= 4)
    min_mastered = req.get("min_skills_mastered", 0)

    # Check if there's a recent failed exam that needs more training
    last_failed = storage.get_last_failed_exam(next_rank)
    needs_more_training = False
    if last_failed:
        sessions_since = storage.count_sessions_since(last_failed.date)
        if sessions_since < 3:
            needs_more_training = True

    # Build result
    checks = {
        "skills_trained": {"required": req["min_skills_trained"], "current": trained_count,
                           "met": trained_count >= req["min_skills_trained"]},
        "avg_accuracy": {"required": req["min_avg_accuracy"], "current": round(avg_accuracy, 2),
                         "met": avg_accuracy >= req["min_avg_accuracy"]},
        "required_skills": {"met": required_met},
        "needs_more_training": needs_more_training,
    }
    if min_mastered > 0:
        checks["skills_mastered"] = {"required": min_mastered, "current": mastered_count,
                                      "met": mastered_count >= min_mastered}

    all_met = (
        checks["skills_trained"]["met"]
        and checks["avg_accuracy"]["met"]
        and checks["required_skills"]["met"]
        and not needs_more_training
        and (min_mastered == 0 or checks.get("skills_mastered", {}).get("met", True))
    )

    return {
        "ready": all_met,
        "next_belt": next_belt,
        "next_rank": next_rank,
        "checks": checks,
        "exam_config": {
            "quizzes": req["exam_quizzes"],
            "challenges": req["exam_challenges"],
            "has_boss": req["exam_boss"],
            "topics": req["topics"],
            "total_rounds": req["exam_quizzes"] + req["exam_challenges"] + (1 if req["exam_boss"] else 0),
        },
        "last_failed_feedback": last_failed.feedback if last_failed else None,
    }
