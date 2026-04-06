"""PyTorch Knowledge Tracer for adaptive Sensei context.

Predicts per-skill mastery, learning velocity, and recommended difficulty
from the student's interaction history.  Output is injected as qualitative
hints into Claude's system prompt.
"""

import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import torch
import torch.nn as nn
import torch.optim as optim

from codedojo.progress import Progress

# ── Constants ──────────────────────────────────────────────────────────

FEATURE_DIM = 9
HIDDEN1 = 32
HIDDEN2 = 16
OUTPUT_DIM = 3  # mastery, velocity, difficulty

EMA_ALPHA = 0.3
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-4
TRAIN_STEPS_PER_EVENT = 5
RETRAIN_EPOCHS = 10

CONFIDENCE_MIN_EVENTS = 3
CONFIDENCE_FULL_EVENTS = 10

BELT_ORDER = ["white", "yellow", "orange", "green", "blue", "purple", "brown", "black"]


# ── Event Log Parsing ──────────────────────────────────────────────────


@dataclass
class SkillEventHistory:
    """Per-skill chronological outcome history derived from session_log.jsonl."""

    outcomes: list[bool] = field(default_factory=list)
    timestamps: list[str] = field(default_factory=list)


def parse_event_log(log_path: Path) -> dict[str, SkillEventHistory]:
    """Parse session_log.jsonl into per-skill event histories.

    Correlates challenge_generated (challenge_id -> skill) with submission
    events (challenge_id -> verdict).  Disputes that overturn flip the
    most recent outcome for that challenge.
    """
    if not log_path.exists():
        return {}

    challenge_skill_map: dict[str, str] = {}
    histories: dict[str, SkillEventHistory] = {}
    last_submission_index: dict[str, tuple[str, int]] = {}

    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue

                event = data.get("event")
                timestamp = data.get("timestamp", "")

                if event == "challenge_generated":
                    cid = data.get("challenge_id", "")
                    skill = data.get("skill", "")
                    if cid and skill:
                        challenge_skill_map[cid] = skill

                elif event == "submission":
                    cid = data.get("challenge_id", "")
                    verdict = data.get("verdict", "")
                    skill = challenge_skill_map.get(cid)
                    if not skill or verdict == "unknown":
                        continue
                    passed = verdict == "pass"
                    hist = histories.setdefault(skill, SkillEventHistory())
                    hist.outcomes.append(passed)
                    hist.timestamps.append(timestamp)
                    last_submission_index[cid] = (skill, len(hist.outcomes) - 1)

                elif event == "submission_dispute":
                    cid = data.get("challenge_id", "")
                    overturned = data.get("overturned", False)
                    if overturned and cid in last_submission_index:
                        skill, idx = last_submission_index[cid]
                        if skill in histories and idx < len(histories[skill].outcomes):
                            histories[skill].outcomes[idx] = True
    except OSError:
        return {}

    return histories


# ── Feature Extraction ─────────────────────────────────────────────────


class FeatureExtractor:
    """Extracts a 9-dim feature vector per skill from Progress + event histories."""

    def __init__(
        self, progress: Progress, event_histories: dict[str, SkillEventHistory]
    ):
        self.progress = progress
        self.event_histories = event_histories

    def extract(self, skill: str) -> torch.Tensor:
        """Return a normalised feature vector for *skill*."""
        p = self.progress
        record = p.skills.get(skill)
        lesson = p.lesson_history.get(skill)
        hist = self.event_histories.get(skill)

        # 1. success_rate [0, 1]
        success_rate = (
            record.successes / record.attempts
            if record and record.attempts > 0
            else 0.0
        )

        # 2. attempt_count – log-normalised against an expected ceiling of ~50
        attempts = record.attempts if record else 0
        attempt_count = math.log1p(attempts) / math.log1p(50)

        # 3. days_since_practice – exponential decay with 30-day half-life
        if record and record.last_practiced:
            try:
                last_dt = datetime.fromisoformat(record.last_practiced)
                now = datetime.now(timezone.utc)
                days = max(0.0, (now - last_dt).total_seconds() / 86400)
            except (ValueError, TypeError):
                days = 365.0
        else:
            days = 365.0
        days_since_practice = 1.0 - math.exp(-days / 30.0)

        # 4. recent_trend – last-3 success rate minus overall rate
        if hist and len(hist.outcomes) >= 3:
            recent_rate = sum(hist.outcomes[-3:]) / 3.0
            overall_rate = sum(hist.outcomes) / len(hist.outcomes)
            recent_trend = max(-1.0, min(1.0, recent_rate - overall_rate))
        else:
            recent_trend = 0.0

        # 5. quiz_score [0, 1]
        quiz_score = 0.0
        if lesson and lesson.quiz_score:
            try:
                parts = lesson.quiz_score.split("/")
                quiz_score = int(parts[0]) / max(int(parts[1]), 1)
            except (ValueError, IndexError):
                pass

        # 6. has_weak_questions {0, 1}
        has_weak = 1.0 if (lesson and lesson.weak_questions) else 0.0

        # 7. streak_success [0, 1]
        streak_s = 0
        if hist:
            for outcome in reversed(hist.outcomes):
                if outcome:
                    streak_s += 1
                else:
                    break
        streak_success = min(streak_s, 5) / 5.0

        # 8. streak_failure [0, 1]
        streak_f = 0
        if hist:
            for outcome in reversed(hist.outcomes):
                if not outcome:
                    streak_f += 1
                else:
                    break
        streak_failure = min(streak_f, 5) / 5.0

        # 9. belt_level [0, 1]
        try:
            belt_idx = BELT_ORDER.index(p.belt)
        except ValueError:
            belt_idx = 0
        belt_level = belt_idx / max(len(BELT_ORDER) - 1, 1)

        return torch.tensor(
            [
                success_rate,
                attempt_count,
                days_since_practice,
                recent_trend,
                quiz_score,
                has_weak,
                streak_success,
                streak_failure,
                belt_level,
            ],
            dtype=torch.float32,
        )

    def extract_all(self) -> dict[str, torch.Tensor]:
        """Extract feature vectors for every taught skill."""
        return {skill: self.extract(skill) for skill in self.progress.skills_taught}


# ── MLP Model ─────────────────────────────────────────────────────────


class KnowledgeTracerMLP(nn.Module):
    """Maps a 9-dim per-skill feature vector to (mastery, velocity, difficulty)."""

    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(FEATURE_DIM, HIDDEN1)
        self.fc2 = nn.Linear(HIDDEN1, HIDDEN2)
        self.fc3 = nn.Linear(HIDDEN2, OUTPUT_DIM)
        self.relu = nn.ReLU()
        self._init_weights()

    def _init_weights(self):
        """Small weights so outputs start near neutral: mastery~0.5, velocity~0, difficulty~0.5."""
        for layer in (self.fc1, self.fc2):
            nn.init.xavier_uniform_(layer.weight, gain=0.1)
            nn.init.zeros_(layer.bias)
        nn.init.xavier_uniform_(self.fc3.weight, gain=0.1)
        nn.init.zeros_(self.fc3.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.relu(self.fc1(x))
        x = self.relu(self.fc2(x))
        raw = self.fc3(x)
        mastery = torch.sigmoid(raw[..., 0])
        velocity = torch.tanh(raw[..., 1])
        difficulty = torch.sigmoid(raw[..., 2])
        return torch.stack([mastery, velocity, difficulty], dim=-1)


# ── Per-Skill Training State ──────────────────────────────────────────


@dataclass
class SkillTrainingState:
    """Running EMA used to derive supervised targets for the MLP."""

    mastery_ema: float = 0.5
    prev_mastery_ema: float = 0.5
    event_count: int = 0


# ── Orchestrator ───────────────────────────────────────────────────────


class KnowledgeTracer:
    """High-level façade: feature extraction, training, inference, formatting."""

    def __init__(self, log_path: Path, model_path: Path):
        self.log_path = log_path
        self.model_path = model_path
        self.model = KnowledgeTracerMLP()
        self.optimizer = optim.Adam(
            self.model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY
        )
        self.training_states: dict[str, SkillTrainingState] = {}
        self.total_events: int = 0
        self.event_histories: dict[str, SkillEventHistory] = {}

    # ── Persistence ────────────────────────────────────────────────────

    def load(self) -> bool:
        """Load model checkpoint from disk.  Returns True on success."""
        if not self.model_path.exists():
            return False
        try:
            try:
                checkpoint = torch.load(self.model_path, weights_only=False)
            except TypeError:
                checkpoint = torch.load(self.model_path)
            self.model.load_state_dict(checkpoint["model_state_dict"])
            self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
            self.total_events = checkpoint.get("total_events", 0)
            for skill, sd in checkpoint.get("training_states", {}).items():
                self.training_states[skill] = SkillTrainingState(**sd)
            return True
        except (RuntimeError, KeyError, TypeError, EOFError):
            self.model = KnowledgeTracerMLP()
            self.optimizer = optim.Adam(
                self.model.parameters(), lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY
            )
            return False

    def save(self):
        """Persist model checkpoint to disk."""
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint = {
            "model_state_dict": self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "total_events": self.total_events,
            "training_states": {
                skill: {
                    "mastery_ema": s.mastery_ema,
                    "prev_mastery_ema": s.prev_mastery_ema,
                    "event_count": s.event_count,
                }
                for skill, s in self.training_states.items()
            },
        }
        torch.save(checkpoint, self.model_path)

    # ── Lifecycle ──────────────────────────────────────────────────────

    def initialize(self, progress: Progress):
        """Bootstrap: parse log, load or retrain model."""
        self.event_histories = parse_event_log(self.log_path)
        log_event_count = sum(len(h.outcomes) for h in self.event_histories.values())
        loaded = self.load()
        if not loaded or self.total_events != log_event_count:
            self.retrain_from_log(progress)

    # ── Training ───────────────────────────────────────────────────────

    def train_step(self, skill: str, passed: bool, progress: Progress):
        """Online update: a few SGD steps after a single submission."""
        hist = self.event_histories.setdefault(skill, SkillEventHistory())
        hist.outcomes.append(passed)
        hist.timestamps.append(datetime.now(timezone.utc).isoformat())

        state = self.training_states.setdefault(skill, SkillTrainingState())
        state.prev_mastery_ema = state.mastery_ema
        state.mastery_ema = (
            EMA_ALPHA * (1.0 if passed else 0.0)
            + (1 - EMA_ALPHA) * state.mastery_ema
        )
        state.event_count += 1
        self.total_events += 1

        velocity_target = state.mastery_ema - state.prev_mastery_ema
        difficulty_target = _difficulty_target(state.mastery_ema, velocity_target)
        targets = torch.tensor(
            [state.mastery_ema, velocity_target, difficulty_target],
            dtype=torch.float32,
        )

        extractor = FeatureExtractor(progress, self.event_histories)
        features = extractor.extract(skill)

        self.model.train()
        loss_fn = nn.MSELoss()
        for _ in range(TRAIN_STEPS_PER_EVENT):
            self.optimizer.zero_grad()
            loss = loss_fn(self.model(features), targets)
            loss.backward()
            self.optimizer.step()

    def retrain_from_log(self, progress: Progress):
        """Replay the entire event log and retrain from scratch."""
        self.event_histories = parse_event_log(self.log_path)
        self.training_states.clear()
        self.total_events = 0

        samples: list[tuple[str, list[float]]] = []
        for skill, hist in self.event_histories.items():
            state = SkillTrainingState()
            for outcome in hist.outcomes:
                state.prev_mastery_ema = state.mastery_ema
                state.mastery_ema = (
                    EMA_ALPHA * (1.0 if outcome else 0.0)
                    + (1 - EMA_ALPHA) * state.mastery_ema
                )
                state.event_count += 1
                self.total_events += 1
            velocity = state.mastery_ema - state.prev_mastery_ema
            difficulty = _difficulty_target(state.mastery_ema, velocity)
            samples.append((skill, [state.mastery_ema, velocity, difficulty]))
            self.training_states[skill] = state

        if not samples:
            return

        extractor = FeatureExtractor(progress, self.event_histories)
        self.model.train()
        loss_fn = nn.MSELoss()
        for _ in range(RETRAIN_EPOCHS):
            for skill, target_vals in samples:
                features = extractor.extract(skill)
                targets = torch.tensor(target_vals, dtype=torch.float32)
                self.optimizer.zero_grad()
                loss = loss_fn(self.model(features), targets)
                loss.backward()
                self.optimizer.step()

    # ── Inference ──────────────────────────────────────────────────────

    def predict(self, progress: Progress) -> dict[str, dict[str, float]]:
        """Run inference for all taught skills."""
        if not progress.skills_taught:
            return {}

        extractor = FeatureExtractor(progress, self.event_histories)
        self.model.eval()
        results: dict[str, dict[str, float]] = {}

        with torch.no_grad():
            for skill in progress.skills_taught:
                out = self.model(extractor.extract(skill))
                results[skill] = {
                    "mastery": out[0].item(),
                    "velocity": out[1].item(),
                    "difficulty": out[2].item(),
                }
        return results

    # ── Formatting ─────────────────────────────────────────────────────

    def format_block(self, progress: Progress) -> str:
        """Qualitative text block for Claude's system prompt.

        Returns an empty string when below the confidence threshold
        (< CONFIDENCE_MIN_EVENTS total submissions).
        """
        if self.total_events < CONFIDENCE_MIN_EVENTS:
            return ""

        predictions = self.predict(progress)
        if not predictions:
            return ""

        is_early = self.total_events < CONFIDENCE_FULL_EVENTS

        lines: list[str] = ["Knowledge Tracer Assessment:"]
        if is_early:
            lines.append("(Early assessment — limited interaction data)")

        for skill, pred in predictions.items():
            m, v, d = pred["mastery"], pred["velocity"], pred["difficulty"]
            lines.append(
                f"- {skill}: Mastery {_mastery_label(m)}, {_velocity_label(v)}. "
                f"{_difficulty_hint(m, v)}"
            )

        avg_velocity = (
            sum(p["velocity"] for p in predictions.values()) / len(predictions)
            if predictions
            else 0.0
        )
        lines.append(f"Overall learning pace: {_pace_label(avg_velocity)}.")

        weakest = min(predictions.items(), key=lambda kv: kv[1]["mastery"])
        wname, wpred = weakest
        if wpred["mastery"] < 0.4:
            lines.append(
                f'Recommendation: Reinforce "{wname}" before advancing to new material.'
            )
        elif wpred["velocity"] < -0.15:
            lines.append(
                f'Recommendation: Student may be losing confidence in "{wname}" — '
                "consider a simpler challenge to rebuild momentum."
            )

        return "\n".join(lines)


# ── Pure helpers (module-level) ────────────────────────────────────────


def _difficulty_target(mastery: float, velocity: float) -> float:
    return max(0.1, min(0.9, mastery * 0.7 + 0.15 + velocity * 0.15))


def _mastery_label(mastery: float) -> str:
    if mastery > 0.75:
        return "high"
    if mastery >= 0.4:
        return "moderate"
    return "low"


def _velocity_label(velocity: float) -> str:
    if velocity > 0.15:
        return "improving"
    if velocity < -0.15:
        return "declining"
    return "stable"


def _difficulty_hint(mastery: float, velocity: float) -> str:
    if mastery > 0.75 and velocity >= -0.15:
        return "Student is confident here — increase complexity."
    if mastery < 0.4 or velocity < -0.15:
        return "Student may need reinforcement — simplify next challenge."
    if velocity > 0.15:
        return "Student is gaining momentum — maintain current level."
    return "Maintain current difficulty level."


def _pace_label(avg_velocity: float) -> str:
    if avg_velocity > 0.15:
        return "Accelerating — student is picking up speed"
    if avg_velocity < -0.15:
        return "Slowing down — student may benefit from review"
    return "Steady — student is progressing at a consistent pace"
