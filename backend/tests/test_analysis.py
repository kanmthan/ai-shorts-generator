"""``app.services.analysis.run_analysis`` - the Claude -> DB seam.

The Anthropic call itself (``AnthropicClient._create``) is monkeypatched to
return a canned string; nothing hits the network.
"""

from __future__ import annotations

import json

import pytest

import app.services.llm as llm_mod
from app.exceptions import ExternalServiceError
from app.models import BrollSegment, Short, SubtitleSegment
from app.services.analysis import run_analysis
from tests.conftest import _register_and_login, make_project, make_short

_SCORES = {
    "hook_strength": 8,
    "standalone_value": 8,
    "engagement": 9,
    "retention": 7,
    "payoff": 8,
    "clarity": 9,
    "shareability": 7,
    "viral_potential": 8,
    "b_roll_quality": 6,
    "overall": 7.9,
}


def _short(idx: int, start: str, end: str, dur: int) -> dict:
    return {
        "id": f"short_{idx}",
        "start_time": start,
        "end_time": end,
        "duration_seconds": dur,
        "title": f"Golden Short {idx}",
        "hook": "A strong hook",
        "summary": "A standalone moment.",
        "reason": "Clear payoff, high energy.",
        "scores": dict(_SCORES),
        "caption": "Great clip",
        "hashtags": ["#shorts", "#ai"],
        "editing": {"b_roll_position": "middle"},
        "broll_segments": [
            {
                "start": "00:15",
                "end": "00:25",
                "original_start": "01:15",
                "original_end": "01:25",
                "duration_seconds": 10,
                "description": "supporting shot",
                "reason": "adds context",
                "search_keywords": ["keyword one", "keyword two"],
                "type": "stock_video",
                "transition": "smooth_cut",
                "placement": "middle",
                "use_broll": True,
            }
        ],
        "subtitle_segments": [
            {"start": "00:00", "end": "00:03", "text": "First line", "highlight_words": ["First"]},
            {"start": "00:03", "end": "00:06", "text": "Second line", "highlight_words": None},
        ],
    }


def _envelope(shorts: list[dict], status: str = "success") -> dict:
    return {
        "status": status,
        "source_video": {
            "url": "https://youtu.be/abc",
            "title": "Source",
            "duration_seconds": 1200,
        },
        "total_shorts": len(shorts),
        "shorts": shorts,
    }


GOLDEN_SIX = _envelope(
    [
        _short(1, "00:01:00", "00:01:45", 45),
        _short(2, "00:03:00", "00:03:50", 50),
        _short(3, "00:05:00", "00:05:40", 40),
        _short(4, "00:07:00", "00:07:55", 55),
        _short(5, "00:09:00", "00:09:35", 35),
        _short(6, "00:11:00", "00:11:48", 48),
    ]
)

# Two of the six shorts are unusable once clamped to [0, duration]:
#   #3 sits past the 1200s video end -> clamps to a ~10s window -> rejected
#   #5 has end <= start -> rejected
GOLDEN_PARTIAL = _envelope(
    [
        _short(1, "00:01:00", "00:01:45", 45),
        _short(2, "00:03:00", "00:03:50", 50),
        _short(3, "00:19:50", "00:20:40", 50),
        _short(4, "00:07:00", "00:07:55", 55),
        _short(5, "00:09:30", "00:09:10", 40),
        _short(6, "00:11:00", "00:11:48", 48),
    ],
    status="partial",
)


@pytest.fixture
def project(client, db):
    owner = _register_and_login(client, "analysis@example.com")
    return make_project(
        db,
        owner.id,
        status="analyzing",
        duration_seconds=1200,
        transcript=[{"start": 0.0, "end": 3.0, "text": "hello world"}],
    )


def _patch_llm(monkeypatch, *returns):
    from unittest.mock import Mock

    monkeypatch.setattr(
        llm_mod.AnthropicClient,
        "_create",
        Mock(side_effect=[json.dumps(r) if isinstance(r, dict) else r for r in returns]),
    )


def test_run_analysis_persists_full_graph(monkeypatch, db, project):
    _patch_llm(monkeypatch, GOLDEN_SIX)

    result = run_analysis(db, project.id)

    assert result == {"created": 6, "partial": False}
    shorts = db.query(Short).filter(Short.project_id == project.id).order_by(Short.index).all()
    assert [s.index for s in shorts] == [1, 2, 3, 4, 5, 6]
    assert db.query(BrollSegment).count() == 6
    assert db.query(SubtitleSegment).count() == 12
    assert shorts[0].duration_seconds == pytest.approx(45.0)
    assert shorts[0].start_time == "00:01:00"
    assert shorts[0].scores["engagement"] == 9


def test_run_analysis_rejects_out_of_band_and_flags_partial(monkeypatch, db, project):
    _patch_llm(monkeypatch, GOLDEN_PARTIAL)

    result = run_analysis(db, project.id)

    assert result["partial"] is True
    assert result["created"] == 4
    kept = db.query(Short).filter(Short.project_id == project.id).all()
    assert len(kept) == 4
    # every persisted short is inside the tolerance band
    for short in kept:
        assert 25.0 <= (short.duration_seconds or 0) <= 65.0


def test_run_analysis_regenerate_replaces_existing_shorts(monkeypatch, db, project):
    make_short(db, project.id, index=1, title="STALE")
    make_short(db, project.id, index=2, title="ALSO STALE")
    _patch_llm(monkeypatch, GOLDEN_SIX)

    run_analysis(db, project.id)

    db.expunge_all()
    rows = db.query(Short).filter(Short.project_id == project.id).order_by(Short.index).all()
    titles = [s.title for s in rows]
    assert "STALE" not in titles and "ALSO STALE" not in titles
    assert titles == [f"Golden Short {i}" for i in range(1, 7)]


def test_run_analysis_invalid_json_after_repair_raises(monkeypatch, db, project):
    _patch_llm(monkeypatch, "not json at all", "{still: broken")

    with pytest.raises(ExternalServiceError):
        run_analysis(db, project.id)

    assert db.query(Short).filter(Short.project_id == project.id).count() == 0


def test_run_analysis_repairs_on_second_attempt(monkeypatch, db, project):
    _patch_llm(monkeypatch, "garbage", GOLDEN_SIX)

    result = run_analysis(db, project.id)
    assert result["created"] == 6


def test_run_analysis_requires_transcript(monkeypatch, db, project):
    project.transcript = None
    db.commit()
    _patch_llm(monkeypatch, GOLDEN_SIX)

    from app.exceptions import ValidationError

    with pytest.raises(ValidationError):
        run_analysis(db, project.id)


def test_run_analysis_unknown_project(db):
    from app.exceptions import NotFoundError

    with pytest.raises(NotFoundError):
        run_analysis(db, 987_654)
