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
