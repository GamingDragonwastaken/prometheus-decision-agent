"""Scout agent for grounded competitive intelligence research."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import google.generativeai as genai
from dotenv import load_dotenv

from backend.llm import (
    GeminiModelNotFoundError,
    GeminiRateLimitError,
    json_from_text,
    looks_like_model_not_found,
    looks_like_rate_limit,
    post_generate_content,
    response_text,
    text_from_rest_response,
)
from backend.models import Citation, ResearchBrief


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


async def run_scout(question: str) -> ResearchBrief:
    """Research a strategic question and return a structured Scout brief."""
    raw_narrative, citations = await _generate_grounded_research(question)
    parsed_payload = await _parse_research_brief(question, raw_narrative)
    parsed_payload["citations"] = [citation.model_dump() for citation in citations]
    return ResearchBrief.model_validate(parsed_payload)


async def _generate_grounded_research(question: str) -> tuple[str, list[Citation]]:
    prompt = f"Research this decision question thoroughly: {question}"

    try:
        response = await asyncio.to_thread(
            SCOUT_MODEL.generate_content,
            prompt,
            tools=GOOGLE_SEARCH_TOOLS,
        )
        return response_text(response), _citations_from_sdk_response(response)
    except ValueError as exc:
        if "google_search" not in str(exc):
            raise
    except Exception as exc:
        if not (looks_like_model_not_found(exc) or looks_like_rate_limit(exc)):
            raise

    return await asyncio.to_thread(
        _generate_grounded_research_rest,
        os.getenv("GEMINI_API_KEY"),
        GEMINI_MODEL_NAME,
        prompt,
    )


def _citations_from_sdk_response(response: Any) -> list[Citation]:
    """Extract de-duplicated citations from a native-SDK Gemini response."""
    try:
        candidate = response.candidates[0]
        metadata = getattr(candidate, "grounding_metadata", None)
        chunks = getattr(metadata, "grounding_chunks", None) or []
    except (IndexError, AttributeError):
        return []
    return _dedupe_citations(
        Citation(
            uri=getattr(getattr(chunk, "web", None), "uri", "") or "",
            title=getattr(getattr(chunk, "web", None), "title", "") or "",
        )
        for chunk in chunks
    )


def _citations_from_rest_response(response: dict[str, Any]) -> list[Citation]:
    """Extract de-duplicated citations from a REST-API Gemini response dict."""
    candidates = response.get("candidates") or []
    if not candidates:
        return []
    metadata = candidates[0].get("groundingMetadata") or {}
    chunks = metadata.get("groundingChunks") or []
    return _dedupe_citations(
        Citation(
            uri=(chunk.get("web") or {}).get("uri", "") or "",
            title=(chunk.get("web") or {}).get("title", "") or "",
        )
        for chunk in chunks
    )


def _dedupe_citations(citations: Any) -> list[Citation]:
    seen: set[str] = set()
    unique: list[Citation] = []
    for citation in citations:
        if not citation.uri or citation.uri in seen:
            continue
        seen.add(citation.uri)
        unique.append(citation)
    return unique


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
        return json_from_text(response_text(response))
    except GeminiRateLimitError:
        raise
    except Exception as exc:
        if not (looks_like_model_not_found(exc) or looks_like_rate_limit(exc)):
            raise

    return await asyncio.to_thread(
        _parse_research_brief_rest,
        os.getenv("GEMINI_API_KEY"),
        GEMINI_FALLBACK_MODEL_NAME,
        prompt,
    )


def _generate_grounded_research_rest(
    api_key: str | None, model_name: str, prompt: str
) -> tuple[str, list[Citation]]:
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in the environment.")

    try:
        response = post_generate_content(
            api_key=api_key,
            model_name=model_name,
            payload={
                "systemInstruction": {"parts": [{"text": SCOUT_SYSTEM_PROMPT}]},
                "contents": [{"parts": [{"text": prompt}]}],
                "tools": GOOGLE_SEARCH_TOOLS,
            },
        )
    except (GeminiModelNotFoundError, GeminiRateLimitError):
        response = post_generate_content(
            api_key=api_key,
            model_name=GEMINI_FALLBACK_MODEL_NAME,
            payload={
                "systemInstruction": {"parts": [{"text": SCOUT_SYSTEM_PROMPT}]},
                "contents": [{"parts": [{"text": prompt}]}],
                "tools": GOOGLE_SEARCH_TOOLS,
            },
        )

    return text_from_rest_response(response), _citations_from_rest_response(response)


def _parse_research_brief_rest(api_key: str | None, model_name: str, prompt: str) -> dict[str, Any]:
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in the environment.")

    response = post_generate_content(
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
    return json_from_text(text_from_rest_response(response))
