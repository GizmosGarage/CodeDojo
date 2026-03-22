"""FastAPI REST API for CodeDojo — wraps all existing functionality."""

import dataclasses
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .assessment import ASSESSMENT_SKILL_MAP, ASSESSMENT_RESULTS
from .challenges import run_challenge, format_test_results
from .config import BELTS, SESSION_LENGTHS, SKILL_TREE, BELT_EXAM_REQUIREMENTS, get_level_from_xp, get_xp_for_level, get_xp_for_next_level
from .display import get_belt, get_next_belt
from .models import (
    BeltExamRecord,
    CodingChallenge,
    SessionRecord,
    SkillProgress,
    UserProfile,
    SKILL_LEVEL_NAMES,
    SKILL_LEVEL_XP,
)
from .ranking import award_xp, award_skill_xp, calculate_streak_bonus, get_rank_summary, check_belt_exam_readiness
from .sensei import Sensei
from .skill_tree import (
    check_and_unlock_new_skills,
    get_all_skill_ids,
    get_branch_options,
    get_recommended_skills,
    get_skill_info,
    get_skill_options_in_branch,
    get_unlocked_skills,
    unlock_initial_skills,
)
from .storage import DojoStorage


# ── Singleton state ───────────────────────────────────────────────

_storage: Optional[DojoStorage] = None
_sensei: Optional[Sensei] = None


def get_storage() -> DojoStorage:
    assert _storage is not None, "Storage not initialised"
    return _storage


def get_sensei() -> Sensei:
    assert _sensei is not None, "Sensei not initialised"
    return _sensei


# ── Lifespan ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _storage, _sensei
    _storage = DojoStorage()
    _sensei = Sensei()
    yield
    _storage.close()


# ── App ───────────────────────────────────────────────────────────

app = FastAPI(title="CodeDojo API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic request/response models ─────────────────────────────

class CreateUserRequest(BaseModel):
    name: str


class QuizGenerateRequest(BaseModel):
    skill_id: str
    difficulty: str = "beginner"
    count: int = 1


class ChallengeGenerateRequest(BaseModel):
    skill_id: str
    difficulty: str = "beginner"


class ChallengeRunRequest(BaseModel):
    challenge: dict
    student_code: str


class ChallengeEvaluateRequest(BaseModel):
    title: str
    code: str
    results: list[dict]
    all_passed: bool


class ReviewRequest(BaseModel):
    code: str
    context: str = "general Python code"


class ChatRequest(BaseModel):
    message: str
    context: str = ""


class AwardXpRequest(BaseModel):
    amount: int
    reason: str
    skill_id: Optional[str] = None
    correct: Optional[bool] = None


class SaveSessionRequest(BaseModel):
    session_id: str
    date: str
    duration_minutes: int = 0
    xp_earned: int = 0
    challenges_completed: int = 0
    quizzes_completed: int = 0
    reviews_completed: int = 0
    skills_practiced: str = ""


class AssessmentAnswerRequest(BaseModel):
    question_index: int
    answer_index: int
    skill_area: str
    is_correct: bool
    total_questions: int
    correct_so_far: int


class AssessmentCompleteRequest(BaseModel):
    correct_count: int
    total: int
    skill_results: dict  # skill_area -> bool


class BeltExamCompleteRequest(BaseModel):
    belt_target: int
    rounds_passed: int
    total_rounds: int
    weak_areas: list[str] = []


# ── Helpers ───────────────────────────────────────────────────────

def _user_to_dict(user: UserProfile) -> dict:
    d = dataclasses.asdict(user)
    belt = BELTS[user.belt_rank] if user.belt_rank < len(BELTS) else BELTS[-1]
    next_rank = user.belt_rank + 1
    next_belt = BELTS[next_rank] if next_rank < len(BELTS) else None
    d["belt"] = belt
    d["next_belt"] = next_belt
    d["rank_summary"] = get_rank_summary(user)
    d["streak_bonus"] = calculate_streak_bonus(user)
    # Level info
    d["level"] = user.level
    d["xp_for_current_level"] = get_xp_for_level(user.level)
    d["xp_for_next_level"] = get_xp_for_next_level(user.level)
    d["level_progress"] = (
        (user.total_xp - get_xp_for_level(user.level)) /
        max(get_xp_for_next_level(user.level) - get_xp_for_level(user.level), 1)
    )
    return d


def _skill_to_dict(skill: SkillProgress) -> dict:
    d = dataclasses.asdict(skill)
    d["level_name"] = SKILL_LEVEL_NAMES.get(skill.level, "Unknown")
    info = get_skill_info(skill.skill_id)
    if info:
        d["name"] = info["name"]
        d["branch_name"] = info["branch_name"]
        d["branch_icon"] = info["branch_icon"]
        d["topics"] = info["topics"]
    return d


def _require_user() -> UserProfile:
    user = get_storage().get_user()
    if not user:
        raise HTTPException(status_code=404, detail="No user profile found. Create one first via POST /api/user.")
    return user


# ── Health ────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "CodeDojo API"}


# ── User ──────────────────────────────────────────────────────────

@app.get("/api/user")
async def get_user():
    user = _require_user()
    # Sync level from XP on read
    user.level = get_level_from_xp(user.total_xp)
    get_storage().update_user(user)
    return _user_to_dict(user)


@app.post("/api/user")
async def create_user(req: CreateUserRequest):
    storage = get_storage()
    existing = storage.get_user()
    if existing:
        raise HTTPException(status_code=409, detail="User already exists.")
    user = storage.create_user(req.name)
    return _user_to_dict(user)


# ── Config ────────────────────────────────────────────────────────

@app.get("/api/config")
async def get_config():
    return {
        "belts": BELTS,
        "session_lengths": SESSION_LENGTHS,
        "skill_tree": SKILL_TREE,
        "xp_thresholds": {
            "skill_levels": SKILL_LEVEL_XP,
            "skill_level_names": SKILL_LEVEL_NAMES,
        },
        "belt_exam_requirements": BELT_EXAM_REQUIREMENTS,
    }


# ── Skills ────────────────────────────────────────────────────────

@app.get("/api/skills")
async def get_skills():
    _require_user()
    storage = get_storage()
    skills = storage.get_all_skills()
    return [_skill_to_dict(s) for s in skills]


@app.get("/api/skills/recommended")
async def get_skills_recommended():
    _require_user()
    storage = get_storage()
    recommended_ids = get_recommended_skills(storage, limit=5)
    result = []
    for sid in recommended_ids:
        info = get_skill_info(sid)
        progress = storage.get_skill(sid)
        entry = {"skill_id": sid}
        if info:
            entry.update({
                "name": info["name"],
                "branch_name": info["branch_name"],
                "branch_icon": info["branch_icon"],
                "topics": info["topics"],
            })
        if progress:
            entry.update({
                "xp": progress.xp,
                "level": progress.level,
                "level_name": SKILL_LEVEL_NAMES.get(progress.level, "Unknown"),
                "correct_rate": progress.correct_rate,
            })
        result.append(entry)
    return result


@app.get("/api/skills/tree")
async def get_skill_tree():
    storage = get_storage()
    all_progress = storage.get_all_skills()
    progress_map = {s.skill_id: s for s in all_progress}

    tree = {}
    for branch_id, branch in SKILL_TREE.items():
        branch_data = {
            "name": branch["name"],
            "icon": branch["icon"],
            "description": branch["description"],
            "skills": {},
        }
        for skill_id, skill_def in branch["skills"].items():
            full_id = f"{branch_id}.{skill_id}"
            progress = progress_map.get(full_id)
            skill_entry = {
                "name": skill_def["name"],
                "topics": skill_def["topics"],
                "prerequisites": skill_def.get("prerequisites", []),
                "unlocked": progress is not None and progress.level >= 1,
            }
            if progress:
                skill_entry.update({
                    "xp": progress.xp,
                    "level": progress.level,
                    "level_name": SKILL_LEVEL_NAMES.get(progress.level, "Unknown"),
                    "times_practiced": progress.times_practiced,
                    "last_practiced": progress.last_practiced,
                    "correct_rate": progress.correct_rate,
                })
            else:
                skill_entry.update({
                    "xp": 0,
                    "level": 0,
                    "level_name": "Locked",
                    "times_practiced": 0,
                    "last_practiced": None,
                    "correct_rate": 0.0,
                })
            branch_data["skills"][full_id] = skill_entry
        tree[branch_id] = branch_data
    return tree


@app.post("/api/skills/unlock-initial")
async def unlock_initial():
    _require_user()
    storage = get_storage()
    unlock_initial_skills(storage)
    unlocked = get_unlocked_skills(storage)
    return {"unlocked": unlocked}


# ── Assessment ────────────────────────────────────────────────────

@app.get("/api/assessment/questions")
async def get_assessment_questions():
    sensei = get_sensei()
    try:
        questions = sensei.generate_assessment_questions()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to generate assessment questions: {e}")
    if not questions:
        raise HTTPException(status_code=502, detail="Assessment generation returned no questions.")
    return {"questions": questions}


@app.post("/api/assessment/answer")
async def process_assessment_answer(req: AssessmentAnswerRequest):
    correct_so_far = req.correct_so_far + (1 if req.is_correct else 0)
    progress_pct = ((req.question_index + 1) / req.total_questions) * 100
    return {
        "question_index": req.question_index,
        "is_correct": req.is_correct,
        "correct_so_far": correct_so_far,
        "total_questions": req.total_questions,
        "progress_percent": progress_pct,
    }


@app.post("/api/assessment/complete")
async def complete_assessment(req: AssessmentCompleteRequest):
    storage = get_storage()
    user = _require_user()

    # Determine starting XP (but NOT belt — belt requires exams now)
    starting_xp = 0
    for low, high, name, xp in ASSESSMENT_RESULTS:
        if low <= req.correct_count <= high:
            starting_xp = xp
            break

    # Set user XP and calculate level
    user.total_xp = starting_xp
    user.level = get_level_from_xp(starting_xp)
    user.belt_rank = 0  # Always start at White Belt — must pass exams
    storage.update_user(user)

    # Unlock initial skills
    unlock_initial_skills(storage)

    # Boost skills the student got correct
    boosted_skills = []
    for area, was_correct in req.skill_results.items():
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
                skill.last_practiced = datetime.now().isoformat()
                storage.upsert_skill(skill)
                boosted_skills.append(mapped_skill)

    belt = BELTS[user.belt_rank]
    return {
        "correct_count": req.correct_count,
        "total": req.total,
        "starting_xp": starting_xp,
        "starting_level": user.level,
        "belt": belt,
        "belt_name": belt["name"],
        "boosted_skills": boosted_skills,
    }


# ── Quiz ──────────────────────────────────────────────────────────

@app.post("/api/quiz/generate")
async def generate_quiz(req: QuizGenerateRequest):
    _require_user()
    info = get_skill_info(req.skill_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"Unknown skill: {req.skill_id}")

    sensei = get_sensei()
    try:
        questions = sensei.generate_quiz(
            skill_id=req.skill_id,
            skill_name=info["name"],
            topics=info["topics"],
            difficulty=req.difficulty,
            count=req.count,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to generate quiz: {e}")

    return {"questions": [dataclasses.asdict(q) for q in questions]}


# ── Challenge ─────────────────────────────────────────────────────

@app.post("/api/challenge/generate")
async def generate_challenge(req: ChallengeGenerateRequest):
    _require_user()
    info = get_skill_info(req.skill_id)
    if not info:
        raise HTTPException(status_code=404, detail=f"Unknown skill: {req.skill_id}")

    sensei = get_sensei()
    try:
        challenge = sensei.generate_challenge(
            skill_id=req.skill_id,
            skill_name=info["name"],
            topics=info["topics"],
            difficulty=req.difficulty,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to generate challenge: {e}")

    return dataclasses.asdict(challenge)


@app.post("/api/challenge/run")
async def run_challenge_tests(req: ChallengeRunRequest):
    try:
        challenge = CodingChallenge(
            title=req.challenge.get("title", ""),
            description=req.challenge.get("description", ""),
            skill_id=req.challenge.get("skill_id", ""),
            difficulty=req.challenge.get("difficulty", ""),
            starter_code=req.challenge.get("starter_code", ""),
            test_cases=req.challenge.get("test_cases", []),
            hints=req.challenge.get("hints", []),
            solution_approach=req.challenge.get("solution_approach", ""),
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid challenge data: {e}")

    try:
        results = run_challenge(challenge, req.student_code)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running challenge: {e}")

    all_passed = all(r["passed"] for r in results)
    formatted = format_test_results(results)

    return {
        "results": results,
        "all_passed": all_passed,
        "summary": formatted,
    }


@app.post("/api/challenge/evaluate")
async def evaluate_challenge(req: ChallengeEvaluateRequest):
    sensei = get_sensei()
    try:
        feedback = sensei.evaluate_solution(
            challenge_title=req.title,
            code=req.code,
            test_results=req.results,
            all_passed=req.all_passed,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to get evaluation: {e}")

    return {"feedback": feedback}


# ── Code Review ───────────────────────────────────────────────────

@app.post("/api/review")
async def review_code(req: ReviewRequest):
    _require_user()
    sensei = get_sensei()
    try:
        result = sensei.review_code(code=req.code, context=req.context)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to perform code review: {e}")

    return dataclasses.asdict(result)


# ── Chat ──────────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat_with_sensei(req: ChatRequest):
    sensei = get_sensei()
    try:
        response = sensei.chat(message=req.message, context=req.context)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Chat failed: {e}")

    return {"response": response}


# ── XP ────────────────────────────────────────────────────────────

@app.post("/api/xp/award")
async def award_xp_endpoint(req: AwardXpRequest):
    storage = get_storage()
    user = _require_user()

    old_level = user.level
    user.total_xp += req.amount
    user.level = get_level_from_xp(user.total_xp)
    level_up = user.level > old_level

    belt = BELTS[user.belt_rank] if user.belt_rank < len(BELTS) else BELTS[-1]

    storage.update_user(user)

    skill_update = None
    if req.skill_id:
        skill = storage.get_skill(req.skill_id)
        if not skill:
            skill = SkillProgress(skill_id=req.skill_id, level=1)
        award_skill_xp(skill, req.amount, req.correct if req.correct is not None else True, storage)
        skill_update = _skill_to_dict(storage.get_skill(req.skill_id))

        newly_unlocked = check_and_unlock_new_skills(storage)
    else:
        newly_unlocked = []

    return {
        "xp_added": req.amount,
        "total_xp": user.total_xp,
        "level": user.level,
        "level_up": level_up,
        "belt": belt,
        "skill_update": skill_update,
        "newly_unlocked": newly_unlocked,
        "streak_bonus": calculate_streak_bonus(user),
    }


# ── Belt Exam ─────────────────────────────────────────────────────

@app.get("/api/belt-exam/readiness")
async def belt_exam_readiness():
    """Check if the student is ready for their next belt exam."""
    user = _require_user()
    storage = get_storage()
    result = check_belt_exam_readiness(user, storage)
    return result


@app.post("/api/belt-exam/generate-quiz")
async def belt_exam_generate_quiz():
    """Generate quiz questions for the belt exam."""
    user = _require_user()
    storage = get_storage()
    readiness = check_belt_exam_readiness(user, storage)

    if not readiness["ready"]:
        raise HTTPException(status_code=400, detail="Not ready for belt exam")

    next_rank = readiness["next_rank"]
    next_belt = readiness["next_belt"]
    exam_config = readiness["exam_config"]

    # Determine difficulty based on belt
    difficulty_map = {1: "beginner", 2: "beginner", 3: "intermediate",
                      4: "intermediate", 5: "advanced", 6: "advanced", 7: "advanced"}
    difficulty = difficulty_map.get(next_rank, "intermediate")

    sensei = get_sensei()
    try:
        questions = sensei.generate_belt_exam_quiz(
            belt_name=next_belt["name"],
            topics=exam_config["topics"],
            difficulty=difficulty,
            count=exam_config["quizzes"],
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to generate exam quiz: {e}")

    return {
        "questions": [dataclasses.asdict(q) for q in questions],
        "belt_target": next_rank,
        "belt_name": next_belt["name"],
    }


@app.post("/api/belt-exam/generate-challenge")
async def belt_exam_generate_challenge():
    """Generate a coding challenge for the belt exam."""
    user = _require_user()
    storage = get_storage()
    readiness = check_belt_exam_readiness(user, storage)

    if not readiness["ready"]:
        raise HTTPException(status_code=400, detail="Not ready for belt exam")

    next_rank = readiness["next_rank"]
    next_belt = readiness["next_belt"]
    exam_config = readiness["exam_config"]

    difficulty_map = {1: "beginner", 2: "beginner", 3: "intermediate",
                      4: "intermediate", 5: "advanced", 6: "advanced", 7: "advanced"}
    difficulty = difficulty_map.get(next_rank, "intermediate")

    sensei = get_sensei()
    try:
        challenge = sensei.generate_challenge(
            skill_id="belt_exam",
            skill_name=f"{next_belt['name']} Exam",
            topics=exam_config["topics"],
            difficulty=difficulty,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to generate exam challenge: {e}")

    return dataclasses.asdict(challenge)


@app.post("/api/belt-exam/generate-boss")
async def belt_exam_generate_boss():
    """Generate the BOSS challenge for the belt exam."""
    user = _require_user()
    storage = get_storage()
    readiness = check_belt_exam_readiness(user, storage)

    if not readiness["ready"]:
        raise HTTPException(status_code=400, detail="Not ready for belt exam")

    next_rank = readiness["next_rank"]
    next_belt = readiness["next_belt"]
    exam_config = readiness["exam_config"]

    difficulty_map = {1: "beginner", 2: "intermediate", 3: "intermediate",
                      4: "advanced", 5: "advanced", 6: "advanced", 7: "advanced"}
    difficulty = difficulty_map.get(next_rank, "advanced")

    sensei = get_sensei()
    try:
        boss = sensei.generate_belt_exam_boss(
            belt_name=next_belt["name"],
            topics=exam_config["topics"],
            difficulty=difficulty,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to generate boss challenge: {e}")

    return dataclasses.asdict(boss)


@app.post("/api/belt-exam/complete")
async def belt_exam_complete(req: BeltExamCompleteRequest):
    """Complete a belt exam — record result and promote if passed."""
    storage = get_storage()
    user = _require_user()
    sensei = get_sensei()

    passed = req.rounds_passed >= req.total_rounds
    next_belt = BELTS[req.belt_target] if req.belt_target < len(BELTS) else BELTS[-1]

    # Get sensei feedback
    try:
        feedback = sensei.evaluate_belt_exam(
            belt_name=next_belt["name"],
            rounds_passed=req.rounds_passed,
            total_rounds=req.total_rounds,
            weak_areas=req.weak_areas,
        )
    except Exception:
        feedback = "The exam is complete. Reflect on your performance."

    # Save exam record
    exam = BeltExamRecord(
        exam_id=str(uuid.uuid4()),
        belt_target=req.belt_target,
        date=datetime.now().isoformat(),
        passed=passed,
        score=req.rounds_passed,
        total_rounds=req.total_rounds,
        feedback=feedback,
    )
    storage.save_belt_exam(exam)

    # Promote if passed
    if passed and user.belt_rank < req.belt_target:
        user.belt_rank = req.belt_target
        storage.update_user(user)

    return {
        "passed": passed,
        "new_belt": BELTS[user.belt_rank] if passed else None,
        "belt_rank": user.belt_rank,
        "feedback": feedback,
        "score": req.rounds_passed,
        "total_rounds": req.total_rounds,
    }


# ── Progress ──────────────────────────────────────────────────────

@app.get("/api/progress")
async def get_progress():
    user = _require_user()
    storage = get_storage()
    skills = storage.get_all_skills()

    # Sync level
    user.level = get_level_from_xp(user.total_xp)
    storage.update_user(user)

    belt = BELTS[user.belt_rank] if user.belt_rank < len(BELTS) else BELTS[-1]
    next_rank = user.belt_rank + 1
    next_belt = BELTS[next_rank] if next_rank < len(BELTS) else None

    unlocked = sum(1 for s in skills if s.level >= 1)
    mastered = sum(1 for s in skills if s.level >= 4)
    total_skills = sum(len(b["skills"]) for b in SKILL_TREE.values())

    challenge_pass_rate = (
        user.challenges_passed / user.challenges_attempted
        if user.challenges_attempted > 0
        else 0.0
    )
    quiz_correct_rate = (
        user.quizzes_correct / user.quizzes_attempted
        if user.quizzes_attempted > 0
        else 0.0
    )

    weakest = storage.get_weakest_skills(3)
    strongest = storage.get_strongest_skills(3)
    needing_review = storage.get_skills_needing_review(7)

    # Check belt exam readiness
    exam_readiness = check_belt_exam_readiness(user, storage)

    return {
        "user": _user_to_dict(user),
        "belt": belt,
        "next_belt": next_belt,
        "stats": {
            "total_xp": user.total_xp,
            "level": user.level,
            "sessions_completed": user.sessions_completed,
            "current_streak": user.current_streak,
            "longest_streak": user.longest_streak,
            "challenges_passed": user.challenges_passed,
            "challenges_attempted": user.challenges_attempted,
            "challenge_pass_rate": challenge_pass_rate,
            "quizzes_correct": user.quizzes_correct,
            "quizzes_attempted": user.quizzes_attempted,
            "quiz_correct_rate": quiz_correct_rate,
            "reviews_completed": user.reviews_completed,
            "skills_unlocked": unlocked,
            "skills_mastered": mastered,
            "total_skills": total_skills,
        },
        "belt_exam_ready": exam_readiness["ready"],
        "belt_exam_details": exam_readiness,
        "weakest_skills": [_skill_to_dict(s) for s in weakest],
        "strongest_skills": [_skill_to_dict(s) for s in strongest],
        "skills_needing_review": [_skill_to_dict(s) for s in needing_review],
    }


# ── Sessions ──────────────────────────────────────────────────────

@app.get("/api/sessions")
async def get_sessions(limit: int = 10):
    _require_user()
    storage = get_storage()
    sessions = storage.get_recent_sessions(limit=limit)
    return [dataclasses.asdict(s) for s in sessions]


@app.post("/api/session/save")
async def save_session(req: SaveSessionRequest):
    storage = get_storage()
    _require_user()
    record = SessionRecord(
        session_id=req.session_id,
        date=req.date,
        duration_minutes=req.duration_minutes,
        xp_earned=req.xp_earned,
        challenges_completed=req.challenges_completed,
        quizzes_completed=req.quizzes_completed,
        reviews_completed=req.reviews_completed,
        skills_practiced=req.skills_practiced,
    )
    try:
        storage.save_session(record)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save session: {e}")

    return {"saved": True, "session_id": req.session_id}


# ── Streak ────────────────────────────────────────────────────────

@app.post("/api/streak/update")
async def update_streak():
    storage = get_storage()
    user = _require_user()
    user = storage.update_streak(user)
    storage.update_user(user)
    return {
        "current_streak": user.current_streak,
        "longest_streak": user.longest_streak,
        "last_session_date": user.last_session_date,
        "streak_bonus": calculate_streak_bonus(user),
    }


# ── Greet / Farewell ─────────────────────────────────────────────

@app.get("/api/greet")
async def greet():
    storage = get_storage()
    user = _require_user()
    sensei = get_sensei()

    belt = BELTS[user.belt_rank] if user.belt_rank < len(BELTS) else BELTS[-1]

    # Calculate days away
    if user.last_session_date:
        last = datetime.fromisoformat(user.last_session_date).date()
        days_away = (datetime.now().date() - last).days
    else:
        days_away = -1  # first visit

    # Get weak/strong areas
    weakest = storage.get_weakest_skills(1)
    strongest = storage.get_strongest_skills(1)

    weak_area = weakest[0].skill_id if weakest else "unknown"
    strong_area = strongest[0].skill_id if strongest else "unknown"

    # Resolve to display names
    weak_info = get_skill_info(weak_area)
    strong_info = get_skill_info(strong_area)
    weak_display = weak_info["name"] if weak_info else weak_area
    strong_display = strong_info["name"] if strong_info else strong_area

    try:
        greeting = sensei.greet(
            name=user.name,
            belt_name=belt["name"],
            belt_icon=belt["icon"],
            xp=user.total_xp,
            days_away=days_away,
            streak=user.current_streak,
            weak_area=weak_display,
            strong_area=strong_display,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to generate greeting: {e}")

    return {"greeting": greeting}


@app.get("/api/farewell")
async def farewell(
    xp_earned: int = 0,
    activities: str = "",
    was_promoted: bool = False,
):
    user = _require_user()
    sensei = get_sensei()
    belt = BELTS[user.belt_rank] if user.belt_rank < len(BELTS) else BELTS[-1]

    try:
        message = sensei.farewell(
            name=user.name,
            xp_earned=xp_earned,
            activities=activities,
            belt_name=belt["name"],
            belt_icon=belt["icon"],
            was_promoted=was_promoted,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to generate farewell: {e}")

    return {"farewell": message}
