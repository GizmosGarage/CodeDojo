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

FEATURE_DIM = 15
EMBED_DIM = 16
SEQ_EVENT_DIM = 12  # features per event in the sequence
SEQ_HIDDEN = 16     # GRU hidden size
MAX_SEQ_LEN = 20    # look at last 20 global events
COMBINED_DIM = FEATURE_DIM + EMBED_DIM + SEQ_HIDDEN  # 15 + 16 + 16 = 47
HIDDEN1 = 32
HIDDEN2 = 16
OUTPUT_DIM = 1  # P(pass next challenge)

LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-4
TRAIN_STEPS_PER_EVENT = 5
RETRAIN_EPOCHS = 10

CONFIDENCE_MIN_EVENTS = 3
CONFIDENCE_FULL_EVENTS = 10

BELT_ORDER = ["white", "yellow", "orange", "green", "blue", "purple", "brown", "black"]

SEVERITY_SCORE = {"minor": 0.33, "moderate": 0.67, "major": 1.0}
UNDERSTANDING_SCORE = {"none": 0.0, "partial": 0.5, "full": 1.0}
CODE_QUALITY_SCORE = {"poor": 0.0, "adequate": 0.5, "good": 1.0}


# ── Event Log Parsing ──────────────────────────────────────────────────


@dataclass
class SkillEventHistory:
    """Per-skill chronological event history derived from session_log.jsonl."""

    outcomes: list[bool] = field(default_factory=list)
    timestamps: list[str] = field(default_factory=list)
    severities: list[str | None] = field(default_factory=list)
    attempt_numbers: list[int] = field(default_factory=list)
    missing_concepts: list[list[str]] = field(default_factory=list)
    forbidden_concepts: list[list[str]] = field(default_factory=list)
    timed_out: list[bool] = field(default_factory=list)
    code_lines: list[int] = field(default_factory=list)
    understanding: list[str] = field(default_factory=list)
    code_quality: list[str] = field(default_factory=list)
    struggle_concepts: list[list[str]] = field(default_factory=list)
    approach: list[str] = field(default_factory=list)


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
                    hist.severities.append(data.get("severity"))
                    hist.attempt_numbers.append(data.get("attempt_number", 1))
                    hist.missing_concepts.append(data.get("missing_concepts", []))
                    hist.forbidden_concepts.append(data.get("forbidden_concepts", []))
                    hist.timed_out.append(data.get("timed_out", False))
                    hist.code_lines.append(data.get("code_lines", 0))
                    hist.understanding.append(data.get("understanding", "partial"))
                    hist.code_quality.append(data.get("code_quality", "adequate"))
                    hist.struggle_concepts.append(data.get("struggle_concepts", []))
                    hist.approach.append(data.get("approach", "standard"))
                    last_submission_index[cid] = (skill, len(hist.outcomes) - 1)

                elif event == "submission_dispute":
                    cid = data.get("challenge_id", "")
                    overturned = data.get("overturned", False)
                    if overturned and cid in last_submission_index:
                        skill, idx = last_submission_index[cid]
                        if skill in histories and idx < len(histories[skill].outcomes):
                            histories[skill].outcomes[idx] = True
                            histories[skill].severities[idx] = None
                            histories[skill].understanding[idx] = "full"
    except OSError:
        return {}

    return histories


def _build_global_timeline(
    histories: dict[str, SkillEventHistory],
) -> list[dict]:
    """Merge per-skill histories into a global chronological event list."""
    events: list[dict] = []
    for skill, hist in histories.items():
        for i in range(len(hist.outcomes)):
            events.append({
                "skill": skill,
                "outcome": hist.outcomes[i],
                "timestamp": hist.timestamps[i],
                "severity": hist.severities[i],
                "attempt_number": hist.attempt_numbers[i],
                "timed_out": hist.timed_out[i],
                "had_missing": bool(hist.missing_concepts[i]),
                "had_forbidden": bool(hist.forbidden_concepts[i]),
                "understanding": hist.understanding[i] if i < len(hist.understanding) else "partial",
                "code_quality": hist.code_quality[i] if i < len(hist.code_quality) else "adequate",
                "had_struggle": bool(hist.struggle_concepts[i]) if i < len(hist.struggle_concepts) else False,
                "approach": hist.approach[i] if i < len(hist.approach) else "standard",
            })
    events.sort(key=lambda e: e["timestamp"])
    return events


# ── Feature Extraction ─────────────────────────────────────────────────


class FeatureExtractor:
    """Extracts a 15-dim feature vector per skill from Progress + event histories."""

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

        # 10. avg_severity [0, 1] — mean severity score of recent failures
        if hist and hist.severities:
            recent_sevs = hist.severities[-5:]
            sev_scores = [SEVERITY_SCORE.get(s, 0.0) for s in recent_sevs if s is not None]
            avg_severity = sum(sev_scores) / len(sev_scores) if sev_scores else 0.0
        else:
            avg_severity = 0.0

        # 11. worst_recent_severity [0, 1] — worst severity in last 3 events
        if hist and hist.severities:
            recent_sevs = hist.severities[-3:]
            sev_scores = [SEVERITY_SCORE.get(s, 0.0) for s in recent_sevs if s is not None]
            worst_recent_severity = max(sev_scores) if sev_scores else 0.0
        else:
            worst_recent_severity = 0.0

        # 12. avg_attempt_count [0, ~1] — log-normalised avg attempts per challenge
        if hist and hist.attempt_numbers:
            recent_attempts = hist.attempt_numbers[-5:]
            raw_avg = sum(recent_attempts) / len(recent_attempts)
            avg_attempt_count = math.log1p(raw_avg) / math.log1p(10)
        else:
            avg_attempt_count = 0.0

        # 13. missing_concept_rate [0, 1] — fraction of recent subs with missing concepts
        if hist and hist.missing_concepts:
            recent_missing = hist.missing_concepts[-5:]
            missing_concept_rate = sum(1 for m in recent_missing if m) / len(recent_missing)
        else:
            missing_concept_rate = 0.0

        # 14. forbidden_concept_rate [0, 1] — fraction of recent subs using forbidden concepts
        if hist and hist.forbidden_concepts:
            recent_forbidden = hist.forbidden_concepts[-5:]
            forbidden_concept_rate = sum(1 for f in recent_forbidden if f) / len(recent_forbidden)
        else:
            forbidden_concept_rate = 0.0

        # 15. timeout_rate [0, 1] — fraction of recent submissions that timed out
        if hist and hist.timed_out:
            recent_timeouts = hist.timed_out[-5:]
            timeout_rate = sum(recent_timeouts) / len(recent_timeouts)
        else:
            timeout_rate = 0.0

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
                avg_severity,
                worst_recent_severity,
                avg_attempt_count,
                missing_concept_rate,
                forbidden_concept_rate,
                timeout_rate,
            ],
            dtype=torch.float32,
        )

    def extract_all(self) -> dict[str, torch.Tensor]:
        """Extract feature vectors for every taught skill."""
        return {skill: self.extract(skill) for skill in self.progress.skills_taught}


# ── Student Encoder ───────────────────────────────────────────────────


class StudentEncoder(nn.Module):
    """Aggregates per-skill features into a fixed-size student embedding."""

    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(FEATURE_DIM, EMBED_DIM)
        self.fc2 = nn.Linear(EMBED_DIM, EMBED_DIM)
        self.relu = nn.ReLU()
        self._init_weights()

    def _init_weights(self):
        for layer in (self.fc1, self.fc2):
            nn.init.xavier_uniform_(layer.weight, gain=0.1)
            nn.init.zeros_(layer.bias)

    def forward(self, skill_features: torch.Tensor) -> torch.Tensor:
        """Input: (N, 15) stacked per-skill features. Output: (EMBED_DIM,) embedding."""
        pooled = skill_features.mean(dim=0)  # (15,) — mean across skills
        x = self.relu(self.fc1(pooled))
        return torch.tanh(self.fc2(x))  # bounded [-1, 1]


# ── Sequence Encoder ──────────────────────────────────────────────────


class SequenceEncoder(nn.Module):
    """GRU that processes the global event timeline into a sequence context vector."""

    def __init__(self):
        super().__init__()
        self.gru = nn.GRU(
            input_size=SEQ_EVENT_DIM,
            hidden_size=SEQ_HIDDEN,
            num_layers=1,
            batch_first=True,
        )
        self._init_weights()

    def _init_weights(self):
        for name, param in self.gru.named_parameters():
            if "weight" in name:
                nn.init.xavier_uniform_(param, gain=0.1)
            elif "bias" in name:
                nn.init.zeros_(param)

    def forward(self, event_features: torch.Tensor) -> torch.Tensor:
        """Input: (seq_len, SEQ_EVENT_DIM). Output: (SEQ_HIDDEN,) context vector."""
        x = event_features.unsqueeze(0)  # (1, seq_len, 8)
        _, hidden = self.gru(x)  # hidden: (1, 1, SEQ_HIDDEN)
        return hidden.squeeze(0).squeeze(0)  # (SEQ_HIDDEN,)


# ── MLP Model ─────────────────────────────────────────────────────────


class KnowledgeTracerMLP(nn.Module):
    """Maps per-skill features + student embedding + sequence context to P(pass)."""

    def __init__(self):
        super().__init__()
        self.fc1 = nn.Linear(COMBINED_DIM, HIDDEN1)
        self.fc2 = nn.Linear(HIDDEN1, HIDDEN2)
        self.fc3 = nn.Linear(HIDDEN2, OUTPUT_DIM)
        self.relu = nn.ReLU()
        self._init_weights()

    def _init_weights(self):
        """Small weights so output starts near 0.5 (neutral prediction)."""
        for layer in (self.fc1, self.fc2):
            nn.init.xavier_uniform_(layer.weight, gain=0.1)
            nn.init.zeros_(layer.bias)
        nn.init.xavier_uniform_(self.fc3.weight, gain=0.1)
        nn.init.zeros_(self.fc3.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.relu(self.fc1(x))
        x = self.relu(self.fc2(x))
        return torch.sigmoid(self.fc3(x)).squeeze(-1)


# ── Per-Skill Training State ──────────────────────────────────────────


@dataclass
class SkillTrainingState:
    """Tracks the model's consecutive predictions for velocity computation."""

    last_prediction: float = 0.5   # Most recent P(pass) prediction
    prev_prediction: float = 0.5   # Previous P(pass) for velocity delta
    event_count: int = 0


# ── Orchestrator ───────────────────────────────────────────────────────


class KnowledgeTracer:
    """High-level façade: feature extraction, training, inference, formatting."""

    def __init__(self, log_path: Path, model_path: Path):
        self.log_path = log_path
        self.model_path = model_path
        self.model = KnowledgeTracerMLP()
        self.encoder = StudentEncoder()
        self.seq_encoder = SequenceEncoder()
        self.optimizer = optim.Adam(
            list(self.model.parameters())
            + list(self.encoder.parameters())
            + list(self.seq_encoder.parameters()),
            lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY,
        )
        self.training_states: dict[str, SkillTrainingState] = {}
        self.total_events: int = 0
        self.event_histories: dict[str, SkillEventHistory] = {}

    # ── Persistence ────────────────────────────────────────────────────

    def load(self) -> bool:
        """Load model checkpoint from disk.  Returns True on success.

        Detects old 3-output format and triggers retrain by returning False.
        """
        if not self.model_path.exists():
            return False
        try:
            try:
                checkpoint = torch.load(self.model_path, weights_only=False)
            except TypeError:
                checkpoint = torch.load(self.model_path)

            # Detect old model dimensions — cannot load, trigger retrain
            old_fc3 = checkpoint["model_state_dict"].get("fc3.weight")
            if old_fc3 is not None and old_fc3.shape[0] != OUTPUT_DIM:
                return False
            old_fc1 = checkpoint["model_state_dict"].get("fc1.weight")
            if old_fc1 is not None and old_fc1.shape[1] != COMBINED_DIM:
                return False

            # Require encoder states — old checkpoints without them trigger retrain
            if "encoder_state_dict" not in checkpoint:
                return False
            if "seq_encoder_state_dict" not in checkpoint:
                return False

            # Detect old GRU input dimension (e.g. 8 before review meta expansion)
            old_gru_ih = checkpoint["seq_encoder_state_dict"].get("gru.weight_ih_l0")
            if old_gru_ih is not None and old_gru_ih.shape[1] != SEQ_EVENT_DIM:
                return False

            self.model.load_state_dict(checkpoint["model_state_dict"])
            self.encoder.load_state_dict(checkpoint["encoder_state_dict"])
            self.seq_encoder.load_state_dict(checkpoint["seq_encoder_state_dict"])
            self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
            self.total_events = checkpoint.get("total_events", 0)
            for skill, sd in checkpoint.get("training_states", {}).items():
                # Migrate old EMA-based state to prediction-based state
                if "mastery_ema" in sd:
                    self.training_states[skill] = SkillTrainingState(
                        last_prediction=sd["mastery_ema"],
                        prev_prediction=sd["prev_mastery_ema"],
                        event_count=sd["event_count"],
                    )
                else:
                    self.training_states[skill] = SkillTrainingState(**sd)
            return True
        except (RuntimeError, KeyError, TypeError, EOFError):
            self.model = KnowledgeTracerMLP()
            self.encoder = StudentEncoder()
            self.seq_encoder = SequenceEncoder()
            self.optimizer = optim.Adam(
                list(self.model.parameters())
                + list(self.encoder.parameters())
                + list(self.seq_encoder.parameters()),
                lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY,
            )
            return False

    def save(self):
        """Persist model checkpoint to disk."""
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        checkpoint = {
            "model_state_dict": self.model.state_dict(),
            "encoder_state_dict": self.encoder.state_dict(),
            "seq_encoder_state_dict": self.seq_encoder.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "total_events": self.total_events,
            "training_states": {
                skill: {
                    "last_prediction": s.last_prediction,
                    "prev_prediction": s.prev_prediction,
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

    # ── Combined Input ────────────────────────────────────────────────

    @staticmethod
    def _encode_timeline_events(
        timeline: list[dict], target_skill: str,
    ) -> torch.Tensor:
        """Encode the last MAX_SEQ_LEN events into (seq_len, SEQ_EVENT_DIM) tensor."""
        recent = timeline[-MAX_SEQ_LEN:]
        if not recent:
            return torch.zeros(1, SEQ_EVENT_DIM)

        rows: list[list[float]] = []
        prev_ts: str | None = None
        for ev in recent:
            sev = SEVERITY_SCORE.get(ev["severity"], 0.0) if ev["severity"] else 0.0
            attempt = min(1.0, math.log1p(ev["attempt_number"]) / math.log1p(10))

            # Time delta from previous event (hour-scale exponential decay)
            time_delta = 0.5  # neutral default
            if prev_ts and ev["timestamp"]:
                try:
                    dt = datetime.fromisoformat(ev["timestamp"])
                    pt = datetime.fromisoformat(prev_ts)
                    secs = max(0.0, (dt - pt).total_seconds())
                    time_delta = 1.0 - math.exp(-secs / 3600.0)
                except (ValueError, TypeError):
                    pass

            rows.append([
                1.0 if ev["outcome"] else 0.0,
                sev,
                attempt,
                1.0 if ev["timed_out"] else 0.0,
                1.0 if ev["had_missing"] else 0.0,
                1.0 if ev["had_forbidden"] else 0.0,
                time_delta,
                1.0 if ev["skill"] == target_skill else 0.0,
                UNDERSTANDING_SCORE.get(ev.get("understanding", "partial"), 0.5),
                CODE_QUALITY_SCORE.get(ev.get("code_quality", "adequate"), 0.5),
                1.0 if ev.get("had_struggle", False) else 0.0,
                1.0 if ev.get("approach") == "creative" else 0.0,
            ])
            prev_ts = ev["timestamp"]

        return torch.tensor(rows, dtype=torch.float32)  # (seq_len, 12)

    def _build_combined_input(
        self, skill: str, extractor: FeatureExtractor
    ) -> torch.Tensor:
        """Return (COMBINED_DIM,) tensor: per-skill features + student embedding + sequence context."""
        skill_features = extractor.extract(skill)
        all_features = extractor.extract_all()
        if all_features:
            stacked = torch.stack(list(all_features.values()))  # (N, 15)
            embedding = self.encoder(stacked)  # (EMBED_DIM,)
        else:
            embedding = torch.zeros(EMBED_DIM)

        # Sequence context from global timeline
        timeline = _build_global_timeline(extractor.event_histories)
        if timeline:
            event_feats = self._encode_timeline_events(timeline, skill)
            seq_context = self.seq_encoder(event_feats)  # (SEQ_HIDDEN,)
        else:
            seq_context = torch.zeros(SEQ_HIDDEN)

        return torch.cat([skill_features, embedding, seq_context])  # (COMBINED_DIM,)

    # ── Training ───────────────────────────────────────────────────────

    def train_step(
        self,
        skill: str,
        passed: bool,
        progress: Progress,
        *,
        severity: str | None = None,
        attempt_number: int = 1,
        missing_concepts: list[str] | None = None,
        forbidden_concepts: list[str] | None = None,
        timed_out: bool = False,
        code_lines: int = 0,
        understanding: str = "partial",
        code_quality: str = "adequate",
        struggle_concepts: list[str] | None = None,
        approach: str = "standard",
    ):
        """Online update: predict P(pass) before seeing outcome, then train on reality."""
        # 1. Extract features BEFORE appending this outcome to event history
        extractor = FeatureExtractor(progress, self.event_histories)
        combined = self._build_combined_input(skill, extractor)

        # 2. Record the model's pre-outcome prediction
        self.model.eval()
        self.encoder.eval()
        self.seq_encoder.eval()
        with torch.no_grad():
            p_pass = self.model(combined).item()

        # 3. NOW append the actual outcome and metadata to history
        hist = self.event_histories.setdefault(skill, SkillEventHistory())
        hist.outcomes.append(passed)
        hist.timestamps.append(datetime.now(timezone.utc).isoformat())
        hist.severities.append(severity)
        hist.attempt_numbers.append(attempt_number)
        hist.missing_concepts.append(missing_concepts or [])
        hist.forbidden_concepts.append(forbidden_concepts or [])
        hist.timed_out.append(timed_out)
        hist.code_lines.append(code_lines)
        hist.understanding.append(understanding)
        hist.code_quality.append(code_quality)
        hist.struggle_concepts.append(struggle_concepts or [])
        hist.approach.append(approach)

        # 4. Update tracking state
        state = self.training_states.setdefault(skill, SkillTrainingState())
        state.prev_prediction = state.last_prediction
        state.last_prediction = p_pass
        state.event_count += 1
        self.total_events += 1

        # 5. Train on the actual outcome (BCE loss)
        target = torch.tensor(1.0 if passed else 0.0)
        self.model.train()
        self.encoder.train()
        self.seq_encoder.train()
        loss_fn = nn.BCELoss()
        for _ in range(TRAIN_STEPS_PER_EVENT):
            # Recompute combined input each step so encoder gradients flow
            combined = self._build_combined_input(skill, extractor)
            self.optimizer.zero_grad()
            loss = loss_fn(self.model(combined), target)
            loss.backward()
            self.optimizer.step()

    def retrain_from_log(self, progress: Progress):
        """Replay the entire event log and retrain from scratch.

        Creates one training sample per historical event: features extracted
        from the state *before* the outcome, label = actual outcome.
        """
        self.event_histories = parse_event_log(self.log_path)
        self.training_states.clear()
        self.total_events = 0

        # Build per-event training samples:
        #   (skill_features, all_skill_features, seq_events, label)
        # We store detached inputs so encoders get fresh gradients each epoch.
        samples: list[tuple[torch.Tensor, torch.Tensor, torch.Tensor, float]] = []
        for skill, hist in self.event_histories.items():
            state = SkillTrainingState()
            for i, outcome in enumerate(hist.outcomes):
                # Build a view of history up to (but not including) this event
                snapshot = dict(self.event_histories)
                snapshot[skill] = SkillEventHistory(
                    outcomes=hist.outcomes[:i],
                    timestamps=hist.timestamps[:i],
                    severities=hist.severities[:i],
                    attempt_numbers=hist.attempt_numbers[:i],
                    missing_concepts=hist.missing_concepts[:i],
                    forbidden_concepts=hist.forbidden_concepts[:i],
                    timed_out=hist.timed_out[:i],
                    code_lines=hist.code_lines[:i],
                    understanding=hist.understanding[:i],
                    code_quality=hist.code_quality[:i],
                    struggle_concepts=hist.struggle_concepts[:i],
                    approach=hist.approach[:i],
                )
                extractor = FeatureExtractor(progress, snapshot)
                skill_feats = extractor.extract(skill).detach()
                all_feats = extractor.extract_all()
                if all_feats:
                    stacked = torch.stack(list(all_feats.values())).detach()
                else:
                    stacked = skill_feats.unsqueeze(0).detach()
                timeline = _build_global_timeline(snapshot)
                seq_events = self._encode_timeline_events(timeline, skill).detach()
                samples.append((skill_feats, stacked, seq_events, 1.0 if outcome else 0.0))

                state.event_count += 1
                self.total_events += 1

            # Record final prediction for velocity tracking
            if hist.outcomes:
                self.model.eval()
                self.encoder.eval()
                self.seq_encoder.eval()
                with torch.no_grad():
                    extractor = FeatureExtractor(progress, self.event_histories)
                    combined = self._build_combined_input(skill, extractor)
                    pred = self.model(combined).item()
                state.last_prediction = pred
                state.prev_prediction = pred
            self.training_states[skill] = state

        if not samples:
            return

        self.model.train()
        self.encoder.train()
        self.seq_encoder.train()
        loss_fn = nn.BCELoss()
        for _ in range(RETRAIN_EPOCHS):
            for skill_feats, all_stacked, seq_events, label in samples:
                embedding = self.encoder(all_stacked)
                seq_context = self.seq_encoder(seq_events)
                combined = torch.cat([skill_feats, embedding, seq_context])
                target = torch.tensor(label)
                self.optimizer.zero_grad()
                loss = loss_fn(self.model(combined), target)
                loss.backward()
                self.optimizer.step()

    # ── Inference ──────────────────────────────────────────────────────

    def predict(self, progress: Progress) -> dict[str, dict[str, float]]:
        """Run inference for all taught skills.

        mastery = model's P(pass) prediction (learned, not copied).
        velocity = change between consecutive predictions.
        difficulty = derived from mastery + velocity.
        """
        if not progress.skills_taught:
            return {}

        extractor = FeatureExtractor(progress, self.event_histories)
        self.model.eval()
        self.encoder.eval()
        self.seq_encoder.eval()
        results: dict[str, dict[str, float]] = {}

        with torch.no_grad():
            for skill in progress.skills_taught:
                combined = self._build_combined_input(skill, extractor)
                p_pass = self.model(combined).item()
                state = self.training_states.get(skill, SkillTrainingState())
                velocity = (
                    p_pass - state.prev_prediction
                    if state.event_count > 1
                    else 0.0
                )
                difficulty = _difficulty_target(p_pass, velocity)
                results[skill] = {
                    "mastery": p_pass,
                    "velocity": velocity,
                    "difficulty": difficulty,
                }
        return results

    # ── Learner Profile ──────────────────────────────────────────────

    def _compute_learner_profile(self) -> dict[str, str]:
        """Derive interpretable learner traits from aggregate event histories."""
        all_outcomes: list[bool] = []
        per_skill_rates: list[float] = []
        post_failure_outcomes: list[bool] = []
        total_severities: dict[str, int] = {"minor": 0, "moderate": 0, "major": 0}
        total_timeouts = 0
        total_forbidden = 0
        total_failures = 0
        all_attempt_numbers: list[int] = []

        for hist in self.event_histories.values():
            all_outcomes.extend(hist.outcomes)
            if hist.outcomes:
                per_skill_rates.append(sum(hist.outcomes) / len(hist.outcomes))
            for i, outcome in enumerate(hist.outcomes):
                if not outcome:
                    total_failures += 1
                    # Track post-failure recovery (next 3 events after failure)
                    for j in range(i + 1, min(i + 4, len(hist.outcomes))):
                        post_failure_outcomes.append(hist.outcomes[j])
            for s in hist.severities:
                if s in total_severities:
                    total_severities[s] += 1
            total_timeouts += sum(hist.timed_out)
            total_forbidden += sum(1 for f in hist.forbidden_concepts if f)
            all_attempt_numbers.extend(hist.attempt_numbers)

        profile: dict[str, str] = {}
        n = len(all_outcomes)
        if n < CONFIDENCE_FULL_EVENTS:
            return profile

        # Learning pace: compare first 30% vs last 30% pass rates
        split = max(1, int(n * 0.3))
        early_rate = sum(all_outcomes[:split]) / split
        late_rate = sum(all_outcomes[-split:]) / split
        delta = late_rate - early_rate
        if delta > 0.15:
            profile["learning_pace"] = "accelerating"
        elif delta < -0.15:
            profile["learning_pace"] = "slowing"
        else:
            profile["learning_pace"] = "steady"

        # Consistency across skills
        if len(per_skill_rates) >= 2:
            mean_rate = sum(per_skill_rates) / len(per_skill_rates)
            variance = sum((r - mean_rate) ** 2 for r in per_skill_rates) / len(per_skill_rates)
            std = variance ** 0.5
            if std < 0.15:
                profile["consistency"] = "consistent across skills"
            elif std < 0.3:
                profile["consistency"] = "mixed across skills"
            else:
                profile["consistency"] = "uneven across skills"

        # Resilience: pass rate in events following a failure
        if len(post_failure_outcomes) >= 3:
            recovery_rate = sum(post_failure_outcomes) / len(post_failure_outcomes)
            if recovery_rate > 0.6:
                profile["resilience"] = "bounces back quickly"
            elif recovery_rate > 0.35:
                profile["resilience"] = "needs encouragement after setbacks"
            else:
                profile["resilience"] = "tends to struggle after failures"

        # Error pattern: dominant failure type
        if total_failures >= 3:
            major_rate = total_severities["major"] / total_failures
            timeout_rate = total_timeouts / total_failures
            forbidden_rate = total_forbidden / total_failures
            if timeout_rate > 0.3:
                profile["error_pattern"] = "rushes (frequent timeouts)"
            elif major_rate > 0.5:
                profile["error_pattern"] = "makes conceptual errors"
            elif forbidden_rate > 0.3:
                profile["error_pattern"] = "tends to use concepts not yet taught"
            elif total_severities["minor"] / total_failures > 0.5:
                profile["error_pattern"] = "tends toward minor mistakes"

        # Attempt efficiency
        if all_attempt_numbers:
            avg_attempts = sum(all_attempt_numbers) / len(all_attempt_numbers)
            if avg_attempts <= 1.3:
                profile["attempt_style"] = "efficient (usually gets it first try)"
            elif avg_attempts <= 2.5:
                profile["attempt_style"] = "persistent (takes a few attempts)"
            else:
                profile["attempt_style"] = "thorough (explores multiple approaches)"

        return profile

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

        # Learner profile (only after enough data)
        profile = self._compute_learner_profile()
        if profile:
            lines.append("")
            lines.append("Learner Profile:")
            trait_labels = {
                "learning_pace": "Learning pace",
                "consistency": "Consistency",
                "resilience": "After setbacks",
                "error_pattern": "Error tendency",
                "attempt_style": "Approach",
            }
            for key, label in trait_labels.items():
                if key in profile:
                    lines.append(f"- {label}: {profile[key]}")

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
