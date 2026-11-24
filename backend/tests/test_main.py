"""App wiring: health route and the one error format (RFC 7807 problem+json), like backend_web's ProblemDetail."""
from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel

from annotator.common.problem import ApiError
from annotator.main import create_app

PROBLEM = "application/problem+json"


def client_with_test_routes():
    app = create_app()
    router = APIRouter()

    class Body(BaseModel):
        name: str

    @router.get("/api/_test/conflict")
    def conflict():
        raise ApiError(409, "CLASS_NAME_TAKEN", "A class with that name already exists.")

    @router.post("/api/_test/body")
    def body(b: Body):
        return b

    @router.get("/api/_test/boom")
    def boom():
        raise RuntimeError("secret internals")

    app.include_router(router)
    return TestClient(app, raise_server_exceptions=False)


def test_health_route_says_ok():
    r = TestClient(create_app()).get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_api_error_becomes_problem_json_with_code_and_trace_id():
    r = client_with_test_routes().get("/api/_test/conflict")
    assert r.status_code == 409
    assert r.headers["content-type"].startswith(PROBLEM)
    body = r.json()
    assert body["status"] == 409
    assert body["code"] == "CLASS_NAME_TAKEN"
    assert body["detail"] == "A class with that name already exists."
    assert body["title"] == "Conflict"
    assert body["traceId"]


def test_unknown_route_is_problem_json_not_found():
    r = client_with_test_routes().get("/api/nope")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith(PROBLEM)
    assert r.json()["code"] == "NOT_FOUND"


def test_invalid_body_is_problem_json_validation_failed_with_field_errors():
    r = client_with_test_routes().post("/api/_test/body", json={})
    assert r.status_code == 400
    body = r.json()
    assert body["code"] == "VALIDATION_FAILED"
    assert body["errors"][0]["field"] == "name"


def test_unexpected_error_is_500_problem_without_leaking_internals():
    r = client_with_test_routes().get("/api/_test/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["code"] == "INTERNAL_ERROR"
    assert "secret internals" not in r.text
    assert body["traceId"]


def test_cors_allows_only_the_web_app_origin():
    c = TestClient(create_app())
    ok = c.options("/api/health", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    bad = c.options("/api/health", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in bad.headers


class FakeListener:
    """Stands in for the NOTIFY listener thread; keeps the callbacks the app gave it."""

    def __init__(self, on_payload, on_connect):
        self.on_payload, self.on_connect = on_payload, on_connect
        self.started = self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


def app_with_fakes(storage=None, build_message=None):
    from annotator.realtime.dependencies import get_listener_factory, get_message_builder
    from annotator.storage.dependencies import get_storage
    from tests.fakes import FakeStorage

    app, made = create_app(), {}
    storage = storage or FakeStorage()

    def factory():
        def make(on_payload, on_connect):
            made["listener"] = FakeListener(on_payload, on_connect)
            return made["listener"]
        return make

    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_listener_factory] = factory
    if build_message:
        app.dependency_overrides[get_message_builder] = lambda: build_message
    return app, storage, made


def test_startup_creates_the_storage_buckets():
    app, storage, _ = app_with_fakes()
    with TestClient(app):
        pass
    assert storage.buckets == ["images", "exports"]


def test_startup_still_works_when_storage_is_down():
    from annotator.storage.storage_service import StorageError
    from tests.fakes import FakeStorage

    storage = FakeStorage()
    storage.fail_with = StorageError(0, "connection refused")
    app, _, _ = app_with_fakes(storage)
    with TestClient(app) as c:
        assert c.get("/api/health").status_code == 200


def test_live_update_listener_starts_with_the_app_and_stops_with_it():
    app, _, made = app_with_fakes()
    with TestClient(app):
        assert made["listener"].started and not made["listener"].stopped
    assert made["listener"].stopped


def test_a_database_change_reaches_the_streams_of_its_project():
    """Listener thread -> message builder -> broadcaster -> the project's SSE subscriptions."""
    app, _, made = app_with_fakes(build_message=lambda payload: (4, {"type": "images", "seen": payload}))
    with TestClient(app) as c:
        broadcaster = app.state.broadcaster
        sub = c.portal.call(lambda: broadcaster.subscribe(4))
        made["listener"].on_payload("raw")
        assert c.portal.call(sub.get) == {"type": "images", "seen": "raw"}


def test_payloads_the_builder_skips_send_nothing():
    app, _, made = app_with_fakes(build_message=lambda payload: None)
    with TestClient(app) as c:
        broadcaster = app.state.broadcaster
        sub = c.portal.call(lambda: broadcaster.subscribe(4))
        made["listener"].on_payload("raw")
        made["listener"].on_connect()
        assert c.portal.call(sub.get)["type"] == "resync"


def test_every_stream_is_told_to_resync_when_the_listener_reconnects():
    """Changes made while the listener was disconnected were missed, so open tabs refetch."""
    app, _, made = app_with_fakes()
    with TestClient(app) as c:
        broadcaster = app.state.broadcaster
        sub = c.portal.call(lambda: broadcaster.subscribe(9))
        made["listener"].on_connect()
        assert c.portal.call(sub.get) == {"type": "resync"}
