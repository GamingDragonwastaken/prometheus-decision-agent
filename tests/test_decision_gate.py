import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from backend.agents.decision_gate import run_decision_gate
from backend.models import CritiqueBrief, DecisionBrief, ResearchBrief, StrategicBrief


class DecisionGateAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_decision_gate_returns_valid_decision_brief(self):
        research = ResearchBrief(
            question="Should I compete with OpenAI in the enterprise AI market?",
            market_position="OpenAI is a dominant enterprise AI incumbent.",
            key_facts=[
                "OpenAI has enterprise distribution.",
                "OpenAI has API revenue.",
                "OpenAI has deployment services.",
                "OpenAI has enterprise security controls.",
                "OpenAI faces Anthropic competition.",
            ],
            recent_signals=[
                "OpenAI launched deployment services.",
                "Anthropic gained enterprise share.",
                "Enterprises adopted multi-model procurement.",
            ],
            raw_narrative="Scout narrative",
        )
        critique = CritiqueBrief(
            assumptions_challenged=[
                "The OpenAI dominance claim relies on usage metrics rather than paid production retention.",
                "The deployment-services claim may indicate product complexity rather than strength.",
            ],
            gaps_identified=[
                "Missing buyer churn data.",
                "Missing competitor win-rate data.",
            ],
            alternative_interpretations=[
                "Deployment services may be a margin drag.",
                "Enterprise adoption may be experimentation.",
            ],
            raw_narrative="Critique narrative",
        )
        strategy = StrategicBrief(
            question=research.question,
            threat_score=8,
            opportunity_score=6,
            threat_score_rationale="OpenAI has distribution and enterprise credibility.",
            opportunity_score_rationale="Narrow vertical workflows remain underserved.",
            recommendations=[
                "Interview 15 regulated enterprise buyers within 30 days.",
                "Prototype one narrow workflow within 45 days.",
                "Benchmark against OpenAI within 60 days.",
            ],
            executive_summary="OpenAI is a serious incumbent. A narrow wedge may still be viable.",
            timestamp=datetime.now(),
        )
        import json

        decision_response = json.dumps(
            {
                # An invalid decision falls back to MONITOR; confidence is clamped to [0, 100].
                "decision": "LAUNCH",
                "confidence_pct": 104,
                "primary_condition": "Target regulated buyers must confirm at least 3 urgent workflow gaps in 15 interviews within 30 days.",
                "secondary_condition": "Prototype must beat OpenAI on the selected workflow by 20% in task completion time.",
                "revisit_trigger": "Revisit if Anthropic or OpenAI launches a dedicated regulated-enterprise workflow product before prototype completion.",
                "rationale": "Challenger's strongest objection is that the OpenAI dominance claim relies on usage metrics rather than paid production retention. The decision remains cautious because this gap prevents a high-confidence GO.",
            }
        )

        with patch(
            "backend.agents.decision_gate._generate_decision",
            new=AsyncMock(return_value=decision_response),
        ) as decision_call:
            decision = await run_decision_gate(research, critique, strategy)

        self.assertIsInstance(decision, DecisionBrief)
        self.assertEqual(decision.decision, "MONITOR")
        self.assertEqual(decision.confidence_pct, 100)
        self.assertIn("15 interviews", decision.primary_condition)
        self.assertIn("OpenAI dominance claim", decision.rationale)
        decision_call.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
