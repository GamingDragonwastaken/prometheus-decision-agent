"""Shared Gemini client helpers used by every PROMETHEUS agent.

The four agent modules used to each carry an identical ~50-line scaffolding
block for the REST fallback path, the model-not-found / rate-limit
classification, and the JSON / text response extraction. This module is the
single home for all of that, so each agent file shrinks to its prompt + the
one function that is actually unique to its role.

Public surface:
- GeminiModelNotFoundError, GeminiRateLimitError exceptions
- post_generate_content(api_key, model_name, payload) -> dict
- response_text(response) -> str  (native SDK Response object)
- text_from_rest_response(response_dict) -> str  (REST API JSON)
- json_from_text(text) -> dict  (strips ``` fences then loads)
- looks_like_model_not_found(exc) -> bool
- looks_like_rate_limit(exc) -> bool

Nothing here knows about specific agent roles or prompts.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx


GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_REST_TIMEOUT_SECONDS = 90


class GeminiModelNotFoundError(RuntimeError):
    """Raised when a configured Gemini model is not available (404)."""


class GeminiRateLimitError(RuntimeError):
    """Raised when the Gemini API rate-limits the request (429)."""


def post_generate_content(
    api_key: str,
    model_name: str,
    payload: dict[str, Any],
    timeout: int = DEFAULT_REST_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """POST a payload to the Gemini REST generateContent endpoint.

    Raises a typed exception on 404 (model not found) and 429 (rate limit) so
    callers can fall back to a different model without re-parsing error
    strings.
    """
    url = f"{GEMINI_API_BASE}/{model_name}:generateContent"
    response = httpx.post(url, params={"key": api_key}, json=payload, timeout=timeout)
    if response.status_code == 404:
        raise GeminiModelNotFoundError(response.text)
    if response.status_code == 429:
        raise GeminiRateLimitError(response.text)
    response.raise_for_status()
    return response.json()


def response_text(response: Any) -> str:
    """Pull the text content from a native-SDK Gemini response object."""
    text = getattr(response, "text", "")
    if not text:
        raise RuntimeError("Gemini returned an empty response.")
    return text


def text_from_rest_response(response: dict[str, Any]) -> str:
    """Pull the text content from a REST-API Gemini response dict."""
    candidates = response.get("candidates", [])
    if not candidates:
        raise RuntimeError("Gemini returned no candidates.")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts).strip()
    if not text:
        raise RuntimeError("Gemini returned an empty response.")
    return text


def json_from_text(text: str) -> dict[str, Any]:
    """Parse JSON from a model response, stripping markdown code fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def looks_like_model_not_found(exc: Exception) -> bool:
    """Heuristic — does this exception look like a 404 / model not found?"""
    message = str(exc).lower()
    return "404" in message or "not found" in message


def looks_like_rate_limit(exc: Exception) -> bool:
    """Heuristic — does this exception look like a 429 / quota exhaustion?"""
    message = str(exc).lower()
    return "429" in message or "too many requests" in message or "resource exhausted" in message
