import unittest
from unittest.mock import AsyncMock, patch

from backend.agents.challenger import run_challenger
from backend.models import CritiqueBrief, ResearchBrief


class ChallengerAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_challenger_returns_structured_critique_brief(self):
        research = ResearchBrief(
            question="Should I compete with OpenAI in enterprise AI?",
            market_position="OpenAI has a strong enterprise position.",
            key_facts=[
                "OpenAI fact 1",
                "OpenAI fact 2",
                "OpenAI fact 3",
                "OpenAI fact 4",
                "OpenAI fact 5",
            ],
            recent_signals=[
                "OpenAI signal 1",
                "OpenAI signal 2",
                "OpenAI signal 3",
            ],
            raw_narrative="Scout narrative",
        )
        raw_critique = "Assumptions Challenged\nThe enterprise position claim needs support."
        parsed_payload = {
            "assumptions_challenged": [
                "The claim that OpenAI has a strong enterprise position needs customer retention evidence.",
                "The API ARR claim does not prove enterprise profitability.",
            ],
            "gaps_identified": [
                "Missing customer churn data.",
                "Missing competitor win-rate data.",
            ],
            "alternative_interpretations": [
                "High adoption could reflect experimentation rather than durable enterprise commitment.",
                "Deployment investments could signal product gaps rather than strength.",
            ],
            "raw_narrative": raw_critique,
        }

        expected_formatted = (
            "Scout's research brief:\n\n"
            f"Market Position: {research.market_position}\n\n"
            "Key Facts:\n"
            + "\n".join(research.key_facts)
            + "\n\nRecent Signals:\n"
            + "\n".join(research.recent_signals)
        )

        with (
            patch(
                "backend.agents.challenger._generate_challenge",
                new=AsyncMock(return_value=raw_critique),
            ) as challenge_call,
            patch(
                "backend.agents.challenger._parse_critique_brief",
                new=AsyncMock(return_value=parsed_payload),
            ) as parse_call,
        ):
            result = await run_challenger(research)

        self.assertIsInstance(result, CritiqueBrief)
        self.assertGreaterEqual(len(result.assumptions_challenged), 2)
        self.assertIn("enterprise position", result.assumptions_challenged[0])
        challenge_call.assert_awaited_once_with(expected_formatted)
        parse_call.assert_awaited_once_with(raw_critique)


if __name__ == "__main__":
    unittest.main()
