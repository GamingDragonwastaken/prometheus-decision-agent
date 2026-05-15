import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from backend.models import (
    AnalysisResult,
    CritiqueBrief,
    DecisionBrief,
    DisagreementRow,
    ResearchBrief,
    StrategicBrief,
)


def sample_analysis_result() -> AnalysisResult:
    research = ResearchBrief(
        question="Should I compete with OpenAI in enterprise AI?",
        market_position="OpenAI is a strong enterprise AI incumbent.",
        key_facts=[
            "OpenAI has enterprise distribution.",
            "OpenAI sells API access.",
            "OpenAI has deployment services.",
            "OpenAI has security controls.",
            "OpenAI faces Anthropic competition.",
        ],
        recent_signals=[
            "OpenAI launched deployment services.",
            "Anthropic gained share.",
            "Enterprises adopted multi-model procurement.",
        ],
        raw_narrative="Scout narrative",
    )
    critique = CritiqueBrief(
        assumptions_challenged=[
            "The dominance claim relies on usage rather than retention.",
            "Deployment services may signal product complexity.",
        ],
        gaps_identified=["Missing churn data.", "Missing win-rate data."],
        alternative_interpretations=[
            "Deployment services may be a margin drag.",
            "Enterprise adoption may be experimentation.",
        ],
        raw_narrative="Critique narrative",
    )
    disagreements = [
        DisagreementRow(
            scout_claim=f"Scout claim {index}",
            challenger_objection=f"Challenger objection {index}",
            strategist_resolution=f"Strategist resolution {index}",
        )
        for index in range(1, 4)
    ]
    strategy = StrategicBrief(
        question=research.question,
        threat_score=8,
        opportunity_score=6,
        threat_score_rationale="OpenAI is a serious incumbent.",
        opportunity_score_rationale="Focused workflows remain open.",
        recommendations=[
            "Interview 15 buyers within 30 days.",
            "Build one workflow prototype within 45 days.",
            "Benchmark against OpenAI within 60 days.",
        ],
        executive_summary="OpenAI is strong. A narrow wedge may work.",
        timestamp=datetime.now(),
    )
    decision = DecisionBrief(
        decision="MONITOR",
        confidence_pct=72,
        primary_condition="Fifteen target buyers must confirm urgent unmet workflow needs within 30 days.",
        secondary_condition="Prototype must beat OpenAI by 20% on task completion time.",
        revisit_trigger="Revisit if OpenAI ships the target workflow before prototype completion.",
        rationale="The strongest objection is that OpenAI usage may not equal retention.",
    )
    return AnalysisResult(
        id="analysis-1",
        question=research.question,
        research=research,
        critique=critique,
        disagreements=disagreements,
        strategy=strategy,
        decision=decision,
        total_duration_seconds=12.34,
    )


class OrchestratorTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_analysis_returns_complete_analysis_result(self):
        result = sample_analysis_result()

        with (
            patch("backend.orchestrator.run_scout", new=AsyncMock(return_value=result.research)),
            patch("backend.orchestrator.run_challenger", new=AsyncMock(return_value=result.critique)),
            patch(
                "backend.orchestrator.run_strategist",
                new=AsyncMock(return_value=(result.strategy, result.disagreements)),
            ),
            patch("backend.orchestrator.run_decision_gate", new=AsyncMock(return_value=result.decision)),
        ):
            from backend.orchestrator import run_analysis

            analysis = await run_analysis(result.question)

        self.assertEqual(analysis.question, result.question)
        self.assertEqual(len(analysis.disagreements), 3)
        self.assertIn(analysis.decision.decision, {"GO", "NO-GO", "MONITOR"})
        self.assertGreaterEqual(analysis.total_duration_seconds, 0)


class DatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def test_save_analysis_and_get_recent_analyses(self):
        from backend.database import get_recent_analyses, init_db, save_analysis

        with tempfile.TemporaryDirectory() as tmp_dir:
            old_db_path = os.environ.get("DB_PATH")
            os.environ["DB_PATH"] = os.path.join(tmp_dir, "prometheus.db")
            try:
                await init_db()
                await save_analysis(sample_analysis_result())
                rows = await get_recent_analyses(limit=10)
            finally:
                if old_db_path is None:
                    os.environ.pop("DB_PATH", None)
                else:
                    os.environ["DB_PATH"] = old_db_path

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "analysis-1")
        self.assertEqual(rows[0]["decision"], "MONITOR")
        self.assertIn("disagreements", rows[0])


class FastApiTests(unittest.TestCase):
    def test_health_scenarios_analyze_and_history(self):
        from backend.main import app

        result = sample_analysis_result()
        with (
            patch("backend.main.run_analysis", new=AsyncMock(return_value=result)),
            patch("backend.main.save_analysis", new=AsyncMock()),
            patch("backend.main.get_recent_analyses", new=AsyncMock(return_value=[{"id": result.id}])),
            TestClient(app) as client,
        ):
            health = client.get("/health")
            scenarios = client.get("/scenarios")
            analysis = client.post("/analyze", json={"question": result.question})
            history = client.get("/history")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["agents"], 4)
        self.assertEqual(scenarios.status_code, 200)
        self.assertEqual(len(scenarios.json()), 3)
        self.assertEqual(analysis.status_code, 200)
        self.assertIn(analysis.json()["decision"]["decision"], {"GO", "NO-GO", "MONITOR"})
        self.assertEqual(len(analysis.json()["disagreements"]), 3)
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json(), [{"id": result.id}])


if __name__ == "__main__":
    unittest.main()
