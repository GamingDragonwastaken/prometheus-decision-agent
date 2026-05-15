"""Validate Gemini API access with Google Search grounding."""

from __future__ import annotations

import os
from pprint import pprint

from dotenv import load_dotenv
import google.generativeai as genai
import httpx


PROMPT = "What are the top 3 facts about OpenAI in 2026?"
PRIMARY_MODEL = "gemini-3-flash-preview"
FALLBACK_MODEL = "gemini-2.5-flash"
TOOLS = [{"google_search": {}}]


def generate_with_google_generativeai(model_name: str):
    model = genai.GenerativeModel(model_name=model_name)
    return model.generate_content(PROMPT, tools=TOOLS)


def generate_with_rest(api_key: str, model_name: str) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": PROMPT}]}],
        "tools": TOOLS,
    }
    response = httpx.post(url, params={"key": api_key}, json=payload, timeout=60)
    if response.status_code == 404:
        raise ModelNotFoundError(response.text)
    if response.status_code == 429:
        raise RateLimitError(response.text)
    response.raise_for_status()
    return response.json()


def text_from_rest_response(response: dict) -> str:
    parts = response["candidates"][0]["content"].get("parts", [])
    return "".join(part.get("text", "") for part in parts).strip()


def print_sdk_grounding_metadata(response) -> None:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        print("\nGrounding metadata: not present")
        return

    metadata = getattr(candidates[0], "grounding_metadata", None)
    if not metadata:
        print("\nGrounding metadata: not present")
        return

    print("\nGrounding metadata: present")
    pprint(metadata)


def print_rest_grounding_metadata(response: dict) -> None:
    candidates = response.get("candidates", [])
    if not candidates:
        print("\nGrounding metadata: not present")
        return

    metadata = candidates[0].get("groundingMetadata")
    if not metadata:
        print("\nGrounding metadata: not present")
        return

    print("\nGrounding metadata: present")
    pprint(metadata)


class ModelNotFoundError(RuntimeError):
    """Raised when the requested Gemini model is unavailable."""


class RateLimitError(RuntimeError):
    """Raised when the requested Gemini model is rate-limited."""


def is_model_not_found(exc: Exception) -> bool:
    message = str(exc).lower()
    return "not found" in message or "404" in message


def main() -> None:
    load_dotenv()

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set in the environment.")

    genai.configure(api_key=api_key)

    model_name = PRIMARY_MODEL
    try:
        response = generate_with_google_generativeai(model_name)
        response_text = response.text
        print_metadata = lambda: print_sdk_grounding_metadata(response)
    except ValueError as exc:
        if "google_search" not in str(exc):
            raise

        print(
            "google-generativeai could not serialize tools=[{\"google_search\": {}}]; "
            "using Gemini REST with the same tools payload."
        )
        try:
            response = generate_with_rest(api_key, model_name)
        except ModelNotFoundError as rest_exc:
            if not is_model_not_found(rest_exc):
                raise

            print(f"{PRIMARY_MODEL} failed with model not found; falling back to {FALLBACK_MODEL}.")
            model_name = FALLBACK_MODEL
            response = generate_with_rest(api_key, model_name)
        except RateLimitError:
            print(f"{PRIMARY_MODEL} failed with 429 Too Many Requests; falling back to {FALLBACK_MODEL}.")
            model_name = FALLBACK_MODEL
            response = generate_with_rest(api_key, model_name)

        response_text = text_from_rest_response(response)
        print_metadata = lambda: print_rest_grounding_metadata(response)
    except Exception as exc:
        if not is_model_not_found(exc):
            raise

        print(f"{PRIMARY_MODEL} failed with model not found; falling back to {FALLBACK_MODEL}.")
        model_name = FALLBACK_MODEL
        response = generate_with_google_generativeai(model_name)
        response_text = response.text
        print_metadata = lambda: print_sdk_grounding_metadata(response)

    print(f"Model used: {model_name}")
    print("\nResponse text:")
    print(response_text)
    print_metadata()


if __name__ == "__main__":
    main()
