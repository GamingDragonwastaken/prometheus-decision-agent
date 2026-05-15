"""Pipeline orchestration for PROMETHEUS analyses."""

import time
import uuid

from backend.agents.challenger import run_challenger
from backend.agents.decision_gate import run_decision_gate
from backend.agents.scout import run_scout
from backend.agents.strategist import run_strategist
from backend.models import AnalysisResult


async def run_analysis(question: str) -> AnalysisResult:
    """Run all four PROMETHEUS agents and return a complete analysis."""
    start = time.time()
    analysis_id = str(uuid.uuid4())

    research = await run_scout(question)
    critique = await run_challenger(research)
    strategy, disagreements = await run_strategist(research, critique)
    decision = await run_decision_gate(research, critique, strategy)

    duration = time.time() - start

    return AnalysisResult(
        id=analysis_id,
        question=question,
        research=research,
        critique=critique,
        disagreements=disagreements,
        strategy=strategy,
        decision=decision,
        total_duration_seconds=round(duration, 2),
    )
