"""Video ingestion: validate → extract audio → transcribe → key points.

Pipeline: authenticated upload (mp4/webm/mov, magic bytes, size cap) →
ffprobe duration gate → ffmpeg WAV extraction → transcription provider →
extractive key points → transcript returned for user confirmation. Nothing
is generated, saved, or published automatically; the transcript must be
confirmed in the UI before any post is created from it.

Transcription providers: `mock` (deterministic labeled placeholder, no
external calls) and `whisper_cli` (local openai-whisper binary, model
downloaded once by that tool). No vendor SDKs, no model downloads by us.
"""

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.config import Settings, get_settings
from app.models import User
from app.security import get_current_user

router = APIRouter(prefix="/api/video", tags=["video"])

VIDEO_EXTENSIONS = {".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime"}
MAX_VIDEO_BYTES = 50 * 1024 * 1024
MAX_VIDEO_SECONDS = 300
FFMPEG_TIMEOUT = 60
WHISPER_TIMEOUT = 300


def _reject(detail: str, code: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
    return HTTPException(status_code=code, detail=detail)


def _sniff_video(data: bytes) -> str | None:
    if data.startswith(b"\x1a\x45\xdf\xa3"):
        return "video/webm"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in (b"isom", b"iso2", b"mp41", b"mp42", b"avc1", b"dash", b"msdh", b"msix"):
            return "video/mp4"
        if brand == b"qt  ":
            return "video/quicktime"
    return None


def _run(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    """Fixed argv, no shell, no user-controlled executable path parts."""
    try:
        return subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise _reject("video_processing_failed", status.HTTP_502_BAD_GATEWAY) from exc


def _probe_duration(ffprobe_bin: str, path: Path) -> float:
    proc = _run(
        [ffprobe_bin, "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)],
        timeout=30,
    )
    if proc.returncode != 0:
        raise _reject("unreadable_video")
    try:
        duration = float(json.loads(proc.stdout.decode("utf-8", errors="replace"))["format"]["duration"])
    except (ValueError, KeyError, TypeError) as exc:
        raise _reject("unreadable_video") from exc
    if duration <= 0:
        raise _reject("unreadable_video")
    return duration


def _extract_wav(ffmpeg_bin: str, src: Path, dst: Path) -> None:
    proc = _run(
        [ffmpeg_bin, "-y", "-v", "error", "-i", str(src),
         "-ac", "1", "-ar", "16000", "-vn", str(dst)],
        timeout=FFMPEG_TIMEOUT,
    )
    if proc.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
        raise _reject("no_audio_track")


def _mock_transcript(filename: str, duration: float) -> dict:
    return {
        "text": (
            f"[MOCK TRANSCRIPT] Development placeholder for '{filename}' "
            f"({duration:.0f}s). Configure TRANSCRIPTION_PROVIDER=whisper_cli "
            "for real local transcription."
        ),
        "mock": True,
        "segments": [],
        "note": "Mock transcription. No audio was analyzed.",
    }


def _whisper_transcript(settings: Settings, wav: Path, workdir: Path) -> dict:
    if shutil.which(settings.whisper_bin) is None:
        raise _reject("transcription_unavailable", status.HTTP_501_NOT_IMPLEMENTED)
    proc = _run(
        [settings.whisper_bin, str(wav), "--model", settings.whisper_model,
         "--output_format", "txt", "--output_dir", str(workdir),
         "--fp16", "False"],
        timeout=WHISPER_TIMEOUT,
    )
    out_file = workdir / f"{wav.stem}.txt"
    if proc.returncode != 0 or not out_file.exists():
        raise _reject("transcription_failed", status.HTTP_502_BAD_GATEWAY)
    try:
        text = out_file.read_text(encoding="utf-8", errors="replace").strip()
    except OSError as exc:
        raise _reject("transcription_failed", status.HTTP_502_BAD_GATEWAY) from exc
    if not text:
        raise _reject("transcription_empty", status.HTTP_502_BAD_GATEWAY)
    return {
        "text": text,
        "mock": False,
        "segments": [],
        "note": "Local transcription. Verify the transcript before generating — errors are possible.",
    }


def _key_points(transcript: str, limit: int = 5) -> list[str]:
    """Extractive only: longest substantive sentences, labeled heuristic."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", transcript) if len(s.strip()) >= 40]
    sentences.sort(key=len, reverse=True)
    return sentences[:limit]


@router.post("/upload")
def upload_video(
    file: UploadFile,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    _ = user
    name = (file.filename or "").split("/")[-1].split("\\")[-1][:120] or "upload"
    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in VIDEO_EXTENSIONS:
        raise _reject("unsupported_video_type")
    data = file.file.read(MAX_VIDEO_BYTES + 1)
    if len(data) > MAX_VIDEO_BYTES:
        raise _reject("video_too_large")
    if not data or _sniff_video(data) is None:
        raise _reject("unreadable_video")

    with tempfile.TemporaryDirectory(prefix="linkedinai-video-") as tmp:
        workdir = Path(tmp)
        src = workdir / f"source{ext}"
        src.write_bytes(data)
        duration = _probe_duration(settings.ffprobe_bin, src)
        if duration > MAX_VIDEO_SECONDS:
            raise _reject("video_too_long")
        wav = workdir / "audio.wav"
        _extract_wav(settings.ffmpeg_bin, src, wav)

        if settings.transcription_provider == "whisper_cli":
            result = _whisper_transcript(settings, wav, workdir)
        else:
            result = _mock_transcript(name, duration)

    return {
        "filename": name,
        "size": len(data),
        "mime": VIDEO_EXTENSIONS[ext],
        "duration_seconds": round(duration, 1),
        "transcript": result["text"],
        "transcript_mock": result["mock"],
        "transcript_note": result["note"],
        "key_points": _key_points(result["text"]),
        "key_points_method": "heuristic extractive selection",
    }


@router.get("/status")
def video_status(
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    _ = user
    real = (
        settings.transcription_provider == "whisper_cli"
        and shutil.which(settings.whisper_bin) is not None
        and shutil.which(settings.ffmpeg_bin) is not None
        and shutil.which(settings.ffprobe_bin) is not None
    )
    return {
        "transcription_provider": settings.transcription_provider,
        "real_transcription_available": real,
        "accepted_types": sorted(VIDEO_EXTENSIONS),
        "max_mb": MAX_VIDEO_BYTES // (1024 * 1024),
        "max_seconds": MAX_VIDEO_SECONDS,
    }
