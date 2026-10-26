from fastapi.testclient import TestClient

from app.main import app, cors_origins

client = TestClient(app)


def test_cors_origins_parsing(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", " https://a.vercel.app/ ,http://localhost:5173,, ")
    assert cors_origins() == ["https://a.vercel.app", "http://localhost:5173"]
    monkeypatch.delenv("CORS_ORIGINS")
    assert cors_origins() == ["http://localhost:5173"]


def test_root_and_health():
    assert client.get("/").json()["docs"] == "/docs"
    assert client.get("/api/health").json() == {"status": "ok"}


def test_cors_preflight_for_local_frontend():
    r = client.options("/api/health", headers={"Origin": "http://localhost:5173",
                                               "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
