"""
OpenRouter integration for the Advisor Console.

Handles the real (non-stub) LLM call: takes a list of chat messages and
returns the model's reply plus token usage, so the caller can persist
cost/telemetry data.

Note: this does NOT yet inject a system prompt from Google Docs (FR-02) —
that's the separate grounding/persona pipeline. Right now this is a plain
multi-turn OpenRouter call (FR-01).
"""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"

# OpenRouter uses these two headers for its public leaderboard attribution.
# Not secrets — safe to have sensible defaults.
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "http://localhost:5173")
OPENROUTER_SITE_NAME = os.getenv("OPENROUTER_SITE_NAME", "Advisor Console")

REQUEST_TIMEOUT_SECONDS = 30.0


class LLMError(Exception):
    """Raised whenever the OpenRouter call fails, times out, or returns
    something we don't know how to parse. Callers should catch this and
    show the user a plain-language error instead of a raw stack trace."""
    pass


async def get_chat_completion(messages: list[dict]) -> dict:
    """
    Send a chat history to OpenRouter and return the reply.

    Args:
        messages: list of {"role": "system"|"user"|"assistant", "content": str},
                  in chronological order.

    Returns:
        {"content": str, "prompt_tokens": int, "completion_tokens": int}

    Raises:
        LLMError on any failure (missing key, timeout, non-2xx, bad shape).
    """
    if not OPENROUTER_API_KEY:
        raise LLMError("OPENROUTER_API_KEY is not set")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": OPENROUTER_SITE_URL,
        "X-Title": OPENROUTER_SITE_NAME,
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.post(OPENROUTER_BASE_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as e:
        raise LLMError("OpenRouter request timed out") from e
    except httpx.HTTPStatusError as e:
        raise LLMError(f"OpenRouter returned {e.response.status_code}: {e.response.text}") from e
    except httpx.RequestError as e:
        raise LLMError(f"OpenRouter request failed: {e}") from e

    try:
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
    except (KeyError, IndexError) as e:
        raise LLMError(f"Unexpected OpenRouter response shape: {data}") from e

    return {
        "content": content,
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
    }
