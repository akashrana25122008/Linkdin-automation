"""Video ingestion tests: validation, mock transcription, safety, cleanup."""

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth
from app import video as video_module
from app.config import Settings, get_settings
from app.database import get_session_local, init_db
from app.main import app
from app.video import _key_points, _sniff_video


@pytest.fixture()
def client(tmp_path):
    init_db(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    yield TestClient(app)
    app.dependency_overrides.clear()


def _login(client: TestClient, sub: str) -> int:
    db = get_session_local()()
    try:
        user = auth.get_or_create_user(
            db, sub=sub, email=f"{sub}@example.com", name=sub, picture=None
        )
        user_id = user.id
        raw = auth.create_session(db, user_id)
    finally:
        db.close()
    client.cookies.set(auth.SESSION_COOKIE, raw)
    return user_id


def _upload(client, filename, data, ctype="application/octet-stream"):
    return client.post("/api/video/upload", files={"file": (filename, data, ctype)})


def test_video_requires_auth(client):
    assert client.post("/api/video/upload").status_code in (401, 422)
    assert client.get("/api/video/status").status_code == 401


def test_video_validation(client):
    _login(client, "sub-vid-bad")
    assert _upload(client, "x.exe", b"MZ...").json()["detail"] == "unsupported_video_type"
    assert _upload(client, "x.mp4", b"not a video").json()["detail"] == "unreadable_video"
    assert _upload(client, "x.mp4", b"\x00" * (51 * 1024 * 1024)).json()["detail"] == "video_too_large"


def test_sniff_video_formats():
    assert _sniff_video(b"\x1a\x45\xdf\xa3rest") == "video/webm"
    assert _sniff_video(b"\x00\x00\x00\x20ftypisomrest") == "video/mp4"
    assert _sniff_video(b"\x00\x00\x00\x20ftypqt  rest") == "video/quicktime"
    assert _sniff_video(b"junk") is None


def test_key_points_are_extractive():
    text = "Short. " + "This is a much longer sentence with real substance in it. " * 2
    points = _key_points(text)
    assert points and all("This is a much longer" in p or len(p) >= 40 for p in points)


def test_video_status_reports_capability(client):
    _login(client, "sub-vid-status")
    body = client.get("/api/video/status").json()
    assert body["accepted_types"] == [".mov", ".mp4", ".webm"]
    assert body["max_mb"] == 50
    assert body["max_seconds"] == 300
    assert isinstance(body["real_transcription_available"], bool)


ffmpeg_present = shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
needs_ffmpeg = pytest.mark.skipif(not ffmpeg_present, reason="ffmpeg/ffprobe not installed")


def _make_test_video(path: Path):
    proc = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=2:size=128x128:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)],
        capture_output=True, timeout=60,
    )
    assert proc.returncode == 0, proc.stderr.decode()[:300]


@needs_ffmpeg
def test_mock_transcription_flow(client, tmp_path):
    _login(client, "sub-vid-mock")
    video_path = tmp_path / "clip.mp4"
    _make_test_video(video_path)
    with open(video_path, "rb") as fh:
        res = _upload(client, "clip.mp4", fh.read(), "video/mp4")
    assert res.status_code == 200
    body = res.json()
    assert body["mime"] == "video/mp4"
    assert 1.5 <= body["duration_seconds"] <= 2.5
    assert body["transcript_mock"] is True
    assert "[MOCK TRANSCRIPT]" in body["transcript"]


def test_whisper_missing_binary_is_honest(client, tmp_path):
    _login(client, "sub-vid-nobin")
    app.dependency_overrides[get_settings] = lambda: Settings(
        transcription_provider="whisper_cli",
        whisper_bin="definitely-not-a-real-binary-xyz",
        frontend_url="http://localhost:5173",
    )
    try:
        with open(__file__, "rb") as fh:
            head = fh.read(64)
        res = _upload(client, "clip.mp4", b"\x00\x00\x00\x20ftypisom" + b"\x00" * 200, "video/mp4")
        # Fails at ffprobe or binary check — either way, honest error, never success.
        assert res.status_code in (400, 501, 502)
    finally:
        app.dependency_overrides.clear()


def test_whisper_provider_uses_configured_binary(client, tmp_path, monkeypatch):
    _login(client, "sub-vid-whisper")
    app.dependency_overrides[get_settings] = lambda: Settings(
        transcription_provider="whisper_cli",
        whisper_bin="/fake/whisper",
        whisper_model="tiny",
        ffmpeg_bin="ffmpeg",
        ffprobe_bin="ffprobe",
        frontend_url="http://localhost:5173",
    )
    calls = {}

    class FakeProc:
        returncode = 0
        stdout = b'{"format": {"duration": "12.5"}}'
        stderr = b""

    def fake_run(cmd, **kwargs):
        calls.setdefault("cmds", []).append(cmd[0])
        if cmd[0] == "ffprobe":
            return FakeProc()
        if cmd[0] == "ffmpeg":
            out = Path(cmd[-1])
            out.write_bytes(b"RIFF....WAVEfake")
            return FakeProc()
        assert cmd[0] == "/fake/whisper"
        assert "--model" in cmd and "tiny" in cmd
        assert "--output_format" in cmd and "txt" in cmd
        assert "--fp16" in cmd
        assert "False" in cmd
        for i, part in enumerate(cmd):
            if part == "--output_dir":
                Path(cmd[i + 1], "audio.txt").write_text("Spoken words here about testing.", encoding="utf-8")
        return FakeProc()

    monkeypatch.setattr(video_module.subprocess, "run", fake_run)
    monkeypatch.setattr(video_module.shutil, "which", lambda *a, **k: "/fake/whisper")
    try:
        res = _upload(client, "clip.mp4", b"\x00\x00\x00\x20ftypisom" + b"\x00" * 200, "video/mp4")
        assert res.status_code == 200
        body = res.json()
        assert body["transcript_mock"] is False
        assert "Spoken words" in body["transcript"]
        assert body["duration_seconds"] == 12.5
    finally:
        app.dependency_overrides.clear()
