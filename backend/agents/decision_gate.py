"""Decision Gate agent for autonomous GO / NO-GO / MONITOR decisions."""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any

import google.generativeai as genai
from dotenv import load_dotenv

from backend.llm import (
    looks_like_model_not_found,
    looks_like_rate_limit,
    post_generate_content,
    response_text,
    text_from_rest_response,
)
from backend.models import CritiqueBrief, DecisionBrief, ResearchBrief, StrategicBrief


DECISION_GATE_SYSTEM_PROMPT = """
You are PROMETHEUS Decision Gate — the final autonomous decision-maker.

You have received the full intelligence picture: Scout's research, Challenger's critique,
and Strategist's synthesis. Your job is not to summarize. Your job is to DECIDE.

Rules:
- Choose exactly one: GO (pursue this), NO-GO (do not pursue), MONITOR (insufficient data).
- Confidence calibration:
  * Challenger found 3+ major unresolved gaps -> confidence max 65
  * Challenger found 1-2 gaps that Strategist resolved -> confidence up to 82
  * Challenger's objections were minor and all resolved -> confidence up to 90
  * NEVER exceed 92 - no business decision has perfect information
- Primary condition: the single most critical assumption that must hold. Be specific.
  Not "market must be viable" but "target segment ARR growth must exceed 15% YoY for 2
  consecutive years."
- Revisit trigger: one specific, observable event. Not "if things change" but
  "if [named competitor] raises Series B above $200M."
- Rationale: name Challenger's STRONGEST specific objection (quote or paraphrase
  precisely) and explain why the decision holds or doesn't hold despite it.

Respond with valid JSON only. No markdown, no commentary outside the JSON object.

Schema:
{
  "decision": "GO" | "NO-GO" | "MONITOR",
  "confidence_pct": <integer 0-100>,
  "primary_condition": "<one specific sentence>",
  "secondary_condition": "<one specific sentence>",
  "revisit_trigger": "<one specific, observable sentence>",
  "rationale": "<2-3 sentences naming Challenger's strongest objection explicitly>"
}
"""


load_dotenv()
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-3-flash-preview")
GEMINI_FALLBACK_MODEL_NAME = os.getenv("GEMINI_FALLBACK_MODEL_NAME", "gemini-2.5-flash")
GENERATION_CONFIG = {
    "temperature": 0.2,
    "response_mime_type": "application/json",
}
VALID_DECISIONS = {"GO", "NO-GO", "MONITOR"}

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
DECISION_GATE_MODEL = genai.GenerativeModel(
    model_name=GEMINI_MODEL_NAME,
    generation_config=GENERATION_CONFIG,
    system_instruction=DECISION_GATE_SYSTEM_PROMPT,
)


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
        return response_text(response)
    except Exception as exc:
        if not (looks_like_model_not_found(exc) or looks_like_rate_limit(exc)):
            raise

    return await asyncio.to_thread(
        _generate_decision_rest,
        os.getenv("GEMINI_API_KEY"),
        GEMINI_FALLBACK_MODEL_NAME,
        decision_context,
    )


def _parse_decision_response(raw_decision: str) -> DecisionBrief:
    payload = _safe_json_load(raw_decision)
    return DecisionBrief(
        decision=_valid_decision(payload.get("decision")),
        confidence_pct=_clamp_confidence(payload.get("confidence_pct")),
        primary_condition=_field_or_fallback(
            payload,
            "primary_condition",
            "Primary condition was missing; require a corrected Decision Gate response before acting.",
        ),
        secondary_condition=_field_or_fallback(
            payload,
            "secondary_condition",
            "Secondary condition was missing; require a corrected Decision Gate response before acting.",
        ),
        revisit_trigger=_field_or_fallback(
            payload,
            "revisit_trigger",
            "Revisit trigger was missing; require a corrected Decision Gate response before acting.",
        ),
        rationale=_field_or_fallback(
            payload,
            "rationale",
            "Rationale was missing; require a corrected Decision Gate response before acting.",
        ),
    )


def _safe_json_load(raw: str) -> dict[str, Any]:
    """Parse Decision Gate JSON, tolerating fences or stray prose."""
    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        loaded = json.loads(cleaned)
        if isinstance(loaded, dict):
            return loaded
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            loaded = json.loads(match.group(0))
            if isinstance(loaded, dict):
                return loaded
        except json.JSONDecodeError:
            pass
    return {}


def _valid_decision(value: Any) -> str:
    decision = str(value or "").strip().upper()
    if decision not in VALID_DECISIONS:
        return "MONITOR"
    return decision


def _clamp_confidence(value: Any) -> int:
    try:
        confidence = int(value)
    except (TypeError, ValueError):
        confidence = 0
    return max(0, min(100, confidence))


def _field_or_fallback(payload: dict[str, Any], key: str, fallback: str) -> str:
    value = str(payload.get(key, "") or "").strip()
    return value or fallback


def _generate_decision_rest(api_key: str | None, model_name: str, decision_context: str) -> str:
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in the environment.")

    response = post_generate_content(
        api_key=api_key,
        model_name=model_name,
        payload={
            "systemInstruction": {"parts": [{"text": DECISION_GATE_SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": decision_context}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        },
    )
    return text_from_rest_response(response)
