"""Supabase Storage REST client, tested against a fake HTTP server (httpx.MockTransport)."""
import json

import httpx
import pytest

from annotator.storage.storage_service import StorageError, StorageService

BASE = "http://127.0.0.1:55321"


def make(handler, key="sb_secret_test"):
    return StorageService(BASE, key, transport=httpx.MockTransport(handler))


def recorder(response=None):
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        return response(request) if response else httpx.Response(200, json={})

    return calls, handler


def test_new_style_secret_key_goes_in_apikey_only():
    calls, handler = recorder()
    make(handler, key="sb_secret_abc").bucket_exists("images")
    assert calls[0].headers["apikey"] == "sb_secret_abc"
    assert "authorization" not in calls[0].headers


def test_jwt_service_role_key_also_goes_in_authorization():
    calls, handler = recorder()
    make(handler, key="eyJhbGciOi.jwt.key").bucket_exists("images")
    assert calls[0].headers["apikey"] == "eyJhbGciOi.jwt.key"
    assert calls[0].headers["authorization"] == "Bearer eyJhbGciOi.jwt.key"


@pytest.mark.parametrize("status,expected", [(200, True), (404, False), (400, False)])
def test_bucket_exists(status, expected):
    calls, handler = recorder(lambda r: httpx.Response(status, json={}))
    assert make(handler).bucket_exists("images") is expected
    assert (calls[0].method, calls[0].url.path) == ("GET", "/storage/v1/bucket/images")


def test_ensure_bucket_creates_a_private_bucket_only_when_missing():
    calls, handler = recorder(lambda r: httpx.Response(404 if r.method == "GET" else 200, json={}))
    make(handler).ensure_bucket("images")
    assert [(c.method, c.url.path) for c in calls] == [("GET", "/storage/v1/bucket/images"), ("POST", "/storage/v1/bucket")]
    assert json.loads(calls[1].content) == {"id": "images", "name": "images", "public": False}

    calls2, handler2 = recorder()
    make(handler2).ensure_bucket("images")
    assert [c.method for c in calls2] == ["GET"]


def test_upload_posts_the_bytes_with_content_type_and_upsert():
    calls, handler = recorder()
    make(handler).upload("images", "1/a b.jpg", b"JPEGDATA", "image/jpeg")
    req = calls[0]
    assert (req.method, req.url.raw_path) == ("POST", b"/storage/v1/object/images/1/a%20b.jpg")
    assert req.content == b"JPEGDATA"
    assert req.headers["content-type"] == "image/jpeg"
    assert req.headers["x-upsert"] == "true"


def test_signed_url_is_absolute_and_asks_for_the_given_lifetime():
    calls, handler = recorder(lambda r: httpx.Response(200, json={"signedURL": "/object/sign/images/1/a.jpg?token=T"}))
    url = make(handler).signed_url("images", "1/a.jpg", 600)
    assert url == f"{BASE}/storage/v1/object/sign/images/1/a.jpg?token=T"
    assert (calls[0].method, calls[0].url.path) == ("POST", "/storage/v1/object/sign/images/1/a.jpg")
    assert json.loads(calls[0].content) == {"expiresIn": 600}


def test_download_returns_the_bytes():
    calls, handler = recorder(lambda r: httpx.Response(200, content=b"IMG"))
    assert make(handler).download("images", "1/a.jpg") == b"IMG"
    assert (calls[0].method, calls[0].url.path) == ("GET", "/storage/v1/object/images/1/a.jpg")


def test_remove_deletes_by_prefixes():
    calls, handler = recorder(lambda r: httpx.Response(200, json=[]))
    make(handler).remove("images", ["1/a.jpg", "1/thumbs/a.jpg"])
    assert (calls[0].method, calls[0].url.path) == ("DELETE", "/storage/v1/object/images")
    assert json.loads(calls[0].content) == {"prefixes": ["1/a.jpg", "1/thumbs/a.jpg"]}


def test_errors_raise_storage_error_with_status_and_message():
    _, handler = recorder(lambda r: httpx.Response(413, json={"statusCode": "413", "error": "Payload too large", "message": "The object exceeded the maximum allowed size"}))
    with pytest.raises(StorageError) as e:
        make(handler).upload("images", "1/a.jpg", b"x", "image/jpeg")
    assert e.value.status == 413
    assert "maximum allowed size" in str(e.value)


def test_connection_failure_is_a_storage_error():
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(StorageError, match="refused"):
        make(handler).download("images", "1/a.jpg")
