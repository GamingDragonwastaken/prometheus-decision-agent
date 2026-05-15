"""Challenger agent for adversarial review of Scout research."""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any

import google.generativeai as genai
import httpx
from dotenv import load_dotenv

from backend.models import CritiqueBrief, ResearchBrief


CHALLENGER_SYSTEM_PROMPT = """
You are PROMETHEUS Challenger — an adversarial intelligence analyst.

Your job: You have received a research brief from Scout. Your sole purpose is to challenge it rigorously before it reaches a decision-maker.

Rules:
- Identify assumptions Scout made without citing evidence
- Identify important information Scout likely missed or understated
- Offer alternative interpretations of the same facts
- Be specific. Vague skepticism is useless. Name the exact claim you are challenging and explain why.
- Only challenge what genuinely deserves challenge.

Output your critique with these sections:
1. Assumptions Challenged (2–4 items: what was stated as fact but not proven)
2. Gaps Identified (2–3 items: what's missing from the picture)
3. Alternative Interpretations (2–3 items: how the same facts could mean something different)
"""


load_dotenv()
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-3-flash-preview")
GEMINI_FALLBACK_MODEL_NAME = os.getenv("GEMINI_FALLBACK_MODEL_NAME", "gemini-2.5-flash")

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
CHALLENGER_MODEL = genai.GenerativeModel(
    model_name=GEMINI_MODEL_NAME,
    system_instruction=CHALLENGER_SYSTEM_PROMPT,
)
PARSER_MODEL = genai.GenerativeModel(model_name=GEMINI_MODEL_NAME)


class GeminiModelNotFoundError(RuntimeError):
    """Raised when a configured Gemini model is not available."""


class GeminiRateLimitError(RuntimeError):
    """Raised when a configured Gemini model is rate-limited."""


async def run_challenger(research: ResearchBrief) -> CritiqueBrief:
    """Challenge Scout research and return a structured critique."""
    formatted_brief = _format_research_brief(research)
    raw_critique = await _generate_challenge(formatted_brief)
    parsed_payload = await _parse_critique_brief(raw_critique)
    return CritiqueBrief.model_validate(parsed_payload)


def _format_research_brief(research: ResearchBrief) -> str:
    return (
        "Scout's research brief:\n\n"
        f"Market Position: {research.market_position}\n\n"
        "Key Facts:\n"
        + "\n".join(research.key_facts)
        + "\n\nRecent Signals:\n"
        + "\n".join(research.recent_signals)
    )


async def _generate_challenge(formatted_brief: str) -> str:
    try:
        response = await asyncio.to_thread(CHALLENGER_MODEL.generate_content, formatted_brief)
        return _response_text(response)
    except Exception as exc:
        if not (_looks_like_model_not_found(exc) or _looks_like_rate_limit(exc)):
            raise

    return await asyncio.to_thread(
        _generate_challenge_rest,
        os.getenv("GEMINI_API_KEY"),
        GEMINI_FALLBACK_MODEL_NAME,
        formatted_brief,
    )


async def _parse_critique_brief(raw_critique: str) -> dict[str, Any]:
    prompt = f"""
Extract structured JSON from this Challenger critique.

Return only valid JSON matching this schema:
{{
  "assumptions_challenged": ["string", "string"],
  "gaps_identified": ["string", "string"],
  "alternative_interpretations": ["string", "string"],
  "raw_narrative": "string"
}}

Rules:
- Preserve at least 2 specific assumptions challenged.
- Preserve at least 2 gaps identified.
- Preserve at least 2 alternative interpretations.
- Each assumption must name the exact Scout claim being challenged when possible.
- The raw_narrative field must contain the original critique verbatim.

Challenger critique:
{raw_critique}
"""

    try:
        response = await asyncio.to_thread(
            PARSER_MODEL.generate_content,
            prompt,
            generation_config={"temperature": 0.1, "response_mime_type": "application/json"},
        )
        return _json_from_text(_response_text(response))
    except Exception as exc:
        if not (_looks_like_model_not_found(exc) or _looks_like_rate_limit(exc)):
            raise

    return await asyncio.to_thread(
        _parse_critique_brief_rest,
        os.getenv("GEMINI_API_KEY"),
        GEMINI_FALLBACK_MODEL_NAME,
        prompt,
    )


def _generate_challenge_rest(api_key: str | None, model_name: str, formatted_brief: str) -> str:
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in the environment.")

    response = _post_generate_content(
        api_key=api_key,
        model_name=model_name,
        payload={
            "systemInstruction": {"parts": [{"text": CHALLENGER_SYSTEM_PROMPT}]},
            "contents": [{"parts": [{"text": formatted_brief}]}],
        },
    )
    return _text_from_rest_response(response)


def _parse_critique_brief_rest(api_key: str | None, model_name: str, prompt: str) -> dict[str, Any]:
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in the environment.")

    response = _post_generate_content(
        api_key=api_key,
        model_name=model_name,
        payload={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        },
    )
    return _json_from_text(_text_from_rest_response(response))


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


def _json_from_text(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    return json.loads(cleaned)


def _looks_like_model_not_found(exc: Exception) -> bool:
    message = str(exc).lower()
    return "404" in message or "not found" in message


def _looks_like_rate_limit(exc: Exception) -> bool:
    message = str(exc).lower()
    return "429" in message or "too many requests" in message or "resource exhausted" in message
