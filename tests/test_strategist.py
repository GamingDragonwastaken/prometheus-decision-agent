import json
import unittest
from unittest.mock import AsyncMock, patch

from backend.agents.strategist import run_strategist
from backend.models import CritiqueBrief, DisagreementRow, ResearchBrief, StrategicBrief


class StrategistAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_strategist_returns_strategy_and_disagreement_rows(self):
        research = ResearchBrief(
            question="Should I compete with OpenAI in the enterprise AI market?",
            market_position="OpenAI has a strong enterprise AI position.",
            key_facts=[
                "OpenAI has enterprise seats across major companies.",
                "OpenAI sells API access to developers.",
                "OpenAI launched a deployment services unit.",
                "OpenAI has security controls for enterprise buyers.",
                "OpenAI faces Anthropic in enterprise LLM spend.",
            ],
            recent_signals=[
                "OpenAI launched deployment services.",
                "OpenAI expanded enterprise security features.",
                "Anthropic gained enterprise share.",
            ],
            raw_narrative="Scout narrative",
        )
        critique = CritiqueBrief(
            assumptions_challenged=[
                "The strong enterprise position claim lacks retention evidence.",
                "The deployment services claim may indicate product complexity.",
            ],
            gaps_identified=[
                "Missing buyer churn data.",
                "Missing competitor win-rate data.",
            ],
            alternative_interpretations=[
                "Deployment services could be a margin drag.",
                "Enterprise adoption may be experimentation.",
            ],
            raw_narrative="Critique narrative",
        )
        strategist_response = json.dumps(
            {
                "threat_score": 12,
                "threat_rationale": "OpenAI is a major incumbent with distribution, models, and enterprise credibility.",
                "opportunity_score": 0,
                "opportunity_rationale": "Focused vertical enterprise workflows remain underserved by broad platforms.",
                "recommendations": [
                    "Interview 15 regulated-enterprise AI buyers within 30 days to isolate two unmet workflow needs.",
                    "Build a security-first proof of concept for one selected workflow within 45 days to validate buyer urgency.",
                    "Benchmark against OpenAI and Anthropic on the selected workflow within 60 days to prove a measurable advantage.",
                ],
                "executive_summary": "OpenAI is a serious threat, but broad coverage leaves room for focused enterprise workflows. Enter only if buyer interviews validate a narrow wedge. Compete on workflow depth, not general model capability.",
                "disagreements": [
                    {
                        "scout_claim": "OpenAI has a strong enterprise AI position",
                        "challenger_objection": "The claim lacks retention evidence",
                        "strategist_resolution": "Treat as strong distribution, not proven durable retention.",
                    },
                    {
                        "scout_claim": "OpenAI launched deployment services",
                        "challenger_objection": "This may indicate product complexity",
                        "strategist_resolution": "Count it as both go-to-market strength and implementation-friction signal.",
                    },
                    {
                        "scout_claim": "Anthropic gained enterprise share",
                        "challenger_objection": "Share shift may reflect multi-model procurement",
                        "strategist_resolution": "Assume buyers are diversifying rather than fully abandoning OpenAI.",
                    },
                ],
            }
        )

        with patch(
            "backend.agents.strategist._generate_strategy",
            new=AsyncMock(return_value=strategist_response),
        ) as strategy_call:
            strategy, disagreements = await run_strategist(research, critique)

        self.assertIsInstance(strategy, StrategicBrief)
        # Out-of-range scores are clamped to [1, 10].
        self.assertEqual(strategy.threat_score, 10)
        self.assertEqual(strategy.opportunity_score, 1)
        self.assertEqual(len(strategy.recommendations), 3)
        self.assertEqual(len(disagreements), 3)
        self.assertTrue(strategy.executive_summary)
        self.assertLessEqual(len([s for s in strategy.executive_summary.split(".") if s.strip()]), 3)
        self.assertTrue(all(isinstance(row, DisagreementRow) for row in disagreements))
        self.assertTrue(all(row.scout_claim for row in disagreements))
        self.assertTrue(all(row.challenger_objection for row in disagreements))
        self.assertTrue(all(row.strategist_resolution for row in disagreements))
        strategy_call.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
