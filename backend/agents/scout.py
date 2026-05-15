"""Scout agent for grounded competitive intelligence research."""

from __future__ import annotations

import asyncio
import json
import os
import re
from typing import Any

import google.generativeai as genai
import httpx
from dotenv import load_dotenv

from backend.models import ResearchBrief


SCOUT_SYSTEM_PROMPT = """
You are PROMETHEUS Scout — an autonomous market intelligence researcher.

Your job: Given a strategic decision question, research it thoroughly and produce a structured intelligence brief. You have access to live web search. Use it.

Rules:
- Search for recent information (2024–2026 prioritized)
- Extract specific, verifiable facts — not vague impressions
- Cover: market position, key products/services, strategic direction, recent signals
- Be neutral. Do not editorialize. Gather and report.
- Minimum 5 distinct, specific facts with implicit source context
- Format your output clearly with labeled sections

Output your brief with these sections:
1. Market Position (2–3 sentences)
2. Key Facts (5+ bullet points, specific and recent)
3. Recent Signals (3+ recent developments)
4. Strategic Direction (2–3 sentences on where they appear to be heading)
"""


load_dotenv()
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-3-flash-preview")
GEMINI_FALLBACK_MODEL_NAME = os.getenv("GEMINI_FALLBACK_MODEL_NAME", "gemini-2.5-flash")
GOOGLE_SEARCH_TOOLS = [{"google_search": {}}]

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
SCOUT_MODEL = genai.GenerativeModel(
    model_name=GEMINI_MODEL_NAME,
    system_instruction=SCOUT_SYSTEM_PROMPT,
)
PARSER_MODEL = genai.GenerativeModel(model_name=GEMINI_MODEL_NAME)


class GeminiModelNotFoundError(RuntimeError):
    """Raised when a configured Gemini model is not available."""


class GeminiRateLimitError(RuntimeError):
    """Raised when a configured Gemini model is rate-limited."""


async def run_scout(question: str) -> ResearchBrief:
    """Research a strategic question and return a structured Scout brief."""
    raw_narrative = await _generate_grounded_research(question)
    parsed_payload = await _parse_research_brief(question, raw_narrative)
    return ResearchBrief.model_validate(parsed_payload)


async def _generate_grounded_research(question: str) -> str:
    prompt = f"Research this decision question thoroughly: {question}"

    try:
        response = await asyncio.to_thread(
            SCOUT_MODEL.generate_content,
            prompt,
            tools=GOOGLE_SEARCH_TOOLS,
        )
        return _response_text(response)
    except ValueError as exc:
        if "google_search" not in str(exc):
            raise
    except Exception as exc:
        if not (_looks_like_model_not_found(exc) or _looks_like_rate_limit(exc)):
            raise

    return await asyncio.to_thread(
        _generate_grounded_research_rest,
        os.getenv("GEMINI_API_KEY"),
        GEMINI_MODEL_NAME,
        prompt,
    )


async def _parse_research_brief(question: str, raw_narrative: str) -> dict[str, Any]:
    prompt = f"""
Extract structured JSON from the Scout research narrative.

Return only valid JSON matching this schema:
{{
  "question": "string",
  "key_facts": ["string", "string", "string", "string", "string"],
  "market_position": "string",
  "recent_signals": ["string", "string", "string"],
  "raw_narrative": "string"
}}

Rules:
- Use the exact question provided.
- Preserve at least 5 specific key facts.
- Preserve at least 3 recent signals.
- The raw_narrative field must contain the original narrative verbatim.

Question:
{question}

Scout research narrative:
{raw_narrative}
"""

    try:
        response = await asyncio.to_thread(
            PARSER_MODEL.generate_content,
            prompt,
            generation_config={"temperature": 0.1, "response_mime_type": "application/json"},
        )
        return _json_from_text(_response_text(response))
    except GeminiRateLimitError:
        raise
    except Exception as exc:
        if not (_looks_like_model_not_found(exc) or _looks_like_rate_limit(exc)):
            raise

    return await asyncio.to_thread(
        _parse_research_brief_rest,
        os.getenv("GEMINI_API_KEY"),
        GEMINI_FALLBACK_MODEL_NAME,
        prompt,
    )


def _generate_grounded_research_rest(api_key: str | None, model_name: str, prompt: str) -> str:
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in the environment.")

    try:
        response = _post_generate_content(
            api_key=api_key,
            model_name=model_name,
            payload={
                "systemInstruction": {"parts": [{"text": SCOUT_SYSTEM_PROMPT}]},
                "contents": [{"parts": [{"text": prompt}]}],
                "tools": GOOGLE_SEARCH_TOOLS,
            },
        )
    except (GeminiModelNotFoundError, GeminiRateLimitError):
        response = _post_generate_content(
            api_key=api_key,
            model_name=GEMINI_FALLBACK_MODEL_NAME,
            payload={
                "systemInstruction": {"parts": [{"text": SCOUT_SYSTEM_PROMPT}]},
                "contents": [{"parts": [{"text": prompt}]}],
                "tools": GOOGLE_SEARCH_TOOLS,
            },
        )

    return _text_from_rest_response(response)


def _parse_research_brief_rest(api_key: str | None, model_name: str, prompt: str) -> dict[str, Any]:
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
