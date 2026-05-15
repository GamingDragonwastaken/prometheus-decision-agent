"""Strategist agent for synthesizing research and critique."""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Any

import google.generativeai as genai
import httpx
from dotenv import load_dotenv

from backend.models import CritiqueBrief, DisagreementRow, ResearchBrief, StrategicBrief


STRATEGIST_SYSTEM_PROMPT = """
You are PROMETHEUS Strategist — a senior strategy consultant producing the final intelligence brief.

You have received Scout's research AND Challenger's critique. Synthesize into a calibrated
strategic brief for a senior executive making a real decision.

Rules:
- Where Challenger's challenge is strong and Scout didn't support the claim with evidence,
  reduce confidence in that finding.
- Where Scout's data is specific and recent and Challenger's objection is weak, maintain it.
- Scores must reflect reality. 7+ means serious. Reserve 9–10 for genuinely extreme situations.
- Recommendations must be specific and immediately actionable. No platitudes like "monitor
  the situation" or "consider partnerships."
- Executive summary: 3 sentences maximum. Make every word earn its place.
- RESOLVED_ lines are machine-parsed. Follow the format exactly — no deviations.

Respond in this EXACT format (each field on its own line, no markdown, no extra text):
THREAT_SCORE: [integer 1-10]
THREAT_RATIONALE: [one sentence]
OPPORTUNITY_SCORE: [integer 1-10]
OPPORTUNITY_RATIONALE: [one sentence]
RECOMMENDATION_1: [specific action — what, by when, expected outcome]
RECOMMENDATION_2: [specific action — what, by when, expected outcome]
RECOMMENDATION_3: [specific action — what, by when, expected outcome]
EXECUTIVE_SUMMARY: [3 sentences maximum]
RESOLVED_1: [Scout claim] | [Challenger objection] | [How resolved]
RESOLVED_2: [Scout claim] | [Challenger objection] | [How resolved]
RESOLVED_3: [Scout claim] | [Challenger objection] | [How resolved]
"""


load_dotenv()
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-3-flash-preview")
GEMINI_FALLBACK_MODEL_NAME = os.getenv("GEMINI_FALLBACK_MODEL_NAME", "gemini-2.5-flash")
GENERATION_CONFIG = {"temperature": 0.4}

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
STRATEGIST_MODEL = genai.GenerativeModel(
    model_name=GEMINI_MODEL_NAME,
    generation_config=GENERATION_CONFIG,
    system_instruction=STRATEGIST_SYSTEM_PROMPT,
)


class GeminiModelNotFoundError(RuntimeError):
    """Raised when a configured Gemini model is not available."""


class GeminiRateLimitError(RuntimeError):
    """Raised when a configured Gemini model is rate-limited."""


async def run_strategist(
    research: ResearchBrief,
    critique: CritiqueBrief,
) -> tuple[StrategicBrief, list[DisagreementRow]]:
    """Synthesize Scout and Challenger briefs into a final strategy."""
    combined_brief = _format_combined_brief(research, critique)
    raw_strategy = await _generate_strategy(combined_brief)
    return _parse_strategy_response(research.question, raw_strategy)


def _format_combined_brief(research: ResearchBrief, critique: CritiqueBrief) -> str:
    return f"""
SCOUT'S RESEARCH BRIEF:
Market Position: {research.market_position}

Key Facts:
{chr(10).join(f"- {fact}" for fact in research.key_facts)}

Recent Signals:
{chr(10).join(f"- {signal}" for signal in research.recent_signals)}

CHALLENGER'S CRITIQUE:
Assumptions Challenged:
{chr(10).join(f"- {assumption}" for assumption in critique.assumptions_challenged)}

Gaps Identified:
{chr(10).join(f"- {gap}" for gap in critique.gaps_identified)}

Alternative Interpretations:
{chr(10).join(f"- {interpretation}" for interpretation in critique.alternative_interpretations)}

Synthesize the above into a calibrated strategic brief.
""".strip()


async def _generate_strategy(combined_brief: str) -> str:
    try:
        response = await asyncio.to_thread(STRATEGIST_MODEL.generate_content, combined_brief)
        return _response_text(response)
    except Exception as exc:
        if not (_looks_like_model_not_found(exc) or _looks_like_rate_limit(exc)):
            raise

    return await asyncio.to_thread(
        _generate_strategy_rest,
        os.getenv("GEMINI_API_KEY"),
        GEMINI_FALLBACK_MODEL_NAME,
        combined_brief,
    )


def _parse_strategy_response(
    question: str,
    raw_strategy: str,
) -> tuple[StrategicBrief, list[DisagreementRow]]:
    fields: dict[str, str] = {}
    for line in raw_strategy.splitlines():
        stripped = line.strip()
        if not stripped or ": " not in stripped:
            continue
        field_name, value = stripped.split(": ", maxsplit=1)
        fields[field_name.strip()] = value.strip()

    recommendations = [
        fields.get(f"RECOMMENDATION_{index}", _fallback_recommendation(index))
        for index in range(1, 4)
    ]
    disagreements = [
        _parse_disagreement_row(fields.get(f"RESOLVED_{index}", ""), index)
        for index in range(1, 4)
    ]

    strategy = StrategicBrief(
        question=question,
        threat_score=_clamp_score(fields.get("THREAT_SCORE")),
        opportunity_score=_clamp_score(fields.get("OPPORTUNITY_SCORE")),
        threat_score_rationale=fields.get(
            "THREAT_RATIONALE",
            "Threat score rationale was not provided by Strategist.",
        ),
        opportunity_score_rationale=fields.get(
            "OPPORTUNITY_RATIONALE",
            "Opportunity score rationale was not provided by Strategist.",
        ),
        recommendations=recommendations,
        executive_summary=fields.get(
            "EXECUTIVE_SUMMARY",
            "Strategist did not provide an executive summary.",
        ),
        timestamp=datetime.now(),
    )
    return strategy, disagreements


def _parse_disagreement_row(value: str, index: int) -> DisagreementRow:
    parts = [part.strip() for part in value.split(" | ", maxsplit=2)]
    if len(parts) != 3 or any(not part for part in parts):
        return DisagreementRow(
            scout_claim=f"Unparsed Scout claim from RESOLVED_{index}: {value or 'missing'}",
            challenger_objection=f"Unparsed Challenger objection from RESOLVED_{index}: {value or 'missing'}",
            strategist_resolution=f"Strategist output for RESOLVED_{index} was malformed; review raw model output.",
        )

    return DisagreementRow(
        scout_claim=parts[0],
        challenger_objection=parts[1],
        strategist_resolution=parts[2],
    )


def _clamp_score(value: str | None) -> int:
    try:
        score = int(value or "")
    except ValueError:
        score = 5
    return max(1, min(10, score))


def _fallback_recommendation(index: int) -> str:
    return (
        f"RECOMMENDATION_{index} was missing; request a corrected Strategist response "
        "before using this brief for a decision."
    )


def _generate_strategy_rest(api_key: str | None, model_name: str, combined_brief: str) -> str:
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in the environment.")

    response = _post_generate_content(
        api_key=api_key,
        model_name=model_name,
        payload={
            "systemInstruction": {"parts": [{"text": STRATEGIST_SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": combined_brief}]}],
            "generationConfig": {"temperature": 0.4},
        },
    )
    return _text_from_rest_response(response)


def _post_generate_content(api_key: str, model_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    response = httpx.post(url, params={"key": api_key}, json=payload, timeout=90)
    if response.status_code == 404:
        raise GeminiModelNotFoundError(response.text)
    if response.status_code == 429:
        raise GeminiRateLimitError(response.text)
    response.raise_for_status()
    return response.json()


def _response_text(response: Any) -> str:
    text = getattr(response, "text", "")
    if not text:
        raise RuntimeError("Gemini returned an empty response.")
    return text


def _text_from_rest_response(response: dict[str, Any]) -> str:
    candidates = response.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned no candidates.")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise RuntimeError("Gemini returned an empty response.")
    return text


def _looks_like_model_not_found(exc: Exception) -> bool:
    message = str(exc).lower()
    return "404" in message or "not found" in message


def _looks_like_rate_limit(exc: Exception) -> bool:
    message = str(exc).lower()
    return "429" in message or "too many requests" in message or "resource exhausted" in message
