import json
from pathlib import Path

import torch

from codedojo.ai_engine import build_system_blocks
from codedojo.knowledge_tracer import (
    CONFIDENCE_MIN_EVENTS,
    KnowledgeTracer,
    parse_event_log,
)
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
