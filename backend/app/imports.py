"""User content import flows: file parsing, URL fetch, GitHub inspect.

All endpoints require authentication. Nothing is written to disk and no
database rows are created here — callers confirm extracted facts in the UI
before anything is saved. Every extracted value is labeled with what could
actually be determined; anything uncertain is reported, never guessed.
"""

import io
import ipaddress
import re
import socket
import zipfile
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status

from app.security import get_current_user
from app.models import User

router = APIRouter(prefix="/api/imports", tags=["imports"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_EXTRACT_CHARS = 20000
MAX_PDF_PAGES = 10
FETCH_TIMEOUT = 10
FETCH_MAX_BYTES = 1024 * 1024
GITHUB_TIMEOUT = 10

ALLOWED_EXTENSIONS = {
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".gif": "image",
    ".pdf": "pdf",
    ".docx": "document",
    ".txt": "text",
    ".md": "text",
}

IMAGE_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def _reject(detail: str, code: int = status.HTTP_400_BAD_REQUEST) -> HTTPException:
    return HTTPException(status_code=code, detail=detail)


def _safe_basename(filename: str | None) -> str:
    """Display-only filename; never used for filesystem paths (no writes)."""
    if not filename:
        return "upload"
    return filename.split("/")[-1].split("\\")[-1][:120] or "upload"


def _sniff_image(data: bytes) -> str | None:
    if data.startswith(IMAGE_SIGNATURES[0][0]):
        return IMAGE_SIGNATURES[0][1]
    if data.startswith(IMAGE_SIGNATURES[1][0]):
        return IMAGE_SIGNATURES[1][1]
    if data.startswith(IMAGE_SIGNATURES[2][0]) or data.startswith(IMAGE_SIGNATURES[3][0]):
        return IMAGE_SIGNATURES[3][1]
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _extract_docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            try:
                xml = archive.read("word/document.xml")
            except KeyError as exc:
                raise _reject("unreadable_file") from exc
    except zipfile.BadZipFile as exc:
        raise _reject("unreadable_file") from exc

    class _Text(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts: list[str] = []
            self.length = 0

        def handle_data(self, text: str):
            # Cap accumulation up front: a small archive can decompress
            # into a very large document (zip bomb).
            if self.length < 100000:
                self.parts.append(text)
                self.length += len(text)

    parser = _Text()
    try:
        parser.feed(xml.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise _reject("unreadable_file") from exc
    return " ".join(part for part in (p.strip() for p in parser.parts) if part)


def _extract_pdf(data: bytes) -> tuple[str, bool]:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(io.BytesIO(data))
        pages = reader.pages[:MAX_PDF_PAGES]
        text = "\n".join((page.extract_text() or "") for page in pages)
    except (PdfReadError, ValueError, IndexError) as exc:
        raise _reject("unreadable_file") from exc
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise _reject("unreadable_file")
    truncated = len(reader.pages) > MAX_PDF_PAGES or len(text) > MAX_EXTRACT_CHARS
    return text[:MAX_EXTRACT_CHARS], truncated


@router.post("/upload")
def upload_file(
    file: UploadFile,
    user: User = Depends(get_current_user),
) -> dict:
    _ = user
    name = _safe_basename(file.filename)
    ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
    kind = ALLOWED_EXTENSIONS.get(ext)
    if kind is None:
        raise _reject("unsupported_type")
    data = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise _reject("file_too_large")
    if not data:
        raise _reject("unreadable_file")

    if kind == "image":
        mime = _sniff_image(data)
        if mime is None:
            raise _reject("unreadable_file")
        return {
            "kind": "image",
            "filename": name,
            "size": len(data),
            "mime": mime,
            "text": "",
            "truncated": False,
            "needs_user_input": True,
            "note": "Image content cannot be read automatically. Describe what "
            "is shown and confirm the facts before generating.",
        }
    if kind == "pdf":
        if not data.startswith(b"%PDF"):
            raise _reject("unreadable_file")
        text, truncated = _extract_pdf(data)
        return {
            "kind": "pdf",
            "filename": name,
            "size": len(data),
            "mime": "application/pdf",
            "text": text,
            "truncated": truncated,
            "needs_user_input": False,
            "note": "Review the extracted text; only confirmed facts will be used.",
        }
    if kind == "document":
        if not data.startswith(b"PK"):
            raise _reject("unreadable_file")
        text = _extract_docx(data)
        if not text:
            raise _reject("unreadable_file")
        return {
            "kind": "document",
            "filename": name,
            "size": len(data),
            "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text": text[:MAX_EXTRACT_CHARS],
            "truncated": len(text) > MAX_EXTRACT_CHARS,
            "needs_user_input": False,
            "note": "Review the extracted text; only confirmed facts will be used.",
        }
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _reject("unreadable_file") from exc
    if not text.strip():
        raise _reject("unreadable_file")
    return {
        "kind": "text",
        "filename": name,
        "size": len(data),
        "mime": "text/plain",
        "text": text[:MAX_EXTRACT_CHARS],
        "truncated": len(text) > MAX_EXTRACT_CHARS,
        "needs_user_input": False,
        "note": "Review the text; only confirmed facts will be used.",
    }


def _validate_public_url(raw: str) -> str:
    """Reject non-HTTP(S), credentials, and non-global destinations (SSRF)."""
    if not isinstance(raw, str) or not raw.strip():
        raise _reject("invalid_url")
    try:
        parsed = urlparse(raw.strip())
    except ValueError as exc:
        raise _reject("invalid_url") from exc
    if parsed.scheme not in ("http", "https"):
        raise _reject("invalid_url")
    if parsed.username or parsed.password or "@" in (parsed.netloc or ""):
        raise _reject("invalid_url")
    host = (parsed.hostname or "").lower().rstrip(".")
    if not host:
        raise _reject("invalid_url")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise _reject("unreachable_url", status.HTTP_502_BAD_GATEWAY) from exc
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError as exc:
            raise _reject("invalid_url") from exc
        if not ip.is_global or ip.is_multicast:
            raise _reject("private_url")
    return parsed.geturl()


class _ArticleParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self._in_title = False
        self._in_p = False
        self._current: list[str] = []
        self.paragraphs: list[str] = []

    def handle_starttag(self, tag, attrs):
        name = tag.lower()
        if name == "title":
            self._in_title = True
        elif name == "p":
            self._in_p = True
            self._current = []
        elif name == "meta":
            data = {k.lower(): v for k, v in attrs}
            if data.get("name") in ("description",) or data.get("property") in (
                "og:description",
            ):
                if data.get("content") and not self.description:
                    self.description = data["content"].strip()[:500]

    def handle_endtag(self, tag):
        name = tag.lower()
        if name == "title":
            self._in_title = False
        elif name == "p":
            self._in_p = False
            text = " ".join("".join(self._current).split())
            if len(text) >= 40:
                self.paragraphs.append(text[:800])
            self._current = []

    def handle_data(self, text):
        if self._in_title:
            self.title += text
        elif self._in_p:
            self._current.append(text)


@router.post("/fetch-url")
def fetch_url(payload: dict, user: User = Depends(get_current_user)) -> dict:
    _ = user
    url = _validate_public_url(payload.get("url", ""))
    try:
        with httpx.Client(timeout=FETCH_TIMEOUT, follow_redirects=True, max_redirects=3) as client:
            with client.stream("GET", url, headers={"User-Agent": "LinkedInAI/1.0"}) as res:
                if res.status_code != 200:
                    raise _reject("fetch_failed", status.HTTP_502_BAD_GATEWAY)
                content_type = res.headers.get("content-type", "")
                chunks: list[bytes] = []
                size = 0
                for chunk in res.iter_bytes(65536):
                    size += len(chunk)
                    if size > FETCH_MAX_BYTES:
                        break
                    chunks.append(chunk)
                body = b"".join(chunks)
    except httpx.HTTPError as exc:
        raise _reject("fetch_failed", status.HTTP_502_BAD_GATEWAY) from exc
    # Re-validate the final URL after redirects (redirect SSRF).
    final_url = _validate_public_url(str(res.url))
    if "text/plain" in content_type:
        text = body.decode("utf-8", errors="replace").strip()
        return {
            "url": final_url,
            "host": urlparse(final_url).hostname,
            "title": "",
            "description": "",
            "excerpts": [text[:800]] if text else [],
            "source": "fetched",
        }
    if "html" not in content_type:
        raise _reject("unsupported_content")
    parser = _ArticleParser()
    try:
        parser.feed(body.decode("utf-8", errors="replace"))
    except (ValueError, MemoryError) as exc:
        raise _reject("fetch_failed", status.HTTP_502_BAD_GATEWAY) from exc
    if not parser.title.strip() and not parser.paragraphs:
        raise _reject("no_readable_content")
    return {
        "url": final_url,
        "host": urlparse(final_url).hostname,
        "title": " ".join(parser.title.split())[:300],
        "description": parser.description,
        "excerpts": parser.paragraphs[:6],
        "source": "fetched",
    }


GITHUB_REPO_RE = re.compile(
    r"^https?://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$"
)


@router.post("/github")
def github_repo(
    payload: dict,
    user: User = Depends(get_current_user),
) -> dict:
    _ = user
    raw = payload.get("url", "")
    match = GITHUB_REPO_RE.match(raw.strip() if isinstance(raw, str) else "")
    if not match:
        raise _reject("invalid_github_url")
    owner, repo = match.groups()
    try:
        with httpx.Client(timeout=GITHUB_TIMEOUT) as client:
            meta = client.get(
                f"https://api.github.com/repos/{owner}/{repo}",
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "LinkedInAI/1.0",
                },
            )
            if meta.status_code == 404:
                raise _reject("github_not_found", status.HTTP_404_NOT_FOUND)
            if meta.status_code != 200:
                raise _reject("github_failed", status.HTTP_502_BAD_GATEWAY)
            try:
                info = meta.json()
            except ValueError as exc:
                raise _reject("github_failed", status.HTTP_502_BAD_GATEWAY) from exc
            readme_text = ""
            readme = client.get(
                f"https://api.github.com/repos/{owner}/{repo}/readme",
                headers={
                    "Accept": "application/vnd.github.raw",
                    "User-Agent": "LinkedInAI/1.0",
                },
            )
            if readme.status_code == 200:
                readme_text = readme.text[:4000]
    except httpx.HTTPError as exc:
        raise _reject("github_failed", status.HTTP_502_BAD_GATEWAY) from exc
    if not isinstance(info, dict) or "full_name" not in info:
        raise _reject("github_failed", status.HTTP_502_BAD_GATEWAY)
    topics = info.get("topics")
    license_info = info.get("license")
    if not isinstance(license_info, dict):
        license_info = {}
    return {
        "url": f"https://github.com/{owner}/{repo}",
        "full_name": info.get("full_name", ""),
        "description": (info.get("description") or "")[:500],
        "language": info.get("language") or "",
        "topics": [t for t in topics if isinstance(t, str)][:10] if isinstance(topics, list) else [],
        "license": license_info.get("spdx_id", "") or license_info.get("name", ""),
        "stars": info.get("stargazers_count", 0) if isinstance(info.get("stargazers_count"), int) else 0,
        "readme_excerpt": readme_text,
        "source": "github_api",
    }
