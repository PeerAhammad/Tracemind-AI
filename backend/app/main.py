import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import benchmark, runs, traces


def cors_origins() -> list[str]:
    """Comma-separated allowed frontend origins, e.g. CORS_ORIGINS=https://tracemind.vercel.app,http://localhost:5173"""
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    return [o.strip().rstrip("/") for o in raw.split(",") if o.strip()]


app = FastAPI(title="TraceMind AI", version="0.5.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    # Optional, e.g. r"https://tracemind-.*\.vercel\.app" to allow Vercel preview deployments.
    allow_origin_regex=os.getenv("CORS_ORIGIN_REGEX") or None,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(traces.router)
app.include_router(runs.tasks_router)
app.include_router(runs.runs_router)
app.include_router(benchmark.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def root():
    return {"name": "TraceMind AI", "docs": "/docs", "health": "/api/health"}
