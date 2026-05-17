"""FastAPI backend entrypoint for PROMETHEUS."""

import os
from contextlib import asynccontextmanager

import yaml
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from backend.database import get_recent_analyses, init_db, save_analysis
from backend.models import AnalysisRequest, AnalysisResult
from backend.orchestrator import run_analysis


# Default origins cover local dev and the deployed Streamlit Cloud frontend.
# Override with the FRONTEND_ORIGINS env var (comma-separated) for new deploys.
_DEFAULT_ORIGINS = (
    "http://localhost:8501,"
    "http://127.0.0.1:8501,"
    "https://prometheus-decision-agent-xrvhtvpsfktvewy5kuyjp4.streamlit.app"
)
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", _DEFAULT_ORIGINS).split(",")
    if origin.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app = FastAPI(title="PROMETHEUS", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"), "agents": 4}


@app.get("/scenarios")
async def get_scenarios():
    with open("configs/scenarios.yaml") as f:
        data = yaml.safe_load(f)
    return [{"id": scenario["id"], "label": scenario["label"]} for scenario in data["scenarios"]]


@app.post("/analyze", response_model=AnalysisResult)
@limiter.limit("10/minute")
async def analyze(request: Request, payload: AnalysisRequest):
    question = payload.question
    if payload.scenario_id:
        with open("configs/scenarios.yaml") as f:
            data = yaml.safe_load(f)
        scenario = next(
            (item for item in data["scenarios"] if item["id"] == payload.scenario_id),
            None,
        )
        if scenario:
            question = scenario["question"]

    result = await run_analysis(question)
    await save_analysis(result)
    return result


@app.get("/history")
async def history():
    return await get_recent_analyses(limit=10)
