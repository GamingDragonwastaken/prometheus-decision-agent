"""FastAPI backend entrypoint for PROMETHEUS."""

import os
from contextlib import asynccontextmanager

import yaml
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import get_recent_analyses, init_db, save_analysis
from backend.models import AnalysisRequest, AnalysisResult
from backend.orchestrator import run_analysis


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="PROMETHEUS", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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
async def analyze(request: AnalysisRequest):
    question = request.question
    if request.scenario_id:
        with open("configs/scenarios.yaml") as f:
            data = yaml.safe_load(f)
        scenario = next(
            (item for item in data["scenarios"] if item["id"] == request.scenario_id),
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
