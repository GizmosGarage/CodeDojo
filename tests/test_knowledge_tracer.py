import json
from pathlib import Path

import torch

from codedojo.ai_engine import build_system_blocks
from codedojo.knowledge_tracer import (
    COMBINED_DIM,
    CONFIDENCE_FULL_EVENTS,
    CONFIDENCE_MIN_EVENTS,
    EMBED_DIM,
    FEATURE_DIM,
    MAX_SEQ_LEN,
    SEQ_EVENT_DIM,
    SEQ_HIDDEN,
    FeatureExtractor,
    KnowledgeTracer,
    KnowledgeTracerMLP,
    SequenceEncoder,
    SkillEventHistory,
    StudentEncoder,
    _build_global_timeline,
    parse_event_log,
)
from codedojo.ai_engine import parse_review_meta
from codedojo.progress import Progress


def test_format_block_empty_when_few_events(tmp_path: Path):
    log_path = tmp_path / "session_log.jsonl"
    model_path = tmp_path / "knowledge_model.pt"
    tracer = KnowledgeTracer(log_path, model_path)
    progress = Progress()
    progress.record_lesson("variables", 3, 3, [])
    tracer.total_events = CONFIDENCE_MIN_EVENTS - 1
    assert tracer.format_block(progress) == ""


def test_format_block_non_empty_after_threshold(tmp_path: Path):
    log_path = tmp_path / "session_log.jsonl"
    model_path = tmp_path / "knowledge_model.pt"
    tracer = KnowledgeTracer(log_path, model_path)
    progress = Progress()
    progress.record_lesson("variables", 3, 3, [])
    for _ in range(CONFIDENCE_MIN_EVENTS):
        tracer.train_step("variables", True, progress)
    text = tracer.format_block(progress)
    assert "Knowledge Tracer Assessment" in text
    assert "variables" in text
    assert tracer.total_events == CONFIDENCE_MIN_EVENTS


def test_format_block_early_assessment_preamble(tmp_path: Path):
    log_path = tmp_path / "session_log.jsonl"
    model_path = tmp_path / "knowledge_model.pt"
    tracer = KnowledgeTracer(log_path, model_path)
    progress = Progress()
    progress.record_lesson("variables", 3, 3, [])
    for _ in range(4):
        tracer.train_step("variables", True, progress)
    text = tracer.format_block(progress)
    assert "Early assessment" in text


def test_parse_event_log_correlates_challenge_and_submission(tmp_path: Path):
    log_path = tmp_path / "log.jsonl"
    lines = [
        {
            "event": "challenge_generated",
            "challenge_id": "cid1",
            "skill": "print() function",
            "timestamp": "2025-01-01T00:00:00Z",
        },
        {
            "event": "submission",
            "challenge_id": "cid1",
            "verdict": "pass",
            "timestamp": "2025-01-01T00:01:00Z",
        },
        {
            "event": "submission",
            "challenge_id": "cid1",
            "verdict": "needs_work",
            "timestamp": "2025-01-01T00:02:00Z",
        },
    ]
    log_path.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    hist = parse_event_log(log_path)
    assert "print() function" in hist
    assert hist["print() function"].outcomes == [True, False]


def test_parse_event_log_dispute_overturn(tmp_path: Path):
    log_path = tmp_path / "log.jsonl"
    lines = [
        {
            "event": "challenge_generated",
            "challenge_id": "x",
            "skill": "loops",
            "timestamp": "t0",
        },
        {
            "event": "submission",
            "challenge_id": "x",
            "verdict": "needs_work",
            "timestamp": "t1",
        },
        {
            "event": "submission_dispute",
            "challenge_id": "x",
            "overturned": True,
            "timestamp": "t2",
        },
    ]
    log_path.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    hist = parse_event_log(log_path)
    assert hist["loops"].outcomes == [True]


def test_save_load_roundtrip(tmp_path: Path):
    log_path = tmp_path / "session_log.jsonl"
    model_path = tmp_path / "knowledge_model.pt"
    t1 = KnowledgeTracer(log_path, model_path)
    progress = Progress()
    progress.record_lesson("a", 3, 3, [])
    t1.train_step("a", True, progress)
    t1.save()

    t2 = KnowledgeTracer(log_path, model_path)
    assert t2.load() is True
    assert t2.total_events == t1.total_events
    sd1 = t1.model.state_dict()
    sd2 = t2.model.state_dict()
    for k in sd1:
        assert torch.allclose(sd1[k], sd2[k])


def test_build_system_blocks_adds_tracer_when_provided():
    progress = Progress()
    progress.record_lesson("x", 3, 3, [])
    blocks = build_system_blocks(progress, tracer_block="Tracer hint line")
    assert len(blocks) == 3
    assert blocks[2]["text"] == "Tracer hint line"


def test_build_system_blocks_two_blocks_without_tracer():
    progress = Progress()
    blocks = build_system_blocks(progress)
    assert len(blocks) == 2


# --- New tests for predict-next-outcome training paradigm ---


def test_train_step_records_prediction_and_increments(tmp_path: Path):
    log_path = tmp_path / "session_log.jsonl"
    model_path = tmp_path / "knowledge_model.pt"
    tracer = KnowledgeTracer(log_path, model_path)
    progress = Progress()
    progress.record_lesson("variables", 3, 3, [])

    tracer.train_step("variables", True, progress)

    state = tracer.training_states["variables"]
    assert 0.0 <= state.last_prediction <= 1.0
    assert state.event_count == 1
    assert tracer.total_events == 1


def test_velocity_from_consecutive_predictions(tmp_path: Path):
    log_path = tmp_path / "session_log.jsonl"
    model_path = tmp_path / "knowledge_model.pt"
    tracer = KnowledgeTracer(log_path, model_path)
    progress = Progress()
    progress.record_lesson("variables", 3, 3, [])

    # Two train steps to establish prev_prediction and last_prediction
    tracer.train_step("variables", True, progress)
    tracer.train_step("variables", True, progress)

    predictions = tracer.predict(progress)
    assert "variables" in predictions
    # Velocity should exist and be a number (may be positive or negative)
    assert isinstance(predictions["variables"]["velocity"], float)


def test_model_learns_from_consistent_outcomes(tmp_path: Path):
    """After consistent passes, P(pass) should be higher than after consistent fails."""
    log_path = tmp_path / "session_log.jsonl"
    model_path = tmp_path / "knowledge_model.pt"

    tracer = KnowledgeTracer(log_path, model_path)
    progress = Progress()
    progress.record_lesson("skill_a", 3, 3, [])
    progress.record_lesson("skill_b", 3, 3, [])

    # Train skill_a with all passes, skill_b with all fails
    for _ in range(20):
        tracer.train_step("skill_a", True, progress)
        tracer.train_step("skill_b", False, progress)

    predictions = tracer.predict(progress)
    assert predictions["skill_a"]["mastery"] > predictions["skill_b"]["mastery"]


def test_predict_returns_difficulty_in_range(tmp_path: Path):
    log_path = tmp_path / "session_log.jsonl"
    model_path = tmp_path / "knowledge_model.pt"
    tracer = KnowledgeTracer(log_path, model_path)
    progress = Progress()
    progress.record_lesson("variables", 3, 3, [])

    for _ in range(5):
        tracer.train_step("variables", True, progress)

    predictions = tracer.predict(progress)
    d = predictions["variables"]["difficulty"]
    assert 0.1 <= d <= 0.9


def test_retrain_from_log_matches_event_count(tmp_path: Path):
    log_path = tmp_path / "log.jsonl"
    model_path = tmp_path / "knowledge_model.pt"

    lines = []
    for i in range(5):
        lines.append({
            "event": "challenge_generated",
            "challenge_id": f"c{i}",
            "skill": "print() function",
            "timestamp": f"2025-01-01T00:0{i}:00Z",
        })
        lines.append({
            "event": "submission",
            "challenge_id": f"c{i}",
            "verdict": "pass" if i % 2 == 0 else "needs_work",
            "timestamp": f"2025-01-01T00:0{i}:30Z",
        })
    log_path.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")

    tracer = KnowledgeTracer(log_path, model_path)
    progress = Progress()
    progress.record_lesson("print() function", 3, 3, [])
    tracer.retrain_from_log(progress)

    assert tracer.total_events == 5
    assert "print() function" in tracer.training_states


def test_old_checkpoint_triggers_retrain(tmp_path: Path):
    """An old 3-output checkpoint should fail to load, triggering retrain."""
    log_path = tmp_path / "session_log.jsonl"
    model_path = tmp_path / "knowledge_model.pt"

    # Create a fake old-format checkpoint with fc3 shape (3, 16)
    old_model_state = {
        "fc1.weight": torch.randn(32, 9),
        "fc1.bias": torch.zeros(32),
        "fc2.weight": torch.randn(16, 32),
        "fc2.bias": torch.zeros(16),
        "fc3.weight": torch.randn(3, 16),  # OLD: 3 outputs
        "fc3.bias": torch.zeros(3),
    }
    torch.save({
        "model_state_dict": old_model_state,
        "optimizer_state_dict": {},
        "total_events": 5,
        "training_states": {
            "variables": {
                "mastery_ema": 0.7,
                "prev_mastery_ema": 0.6,
                "event_count": 5,
            }
        },
    }, model_path)

    tracer = KnowledgeTracer(log_path, model_path)
    assert tracer.load() is False  # Old format rejected


# --- Step 2: Richer failure tracking tests ---


def test_parse_event_log_reads_enriched_fields(tmp_path: Path):
    log_path = tmp_path / "log.jsonl"
    lines = [
        {
            "event": "challenge_generated",
            "challenge_id": "c1",
            "skill": "variables",
            "timestamp": "t0",
        },
        {
            "event": "submission",
            "challenge_id": "c1",
            "verdict": "needs_work",
            "timestamp": "t1",
            "severity": "major",
            "attempt_number": 2,
            "missing_concepts": ["print()"],
            "forbidden_concepts": ["if/else"],
            "timed_out": True,
            "code_lines": 15,
        },
    ]
    log_path.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    hist = parse_event_log(log_path)

    assert hist["variables"].severities == ["major"]
    assert hist["variables"].attempt_numbers == [2]
    assert hist["variables"].missing_concepts == [["print()"]]
    assert hist["variables"].forbidden_concepts == [["if/else"]]
    assert hist["variables"].timed_out == [True]
    assert hist["variables"].code_lines == [15]


def test_parse_event_log_defaults_for_old_entries(tmp_path: Path):
    log_path = tmp_path / "log.jsonl"
    lines = [
        {
            "event": "challenge_generated",
            "challenge_id": "c1",
            "skill": "print() function",
            "timestamp": "t0",
        },
        {
            "event": "submission",
            "challenge_id": "c1",
            "verdict": "pass",
            "timestamp": "t1",
            # No enriched fields — old format
        },
    ]
    log_path.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    hist = parse_event_log(log_path)

    assert hist["print() function"].severities == [None]
    assert hist["print() function"].attempt_numbers == [1]
    assert hist["print() function"].missing_concepts == [[]]
    assert hist["print() function"].forbidden_concepts == [[]]
    assert hist["print() function"].timed_out == [False]
    assert hist["print() function"].code_lines == [0]


def test_feature_extractor_produces_15_dim():
    progress = Progress()
    progress.record_lesson("variables", 3, 3, [])
    hist = SkillEventHistory(
        outcomes=[True, False, True],
        timestamps=["t0", "t1", "t2"],
        severities=[None, "moderate", None],
        attempt_numbers=[1, 2, 1],
        missing_concepts=[[], ["print()"], []],
        forbidden_concepts=[[], [], ["if/else"]],
        timed_out=[False, False, True],
        code_lines=[5, 10, 8],
    )
    histories = {"variables": hist}
    extractor = FeatureExtractor(progress, histories)
    features = extractor.extract("variables")
    assert features.shape == (FEATURE_DIM,)
    assert FEATURE_DIM == 15
    # All features should be finite numbers
    assert torch.isfinite(features).all()


def test_train_step_with_metadata(tmp_path: Path):
    log_path = tmp_path / "session_log.jsonl"
    model_path = tmp_path / "knowledge_model.pt"
    tracer = KnowledgeTracer(log_path, model_path)
    progress = Progress()
    progress.record_lesson("variables", 3, 3, [])

    tracer.train_step(
        "variables", False, progress,
        severity="major",
        attempt_number=3,
        missing_concepts=["round()"],
        forbidden_concepts=["if/else"],
        timed_out=True,
        code_lines=20,
    )

    hist = tracer.event_histories["variables"]
    assert hist.severities == ["major"]
    assert hist.attempt_numbers == [3]
    assert hist.missing_concepts == [["round()"]]
    assert hist.forbidden_concepts == [["if/else"]]
    assert hist.timed_out == [True]
    assert hist.code_lines == [20]


def test_severity_features_reflect_data():
    progress = Progress()
    progress.record_lesson("variables", 3, 3, [])
    hist = SkillEventHistory(
        outcomes=[False, False, False],
        timestamps=["t0", "t1", "t2"],
        severities=["major", "major", "major"],
        attempt_numbers=[1, 2, 3],
        missing_concepts=[[], [], []],
        forbidden_concepts=[[], [], []],
        timed_out=[False, False, False],
        code_lines=[5, 5, 5],
    )
    histories = {"variables": hist}
    extractor = FeatureExtractor(progress, histories)
    features = extractor.extract("variables")

    # Feature indices: 9=avg_severity, 10=worst_recent_severity
    assert abs(features[9].item() - 1.0) < 0.01   # all major -> avg ~ 1.0
    assert abs(features[10].item() - 1.0) < 0.01  # worst recent = major -> 1.0

    # Now test with all minor
    hist2 = SkillEventHistory(
        outcomes=[False, False, False],
        timestamps=["t0", "t1", "t2"],
        severities=["minor", "minor", "minor"],
        attempt_numbers=[1, 1, 1],
        missing_concepts=[[], [], []],
        forbidden_concepts=[[], [], []],
        timed_out=[False, False, False],
        code_lines=[5, 5, 5],
    )
    histories2 = {"variables": hist2}
    extractor2 = FeatureExtractor(progress, histories2)
    features2 = extractor2.extract("variables")
    assert abs(features2[9].item() - 0.33) < 0.02  # all minor -> avg ~ 0.33


def test_old_9dim_checkpoint_triggers_retrain(tmp_path: Path):
    """A checkpoint with old 9-dim fc1 input should fail to load."""
    log_path = tmp_path / "session_log.jsonl"
    model_path = tmp_path / "knowledge_model.pt"

    old_model_state = {
        "fc1.weight": torch.randn(32, 9),   # OLD: 9-dim input
        "fc1.bias": torch.zeros(32),
        "fc2.weight": torch.randn(16, 32),
        "fc2.bias": torch.zeros(16),
        "fc3.weight": torch.randn(1, 16),   # Correct output dim
        "fc3.bias": torch.zeros(1),
    }
    torch.save({
        "model_state_dict": old_model_state,
        "optimizer_state_dict": {},
        "total_events": 5,
        "training_states": {},
    }, model_path)

    tracer = KnowledgeTracer(log_path, model_path)
    assert tracer.load() is False


def test_dispute_overturn_clears_severity(tmp_path: Path):
    log_path = tmp_path / "log.jsonl"
    lines = [
        {
            "event": "challenge_generated",
            "challenge_id": "x",
            "skill": "loops",
            "timestamp": "t0",
        },
        {
            "event": "submission",
            "challenge_id": "x",
            "verdict": "needs_work",
            "severity": "major",
            "attempt_number": 1,
            "timestamp": "t1",
        },
        {
            "event": "submission_dispute",
            "challenge_id": "x",
            "overturned": True,
            "timestamp": "t2",
        },
    ]
    log_path.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    hist = parse_event_log(log_path)

    assert hist["loops"].outcomes == [True]       # Flipped to pass
    assert hist["loops"].severities == [None]     # Severity cleared


# --- Step 3: Student embedding and learner profile tests ---


def test_student_encoder_output_shape():
    encoder = StudentEncoder()
    # 3 skills, each with 15-dim features
    skill_features = torch.randn(3, FEATURE_DIM)
    embedding = encoder(skill_features)
    assert embedding.shape == (EMBED_DIM,)
    # Tanh output: all values in [-1, 1]
    assert (embedding >= -1.0).all()
    assert (embedding <= 1.0).all()


def test_student_encoder_single_skill():
    encoder = StudentEncoder()
    skill_features = torch.randn(1, FEATURE_DIM)
    embedding = encoder(skill_features)
    assert embedding.shape == (EMBED_DIM,)


def test_combined_input_dimension(tmp_path: Path):
    log_path = tmp_path / "session_log.jsonl"
    model_path = tmp_path / "knowledge_model.pt"
    tracer = KnowledgeTracer(log_path, model_path)
    progress = Progress()
    progress.record_lesson("variables", 3, 3, [])
    progress.record_lesson("print() function", 3, 3, [])

    extractor = FeatureExtractor(progress, tracer.event_histories)
    combined = tracer._build_combined_input("variables", extractor)
    assert combined.shape == (COMBINED_DIM,)
    assert COMBINED_DIM == 47


def test_model_accepts_combined_input():
    model = KnowledgeTracerMLP()
    x = torch.randn(COMBINED_DIM)
    output = model(x)
    assert output.shape == ()  # scalar
    assert 0.0 <= output.item() <= 1.0


def test_train_step_updates_encoder(tmp_path: Path):
    log_path = tmp_path / "session_log.jsonl"
    model_path = tmp_path / "knowledge_model.pt"
    tracer = KnowledgeTracer(log_path, model_path)
    progress = Progress()
    progress.record_lesson("variables", 3, 3, [])
    progress.record_lesson("loops", 3, 3, [])

    # Capture encoder weights before training
    before = tracer.encoder.fc1.weight.data.clone()

    for _ in range(5):
        tracer.train_step("variables", True, progress)
        tracer.train_step("loops", False, progress)

    after = tracer.encoder.fc1.weight.data
    assert not torch.allclose(before, after), "Encoder weights should change during training"


def test_learner_profile_traits(tmp_path: Path):
    log_path = tmp_path / "session_log.jsonl"
    model_path = tmp_path / "knowledge_model.pt"
    tracer = KnowledgeTracer(log_path, model_path)
    progress = Progress()
    progress.record_lesson("variables", 3, 3, [])
    progress.record_lesson("loops", 3, 3, [])

    # Build enough history for profile to compute (>= CONFIDENCE_FULL_EVENTS)
    for i in range(CONFIDENCE_FULL_EVENTS + 5):
        tracer.train_step("variables", True, progress)
        tracer.train_step("loops", i % 2 == 0, progress)

    profile = tracer._compute_learner_profile()
    # Should have at least some traits computed
    assert isinstance(profile, dict)
    assert len(profile) > 0
    # All values should be non-empty strings
    for v in profile.values():
        assert isinstance(v, str)
        assert len(v) > 0


def test_format_block_includes_learner_profile(tmp_path: Path):
    log_path = tmp_path / "session_log.jsonl"
    model_path = tmp_path / "knowledge_model.pt"
    tracer = KnowledgeTracer(log_path, model_path)
    progress = Progress()
    progress.record_lesson("variables", 3, 3, [])
    progress.record_lesson("loops", 3, 3, [])

    # Build enough data for both tracer assessment and learner profile
    for i in range(CONFIDENCE_FULL_EVENTS + 5):
        tracer.train_step("variables", True, progress)
        tracer.train_step("loops", i % 3 != 0, progress)

    text = tracer.format_block(progress)
    assert "Knowledge Tracer Assessment" in text
    assert "Learner Profile:" in text


def test_old_15dim_checkpoint_triggers_retrain(tmp_path: Path):
    """A checkpoint with old 15-dim fc1 input (no encoder) should fail to load."""
    log_path = tmp_path / "session_log.jsonl"
    model_path = tmp_path / "knowledge_model.pt"

    old_model_state = {
        "fc1.weight": torch.randn(32, 15),   # OLD: 15-dim input (no embedding)
        "fc1.bias": torch.zeros(32),
        "fc2.weight": torch.randn(16, 32),
        "fc2.bias": torch.zeros(16),
        "fc3.weight": torch.randn(1, 16),
        "fc3.bias": torch.zeros(1),
    }
    torch.save({
        "model_state_dict": old_model_state,
        "optimizer_state_dict": {},
        "total_events": 5,
        "training_states": {},
    }, model_path)

    tracer = KnowledgeTracer(log_path, model_path)
    assert tracer.load() is False


def test_encoder_saved_and_loaded(tmp_path: Path):
    log_path = tmp_path / "session_log.jsonl"
    model_path = tmp_path / "knowledge_model.pt"

    t1 = KnowledgeTracer(log_path, model_path)
    progress = Progress()
    progress.record_lesson("variables", 3, 3, [])

    # Train to change encoder weights from init
    for _ in range(5):
        t1.train_step("variables", True, progress)
    t1.save()

    t2 = KnowledgeTracer(log_path, model_path)
    assert t2.load() is True

    # Encoder weights should match
    for k in t1.encoder.state_dict():
        assert torch.allclose(t1.encoder.state_dict()[k], t2.encoder.state_dict()[k])


# --- Step 4: Sequence modeling (GRU) tests ---


def test_build_global_timeline_sorts_by_timestamp():
    histories = {
        "loops": SkillEventHistory(
            outcomes=[True],
            timestamps=["2025-01-01T00:02:00Z"],
            severities=[None],
            attempt_numbers=[1],
            missing_concepts=[[]],
            forbidden_concepts=[[]],
            timed_out=[False],
            code_lines=[5],
        ),
        "variables": SkillEventHistory(
            outcomes=[False],
            timestamps=["2025-01-01T00:01:00Z"],
            severities=["minor"],
            attempt_numbers=[1],
            missing_concepts=[[]],
            forbidden_concepts=[[]],
            timed_out=[False],
            code_lines=[3],
        ),
    }
    timeline = _build_global_timeline(histories)
    assert len(timeline) == 2
    assert timeline[0]["skill"] == "variables"  # earlier timestamp
    assert timeline[1]["skill"] == "loops"


def test_build_global_timeline_empty():
    assert _build_global_timeline({}) == []


def test_encode_timeline_events_shape():
    histories = {
        "variables": SkillEventHistory(
            outcomes=[True, False, True],
            timestamps=["2025-01-01T00:01:00Z", "2025-01-01T00:02:00Z", "2025-01-01T00:03:00Z"],
            severities=[None, "minor", None],
            attempt_numbers=[1, 2, 1],
            missing_concepts=[[], ["x"], []],
            forbidden_concepts=[[], [], []],
            timed_out=[False, False, False],
            code_lines=[5, 8, 6],
        ),
    }
    timeline = _build_global_timeline(histories)
    events = KnowledgeTracer._encode_timeline_events(timeline, "variables")
    assert events.shape == (3, SEQ_EVENT_DIM)
    assert SEQ_EVENT_DIM == 12


def test_encode_timeline_skill_match_flag():
    histories = {
        "variables": SkillEventHistory(
            outcomes=[True],
            timestamps=["2025-01-01T00:01:00Z"],
            severities=[None],
            attempt_numbers=[1],
            missing_concepts=[[]],
            forbidden_concepts=[[]],
            timed_out=[False],
            code_lines=[5],
        ),
        "loops": SkillEventHistory(
            outcomes=[False],
            timestamps=["2025-01-01T00:02:00Z"],
            severities=["major"],
            attempt_numbers=[1],
            missing_concepts=[[]],
            forbidden_concepts=[[]],
            timed_out=[False],
            code_lines=[10],
        ),
    }
    timeline = _build_global_timeline(histories)
    events = KnowledgeTracer._encode_timeline_events(timeline, "variables")
    # Feature 7 = skill_match: first event is "variables" (1.0), second is "loops" (0.0)
    assert events[0, 7].item() == 1.0
    assert events[1, 7].item() == 0.0


def test_sequence_encoder_output_shape():
    encoder = SequenceEncoder()
    event_features = torch.randn(5, SEQ_EVENT_DIM)
    output = encoder(event_features)
    assert output.shape == (SEQ_HIDDEN,)
    assert SEQ_HIDDEN == 16


def test_combined_input_47_dim(tmp_path: Path):
    log_path = tmp_path / "session_log.jsonl"
    model_path = tmp_path / "knowledge_model.pt"
    tracer = KnowledgeTracer(log_path, model_path)
    progress = Progress()
    progress.record_lesson("variables", 3, 3, [])

    extractor = FeatureExtractor(progress, tracer.event_histories)
    combined = tracer._build_combined_input("variables", extractor)
    assert combined.shape == (COMBINED_DIM,)
    assert COMBINED_DIM == 47


def test_model_accepts_47_dim_input():
    model = KnowledgeTracerMLP()
    x = torch.randn(COMBINED_DIM)
    output = model(x)
    assert output.shape == ()
    assert 0.0 <= output.item() <= 1.0


def test_old_31dim_checkpoint_triggers_retrain(tmp_path: Path):
    """A checkpoint with old 31-dim fc1 input (no seq_encoder) should fail to load."""
    log_path = tmp_path / "session_log.jsonl"
    model_path = tmp_path / "knowledge_model.pt"

    old_model_state = {
        "fc1.weight": torch.randn(32, 31),   # OLD: 31-dim input (no sequence)
        "fc1.bias": torch.zeros(32),
        "fc2.weight": torch.randn(16, 32),
        "fc2.bias": torch.zeros(16),
        "fc3.weight": torch.randn(1, 16),
        "fc3.bias": torch.zeros(1),
    }
    torch.save({
        "model_state_dict": old_model_state,
        "encoder_state_dict": {},
        "optimizer_state_dict": {},
        "total_events": 5,
        "training_states": {},
    }, model_path)

    tracer = KnowledgeTracer(log_path, model_path)
    assert tracer.load() is False


def test_seq_encoder_saved_and_loaded(tmp_path: Path):
    log_path = tmp_path / "session_log.jsonl"
    model_path = tmp_path / "knowledge_model.pt"

    t1 = KnowledgeTracer(log_path, model_path)
    progress = Progress()
    progress.record_lesson("variables", 3, 3, [])

    for _ in range(5):
        t1.train_step("variables", True, progress)
    t1.save()

    t2 = KnowledgeTracer(log_path, model_path)
    assert t2.load() is True

    for k in t1.seq_encoder.state_dict():
        assert torch.allclose(t1.seq_encoder.state_dict()[k], t2.seq_encoder.state_dict()[k])


def test_gru_receives_gradients(tmp_path: Path):
    log_path = tmp_path / "session_log.jsonl"
    model_path = tmp_path / "knowledge_model.pt"
    tracer = KnowledgeTracer(log_path, model_path)
    progress = Progress()
    progress.record_lesson("variables", 3, 3, [])
    progress.record_lesson("loops", 3, 3, [])

    # Capture GRU weights before training
    before = {k: v.data.clone() for k, v in tracer.seq_encoder.gru.named_parameters()}

    for _ in range(10):
        tracer.train_step("variables", True, progress)
        tracer.train_step("loops", False, progress)

    changed = False
    for k, v in tracer.seq_encoder.gru.named_parameters():
        if not torch.allclose(before[k], v.data):
            changed = True
            break
    assert changed, "GRU weights should change during training"


# --- Step 5: Sensei review feedback loop tests ---


def test_parse_event_log_reads_review_meta(tmp_path: Path):
    log_path = tmp_path / "log.jsonl"
    lines = [
        {
            "event": "challenge_generated",
            "challenge_id": "c1",
            "skill": "variables",
            "timestamp": "t0",
        },
        {
            "event": "submission",
            "challenge_id": "c1",
            "verdict": "needs_work",
            "timestamp": "t1",
            "understanding": "none",
            "code_quality": "poor",
            "struggle_concepts": ["variable assignment"],
            "approach": "standard",
        },
    ]
    log_path.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    hist = parse_event_log(log_path)

    assert hist["variables"].understanding == ["none"]
    assert hist["variables"].code_quality == ["poor"]
    assert hist["variables"].struggle_concepts == [["variable assignment"]]
    assert hist["variables"].approach == ["standard"]


def test_parse_event_log_defaults_review_meta_for_old_entries(tmp_path: Path):
    log_path = tmp_path / "log.jsonl"
    lines = [
        {
            "event": "challenge_generated",
            "challenge_id": "c1",
            "skill": "print() function",
            "timestamp": "t0",
        },
        {
            "event": "submission",
            "challenge_id": "c1",
            "verdict": "pass",
            "timestamp": "t1",
            # No review meta fields — old format
        },
    ]
    log_path.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    hist = parse_event_log(log_path)

    assert hist["print() function"].understanding == ["partial"]
    assert hist["print() function"].code_quality == ["adequate"]
    assert hist["print() function"].struggle_concepts == [[]]
    assert hist["print() function"].approach == ["standard"]


def test_encode_timeline_events_12_dim():
    histories = {
        "variables": SkillEventHistory(
            outcomes=[True, False],
            timestamps=["2025-01-01T00:01:00Z", "2025-01-01T00:02:00Z"],
            severities=[None, "moderate"],
            attempt_numbers=[1, 2],
            missing_concepts=[[], ["print()"]],
            forbidden_concepts=[[], []],
            timed_out=[False, False],
            code_lines=[5, 8],
            understanding=["full", "partial"],
            code_quality=["good", "adequate"],
            struggle_concepts=[[], ["print()"]],
            approach=["standard", "standard"],
        ),
    }
    timeline = _build_global_timeline(histories)
    events = KnowledgeTracer._encode_timeline_events(timeline, "variables")
    assert events.shape == (2, SEQ_EVENT_DIM)
    assert SEQ_EVENT_DIM == 12
    # Check review meta features for first event (understanding=full, quality=good)
    assert events[0, 8].item() == 1.0   # understanding: full -> 1.0
    assert events[0, 9].item() == 1.0   # code_quality: good -> 1.0
    assert events[0, 10].item() == 0.0  # no struggle concepts
    assert events[0, 11].item() == 0.0  # standard approach


def test_train_step_with_review_meta(tmp_path: Path):
    log_path = tmp_path / "session_log.jsonl"
    model_path = tmp_path / "knowledge_model.pt"
    tracer = KnowledgeTracer(log_path, model_path)
    progress = Progress()
    progress.record_lesson("variables", 3, 3, [])

    tracer.train_step(
        "variables", False, progress,
        severity="major",
        understanding="none",
        code_quality="poor",
        struggle_concepts=["variable assignment", "f-strings"],
        approach="standard",
    )

    hist = tracer.event_histories["variables"]
    assert hist.understanding == ["none"]
    assert hist.code_quality == ["poor"]
    assert hist.struggle_concepts == [["variable assignment", "f-strings"]]
    assert hist.approach == ["standard"]


def test_old_8dim_gru_triggers_retrain(tmp_path: Path):
    """A checkpoint with old 8-dim GRU input should fail to load."""
    log_path = tmp_path / "session_log.jsonl"
    model_path = tmp_path / "knowledge_model.pt"

    # Build a fake checkpoint with correct fc1 but old GRU input size
    from codedojo.knowledge_tracer import COMBINED_DIM as CD, HIDDEN1, HIDDEN2, OUTPUT_DIM, SEQ_HIDDEN

    model_state = {
        "fc1.weight": torch.randn(HIDDEN1, CD),
        "fc1.bias": torch.zeros(HIDDEN1),
        "fc2.weight": torch.randn(HIDDEN2, HIDDEN1),
        "fc2.bias": torch.zeros(HIDDEN2),
        "fc3.weight": torch.randn(OUTPUT_DIM, HIDDEN2),
        "fc3.bias": torch.zeros(OUTPUT_DIM),
    }
    # GRU with old 8-dim input
    old_gru_state = {
        "gru.weight_ih_l0": torch.randn(3 * SEQ_HIDDEN, 8),  # OLD: 8-dim input
        "gru.weight_hh_l0": torch.randn(3 * SEQ_HIDDEN, SEQ_HIDDEN),
        "gru.bias_ih_l0": torch.zeros(3 * SEQ_HIDDEN),
        "gru.bias_hh_l0": torch.zeros(3 * SEQ_HIDDEN),
    }
    torch.save({
        "model_state_dict": model_state,
        "encoder_state_dict": {},
        "seq_encoder_state_dict": old_gru_state,
        "optimizer_state_dict": {},
        "total_events": 5,
        "training_states": {},
    }, model_path)

    tracer = KnowledgeTracer(log_path, model_path)
    assert tracer.load() is False


def test_dispute_overturn_sets_understanding_full(tmp_path: Path):
    log_path = tmp_path / "log.jsonl"
    lines = [
        {
            "event": "challenge_generated",
            "challenge_id": "x",
            "skill": "loops",
            "timestamp": "t0",
        },
        {
            "event": "submission",
            "challenge_id": "x",
            "verdict": "needs_work",
            "severity": "major",
            "understanding": "none",
            "code_quality": "poor",
            "timestamp": "t1",
        },
        {
            "event": "submission_dispute",
            "challenge_id": "x",
            "overturned": True,
            "timestamp": "t2",
        },
    ]
    log_path.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    hist = parse_event_log(log_path)

    assert hist["loops"].outcomes == [True]           # Flipped to pass
    assert hist["loops"].severities == [None]         # Severity cleared
    assert hist["loops"].understanding == ["full"]    # Understanding upgraded
