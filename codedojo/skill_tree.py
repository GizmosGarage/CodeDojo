"""Skill tree management for CodeDojo."""

from .config import SKILL_TREE
from .models import SkillProgress
from .storage import DojoStorage


def get_all_skill_ids() -> list[str]:
    """Get flat list of all skill IDs (branch.skill format)."""
    ids = []
    for branch_id, branch in SKILL_TREE.items():
        for skill_id in branch["skills"]:
            ids.append(f"{branch_id}.{skill_id}")
    return ids


def get_skill_info(full_skill_id: str) -> dict | None:
    """Get skill definition by full ID (e.g., 'fundamentals.variables_types')."""
    parts = full_skill_id.split(".", 1)
    if len(parts) != 2:
        return None
    branch_id, skill_id = parts
    branch = SKILL_TREE.get(branch_id)
    if not branch:
        return None
    skill = branch["skills"].get(skill_id)
    if not skill:
        return None
    return {
        "full_id": full_skill_id,
        "branch_id": branch_id,
        "skill_id": skill_id,
        "branch_name": branch["name"],
        "branch_icon": branch["icon"],
        **skill,
    }


def get_prerequisites_met(full_skill_id: str, storage: DojoStorage) -> bool:
    """Check if all prerequisites for a skill are met (unlocked)."""
    info = get_skill_info(full_skill_id)
    if not info:
        return False

    for prereq_id in info.get("prerequisites", []):
        prereq = storage.get_skill(prereq_id)
        if not prereq or prereq.level < 1:
            return False
    return True


def get_unlockable_skills(storage: DojoStorage) -> list[str]:
    """Get skills that can be unlocked based on current progress."""
    unlockable = []
    for skill_id in get_all_skill_ids():
        existing = storage.get_skill(skill_id)
        if existing and existing.level > 0:
            continue  # Already unlocked
        if get_prerequisites_met(skill_id, storage):
            unlockable.append(skill_id)
    return unlockable


def get_unlocked_skills(storage: DojoStorage) -> list[str]:
    """Get all currently unlocked skill IDs."""
    all_skills = storage.get_all_skills()
    return [s.skill_id for s in all_skills if s.level >= 1]


def get_recommended_skills(storage: DojoStorage, limit: int = 3) -> list[str]:
    """Smart recommendation: weak skills first, then unlockable new ones."""
    recommended = []

    # Priority 1: Skills needing review (not practiced in 7+ days)
    stale = storage.get_skills_needing_review(days=7)
    for s in stale[:limit]:
        if s.skill_id not in recommended:
            recommended.append(s.skill_id)

    # Priority 2: Weakest unlocked skills
    weak = storage.get_weakest_skills(limit=limit)
    for s in weak:
        if s.skill_id not in recommended and len(recommended) < limit:
            recommended.append(s.skill_id)

    # Priority 3: New unlockable skills
    if len(recommended) < limit:
        unlockable = get_unlockable_skills(storage)
        for sid in unlockable:
            if sid not in recommended and len(recommended) < limit:
                recommended.append(sid)

    return recommended


def unlock_initial_skills(storage: DojoStorage):
    """Unlock the starter skills (no prerequisites)."""
    for branch_id, branch in SKILL_TREE.items():
        for skill_id, skill_def in branch["skills"].items():
            if not skill_def.get("prerequisites"):
                full_id = f"{branch_id}.{skill_id}"
                storage.unlock_skill(full_id)


def check_and_unlock_new_skills(storage: DojoStorage) -> list[str]:
    """Check if any new skills can be unlocked. Returns newly unlocked IDs."""
    newly_unlocked = []
    unlockable = get_unlockable_skills(storage)
    for skill_id in unlockable:
        storage.unlock_skill(skill_id)
        newly_unlocked.append(skill_id)
    return newly_unlocked


def get_branch_options() -> list[tuple[str, str]]:
    """Get list of (branch_id, display_name) for menu selection."""
    return [(bid, f"{b['icon']} {b['name']}") for bid, b in SKILL_TREE.items()]


def get_skill_options_in_branch(branch_id: str, storage: DojoStorage) -> list[tuple[str, str]]:
    """Get unlocked skills in a branch for menu selection."""
    branch = SKILL_TREE.get(branch_id, {})
    options = []
    for skill_id, skill_def in branch.get("skills", {}).items():
        full_id = f"{branch_id}.{skill_id}"
        progress = storage.get_skill(full_id)
        if progress and progress.level >= 1:
            from .models import SKILL_LEVEL_NAMES
            level_name = SKILL_LEVEL_NAMES.get(progress.level, "?")
            options.append((full_id, f"{skill_def['name']} [Lv.{progress.level} {level_name}]"))
    return options
