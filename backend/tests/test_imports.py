"""Import flow tests: uploads, URL fetch, GitHub inspect.

No real network, no real files on disk. PDFs/DOCXs are built in-test.
"""

import io
import zipfile

import httpx
import pytest
from fastapi.testclient import TestClient

from app import auth
from app.database import get_session_local, init_db
from app.main import app


@pytest.fixture()
def client(tmp_path):
    init_db(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    return TestClient(app)


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


def _minimal_pdf(text: str) -> bytes:
    esc = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 10 180 Td ({esc}) Tj ET".encode("latin-1")
    objs = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Resources<</Font<</F1 5 0 R>>>>/Contents 4 0 R>>",
        b"<</Length %d>>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<</Size {len(objs) + 1}/Root 1 0 R>>\n"
        f"startxref\n{xref_pos}\n%%EOF"
    ).encode()
    return bytes(out)


def _minimal_docx(text: str) -> bytes:
    xml = (
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", xml)
    return buffer.getvalue()


def _upload(client, filename, data, ctype="application/octet-stream"):
    return client.post("/api/imports/upload", files={"file": (filename, data, ctype)})


def test_imports_require_auth(client):
    assert client.post("/api/imports/upload").status_code in (401, 422)
    assert client.post("/api/imports/fetch-url", json={"url": "https://x.test"}).status_code == 401
    assert client.post("/api/imports/github", json={"url": "https://github.com/a/b"}).status_code == 401


def test_upload_rejects_bad_files(client):
    _login(client, "sub-upload-bad")
    assert _upload(client, "evil.exe", b"MZ...").json()["detail"] == "unsupported_type"
    assert _upload(client, "noext", b"data").json()["detail"] == "unsupported_type"
    assert _upload(client, "big.pdf", b"%PDF" + b"x" * (5 * 1024 * 1024)).json()["detail"] == "file_too_large"
    assert _upload(client, "fake.png", b"not-an-image-at-all").json()["detail"] == "unreadable_file"
    assert _upload(client, "empty.txt", b"").json()["detail"] == "unreadable_file"


def test_upload_text_and_docx(client):
    _login(client, "sub-upload-text")
    res = _upload(client, "notes.md", b"# Achievements\n\nShipped v2 in June.")
    assert res.status_code == 200
    body = res.json()
    assert body["kind"] == "text"
    assert "Shipped v2" in body["text"]
    assert body["needs_user_input"] is False

    res = _upload(client, "resume.docx", _minimal_docx("Jane Doe Senior Engineer"))
    assert res.status_code == 200
    body = res.json()
    assert body["kind"] == "document"
    assert "Jane Doe Senior Engineer" in body["text"]


def test_upload_pdf_extracts_text(client):
    _login(client, "sub-upload-pdf")
    res = _upload(client, "cert.pdf", _minimal_pdf("Certificate of Completion"))
    assert res.status_code == 200
    body = res.json()
    assert body["kind"] == "pdf"
    assert "Certificate of Completion" in body["text"]


def test_upload_image_needs_user_input(client):
    _login(client, "sub-upload-img")
    png = bytes.fromhex("89504e470d0a1a0a") + b"\x00" * 100
    res = _upload(client, "shot.png", png, "image/png")
    assert res.status_code == 200
    body = res.json()
    assert body["kind"] == "image"
    assert body["text"] == ""
    assert body["needs_user_input"] is True


def test_fetch_url_blocks_unsafe_destinations(client):
    _login(client, "sub-ssrf")
    for bad in (
        "ftp://example.com/x",
        "javascript:alert(1)",
        "http://127.0.0.1/admin",
        "http://localhost:8000/health",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "not a url",
        "",
    ):
        res = client.post("/api/imports/fetch-url", json={"url": bad})
        assert res.status_code in (400, 502), bad


def test_fetch_url_parses_html(client, monkeypatch):
    _login(client, "sub-fetch")
    import socket as socket_module

    real_getaddrinfo = socket_module.getaddrinfo

    def fake_getaddrinfo(host, *args, **kwargs):
        if host == "example.test":
            return [(socket_module.AF_INET, 1, 6, "", ("93.184.216.34", 0))]
        return real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket_module, "getaddrinfo", fake_getaddrinfo)
    html = (
        "<html><head><title>Great Article</title>"
        '<meta name="description" content="About things."></head>'
        "<body><p>First paragraph with more than forty characters in it here.</p>"
        "<p>Second paragraph also long enough to qualify as excerpt.</p></body></html>"
    )

    class FakeStream:
        status_code = 200
        headers = {"content-type": "text/html"}
        url = "https://example.test/post"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def iter_bytes(self, n):
            yield html.encode()

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def stream(self, *a, **k):
            return FakeStream()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    res = client.post("/api/imports/fetch-url", json={"url": "https://example.test/post"})
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "Great Article"
    assert body["description"] == "About things."
    assert len(body["excerpts"]) == 2
    assert body["host"] == "example.test"


def test_github_inspect_verified_fields(client, monkeypatch):
    _login(client, "sub-github")

    class FakeResp:
        def __init__(self, status_code, payload="", text=""):
            self.status_code = status_code
            self._payload = payload
            self.text = text

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, headers=None):
            if url.endswith("/readme"):
                return FakeResp(200, {}, text="# Demo\nReal readme text.")
            return FakeResp(200, {
                "full_name": "octo/demo",
                "description": "A demo repo.",
                "language": "Python",
                "topics": ["demo"],
                "license": {"spdx_id": "MIT"},
                "stargazers_count": 42,
            })

    monkeypatch.setattr(httpx, "Client", FakeClient)
    res = client.post("/api/imports/github", json={"url": "https://github.com/octo/demo"})
    assert res.status_code == 200
    body = res.json()
    assert body["full_name"] == "octo/demo"
    assert body["language"] == "Python"
    assert body["stars"] == 42
    assert "Real readme text." in body["readme_excerpt"]
    assert body["source"] == "github_api"


def test_github_rejects_non_github_and_missing(client, monkeypatch):
    _login(client, "sub-github-bad")
    assert client.post("/api/imports/github", json={"url": "https://gitlab.com/a/b"}).json()["detail"] == "invalid_github_url"
    assert client.post("/api/imports/github", json={"url": "not a url"}).json()["detail"] == "invalid_github_url"

    class FakeResp:
        status_code = 404

        def json(self):
            return {"message": "Not Found"}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, headers=None):
            return FakeResp()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    res = client.post("/api/imports/github", json={"url": "https://github.com/a/missing"})
    assert res.status_code == 404
    assert res.json()["detail"] == "github_not_found"
