import unittest
from unittest.mock import AsyncMock, patch

from backend.models import ResearchBrief
from backend.agents.scout import run_scout


class ScoutAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_scout_returns_structured_research_brief(self):
        raw_narrative = "Market Position\nOpenAI is a leading enterprise AI provider."
        parsed_payload = {
            "question": "Should I compete with OpenAI in the enterprise AI market?",
            "key_facts": [
                "OpenAI fact 1",
                "OpenAI fact 2",
                "OpenAI fact 3",
                "OpenAI fact 4",
                "OpenAI fact 5",
            ],
            "market_position": "OpenAI has a strong enterprise position.",
            "recent_signals": [
                "OpenAI signal 1",
                "OpenAI signal 2",
                "OpenAI signal 3",
            ],
            "raw_narrative": raw_narrative,
        }

        with (
            patch(
                "backend.agents.scout._generate_grounded_research",
                new=AsyncMock(return_value=raw_narrative),
            ) as research_call,
            patch(
                "backend.agents.scout._parse_research_brief",
                new=AsyncMock(return_value=parsed_payload),
            ) as parse_call,
        ):
            result = await run_scout(parsed_payload["question"])

        self.assertIsInstance(result, ResearchBrief)
        self.assertEqual(result.question, parsed_payload["question"])
        self.assertGreaterEqual(len(result.key_facts), 5)
        self.assertGreaterEqual(len(result.recent_signals), 3)
        research_call.assert_awaited_once_with(parsed_payload["question"])
        parse_call.assert_awaited_once_with(parsed_payload["question"], raw_narrative)


if __name__ == "__main__":
    unittest.main()
