"""Decision Gate agent for autonomous GO / NO-GO / MONITOR decisions."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import google.generativeai as genai
import httpx
from dotenv import load_dotenv

from backend.models import CritiqueBrief, DecisionBrief, ResearchBrief, StrategicBrief


DECISION_GATE_SYSTEM_PROMPT = """
You are PROMETHEUS Decision Gate — the final autonomous decision-maker.

You have received the full intelligence picture: Scout's research, Challenger's critique,
and Strategist's synthesis. Your job is not to summarize. Your job is to DECIDE.

Rules:
- Choose exactly one: GO (pursue this), NO-GO (do not pursue), MONITOR (insufficient data).
- Confidence calibration:
  * Challenger found 3+ major unresolved gaps → confidence max 65%
  * Challenger found 1-2 gaps that Strategist resolved → confidence up to 82%
  * Challenger's objections were minor and all resolved → confidence up to 90%
  * NEVER exceed 92% — no business decision has perfect information
- Primary condition: The single most critical assumption that must hold for your decision
  to stand. Be specific — not "market must be viable" but "target segment ARR growth must
  exceed 15% YoY for 2 consecutive years."
- Revisit trigger: One specific, observable event. Not "if things change" but
  "if [named competitor] raises Series B above $200M" or "if [named regulation] passes."
- Rationale: Name Challenger's STRONGEST specific objection (quote it or paraphrase precisely)
  and explain why the decision holds (or doesn't hold) despite it.

Respond in this EXACT format (machine-parsed, no deviations, no markdown):
DECISION: [GO / NO-GO / MONITOR]
CONFIDENCE: [integer 0-100]
PRIMARY_CONDITION: [one specific sentence]
SECONDARY_CONDITION: [one specific sentence]
REVISIT_TRIGGER: [one specific, observable sentence]
RATIONALE: [2-3 sentences naming Challenger's strongest objection explicitly]
"""


load_dotenv()
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-3-flash-preview")
GEMINI_FALLBACK_MODEL_NAME = os.getenv("GEMINI_FALLBACK_MODEL_NAME", "gemini-2.5-flash")
GENERATION_CONFIG = {"temperature": 0.2}
VALID_DECISIONS = {"GO", "NO-GO", "MONITOR"}

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
DECISION_GATE_MODEL = genai.GenerativeModel(
    model_name=GEMINI_MODEL_NAME,
    generation_config=GENERATION_CONFIG,
    system_instruction=DECISION_GATE_SYSTEM_PROMPT,
)


class GeminiModelNotFoundError(RuntimeError):
    """Raised when a configured Gemini model is not available."""


class GeminiRateLimitError(RuntimeError):
    """Raised when a configured Gemini model is rate-limited."""


async def run_decision_gate(
    research: ResearchBrief,
    critique: CritiqueBrief,
    strategy: StrategicBrief,
) -> DecisionBrief:
    """Produce the final autonomous decision from all prior agent outputs."""
    decision_context = _format_decision_context(research, critique, strategy)
    raw_decision = await _generate_decision(decision_context)
    return _parse_decision_response(raw_decision)


def _format_decision_context(
    research: ResearchBrief,
    critique: CritiqueBrief,
    strategy: StrategicBrief,
) -> str:
    return f"""
STRATEGIC CONTEXT:
Decision question: {strategy.question}
Threat Score: {strategy.threat_score}/10 — {strategy.threat_score_rationale}
Opportunity Score: {strategy.opportunity_score}/10 — {strategy.opportunity_score_rationale}

SCOUT'S RESEARCH SUMMARY:
{research.market_position}
Key facts gathered: {len(research.key_facts)}

CHALLENGER'S STRONGEST OBJECTIONS:
{chr(10).join(f"- {assumption}" for assumption in critique.assumptions_challenged)}

STRATEGIST'S RECOMMENDATIONS:
{chr(10).join(f"{index + 1}. {recommendation}" for index, recommendation in enumerate(strategy.recommendations))}

STRATEGIST'S EXECUTIVE SUMMARY:
{strategy.executive_summary}

Make the autonomous decision.
""".strip()


async def _generate_decision(decision_context: str) -> str:
    try:
        response = await asyncio.to_thread(DECISION_GATE_MODEL.generate_content, decision_context)
        return _response_text(response)
    except Exception as exc:
        if not (_looks_like_model_not_found(exc) or _looks_like_rate_limit(exc)):
            raise

    return await asyncio.to_thread(
        _generate_decision_rest,
        os.getenv("GEMINI_API_KEY"),
        GEMINI_FALLBACK_MODEL_NAME,
        decision_context,
    )


def _parse_decision_response(raw_decision: str) -> DecisionBrief:
    fields: dict[str, str] = {}
    for line in raw_decision.splitlines():
        stripped = line.strip()
        if not stripped or ": " not in stripped:
            continue
        field_name, value = stripped.split(": ", maxsplit=1)
        fields[field_name.strip()] = value.strip()

    return DecisionBrief(
        decision=_valid_decision(fields.get("DECISION")),
        confidence_pct=_clamp_confidence(fields.get("CONFIDENCE")),
        primary_condition=_field_or_fallback(
            fields,
            "PRIMARY_CONDITION",
            "Primary condition was missing; require a corrected Decision Gate response before acting.",
        ),
        secondary_condition=_field_or_fallback(
            fields,
            "SECONDARY_CONDITION",
            "Secondary condition was missing; require a corrected Decision Gate response before acting.",
        ),
        revisit_trigger=_field_or_fallback(
            fields,
            "REVISIT_TRIGGER",
            "Revisit trigger was missing; require a corrected Decision Gate response before acting.",
        ),
        rationale=_field_or_fallback(
            fields,
            "RATIONALE",
            "Rationale was missing; require a corrected Decision Gate response before acting.",
        ),
    )


def _valid_decision(value: str | None) -> str:
    decision = (value or "").strip()
    if decision not in VALID_DECISIONS:
        return "MONITOR"
    return decision


def _clamp_confidence(value: str | None) -> int:
    try:
        confidence = int(value or "")
    except ValueError:
        confidence = 0
    return max(0, min(100, confidence))


def _field_or_fallback(fields: dict[str, str], key: str, fallback: str) -> str:
    value = fields.get(key, "").strip()
    return value or fallback


def _generate_decision_rest(api_key: str | None, model_name: str, decision_context: str) -> str:
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in the environment.")

    response = _post_generate_content(
        api_key=api_key,
        model_name=model_name,
        payload={
            "systemInstruction": {"parts": [{"text": DECISION_GATE_SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": decision_context}]}],
            "generationConfig": {"temperature": 0.2},
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
