"""Focused unit tests for service modules that the API/task tests don't exercise
deeply: transcript parsers, B-roll lookup, rendering helpers, storage, the
analyze task, url_guard edge cases and the LLM message builder.

Everything external (yt-dlp, youtube-transcript-api, ffmpeg, httpx, Anthropic)
is stubbed.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

# --------------------------------------------------------------------------- #
# app.services.transcript - pure parsers                                      #
# --------------------------------------------------------------------------- #
from app.services import transcript as tr


def test_parse_vtt():
    body = (
        "WEBVTT\n\n"
        "00:00:00.000 --> 00:00:02.000\nHello <b>there</b>\n\n"
        "00:00:02.000 --> 00:00:04.000\nSecond line\n"
    )
    segs = tr._parse_vtt(body)
    assert [s["text"] for s in segs] == ["Hello there", "Second line"]
    assert segs[0]["start"] == 0.0 and segs[0]["end"] == 2.0


def test_parse_json3_and_dedupe():
    body = (
        '{"events":['
        '{"tStartMs":0,"dDurationMs":1000,"segs":[{"utf8":"foo"}]},'
        '{"tStartMs":1000,"dDurationMs":1000,"segs":[{"utf8":"foo"}]},'
        '{"tStartMs":2000,"dDurationMs":1000,"segs":[{"utf8":"bar"}]}'
        "]}"
    )
    segs = tr._parse_json3(body)
    # the two identical "foo" cues collapse into one
    assert [s["text"] for s in segs] == ["foo", "bar"]
    assert segs[0]["end"] == 2.0


def test_parse_timed_xml_text_and_p_forms():
    xml_text = '<transcript><text start="0.0" dur="1.5">alpha</text>' \
               '<text start="1.5" dur="1.0">beta</text></transcript>'
    segs = tr._parse_timed_xml(xml_text)
    assert [s["text"] for s in segs] == ["alpha", "beta"]

    ttml = '<p begin="00:00:00.000" end="00:00:01.000">one</p>' \
           '<p begin="00:00:01.000" end="00:00:02.000">two</p>'
    segs2 = tr._parse_timed_xml(ttml)
    assert [s["text"] for s in segs2] == ["one", "two"]


def test_transcript_helpers():
    assert tr._hms_to_seconds("01", "02", "03", "500") == pytest.approx(3723.5)
    assert tr._clean_text("<i>hi</i>\nthere &amp; you") == "hi there & you"
    assert tr._parse_clock("90s") == 90.0
    assert tr._parse_clock("00:01:30") == 90.0
    assert tr._as_float("bad") == 0.0
    assert tr._as_float("2.5") == 2.5


def test_fetch_transcript_success_via_strategy1(monkeypatch):
    seg = tr.TranscriptSegments([{"start": 1.0, "end": 2.0, "text": "hi"}])
    seg.language = "en"
    monkeypatch.setattr(tr, "_try_youtube_transcript_api", lambda vid: seg)
    out = tr.fetch_transcript("https://x", "vid", "youtube")
    assert out == [{"start": 1.0, "end": 2.0, "text": "hi"}]
    assert out.language == "en"


def test_fetch_transcript_falls_back_then_raises(monkeypatch):
    monkeypatch.setattr(tr, "_try_youtube_transcript_api", lambda vid: None)
    monkeypatch.setattr(tr, "_try_ytdlp_subtitles", lambda url: None)
    from app.exceptions import ExternalServiceError

    with pytest.raises(ExternalServiceError):
        tr.fetch_transcript("https://x", "vid", "youtube")


def test_parse_subtitles_dispatch():
    assert tr._parse_subtitles("00:00:00.000 --> 00:00:01.000\nhi\n", "vtt")
    assert tr._parse_subtitles('{"events":[{"tStartMs":0,"segs":[{"utf8":"hi"}]}]}', "json3")
    assert tr._parse_subtitles('<text start="0.0" dur="1">hi</text>', "srv3")


# --------------------------------------------------------------------------- #
# app.services.broll                                                          #
# --------------------------------------------------------------------------- #
from app.services import broll


@pytest.fixture(autouse=True)
def _clear_broll_cache():
    broll.clear_cache()
    yield
    broll.clear_cache()


def test_broll_use_false_is_skipped():
    out = broll.fetch_broll_asset({"use_broll": False, "search_keywords": ["x"]})
    assert out["asset_status"] == "skipped"


def test_broll_no_provider_keys_skipped(monkeypatch):
    monkeypatch.setattr(broll.settings, "PEXELS_API_KEY", "", raising=False)
    monkeypatch.setattr(broll.settings, "PIXABAY_API_KEY", "", raising=False)
    out = broll.fetch_broll_asset({"search_keywords": ["ocean"]})
    assert out["asset_status"] == "skipped"


def test_broll_no_keywords_not_found(monkeypatch):
    monkeypatch.setattr(broll.settings, "PEXELS_API_KEY", "key", raising=False)
    out = broll.fetch_broll_asset({"search_keywords": []})
    assert out["asset_status"] == "not_found"


def test_broll_pexels_hit_then_cached(monkeypatch):
    monkeypatch.setattr(broll.settings, "PEXELS_API_KEY", "key", raising=False)
    calls = {"n": 0}

    def fake_search_pexels(client, keywords):
        calls["n"] += 1
        return "https://cdn.pexels.com/clip.mp4"

    monkeypatch.setattr(broll, "_search_pexels", fake_search_pexels)
    seg = {"search_keywords": ["city skyline"]}
    first = broll.fetch_broll_asset(seg)
    second = broll.fetch_broll_asset(seg)
    assert first["asset_status"] == "fetched"
    assert first["asset_source"] == "pexels"
    assert second == first
    assert calls["n"] == 1  # second call served from cache


def test_broll_pixabay_fallback(monkeypatch):
    monkeypatch.setattr(broll.settings, "PEXELS_API_KEY", "key", raising=False)
    monkeypatch.setattr(broll.settings, "PIXABAY_API_KEY", "key2", raising=False)
    monkeypatch.setattr(broll, "_search_pexels", lambda c, k: None)
    monkeypatch.setattr(broll, "_search_pixabay", lambda c, k: "https://cdn.pixabay.com/v.mp4")
    out = broll.fetch_broll_asset({"search_keywords": ["forest"]})
    assert out["asset_source"] == "pixabay"
    assert out["asset_status"] == "fetched"


def test_broll_request_with_backoff_retries(monkeypatch):

    monkeypatch.setattr(broll.time, "sleep", lambda *_: None)

    class FakeResp:
        def __init__(self, status_code):
            self.status_code = status_code

        def json(self):
            return {"videos": [{"video_files": [{"link": "u", "width": 1}]}]}

    seq = [FakeResp(429), FakeResp(500), FakeResp(200)]

    class FakeClient:
        def request(self, method, url, **kw):
            return seq.pop(0)

    resp = broll._request_with_backoff(FakeClient(), "GET", "http://x")
    assert resp.status_code == 200
    assert not seq


# --------------------------------------------------------------------------- #
# app.services.rendering - helpers + pass-through stages                      #
# --------------------------------------------------------------------------- #
from app.services import rendering as rnd


def test_parse_timecode_forms():
    assert rnd._parse_timecode("01:02:03") == 3723.0
    assert rnd._parse_timecode("02:30") == 150.0
    assert rnd._parse_timecode(12) == 12.0
    assert rnd._parse_timecode(None) == 0.0
    assert rnd._parse_timecode("") == 0.0


def test_parse_timecode_invalid_raises():
    from app.exceptions import ExternalServiceError

    with pytest.raises(ExternalServiceError):
        rnd._parse_timecode("aa:bb")


def test_escape_drawtext():
    out = rnd._escape_drawtext("a:b'c%d\ne")
    assert ":" not in out.replace("\\:", "")
    assert "\n" not in out


def test_seg_get_dict_and_obj():
    assert rnd._seg_get({"a": 1}, "a") == 1
    obj = types.SimpleNamespace(a=2)
    assert rnd._seg_get(obj, "a") == 2
    assert rnd._seg_get({}, "missing", "d") == "d"


def test_ffprobe_binary(monkeypatch):
    monkeypatch.setattr(rnd.settings, "FFMPEG_BINARY", "/usr/bin/ffmpeg", raising=False)
    assert rnd._ffprobe_binary().endswith("ffprobe")


def test_resolve_asset(tmp_path, monkeypatch):
    assert rnd._resolve_asset("https://x/a.mp4", tmp_path) == "https://x/a.mp4"
    assert rnd._resolve_asset("", tmp_path) is None
    assert rnd._resolve_asset("/nope/missing.mp4", tmp_path) is None
    real = tmp_path / "a.mp4"
    real.write_bytes(b"x")
    assert rnd._resolve_asset(str(real), tmp_path) == str(real)


def test_burn_captions_passthrough_when_no_segments(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    assert rnd.burn_captions(src, None, tmp_path) == Path(src)
    assert rnd.burn_captions(src, [], tmp_path) == Path(src)


def test_overlay_broll_passthrough_when_no_fetched_assets(tmp_path):
    src = tmp_path / "in.mp4"
    src.write_bytes(b"x")
    assert rnd.overlay_broll(src, None, tmp_path) == Path(src)
    assert rnd.overlay_broll(src, [{"asset_status": "pending"}], tmp_path) == Path(src)


def test_download_source_segment_rejects_bad_window(tmp_path):
    from app.exceptions import ExternalServiceError

    with pytest.raises(ExternalServiceError):
        rnd.download_source_segment("https://x", "00:00:10", "00:00:05", tmp_path)


def test_rendering_stage_runs_with_ffmpeg_stubbed(tmp_path, monkeypatch):
    """crop/remove_silence/captions/encode with ffmpeg.run + probe stubbed."""
    outputs: list[Path] = []

    def fake_run(stream, *, desc):
        # emulate ffmpeg writing the stage's declared output file
        outputs.append(desc)

    monkeypatch.setattr(rnd, "_run", fake_run)
    monkeypatch.setattr(rnd, "_probe_duration", lambda p: 30.0)

    src = tmp_path / "src.mp4"
    src.write_bytes(b"x" * 2048)

    # crop_vertical builds a stream and calls _run; output file won't exist but
    # the function returns its intended path without raising.
    out = rnd.crop_vertical(src, tmp_path)
    assert out.name == "vertical.mp4"
    assert "crop" in outputs

    seg = {"start": "00:02", "end": "00:08", "text": "hi", "highlight_words": ["hi"]}
    cap = rnd.burn_captions(src, [seg], tmp_path)
    assert cap.name == "captioned.mp4"


# --------------------------------------------------------------------------- #
# app.services.storage                                                        #
# --------------------------------------------------------------------------- #
from app.services import storage


def test_storage_local_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(storage.settings, "MEDIA_ROOT", str(tmp_path), raising=False)
    monkeypatch.setattr(storage.settings, "S3_BUCKET", "", raising=False)
    src = tmp_path / "render.mp4"
    src.write_bytes(b"video")
    url = storage.store_output(src, "renders/1/9.mp4")
    assert url == "/media/renders/1/9.mp4"
    assert (tmp_path / "renders/1/9.mp4").read_bytes() == b"video"


def test_storage_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr(storage.settings, "MEDIA_ROOT", str(tmp_path), raising=False)
    from app.exceptions import ExternalServiceError

    with pytest.raises(ExternalServiceError):
        storage.local_media_path("../../etc/passwd")


def test_storage_missing_source_raises(tmp_path):
    from app.exceptions import ExternalServiceError

    with pytest.raises(ExternalServiceError):
        storage.store_output(tmp_path / "nope.mp4", "k.mp4")


def test_ensure_media_root_creates(tmp_path, monkeypatch):
    target = tmp_path / "media_sub"
    monkeypatch.setattr(storage.settings, "MEDIA_ROOT", str(target), raising=False)
    assert storage.ensure_media_root().is_dir()


# --------------------------------------------------------------------------- #
# app.services.ingestion - yt-dlp stubbed via sys.modules                     #
# --------------------------------------------------------------------------- #
def _install_fake_ytdlp(monkeypatch, info):
    fake = types.ModuleType("yt_dlp")

    class _YDL:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def extract_info(self, url, download=False):
            if isinstance(info, Exception):
                raise info
            return info

    fake.YoutubeDL = _YDL
    utils = types.ModuleType("yt_dlp.utils")

    class DownloadError(Exception):
        pass

    class ExtractorError(Exception):
        pass

    utils.DownloadError = DownloadError
    utils.ExtractorError = ExtractorError
    fake.utils = utils
    monkeypatch.setitem(sys.modules, "yt_dlp", fake)
    monkeypatch.setitem(sys.modules, "yt_dlp.utils", utils)


def test_fetch_metadata_success(monkeypatch):
    from app.services import ingestion

    _install_fake_ytdlp(
        monkeypatch,
        {
            "id": "abc",
            "title": "Hello",
            "duration": 300,
            "extractor_key": "Youtube",
            "thumbnail": "https://t/x.jpg",
            "webpage_url": "https://youtu.be/abc",
        },
    )
    meta = ingestion.fetch_metadata("https://youtu.be/abc")
    assert meta.video_id == "abc"
    assert meta.duration_seconds == 300
    assert meta.platform == "youtube"


def test_fetch_metadata_too_long_rejected(monkeypatch):
    from app.services import ingestion

    monkeypatch.setattr(ingestion.settings, "MAX_VIDEO_DURATION_SECONDS", 60, raising=False)
    _install_fake_ytdlp(monkeypatch, {"id": "x", "title": "T", "duration": 99999})
    from app.exceptions import ValidationError

    with pytest.raises(ValidationError):
        ingestion.fetch_metadata("https://youtu.be/x")


def test_fetch_metadata_extractor_error(monkeypatch):
    from app.services import ingestion

    _install_fake_ytdlp(monkeypatch, None)
    from app.exceptions import ExternalServiceError

    with pytest.raises(ExternalServiceError):
        ingestion.fetch_metadata("https://youtu.be/x")


# --------------------------------------------------------------------------- #
# app.tasks.analyze                                                           #
# --------------------------------------------------------------------------- #
def test_analyze_task_success_marks_ready(monkeypatch, db, client):
    import app.tasks.analyze as analyze_mod
    from app.models import Project
    from tests.conftest import _register_and_login, make_project

    owner = _register_and_login(client, "analyze-task@example.com")
    project = make_project(db, owner.id, status="analyzing")

    monkeypatch.setattr(
        analyze_mod, "run_analysis", lambda db_, pid: {"created": 6, "partial": False}
    )
    monkeypatch.setattr(analyze_mod, "_apply_broll_assets", lambda segs: 0)

    result = analyze_mod.analyze_project(project.id)
    assert result == {"created": 6, "partial": False}

    db.expire_all()
    assert db.get(Project, project.id).status == "ready"


def test_analyze_task_failure_marks_failed_and_reraises(monkeypatch, db, client):
    import app.tasks.analyze as analyze_mod
    from app.models import Project
    from tests.conftest import _register_and_login, make_project

    owner = _register_and_login(client, "analyze-fail@example.com")
    project = make_project(db, owner.id, status="analyzing")

    def _boom(db_, pid):
        raise RuntimeError("claude exploded")

    monkeypatch.setattr(analyze_mod, "run_analysis", _boom)

    with pytest.raises(RuntimeError):
        analyze_mod.analyze_project(project.id)

    db.expire_all()
    row = db.get(Project, project.id)
    assert row.status == "failed"
    assert "claude exploded" in (row.error_message or "")


def test_refetch_short_broll_task(monkeypatch, db, client):
    import app.tasks.analyze as analyze_mod
    from tests.conftest import _register_and_login, make_broll, make_project, make_short

    owner = _register_and_login(client, "refetch@example.com")
    project = make_project(db, owner.id)
    short = make_short(db, project.id, index=1)
    make_broll(db, short.id, search_keywords=["ocean"])

    monkeypatch.setattr(
        analyze_mod,
        "fetch_broll_asset",
        lambda seg: {"asset_url": "u", "asset_source": "pexels", "asset_status": "fetched"},
    )
    out = analyze_mod.refetch_short_broll(short.id)
    assert out["updated"] == 1


# --------------------------------------------------------------------------- #
# app.services.url_guard - remaining branches                                 #
# --------------------------------------------------------------------------- #
def test_url_guard_normalises_and_strips_fragment():
    from app.services.url_guard import validate_public_url

    out = validate_public_url("HTTPS://Example.COM/watch?v=1#frag")
    assert out.startswith("https://example.com/watch?v=1")
    assert "#" not in out


def test_url_guard_empty_and_missing_host():
    from app.exceptions import ValidationError
    from app.services.url_guard import validate_public_url

    with pytest.raises(ValidationError):
        validate_public_url("   ")
    with pytest.raises(ValidationError):
        validate_public_url("https://")


def test_url_guard_unresolvable(monkeypatch):
    import socket

    from app.exceptions import ValidationError
    from app.services import url_guard

    def _fail(*a, **k):
        raise socket.gaierror("nope")

    monkeypatch.setattr(url_guard.socket, "getaddrinfo", _fail)
    with pytest.raises(ValidationError):
        url_guard.validate_public_url("https://doesnotexist.example")


# --------------------------------------------------------------------------- #
# app.services.llm - message builder + text extraction                        #
# --------------------------------------------------------------------------- #
def test_llm_build_user_message_and_extract_text():
    from app.services import llm

    proj = types.SimpleNamespace(
        url="https://x", title="T", duration_seconds=100, language="en"
    )
    msg = llm._build_user_message(proj, [{"start": 0, "end": 1, "text": "hi"}])
    assert "FULL TRANSCRIPT" in msg and "hi" in msg

    resp = types.SimpleNamespace(
        content=[types.SimpleNamespace(text="foo"), types.SimpleNamespace(text="bar")]
    )
    assert llm._extract_text(resp) == "foobar"

    assert llm._strip_code_fence("```json\n{}\n```") == "{}"


def test_llm_missing_api_key_raises(monkeypatch):
    from app.exceptions import ExternalServiceError
    from app.services import llm

    monkeypatch.setattr(llm.settings, "ANTHROPIC_API_KEY", "", raising=False)
    client = llm.AnthropicClient()
    with pytest.raises(ExternalServiceError):
        client._get_client()
